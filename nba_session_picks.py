"""One immutable official selection per Italian NBA evening session.

Uses only persisted same-evening odds snapshots for the two calendar dates.
Never triggers an OddsPapi request or rewrites historical daily predictions.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from psycopg.types.json import Jsonb
import storage
import recommendations

ROME = ZoneInfo("Europe/Rome")
POLICY = "nba-evening-session-v1"
START = date(2026, 11, 2)


def eligible(day):
    return date.fromisoformat(str(day)) >= START


def cutoff_for(day):
    return datetime.combine(date.fromisoformat(str(day)), time(18), ROME)


def initialize():
    with storage.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_official_sessions (
                publication_date DATE PRIMARY KEY,
                published_at TIMESTAMPTZ NOT NULL,
                snapshot_job_ids JSONB NOT NULL,
                selections JSONB NOT NULL,
                single_selection JSONB,
                policy TEXT NOT NULL
            )
        """)


def read(day):
    with storage.connection() as conn:
        row = conn.execute("""
            SELECT published_at,snapshot_job_ids,selections,single_selection,policy
            FROM nba_official_sessions WHERE publication_date=%s
        """, (day,)).fetchone()
    if row is None:
        return None
    if len(row[2]) < 10:
        with storage.connection() as conn:
            snapshots = conn.execute(
                "SELECT payload FROM nba_scan_snapshots WHERE job_id = ANY(%s) AND created_at <= %s",
                (list(row[1].values()), row[0])).fetchall()
        expanded = recommendations.expand_saved_picks(row[2], row[3], [item[0] for item in snapshots])
        if len(expanded) > len(row[2]):
            with storage.connection() as conn:
                conn.execute(
                    "UPDATE nba_official_sessions SET selections=%s WHERE publication_date=%s AND selections=%s",
                    (Jsonb(expanded), day, Jsonb(row[2])))
        row = (row[0], row[1], expanded, row[3], row[4])
    return {'published_at': row[0].isoformat(), 'snapshot_job_ids': row[1],
            'lines': row[2], 'single': row[3], 'policy': row[4]}


def _fixture_key(name):
    return frozenset(x.strip().casefold() for x in str(name or '').split(' - '))


def _valid_rows(payload, eligible_games, earliest):
    rows = []
    for row in payload.get('results', []):
        start = eligible_games.get(_fixture_key(row.get('Partita')))
        if start is not None and start >= earliest:
            rows.append(row)
    return rows


def publish(day, games, now=None):
    if not eligible(day):
        return None
    now = now or datetime.now(ROME)
    if now.tzinfo is None:
        raise ValueError('Timezone-aware now required')
    cutoff = cutoff_for(day)
    if now.astimezone(ROME) < cutoff:
        return None
    # Only genuine upcoming games at least one hour after publication.
    earliest = max(now.astimezone(ROME), cutoff) + timedelta(hours=1)
    eligible_games = {}
    for game in games:
        raw = game.get('start_at')
        if not raw or not game.get('home') or not game.get('away'):
            continue
        try:
            start = datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            continue
        if start.tzinfo is None or start < earliest:
            continue
        eligible_games[frozenset((game['home'].strip().casefold(),
                                  game['away'].strip().casefold()))] = start
    if not eligible_games:
        return None
    with storage.connection() as conn:
        with conn.transaction():
            conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                         ('basketlab-session-' + str(day),))
            existing = conn.execute("""
                SELECT published_at,snapshot_job_ids,selections,single_selection,policy
                FROM nba_official_sessions WHERE publication_date=%s
            """, (day,)).fetchone()
            if existing:
                return {'published_at': existing[0].isoformat(),
                        'snapshot_job_ids': existing[1], 'lines': existing[2],
                        'single': existing[3], 'policy': existing[4]}
            next_day = (date.fromisoformat(str(day)) + timedelta(days=1)).isoformat()
            # Latest completed scan per Italian calendar date, no later than 18:00.
            rows = conn.execute("""
                SELECT DISTINCT ON (scan_date) scan_date,job_id,payload,created_at
                FROM nba_scan_snapshots
                WHERE scan_date IN (%s,%s)
                  AND created_at <= %s AND created_at >= %s
                  AND state IN ('done','partial')
                ORDER BY scan_date,created_at DESC
            """, (day, next_day, cutoff, cutoff - timedelta(hours=4))).fetchall()
            if not rows:
                return None
            # Never freeze a partial session when an eligible date has no scan.
            required_dates = {g.get('calendar_date') for g in games
                              if _fixture_key(str(g.get('home'))+' - '+str(g.get('away'))) in eligible_games}
            if not required_dates.issubset({str(row[0]) for row in rows}):
                return None
            all_rows, job_ids = [], {}
            for scan_date, job_id, payload, created in rows:
                job_ids[str(scan_date)] = str(job_id)
                all_rows.extend(_valid_rows(payload, eligible_games, earliest))
            # Recompute rankings over both dates, instead of concatenating
            # independently ranked Top 5 lists.
            single = recommendations.select_single(all_rows)
            selected = recommendations.select_daily(all_rows)['lines']
            single_id = str((single or {}).get('ESPN ID') or (single or {}).get('Giocatore') or '').strip().casefold()
            selections = [row for row in selected
                          if str(row.get('ESPN ID') or row.get('Giocatore') or '').strip().casefold() != single_id][:10]
            conn.execute("""
                INSERT INTO nba_official_sessions
                  (publication_date,published_at,snapshot_job_ids,selections,single_selection,policy)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (day, now, Jsonb(job_ids), Jsonb(selections),
                  Jsonb(single) if single else None, POLICY))
            return {'published_at': now.isoformat(), 'snapshot_job_ids': job_ids,
                    'lines': selections, 'single': single, 'policy': POLICY}
