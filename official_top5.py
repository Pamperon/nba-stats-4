"""Immutable daily Top 5 published at 18:00 Europe/Rome.

Only dates from 2026-11-02 use this policy. Legacy archives are untouched.
The first successful publication is transactional and cannot be replaced by
later scans. No OddsPapi requests are made here.
"""
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
import storage
import recommendations

ROME = ZoneInfo("Europe/Rome")
START = date(2026, 11, 2)
POLICY = "fixed-1800-v2-overnight"

def eligible_day(day):
    return date.fromisoformat(str(day)) >= START

def initialize():
    with storage.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_official_daily_top5 (
                scan_date DATE PRIMARY KEY,
                published_at TIMESTAMPTZ NOT NULL,
                snapshot_job_id TEXT NOT NULL,
                selections JSONB NOT NULL,
                policy TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_official_daily_singles (
                scan_date DATE PRIMARY KEY,
                published_at TIMESTAMPTZ NOT NULL,
                snapshot_job_id TEXT NOT NULL,
                selection JSONB,
                outcome JSONB,
                policy TEXT NOT NULL
            )
        """)

def get(day):
    with storage.connection() as conn:
        row = conn.execute(
            "SELECT published_at,snapshot_job_id,selections FROM nba_official_daily_top5 WHERE scan_date=%s",
            (day,)).fetchone()
    if row and len(row[2]) < 10:
        import recommendations
        with storage.connection() as conn:
            snapshot = conn.execute(
                "SELECT payload FROM nba_scan_snapshots WHERE job_id=%s AND created_at <= %s",
                (row[1], row[0])).fetchone()
            single_row = conn.execute(
                "SELECT selection FROM nba_official_daily_singles WHERE scan_date=%s",
                (day,)).fetchone()
        if snapshot:
            expanded = recommendations.expand_saved_picks(
                row[2], single_row[0] if single_row else None, [snapshot[0]])
            if len(expanded) > len(row[2]):
                with storage.connection() as conn:
                    conn.execute(
                        "UPDATE nba_official_daily_top5 SET selections=%s WHERE scan_date=%s AND selections=%s",
                        (Jsonb(expanded), day, Jsonb(row[2])))
            row = (row[0], row[1], expanded)
    return {'published_at': row[0].isoformat(), 'snapshot_job_id': row[1],
            'lines': row[2], 'policy': POLICY} if row else None

def publication_cutoff(day, games):
    """Publish a Rome calendar date on the preceding evening if it has overnight tips.

    A single immutable official set exists per date, so every game in that date
    shares the same publication deadline. Existing published rows are untouched.
    """
    target = date.fromisoformat(str(day))
    cutoff = datetime.combine(target, time(18), ROME)
    for game in games:
        raw = game.get('start_at')
        if not raw:
            continue
        try:
            start = datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            continue
        if start.tzinfo is None:
            continue
        if start.astimezone(ROME) < cutoff + timedelta(hours=1):
            return datetime.combine(target - timedelta(days=1), time(18), ROME)
    return cutoff


def publish(day, games, now=None):
    """Publish once, using only completed scans from before 18:00 Rome.

    Requires a recent scan (within 4 hours of the chosen cutoff) and confirmed ESPN
    starts at least 60 minutes after publication. Missing inputs cause no publication, never a guessed list.
    """
    if not eligible_day(day):
        return None
    now = now or datetime.now(ROME)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    cutoff = publication_cutoff(day, games)
    if now.astimezone(ROME) < cutoff:
        return None
    # A delayed publish must never include games already started.
    earliest_allowed_start = max(cutoff, now.astimezone(ROME)) + timedelta(minutes=60)
    starts = {}
    for game in games:
        home, away = str(game.get('home') or '').strip(), str(game.get('away') or '').strip()
        raw = game.get('start_at')
        if not home or not away or not raw:
            continue
        start = datetime.fromisoformat(raw)
        if start.tzinfo is None:
            continue
        key = frozenset((home.casefold(), away.casefold()))
        starts[key] = start
    if not starts:
        return None
    with storage.connection() as conn:
        with conn.transaction():
            # Serialize simultaneous requests, including across Render instances.
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                         ("basketlab-official-" + str(day),))
            existing = conn.execute(
                "SELECT published_at,snapshot_job_id,selections FROM nba_official_daily_top5 WHERE scan_date=%s",
                (day,)).fetchone()
            if existing:
                return {'published_at': existing[0].isoformat(),
                        'snapshot_job_id': existing[1], 'lines': existing[2], 'policy': POLICY}
            row = conn.execute("""
                SELECT job_id, payload, created_at FROM nba_scan_snapshots
                WHERE scan_date=%s AND created_at <= %s
                  AND created_at >= %s
                  AND payload->'recommendations' ? 'lines'
                ORDER BY created_at DESC LIMIT 1
            """, (day, cutoff, cutoff - timedelta(hours=4))).fetchone()
            if row is None:
                return None
            job_id, payload, created = row
            saved_recommendations = payload.get('recommendations') or {}
            valid_rows = []
            for candidate in payload.get('results', []):
                parts = str(candidate.get('Partita') or '').split(' - ')
                if len(parts) != 2:
                    continue
                start = starts.get(frozenset(p.strip().casefold() for p in parts))
                if start is None or start < earliest_allowed_start:
                    continue
                valid_rows.append(candidate)
            single = recommendations.select_single(valid_rows)
            single_id = str((single or {}).get('ESPN ID') or (single or {}).get('Giocatore') or '').strip().casefold()
            selections = []
            used = {single_id} if single_id else set()
            for pick in saved_recommendations.get('lines', []):
                parts = str(pick.get('Partita') or '').split(' - ')
                if len(parts) != 2:
                    continue
                start = starts.get(frozenset(p.strip().casefold() for p in parts))
                if start is None or start < cutoff + timedelta(minutes=60):
                    continue
                player = str(pick.get('ESPN ID') or pick.get('Giocatore') or '').strip().casefold()
                if not player or player in used:
                    continue
                try:
                    p, odds = float(pick['Prob. stimata %']), float(pick['Quota'])
                    if p < 70 or not 1.20 <= odds <= 2.20 or p - 100 / odds < 3:
                        continue
                except (KeyError, TypeError, ValueError):
                    continue
                used.add(player)
                selections.append(pick)
                if len(selections) == 10:
                    break
            conn.execute("""
                INSERT INTO nba_official_daily_singles
                    (scan_date,published_at,snapshot_job_id,selection,outcome,policy)
                VALUES (%s,%s,%s,%s,NULL,%s)
                ON CONFLICT(scan_date) DO NOTHING
            """, (day, now, job_id, Jsonb(single) if single else None, 'single-1800-v1'))
            conn.execute("""
                INSERT INTO nba_official_daily_top5
                    (scan_date,published_at,snapshot_job_id,selections,policy)
                VALUES (%s,%s,%s,%s,%s)
            """, (day, now, job_id, Jsonb(selections), POLICY))
            return {'published_at': now.isoformat(), 'snapshot_job_id': job_id,
                    'lines': selections, 'policy': POLICY}
