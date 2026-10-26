"""Retrospective paired comparison from point-in-time archives only.

Models and selectors are fixed before this comparison. These dates have been
examined before and are NOT an independent holdout or a promotion criterion.
"""
import argparse
import json
import math
from pathlib import Path
import requests
import model_candidates as models
import recommendations
import settle_espn

from shadow_study import CONFIGS, identity, line_key, policy_select, score, choose_panel


def compare(archive, verified):
    contexts, rows, mismatches, missing = {}, [], 0, 0
    for original in archive['results']:
        if original.get('Stato analisi') != 'Valutabile (stima empirica)':
            continue
        name = original['Giocatore']
        if name not in contexts:
            history = archive.get('player_logs', {}).get(name)
            contexts[name] = models.prepare(history, archive['season'], archive.get('scan_finished_at') or archive['saved_at']) if history else None
        if contexts[name] is None:
            missing += 1
            continue
        predictions = models.estimate(contexts[name], original['Mercato'], original['Linea'], original['Scelta'])
        if predictions is None:
            missing += 1
            continue
        raw = float(original.get('Prob. grezza %', original['Prob. stimata %'])) / 100
        if abs(predictions[models.BASELINE] - raw) > .00051:
            mismatches += 1
            continue
        # Reproduce the site's actual displayed precision for all alternatives.
        predictions = {k: round(p*100, 1)/100 if p is not None else None for k,p in predictions.items()}
        predictions[models.BASELINE] = raw
        rows.append({**original, '_models': predictions})
    outcome = {line_key(row): row for row in verified if row.get('played') is True}
    panel = choose_panel(rows)
    paired = [{**row, 'actual': outcome[line_key(row)]['actual']} for row in panel if line_key(row) in outcome]
    tickets = {name: recommendations.evaluate(policy_select(rows, model, policy), verified)
               for name, model, policy in CONFIGS}
    return {'date': archive['date'], 'job_id': archive['job_id'], 'saved_at': archive['saved_at'],
            'eligible_lines': len(rows), 'missing_history_lines': missing, 'baseline_mismatch_lines': mismatches,
            'panel_selected': len(panel), 'panel_verified': len(paired),
            'models': {model: score(paired, model) for model in models.MODELS},
            'tickets': tickets}, paired


def run(archives):
    daily, all_paired, skipped = [], [], []
    evidence = {}
    for archive in sorted(archives, key=lambda a:a['date']):
        try:
            verified, _ = settle_espn.settle_archive(archive, archive['date'], evidence=evidence)
            result, paired = compare(archive, verified)
            daily.append(result); all_paired.extend(paired)
        except (ValueError, requests.RequestException) as exc:
            skipped.append({'date': archive['date'], 'reason': str(exc)[:200]})
    def day_mean(model):
        scores = [d['models'][model]['brier'] for d in daily if d['models'][model]['brier'] is not None]
        return sum(scores)/len(scores) if scores else None
    return {'study': models.VERSION, 'mode': 'retrospective_only', 'promotion_allowed': False,
            'panel_rule': 'One pregame line per player/market/fixture nearest odds 1.80 in 1.20–2.00, identical for all models',
            'daily': daily, 'skipped': skipped,
            'models': {model: score(all_paired, model) for model in models.MODELS},
            'equal_day_brier': {model: day_mean(model) for model in models.MODELS},
            'ticket_summary': {config: {group: {
                'won': sum(d['tickets'][config]['groups'][group]['status']=='won' for d in daily),
                'lost': sum(d['tickets'][config]['groups'][group]['status']=='lost' for d in daily),
                'unresolved': sum(d['tickets'][config]['groups'][group]['status']=='unresolved' for d in daily),
                'incomplete': sum(d['tickets'][config]['groups'][group]['status']=='incomplete' for d in daily)}
                for group,_,_,_ in recommendations.GROUPS} for config,_,_ in CONFIGS},
            'limitations': ['Four previously examined dates are not an independent holdout.',
                           'Player markets within one game remain correlated.',
                           'Injury reports are used only if present in the original pregame archive.',
                           'Ticket counts are hypothetical replays of current filters, not visitors actual bets.',
                           'Only Over predictions are available.'],
            'odds_api_calls':0, 'database_writes':0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dates', nargs='+', required=True)
    parser.add_argument('--saved-dir')
    args = parser.parse_args()
    archives = []
    for day in args.dates:
        if args.saved_dir:
            archive = json.loads((Path(args.saved_dir)/('archive-'+day[-2:]+'.json')).read_text())
        else:
            response = requests.get('https://nba-stats-4.onrender.com/api/saved/archive', params={'date':day,'include_logs':'true'}, timeout=60)
            response.raise_for_status(); archive = response.json()
        if archive.get('date') != day:
            raise ValueError('Archive date mismatch')
        archives.append(archive)
    print(json.dumps(run(archives), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
