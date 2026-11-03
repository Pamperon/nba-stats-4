"""Fixed, prospective shadow candidates. No live probability modifications.

Definitions are frozen in weights-v1; future changes need a new version.
All inputs must be pregame game logs. Current injuries never backfill history.
"""
import math
from datetime import datetime, timezone

VERSION = 'weights-v1'
BASELINE = 'pooled80_recent20'
CAPPED = 'last40_80_recent20'
SEASON = 'current_with_prior20'
MODELS = (BASELINE, CAPPED, SEASON)


def prepare(records, season, cutoff):
    """Use only dated regular-season samples strictly before the snapshot.

    Saved GAME_DATE values can have date precision; that is the original
    archive precision, not a reconstruction from current ESPN data.
    """
    if hasattr(records, 'to_dict'):
        records = records.to_dict('records')
    deadline = datetime.fromisoformat(str(cutoff).replace('Z', '+00:00'))
    if deadline.tzinfo is None:
        raise ValueError('Timezone required on pregame cutoff')
    samples, seen = [], set()
    for original in records:
        row = dict(original)
        try:
            when = datetime.fromisoformat(str(row['GAME_DATE']).replace('Z', '+00:00'))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= deadline or int(row['SEASON_TYPE']) != 2:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        identifier = str(row.get('GAME_ID') or '')
        if not identifier:
            raise ValueError('Game identity required for model comparison')
        if identifier in seen:
            raise ValueError('Duplicate game in pregame history')
        seen.add(identifier)
        row['_date'] = when
        samples.append(row)
    samples.sort(key=lambda r: r['_date'], reverse=True)
    return {'season': str(season), 'samples': samples}


def estimate(context, market, line, choice='Over'):
    if market not in ('PTS', 'AST', 'REB') or str(choice).lower() not in ('over', 'under'):
        return None
    line = float(line)
    if not math.isfinite(line) or abs(line % 1 - .5) > 1e-6:
        return None
    samples = []
    for row in context['samples']:
        try:
            value = float(row[market])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value):
            samples.append((value > line if choice.lower() == 'over' else value < line,
                            str(row.get('ANNO_STAGIONE') or '')))
    if len(samples) < 15:
        return None
    def jeffreys(items):
        return (sum(hit for hit, _ in items) + .5) / (len(items) + 1)
    baseline = .8 * jeffreys(samples) + .2 * jeffreys(samples[:20])
    capped = .8 * jeffreys(samples[:40]) + .2 * jeffreys(samples[:20])
    current = [s for s in samples if s[1] == context['season']]
    previous_name = str(int(context['season'][:4]) - 1) + '-' + context['season'][2:4]
    previous = [s for s in samples if s[1] == previous_name][:40]
    season_estimate = None
    if all(label in (context['season'], previous_name) for _, label in samples):
        if previous:
            season_estimate = (sum(hit for hit, _ in current) + 20 * jeffreys(previous)) / (len(current) + 20)
        elif current:
            season_estimate = jeffreys(current)
    return {BASELINE: baseline, CAPPED: capped, SEASON: season_estimate}


def shadow_row(row, context):
    result = estimate(context, row['Mercato'], row['Linea'], row['Scelta'])
    if result is None:
        return dict(row)
    return {**row, 'Probabilità alternative %': {
        name: round(p * 100, 4) for name, p in result.items() if p is not None}}
