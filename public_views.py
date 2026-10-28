"""Public archive and quote movements from saved PostgreSQL records only.

Never reconstruct old recommendations or contact a bookmaker/statistics feed.
"""
import math
from collections import defaultdict
import storage

GROUP_SIZES = {'Singola': 1, 'Doppia': 2, 'Tripla': 3}
LEG_FIELDS = ('Giocatore', 'ESPN ID', 'Squadra', 'Partita', 'Mercato', 'Scelta',
              'Linea', 'Quota', 'Prob. stimata %')


def history_dates(today):
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT scan_date, COUNT(*) FROM nba_scan_snapshots
            WHERE scan_date <= %s AND payload ? 'recommendations'
            GROUP BY scan_date ORDER BY scan_date DESC LIMIT 90
        """, (today,)).fetchall()
    return {'dates': [{'date': day.isoformat(), 'versions': count} for day, count in rows],
            'odds_api_calls': 0}


def ticket_groups(saved, settled_groups):
    """Expose exact published legs and verified outcomes for this snapshot only."""
    output = {}
    for name, size in GROUP_SIZES.items():
        group = saved.get('groups', {}).get(name, {})
        chosen = group.get('legs', [])
        if group.get('complete') is not True or len(chosen) != size:
            output[name] = {'status': 'incomplete', 'legs': [], 'combined_odds': None}
            continue
        verified = (settled_groups or {}).get(name, {}).get('legs', [])
        legs = []
        for row in chosen:
            matches = [item for item in verified if (
                item.get('player'), item.get('market'), item.get('choice'), item.get('line'), item.get('odds')) == (
                row.get('Giocatore'), row.get('Mercato'), row.get('Scelta'), row.get('Linea'), row.get('Quota'))]
            actual = matches[0].get('actual') if len(matches) == 1 else None
            valid = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual)
            win = None if not valid or actual == row['Linea'] else (
                actual > row['Linea'] if str(row['Scelta']).lower() == 'over' else actual < row['Linea'])
            legs.append({**{key: row.get(key) for key in LEG_FIELDS},
                         'actual': actual if valid else None, 'win': win})
        status = ('lost' if any(row['win'] is False for row in legs) else
                  'unresolved' if any(row['win'] is None for row in legs) else 'won')
        distinct = all(row.get('Partita') for row in chosen) and len({row['Partita'] for row in chosen}) == size
        output[name] = {'status': status, 'legs': legs,
                        'combined_odds': round(math.prod(float(row['Quota']) for row in chosen), 4) if distinct else None}
    return output


def history(day):
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT s.job_id, s.created_at, s.payload->'recommendations',
                   r.report->'groups', s.payload->>'odds_feed_fetched_at'
            FROM nba_scan_snapshots s
            LEFT JOIN nba_recommendation_results r ON r.snapshot_job_id=s.job_id
            WHERE s.scan_date=%s AND s.payload ? 'recommendations'
            ORDER BY s.created_at DESC LIMIT 100
        """, (day,)).fetchall()
    return {'date': day, 'versions': [
        {'job_id': job, 'saved_at': at.isoformat(), 'odds_at': odds_at,
         'policy': saved.get('policy'), 'groups': ticket_groups(saved, report)}
        for job, at, saved, report, odds_at in rows if isinstance(saved, dict)],
        'odds_api_calls': 0}


def selection_index(rows):
    result, ambiguous = {}, set()
    for row in rows:
        try:
            line, price = float(row['Linea']), float(row['Quota'])
            if not math.isfinite(line) or not math.isfinite(price) or price <= 1:
                continue
            key = (str(row['Partita']).strip().casefold(),
                   str(row.get('ESPN ID') or row['Giocatore']).strip().casefold(),
                   str(row['Mercato']).upper(), str(row['Scelta']).casefold(), line)
        except (KeyError, TypeError, ValueError):
            continue
        if key in result:
            ambiguous.add(key)
        result[key] = row
    return {key: value for key, value in result.items() if key not in ambiguous}, len(ambiguous)


def compare_quotes(current, previous):
    now, bad_now = selection_index(current)
    before, bad_before = selection_index(previous)
    common = now.keys() & before.keys()
    changes = []
    counts = {'up': 0, 'down': 0, 'unchanged': 0, 'added': 0, 'removed': 0}
    for key in now.keys() | before.keys():
        old, new = before.get(key), now.get(key)
        if old is None:
            kind = 'added'
        elif new is None:
            kind = 'removed'
        else:
            delta = float(new['Quota']) - float(old['Quota'])
            kind = 'unchanged' if abs(delta) < 1e-8 else 'up' if delta > 0 else 'down'
        counts[kind] += 1
        if kind == 'unchanged':
            continue
        row = new if new is not None else old
        changes.append({'player': row.get('Giocatore'), 'team': row.get('Squadra'),
                        'game': row.get('Partita'), 'market': row.get('Mercato'),
                        'choice': row.get('Scelta'), 'line': row.get('Linea'), 'kind': kind,
                        'before': float(old['Quota']) if old is not None else None,
                        'after': float(new['Quota']) if new is not None else None})
    lines_now, lines_before = defaultdict(set), defaultdict(set)
    for key in now:
        lines_now[key[:-1]].add(key[-1])
    for key in before:
        lines_before[key[:-1]].add(key[-1])
    counts['line_groups_changed'] = sum(lines_now[k] != lines_before[k] for k in lines_now.keys() & lines_before.keys())
    changes.sort(key=lambda row: (str(row['player']), str(row['game']), str(row['market']), float(row['line'])))
    return {'summary': {**counts, 'comparable': len(common), 'ambiguous': bad_now + bad_before},
            'changes': changes[:1000], 'truncated': len(changes) > 1000}


def movements(day):
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT job_id, created_at, payload->'results', payload->>'odds_feed_fetched_at'
            FROM nba_scan_snapshots WHERE scan_date=%s
            ORDER BY created_at DESC LIMIT 2
        """, (day,)).fetchall()
    versions = [{'job_id': job, 'saved_at': at.isoformat(), 'odds_at': odds_at}
                for job, at, _, odds_at in rows]
    result = compare_quotes(rows[0][2] or [], rows[1][2] or []) if len(rows) == 2 else {'summary': None, 'changes': [], 'truncated': False}
    return {'date': day, 'versions': versions, **result, 'odds_api_calls': 0}


def movement_dates():
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT scan_date, COUNT(*) FROM nba_scan_snapshots
            GROUP BY scan_date ORDER BY scan_date DESC LIMIT 90
        """).fetchall()
    return {'dates': [{'date': day.isoformat(), 'versions': count} for day, count in rows],
            'odds_api_calls': 0}
