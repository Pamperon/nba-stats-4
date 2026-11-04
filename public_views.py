"""Public daily recommendation archive from saved PostgreSQL records only.

Never reconstruct old recommendations or contact a bookmaker/statistics feed.
"""
import math
import storage

GROUP_SIZES = {'Singola': 1, 'Doppia': 2, 'Tripla': 3}
LEG_FIELDS = ('Giocatore', 'ESPN ID', 'Squadra', 'Partita', 'Mercato', 'Scelta',
              'Linea', 'Quota', 'Prob. stimata %')


def history_dates(today):
    import nba_session_picks
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT archive_date FROM (
                SELECT DISTINCT scan_date AS archive_date FROM nba_scan_snapshots
                WHERE scan_date < %s AND payload ? 'recommendations'
                UNION
                SELECT publication_date AS archive_date FROM nba_official_sessions
            ) days
            WHERE archive_date <= %s
            ORDER BY archive_date DESC
        """, (nba_session_picks.START, today)).fetchall()
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



def saved_lines(saved, settled):
    """Individual published selections, including historic completed tickets."""
    if isinstance(saved.get('lines'), list):
        source = saved['lines']
        verified = (settled or {}).get('lines', []) if isinstance(settled, dict) else []
    else:
        source = []
        for name, size in GROUP_SIZES.items():
            group = saved.get('groups', {}).get(name, {})
            if group.get('complete') is True and len(group.get('legs', [])) == size:
                source.extend(group['legs'])
        verified = []
        for group in (settled or {}).get('groups', {}).values():
            verified.extend(group.get('legs', []))
    output = []
    for row in source:
        matches = [item for item in verified if (
            item.get('player'), item.get('market'), str(item.get('choice', '')).lower(),
            float(item.get('line', -999)), float(item.get('odds', -999))) == (
            row.get('Giocatore'), row.get('Mercato'), str(row.get('Scelta', '')).lower(),
            float(row['Linea']), float(row['Quota']))]
        actual = matches[0].get('actual') if len(matches) == 1 else None
        valid = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual)
        win = None if not valid or actual == float(row['Linea']) else (
            actual > float(row['Linea']) if str(row['Scelta']).lower() == 'over' else actual < float(row['Linea']))
        output.append({**{key: row.get(key) for key in LEG_FIELDS},
                       'actual': actual if valid else None, 'win': win})
    return output


def daily_lines(versions):
    """One saved line per fixture/player/market/choice/threshold per day.

    First published odds and probability are immutable. Conflicting evidence
    remains unresolved, even when later scans disagree.
    """
    from copy import deepcopy
    first, evidence = {}, {}
    for version in sorted(versions, key=lambda v: v['saved_at']):
        for row in version['lines']:
            identity = leg_identity(row)
            if identity not in first:
                first[identity] = {**deepcopy(row), 'first_seen': version['saved_at']}
            actual = row.get('actual')
            if isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual):
                evidence.setdefault(identity, set()).add(float(actual))
    output = []
    for identity, row in first.items():
        values = evidence.get(identity, set())
        actual = next(iter(values)) if len(values) == 1 else None
        row['actual'] = actual
        row['win'] = None if actual is None or actual == float(row['Linea']) else (
            actual > float(row['Linea']) if str(row['Scelta']).lower() == 'over' else actual < float(row['Linea']))
        row['status'] = 'unresolved' if row['win'] is None else 'won' if row['win'] else 'lost'
        output.append(row)
    return output


def scan_comparison(versions):
    """Read-only audit of daily Top 5 changes; never changes official picks."""
    daily = [v for v in versions if v['is_daily']]
    previous = set()
    output = []
    for version in daily:
        current = [leg_identity(row) for row in version['lines'][:5]]
        identities = set(current)
        output.append({
            'saved_at': version['saved_at'],
            'count': len(current),
            'added': len(identities - previous),
            'removed': len(previous - identities),
            'changed': bool(previous and identities != previous),
        })
        previous = identities
    return output


def progressive_preview(versions, starts, margin_minutes=15, as_of=None, max_age_hours=3):
    """Read-only deadline-based replay of saved pregame snapshots.

    Select the newest available snapshot before each game's cutoff, never
    revise a confirmed quote, and do not backfill an unobserved cutoff.
    Games with unknown starts or deadlines in the future remain unconfirmed.
    This is research-only and never changes the official archive.
    """
    from datetime import datetime, timedelta, timezone
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    daily = sorted((v for v in versions if v['is_daily']),
                   key=lambda v: v['saved_at'])
    candidates = []
    for fixture, start in starts.items():
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if start.tzinfo is None:
            continue
        deadline = start - timedelta(minutes=margin_minutes)
        if deadline > as_of:
            continue
        snapshots = [v for v in daily
                     if datetime.fromisoformat(v['saved_at']).tzinfo is not None
                     and datetime.fromisoformat(v['saved_at']) < deadline]
        if not snapshots:
            continue
        fixture_key = str(fixture).strip().casefold()
        # The newest scan may have incomplete provider coverage for this
        # particular fixture. Use the latest snapshot where this fixture was
        # actually observed, rather than silently dropping valid earlier odds.
        observed = next((
            (v, [row for row in v['lines']
                 if str(row.get('Partita') or '').strip().casefold() == fixture_key])
            for v in reversed(snapshots)
            if any(str(row.get('Partita') or '').strip().casefold() == fixture_key
                   for row in v['lines'])
        ), None)
        if observed is None:
            continue
        latest, fixture_lines = observed
        # Never promote a stale quote from an earlier partial scan.
        if deadline - datetime.fromisoformat(latest['saved_at']) > timedelta(hours=max_age_hours):
            continue
        for row in fixture_lines:
            athlete = str(row.get('ESPN ID') or row.get('Giocatore') or '').strip().casefold()
            if not athlete:
                continue
            candidates.append((deadline, latest['saved_at'], athlete, row))
    candidates.sort(key=lambda item: (item[0], -float(item[3].get('Prob. stimata %') or 0),
                                      item[2]))
    confirmed, seen = [], set()
    for deadline, saved_at, athlete, row in candidates:
        key = (str(row.get('Partita') or '').strip().casefold(), athlete)
        if key in seen:
            continue
        seen.add(key)
        confirmed.append({'saved_at': saved_at, 'confirmed_at': deadline.isoformat(),
                          'row': row})
        if len(confirmed) == 5:
            break
    return confirmed



def fixture_start_map(games):
    """Match saved 'Home - Away' fixtures to verified ESPN tip-off times."""
    starts = {}
    for game in games:
        home = str(game.get('home') or '').strip()
        away = str(game.get('away') or '').strip()
        start = game.get('start_at')
        if home and away and start:
            starts[f'{home} - {away}'.casefold()] = start
            starts[f'{away} - {home}'.casefold()] = start
    return starts


def history(day, starts=None):
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT s.created_at, s.payload->'recommendations', r.report
            FROM nba_scan_snapshots s
            LEFT JOIN nba_recommendation_results r ON r.snapshot_job_id=s.job_id
            WHERE s.scan_date=%s AND s.payload ? 'recommendations'
            ORDER BY s.created_at ASC, s.job_id ASC
        """, (day,)).fetchall()
    versions = [{'saved_at': at.isoformat(), 'groups': ticket_groups(saved, (report or {}).get('groups')) if 'groups' in saved else {},
                 'lines': saved_lines(saved, report), 'is_daily': isinstance(saved.get('lines'), list)}
                for at, saved, report in rows if isinstance(saved, dict)]
    groups = daily_groups([v for v in versions if v['groups']])
    lines = daily_lines(versions)
    tickets = [ticket for group in groups.values() for ticket in group]
    # Freeze the first published new-model Top 5 for each day. Later scans
    # supply settlement evidence only; they cannot silently replace picks.
    # Legacy 1 Nov used rolling daily recommendations, not an immutable
    # 18:00 Top 5. Display the last published five for that day, rather
    # than the first provisional five. From 2 Nov onward use official tables.
    from datetime import date as _date
    daily_versions = [v for v in versions if v['is_daily'] and v['lines']]
    first_daily = (daily_versions[-1] if str(day) == '2026-11-01'
                   else daily_versions[0] if daily_versions else None)
    official = []
    if first_daily is not None:
        by_identity = {leg_identity(row): row for row in lines}
        for selected in first_daily['lines'][:10]:
            row = by_identity.get(leg_identity(selected))
            if row is not None:
                official.append(row)
    if str(day) == '2026-11-01' and len(official) < 10:
        # Legacy daily lists were already capped when saved. Extend from
        # other published pregame lines, ranking independently of outcomes.
        used = {str(row.get('ESPN ID') or row.get('Giocatore') or '').casefold()
                for row in official}
        ranked = sorted(lines, key=lambda row: -float(row.get('Prob. stimata %') or 0))
        for row in ranked:
            player = str(row.get('ESPN ID') or row.get('Giocatore') or '').casefold()
            if (len(official) >= 10 or player in used or not player
                    or float(row.get('Prob. stimata %') or 0) < 70
                    or not 1.20 <= float(row.get('Quota') or 0) <= 2.20):
                continue
            used.add(player)
            official.append(row)
    preview = progressive_preview(versions, starts) if starts else []
    # Match simulated picks against settled lines without changing their
    # original pregame odds or estimated probability.
    by_identity = {leg_identity(row): row for row in lines}
    evaluated_preview = []
    for item in preview:
        saved_row = item['row']
        settled = by_identity.get(leg_identity(saved_row), {})
        actual = settled.get('actual')
        valid = isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual)
        line = float(saved_row['Linea'])
        win = None if not valid or actual == line else (
            actual > line if str(saved_row['Scelta']).lower() == 'over' else actual < line)
        evaluated_preview.append({
            **item, 'actual': actual if valid else None,
            'win': win, 'status': 'unresolved' if win is None else 'won' if win else 'lost'
        })
    preview = evaluated_preview
    def performance(rows, unpack):
        evaluated = [unpack(row) for row in rows]
        settled = [row for row in evaluated if row['win'] is not None]
        wins = sum(row['win'] is True for row in settled)
        profit = sum((float(row['Quota']) - 1) if row['win'] else -1 for row in settled)
        return {'total': len(evaluated), 'settled': len(settled),
                'wins': wins, 'losses': len(settled) - wins,
                'success_pct': round(100 * wins / len(settled), 1) if settled else None,
                'roi_pct': round(100 * profit / len(settled), 1) if settled else None}
    comparison = {
        'official': performance(official, lambda row: row),
        'progressive': performance(preview, lambda item: {**item['row'], 'win': item['win']}),
        'overlap': len({leg_identity(row) for row in official} &
                       {leg_identity(item['row']) for item in preview}),
        'research_only': True,
    }
    official_ids = {leg_identity(row) for row in official}
    other = [row for row in lines if leg_identity(row) not in official_ids]
    return {'date': day, 'groups': groups, 'lines': lines,
            'official_lines': official, 'other_lines': other,
            'scan_comparison': scan_comparison(versions),
            'progressive_preview': preview,
            'progressive_preview_count': len(preview),
            'progressive_comparison': comparison,
            'has_daily_model': first_daily is not None,
            'official_saved_at': first_daily['saved_at'] if first_daily else None,
            'official_summary': {state: sum(line['status'] == state for line in official) for state in ('won', 'lost', 'unresolved')},
            'line_summary': {state: sum(line['status'] == state for line in lines) for state in ('won', 'lost', 'unresolved')},
            'summary': {state: sum(ticket['status'] == state for ticket in tickets)
                        for state in ('won', 'lost', 'unresolved')},
            'odds_api_calls': 0}
