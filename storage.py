"""Persistent scan snapshots stored in Supabase PostgreSQL (server-side only)."""
import json
import math
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

log = logging.getLogger(__name__)


def configured():
    return bool(os.getenv("DATABASE_URL"))


def connection():
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10, sslmode="require")


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
    return True


def claim_slot(slot_key):
    """Atomic reservation across GitHub runners; retry stale/failed claims."""
    if not configured():
        raise RuntimeError("Database required for scan deduplication")
    with connection() as conn:
        row = conn.execute("""
            INSERT INTO nba_scan_slots(slot_key, status)
            VALUES (%s, 'running')
            ON CONFLICT(slot_key) DO UPDATE
            SET status='running', claimed_at=NOW(), finished_at=NULL
            WHERE nba_scan_slots.status='failed'
               OR (nba_scan_slots.status='running'
                   AND nba_scan_slots.claimed_at < NOW() - INTERVAL '80 minutes')
            RETURNING slot_key
        """, (slot_key,)).fetchone()
    return bool(row)


def finish_slot(slot_key, success):
    with connection() as conn:
        conn.execute("""
            UPDATE nba_scan_slots SET status=%s, finished_at=NOW()
            WHERE slot_key=%s AND status='running'
        """, ('done' if success else 'failed', slot_key))


def cache_read(key, max_age_hours):
    if not configured():
        return None
    with connection() as conn:
        row = conn.execute("""
            SELECT payload FROM nba_player_cache
            WHERE cache_key=%s AND updated_at >= NOW() - (%s * INTERVAL '1 hour')
        """, (key, max_age_hours)).fetchone()
    return row[0] if row else None


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

def earliest_completed(date):
    """Oldest nonempty completed snapshot for a date, for pregame calibration.

    Prefer a snapshot before all games rather than latest (possibly post-tipoff).
    Never delete or mutate the underlying archived scan.
    """
    if not configured():
        return None
    with connection() as conn:
        rows = conn.execute("""
            SELECT job_id,payload,created_at
            FROM nba_scan_snapshots
            WHERE scan_date=%s AND state='done'
            ORDER BY created_at ASC
        """, (date,)).fetchall()
    for job_id,payload,created_at in rows:
        if payload.get("results"):
            return {"job_id":job_id,"saved_at":created_at.isoformat(),**payload}
    return None


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
