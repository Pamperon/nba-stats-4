"""Chronological replay of the fixed v3 candidate; no database writes or paid calls."""
import sys,json,collections,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import probability_model_v3 as model
DATA=Path(__file__).resolve().parents[1]/'audit-data'
def identity(row):return tuple(str(row.get(k,'')) for k in ('Partita','ESPN ID','Giocatore','Mercato','Scelta','Linea'))

def fit(entries):
    if not entries:return {}
    grouped=collections.defaultdict(list)
    for e in entries:grouped[(e['day'],e['id'],e['fixture'],e['market'])].append(e)
    stats=collections.defaultdict(lambda:{'n':0.,'wins':0.,'sum_p':0.,'days':set()})
    for group in grouped.values():
        w=1/len(group)
        for e in group:
            key=(e['market'],min(9,int(e['raw']*10)));s=stats[key];s['n']+=w;s['wins']+=w*e['win'];s['sum_p']+=w*e['raw'];s['days'].add(e['day'])
    markets={}
    for market in model.MARKETS:
        cells=[]
        for b in range(10):
            s=stats[(market,b)];n=s['n'];prior=s['sum_p']/n if n else (b+.5)/10
            cells.append({'bin':b,'effective_n':n,'days':len(s['days']),'probability':(s['wins']+30*prior)/(n+30)})
        # Weighted isotonic pooling preserves monotonic probabilities.
        blocks=[]
        for cell in cells:
            blocks.append(([cell],cell['probability'],cell['effective_n']+30))
            while len(blocks)>1 and blocks[-2][1]>blocks[-1][1]:
                b,p,w=blocks.pop();a,q,v=blocks.pop();blocks.append((a+b,(p*w+q*v)/(w+v),w+v))
        for group,p,_ in blocks:
            for c in group:c['probability']=p
        markets[market]=cells
    return {'model_version':model.VERSION,'days':len({e['day'] for e in entries}),
            'trained_through':max(e['day'] for e in entries),'markets':markets,'weighting':'one total unit per athlete-market-fixture-day'}

def entries():
    result=[];checks=collections.Counter()
    for file in sorted(DATA.glob('v3-source-*.json')):
        source=json.loads(file.read_text());day=source['scan_date'];season=source['season'];cutoff=source['cutoff'] or source['created_at']
        outcomes={identity(r):r for r in json.loads((DATA/('verified-'+day+'.json')).read_text())}
        contexts={name:model.context(log,season,cutoff) for name,log in (source['logs'] or {}).items()}
        for row in source['rows']:
            checked=outcomes.get(identity(row));checks['rows']+=1
            if not checked or checked.get('_win') is None or not checked.get('_pregame'):continue
            f=model.estimate(contexts.get(row['Giocatore']),row['Mercato'],row['Linea'],row['Scelta'])
            if not f:continue
            checks['estimated']+=1
            result.append({'day':day,'id':row.get('ESPN ID') or row['Giocatore'],'fixture':row['Partita'],'market':row['Mercato'],
                'win':checked['_win'],'raw':f['raw_probability'],'old':float(row['Prob. stimata %'])/100 if row.get('Prob. stimata %') is not None else None,'features':f,'row':row})
    print(dict(checks),flush=True);return result

def summary(items):
    if not items:return {'n':0}
    return {'n':len(items),'brier':sum((p-y)**2 for p,y in items)/len(items),'predicted_pct':100*sum(p for p,y in items)/len(items),'observed_pct':100*sum(y for p,y in items)/len(items)}

def main():
    data=entries();days=sorted({e['day'] for e in data});report=[];scored=[]
    for day in days:
        training=fit([e for e in data if e['day']<day]);today=[e for e in data if e['day']==day];old=[];raw=[];new=[];eligible=[]
        for e in today:
            f=model.calibrated(e['features'],e['market'],day,training)
            e={**e,'p':f['probability'],'support':f['calibration_supported'],'lower':f['lower_bound']};scored.append(e)
            if e['old'] is not None:old.append((e['old'],e['win']));raw.append((e['raw'],e['win']));new.append((e['p'],e['win']))
            if f['calibration_supported'] and f['role_stable'] and f['effective_n']>=10 and f['lower_bound']>=.55 and f['probability']>=.70:eligible.append((e['p'],e['win']))
        report.append({'day':day,'training_days':training.get('days',0),'old':summary(old),'new_raw':summary(raw),'new_calibrated':summary(new),'eligible':summary(eligible)})
    (DATA/'v3-replay-entries.json').write_text(json.dumps(scored))
    fit_all=fit(data);fit_all['validation']={'method':'chronological earlier days only','retrospective':True,'daily':report}
    Path('probability_model_v3_calibration.json').write_text(json.dumps(fit_all,indent=2))
    for r in report:print(json.dumps(r))
    print('ALL OLD',summary([(e['old'],e['win']) for e in scored if e['old'] is not None]))
    print('ALL NEW',summary([(e['p'],e['win']) for e in scored if e['old'] is not None]))
    later=[e for e in scored if e['day']>='2026-10-31' and e['old'] is not None]
    print('LATER OLD',summary([(e['old'],e['win']) for e in later]));print('LATER NEW',summary([(e['p'],e['win']) for e in later]))
    print('CALIBRATION CELLS',[(m,c['bin'],round(c['effective_n'],1),round(c['probability'],3)) for m,cells in fit_all['markets'].items() for c in cells if c['effective_n']>=20])
if __name__=='__main__':main()
