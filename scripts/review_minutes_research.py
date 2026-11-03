"""Read-only development review. Historical reconstruction is not a holdout.

Input: JSON list of frozen snapshots with date, results, player_logs, and
scan_finished_at/saved_at. Optional verified JSON is exported by the ESPN audit.
No live model promotion, database writes, or bookmaker calls.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import minutes_research
import settle_espn


def key(row):
    return (row.get('Partita'),row.get('Squadra'),
            str(row.get('ESPN ID') or row.get('Giocatore')),
            row.get('Mercato'),str(row.get('Scelta','')).lower(),float(row['Linea']))


def metrics(rows):
    n=len(rows)
    if not n:
        return {'n':0}
    return {'n':n,'observed':sum(r['win'] for r in rows)/n,
            **{model:{'predicted':sum(r[model] for r in rows)/n,
                      'brier':sum((r[model]-r['win'])**2 for r in rows)/n}
               for model in ('baseline_probability','candidate_probability')}}


def paired_interval(rows, cluster_field, iterations=2000):
    groups=defaultdict(list)
    for row in rows:
        groups[row[cluster_field]].append(row)
    if len(groups)<2:
        return {'clusters':len(groups),'interval':None}
    # Resample complete games/dates, retaining the paired model comparison.
    blocks=list(groups.values());rng=random.Random(271828);deltas=[]
    for _ in range(iterations):
        draw=[row for block in rng.choices(blocks,k=len(blocks)) for row in block]
        deltas.append(sum((r['candidate_probability']-r['win'])**2-
                          (r['baseline_probability']-r['win'])**2 for r in draw)/len(draw))
    deltas.sort()
    return {'clusters':len(groups),'interval':[deltas[int(.025*iterations)],deltas[int(.975*iterations)]],
            'meaning':'candidate Brier minus baseline; negative favors candidate'}


def review(snapshots, supplied_verified=None):
    dates=[s['date'] for s in snapshots]
    if len(set(dates))!=len(dates):
        raise ValueError('Choose one snapshot per date before looking at outcomes')
    rows,days=[],[]
    evidence={}
    for snapshot in sorted(snapshots,key=lambda s:s['date']):
        day=snapshot['date']
        saved=snapshot.get('minutes_research')
        reconstruction=not isinstance(saved,dict)
        if reconstruction:
            saved=minutes_research.capture(snapshot.get('results',[]),snapshot.get('player_logs',{}),
                    snapshot.get('scan_finished_at') or snapshot['saved_at'])
        if saved.get('version')!=minutes_research.VERSION or saved.get('promotion_allowed') is not False:
            raise ValueError('Unexpected research version or release flag')
        if supplied_verified is None:
            verified,_=settle_espn.settle_archive(snapshot,day,evidence=evidence)
        else:
            verified=[r for r in supplied_verified if r['_audit_date']==day and r.get('played') is True]
        actuals={}
        for r in verified:
            try:
                value=float(r['actual'])
                if not math.isfinite(value) or value<0 or not value.is_integer():
                    continue
                identity=key(r)
                if identity in actuals and float(actuals[identity]['actual'])!=value:
                    raise ValueError('Conflicting verified outcomes')
                actuals[identity]=r
            except (KeyError,TypeError):
                continue
        paired=[]
        for row in saved['panel']:
            actual=actuals.get(key(row))
            if actual is None:
                continue
            win=int(actual['actual']>float(row['Linea']))
            paired.append({**row,'win':win,'date':day,
                           'game':day+':'+str(row['Partita'])})
        rows.extend(paired)
        days.append({'date':day,'historically_reconstructed':reconstruction,
                     'selected':saved['selected_before_labels'],'candidate_covered':len(saved['panel']),
                     'verified':len(paired),'excluded_history':saved['excluded'],**metrics(paired)})
    groups=defaultdict(list)
    for row in rows:
        f=row['features']
        groups['pregame_minutes_cv_high' if f['recent10_cv_minutes']>=.25 else 'pregame_minutes_cv_lower'].append(row)
        groups['pregame_last_minutes_drop' if f['last_game_minutes_ratio']<.8 else 'pregame_last_minutes_stable'].append(row)
    return {'version':minutes_research.VERSION,'promotion_allowed':False,
            'evaluation_type':'retrospective development; candidate defined after inspecting historical outcomes',
            'notes':['Not an out-of-sample validation or a causal estimate.',
                     'Unknown starts/role are not imputed.',
                     'No calibration settlements or selections are rewritten.',
                     'The candidate rescales historical scoring rates; score/minute transferability is unvalidated.'],
            'overall':metrics(rows),'by_date':days,
            'pregame_groups':{name:metrics(values) for name,values in groups.items()},
            'paired_brier_delta_game_cluster':paired_interval(rows,'game'),
            'paired_brier_delta_date_cluster':paired_interval(rows,'date'),
            'odds_api_calls':0,'database_writes':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--verified',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=review(json.loads(args.input.read_text()),
                  json.loads(args.verified.read_text()) if args.verified else None)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result['overall']))


if __name__=='__main__':
    main()
