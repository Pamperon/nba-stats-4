"""Frozen minutes experiment. Never modifies live probabilities or selections.

minutes-v1 is a development candidate, not a validated replacement model.
It scales historical PTS/MIN rates to the median minutes of the latest five
eligible games. This provisional rate/minutes assumption needs prospective tests.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import math
from statistics import mean, median, pstdev

VERSION = 'minutes-v1'
MIN_HISTORY = 15
ODDS_RANGE = (1.20, 2.00)


def minutes(value):
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, str) and ':' in value:
            minute, second = value.split(':')
            if not minute.isdigit() or not second.isdigit() or not 0 <= int(second) < 60:
                return None
            value = int(minute) + int(second)/60
        value = float(value)
        return value if math.isfinite(value) and 0 < value <= 80 else None
    except (TypeError, ValueError):
        return None


def deadline(value):
    stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timezone-aware capture timestamp required')
    return stamp.astimezone(timezone.utc)


def history(records, cutoff):
    cutoff = deadline(cutoff)
    samples, seen, excluded = [], set(), Counter()
    for item in records:
        if not isinstance(item, dict):
            excluded['invalid_record'] += 1
            continue
        try:
            identifier = str(item.get('GAME_ID') or '').strip()
            if not identifier:
                excluded['missing_game_id'] += 1
                continue
            if identifier in seen:
                raise ValueError('Duplicate historical game identity')
            seen.add(identifier)
            raw = str(item['GAME_DATE'])
            stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if len(raw) == 10:
                # A date-only record does not prove intraday ordering. Require
                # the entire UTC day to have ended before the capture timestamp.
                stamp = stamp.replace(tzinfo=timezone.utc) + timedelta(days=1)
            elif stamp.tzinfo is None:
                excluded['unknown_timezone'] += 1
                continue
            if stamp >= cutoff:
                excluded['not_strictly_pregame'] += 1
                continue
            if int(item.get('SEASON_TYPE') or 0) != 2:
                excluded['not_regular_season'] += 1
                continue
            mins = minutes(item.get('MIN'))
            points = float(item['PTS'])
            if mins is None or not math.isfinite(points) or points < 0:
                excluded['invalid_statistic'] += 1
                continue
        except (KeyError, TypeError, OverflowError):
            excluded['invalid_record'] += 1
            continue
        except ValueError as exc:
            if str(exc) == 'Duplicate historical game identity':
                raise
            excluded['invalid_record'] += 1
            continue
        samples.append({'id': identifier, 'date': stamp, 'minutes': mins,
                        'points': points, 'season': str(item.get('ANNO_STAGIONE') or '')})
    samples.sort(key=lambda r: r['date'], reverse=True)
    return samples, dict(excluded)


def profile(records, cutoff):
    samples, excluded = history(records, cutoff)
    if len(samples) < MIN_HISTORY:
        return {'eligible': False, 'reason': 'insufficient_verified_history',
                'history_n': len(samples), 'excluded_history': excluded}
    recent = samples[:20]
    mins5 = [r['minutes'] for r in recent[:5]]
    mins10 = [r['minutes'] for r in recent[:10]]
    projected = median(mins5)
    return {'eligible': True, 'history_n': len(samples), 'recent_n': len(recent),
            'projected_minutes': projected, 'recent5_mean_minutes': mean(mins5),
            'recent10_cv_minutes': pstdev(mins10)/mean(mins10),
            'recent10_low_minutes_rate': sum(m < .8*projected for m in mins10)/len(mins10),
            'last_game_minutes_ratio': mins5[0]/projected,
            'starter': None, 'role': None,  # Not supplied by archived logs.
            'excluded_history': excluded,
            '_scenario_points': [r['points']/r['minutes']*projected for r in recent]}


def identity(row):
    return (row.get('Partita'), str(row.get('ESPN ID') or row.get('Giocatore') or '').strip())


def capture(rows, logs, captured_at):
    deadline(captured_at)
    # Freeze one PTS line per athlete/fixture using only pregame odds and line.
    selected = {}
    for row in rows:
        if row.get('Mercato') != 'PTS' or str(row.get('Scelta', '')).lower() != 'over':
            continue
        try:
            odds, line, p = float(row['Quota']), float(row['Linea']), float(row['Prob. stimata %'])/100
            if not (math.isfinite(odds) and ODDS_RANGE[0] <= odds <= ODDS_RANGE[1]
                    and math.isfinite(line) and abs(line % 1-.5) < 1e-6
                    and math.isfinite(p) and 0 <= p <= 1):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        key = identity(row)
        if not all(key):
            continue
        rank = (abs(odds-1.80), line, str(row.get('Giocatore') or ''))
        if key not in selected or rank < selected[key][0]:
            selected[key] = (rank, row)
    panel, excluded = [], Counter()
    profiles = {}
    for _, row in selected.values():
        name = row.get('Giocatore')
        if name not in profiles:
            try:
                profiles[name] = profile(logs.get(name, []), captured_at)
            except (ValueError, TypeError):
                profiles[name] = {'eligible': False, 'reason': 'ambiguous_history'}
        features = profiles[name]
        if not features['eligible']:
            excluded[features['reason']] += 1
            continue
        scenarios = features['_scenario_points']
        candidate = (sum(value > float(row['Linea']) for value in scenarios)+.5)/(len(scenarios)+1)
        checked = row.get('Disponibilità verificata alle')
        try:
            availability = row.get('Disponibilità ESPN') if checked and deadline(checked) <= deadline(captured_at) else 'unknown'
        except (TypeError, ValueError):
            availability = 'unknown'
        fields = ('Partita','Squadra','Giocatore','ESPN ID','Mercato','Scelta','Linea','Quota')
        panel.append({**{key: row.get(key) for key in fields},
                      'baseline_probability': float(row['Prob. stimata %'])/100,
                      'candidate_probability': candidate,
                      'availability_at_capture': availability,
                      'features': {key: value for key,value in features.items() if not key.startswith('_')}})
    return {'version': VERSION, 'mode': 'shadow', 'promotion_allowed': False,
            'captured_at': captured_at, 'selected_before_labels': len(selected),
            'excluded': dict(excluded), 'panel': panel, 'odds_api_calls': 0}
