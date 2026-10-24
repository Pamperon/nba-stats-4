"""FastAPI app. One process for the free-tier MVP; persistent jobs need external storage later."""
import os, secrets, threading, uuid, io, time
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
import player_stats
from cachetools import TTLCache
import logging
logger = logging.getLogger(__name__)

app = FastAPI(title='NBA STATS 4.0', docs_url=None, redoc_url=None)
TOKEN = os.getenv('NBA_STATS_ACCESS_TOKEN', '')
if not TOKEN:
    raise RuntimeError('Set NBA_STATS_ACCESS_TOKEN before starting the server')
if not engine.API_KEY:
    raise RuntimeError('Set ODDSPAPI_API_KEY before starting the server')

jobs = {}
lock = threading.Lock()
headshot_cache = TTLCache(maxsize=80, ttl=86400)
headshot_lock = threading.RLock()

@app.on_event('startup')
def init_storage():
    if storage.configured():
        try:
            storage.initialize()
            logger.info('Persistent PostgreSQL scan storage ready')
        except Exception:
            logger.exception('Persistent storage unavailable; service remains accessible')
    # Independent best-effort fallback while Render is awake. GitHub Actions
    # remains the primary scheduler; Supabase claims deduplicate both.
    threading.Thread(target=_render_scheduler_loop, daemon=True,
                     name='nba-render-scheduler').start()


def _render_scheduler_loop():
    """Recover missed slots if GitHub scheduled events are dropped."""
    import scripts.scheduled_scan as scheduler
    time.sleep(35)  # Wait for Uvicorn to start accepting requests.
    while True:
        try:
            scheduler.run()
        except Exception:
            logger.exception('Render fallback scan scheduler failed')
        time.sleep(600)


def auth(authorization: str = Header(default='')):
    if not secrets.compare_digest(authorization, f'Bearer {TOKEN}'):
        raise HTTPException(401, 'Accesso non autorizzato')

@app.get('/api/health')
def health():
    return {'status':'ok', 'version':'4.0-optimized'}

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
        matches = [f for f in engine.get_fixtures(date) if not engine.fixture_is_completed(f)]
        return [{'id':str(f['fixtureId']), 'home':f.get('participant1Name'), 'away':f.get('participant2Name'), 'time':str(engine.fixture_start_rome(f))} for f in matches]
    except Exception:
        raise HTTPException(502,'Calendario temporaneamente non disponibile')

def do_scan(job_id, date):
    with lock: jobs[job_id]['state']='running'
    try:
        started_at = time.monotonic()
        scan_started_at = datetime.now(ZoneInfo('Europe/Rome')).isoformat()
        season = engine.current_nba_season(datetime.strptime(date,'%Y-%m-%d'))
        fixtures = [f for f in engine.get_fixtures(date) if not engine.fixture_is_completed(f)]
        if not fixtures: raise ValueError('Nessuna partita futura disponibile')
        catalog = engine.get_markets()
        setup_seconds = round(time.monotonic() - started_at, 2)
        analysis_started = time.monotonic()
        def progress(p, label):
            with lock: jobs[job_id].update(progress=round(p*100),stage=label)
        rows, issues, odds_count, player_count, raw, filtered, logs, fixture_reports = engine.finder_scan(fixtures,catalog,season,15,1.01,20.,-100,progress)
        analysis_seconds = round(time.monotonic() - analysis_started, 2)
        serialized_logs = {}
        for name, log in logs.items():
            records=log.copy();records['GAME_DATE']=records['GAME_DATE'].dt.strftime('%Y-%m-%d')
            serialized_logs[name]=records.where(pd.notna(records),None).to_dict('records')
        final_state = 'partial' if any(r['stato'] != 'ok' for r in fixture_reports) else 'done'
        final_stage = 'Parziale' if final_state == 'partial' else 'Completata'
        snapshot = {
            'date': date, 'state': final_state, 'progress': 100, 'stage': final_stage,
            'results': rows, 'issues': issues, 'fixture_reports': fixture_reports,
            'player_logs': serialized_logs, 'fixture_count': len(fixtures),
            'player_count': player_count, 'season': season,
            'scan_started_at': scan_started_at,
            'scan_finished_at': datetime.now(ZoneInfo('Europe/Rome')).isoformat(),
            'odds_api_calls_scan': odds_count,
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
        with lock: jobs[job_id].update(state='error',stage=f'Analisi non completata ({type(exc).__name__})')

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
    result['results'] = [row for row in snapshot.get('results', []) if is_upcoming(row)]
    players = {row.get('Giocatore') for row in result['results']}
    result['player_logs'] = {name: log for name, log in snapshot.get('player_logs', {}).items() if name in players}
    result['fixture_reports'] = []
    result['issues'] = []
    result['player_count'] = len(players)
    result['fixture_count'] = len({row.get('Partita') for row in result['results']})
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
            'scan_started_at': snapshot.get('scan_started_at', 'non registrato'),
            'scan_finished_at': snapshot.get('scan_finished_at', 'non registrato'),
            'status': snapshot.get('state', 'sconosciuto'),
            'odds_api_calls_scan': snapshot.get('odds_api_calls_scan', 'non registrato'),
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
        # Include scheduled NBA days even before player-prop odds have been saved.
        # ESPN is free; a temporary ESPN outage must not hide archived days.
        for offset in range(3):
            day = (today + timedelta(days=offset)).isoformat()
            try:
                if schedule(day)['games']:
                    dates.add(day)
            except HTTPException:
                logger.warning('Cannot check ESPN calendar for %s; retaining archived dates', day)
        return {'dates': [{'date': day} for day in sorted(dates)], 'odds_api_calls': 0}
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
        datetime.strptime(slot, '%Y-%m-%dT%H:%M')
        if len(slot) != 16 or slot[-5:] not in ('00:00', '10:00', '14:00', '18:00', '22:00'):
            raise ValueError('Invalid slot')
    except ValueError:
        raise HTTPException(400, 'Fascia oraria non valida')
    try:
        return {'claimed': storage.claim_slot(slot), 'odds_api_calls': 0}
    except Exception:
        logger.exception('Scan slot claim failed')
        raise HTTPException(503, 'Impossibile prenotare la fascia di scansione')


@app.post('/api/storage/slot/finish', dependencies=[Depends(auth)])
def slot_finish(slot: str = Query(), success: bool = Query()):
    try:
        datetime.strptime(slot, '%Y-%m-%dT%H:%M')
        if len(slot) != 16 or slot[-5:] not in ('00:00', '10:00', '14:00', '18:00', '22:00'):
            raise ValueError('Invalid slot')
    except ValueError:
        raise HTTPException(400, 'Fascia oraria non valida')
    try:
        storage.finish_slot(slot, success)
        return {'ok': True, 'odds_api_calls': 0}
    except Exception:
        logger.exception('Scan slot completion failed')
        raise HTTPException(503, 'Impossibile registrare il completamento')


@app.post('/api/storage/cleanup', dependencies=[Depends(auth)])
def storage_cleanup():
    """Protected, idempotent cleanup; does not contact OddsPapi."""
    try:
        return storage.cleanup_expired(retention_days=7)
    except Exception:
        logger.exception('NBA archive retention cleanup failed')
        raise HTTPException(503, 'Pulizia archivio non riuscita')

@app.post('/api/scan', dependencies=[Depends(auth)])
def scan(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$')):
    try: datetime.strptime(date,'%Y-%m-%d')
    except ValueError: raise HTTPException(400,'Data non valida')
    with lock:
        for job_id, job in jobs.items():
            if job['date']==date and job['state'] in ('queued','running'):
                return {'job_id':job_id,'reused':True}
        if any(job['state'] in ('queued','running') for job in jobs.values()):
            raise HTTPException(409, 'Una scansione è già in corso')
        if len(jobs)>15:
            for old_id in list(jobs):
                if jobs[old_id]['state'] not in ('queued','running'):
                    del jobs[old_id]
                if len(jobs)<=10: break
        job_id=uuid.uuid4().hex
        jobs[job_id]={'date':date,'state':'queued','progress':0,'stage':'In coda'}
    threading.Thread(target=do_scan,args=(job_id,date),daemon=True).start()
    return {'job_id':job_id,'reused':False}

@app.get('/api/scan/{job_id}', dependencies=[Depends(auth)])
def scan_result(job_id: str):
    with lock:
        job = dict(jobs[job_id]) if job_id in jobs else None
    if job is not None:
        return job
    if storage.configured():
        try:
            saved = storage.latest()
            if saved and saved.get('job_id') == job_id:
                return saved
        except Exception:
            logger.exception('Cannot restore scan from database')
    raise HTTPException(404,'Scansione non trovata')

@app.get('/api/scan/{job_id}/csv', dependencies=[Depends(auth)])
def scan_csv(job_id: str):
    with lock: job=jobs.get(job_id)
    if not job or job['state'] not in ('done','partial','save_failed'): raise HTTPException(404,'Analisi non disponibile')
    data=engine.csv_excel_friendly(pd.DataFrame(job['results']))
    return StreamingResponse(io.BytesIO(data),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="nba_stats_4_completo.csv"'})

app.mount('/static',StaticFiles(directory='web'),name='static')
@app.get('/')
def index(): return FileResponse('web/index.html')
