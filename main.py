"""FastAPI app. One process for the free-tier MVP; persistent jobs need external storage later."""
import os, secrets, threading, uuid, io, time
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
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
        with lock:
            jobs[job_id].update(state='partial' if any(r['stato'] != 'ok' for r in fixture_reports) else 'done',progress=100,stage='Parziale' if any(r['stato'] != 'ok' for r in fixture_reports) else 'Completata',results=rows,issues=issues,fixture_reports=fixture_reports,player_logs=serialized_logs,fixture_count=len(fixtures),player_count=player_count,season=season,timings={'preparazione_s':setup_seconds,'scansione_s':analysis_seconds,'totale_s':round(time.monotonic()-started_at,2)})
        with lock:
            snapshot = dict(jobs[job_id])
        try:
            if storage.configured():
                storage.save(job_id, snapshot)
        except Exception:
            logger.exception('Scan %s finished but PostgreSQL persistence failed', job_id)
            with lock:
                jobs[job_id]['persistence_warning'] = 'Salvataggio cloud non riuscito; esporta subito il CSV'
    except Exception as exc:
        with lock: jobs[job_id].update(state='error',stage=f'Analisi non completata ({type(exc).__name__})')

@app.get('/api/saved/latest', dependencies=[Depends(auth)])
def saved_latest(date: str | None = Query(default=None, pattern=r'^\\d{4}-\\d{2}-\\d{2}
def scan(date: str = Query(pattern=r'^\d{4}-\d{2}-\d{2}$')):
    try: datetime.strptime(date,'%Y-%m-%d')
    except ValueError: raise HTTPException(400,'Data non valida')
    with lock:
        for job_id, job in jobs.items():
            if job['date']==date and job['state'] in ('queued','running','done'):
                return {'job_id':job_id,'reused':True}
        if len(jobs)>15: raise HTTPException(429,'Limite scansioni raggiunto; riavvia il servizio')
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
    if not job or job['state'] not in ('done','partial'): raise HTTPException(404,'Analisi non disponibile')
    data=engine.csv_excel_friendly(pd.DataFrame(job['results']))
    return StreamingResponse(io.BytesIO(data),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="nba_stats_4_completo.csv"'})

app.mount('/static',StaticFiles(directory='web'),name='static')
@app.get('/')
def index(): return FileResponse('web/index.html')
)):
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
            if job['date']==date and job['state'] in ('queued','running','done'):
                return {'job_id':job_id,'reused':True}
        if len(jobs)>15: raise HTTPException(429,'Limite scansioni raggiunto; riavvia il servizio')
        job_id=uuid.uuid4().hex
        jobs[job_id]={'date':date,'state':'queued','progress':0,'stage':'In coda'}
    threading.Thread(target=do_scan,args=(job_id,date),daemon=True).start()
    return {'job_id':job_id,'reused':False}

@app.get('/api/scan/{job_id}', dependencies=[Depends(auth)])
def scan_result(job_id: str):
    with lock:
        if job_id not in jobs: raise HTTPException(404,'Scansione non trovata')
        return dict(jobs[job_id])

@app.get('/api/scan/{job_id}/csv', dependencies=[Depends(auth)])
def scan_csv(job_id: str):
    with lock: job=jobs.get(job_id)
    if not job or job['state'] not in ('done','partial'): raise HTTPException(404,'Analisi non disponibile')
    data=engine.csv_excel_friendly(pd.DataFrame(job['results']))
    return StreamingResponse(io.BytesIO(data),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="nba_stats_4_completo.csv"'})

app.mount('/static',StaticFiles(directory='web'),name='static')
@app.get('/')
def index(): return FileResponse('web/index.html')
