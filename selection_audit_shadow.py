"""Freeze candidate daily rankings before outcomes. Never changes live picks."""
import math
import recommendations

VERSION = 'daily-selection-audit-v2-ten-days'

def athlete(row):
    return str(row.get('ESPN ID') or row.get('Giocatore') or '').strip().casefold()

def identity(row):
    return (str(row.get('Partita') or '').strip().casefold(), athlete(row),
            row.get('Mercato'), str(row.get('Scelta') or '').casefold(), float(row['Linea']))

def capture(rows, single_mode=False):
    rows = [{k: v for k, v in r.items() if k not in ('_models', '_shadow_probabilities')} for r in rows]
    single = recommendations.select_single(rows)
    excluded = '' if single_mode else athlete(single or {})
    pool = [r for r in rows if athlete(r) != excluded
            and not recommendations.rejection_reasons(r)
            and (1.70 if single_mode else 1.20) <= float(r['Quota']) <= (1.90 if single_mode else 2.20) and float(r['Prob. stimata %']) >= 70
            and (not single_mode or float(r['Prob. stimata %']) > 70 and float(r['Prob. stimata %'])-100/float(r['Quota']) >= 5)]
    variants = {}
    for name in ('current', 'minutes90', 'price_benchmark', 'recent10'):
        if name == 'current':
            variants[name] = ([single] if single else []) if single_mode else recommendations.select_daily(pool)['lines'][:10]
            continue
        candidates = [r for r in pool if name != 'minutes90'
                      or float(r['Minuti ultime 5']) >= .90 * float(r['Minuti medi'])]
        def rank(r):
            p = float(r['Prob. stimata %'])
            q = float(r['Quota'])
            parts = str(r.get('Ultime 10') or '').split('/')
            try:
                recent = float(parts[0]) / float(parts[1]) if len(parts) == 2 and float(parts[1]) > 0 else -1
            except ValueError:
                recent = -1
            primary = 1/q if name == 'price_benchmark' else recent if name == 'recent10' else p
            return (-primary, -p, -(p*q/100-1), str(r.get('Giocatore') or ''),
                    str(r.get('Mercato') or ''), str(r.get('Linea') or ''))
        selected, seen = [], set()
        for row in sorted(candidates, key=rank):
            key = (row.get('Partita'), athlete(row))
            if key in seen:
                continue
            seen.add(key)
            selected.append(row)
            if len(selected) == (1 if single_mode else 10):
                break
        variants[name] = selected
    return {'version': VERSION, 'promotion_allowed': False,
            'single_excluded_id': excluded, 'variants': variants,
            'protocol': {'target_game_days':10,'start_date':'2026-11-06','automatic_promotion':False},
            **({'singles': capture(rows, True)} if not single_mode else {})}

def evaluate(saved, verified):
    evidence = {identity(r): r for r in verified if r.get('played') is True}
    output = {}
    for name, rows in saved.get('variants', {}).items():
        results = []
        for row in rows:
            found = evidence.get(identity(row))
            if not found:
                continue
            try:
                actual, line, p, q = float(found['actual']), float(row['Linea']), float(row['Prob. stimata %'])/100, float(row['Quota'])
            except (KeyError, TypeError, ValueError):
                continue
            if not all(map(math.isfinite, (actual, line, p, q))) or actual == line:
                continue
            win = actual > line if str(row['Scelta']).casefold() == 'over' else actual < line
            results.append((int(win), p, q))
        n = len(results)
        output[name] = {'selected': len(rows), 'verified': n, 'unresolved': len(rows)-n,
                        'wins': sum(x[0] for x in results),
                        'mean_predicted': sum(x[1] for x in results)/n if n else None,
                        'brier': sum((p-y)**2 for y,p,_ in results)/n if n else None,
                        'flat_stake_roi': sum(y*q-1 for y,_,q in results)/n if n else None,
                        'success_pct': 100*sum(y for y,_,_ in results)/n if n else None}
    return {'version': saved.get('version'), 'promotion_allowed': False, 'variants': output,
            **({'singles':evaluate(saved['singles'],verified)} if saved.get('singles') else {})}
