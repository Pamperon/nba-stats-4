"""Separate read-only archive for independently published daily singles.

The category is intentionally empty until a single is explicitly published.
Existing Top 5 and legacy tickets are never reclassified.
"""
import storage


def read(day):
    with storage.connection() as conn:
        row = conn.execute(
            "SELECT to_regclass('public.nba_official_daily_singles')"
        ).fetchone()
        if not row or row[0] is None:
            return {'published': False, 'selection': None, 'outcome': None,
                    'status': 'not_published'}
        record = conn.execute(
            """SELECT selection, outcome, published_at, snapshot_job_id
               FROM nba_official_daily_singles WHERE scan_date=%s""",
            (day,)
        ).fetchone()
    if record is None:
        return {'published': False, 'selection': None, 'outcome': None,
                'status': 'not_published'}
    selection, outcome, published_at, job_id = record
    if selection:
        with storage.connection() as conn:
            settled = conn.execute(
                "SELECT report->'daily_single' FROM nba_recommendation_results WHERE snapshot_job_id=%s",
                (job_id,)
            ).fetchone()
        if settled and settled[0]:
            leg = settled[0]
            win = leg.get('win')
            outcome = {'status': 'unresolved' if win is None else 'won' if win else 'lost',
                       'actual': leg.get('actual')}
    return {'published': selection is not None, 'selection': selection, 'outcome': outcome,
            'published_at': published_at.isoformat(),
            'status': (outcome or {}).get('status', 'unresolved')}
