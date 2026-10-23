"""Persistent scan snapshots stored in Supabase PostgreSQL (server-side only)."""
import json
import math
import logging
import os
import uuid
from datetime import datetime, timezone

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
    return True


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
