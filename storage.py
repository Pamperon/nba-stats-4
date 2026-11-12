"""Persistent scan snapshots stored in Supabase PostgreSQL (server-side only)."""
import json
import math
import logging
import os
import uuid
import time
import threading
from functools import lru_cache
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)
_pool = None
_pool_lock = threading.Lock()


def configured():
    return bool(os.getenv("DATABASE_URL"))


def connection():
    # CLI jobs retain short-lived connections. Only the persistent web process
    # explicitly opens a pool; importing this module never opens a socket.
    if _pool is not None:
        return _pool.connection()
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10, sslmode="require")


def open_pool():
    """Warm a bounded process-local pool before the HTTP server accepts work."""
    global _pool
    if os.getenv('NBA_DATABASE_POOL_ENABLED', '1') == '0':
        return
    with _pool_lock:
        if _pool is not None and not _pool.closed:
            return
        candidate = ConnectionPool(
            os.environ['DATABASE_URL'], open=False, min_size=1, max_size=4,
            timeout=10, max_waiting=16, max_idle=60, max_lifetime=300,
            reconnect_timeout=30, name='basketlab-db',
            kwargs={'connect_timeout': 10, 'sslmode': 'require',
                    'application_name': 'basketlab-web',
                    # Safe with Supavisor transaction mode as well as direct PG.
                    'prepare_threshold': None},
            check=ConnectionPool.check_connection,
        )
        try:
            candidate.open(wait=True, timeout=10)
        except Exception:
            candidate.close()
            raise
        _pool = candidate


def close_pool():
    # Retain the closed object so late shutdown work cannot open new sockets.
    with _pool_lock:
        if _pool is not None:
            _pool.close(timeout=5)


def pool_stats():
    """Numeric operational counters only; never return the connection string."""
    if _pool is None:
        return {'enabled': False}
    return {'enabled': True, 'closed': _pool.closed, **_pool.get_stats()}


def initialize():
    if not configured():
        return False
    with connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_scan_snapshots (
                job_id TEXT PRIMARY KEY,
                scan_date DATE NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('done','partial')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                payload JSONB NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS nba_scan_snapshots_date_idx
            ON nba_scan_snapshots (scan_date, created_at DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_player_cache (
                cache_key TEXT PRIMARY KEY,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                payload JSONB NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_scan_slots (
                slot_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMPTZ
            )
        """)
        conn.execute("ALTER TABLE nba_scan_slots ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ")
        conn.execute("ALTER TABLE nba_scan_slots ADD COLUMN IF NOT EXISTS instance_id TEXT")
        conn.execute("ALTER TABLE nba_scan_slots ADD COLUMN IF NOT EXISTS recovery_count INTEGER NOT NULL DEFAULT 0")
    return True


def claim_slot(slot_key, instance_id=None):
    """Atomic reservation with one bounded recovery after a dead/failed batch."""
    if not configured():
        raise RuntimeError("Database required for scan deduplication")
    with connection() as conn:
        if instance_id is not None:
            import scan_tracking
            scan_tracking.ensure_claim_allowed(conn, instance_id)
        row = conn.execute("""
            INSERT INTO nba_scan_slots(slot_key, status, heartbeat_at, instance_id)
            VALUES (%s, 'running', NOW(), %s)
            ON CONFLICT(slot_key) DO UPDATE SET status='running',
                claimed_at=NOW(), heartbeat_at=NOW(), finished_at=NULL,
                instance_id=EXCLUDED.instance_id,
                recovery_count=nba_scan_slots.recovery_count+1
            WHERE nba_scan_slots.status IN ('running','failed')
              AND nba_scan_slots.recovery_count < 1
              AND COALESCE(nba_scan_slots.heartbeat_at,nba_scan_slots.claimed_at)<NOW()-INTERVAL '2 minutes'
              AND NOT EXISTS (
                SELECT 1 FROM nba_scan_attempts a
                WHERE a.slot_key=nba_scan_slots.slot_key AND a.state IN ('queued','running')
                  AND a.heartbeat_at>NOW()-INTERVAL '2 minutes'
              )
            RETURNING slot_key
        """, (slot_key, instance_id)).fetchone()
    return bool(row)


def finish_slot(slot_key, success):
    with connection() as conn:
        conn.execute("""
            UPDATE nba_scan_slots SET status=%s, finished_at=NOW(), heartbeat_at=NOW()
            WHERE slot_key=%s AND status='running'
        """, ('done' if success else 'failed', slot_key))


def touch_slot(slot_key):
    with connection() as conn:
        conn.execute("UPDATE nba_scan_slots SET heartbeat_at=NOW() WHERE slot_key=%s AND status='running'", (slot_key,))


def cache_read(key, max_age_hours, *, identity=None):
    if not configured():
        return None
    with connection() as conn:
        row = conn.execute("""
            SELECT payload FROM nba_player_cache
            WHERE cache_key=%s AND updated_at >= NOW() - (%s * INTERVAL '1 hour')
              AND (%s::text IS NULL OR COALESCE(payload->>'identity', %s) = %s)
        """, (key, max_age_hours, identity, identity, identity)).fetchone()
    return row[0] if row else None


def cache_read_many(keys, max_age_hours):
    """Read one team's saved logs in one connection; never contact providers."""
    if not configured() or not keys:
        return {}
    with connection() as conn:
        rows = conn.execute("""
            SELECT cache_key, payload FROM nba_player_cache
            WHERE cache_key = ANY(%s)
              AND updated_at >= NOW() - (%s * INTERVAL '1 hour')
        """, (list(keys), max_age_hours)).fetchall()
    return dict(rows)


def cached_player_previews(keys, max_age_hours):
    """Project ten games inside PostgreSQL instead of downloading full seasons."""
    if not configured() or not keys:
        return {}
    with connection() as conn:
        rows = conn.execute("""
            SELECT c.cache_key, COALESCE((
                SELECT jsonb_agg(recent.game ORDER BY recent.day DESC)
                FROM (
                    SELECT g->>'GAME_DATE' AS day,
                        jsonb_build_object('GAME_DATE',g->>'GAME_DATE',
                            'PTS',g->'PTS','REB',g->'REB','AST',g->'AST') AS game
                    FROM jsonb_array_elements(CASE WHEN jsonb_typeof(c.payload->'games')='array'
                        THEN c.payload->'games' ELSE '[]'::jsonb END) g
                    WHERE g->>'GAME_DATE' IS NOT NULL
                    ORDER BY g->>'GAME_DATE' DESC LIMIT 10
                ) recent
            ), '[]'::jsonb)
            FROM nba_player_cache c WHERE c.cache_key=ANY(%s)
                AND c.updated_at>=NOW()-(%s * INTERVAL '1 hour')
        """, (list(keys), max_age_hours)).fetchall()
    return dict(rows)


def cache_write(key, payload):
    if not configured():
        return
    with connection() as conn:
        conn.execute("""
            INSERT INTO nba_player_cache(cache_key, payload)
            VALUES (%s, %s) ON CONFLICT(cache_key) DO UPDATE
            SET payload=EXCLUDED.payload, updated_at=NOW()
        """, (key, Jsonb(_clean(payload))))


def save(job_id, snapshot):
    if not configured():
        return False
    if snapshot.get("state") not in ("done", "partial"):
        raise ValueError("Only completed scan snapshots may be persisted")
    # Convert numpy/pandas scalars and nonfinite values safely via JSON serialization.
    clean = _clean(snapshot)
    with connection() as conn:
        conn.execute("""
            INSERT INTO nba_scan_snapshots(job_id, scan_date, state, payload)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(job_id) DO UPDATE SET
                state=EXCLUDED.state, payload=EXCLUDED.payload
        """, (job_id, snapshot["date"], snapshot["state"], Jsonb(clean)))
    _cached_fixture_coverage.cache_clear()
    return True


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, 'item'):
        return _clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def latest(date=None):
    if not configured():
        return None
    with connection() as conn:
        if date:
            row = conn.execute("""
                SELECT job_id, payload, created_at FROM nba_scan_snapshots
                WHERE scan_date=%s ORDER BY created_at DESC LIMIT 1
            """, (date,)).fetchone()
        else:
            row = conn.execute("""
                SELECT job_id, payload, created_at FROM nba_scan_snapshots
                ORDER BY scan_date DESC, created_at DESC LIMIT 1
            """).fetchone()
    if not row:
        return None
    job_id, payload, created_at = row
    return {"job_id": job_id, "saved_at": created_at.isoformat(), **payload}

def recent_fixture_coverage(date, max_age_hours=24):
    """Return the newest available quote rows for each fixture.

    Cache repeated public reads for at most 45 seconds, invalidated whenever
    a new snapshot is saved. This avoids repeated large JSONB reads on navigation.
    """
    if not configured():
        return []
    bucket = int(time.monotonic() // 45)
    return list(_cached_fixture_coverage(date, max_age_hours, bucket))


# The time bucket is part of the key: retaining 32 buckets kept many copies of
# the same thousands of quote rows alive for 24 minutes. Two cover active dates.
@lru_cache(maxsize=2)
def _cached_fixture_coverage(date, max_age_hours, _bucket):
    with connection() as conn:
        rows = conn.execute("""
            SELECT jsonb_build_object('results', payload->'results') AS payload
            FROM nba_scan_snapshots
            WHERE scan_date=%s
              AND created_at >= NOW() - (%s * INTERVAL '1 hour')
              AND state IN ('done','partial')
            ORDER BY created_at DESC
        """, (date, max_age_hours)).fetchall()
    fixtures = {}
    for (payload,) in rows:
        groups = {}
        for item in payload.get('results', []):
            fixture = str(item.get('Partita') or '').strip().casefold()
            if fixture:
                groups.setdefault(fixture, []).append(item)
        for fixture, items in groups.items():
            fixtures.setdefault(fixture, items)
    return tuple(row for fixture_rows in fixtures.values() for row in fixture_rows)


def earliest_completed(date):
    """Oldest nonempty completed snapshot for a date, for pregame calibration.

    Prefer a snapshot before all games rather than latest (possibly post-tipoff).
    Never delete or mutate the underlying archived scan.
    """
    if not configured():
        return None
    with connection() as conn:
        row = conn.execute("""
            SELECT job_id,payload,created_at
            FROM nba_scan_snapshots
            WHERE scan_date=%s AND state='done'
              AND CASE WHEN jsonb_typeof(payload->'results') = 'array'
                       THEN jsonb_array_length(payload->'results') > 0
                       ELSE FALSE END
            ORDER BY created_at ASC LIMIT 1
        """, (date,)).fetchone()
    if row is None:
        return None
    job_id, payload, created_at = row
    return {"job_id":job_id,"saved_at":created_at.isoformat(),**payload}


def by_job_id(job_id):
    """Restore the requested completed job, even if a later date was saved."""
    if not configured():
        return None
    with connection() as conn:
        row = conn.execute("""
            SELECT job_id, payload, created_at FROM nba_scan_snapshots
            WHERE job_id=%s
        """, (job_id,)).fetchone()
    if row is None:
        return None
    saved_id, payload, created_at = row
    return {**payload, 'job_id': saved_id, 'saved_at': created_at.isoformat()}


def calibration_retention_preview(retention_days=7):
    """Read-only count of snapshots eligible for future pruning.

    A date is eligible only if settled and old enough. No deletion is performed.
    Unsettled archives are never considered safe to remove.
    """
    if not configured():
        return {"eligible_dates":0,"eligible_snapshots":0,
                "unsettled_snapshots":0,"deletion_enabled":False}
    with connection() as conn:
        row = conn.execute("""
            SELECT COUNT(DISTINCT s.scan_date), COUNT(*)
            FROM nba_scan_snapshots s
            JOIN nba_calibration_settled c ON c.scan_date=s.scan_date
            WHERE s.scan_date < CURRENT_DATE - (%s * INTERVAL '1 day')
        """,(retention_days,)).fetchone()
        unsettled = conn.execute("""
            SELECT COUNT(*) FROM nba_scan_snapshots s
            WHERE NOT EXISTS (
                SELECT 1 FROM nba_calibration_settled c
                WHERE c.scan_date=s.scan_date)
        """).fetchone()[0]
    return {"eligible_dates":row[0],"eligible_snapshots":row[1],
            "unsettled_snapshots":unsettled,"deletion_enabled":False}


def self_test():
    """Insert, read back and delete one isolated synthetic record; no external APIs."""
    if not configured():
        raise RuntimeError("DATABASE_URL missing")
    test_id = "storage-test-" + uuid.uuid4().hex
    sample = {"date": "2000-01-01", "state": "done", "results": [],
              "issues": [], "player_logs": {}, "fixture_reports": [],
              "test_marker": test_id}
    with connection() as conn:
        try:
            conn.execute("""
                INSERT INTO nba_scan_snapshots(job_id, scan_date, state, payload)
                VALUES (%s, %s, %s, %s)
            """, (test_id, sample["date"], "done", Jsonb(sample)))
            row = conn.execute("""
                SELECT payload FROM nba_scan_snapshots WHERE job_id=%s
            """, (test_id,)).fetchone()
            if not row or row[0].get("test_marker") != test_id:
                raise RuntimeError("Readback mismatch")
            conn.execute("DELETE FROM nba_scan_snapshots WHERE job_id=%s", (test_id,))
            remaining = conn.execute(
                "SELECT 1 FROM nba_scan_snapshots WHERE job_id=%s", (test_id,)
            ).fetchone()
            if remaining:
                raise RuntimeError("Cleanup failed")
        except Exception:
            conn.rollback()
            raise
    return {"status": "ok", "write": True, "read": True, "cleanup": True,
            "odds_api_calls": 0}


def available_dates():
    """Distinct dates with saved analyses, newest first; no OddsPapi calls."""
    if not configured():
        return []
    with connection() as conn:
        rows = conn.execute("""
            SELECT scan_date, MAX(created_at) AS last_saved
            FROM nba_scan_snapshots
            GROUP BY scan_date ORDER BY scan_date DESC
        """).fetchall()
    return [{"date": day.isoformat(), "saved_at": saved.isoformat()} for day, saved in rows]


def cleanup_expired(retention_days=7):
    """Legacy compatibility: historical predictions are never deleted automatically.

    The prior implementation deleted all scans older than seven days.
    This function deliberately performs no deletion; keep for existing callers.
    """
    log.info("NBA scan retention disabled: preserving all historical snapshots")
    return {"deleted_snapshots": 0, "retention_policy": "permanent",
            "odds_api_calls": 0}

