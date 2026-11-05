"""Read-only all-line selection audit. Saved pregame inputs; ESPN outcomes only.
No bookmaker calls, DB writes, or automatic production policy changes.
"""
import sys,json,math,collections,hashlib,concurrent.futures,uuid
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import settle_espn,recommendations,engine
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'audit-data'
CACHE=DATA/'espn-evidence';CACHE.mkdir(parents=True,exist_ok=True)
original_fetch=settle_espn.fetch

def cached_fetch(url,**params):
 key=hashlib.sha256(json.dumps([url,params],sort_keys=True).encode()).hexdigest()
 file=CACHE/(key+'.json')
 if file.exists():return json.loads(file.read_text())
 result=original_fetch(url,**params)
 if url.endswith('/summary'):result=settle_espn.compact_summary(result)
 elif url.endswith('/scoreboard'):result={'events':[{k:e.get(k) for k in ('id','date','status','competitions')} for e in result.get('events',[])]}
 temporary=file.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(result));temporary.replace(file)
 return result
settle_espn.fetch=cached_fetch

def num(x):
 try:return float(x) if x is not None and x!='' and math.isfinite(float(x)) else None
 except (ValueError,TypeError):return None

def summarize(rows):
 scored=[r for r in rows if r.get('_win') is not None and num(r.get('Prob. stimata %')) is not None]
 n=len(scored)
 if not n:return {'candidates':len(rows),'n':0}
 return {'candidates':len(rows),'n':n,'wins':sum(r['_win'] for r in scored),
 'hit_pct':round(100*sum(r['_win'] for r in scored)/n,2),
 'predicted_pct':round(sum(float(r['Prob. stimata %']) for r in scored)/n,2),
 'implied_pct':round(sum(100/float(r['Quota']) for r in scored)/n,2),
 'mean_odds':round(sum(float(r['Quota']) for r in scored)/n,3),
 'brier':round(sum((float(r['Prob. stimata %'])/100-r['_win'])**2 for r in scored)/n,5),
 'book_brier':round(sum((1/float(r['Quota'])-r['_win'])**2 for r in scored)/n,5),
 'roi_pct':round(100*sum(float(r['Quota'])*r['_win']-1 for r in scored)/n,2),
 'games':len({(r['_day'],r['Partita']) for r in scored}),
 'athlete_games':len({(r['_day'],r['Partita'],r.get('ESPN ID') or r.get('Giocatore')) for r in scored})}

def identity(row):return tuple(str(row.get(k,'')) for k in ('Partita','ESPN ID','Giocatore','Mercato','Scelta','Linea'))
def select(rows,key='prob',minimum=70,market=None,extra=None,single=False):
 eligible=[]
 for r in rows:
  if recommendations.rejection_reasons(r) or not 1.2<=float(r['Quota'])<=2.2 or float(r['Prob. stimata %'])<minimum:continue
  if market and r['Mercato']!=market:continue
  if extra and not extra(r):continue
  if single and not (1.7<=float(r['Quota'])<=1.9 and float(r['Prob. stimata %'])>70 and float(r['Prob. stimata %'])-100/float(r['Quota'])>=5):continue
  eligible.append(r)
 def rank(r):
  p=float(r['Prob. stimata %'])/100;q=float(r['Quota'])
  if key=='recent':
   parts=str(r.get('Ultime 10','0/1')).split('/')
   return float(parts[0])/max(1,float(parts[-1])) if len(parts)==2 else -1
  return {'prob':p,'value':p*q-1,'book':1/q}[key]
 eligible.sort(key=lambda r:(-rank(r),-float(r['Prob. stimata %']),str(r.get('Giocatore')),str(r.get('Mercato')),str(r.get('Linea'))))
 result=[];seen=set()
 for r in eligible:
  k=(r['Partita'],r.get('ESPN ID') or r['Giocatore'])
  if k not in seen:seen.add(k);result.append(r)
 return result[:1 if single else 10]

def day_audit(file):
 day=file.stem.replace('raw-','');items=json.loads(file.read_text());evidence={};out=[];errors=[]
 groups=collections.defaultdict(list)
 for item in items:groups[item['saved_at']].append(item['row'])
 for stamp,rows in groups.items():
  try:verified=settle_espn.settle_completed_fixtures({'results':rows,'saved_at':stamp},day,evidence)
  except Exception as e:errors.append(type(e).__name__+': '+str(e)[:150]);verified=[]
  lookup={identity(r):r for r in verified}
  for row in rows:
   r={**row,'_day':day,'_saved_at':stamp,'_win':None,'_status':'unresolved'}
   match=lookup.get(identity(r))
   if match and match.get('played') is True:
    actual=num(match.get('actual'));line=num(r.get('Linea'))
    if actual is not None and line is not None and actual!=line:
     r['_actual']=actual;r['_win']=int(actual>line if r['Scelta'].lower()=='over' else actual<line);r['_status']='played'
   elif match and match.get('status')=='not_played':r['_status']='not_played'
   out.append(r)
 events=evidence.get(('events',day),[])
 for r in out:
  fixture=frozenset(engine.normalized_name(t) for t in str(r.get('Partita','')).split(' - '))
  event=next((e for e in events if frozenset(engine.normalized_name(c['team']['displayName']) for c in e['competitions'][0]['competitors'])==fixture),None)
  if event:
   r['_event_id']=event['id'];r['_start']=event['date'];r['_pregame']=datetime.fromisoformat(r['_saved_at'].replace('Z','+00:00'))<datetime.fromisoformat(event['date'].replace('Z','+00:00'))
   summary=evidence.get(('summary',event['id']),{})
   actual_team=[g['team']['displayName'] for g in summary.get('boxscore',{}).get('players',[]) for stat in g.get('statistics',[]) for a in stat.get('athletes',[]) if str(a.get('athlete',{}).get('id'))==str(r.get('ESPN ID'))]
   if actual_team:r['_team_match']=engine.normalized_name(r.get('Squadra',''))==engine.normalized_name(actual_team[0]);r['_actual_team']=actual_team[0]
 (DATA/('verified-'+day+'.json')).write_text(json.dumps(out,ensure_ascii=False))
 print(day,len(out),dict(collections.Counter(r['_status'] for r in out)),flush=True)
 return out,errors

def analyze():
 allrows=[]
 for f in sorted(DATA.glob('verified-*.json')):allrows+=json.loads(f.read_text())
 rows=[r for r in allrows if r.get('_pregame') and num(r.get('Prob. stimata %')) is not None and num(r.get('Quota')) is not None and float(r['Quota'])>1]
 buckets={}
 for label,fn in [('market',lambda r:r['Mercato']),('probability',lambda r:str(min(90,int(float(r['Prob. stimata %'])//10)*10))),('odds',lambda r:'1.20–1.39' if 1.2<=float(r['Quota'])<1.4 else '1.40–1.69' if 1.4<=float(r['Quota'])<1.7 else '1.70–1.90' if 1.7<=float(r['Quota'])<=1.9 else '1.91–2.20' if 1.9<float(r['Quota'])<=2.2 else 'outside'),('current_season',lambda r:'0–4' if float(r.get('Stagione attuale (n)') or 0)<5 else '5–9' if float(r.get('Stagione attuale (n)') or 0)<10 else '10+')]:
  g=collections.defaultdict(list)
  for r in rows:g[fn(r)].append(r)
  buckets[label]={k:summarize(v) for k,v in sorted(g.items())}
 policies={'current':{},'value':{'key':'value'},'book':{'key':'book'},'recent':{'key':'recent'},'prob80':{'minimum':80},'prob90':{'minimum':90},'current5':{'extra':lambda r:float(r.get('Stagione attuale (n)') or 0)>=5},'current10':{'extra':lambda r:float(r.get('Stagione attuale (n)') or 0)>=10},'minutes90':{'extra':lambda r:float(r['Minuti ultime 5'])>=.9*float(r['Minuti medi'])},'PTS':{'market':'PTS'},'REB':{'market':'REB'},'AST':{'market':'AST'},'single':{'single':True,'key':'value'}}
 comparisons={};byday=collections.defaultdict(list)
 for r in rows:byday[r['_day']].append(r)
 dates=sorted(byday);split=dates[8] if len(dates)>8 else dates[-1]
 for policy,args in policies.items():
  chosen=[r for day,group in sorted(byday.items()) for r in select(group,**args)]
  comparisons[policy]={'all':summarize(chosen),'development':summarize([r for r in chosen if r['_day']<split]),'later_holdout':summarize([r for r in chosen if r['_day']>=split]),'daily':{day:summarize([r for r in chosen if r['_day']==day]) for day in dates}}
 reasons=collections.defaultdict(list)
 for r in rows:
  rejected=recommendations.rejection_reasons(r)
  for reason in rejected:reasons[reason].append(r)
 valid=[r for r in rows if not recommendations.rejection_reasons(r) and 1.2<=float(r['Quota'])<=2.2 and float(r['Prob. stimata %'])>=70]
 unique={}
 for r in sorted(rows,key=lambda r:(r['_saved_at'],identity(r))):unique.setdefault((r.get('_event_id'),r.get('ESPN ID'),r['Mercato']),r)
 range_rows=[r for r in rows if 1.2<=float(r['Quota'])<=2.2]
 stratified={}
 for market in ('PTS','REB','AST'):
  for lo,hi in ((1.2,1.4),(1.4,1.7),(1.7,1.91),(1.91,2.200001)):
   subset=[r for r in range_rows if r['Mercato']==market and lo<=float(r['Quota'])<hi]
   stratified[market+':'+str(lo)]={'all':summarize(subset),'passes':summarize([r for r in subset if not recommendations.rejection_reasons(r)]),'excluded':summarize([r for r in subset if recommendations.rejection_reasons(r)])}
 report={'scope':{'days':dates,'raw_unique_lines':len(allrows),'evaluable_pregame':len(rows),'resolved':sum(r['_win'] is not None for r in rows),'not_played':sum(r['_status']=='not_played' for r in rows),'team_mismatch_rows':sum(r.get('_team_match') is False for r in rows),'team_mismatch_athlete_games':len({(r.get('_event_id'),r.get('ESPN ID')) for r in rows if r.get('_team_match') is False}),'unknown_event':sum(not r.get('_event_id') for r in allrows),'post_start':sum(r.get('_pregame') is False for r in allrows),'split_date':split},'all':summarize(rows),'in_odds_range':summarize(range_rows),'stratified_screen':stratified,'one_line_per_athlete_market_game_first':summarize(list(unique.values())),'eligible':summarize(valid),'buckets':buckets,'rejections':{k:summarize(v) for k,v in reasons.items()},'policies':comparisons,'notes':['First observed saved line, deduplicated across scans; not an exact replay of the official 18:00 selection.','Policies fixed for descriptive comparison, no fitted thresholds. Later dates are a temporal sensitivity check, not an untouched prospective test.','Alternate lines and games involving the same athlete are correlated. ROI uses one nominal unit and quoted odds, excludes unresolved/DNP.','Results use exact fixture and ESPN athlete IDs. No bookmaker requests or DB writes.']}
 (DATA/'full-selection-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
 print(json.dumps({'scope':report['scope'],'overall':report['all'],'policies':{k:{a:b for a,b in v.items() if a!='daily'} for k,v in comparisons.items()}},indent=2))

if __name__=='__main__':
 if '--analyze-only' not in sys.argv:
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   for _,errors in pool.map(day_audit,sorted(DATA.glob('raw-*.json'))):
    if errors:print('ERRORS',errors,flush=True)
 analyze()
