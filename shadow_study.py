"""Frozen pregame model/selection study, scored only after finalized outcomes.

Parallel evaluation only: never promotes a candidate or edits public estimates.
"""
import math
import model_candidates as models
import recommendations

CONFIGS = (
    ('baseline', models.BASELINE, 'probability'),
    ('capped40', models.CAPPED, 'probability'),
    ('season_prior20', models.SEASON, 'probability'),
    ('value_first', models.BASELINE, 'value'),
    ('distinct_games', models.BASELINE, 'distinct_games'),
)


def identity(row):
    return (row.get('Partita'), row.get('Squadra'),
            str(row.get('ESPN ID') or row.get('Giocatore')), row.get('Mercato'),
            str(row.get('Scelta', '')).lower())


def line_key(row):
    return identity(row) + (float(row['Linea']),)


def policy_select(rows, model, policy):
    eligible = []
    for original in rows:
        p = original['_models'].get(model)
        if p is None:
            continue
        row = {k: v for k, v in original.items() if k != '_models'}
        if model != models.BASELINE:
            row['Prob. stimata %'] = round(p * 100, 1)
            row['Value stimato %'] = round((p * float(row['Quota']) - 1) * 100, 1)
        if not recommendations.rejection_reasons(row):
            eligible.append(row)
    def rank(row):
        p, value = float(row['Prob. stimata %']), float(row.get('Value stimato %') or 0)
        return (-value, -p) if policy == 'value' else (-p, -value)
    eligible.sort(key=rank)
    groups = {}
    for name, count, low, high in recommendations.GROUPS:
        picks, players, games = [], set(), set()
        for row in eligible:
            player = str(row.get('Giocatore') or '').strip().lower()
            if not player or player in players or not low <= float(row['Quota']) <= high:
                continue
            if policy == 'distinct_games' and row['Partita'] in games:
                continue
            picks.append(row); players.add(player); games.add(row['Partita'])
            if len(picks) == count:
                break
        groups[name] = {'complete': len(picks) == count, 'legs': picks}
    return {'policy': models.VERSION + ':' + model + ':' + policy, 'groups': groups}


def score(rows, model):
    entries = []
    for row in rows:
        p = row['_models'].get(model)
        if p is None or row['actual'] == float(row['Linea']):
            continue
        win = int(row['actual'] > float(row['Linea'])) if row['Scelta'].lower() == 'over' else int(row['actual'] < float(row['Linea']))
        entries.append((p, win))
    n = len(entries)
    return {'n': n, 'wins': sum(w for _, w in entries),
            'mean_predicted': sum(p for p, _ in entries)/n if n else None,
            'observed': sum(w for _, w in entries)/n if n else None,
            'brier': sum((p-w)**2 for p, w in entries)/n if n else None,
            'log_loss': -sum(w*math.log(max(.000001,p))+(1-w)*math.log(max(.000001,1-p)) for p,w in entries)/n if n else None}


def choose_panel(rows):
    """Freeze line choices before labels; all candidates share the same panel."""
    panel = {}
    for row in rows:
        if not 1.20 <= float(row['Quota']) <= 2.00 or any(row['_models'].get(m) is None for m in models.MODELS):
            continue
        key = identity(row)
        ranking = (abs(float(row['Quota']) - 1.80), -float(row['Prob. stimata %']), float(row['Linea']))
        if key not in panel or ranking < panel[key][0]:
            panel[key] = (ranking, row)
    return [dict(row) for _, row in panel.values()]


def capture(rows):
    """Called during a scan: consume internal candidates, leaving public rows intact."""
    prepared = []
    for row in rows:
        predictions = row.pop('_shadow_probabilities', None)
        if not predictions or row.get('Stato analisi') != 'Valutabile (stima empirica)':
            continue
        probabilities = {model: round(p * 100, 1)/100 if p is not None else None
                         for model, p in predictions.items()}
        probabilities['live_control'] = float(row['Prob. stimata %'])/100
        probabilities[models.BASELINE] = float(row.get('Prob. grezza %', row['Prob. stimata %']))/100
        prepared.append({**row, '_models': probabilities})
    fields = ('Partita','Squadra','ESPN ID','Giocatore','Mercato','Scelta','Linea','Quota','Prob. stimata %','_models')
    return {'version': models.VERSION, 'mode': 'shadow', 'promotion_allowed': False,
            'covered_lines': len(prepared),
            'probability_panel': [{key: row.get(key) for key in fields} for row in choose_panel(prepared)],
            'tickets': {name: policy_select(prepared, model, policy) for name, model, policy in CONFIGS}}


def evaluate(saved, verified):
    """Keep missing outcomes explicit; never choose new lines after the result."""
    lookup = {line_key(row): row for row in verified if row.get('played') is True}
    panel = saved.get('probability_panel', [])
    paired = [{**row, 'actual': lookup[line_key(row)]['actual']} for row in panel if line_key(row) in lookup]
    return {'version': saved.get('version'), 'mode': 'shadow', 'promotion_allowed': False,
            'panel_selected': len(panel), 'panel_verified': len(paired),
            'models': {model: score(paired, model) for model in models.MODELS + ('live_control',)},
            'tickets': {name: recommendations.evaluate(ticket, verified)
                        for name, ticket in saved.get('tickets', {}).items()}}

