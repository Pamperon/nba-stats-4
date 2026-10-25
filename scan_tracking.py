"""Durable scan attempts, metered HTTP attempts and safe deployment coordination.

Only local PostgreSQL is used here. No bookmaker requests or automatic retries.
"""
import time
import uuid
from datetime import datetime, timezone
import storage

COORDINATION_LOCK = 748219400
ACTIVE_STATES = ('queued', 'running')


class ScanPaused(RuntimeError):
    pass


def initialize():
    with storage.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_scan_attempts (
                job_id TEXT PRIMARY KEY, scan_date DATE NOT NULL,
                instance_id TEXT NOT NULL, source TEXT NOT NULL, slot_key TEXT,
                state TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                stage TEXT NOT NULL DEFAULT 'In coda',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMPTZ
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS nba_scan_attempts_date_idx ON nba_scan_attempts(scan_date, created_at DESC)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_odds_request_log (
                request_id TEXT PRIMARY KEY, job_id TEXT, endpoint TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending', http_status INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS nba_odds_request_job_idx ON nba_odds_request_log(job_id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_deploy_guard (
                id INTEGER PRIMARY KEY CHECK (id = 1), instance_id TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), expires_at TIMESTAMPTZ NOT NULL
            )
        """)


def _lock(conn):
    conn.execute('SELECT pg_advisory_xact_lock(%s)', (COORDINATION_LOCK,))


def _guard(conn):
    return conn.execute("SELECT instance_id, created_at FROM nba_deploy_guard WHERE id=1 AND expires_at>NOW()").fetchone()


def ensure_claim_allowed(conn, instance_id):
    """Called inside the slot-claim transaction, serialized against new deploys."""
    _lock(conn)
    guard = _guard(conn)
    if guard and guard[0] != instance_id:
        raise ScanPaused('Aggiornamento del servizio in corso; riprovare al prossimo controllo')


def begin_deploy_guard(instance_id):
    with storage.connection() as conn:
        _lock(conn)
        conn.execute("""
            INSERT INTO nba_deploy_guard(id,instance_id,expires_at) VALUES(1,%s,NOW()+INTERVAL '12 minutes')
            ON CONFLICT(id) DO UPDATE SET instance_id=EXCLUDED.instance_id,
                created_at=NOW(), expires_at=EXCLUDED.expires_at
        """, (instance_id,))


def release_deploy_guard(instance_id):
    with storage.connection() as conn:
        conn.execute('DELETE FROM nba_deploy_guard WHERE id=1 AND instance_id=%s', (instance_id,))


def deployment_blockers(instance_id):
    with storage.connection() as conn:
        active = conn.execute("""
            SELECT COUNT(*) FROM nba_scan_attempts WHERE instance_id<>%s
                AND state IN ('queued','running') AND heartbeat_at>NOW()-INTERVAL '2 minutes'
                AND NOT EXISTS (SELECT 1 FROM nba_scan_snapshots saved WHERE saved.job_id=nba_scan_attempts.job_id)
        """, (instance_id,)).fetchone()[0]
        # Keep an already claimed two-date batch alive between its individual jobs.
        # A dead caller's lease expires; it must not block cold starts indefinitely.
        batches = conn.execute("""
            SELECT COUNT(*) FROM nba_scan_slots WHERE status='running'
                AND heartbeat_at>NOW()-INTERVAL '2 minutes'
        """).fetchone()[0]
    return active + batches


def wait_for_deployment(instance_id, timeout=600, poll=2):
    """Delay readiness until previous scans/batches finish; fail the new deploy if busy."""
    begin_deploy_guard(instance_id)
    try:
        deadline = time.monotonic() + timeout
        while deployment_blockers(instance_id):
            if time.monotonic() >= deadline:
                raise ScanPaused('Scansioni ancora attive: deploy rinviato per evitare interruzioni')
            time.sleep(poll)
    except BaseException:
        release_deploy_guard(instance_id)
        raise


def begin_attempt(job_id, date, instance_id, source, slot_key=None):
    with storage.connection() as conn:
        _lock(conn)
        guard = _guard(conn)
        if guard and guard[0] != instance_id:
            # A batch claimed BEFORE this deploy may finish both dates. A new
            # batch cannot claim a slot until the new instance serves traffic.
            existing_batch = None
            if source in ('github', 'render') and slot_key:
                existing_batch = conn.execute("""
                    SELECT 1 FROM nba_scan_slots WHERE slot_key=%s AND status='running'
                        AND claimed_at<=%s AND heartbeat_at>NOW()-INTERVAL '2 minutes'
                """, (slot_key, guard[1])).fetchone()
            if not existing_batch:
                raise ScanPaused('Aggiornamento del servizio in corso; nuova scansione rinviata')
        active = conn.execute("""
            SELECT job_id,scan_date FROM nba_scan_attempts WHERE state IN ('queued','running')
                AND heartbeat_at>NOW()-INTERVAL '2 minutes'
                AND NOT EXISTS (SELECT 1 FROM nba_scan_snapshots saved WHERE saved.job_id=nba_scan_attempts.job_id)
                ORDER BY created_at DESC LIMIT 1
        """).fetchone()
        if active:
            return {'job_id': active[0], 'date': active[1].isoformat(), 'reused': True}
        conn.execute("""
            INSERT INTO nba_scan_attempts(job_id,scan_date,instance_id,source,slot_key,state)
            VALUES(%s,%s,%s,%s,%s,'queued')
        """, (job_id, date, instance_id, source, slot_key))
    return {'job_id': job_id, 'date': date, 'reused': False}


def heartbeat(job_id, progress=0, stage='In elaborazione'):
    with storage.connection() as conn:
        conn.execute("""
            UPDATE nba_scan_attempts SET state='running',progress=%s,stage=%s,
                updated_at=NOW(),heartbeat_at=NOW()
            WHERE job_id=%s AND state IN ('queued','running')
        """, (int(progress), str(stage)[:180], job_id))


def finish_attempt(job_id, state, progress, stage):
    if state not in ('done', 'partial', 'error', 'save_failed', 'interrupted'):
        raise ValueError('Invalid terminal scan state')
    with storage.connection() as conn:
        conn.execute("""
            UPDATE nba_scan_attempts SET state=%s,progress=%s,stage=%s,
                updated_at=NOW(),heartbeat_at=NOW(),finished_at=NOW() WHERE job_id=%s
        """, (state, int(progress), str(stage)[:180], job_id))


def start_request(job_id, endpoint):
    """Commit BEFORE HTTP. If persistence fails, callers must not send the request."""
    if endpoint not in ('fixtures', 'markets', 'odds'):
        raise ValueError('Unrecognized metered endpoint')
    request_id = uuid.uuid4().hex
    with storage.connection() as conn:
        conn.execute("INSERT INTO nba_odds_request_log(request_id,job_id,endpoint) VALUES(%s,%s,%s)",
                     (request_id, job_id, endpoint))
    return request_id


def finish_request(request_id, http_status=None):
    with storage.connection() as conn:
        conn.execute("""
            UPDATE nba_odds_request_log SET state=%s,http_status=%s,finished_at=NOW()
            WHERE request_id=%s
        """, ('responded' if http_status is not None else 'unknown', http_status, request_id))


def request_usage(job_id):
    with storage.connection() as conn:
        row = conn.execute("""
            SELECT COUNT(*), COUNT(*) FILTER(WHERE state='responded')
            FROM nba_odds_request_log WHERE job_id=%s
        """, (job_id,)).fetchone()
    logged, responded = row
    return {'logged': logged, 'responded': responded, 'uncertain': logged - responded}


def attempt(date=None, job_id=None):
    if job_id is not None:
        where, value = 'job_id=%s', job_id
    else:
        where, value = 'scan_date=%s', date
    with storage.connection() as conn:
        row = conn.execute("""
            SELECT job_id,scan_date,state,source,created_at,updated_at,finished_at,
                progress,stage,heartbeat_at FROM nba_scan_attempts WHERE """ + where +
            ' ORDER BY created_at DESC LIMIT 1', (value,)).fetchone()
    if row is None:
        return None
    keys = ('job_id','date','state','source','started_at','updated_at','finished_at','progress','stage','heartbeat_at')
    result = dict(zip(keys, row))
    if result['state'] in ACTIVE_STATES and (datetime.now(timezone.utc) - result['heartbeat_at']).total_seconds() > 120:
        result['state'] = 'interrupted'
        result['stage'] = 'Scansione interrotta o non più raggiungibile'
    result.pop('heartbeat_at')
    result['api_requests'] = request_usage(result['job_id'])
    return result


def last_saved(date):
    with storage.connection() as conn:
        row = conn.execute("""
            SELECT job_id,state,created_at,payload->>'scan_started_at',payload->>'scan_finished_at',
                payload->>'scan_source',payload->'odds_api_http_requests_scan'
            FROM nba_scan_snapshots WHERE scan_date=%s ORDER BY created_at DESC LIMIT 1
        """, (date,)).fetchone()
    if row is None:
        return None
    return dict(zip(('job_id','state','saved_at','started_at','finished_at','source','api_requests'), row))


def day_status(date):
    latest, saved = attempt(date=date), last_saved(date)
    if latest is not None and saved is not None and latest['job_id'] == saved['job_id']:
        # A snapshot is already committed even if the process died before the
        # final attempt-state update. Never label that completed save as lost.
        latest['state'] = saved['state']
    return {'date': date, 'state': latest['state'] if latest else saved['state'] if saved else 'waiting',
            'latest_attempt': latest, 'last_saved': saved, 'odds_api_calls': 0}
