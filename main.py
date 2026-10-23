"""FastAPI app. One process for the free-tier MVP; persistent jobs need external storage later."""
import os, secrets, threading, uuid, io, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import requests
import engine
import storage
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

@app.on_event('startup')
def init_storage():
    if storage.configured():
        try:
            storage.initialize()
            logger.info('Persistent PostgreSQL scan storage ready')
        except Exception:
            logger.exception('Persistent storage unavailable; service remains accessible')


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

@app.get('/api/saved/latest', dependencies=[Depends(auth)])
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
    return snapshot

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
