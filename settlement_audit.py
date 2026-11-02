"""Read-only explanation of settlement gaps; never changes outcomes or forecasts."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
import engine
import settle_espn


def eligible(row):
    """Mirror historical settlement's denominator, including unresolved pushes."""
    try:
        p = float(row.get('Prob. stimata %'))
        return (row.get('Mercato') in ('PTS', 'AST', 'REB')
                and str(row.get('Scelta', '')).lower() in ('over', 'under')
                and math.isfinite(p) and 0 <= p <= 100)
    except (TypeError, ValueError):
        return False


def fixture_key(value):
    return frozenset(engine.normalized_name(t) for t in str(value or '').split(' - '))


def diagnose(snapshot, scan_date, evidence):
    """Require exact dated fixtures and pregame timestamps; report every eligible row.

    Evidence uses the same batch-local cache keys as settle_espn. Absence from a
    boxscore is not proof of DNP. Wrong-team ID matches are diagnostic only.
    """
    events = evidence[('events', scan_date)]
    fixtures = defaultdict(list)
    for event in events:
        competitors = (event.get('competitions') or [{}])[0].get('competitors', [])
        fixtures[frozenset(engine.normalized_name((c.get('team') or {}).get('displayName', ''))
                           for c in competitors)].append(event)
    saved = snapshot.get('scan_finished_at') or snapshot.get('saved_at')
    try:
        timestamp = datetime.fromisoformat(str(saved).replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            timestamp = None
    except ValueError:
        timestamp = None
    counts, missing, verified, seen = Counter(), [], [], Counter()
    for index, row in enumerate(snapshot.get('results') or []):
        if not eligible(row):
            continue
        fixture = fixture_key(row.get('Partita'))
        athlete_id = str(row.get('ESPN ID') or '').strip()
        player = 'id:' + athlete_id if athlete_id else engine.espn_player_key(row.get('Giocatore', ''))
        team = engine.normalized_name(row.get('Squadra', ''))
        event_list = fixtures.get(fixture, [])
        reason, actual = None, None
        if len(fixture) != 2 or not all(fixture):
            reason = 'malformed_fixture'
        elif len(event_list) != 1:
            reason = 'missing_fixture' if not event_list else 'ambiguous_fixture'
        else:
            event = event_list[0]
            if timestamp is None:
                reason = 'unverifiable_timestamp'
            elif event.get('status', {}).get('type', {}).get('completed') is not True:
                reason = 'game_not_final'
            elif not event.get('date'):
                reason = 'missing_tipoff'
            elif timestamp.astimezone(timezone.utc) >= datetime.fromisoformat(event['date'].replace('Z', '+00:00')):
                reason = 'post_tipoff_snapshot'
            else:
                box = evidence.get(('summary', event['id']))
                if box is None:
                    reason = 'missing_boxscore'
                else:
                    try:
                        stats = settle_espn.player_stats(box)
                    except ValueError:
                        stats = {}
                        reason = 'ambiguous_boxscore'
                    if not reason:
                        actuals = stats.get((team, player)) if team in fixture and (not athlete_id or athlete_id.isdigit()) else None
                        if actuals is None:
                            cross_team = [stats[(t, player)] for t in fixture if (t, player) in stats]
                            reason = 'team_mismatch_verified_id' if athlete_id.isdigit() and len(cross_team) == 1 else 'athlete_not_in_boxscore'
                            for box_team in box.get('boxscore', {}).get('players', []):
                                if engine.normalized_name((box_team.get('team') or {}).get('displayName', '')) != team:
                                    continue
                                for group in box_team.get('statistics', []):
                                    for athlete in group.get('athletes', []):
                                        person = athlete.get('athlete') or {}
                                        match = str(person.get('id') or '') == athlete_id if athlete_id else engine.espn_player_key(person.get('displayName', '')) == player
                                        if match and athlete.get('didNotPlay') is True:
                                            reason = 'confirmed_dnp'
                        else:
                            actual = actuals.get(row['Mercato'])
                            try:
                                line = float(row['Linea'])
                                p = float(row.get('Prob. grezza %', row['Prob. stimata %'])) / 100
                                if not math.isfinite(line) or not math.isfinite(p) or not 0 <= p <= 1:
                                    reason = 'invalid_binary_input'
                                elif actual == line:
                                    reason = 'push'
                                elif actual is None:
                                    reason = 'missing_statistic'
                            except (KeyError, TypeError, ValueError):
                                reason = 'invalid_binary_input'
        reason = reason or 'matched'
        counts[reason] += 1
        if reason == 'matched':
            key = (tuple(sorted(fixture)), team, player, row['Mercato'], str(row['Scelta']).lower(), float(row['Linea']))
            seen[key] += 1
            verified.append({**row, 'actual': actual, 'played': True, '_audit_date': scan_date})
        else:
            missing.append({'row_index': index, 'reason': reason, 'player': row.get('Giocatore'),
                            'team': row.get('Squadra'), 'fixture': row.get('Partita'),
                            'athlete_id': athlete_id, 'market': row.get('Mercato'), 'line': row.get('Linea')})
    return {'date': scan_date, 'eligible': sum(counts.values()), 'reasons': dict(counts),
            'duplicate_matched_lines': sum(n - 1 for n in seen.values()),
            'missing': missing}, verified
