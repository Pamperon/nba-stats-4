"""Public daily recommendation archive from saved PostgreSQL records only.

Never reconstruct old recommendations or contact a bookmaker/statistics feed.
"""
import math
import storage

GROUP_SIZES = {'Singola': 1, 'Doppia': 2, 'Tripla': 3}
LEG_FIELDS = ('Giocatore', 'ESPN ID', 'Squadra', 'Partita', 'Mercato', 'Scelta',
              'Linea', 'Quota', 'Prob. stimata %')


def history_dates(today):
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT DISTINCT scan_date FROM nba_scan_snapshots
            WHERE scan_date <= %s AND payload ? 'recommendations'
            ORDER BY scan_date DESC LIMIT 90
        """, (today,)).fetchall()
    return {'dates': [{'date': day.isoformat()} for (day,) in rows],
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


def leg_identity(row):
    return (str(row.get('Partita', '')).strip().casefold(),
            str(row.get('Squadra', '')).strip().casefold(),
            str(row.get('ESPN ID') or row.get('Giocatore', '')).strip().casefold(),
            str(row.get('Mercato', '')).upper(), str(row.get('Scelta', '')).casefold(),
            float(row['Linea']))


def daily_groups(versions):
    """One daily collection: deduplicate whole tickets, never invent multiples.

    Changes in odds, probability or leg order do not create a new prediction.
    Keep the first published price. Conflicting final results stay unresolved.
    """
    from copy import deepcopy
    tickets, evidence = {}, {}
    for version in sorted(versions, key=lambda item: item['saved_at']):
        for name in GROUP_SIZES:
            group = version['groups'].get(name, {})
            if group.get('status') == 'incomplete' or len(group.get('legs', [])) != GROUP_SIZES[name]:
                continue
            identity = (name, tuple(sorted(leg_identity(row) for row in group['legs'])))
            if identity not in tickets:
                tickets[identity] = {**deepcopy(group), 'first_seen': version['saved_at']}
            for row in group['legs']:
                actual = row.get('actual')
                if isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual):
                    evidence.setdefault(leg_identity(row), set()).add(float(actual))
    output = {name: [] for name in GROUP_SIZES}
    for (name, _), ticket in tickets.items():
        conflict = False
        for row in ticket['legs']:
            values = evidence.get(leg_identity(row), set())
            conflict |= len(values) > 1
            actual = next(iter(values)) if len(values) == 1 else None
            row['actual'] = actual
            row['win'] = None if actual is None or actual == row['Linea'] else (
                actual > row['Linea'] if str(row['Scelta']).lower() == 'over' else actual < row['Linea'])
        ticket['status'] = ('unresolved' if conflict else 'lost' if any(row['win'] is False for row in ticket['legs'])
                            else 'unresolved' if any(row['win'] is None for row in ticket['legs']) else 'won')
        output[name].append(ticket)
    return output


def history(day):
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT s.created_at, s.payload->'recommendations', r.report->'groups'
            FROM nba_scan_snapshots s
            LEFT JOIN nba_recommendation_results r ON r.snapshot_job_id=s.job_id
            WHERE s.scan_date=%s AND s.payload ? 'recommendations'
            ORDER BY s.created_at ASC, s.job_id ASC
        """, (day,)).fetchall()
    versions = [{'saved_at': at.isoformat(), 'groups': ticket_groups(saved, report)}
                for at, saved, report in rows if isinstance(saved, dict)]
    groups = daily_groups(versions)
    tickets = [ticket for group in groups.values() for ticket in group]
    return {'date': day, 'groups': groups,
            'summary': {state: sum(ticket['status'] == state for ticket in tickets)
                        for state in ('won', 'lost', 'unresolved')},
            'odds_api_calls': 0}
