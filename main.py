"""Single-process FastAPI app with durable PostgreSQL scans and request tracking."""
import os, secrets, threading, uuid, io, time, asyncio
from PIL import Image
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Header, Depends, Query, Request
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse, Response, JSONResponse
from psycopg_pool import PoolTimeout, TooManyRequests, PoolClosed
from web_delivery import VersionedStaticFiles
from fastapi.middleware.gzip import GZipMiddleware
import pandas as pd
import requests
import engine
import storage
import scan_tracking
import audience
import player_stats
from cachetools import TTLCache
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
logger = logging.getLogger(__name__)

app = FastAPI(title='BasketLab', docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=4)
from api_timing import ApiTimingMiddleware
app.add_middleware(ApiTimingMiddleware)


@app.exception_handler(PoolTimeout)
@app.exception_handler(TooManyRequests)
@app.exception_handler(PoolClosed)
async def database_pool_unavailable(request: Request, exc: Exception):
    return JSONResponse(status_code=503,
                        content={'detail': 'Archivio cloud temporaneamente non disponibile. Riprova.'},
                        headers={'Retry-After': '3', 'Cache-Control': 'no-store'})

# Explicit release gate: collecting results must not activate live calibration.
# Change only after a separate review of the accumulated NBA evidence.
LIVE_CALIBRATION_ENABLED = False
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
    storage.open_pool()
    storage.initialize()
    import official_top5
    official_top5.initialize()
    import nba_session_picks
    nba_session_picks.initialize()
    scan_tracking.initialize()
    audience.initialize()
    import calibration
    calibration.initialize()
    # Uvicorn has not opened its listening port yet. Render keeps the previous
    # instance serving traffic while its already-claimed batch finishes.
    scan_tracking.wait_for_deployment(RUNTIME_ID)
    tracking_ready = True
    threading.Thread(target=_release_guard_when_public, daemon=True, name='nba-deploy-release').start()
    threading.Thread(target=_render_scheduler_loop, daemon=True, name='nba-render-scheduler').start()
    threading.Thread(target=_official_publication_loop, daemon=True, name='nba-official-publisher').start()
    threading.Thread(target=_archive_settlement_loop, daemon=True, name='nba-archive-verifier').start()
    from match_prewarm import run as warm_match_history
    threading.Thread(target=warm_match_history, args=(shutdown_event, schedule),
                     daemon=True, name='nba-match-history-warmup').start()


def _archive_settlement_loop():
    """Verify recent published lines independently of the calibration workflow.

    ESPN only, no paid odds calls. Never reselect or alter pregame picks.
    """
    from datetime import timedelta as _timedelta
    if shutdown_event.wait(75):
        return
    while not shutdown_event.is_set():
        try:
            import recommendations
            today = datetime.now(ZoneInfo('Europe/Rome')).date()
            for offset in (2, 1, 0):
                day = (today - _timedelta(days=offset)).isoformat()
                if shutdown_event.is_set():
                    return
                try:
                    updated = recommendations.settle_snapshots(day)
                    logger.info('NBA archive verifier %s: %s snapshots checked', day, updated)
                except Exception:
                    logger.exception('NBA archive verifier failed for %s', day)
        except Exception:
            logger.exception('NBA archive verifier loop failed')
        if shutdown_event.wait(3600):
            return


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


def _official_publication_loop():
    """Publish independently of visitors, with no paid odds-provider calls."""
    import official_top5
    last_attempt = None
    while not shutdown_event.wait(20):
        now = datetime.now(ZoneInfo('Europe/Rome'))
        if now.hour != 18 or now.minute > 20:
            continue
        attempt = now.strftime('%Y-%m-%dT%H:%M')[:16]
        if attempt == last_attempt:
            continue
        last_attempt = attempt
        # Freeze one session across tonight and the following morning.
        try:
            import nba_session_picks
            session_day = now.date().isoformat()
            if nba_session_picks.eligible(session_day) and nba_session_picks.read(session_day) is None:
                nba_session_picks.publish(session_day, nba_publication_session(session_day)['games'], now=now)
        except Exception:
            logger.exception('Combined NBA evening publication attempt failed')
        # Both calendar dates may have an official set due this evening.
        # Tomorrow's overnight fixtures must not wait until tomorrow 18:00.
        for offset in (0, 1):
            day = (now.date() + timedelta(days=offset)).isoformat()
            if not official_top5.eligible_day(day):
                continue
            if nba_session_picks.eligible(day):
                continue
            try:
                if official_top5.get(day) is not None:
                    continue
                games = schedule(day)['games']
                if official_top5.publication_cutoff(day, games) <= now:
                    official_top5.publish(day, games, now=now)
            except Exception:
                logger.exception('Official Top 5 publication attempt failed for %s', day)


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
    await asyncio.to_thread(storage.close_pool)


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

@app.post('/api/audience/event', status_code=204)
async def audience_event(request: Request):
    # Collection is best effort; counts are not billing or audited human traffic.
    origin = request.headers.get('origin', '')
    if origin not in ('https://basketlab.it', 'https://www.basketlab.it',
                      'https://nba-stats-4.onrender.com'):
        return Response(status_code=204)
    ua = request.headers.get('user-agent', '').lower()
    if (request.headers.get('dnt') == '1' or request.headers.get('sec-gpc') == '1'
            or any(word in ua for word in ('bot', 'crawler', 'spider', 'headless', 'uptime'))
            or not audience.allowed()):
        return Response(status_code=204)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 2048:
            return Response(status_code=204)
    try:
        import json
        source, events = audience.validate(json.loads(body))
    except (ValueError, TypeError, UnicodeError):
        return Response(status_code=204)
    try:
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(audience.record, source, events)
    except Exception:
        logger.warning('Aggregate audience counter unavailable')
    return Response(status_code=204)


@app.get('/api/audience/report', dependencies=[Depends(auth)])
def audience_report(days: int = Query(default=30, ge=1, le=90)):
    from fastapi.responses import JSONResponse
    return JSONResponse(audience.report(days), headers={'Cache-Control': 'no-store'})


@app.get('/admin/visite', include_in_schema=False)
def audience_admin():
    return FileResponse('web/audience-admin.html', headers={
        'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
        'Referrer-Policy': 'no-referrer'})


@app.get('/api/health')
def health():
    import match_prewarm
    with lock:
        active = sum(job['state'] in ('queued','running') for job in jobs.values())
    return {'status': 'ok', 'version': '4.0-optimized', 'odds_download_method': 'tournament-v1',
            'live_calibration_enabled': LIVE_CALIBRATION_ENABLED,
            'deployment_commit': os.getenv('RENDER_GIT_COMMIT'),
            'scheduler_revision': 'rome-five-prepublication-slots-v1',
            'scan_slots_italy': ['09:00', '12:00', '14:30', '16:30', '17:30'],
            'runtime_instance': RUNTIME_ID, 'scan_tracking_ready': tracking_ready,
            'active_scans': active, 'history_warmup': match_prewarm.status()}

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

_schedule_scoreboards = TTLCache(maxsize=32, ttl=60)
_schedule_scoreboard_lock = threading.RLock()


def _schedule_scoreboard(us_day):
    with _schedule_scoreboard_lock:
        if us_day in _schedule_scoreboards:
            return _schedule_scoreboards[us_day]
        response = requests.get(
            'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
            params={'dates': us_day, 'limit': 100}, timeout=12)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get('events'), list):
            raise ValueError('Invalid ESPN calendar')
        _schedule_scoreboards[us_day] = payload
        return payload


@app.get('/api/schedule', dependencies=[Depends(auth)])
def schedule(date: str):
    """NBA fixtures from ESPN only; zero OddsPapi calls."""
    try:
        day = datetime.strptime(date, '%Y-%m-%d')
        events = {}
        for offset in (-1, 0):
            us_day = (day + timedelta(days=offset)).strftime('%Y%m%d')
            for event in _schedule_scoreboard(us_day)['events']:
                start = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                rome = start.astimezone(ZoneInfo('Europe/Rome'))
                status_state = event.get('status', {}).get('type', {}).get('state', '')
                # Show previous-day games on today's calendar only while ESPN marks them live.
                if rome.strftime('%Y-%m-%d') != date and not (status_state == 'in' and rome.date() == (day.date() - timedelta(days=1))):
                    continue
                teams = (event.get('competitions') or [{}])[0].get('competitors') or []
                home = next((x for x in teams if x.get('homeAway') == 'home'), {})
                away = next((x for x in teams if x.get('homeAway') == 'away'), {})
                if home and away:
                    events[str(event['id'])] = {
                        'event_id': str(event['id']),
                        'home': home.get('team', {}).get('displayName', ''),
                        'away': away.get('team', {}).get('displayName', ''),
                        'time': rome.strftime('%H:%M'),
                        'start_at': rome.isoformat(),
                        'status': event.get('status', {}).get('type', {}).get('description', ''),
                        'upcoming': status_state == 'pre',
                        'state': status_state,
                        'carried_live': rome.strftime('%Y-%m-%d') != date,
                        'home_score': home.get('score'),
                        'away_score': away.get('score')
                    }
        return {'date': date, 'games': sorted(events.values(), key=lambda x: x['time']),
                'source': 'ESPN', 'odds_api_calls': 0}
    except Exception:
        logger.exception('ESPN schedule unavailable for %s', date)
        raise HTTPException(502, 'Calendario ESPN temporaneamente non disponibile')

def nba_publication_session(day: str):
    """Return the evening-to-next-morning NBA session, in Italian time.

    This is independent of the calendar-date navigation used for match analysis.
    It reads ESPN only and never requests bookmaker odds.
    """
    rome = ZoneInfo('Europe/Rome')
    target = datetime.strptime(day, '%Y-%m-%d').date()
    start = datetime.combine(target, datetime.min.time(), rome).replace(hour=18)
    end = datetime.combine(target + timedelta(days=1), datetime.min.time(), rome).replace(hour=12)
    games = []
    for offset in (0, 1):
        calendar_date = (target + timedelta(days=offset)).isoformat()
        for game in schedule(calendar_date)['games']:
            raw = game.get('start_at')
            if not raw:
                continue
            try:
                tipoff = datetime.fromisoformat(raw).astimezone(rome)
            except (TypeError, ValueError):
                continue
            if start <= tipoff < end:
                games.append({**game, 'calendar_date': calendar_date})
    games.sort(key=lambda game: game['start_at'])
    return {'publication_date': day, 'start_at': start.isoformat(),
            'end_at': end.isoformat(), 'games': games,
            'source': 'ESPN', 'odds_api_calls': 0}


@app.get('/api/nba/boxscore')
def public_nba_boxscore(event_id: str = Query(..., pattern=r'^\d{5,15}$')):
    """ESPN final-game player box score, without bookmaker requests."""
    try:
        response = requests.get(
            'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary',
            params={'event': event_id}, timeout=15)
        response.raise_for_status()
        payload = response.json()
        state = (payload.get('header', {}).get('competitions') or [{}])[0].get('status', {}).get('type', {}).get('state', '')
        if state not in ('post', 'in'):
            raise HTTPException(409, 'Tabellino disponibile durante o dopo la partita')
        competition = (payload.get('header', {}).get('competitions') or [{}])[0]
        quarters = []
        competitors = competition.get('competitors') or []
        by_side = {entry.get('homeAway'): entry for entry in competitors}
        away_lines = by_side.get('away', {}).get('linescores') or []
        home_lines = by_side.get('home', {}).get('linescores') or []
        for index in range(max(len(away_lines), len(home_lines))):
            away_period = away_lines[index] if index < len(away_lines) else {}
            home_period = home_lines[index] if index < len(home_lines) else {}
            quarters.append({
                'period': index + 1,
                'label': f'Q{index + 1}' if index < 4 else f'OT{index - 3}',
                'away': away_period.get('displayValue', away_period.get('value')),
                'home': home_period.get('displayValue', home_period.get('value')),
            })
        teams = []
        for group in payload.get('boxscore', {}).get('players', []):
            team = group.get('team', {}).get('displayName', '')
            players = []
            for statgroup in group.get('statistics', []):
                labels = [str(x).upper() for x in statgroup.get('labels', [])]
                for entry in statgroup.get('athletes', []):
                    stats = entry.get('stats') or []
                    def value(*keys):
                        for key in keys:
                            if key in labels:
                                idx = labels.index(key)
                                return str(stats[idx]) if idx < len(stats) else '—'
                        return '—'
                    athlete = entry.get('athlete') or {}
                    players.append({'name': athlete.get('displayName', ''),
                                    'minutes': value('MIN'), 'points': value('PTS'),
                                    'rebounds': value('REB'), 'assists': value('AST')})
            teams.append({'team': team, 'players': players})
        return {'event_id': event_id, 'teams': teams, 'quarters': quarters, 'state': state, 'source': 'ESPN', 'odds_api_calls': 0}
    except HTTPException:
        raise
    except Exception:
        logger.exception('ESPN boxscore unavailable for %s', event_id)
        raise HTTPException(502, 'Tabellino ESPN temporaneamente non disponibile')


@app.get('/api/nba/quote-coverage')
def nba_quote_coverage(date: str = Query(..., pattern=r'^\d{4}-\d{2}-\d{2}$')):
    """Recent observed quote coverage by fixture, independent of UI dropdown."""
    if not storage.configured():
        return {'date': date, 'fixtures': []}
    rows = storage.recent_fixture_coverage(date, max_age_hours=24)
    return {'date': date, 'fixtures': sorted({
        str(row.get('Partita') or '').strip() for row in rows
        if str(row.get('Partita') or '').strip()
    })}


@app.get('/api/nba/fixtures')
def public_nba_fixtures(date: str = Query(..., pattern=r'^\d{4}-\d{2}-\d{2}$')):
    """Public ESPN fixtures by Italian tipoff date, independent of odds."""
    try:
        return schedule(date)
    except ValueError:
        raise HTTPException(400, 'Data non valida')


@app.get('/api/nba/publication-session')
def publication_session(date: str = Query(..., pattern=r'^\d{4}-\d{2}-\d{2}$'), upcoming: bool = False):
    """Read-only session fixture manifest; not yet an official picks endpoint."""
    if upcoming:
        from session_window import next_publication_session
        _, manifest = next_publication_session(datetime.strptime(date, '%Y-%m-%d').date(),
                                               datetime.now(ZoneInfo('Europe/Rome')), nba_publication_session)
        return manifest
    return nba_publication_session(date)


@app.get('/api/picks/session')
def session_picks(compact: bool = False):
    """One publication date and one immutable official set, regardless of tipoff date."""
    import nba_session_picks
    import recommendations
    now = datetime.now(ZoneInfo('Europe/Rome'))
    today = now.date()
    # Retain yesterday's overnight session only while one of its games is still upcoming.
    # Once all its fixtures have tipped off, show today's upcoming session immediately.
    day = today.isoformat()
    if now.hour < 12:
        previous_day = (today - timedelta(days=1)).isoformat()
        previous_manifest = nba_publication_session(previous_day)
        if any(g.get('upcoming') and g.get('start_at') and
               datetime.fromisoformat(g['start_at']) > now
               for g in previous_manifest['games']):
            day = previous_day
    from session_window import next_publication_session
    day, manifest = next_publication_session(datetime.strptime(day, '%Y-%m-%d').date(), now, nba_publication_session)
    official = nba_session_picks.read(day) if nba_session_picks.eligible(day) else None
    # Publish on demand only when due; no paid API calls.
    if official is None and nba_session_picks.eligible(day) and now >= nba_session_picks.cutoff_for(day):
        official = nba_session_picks.publish(day, manifest['games'], now=now)
    allowed = {frozenset((g['home'].casefold().strip(),g['away'].casefold().strip())): g
               for g in manifest['games']}
    results, seen = [], set()
    for calendar_date in (day, (datetime.strptime(day,'%Y-%m-%d')+timedelta(days=1)).strftime('%Y-%m-%d')):
        # Merge recent scans by fixture: partial updates must not hide games
        # that had valid odds in an earlier scan. Official picks stay immutable.
        for row in storage.recent_fixture_coverage(calendar_date, max_age_hours=24):
            parts = str(row.get('Partita') or '').split(' - ')
            if len(parts) != 2:
                continue
            game = allowed.get(frozenset(x.casefold().strip() for x in parts))
            if not game or not game.get('upcoming'):
                continue
            try:
                tipoff = datetime.fromisoformat(game['start_at'])
            except (ValueError, TypeError):
                continue
            if tipoff <= now:
                continue
            key = (row.get('Partita'),row.get('Giocatore'),row.get('Mercato'),row.get('Linea'),row.get('Scelta'))
            if key in seen:
                continue
            seen.add(key)
            results.append(row)
    single = official['single'] if official else recommendations.select_single(results)
    preliminary = [] if official else recommendations.select_daily(results)['lines']
    if single:
        sid = str(single.get('ESPN ID') or single.get('Giocatore') or '').strip().casefold()
        preliminary = [p for p in preliminary if str(p.get('ESPN ID') or p.get('Giocatore') or '').strip().casefold()!=sid]
    quote_count = len(results)
    player_count = len({r.get('Giocatore') for r in results})
    # Metadata only: retain the update timestamp without loading full quote snapshots.
    session_dates = {day, (datetime.strptime(day,'%Y-%m-%d')+timedelta(days=1)).strftime('%Y-%m-%d')}
    try:
        saved_at = max((item['saved_at'] for item in storage.available_dates()
                        if item['date'] in session_dates and item.get('saved_at')), default=None)
    except Exception:
        logger.warning('Session update timestamp unavailable', exc_info=True)
        saved_at = None
    # The forecast page already has every selected row in its frozen picks.
    # Quote exploration uses saved/latest, so compact clients need only counts.
    return {'date':day,'publication_date':day,'saved_at':saved_at,'session_start_at':manifest['start_at'],
            'session_end_at':manifest['end_at'],'results':[] if compact else results,
            'quote_count': quote_count, 'publication_cutoff_at': nba_session_picks.cutoff_for(day).isoformat(),
            'recommendations':{'policy':'fixed-1800-v1','lines':official['lines'] if official else []},
            'official_top5':official,'official_top5_pending':official is None,
            'official_single':official['single'] if official else None,
            'official_single_pending':official is None,
            'preliminary_top5':preliminary[:10] if official is None else [],
            'preliminary_single':single if official is None else None,
            'fixture_count':len(manifest['games']),
            'player_count':player_count,
            'odds_api_calls':0}


_match_form_cache = TTLCache(maxsize=40, ttl=1800)
_match_form_lock = threading.RLock()
import match_history
_ODDS_NOT_LOADED = object()

def _cached_match_moneyline(date, team_a, team_b, envelope=_ODDS_NOT_LOADED):
    """Read only the existing saved OddsPapi feed; never trigger a paid call."""
    if not storage.configured():
        return None
    try:
        if envelope is _ODDS_NOT_LOADED:
            envelope = storage.cache_read("odds:nba:bet365.it:v1", max_age_hours=12)
        if not isinstance(envelope, dict):
            return None
        for fixture in (envelope.get("data") or {}).values():
            def canonical_team(value):
                name = str(value or "").casefold().strip()
                return "los angeles clippers" if name in ("la clippers", "los angeles clippers") else name
            if {canonical_team(fixture.get("participant1Name")), canonical_team(fixture.get("participant2Name"))} != {canonical_team(team_a), canonical_team(team_b)}:
                continue
            start = engine.fixture_start_rome(fixture)
            if start is None or start.date().isoformat() != date:
                continue
            book = (fixture.get("bookmakerOdds") or {}).get("bet365.it") or {}
            if book.get("bookmakerIsActive") is not True or book.get("suspended"):
                continue
            market = (book.get("markets") or {}).get("111") or {}
            if market.get("marketActive") is not True:
                continue
            outcomes = market.get("outcomes") or {}
            prices = []
            for outcome_id in ("111", "112"):
                item = ((outcomes.get(outcome_id) or {}).get("players") or {}).get("0") or {}
                price = item.get("price")
                if isinstance(price, bool) or not isinstance(price, (int, float)) or not 1 < price < 1000:
                    break
                if item.get("active") is False:
                    break
                prices.append(float(price))
            if len(prices) == 2:
                return prices if canonical_team(fixture.get("participant1Name")) == canonical_team(team_a) else prices[::-1]
    except Exception:
        logger.exception("Cannot read saved match winner odds")
    return None


def _cached_match_fixture_meta(date, team_a, team_b, envelope=_ODDS_NOT_LOADED):
    """Fixture time and cached odds timestamp without additional provider requests."""
    try:
        if envelope is _ODDS_NOT_LOADED:
            envelope = storage.cache_read("odds:nba:bet365.it:v1", max_age_hours=12)
        if not isinstance(envelope, dict):
            return {}
        def canonical(name):
            name = str(name or "").casefold().strip()
            return "los angeles clippers" if name == "la clippers" else name
        requested = {canonical(team_a), canonical(team_b)}
        for fixture in (envelope.get("data") or {}).values():
            if {canonical(fixture.get("participant1Name")), canonical(fixture.get("participant2Name"))} != requested:
                continue
            start = engine.fixture_start_rome(fixture)
            if start and start.date().isoformat() == date:
                return {"fixture_time": start.isoformat(),
                        "odds_cached_at": envelope.get("fetched_at")}
    except Exception:
        logger.exception("Could not load cached fixture metadata")
    return {}


def _match_market_data(date, team_a, team_b):
    """Use one saved envelope for both price and time; never fetch provider odds."""
    envelope = None
    if storage.configured():
        try:
            envelope = storage.cache_read("odds:nba:bet365.it:v1", max_age_hours=12)
        except Exception:
            logger.warning('Saved match odds unavailable', exc_info=True)
    return {'moneyline_odds': _cached_match_moneyline(date, team_a, team_b, envelope),
            **_cached_match_fixture_meta(date, team_a, team_b, envelope)}


@app.get('/api/match/form')
def match_form(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$'),
               team_a: str = Query(min_length=2, max_length=80),
               team_b: str = Query(min_length=2, max_length=80)):
    """Verified final ESPN scores only; never infers a win probability."""
    try:
        target = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(400, 'Data non valida')
    if team_a.casefold() == team_b.casefold():
        raise HTTPException(400, 'Le squadre devono essere diverse')
    key = (date, team_a.casefold(), team_b.casefold())
    with _match_form_lock:
        cached = _match_form_cache.get(key)
    if cached is not None:
        return {**cached, **_match_market_data(date, team_a, team_b)}
    try:
        events, failed_days = match_history.load_window(target)
        if failed_days == 21:
            raise HTTPException(503, 'Risultati ESPN temporaneamente non disponibili')
        games = []
        for event in events:
            if event.get('status', {}).get('type', {}).get('state') != 'post':
                continue
            competitors = (event.get('competitions') or [{}])[0].get('competitors') or []
            if len(competitors) != 2:
                continue
            try:
                score_a, score_b = [int(c.get('score')) for c in competitors]
                event_date = datetime.fromisoformat(event['date'].replace('Z', '+00:00')).date()
            except (ValueError, TypeError, KeyError):
                continue
            if event_date >= target:
                continue
            names = [c.get('team', {}).get('displayName', '') for c in competitors]
            games.append({'date': event_date.isoformat(), 'teams': names, 'scores': [score_a, score_b], 'id': str(event.get('id', ''))})
        games.sort(key=lambda g: (g['date'], g['id']), reverse=True)
        def team_stats(name):
            sample = [g for g in games if name in g['teams']][:5]
            wins = sum(g['scores'][g['teams'].index(name)] > g['scores'][1-g['teams'].index(name)] for g in sample)
            points = [g['scores'][g['teams'].index(name)] for g in sample]
            return {'team': name, 'games': len(sample), 'wins': wins,
                    'losses': len(sample)-wins,
                    'avg_points': round(sum(points)/len(points), 1) if points else None,
                    'results': [{'date': g['date'], 'opponent': g['teams'][1-g['teams'].index(name)],
                                 'scored': g['scores'][g['teams'].index(name)],
                                 'allowed': g['scores'][1-g['teams'].index(name)]} for g in sample]}
        h2h = [g for g in games if set(g['teams']) == {team_a, team_b}][:5]
        result = {'source': 'ESPN', 'window_days': 21, 'odds_api_calls': 0,
                  'teams': [team_stats(team_a), team_stats(team_b)],
                  'h2h': [{'date': g['date'], 'teams': g['teams'], 'scores': g['scores']} for g in h2h]}
        result['history_complete'] = failed_days == 0
        if not failed_days:
            with _match_form_lock:
                _match_form_cache[key] = result
        return {**result, **_match_market_data(date, team_a, team_b)}
    except requests.RequestException:
        logger.warning('ESPN historical scoreboard temporarily unavailable', exc_info=True)
        raise HTTPException(503, 'Risultati storici ESPN temporaneamente non disponibili')

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
        odds_batch = engine.get_tournament_odds(jobs[job_id].get('scan_slot'), catalog=catalog)
        fixtures = [f for f in engine.get_fixtures(date, odds_batch=odds_batch) if engine.fixture_is_upcoming(f)]
        if not fixtures:
            raise ValueError('Nessuna partita futura disponibile nel calendario aggiornato')
        setup_seconds = round(time.monotonic() - started_at, 2)
        analysis_started = time.monotonic()
        def progress(p, label):
            with lock: jobs[job_id].update(progress=round(p*100),stage=label)
        rows, issues, odds_count, player_count, raw, filtered, logs, fixture_reports = engine.finder_scan(fixtures,catalog,season,15,1.01,20.,-100,progress,odds_batch=odds_batch)
        # Apply calibration only after independent walk-forward validation on
        # previously settled days. Never block the scan on a calibration error.
        calibration_status = {'active': False, 'adjusted': 0}
        if LIVE_CALIBRATION_ENABLED and storage.configured():
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
        saved_recommendations = recommendations.select_daily(rows)
        serialized_logs = {}
        for name, log in logs.items():
            records=log.copy();records['GAME_DATE']=records['GAME_DATE'].dt.strftime('%Y-%m-%d')
            serialized_logs[name]=records.where(pd.notna(records),None).to_dict('records')
        minutes_experiment = None
        try:
            import minutes_research
            minutes_experiment = minutes_research.capture(
                rows, serialized_logs, datetime.now(ZoneInfo('UTC')).isoformat())
        except Exception:
            logger.exception('Minutes experiment unavailable; live predictions unchanged')
        final_state = 'partial' if any(r['stato'] != 'ok' for r in fixture_reports) else 'done'
        final_stage = 'Parziale' if final_state == 'partial' else 'Completata'
        import minutes_shadow
        minutes_audit = minutes_shadow.audit(rows)
        snapshot = {
            'model_shadow': model_shadow,
            'recommendations': saved_recommendations,
            'availability': availability_status,
            'minutes_audit': minutes_audit,
            'minutes_research': minutes_experiment,
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
            'odds_download_method': 'tournament',
            'odds_feed_source': odds_batch['source'],
            'odds_feed_fetched_at': datetime.fromtimestamp(odds_batch['fetched_at'], ZoneInfo('UTC')).isoformat(),
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
            # The durable snapshot owns results and history. Avoid accumulating
            # up to 16 full copies in the 512 MiB Render instance.
            jobs[job_id].update({key: snapshot[key] for key in (
                'date', 'state', 'progress', 'stage', 'scan_started_at',
                'scan_finished_at', 'odds_api_http_requests_scan')}, cloud_saved=True)
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
    result.pop('minutes_research', None)
    result['results'] = [row for row in snapshot.get('results', []) if is_upcoming(row)]
    players = {row.get('Giocatore') for row in result['results']}
    result['player_logs'] = {name: log for name, log in snapshot.get('player_logs', {}).items() if name in players}
    result['fixture_reports'] = []
    result['issues'] = []
    result['player_count'] = len(players)
    # Games exist independently of whether the provider offers player odds.
    result['fixture_count'] = len(upcoming)
    now = datetime.now(ZoneInfo('UTC'))
    starts = []
    for game in games:
        if not game.get('upcoming') or not game.get('start_at'):
            continue
        start = datetime.fromisoformat(game['start_at'])
        # If ESPN still reports pregame after the announced start (a delay),
        # check again in a minute rather than creating an immediate reload loop.
        starts.append(start if start > now else now + timedelta(seconds=60))
    result['visibility_valid_until'] = min(starts).isoformat() if starts else None
    return result

_nba_news_cache = TTLCache(maxsize=1, ttl=600)
_nba_news_lock = threading.Lock()


_nba_news_last = TTLCache(maxsize=1, ttl=86400)


def _pianeta_basket_articles(html):
    from html.parser import HTMLParser
    from urllib.parse import urljoin, urlsplit

    origin = 'https://www.pianetabasket.com/nba'

    class Headlines(HTMLParser):
        def __init__(self):
            super().__init__()
            self.url = None
            self.parts = []
            self.articles = {}
            self.images = {}

        def handle_starttag(self, tag, attrs):
            if tag == 'img' and self.url:
                image = urljoin(origin, dict(attrs).get('src') or '')
                parsed_image = urlsplit(image)
                if (parsed_image.scheme == 'https' and parsed_image.hostname in {
                        'r.testifier.nl', 's3-newsifier.ams3.digitaloceanspaces.com',
                        'www.pianetabasket.com'}):
                    self.images[self.url] = image
            if tag != 'a':
                return
            parsed = urlsplit(urljoin(origin, dict(attrs).get('href') or ''))
            self.url = None
            self.parts = []
            if (parsed.netloc == 'www.pianetabasket.com' and parsed.scheme == 'https'
                    and parsed.path.startswith('/nba/') and parsed.path.rstrip('/') != '/nba'
                    and not parsed.fragment and not parsed.query):
                self.url = parsed.geturl()

        def handle_data(self, data):
            if self.url:
                self.parts.append(data)

        def handle_endtag(self, tag):
            if tag == 'a' and self.url:
                title = ' '.join(' '.join(self.parts).split())
                if len(title) >= 16:
                    self.articles.setdefault(self.url, {
                        'title': title, 'url': self.url, 'image': None, 'published': None,
                    })
                self.url = None

    parser = Headlines()
    parser.feed(html)
    parser.close()
    articles = list(parser.articles.values())[:24]
    for article in articles:
        article['image'] = parser.images.get(article['url'])
    return articles


@app.get('/api/nba/news')
def nba_news():
    """Expose headlines linking to Pianeta Basket's NBA coverage."""
    with _nba_news_lock:
        cached = _nba_news_cache.get('current')
        if cached is not None:
            return cached
        try:
            response = requests.get('https://www.pianetabasket.com/nba', timeout=8)
            response.raise_for_status()
            articles = _pianeta_basket_articles(response.text)
            if len(articles) < 4:
                raise ValueError('Insufficient NBA headlines')
        except (requests.RequestException, ValueError) as error:
            logging.getLogger(__name__).warning('Pianeta Basket news: %s', error)
            cached = _nba_news_last.get('current')
            if cached is not None:
                return cached
            raise HTTPException(503, 'Notizie Pianeta Basket temporaneamente non disponibili') from None
        result = {'source': 'Pianeta Basket', 'articles': articles,
                  'updated_at': datetime.now(ZoneInfo('UTC')).isoformat()}
        _nba_news_cache['current'] = result
        _nba_news_last['current'] = result
        return result


_nba_updates_cache = TTLCache(maxsize=1, ttl=300)
_nba_updates_lock = threading.Lock()


@app.get('/api/nba/updates')
def nba_updates():
    """Return current ESPN injury reports independently of the odds scanner."""
    import availability
    with _nba_updates_lock:
        cached = _nba_updates_cache.get('current')
        if cached is not None:
            return cached
        try:
            response = requests.get(availability.URL, timeout=8)
            response.raise_for_status()
            payload = response.json()
            timestamp = datetime.fromisoformat(payload['timestamp'].replace('Z', '+00:00'))
            age = (datetime.now(ZoneInfo('UTC')) - timestamp).total_seconds()
            if payload.get('status') != 'success' or not 0 <= age <= 1800:
                raise ValueError('Unverified injury report')
            updates = []
            for group in payload['injuries']:
                team = group.get('displayName') or group.get('team', {}).get('displayName')
                if not team:
                    continue
                for item in group['injuries']:
                    player = item['athlete'].get('displayName')
                    status = str(item.get('status') or '').strip().lower()
                    if player and status in {'out', 'doubtful', 'questionable', 'day-to-day', 'suspension'}:
                        updates.append({'team': team, 'player': player, 'status': status})
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
            raise HTTPException(503, 'Aggiornamenti ESPN temporaneamente non disponibili') from None
        result = {'source': 'ESPN', 'report_at': timestamp.isoformat(), 'updates': updates}
        _nba_updates_cache['current'] = result
        return result


@app.get('/api/saved/latest')
def saved_latest(date: str | None = Query(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$'),
                 compact: bool = False):
    if not storage.configured():
        raise HTTPException(503, 'Database non configurato')
    try:
        snapshot = storage.latest(date)
    except Exception:
        logger.exception('Cannot read saved scan')
        raise HTTPException(503, 'Archivio cloud temporaneamente non disponibile')
    if not snapshot:
        raise HTTPException(404, 'Nessuna analisi salvata')
    # Live player-quote explorer must preserve fixture coverage across partial
    # scans. Historical snapshots and immutable official picks remain untouched.
    rome_today = datetime.now(ZoneInfo('Europe/Rome')).date()
    snapshot_day = snapshot.get('date')
    if snapshot_day and rome_today <= datetime.strptime(snapshot_day, '%Y-%m-%d').date() < rome_today + timedelta(days=7):
        merged_rows = storage.recent_fixture_coverage(snapshot_day, max_age_hours=24)
        if merged_rows:
            snapshot = {**snapshot, 'results': merged_rows}
    visible = visible_snapshot(snapshot)
    import official_top5
    if official_top5.eligible_day(visible['date']):
        now = datetime.now(ZoneInfo('Europe/Rome'))
        official = official_top5.get(visible['date'])
        if official is None and visible['date'] in {
                now.date().isoformat(), (now.date() + timedelta(days=1)).isoformat()}:
            try:
                games = schedule(visible['date'])['games']
                if now >= official_top5.publication_cutoff(visible['date'], games):
                    official = official_top5.publish(visible['date'], games, now=now)
            except Exception:
                logger.exception('Cannot publish immutable daily Top 5')
                raise HTTPException(503, 'Pubblicazione Top 5 temporaneamente non disponibile')
        # Provisional picks are distinct from immutable official selections.
        # Never include future-started games or re-rank official picks.
        preliminary = snapshot.get('recommendations', {}).get('lines', [])
        if official is None:
            import recommendations
            valid_rows = visible.get('results', [])
            # Reapply current quality thresholds to older saved snapshots.
            eligible = recommendations.select_daily(valid_rows).get('lines', [])
            visible['preliminary_top5'] = eligible[:10]
        else:
            visible['preliminary_top5'] = []
        visible['recommendations'] = {'policy': 'fixed-1800-v1',
                                      'lines': official['lines'] if official else []}
        visible['official_top5'] = official
        visible['official_top5_pending'] = official is None
        import recommendations
        import daily_single_archive
        single = daily_single_archive.read(visible['date'])
        if official is None:
            visible['preliminary_single'] = recommendations.select_single(visible.get('results', []))
        else:
            visible['preliminary_single'] = None
        visible['official_single'] = single.get('selection') if single.get('published') else None
        visible['official_single_pending'] = official is None
        if official is None and visible.get('preliminary_single'):
            single_id = str(visible['preliminary_single'].get('ESPN ID') or
                            visible['preliminary_single'].get('Giocatore') or '').strip().casefold()
            visible['preliminary_top5'] = [
                pick for pick in visible['preliminary_top5']
                if str(pick.get('ESPN ID') or pick.get('Giocatore') or '').strip().casefold() != single_id
            ][:10]
    if compact:
        import public_payload
        visible = {**visible, 'player_logs': public_payload.explanation_logs(visible)}
    return visible

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
            'odds_download_method': snapshot.get('odds_download_method', 'per-fixture'),
            'odds_feed_source': snapshot.get('odds_feed_source'),
            'odds_feed_fetched_at': snapshot.get('odds_feed_fetched_at'),
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
        if not upcoming_dates:
            from session_window import scan_schedules
            try:
                future_schedules = scan_schedules(today, schedule)
            except RuntimeError:
                logger.warning('Cannot discover next NBA date; retaining archived dates')
                future_schedules = []
            for future_day, payload in future_schedules:
                if any(game.get('upcoming') for game in payload['games']):
                    dates.add(future_day);upcoming_dates.add(future_day)
        return {'dates': [{'date': day} for day in sorted(dates)],
                'default_date': min(upcoming_dates) if upcoming_dates else None,
                'odds_api_calls': 0, 'session_picks_enabled': True}
    except Exception:
        logger.exception('Cannot list saved dates')
        raise HTTPException(503, 'Archivio temporaneamente non disponibile')

@app.get('/api/players/teams')
def player_teams():
    try: return {'teams': player_stats.catalog(), 'odds_api_calls': 0}
    except Exception:
        logger.exception('NBA teams unavailable')
        raise HTTPException(503, 'Squadre ESPN temporaneamente non disponibili')

@app.get('/api/players/directory')
def player_directory():
    try: return {'players': player_stats.directory(), 'odds_api_calls': 0}
    except Exception:
        logger.exception('NBA player directory unavailable')
        raise HTTPException(503, 'Ricerca giocatori temporaneamente non disponibile')

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

@app.get('/api/players/game')
def player_game_details(event_id: str = Query(pattern=r'^[0-9]{1,12}$')):
    try:
        return {**player_stats.game_details(event_id), 'odds_api_calls': 0}
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception:
        logger.warning('NBA final score temporarily unavailable')
        raise HTTPException(503, 'Risultato ESPN temporaneamente non disponibile')


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
        from scripts.scheduled_scan import valid_slot
        if not valid_slot(slot):
            raise ValueError('Invalid slot')
    except ValueError:
        raise HTTPException(400, 'Fascia oraria non valida')
    try:
        return {'claimed': storage.claim_slot(slot, RUNTIME_ID), 'odds_api_calls': 0}
    except Exception:
        logger.exception('Scan slot claim failed')
        raise HTTPException(503, 'Impossibile prenotare la fascia di scansione')


@app.post('/api/storage/slot/heartbeat', dependencies=[Depends(auth)])
def slot_heartbeat(slot: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$')):
    from scripts.scheduled_scan import valid_slot
    if not valid_slot(slot):
        raise HTTPException(400, 'Slot non valido')
    try:
        storage.touch_slot(slot)
        return {'ok': True, 'odds_api_calls': 0}
    except Exception:
        raise HTTPException(503, 'Impossibile aggiornare lo stato della fascia')


@app.post('/api/storage/slot/finish', dependencies=[Depends(auth)])
def slot_finish(slot: str = Query(), success: bool = Query()):
    try:
        from scripts.scheduled_scan import valid_slot
        if not valid_slot(slot):
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
    # Archive verification is independent from calibration and must also run
    # for dates already calibrated, including the official Top 5 and single.
    import recommendations
    archive_updates = []
    for archive_day in [item['date'] for item in reversed(storage.available_dates())][:14]:
        if archive_day > today:
            continue
        try:
            updated = recommendations.settle_snapshots(archive_day)
            archive_updates.append({'date': archive_day, 'snapshots': updated})
        except Exception:
            logger.exception('Incremental archive verification failed for %s', archive_day)
    processed = []
    # Rotate through the backlog: two permanently unverifiable days must not
    # starve every other historical date on each scheduled run.
    from datetime import date as _date
    from datetime import timedelta as _timedelta
    # Exclude today's unfinished games; a completed game day is eligible.
    for day in candidates[:14]:
        try:
            snapshot = storage.earliest_completed(day)
            if not snapshot or not snapshot.get('results'):
                processed.append({'date':day,'status':'empty'})
                continue
            import recommendations
            ticket_count = recommendations.settle_snapshots(day)
            verified, expected = settle_espn.settle_archive(snapshot, day)
            result = calibration.settle(day, snapshot['job_id'], verified, expected)
            processed.append({'date':day,'status':'settled', 'recommendation_snapshots': ticket_count, **result})
        except Exception as exc:
            logger.exception('NBA calibration settlement failed for %s', day)
            processed.append({'date':day,'status':'skipped','reason':str(exc)[:160]})
    return {'processed':processed,'archive_updates':archive_updates,'pending':max(0,len(candidates)-14),'odds_api_calls':0}

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


@app.get('/admin/monitor', include_in_schema=False)
def admin_monitor_page():
    return FileResponse('web/monitor-admin.html', headers={
        'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
        'Referrer-Policy': 'no-referrer',
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})


@app.get('/api/admin/monitor', dependencies=[Depends(auth)])
def admin_monitor_report(response: Response):
    import admin_monitor
    response.headers['Cache-Control'] = 'no-store'
    try:
        return admin_monitor.report()
    except Exception:
        logger.exception('Admin monitor unavailable')
        raise HTTPException(503, 'Monitoraggio temporaneamente non disponibile',
                            headers={'Cache-Control': 'no-store'})


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


def _published_history(date, result):
    import public_views
    day = datetime.strptime(date, '%Y-%m-%d').date()
    import official_top5
    if official_top5.eligible_day(date):
        official = official_top5.get(date)
        if official:
            result['official_lines'] = []
            identities = {public_views.leg_identity(row) for row in official['lines']}
            by_identity = {public_views.leg_identity(row): row for row in result['lines']}
            for row in official['lines']:
                result['official_lines'].append(by_identity.get(public_views.leg_identity(row), row))
            result['other_lines'] = [row for row in result['lines'] if public_views.leg_identity(row) not in identities]
            result['official_saved_at'] = official['published_at']
            result['has_daily_model'] = True
            result['official_summary'] = {status: sum(row.get('status') == status for row in result['official_lines'])
                                          for status in ('won','lost','unresolved')}
            result['official_policy'] = official['policy']
        else:
            result['official_lines'] = []
            result['official_summary'] = {status: 0 for status in ('won','lost','unresolved')}
            result['has_daily_model'] = False
    # Session-era archive: official picks belong to their publication day,
    # even if the NBA game starts after midnight on the next calendar date.
    import nba_session_picks
    if nba_session_picks.eligible(date):
        session_official = nba_session_picks.read(date)
        if session_official:
            tomorrow = (day + timedelta(days=1)).isoformat()
            next_history = public_views.history(tomorrow)
            all_scored = list(result.get('lines', [])) + list(next_history.get('lines', []))
            by_identity = {public_views.leg_identity(row): row for row in all_scored}
            result['official_lines'] = [
                by_identity.get(public_views.leg_identity(row), row)
                for row in session_official['lines']
            ]
            result['official_saved_at'] = session_official['published_at']
            result['has_daily_model'] = True
            result['official_policy'] = session_official['policy']
            result['official_summary'] = {
                status: sum(row.get('status') == status for row in result['official_lines'])
                for status in ('won', 'lost', 'unresolved')
            }
            single = session_official.get('single')
            scored_single = (by_identity.get(public_views.leg_identity(single), single)
                             if single else None)
            result['session_single_archive'] = {
                'published': bool(single), 'selection': scored_single,
                'outcome': {'status': scored_single.get('status', 'unresolved'),
                            'actual': scored_single.get('actual')} if scored_single else None,
                'status': scored_single.get('status', 'unresolved') if scored_single else 'not_published',
                'published_at': session_official['published_at']
            }
    # New category remains separate from existing historical Top 5.
    # No backfilling: only explicitly published singles count.
    import daily_single_archive
    result['single_archive'] = (daily_single_archive.read(date) if official_top5.eligible_day(date)
                                else {'published': False, 'selection': None, 'outcome': None})
    single_record = result['single_archive']
    if (single_record.get('published') and single_record.get('selection')
            and not single_record.get('outcome')):
        saved_single = single_record['selection']
        identity = public_views.leg_identity(saved_single)
        matched = next((row for row in result.get('lines', [])
                        if public_views.leg_identity(row) == identity), None)
        if matched:
            single_record['outcome'] = {'status': matched.get('status', 'unresolved'),
                                        'actual': matched.get('actual')}
            single_record['status'] = matched.get('status', 'unresolved')
        else:
            single_record['outcome'] = {'status': 'unresolved', 'actual': None}
            single_record['status'] = 'unresolved'
    if result.get('session_single_archive'):
        result['single_archive'] = result['session_single_archive']
    result['top5_archive'] = {
        'lines': result.get('official_lines', []),
        'summary': result.get('official_summary', {}),
    }
    return result


def _performance_counts(states):
    won = states.count('won')
    lost = states.count('lost')
    verified = won + lost
    return {'published': len(states), 'verified': verified, 'won': won, 'lost': lost,
            'pending': len(states) - verified,
            'success_pct': round(won * 100 / verified, 1) if verified else None}


@app.get('/api/history/performance')
def public_history_performance():
    """Summarize published selections from the public archive."""
    import public_views
    import official_top5
    today = datetime.now(ZoneInfo('Europe/Rome')).date()
    dates = public_views.history_dates(today)['dates'][:30]
    top5_states = []
    single_states = []
    days = 0
    for entry in dates:
        date = entry['date']
        if not official_top5.eligible_day(date):
            continue
        archive = _published_history(date, public_views.history(date))
        lines = archive['top5_archive']['lines']
        top5_states.extend(line.get('status') for line in lines)
        days += bool(lines)
        single = archive['single_archive']
        if single.get('published'):
            single_states.append((single.get('outcome') or {}).get('status'))
    return {**_performance_counts(top5_states), 'single': _performance_counts(single_states),
            'days': days, 'odds_api_calls': 0}


@app.get('/api/history/dates')
def public_history_dates():
    import public_views
    try:
        return public_views.history_dates(datetime.now(ZoneInfo('Europe/Rome')).date())
    except Exception:
        logger.exception('Cannot list public recommendation archive')
        raise HTTPException(503, 'Archivio temporaneamente non disponibile')


@app.get('/api/history')
def public_history(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$')):
    import public_views
    try:
        day = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(400, 'Data non valida')
    if day > datetime.now(ZoneInfo('Europe/Rome')).date():
        raise HTTPException(400, 'La giornata non è ancora archiviabile')
    try:
        # ESPN fixture times are used only for shadow evaluation; archive stays immutable.
        starts = None
        try:
            starts = public_views.fixture_start_map(schedule(date)['games'])
        except Exception:
            logger.warning('ESPN start times unavailable for progressive preview: %s', date)
        result = public_views.history(date, starts=starts)
        return _published_history(date, result)
    except Exception:
        logger.exception('Cannot read public recommendation archive')
        raise HTTPException(503, 'Archivio temporaneamente non disponibile')


@app.post('/api/diagnostics/odds-tournament', dependencies=[Depends(auth)])
def diagnose_odds_tournament(check_missing: bool = False):
    """One explicit, durable, five-request probe; never starts a scan."""
    import odds_provider_probe
    try:
        return (odds_provider_probe.check_missing_once(engine.API_KEY) if check_missing
                else odds_provider_probe.run_once(engine.API_KEY))
    except odds_provider_probe.ProbeError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        logger.exception('Cannot access one-shot provider diagnostic')
        raise HTTPException(503, 'Diagnostica temporaneamente non disponibile') from None

@app.post('/api/diagnostics/odds-date', dependencies=[Depends(auth)])
def diagnose_odds_date(confirmed: bool = False, unfiltered: bool = False, evening: bool = False):
    import odds_date_probe
    import odds_provider_probe
    try:
        return (odds_date_probe.run_unfiltered_once(engine.API_KEY) if unfiltered else
                odds_date_probe.run_confirmed_once(engine.API_KEY, evening=evening) if confirmed or evening
                else odds_date_probe.run_once(engine.API_KEY))
    except odds_provider_probe.ProbeError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        logger.exception('Date feed diagnostic unavailable')
        raise HTTPException(503, 'Diagnostica temporaneamente non disponibile') from None


@app.post('/api/scan', dependencies=[Depends(auth)])
def scan(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$'),
         source: str = Query(default='manual', pattern=r'^(github|render|manual)$'),
         slot: str | None = Query(default=None, pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$')):
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(400, 'Data non valida')
    if slot is not None:
        from scripts.scheduled_scan import valid_slot
        if not valid_slot(slot):
            raise HTTPException(400, 'Slot non valido')
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
        jobs[job_id] = {'date':date,'state':'queued','progress':0,'stage':'In coda','scan_source':source,'scan_slot':slot}
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
    if job is not None and not job.get('cloud_saved'):
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
            raise HTTPException(503, 'Analisi salvata temporaneamente non disponibile')
    raise HTTPException(404,'Scansione non trovata')

@app.get('/api/scan/{job_id}/csv', dependencies=[Depends(auth)])
def scan_csv(job_id: str):
    job = scan_result(job_id)
    if job['state'] not in ('done','partial','save_failed'): raise HTTPException(404,'Analisi non disponibile')
    data=engine.csv_excel_friendly(pd.DataFrame(job['results']))
    return StreamingResponse(io.BytesIO(data),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="basketlab_completo.csv"'})

@app.get('/favicon.ico', include_in_schema=False)
def favicon():
    return FileResponse('web/favicon.ico', media_type='image/x-icon')


@app.get('/ads.txt', include_in_schema=False)
def ads_txt():
    return FileResponse('web/ads.txt', media_type='text/plain')


@app.get('/robots.txt', include_in_schema=False)
def robots_txt():
    return PlainTextResponse('User-agent: *\nAllow: /\nSitemap: https://basketlab.it/sitemap.xml\n')

@app.get('/sitemap.xml', include_in_schema=False)
def sitemap_xml():
    return Response(content='<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    '<url><loc>https://basketlab.it/</loc></url></urlset>',
                    media_type='application/xml')

app.mount('/static',VersionedStaticFiles(directory='web'),name='static')
@app.get('/')
@app.get('/notizie', include_in_schema=False)
@app.get('/pronostici', include_in_schema=False)
@app.get('/partite', include_in_schema=False)
@app.get('/analisi-partita', include_in_schema=False)
@app.get('/archivio', include_in_schema=False)
@app.get('/statistiche', include_in_schema=False)
@app.get('/analisi-quote', include_in_schema=False)
@app.get('/come-funziona', include_in_schema=False)
def index():
    return FileResponse('web/index.html', headers={'Cache-Control': 'no-cache'})

