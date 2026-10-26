"""FastAPI app. One process for the free-tier MVP; persistent jobs need external storage later."""
import os, secrets, threading, uuid, io, time, asyncio
from PIL import Image
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import requests
import engine
import storage
import scan_tracking
import player_stats
from cachetools import TTLCache
import logging
logger = logging.getLogger(__name__)

app = FastAPI(title='BasketLab', docs_url=None, redoc_url=None)
TOKEN = os.getenv('NBA_STATS_ACCESS_TOKEN', '')
if not TOKEN:
    raise RuntimeError('Set NBA_STATS_ACCESS_TOKEN before starting the server')
if not engine.API_KEY:
    raise RuntimeError('Set ODDSPAPI_API_KEY before starting the server')

jobs = {}
lock = threading.Lock()
headshot_cache = TTLCache(maxsize=80, ttl=86400)
headshot_lock = threading.RLock()

RUNTIME_ID = uuid.uuid4().hex
shutdown_event = threading.Event()
scan_threads = {}
tracking_ready = False


@app.on_event('startup')
def init_storage():
    global tracking_ready
    if not storage.configured():
        raise RuntimeError('Database required for durable scan/API tracking')
    storage.initialize()
    scan_tracking.initialize()
    import calibration
    calibration.initialize()
    # Uvicorn has not opened its listening port yet. Render keeps the previous
    # instance serving traffic while its already-claimed batch finishes.
    scan_tracking.wait_for_deployment(RUNTIME_ID)
    tracking_ready = True
    threading.Thread(target=_release_guard_when_public, daemon=True, name='nba-deploy-release').start()
    threading.Thread(target=_render_scheduler_loop, daemon=True, name='nba-render-scheduler').start()


def _release_guard_when_public():
    for _ in range(30):
        if shutdown_event.wait(2):
            return
        try:
            response = requests.get('https://nba-stats-4.onrender.com/api/health', timeout=5)
            if response.ok and response.json().get('runtime_instance') == RUNTIME_ID:
                scan_tracking.release_deploy_guard(RUNTIME_ID)
                return
        except Exception:
            logger.warning('Waiting for public routing before releasing deploy guard')
    # Guard expires automatically. This instance may still process new work;
    # only older instances are fenced by the guard's runtime ID.
    logger.warning('Deploy guard retained until automatic expiry')


def _render_scheduler_loop():
    import scripts.scheduled_scan as scheduler
    if shutdown_event.wait(scheduler.seconds_until_check(maximum=35)):
        return
    while not shutdown_event.is_set():
        try:
            scheduler.run(source='render')
        except Exception:
            logger.exception('Render fallback scan scheduler failed')
        shutdown_event.wait(scheduler.seconds_until_check())


@app.on_event('shutdown')
async def drain_scans():
    shutdown_event.set()
    with lock:
        pending = [thread for thread in scan_threads.values() if thread.is_alive()]
    # Normal deploys waited at startup. This bounded drain also helps with
    # restarts; a platform hard kill can still interrupt an unusually long job.
    deadline = time.monotonic() + 20
    for thread in pending:
        await asyncio.to_thread(thread.join, max(0, deadline - time.monotonic()))


def _scan_heartbeat(job_id, stop):
    while not stop.is_set():
        try:
            with lock:
                job = dict(jobs[job_id])
            scan_tracking.heartbeat(job_id, job.get('progress', 0), job.get('stage', 'In elaborazione'))
        except Exception:
            logger.exception('Cannot persist scan heartbeat %s', job_id)
        stop.wait(15)


def auth(authorization: str = Header(default='')):
    if not secrets.compare_digest(authorization, f'Bearer {TOKEN}'):
        raise HTTPException(401, 'Accesso non autorizzato')

@app.get('/api/health')
def health():
    with lock:
        active = sum(job['state'] in ('queued','running') for job in jobs.values())
    return {'status': 'ok', 'version': '4.0-optimized',
            'deployment_commit': os.getenv('RENDER_GIT_COMMIT'),
            'scheduler_revision': 'rome-slots-at-most-once-v2',
            'runtime_instance': RUNTIME_ID, 'scan_tracking_ready': tracking_ready,
            'active_scans': active}

@app.get('/api/session', dependencies=[Depends(auth)])
def session():
    return {'authenticated': True, 'database_configured': storage.configured()}

@app.post('/api/storage/self-test', dependencies=[Depends(auth)])
def storage_self_test():
    try:
        return storage.self_test()
    except Exception:
        logger.exception('Database self-test failed')
        raise HTTPException(503, 'Test database fallito; controlla i log Render')

@app.get('/api/schedule', dependencies=[Depends(auth)])
def schedule(date: str):
    """NBA fixtures from ESPN only; zero OddsPapi calls."""
    try:
        day = datetime.strptime(date, '%Y-%m-%d')
        events = {}
        for offset in (-1, 0):
            us_day = (day + timedelta(days=offset)).strftime('%Y%m%d')
            response = requests.get(
                'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
                params={'dates': us_day, 'limit': 100}, timeout=12)
            response.raise_for_status()
            for event in response.json().get('events', []):
                start = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                rome = start.astimezone(ZoneInfo('Europe/Rome'))
                if rome.strftime('%Y-%m-%d') != date:
                    continue
                teams = (event.get('competitions') or [{}])[0].get('competitors') or []
                home = next((x for x in teams if x.get('homeAway') == 'home'), {})
                away = next((x for x in teams if x.get('homeAway') == 'away'), {})
                if home and away:
                    events[str(event['id'])] = {
                        'home': home.get('team', {}).get('displayName', ''),
                        'away': away.get('team', {}).get('displayName', ''),
                        'time': rome.strftime('%H:%M'),
                        'status': event.get('status', {}).get('type', {}).get('description', ''),
                        'upcoming': event.get('status', {}).get('type', {}).get('state') == 'pre'
                    }
        return {'date': date, 'games': sorted(events.values(), key=lambda x: x['time']),
                'source': 'ESPN', 'odds_api_calls': 0}
    except Exception:
        logger.exception('ESPN schedule unavailable for %s', date)
        raise HTTPException(502, 'Calendario ESPN temporaneamente non disponibile')

@app.get('/api/fixtures', dependencies=[Depends(auth)])
def fixtures(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$')):
    try:
        datetime.strptime(date,'%Y-%m-%d')
        matches = [f for f in engine.get_fixtures(date) if engine.fixture_is_upcoming(f)]
        return [{'id':str(f['fixtureId']), 'home':f.get('participant1Name'), 'away':f.get('participant2Name'), 'time':str(engine.fixture_start_rome(f))} for f in matches]
    except Exception:
        raise HTTPException(502,'Calendario temporaneamente non disponibile')

def do_scan(job_id, date):
    with lock: jobs[job_id]['state']='running'
    engine.set_odds_request_job(job_id)
    heartbeat_stop = threading.Event()
    heartbeat_thread = threading.Thread(target=_scan_heartbeat, args=(job_id, heartbeat_stop), daemon=True)
    try:
        engine.reset_odds_api_request_count()
        heartbeat_thread.start()
        started_at = time.monotonic()
        scan_started_at = datetime.now(ZoneInfo('Europe/Rome')).isoformat()
        season = engine.current_nba_season(datetime.strptime(date,'%Y-%m-%d'))
        fixtures = [f for f in engine.get_fixtures(date) if engine.fixture_is_upcoming(f)]
        if not fixtures: raise ValueError('Nessuna partita futura disponibile')
        catalog = engine.get_markets()
        setup_seconds = round(time.monotonic() - started_at, 2)
        analysis_started = time.monotonic()
        def progress(p, label):
            with lock: jobs[job_id].update(progress=round(p*100),stage=label)
        rows, issues, odds_count, player_count, raw, filtered, logs, fixture_reports = engine.finder_scan(fixtures,catalog,season,15,1.01,20.,-100,progress)
        # Apply calibration only after independent walk-forward validation on
        # previously settled days. Never block the scan on a calibration error.
        calibration_status = {'active': False, 'adjusted': 0}
        if storage.configured():
            try:
                import progressive_calibration
                with storage.connection() as conn:
                    history = conn.execute("""
                        SELECT scan_date,market,probability_bin,n,wins,sum_p,sum_brier
                        FROM nba_calibration_daily
                        WHERE scan_date < %s
                        ORDER BY scan_date,market,probability_bin
                    """, (date,)).fetchall()
                daily = [dict(date=day.isoformat(),market=market,
                              probability_bin=bucket,n=n,wins=wins,sum_p=sp,
                              sum_brier=sb)
                         for day,market,bucket,n,wins,sp,sb in history]
                rows, calibration_status = progressive_calibration.apply(rows, daily)
            except Exception:
                logger.exception('Progressive calibration unavailable; raw probabilities retained')
        analysis_seconds = round(time.monotonic() - analysis_started, 2)
        import availability
        import recommendations
        rows, availability_status = availability.check(rows)
        model_shadow = None
        try:
            import shadow_study
            model_shadow = shadow_study.capture(rows)
        except Exception:
            logger.exception('Parallel model comparison unavailable; live predictions unchanged')
        finally:
            for row in rows:
                row.pop('_shadow_probabilities', None)
        saved_recommendations = recommendations.select(rows)
        serialized_logs = {}
        for name, log in logs.items():
            records=log.copy();records['GAME_DATE']=records['GAME_DATE'].dt.strftime('%Y-%m-%d')
            serialized_logs[name]=records.where(pd.notna(records),None).to_dict('records')
        final_state = 'partial' if any(r['stato'] != 'ok' for r in fixture_reports) else 'done'
        final_stage = 'Parziale' if final_state == 'partial' else 'Completata'
        import minutes_shadow
        minutes_audit = minutes_shadow.audit(rows)
        snapshot = {
            'model_shadow': model_shadow,
            'recommendations': saved_recommendations,
            'availability': availability_status,
            'minutes_audit': minutes_audit,
            'scan_source': jobs[job_id].get('scan_source', 'unknown'),
            'date': date, 'state': final_state, 'progress': 100, 'stage': final_stage,
            'results': rows, 'issues': issues, 'fixture_reports': fixture_reports,
            'calibration': calibration_status,
            'player_logs': serialized_logs, 'fixture_count': len(fixtures),
            'player_count': player_count, 'season': season,
            'scan_started_at': scan_started_at,
            'scan_finished_at': datetime.now(ZoneInfo('Europe/Rome')).isoformat(),
            'odds_api_calls_scan': odds_count,  # Legacy field: counts quote lines, NOT API requests.
            'odds_api_http_requests_scan': engine.odds_api_request_count(),
            'quote_lines_scan': odds_count,
            'timings': {'preparazione_s': setup_seconds,
                        'scansione_s': analysis_seconds,
                        'totale_s': round(time.monotonic()-started_at, 2)}
        }
        with lock:
            jobs[job_id].update(progress=99, stage='Salvataggio su Supabase…')
        try:
            if not storage.configured():
                raise RuntimeError('DATABASE_URL non configurato')
            storage.save(job_id, snapshot)
        except Exception:
            logger.exception('Scan %s completed but cloud persistence failed', job_id)
            with lock:
                jobs[job_id].update(snapshot, state='save_failed', progress=100,
                                    stage='Analisi completata ma NON salvata su Supabase; esporta subito il CSV')
            return
        with lock:
            jobs[job_id].update(snapshot, cloud_saved=True)
    except Exception as exc:
        logger.exception('Scan %s failed for %s', job_id, date)
        with lock: jobs[job_id].update(state='error',stage=f'Analisi non completata ({type(exc).__name__})')
    finally:
        heartbeat_stop.set()
        with lock:
            terminal = dict(jobs[job_id])
            state = terminal['state']
            jobs[job_id]['odds_api_http_requests_scan'] = engine.odds_api_request_count()
        try:
            scan_tracking.finish_attempt(job_id, state, terminal.get('progress', 0), terminal.get('stage', ''))
        except Exception:
            logger.exception('Cannot finalize durable scan attempt %s', job_id)
        engine.set_odds_request_job(None)
        print(f'NBA scan date={date} job={job_id} state={state} '
              f'odds_api_http_requests={engine.odds_api_request_count()}', flush=True)

def visible_snapshot(snapshot):
    """Filter out started games from the public view, without OddsPapi calls."""
    if not snapshot:
        return None
    day = snapshot.get('date')
    if not day:
        return None
    try:
        games = schedule(day)['games']
    except Exception:
        logger.exception('ESPN status unavailable; refusing to publish stale odds')
        raise HTTPException(503, 'Stato partite non verificabile; riprova')
    upcoming = set()
    for game in games:
        if game.get('upcoming'):
            upcoming.add(frozenset((game['home'].casefold().strip(), game['away'].casefold().strip())))
    def is_upcoming(row):
        parts = str(row.get('Partita', '')).split(' - ')
        return len(parts) == 2 and frozenset(p.casefold().strip() for p in parts) in upcoming
    result = dict(snapshot)
    result.pop('model_shadow', None)  # Parallel research must not slow public navigation.
    result['results'] = [row for row in snapshot.get('results', []) if is_upcoming(row)]
    players = {row.get('Giocatore') for row in result['results']}
    result['player_logs'] = {name: log for name, log in snapshot.get('player_logs', {}).items() if name in players}
    result['fixture_reports'] = []
    result['issues'] = []
    result['player_count'] = len(players)
    # Games exist independently of whether the provider offers player odds.
    result['fixture_count'] = len(upcoming)
    return result

@app.get('/api/saved/latest')
def saved_latest(date: str | None = Query(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')):
    if not storage.configured():
        raise HTTPException(503, 'Database non configurato')
    try:
        snapshot = storage.latest(date)
    except Exception:
        logger.exception('Cannot read saved scan')
        raise HTTPException(503, 'Archivio cloud temporaneamente non disponibile')
    if not snapshot:
        raise HTTPException(404, 'Nessuna analisi salvata')
    return visible_snapshot(snapshot)

@app.get('/api/saved/archive')
def saved_archive(date: str = Query(..., pattern=r'^\d{4}-\d{2}-\d{2}$'),
                  include_logs: bool = False):
    """Read-only historical predictions without hiding completed games."""
    try:
        requested = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(400, 'Data non valida')
    if requested > datetime.now(ZoneInfo('Europe/Rome')).date():
        raise HTTPException(400, 'Archivio disponibile solo per date passate')
    if not storage.configured():
        raise HTTPException(503, 'Database non configurato')
    try:
        snapshot = storage.latest(date)
    except Exception:
        logger.exception('Cannot read historical snapshot')
        raise HTTPException(503, 'Archivio cloud temporaneamente non disponibile')
    if not snapshot:
        raise HTTPException(404, 'Nessuna analisi storica salvata')
    return {'date': date, 'historical': True,
            'job_id': snapshot.get('job_id'), 'saved_at': snapshot.get('saved_at'),
            'state': snapshot.get('state'),
            'fixture_count': snapshot.get('fixture_count', 0),
            'player_count': snapshot.get('player_count', 0),
            'results': snapshot.get('results', []),
            'recommendations': snapshot.get('recommendations'),
            'availability': snapshot.get('availability'),
            'calibration': snapshot.get('calibration'),
            'season': snapshot.get('season'),
            'scan_finished_at': snapshot.get('scan_finished_at'),
            **({'player_logs': snapshot.get('player_logs', {}),
                'model_shadow': snapshot.get('model_shadow')} if include_logs else {}),
            'fixture_reports': snapshot.get('fixture_reports', [])}

@app.get('/api/saved/time')
def saved_time(date: str):
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(400, 'Data non valida')
    if not storage.configured():
        raise HTTPException(503, 'Database non configurato')
    try:
        snapshot = storage.latest(date)
        if not snapshot:
            raise HTTPException(404, 'Nessuna analisi salvata')
        timestamp = datetime.fromisoformat(snapshot['saved_at'])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=ZoneInfo('UTC'))
        return {
            'date': date,
            'saved_at_italy': timestamp.astimezone(ZoneInfo('Europe/Rome')).strftime('%d/%m/%Y %H:%M:%S'),
            'scan_source': snapshot.get('scan_source', 'non registrata'),
            'calibration': snapshot.get('calibration', {'active': False, 'adjusted': 0}),
            'scan_started_at': snapshot.get('scan_started_at', 'non registrato'),
            'scan_finished_at': snapshot.get('scan_finished_at', 'non registrato'),
            'status': snapshot.get('state', 'sconosciuto'),
            'odds_api_calls_scan': snapshot.get('odds_api_calls_scan', 'non registrato'),  # Legacy: quote lines, not HTTP requests.
            'quote_lines_scan': snapshot.get('quote_lines_scan', snapshot.get('odds_api_calls_scan', 'non registrato')),
            'odds_api_requests_scan': snapshot.get('odds_api_http_requests_scan', 'non misurate'),
            'odds_api_http_requests_scan': snapshot.get('odds_api_http_requests_scan'),
            'coverage_status': ('completa' if snapshot.get('fixture_reports') and all(item.get('stato') == 'ok' for item in snapshot['fixture_reports']) else 'in_attesa_quote' if snapshot.get('fixture_reports') and all(item.get('stato') in ('ok', 'vuota') for item in snapshot['fixture_reports']) else 'errore_o_dati_incompleti'),
            'fixture_count': snapshot.get('fixture_count', 0),
            'fixture_status_counts': {state: sum(1 for item in snapshot.get('fixture_reports', []) if item.get('stato') == state) for state in ('ok', 'vuota', 'errore', 'in_elaborazione')},
            'fixture_reports': [{'id': item.get('id'), 'partita': item.get('partita'), 'inizio_italia': item.get('inizio_italia'), 'stato': item.get('stato'), 'linee': item.get('linee', 0), 'dettaglio': item.get('dettaglio', ''), 'diagnostica': item.get('diagnostica', {})} for item in snapshot.get('fixture_reports', [])],
            'odds_api_calls': 0
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception('Cannot read scan timestamp')
        raise HTTPException(503, 'Orario scansione non disponibile')

@app.get('/api/saved/dates')
def saved_dates():
    if not storage.configured():
        raise HTTPException(503, 'Database non configurato')
    try:
        today = datetime.now(ZoneInfo('Europe/Rome')).date()
        dates = {item['date'] for item in storage.available_dates() if item['date'] >= today.isoformat()}
        upcoming_dates = set()
        # Include scheduled NBA days even before player-prop odds have been saved.
        # ESPN is free; a temporary ESPN outage must not hide archived days.
        for offset in range(3):
            day = (today + timedelta(days=offset)).isoformat()
            try:
                games = schedule(day)['games']
                if games:
                    dates.add(day)
                if any(game.get('upcoming') for game in games):
                    upcoming_dates.add(day)
            except HTTPException:
                logger.warning('Cannot check ESPN calendar for %s; retaining archived dates', day)
        return {'dates': [{'date': day} for day in sorted(dates)],
                'default_date': min(upcoming_dates) if upcoming_dates else None,
                'odds_api_calls': 0}
    except Exception:
        logger.exception('Cannot list saved dates')
        raise HTTPException(503, 'Archivio temporaneamente non disponibile')

@app.get('/api/players/teams')
def player_teams():
    try: return {'teams': player_stats.catalog(), 'odds_api_calls': 0}
    except Exception:
        logger.exception('NBA teams unavailable')
        raise HTTPException(503, 'Squadre ESPN temporaneamente non disponibili')

@app.get('/api/players/roster')
def player_roster(team_id: str = Query(pattern=r'^[0-9]{1,8}$')):
    try: return {'players': player_stats.roster(team_id), 'odds_api_calls': 0}
    except ValueError as exc: raise HTTPException(400, str(exc))
    except Exception:
        logger.exception('NBA roster unavailable')
        raise HTTPException(503, 'Roster ESPN temporaneamente non disponibile')

# Read-only lookup for historical Dashboard picks without an ESPN athlete ID.
# Uses the same ESPN name normalization and roster index as the analysis engine.
pick_identity_cache = TTLCache(maxsize=1, ttl=21600)
pick_identity_lock = threading.RLock()

@app.get('/api/players/resolve')
def resolve_pick_player(name: str = Query(min_length=2, max_length=100)):
    key = engine.espn_player_key(name)
    with pick_identity_lock:
        index = pick_identity_cache.get('index')
    if index is None:
        try:
            index = engine.finder_player_index(None)
        except Exception:
            logger.exception('Dashboard ESPN identity lookup failed')
            raise HTTPException(503, 'Roster ESPN temporaneamente non disponibile')
        with pick_identity_lock:
            pick_identity_cache['index'] = index
    player = index.get(key)
    if not player:
        raise HTTPException(404, 'Giocatore non identificato nel roster ESPN')
    return {'id': str(player['id']), 'name': player['full_name'], 'team': player['team_name']}

@app.get('/api/players/headshot/{athlete_id}')
def player_headshot(athlete_id: int):
    if athlete_id < 1 or athlete_id > 999999999999:
        raise HTTPException(400, 'ID giocatore non valido')
    with headshot_lock:
        cached = headshot_cache.get(athlete_id)
    if cached is not None:
        return StreamingResponse(io.BytesIO(cached), media_type='image/webp',
                                 headers={'Cache-Control': 'public, max-age=604800, immutable'})
    # The full-resolution ESPN PNG is wasteful for a small circular avatar.
    # Resize and encode as WebP once, then cache the compact result.
    url = f'https://a.espncdn.com/i/headshots/nba/players/full/{athlete_id}.png'
    try:
        response = requests.get(url, timeout=(4, 9), headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200 or not response.headers.get('Content-Type', '').startswith('image/'):
            raise HTTPException(404, 'Fotografia ESPN non disponibile')
        if len(response.content) > 2000000:
            raise HTTPException(502, 'Immagine troppo grande')
        with Image.open(io.BytesIO(response.content)) as original:
            original.thumbnail((180, 180), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            original.convert('RGBA').save(output, format='WEBP', quality=76, method=3)
            content = output.getvalue()
        with headshot_lock:
            headshot_cache[athlete_id] = content
        return StreamingResponse(io.BytesIO(content), media_type='image/webp',
                                 headers={'Cache-Control': 'public, max-age=604800, immutable'})
    except requests.RequestException:
        logger.warning('ESPN headshot unavailable for athlete %s', athlete_id, exc_info=True)
        raise HTTPException(503, 'Fotografia ESPN temporaneamente non disponibile')
    except (OSError, ValueError):
        logger.warning('Invalid ESPN headshot for athlete %s', athlete_id, exc_info=True)
        raise HTTPException(502, 'Fotografia ESPN non elaborabile')

@app.get('/api/players/profile')
def player_profile(team_id: str = Query(pattern=r'^[0-9]{1,8}$'),
                   athlete_id: str = Query(pattern=r'^[0-9]{1,12}$')):
    try:
        return {**player_stats.player_profile(team_id, athlete_id), 'odds_api_calls': 0}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception:
        logger.exception('NBA athlete profile unavailable')
        raise HTTPException(503, 'Profilo ESPN temporaneamente non disponibile')

@app.get('/api/players/team-logs')
def player_team_logs(team_id: str = Query(pattern=r'^[0-9]{1,8}$'),
                     season: str = Query(pattern=r'^[0-9]{4}$')):
    try:
        return {'logs': player_stats.team_cached_logs(team_id, season), 'odds_api_calls': 0}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception:
        logger.exception('Saved team statistics unavailable')
        raise HTTPException(503, 'Statistiche salvate temporaneamente non disponibili')

@app.get('/api/players/log')
def player_log(team_id: str = Query(pattern=r'^[0-9]{1,8}$'),
               athlete_id: str = Query(pattern=r'^[0-9]{1,12}$'),
               season: str = Query(pattern=r'^[0-9]{4}$')):
    try: return {**player_stats.player_log(team_id, athlete_id, season), 'odds_api_calls': 0}
    except ValueError as exc: raise HTTPException(400, str(exc))
    except Exception:
        logger.exception('NBA game log unavailable')
        raise HTTPException(503, 'Statistiche ESPN temporaneamente non disponibili')

@app.post('/api/storage/slot/claim', dependencies=[Depends(auth)])
def slot_claim(slot: str = Query()):
    try:
        from scripts.scheduled_scan import SLOTS
        parsed = datetime.strptime(slot, '%Y-%m-%dT%H:%M')
        if parsed.strftime('%Y-%m-%dT%H:%M') != slot or parsed.minute != 0 or parsed.hour not in SLOTS:
            raise ValueError('Invalid slot')
    except ValueError:
        raise HTTPException(400, 'Fascia oraria non valida')
    try:
        return {'claimed': storage.claim_slot(slot, RUNTIME_ID), 'odds_api_calls': 0}
    except Exception:
        logger.exception('Scan slot claim failed')
        raise HTTPException(503, 'Impossibile prenotare la fascia di scansione')


@app.post('/api/storage/slot/heartbeat', dependencies=[Depends(auth)])
def slot_heartbeat(slot: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:00$')):
    try:
        storage.touch_slot(slot)
        return {'ok': True, 'odds_api_calls': 0}
    except Exception:
        raise HTTPException(503, 'Impossibile aggiornare lo stato della fascia')


@app.post('/api/storage/slot/finish', dependencies=[Depends(auth)])
def slot_finish(slot: str = Query(), success: bool = Query()):
    try:
        from scripts.scheduled_scan import SLOTS
        parsed = datetime.strptime(slot, '%Y-%m-%dT%H:%M')
        if parsed.strftime('%Y-%m-%dT%H:%M') != slot or parsed.minute != 0 or parsed.hour not in SLOTS:
            raise ValueError('Invalid slot')
    except ValueError:
        raise HTTPException(400, 'Fascia oraria non valida')
    try:
        storage.finish_slot(slot, success)
        return {'ok': True, 'odds_api_calls': 0}
    except Exception:
        logger.exception('Scan slot completion failed')
        raise HTTPException(503, 'Impossibile registrare il completamento')


@app.get('/api/calibration/dry-run', dependencies=[Depends(auth)])
def calibration_dry_run(date: str):
    """Read-only ESPN audit of a historical snapshot. Never writes to database."""
    from datetime import date as date_type
    import calibration
    import settle_espn
    try:
        requested = date_type.fromisoformat(date)
    except ValueError:
        raise HTTPException(422, 'Invalid date')
    if requested > datetime.now(ZoneInfo('Europe/Rome')).date():
        raise HTTPException(422, 'Future dates cannot be audited')
    snapshot = storage.earliest_completed(date)
    if not snapshot:
        raise HTTPException(404, 'No completed archived snapshot')
    try:
        verified, eligible = settle_espn.settle_archive(snapshot, date)
        aggregates = calibration.aggregate(verified)
        matched = sum(v['n'] for v in aggregates.values())
        return {'date':date,'job_id':snapshot['job_id'],
                'eligible_predictions':eligible,'verified_predictions':matched,
                'coverage':matched/eligible if eligible else 0,
                'calibration_bins':len(aggregates),
                'can_settle':bool(eligible and matched/eligible >= 0.9),
                'odds_api_calls':0,'database_writes':0}
    except Exception as exc:
        logger.exception('ESPN calibration audit failed for %s', date)
        return {'date':date,'status':'failed','reason':str(exc)[:180],
                'odds_api_calls':0,'database_writes':0}


@app.post('/api/calibration/settle', dependencies=[Depends(auth)])
def calibration_settle():
    """Process up to two archived dates, including today if all games are final."""
    import calibration
    import settle_espn
    today = datetime.now(ZoneInfo('Europe/Rome')).date().isoformat()
    with storage.connection() as conn:
        settled = {r[0].isoformat() for r in conn.execute(
            "SELECT scan_date FROM nba_calibration_settled").fetchall()}
    candidates = [x['date'] for x in reversed(storage.available_dates())
                  if x['date'] <= today and x['date'] not in settled]
    processed = []
    for day in candidates[:2]:
        try:
            snapshot = storage.earliest_completed(day)
            if not snapshot or not snapshot.get('results'):
                processed.append({'date':day,'status':'empty'})
                continue
            verified, expected = settle_espn.settle_archive(snapshot, day)
            import recommendations
            ticket_count = recommendations.settle_snapshots(day)
            result = calibration.settle(day, snapshot['job_id'], verified, expected)
            processed.append({'date':day,'status':'settled', 'recommendation_snapshots': ticket_count, **result})
        except Exception as exc:
            logger.exception('NBA calibration settlement failed for %s', day)
            processed.append({'date':day,'status':'skipped','reason':str(exc)[:160]})
    return {'processed':processed,'pending':max(0,len(candidates)-2),'odds_api_calls':0}

@app.get('/api/calibration/settlement-status', dependencies=[Depends(auth)])
def calibration_settlement_status():
    """Read-only confirmation of committed daily calibration rows."""
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT s.scan_date, s.snapshot_job_id, s.prediction_count,
                   s.matched_count, COUNT(d.market)
            FROM nba_calibration_settled s
            LEFT JOIN nba_calibration_daily d ON d.scan_date = s.scan_date
            GROUP BY s.scan_date, s.snapshot_job_id, s.prediction_count, s.matched_count
            ORDER BY s.scan_date DESC LIMIT 30
        """).fetchall()
    return {'settled': [{'date': day.isoformat(), 'job_id': job,
                         'eligible': expected, 'verified': matched, 'bins': bins}
                        for day, job, expected, matched, bins in rows],
            'odds_api_calls': 0}


@app.get('/api/calibration/summary', dependencies=[Depends(auth)])
def calibration_summary():
    import calibration
    return {'calibration':calibration.summary(),'odds_api_calls':0}


@app.get('/api/calibration/recommendation-results', dependencies=[Depends(auth)])
def recommendation_results(date: str | None = Query(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')):
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT scan_date,snapshot_job_id,report FROM nba_recommendation_results
            WHERE (%s::date IS NULL OR scan_date=%s::date)
            ORDER BY scan_date DESC,settled_at DESC LIMIT 100
        """, (date, date)).fetchall()
    return {'snapshots': [{'date': day.isoformat(), 'job_id': job, 'report': report}
                          for day, job, report in rows], 'odds_api_calls': 0}


@app.get('/api/calibration/performance', dependencies=[Depends(auth)])
def calibration_performance():
    """Descriptive outcomes by market/date/probability bin; read-only."""
    import performance_report
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT scan_date,market,probability_bin,n,wins,sum_p,sum_brier
            FROM nba_calibration_daily ORDER BY scan_date,market,probability_bin
        """).fetchall()
    data = [dict(date=day.isoformat(),market=market,probability_bin=bucket,
                 n=n,wins=wins,sum_p=sp,sum_brier=sb)
            for day,market,bucket,n,wins,sp,sb in rows]
    return performance_report.report(data)


@app.get('/api/calibration/validation', dependencies=[Depends(auth)])
def calibration_validation_report():
    """Leakage-free walk-forward report; never activates a model automatically."""
    import calibration_validation
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT scan_date,market,probability_bin,n,wins,sum_p,sum_brier
            FROM nba_calibration_daily ORDER BY scan_date,market,probability_bin
        """).fetchall()
    data = [dict(date=day.isoformat(),market=market,probability_bin=bucket,
                 n=n,wins=wins,sum_p=sp,sum_brier=sb)
            for day,market,bucket,n,wins,sp,sb in rows]
    return {**calibration_validation.walk_forward(data), 'odds_api_calls':0}


@app.get('/api/calibration/retention-preview', dependencies=[Depends(auth)])
def calibration_retention_preview():
    """Report potentially removable snapshots; does not delete any records."""
    return storage.calibration_retention_preview(retention_days=7)


@app.post('/api/storage/cleanup', dependencies=[Depends(auth)])
def storage_cleanup():
    """Protected, idempotent cleanup; does not contact OddsPapi."""
    try:
        return storage.cleanup_expired(retention_days=7)
    except Exception:
        logger.exception('NBA archive retention cleanup failed')
        raise HTTPException(503, 'Pulizia archivio non riuscita')

@app.get('/api/saved/status')
def saved_status(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$')):
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(400, 'Data non valida')
    try:
        return scan_tracking.day_status(date)
    except Exception:
        logger.exception('Cannot read durable scan status')
        raise HTTPException(503, 'Stato aggiornamento temporaneamente non disponibile')


@app.post('/api/scan', dependencies=[Depends(auth)])
def scan(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$'),
         source: str = Query(default='manual', pattern=r'^(github|render|manual)$'),
         slot: str | None = Query(default=None, pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:00$')):
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(400, 'Data non valida')
    if shutdown_event.is_set():
        raise HTTPException(503, 'Servizio in aggiornamento; nuova scansione rinviata')
    with lock:
        for job_id, job in jobs.items():
            if job['date'] == date and job['state'] in ('queued','running'):
                return {'job_id': job_id, 'reused': True}
        if any(job['state'] in ('queued','running') for job in jobs.values()):
            raise HTTPException(409, 'Una scansione è già in corso')
        job_id = uuid.uuid4().hex
        try:
            reservation = scan_tracking.begin_attempt(job_id, date, RUNTIME_ID, source, slot)
        except scan_tracking.ScanPaused as exc:
            raise HTTPException(503, str(exc))
        except Exception:
            logger.exception('Cannot persist new scan attempt')
            raise HTTPException(503, 'Archivio non disponibile; nessuna scansione avviata')
        if reservation['reused']:
            if reservation['date'] != date:
                raise HTTPException(409, 'Una scansione è già in corso')
            return {'job_id': reservation['job_id'], 'reused': True}
        if len(jobs) > 15:
            for old_id in list(jobs):
                if jobs[old_id]['state'] not in ('queued','running'):
                    del jobs[old_id]
                    scan_threads.pop(old_id, None)
                if len(jobs) <= 10:
                    break
        jobs[job_id] = {'date':date,'state':'queued','progress':0,'stage':'In coda','scan_source':source}
        thread = threading.Thread(target=do_scan, args=(job_id,date), daemon=True)
        scan_threads[job_id] = thread
    try:
        thread.start()
    except Exception:
        with lock:
            jobs[job_id].update(state='error', stage='Impossibile avviare la scansione')
        try:
            scan_tracking.finish_attempt(job_id, 'error', 0, 'Impossibile avviare la scansione')
        except Exception:
            logger.exception('Cannot persist failed worker startup')
        raise HTTPException(503, 'Impossibile avviare la scansione')
    return {'job_id':job_id,'reused':False}

@app.get('/api/scan/{job_id}', dependencies=[Depends(auth)])
def scan_result(job_id: str):
    with lock:
        job = dict(jobs[job_id]) if job_id in jobs else None
    if job is not None:
        return job
    if storage.configured():
        try:
            saved = storage.by_job_id(job_id)
            if saved:
                return saved
            attempt = scan_tracking.attempt(job_id=job_id)
            if attempt:
                return attempt
        except Exception:
            logger.exception('Cannot restore scan from database')
    raise HTTPException(404,'Scansione non trovata')

@app.get('/api/scan/{job_id}/csv', dependencies=[Depends(auth)])
def scan_csv(job_id: str):
    with lock: job=jobs.get(job_id)
    if not job or job['state'] not in ('done','partial','save_failed'): raise HTTPException(404,'Analisi non disponibile')
    data=engine.csv_excel_friendly(pd.DataFrame(job['results']))
    return StreamingResponse(io.BytesIO(data),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="basketlab_completo.csv"'})

app.mount('/static',StaticFiles(directory='web'),name='static')
@app.get('/')
def index(): return FileResponse('web/index.html')

