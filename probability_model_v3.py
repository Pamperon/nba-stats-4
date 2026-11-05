"""Minutes and current-role probability model. Pure bounded CPU; no network I/O."""
import json, math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from statistics import median, pstdev

VERSION = 'minutes-role-calibrated-v3'
MARKETS = ('PTS','REB','AST')

def numeric(value):
    if isinstance(value,bool) or value is None or value=='':return None
    try:
        if isinstance(value,str) and ':' in value:
            m,s=value.split(':');value=float(m)+float(s)/60
        value=float(value)
        return value if math.isfinite(value) else None
    except (ValueError,TypeError):return None

def context(records,season,cutoff):
    stamp=datetime.fromisoformat(str(cutoff).replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('Timezone required')
    seen=set();samples=[]
    for original in records:
        identifier=str(original.get('GAME_ID') or '')
        if not identifier or identifier in seen:continue
        seen.add(identifier)
        try:
            raw=str(original['GAME_DATE']);day=datetime.fromisoformat(raw.replace('Z','+00:00'))
            if len(raw)==10:day=day.replace(tzinfo=timezone.utc)+timedelta(days=1)
            if day.tzinfo is None or day>=stamp or int(original.get('SEASON_TYPE') or 0)!=2:continue
        except (ValueError,TypeError,KeyError):continue
        mins=numeric(original.get('MIN'))
        if mins is None or not 0<mins<=80:continue
        label=str(original.get('ANNO_STAGIONE') or '')
        if not label:
            y=int(raw[:4])-(int(raw[5:7])<10);label=f'{y}-{str(y+1)[-2:]}'
        samples.append({**original,'_date':day,'_minutes':mins,'_season':label})
    samples.sort(key=lambda g:g['_date'],reverse=True)
    current=[g for g in samples if g['_season']==season]
    previous=[g for g in samples if g['_season']!=season][:50]
    recent=(current or samples)[:10]
    if not recent:return None
    m5=[g['_minutes'] for g in recent[:5]];m10=[g['_minutes'] for g in recent]
    expected=min(40,max(0,.7*median(m5)+.3*median(m10)))
    cv=pstdev(m10)/(sum(m10)/len(m10)) if sum(m10)>0 else 1
    current_weights=[.5**(i/10) for i in range(len(current))]
    previous_weights=[.15*.5**(i/20) for i in range(len(previous))]
    limit=.5*sum(current_weights) if current else 2
    if sum(previous_weights)>limit:
        previous_weights=[w*limit/sum(previous_weights) for w in previous_weights]
    weighted=list(zip(current,current_weights))+list(zip(previous,previous_weights))
    spread=min(.30, max(.08,cv))
    return {'weighted':weighted,'expected_minutes':expected,'minutes_cv':cv,'current_n':len(current),
            'history_n':len(samples),'scenarios':[(max(0,expected*(1-spread)),.2),(expected,.6),(min(48,expected*(1+spread)),.2)],
            'role_stable':len(current)>=5 and expected>=15 and cv<=.25}

def estimate(ctx,market,line,choice='Over'):
    line=numeric(line)
    if not ctx or market not in MARKETS or line is None or abs(line%1-.5)>1e-6 or choice not in ('Over','Under'):return None
    hits=weight=weight2=0.;count=0
    for game,w in ctx['weighted']:
        value=numeric(game.get(market))
        if value is None or value<0:continue
        # Keep short-minute games as downside evidence rather than inflating their rate.
        outcomes=[(value if game['_minutes']<8 else value/game['_minutes']*mins,prob) for mins,prob in ctx['scenarios']]
        rate=sum(prob for val,prob in outcomes if (val>line if choice=='Over' else val<line))
        hits+=w*rate;weight+=w;weight2+=w*w;count+=1
    if count<15 or weight<=0:return None
    p=(hits+1.5)/(weight+3)
    return {'raw_probability':p,'effective_n':weight*weight/weight2,
            'expected_minutes':ctx['expected_minutes'],'minutes_cv':ctx['minutes_cv'],
            'current_n':ctx['current_n'],'history_n':count,'role_stable':ctx['role_stable']}

@lru_cache(maxsize=1)
def artifact():
    try:
        data=json.loads(Path(__file__).with_name('probability_model_v3_calibration.json').read_text())
        return data if data.get('model_version')==VERSION else {}
    except (OSError,ValueError):return {}

def calibrated(features,market,as_of,training=None):
    data=artifact() if training is None else training
    p=features['raw_probability'];out={**features,'probability':p,'calibration_supported':False,'lower_bound':0.0}
    if not data or str(as_of)[:10]<=data.get('trained_through','9999'):return out
    cells=data.get('markets',{}).get(market,[])
    index=min(9,int(p*10));cell=next((c for c in cells if c['bin']==index),None)
    if not cell:return out
    # Calibration is fitted only to earlier outcomes. Do not inflate the raw estimate.
    corrected=min(p,float(cell['probability']))
    n=float(cell['effective_n']);se=math.sqrt(max(.001,corrected*(1-corrected))/(n+30))
    if n<100 or corrected-1.64*se<.80:corrected=min(corrected,.89)
    return {**out,'probability':max(.01,min(.99,corrected)),
            'calibration_supported':n>=20 and cell['days']>=3 and data.get('days',0)>=5,
            'lower_bound':max(0,corrected-1.64*se),'calibration_n':n,
            'trained_through':data['trained_through']}

def fields(features):
    return {'Modello probabilità':VERSION,'Prob. modello grezza %':round(features['raw_probability']*100,1),
            'Minuti attesi':round(features['expected_minutes'],1),'Variabilità minuti':round(features['minutes_cv'],3),
            'Campione effettivo':round(features['effective_n'],1),'Partite ruolo attuale':features['current_n'],
            'Ruolo stabile':features['role_stable'],'Calibrazione supportata':features['calibration_supported'],
            'Limite prudente %':round(features['lower_bound']*100,1),
            'Calibrazione fino al':features.get('trained_through')}

def apply_rows(rows,logs,season,target_day,cutoff):
    contexts={};output=[];estimated=0;eligible=0
    for original in rows:
        row=dict(original);name=row.get('Giocatore');ctx=contexts.get(name)
        if name not in contexts:
            records=logs.get(name,[])
            if records is None:records=[]
            if hasattr(records,'to_dict'):
                if records.empty or 'GAME_DATE' not in records.columns:records=[]
                else:
                    records=records.copy();records['GAME_DATE']=records['GAME_DATE'].dt.strftime('%Y-%m-%d');records=records.to_dict('records')
            contexts[name]=ctx=context(records,season,cutoff)
        row['Prob. storica %']=row.get('Prob. stimata %');row['Prob. grezza %']=row.get('Prob. stimata %')
        row['Modello probabilità']=VERSION
        features=estimate(ctx,row.get('Mercato'),row.get('Linea'),row.get('Scelta','Over'))
        row['Prob. stimata %']=None;row['Value stimato %']=None
        if features and original.get('Stato analisi')=='Valutabile (stima empirica)':
            f=calibrated(features,row['Mercato'],target_day);row.update(fields(f));estimated+=1
            row['Prob. stimata %']=round(f['probability']*100,1)
            price=numeric(row.get('Quota'))
            if price and price>1:row['Value stimato %']=round((f['probability']*price-1)*100,1)
            row['Nota']='Stima corretta per minuti attesi, ruolo recente e risultati precedenti; verifica disponibilità'
            eligible+=f['role_stable'] and f['calibration_supported']
        else:
            row['Ruolo stabile']=False;row['Calibrazione supportata']=False
            row['Stato analisi']='Non valutabile'
            row['Nota']='Dati insufficienti per stimare minuti, ruolo e probabilità corretta'
        output.append(row)
    return output,{'version':VERSION,'estimated':estimated,'role_and_calibration_supported':eligible,'trained_through':artifact().get('trained_through')}
