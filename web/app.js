const $=id=>document.getElementById(id);let token='',jobId='',data=null;const savedKey='nba-stats-4-last-scan';const dbName='nba-stats-4-local-results';
function scanDB(){return new Promise((resolve,reject)=>{if(!('indexedDB'in window))return reject(new Error('Archivio browser non disponibile'));const r=indexedDB.open(dbName,1);r.onupgradeneeded=()=>r.result.createObjectStore('scans');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}
async function saveLocalScan(j){try{const db=await scanDB();await new Promise((resolve,reject)=>{const tx=db.transaction('scans','readwrite');tx.objectStore('scans').put(j,j.date);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});db.close();$('status').textContent+=' · copia salvata nel browser';}catch(e){$('status').textContent+=' · salvataggio locale non riuscito';}}
async function readLocalScan(date){const db=await scanDB();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('scans','readonly');const r=tx.objectStore('scans').get(date);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}finally{db.close()}}
async function showLocalScan(date){try{const j=await readLocalScan(date);if(!j)return false;data=j;jobId='';render();$('status').textContent=updatedStatus(j,true);return true}catch{return false}}
function updatedStatus(snapshot,local=false){
 const saved=snapshot?.saved_at;
 const when=saved?new Date(saved):null;
 const formatted=when&&!Number.isNaN(when.getTime())?when.toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'orario non disponibile';
 return 'Ultimo aggiornamento effettuato: '+formatted+(local?' · copia locale':'');
}
const fmtOdd=x=>x==null||x===''?'—':Number.isFinite(Number(x))?Number(x).toFixed(2).replace('.',','):String(x);
const fmt=x=>x==null?'—':x;
async function api(path,options={}){let r=await fetch(path,{...options,headers:{...options.headers}});if(!r.ok)throw new Error('HTTP '+r.status);return r}
async function loadCloudScan(date=null){try{const r=await api('/api/saved/latest'+(date?'?date='+encodeURIComponent(date):''));const j=await r.json();data=j;jobId='';render();$('status').textContent=updatedStatus(j);return true}catch{return false}}
let playerStatsInitialized=false;
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active');if(b.dataset.tab==='player'&&!playerStatsInitialized){playerStatsInitialized=true;initPlayers();}document.querySelectorAll('.tab').forEach(x=>x.hidden=x.id!==b.dataset.tab);$('quote-summary').hidden=!data||b.dataset.tab==='player'});
function renderDateStrip(){
 const select=$('date'), strip=$('date-strip'), month=$('date-month');
 if(!strip||!select)return;
 const dates=Array.from(select.options).map(o=>o.value).filter(Boolean);
 const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 strip.replaceChildren();
 for(const date of dates.filter(d=>d>=today)){
  const parsed=new Date(date+'T12:00:00');
  const chip=document.createElement('button');
  chip.type='button';chip.className='date-chip';chip.dataset.date=date;
  chip.setAttribute('aria-pressed',String(date===select.value));
  chip.setAttribute('aria-label',parsed.toLocaleDateString('it-IT',{weekday:'long',day:'numeric',month:'long',year:'numeric'}));
  const day=document.createElement('span');day.className='day-name';
  day.textContent=date===today?'OGGI':parsed.toLocaleDateString('it-IT',{weekday:'short'}).replace('.','').toUpperCase();
  const number=document.createElement('span');number.className='day-number';number.textContent=String(parsed.getDate());
  chip.append(day,number);
  chip.addEventListener('click',()=>{if(select.value!==date){select.value=date;select.dispatchEvent(new Event('change',{bubbles:true}));}else renderDateStrip();});
  strip.append(chip);
 }
 if(month){month.textContent=select.value?new Date(select.value+'T12:00:00').toLocaleDateString('it-IT',{month:'long',year:'numeric'}):'Nessuna giornata disponibile';}
}
let dateSelectionRequest=0;
function setDateLoading(loading){
 $('app').classList.toggle('date-is-loading',loading);
 $('date-loading').hidden=!loading;
}
$('date').addEventListener('change',async()=>{
 const selected=$('date').value;
 renderDateStrip();
 const request=++dateSelectionRequest;
 // Android Chrome can retain the native focus ring after the date menu closes.
 $('date').blur();
 setDateLoading(true);
 $('status').textContent='Caricamento archivio del '+selected+'…';
 try{
  const response=await api('/api/saved/latest?date='+encodeURIComponent(selected));
  const saved=await response.json();
  if(request!==dateSelectionRequest||$('date').value!==selected)return;
  data=saved;jobId='';render();
  $('status').textContent=updatedStatus(saved);
 }catch(error){
  if(request!==dateSelectionRequest||$('date').value!==selected)return;
  if(error.message==='HTTP 404'){
   // Read local data without letting an outdated request overwrite a newer date.
   let local=null;
   try{local=await readLocalScan(selected)}catch(e){}
   if(request!==dateSelectionRequest||$('date').value!==selected)return;
   if(local){
    data=local;jobId='';render();$('status').textContent=updatedStatus(local,true);
   }else{
    data=null;jobId='';render();
    $('status').textContent='Nessuna quota ancora disponibile per il '+selected+' · 0 chiamate OddsPapi';
   }
  }else{
   data=null;jobId='';render();
   $('status').textContent='Impossibile consultare Supabase per il '+selected+' ('+error.message+') · riprova più tardi';
  }
 }finally{
  if(request===dateSelectionRequest&&$('date').value===selected)setDateLoading(false);
 }
});
const number=x=>Number(x)||0;function eligible(){return (data?.results||[]).filter(r=>r['Stato analisi']==='Valutabile (stima empirica)'&&number(r['Quota'])>=number($('oddmin').value)&&number(r['Quota'])<=number($('oddmax').value)&&number(r['Prob. stimata %'])>=number($('probmin').value)&&($('market').value==='Tutti'||r.Mercato===$('market').value)).sort((a,b)=>number(b['Prob. stimata %'])-number(a['Prob. stimata %']))}
const marketNames={PTS:'PUNTI',REB:'RIMBALZI',AST:'ASSIST'};
const pickIdentityCache=new Map();
let pickProfileRequest=0;
function candidateAvatar(row){
 const name=String(row.Giocatore||'');
 const initials=name.trim().split(/\s+/).slice(0,2).map(part=>part[0]||'').join('').toUpperCase();
 return '<div class="pick-avatar"><span>'+esc(initials)+'</span></div>';
}
function setPickPhoto(avatar,id,name,request){
 if(!avatar||!/^\d{1,12}$/.test(String(id||'')))return;
 const photo=document.createElement('img');
 photo.alt='Foto di '+name;photo.loading='eager';photo.decoding='async';photo.referrerPolicy='no-referrer';
 photo.onload=()=>{if(request===pickProfileRequest&&photo.isConnected&&photo.naturalWidth>0)avatar.classList.add('has-photo')};
 photo.onerror=()=>{photo.remove();avatar.classList.remove('has-photo')};
 avatar.querySelector('img')?.remove();
 avatar.classList.remove('has-photo');avatar.appendChild(photo);
 photo.src='/api/players/headshot/'+encodeURIComponent(id);
}
async function enrichPickProfile(row,card,request){
 const avatar=card.querySelector('.pick-avatar');
 const meta=card.querySelector('.pick-player-meta');
 const name=String(row.Giocatore||'').trim();
 const id=String(row['ESPN ID']||'').trim();
 if(/^\d{1,12}$/.test(id)){setPickPhoto(avatar,id,name,request);return;}
 if(!name)return;
 try{
  if(!pickIdentityCache.has(name))pickIdentityCache.set(name,api('/api/players/resolve?name='+encodeURIComponent(name)).then(r=>r.json()).catch(error=>{pickIdentityCache.delete(name);throw error}));
  const profile=await pickIdentityCache.get(name);
  if(request!==pickProfileRequest||!card.isConnected)return;
  if(profile.team&&meta)meta.textContent=profile.team;
  setPickPhoto(avatar,profile.id,profile.name||name,request);
 }catch(error){console.warn('Dashboard ESPN identity unavailable:',name,error.message)}
}
// Keep a minimum evidence floor without requiring 80% hits in every window.
// Calibration estimates remain the source of probability, not the selection filter.
function pickRejectionReasons(row){
 const reasons=[];
 const p=Number(row['Prob. stimata %']),odd=Number(row.Quota);
 const games=Number(row['Partite']),season=Number(row['Stagione %']);
 const minutes=Number(row['Minuti medi']),recent=Number(row['Minuti ultime 5']);
 if(row['Stato analisi']!=='Valutabile (stima empirica)')reasons.push('analisi non valutabile');
 if(!Number.isFinite(p)||p<=0||p>=100)reasons.push('stima non valida');
 if(!Number.isFinite(odd)||odd<=1)reasons.push('quota non valida');
 if(!Number.isFinite(games)||games<10)reasons.push('meno di 10 partite');
 if(!Number.isFinite(season)||season<50)reasons.push('frequenza stagionale insufficiente');
 if(!Number.isFinite(minutes)||minutes<15)reasons.push('minuti medi insufficienti');
 if(!Number.isFinite(recent)||recent<0.65*minutes)reasons.push('minuti recenti in calo');
 if(Number.isFinite(p)&&Number.isFinite(odd)&&odd>1&&p-100/odd<3)reasons.push('value insufficiente');
 return reasons;
}
function reliablePick(row){return pickRejectionReasons(row).length===0;}
function pickCandidates(rows,min,max,count){
 const sorted=rows.filter(r=>reliablePick(r)&&number(r.Quota)>=min&&number(r.Quota)<=max)
 .sort((a,b)=>number(b['Prob. stimata %'])-number(a['Prob. stimata %'])||
 number(b['Value stimato %'])-number(a['Value stimato %']));
 const chosen=[],used=new Set();
 for(const row of sorted){
  const key=String(row.Giocatore||'').trim().toLowerCase();
  if(!key||used.has(key))continue;
  used.add(key);chosen.push(row);
  if(chosen.length===count)break;
 }
 return chosen;
}
function pickEmptyReason(rows,min,max,count,found){
 const inRange=rows.filter(r=>Number(r.Quota)>=min&&Number(r.Quota)<=max);
 if(!inRange.length)return 'Nessuna quota disponibile in questa fascia';
 const rejected=inRange.filter(r=>!reliablePick(r));
 if(found<count)return 'Nessuna selezione completa: '+found+' di '+count+' giocatori idonei ('+rejected.length+' esclusi dai controlli sui dati)';
 return '';
}
function pickCard(row){
 return '<article class="pick-selection"><div class="pick-profile">'+candidateAvatar(row)+
 '<div class="pick-profile-info"><h3>'+esc(row.Giocatore)+'</h3><p class="pick-player-meta">'+esc(row.Squadra||row.Partita)+'</p>'+
 '<div class="pick-market">OVER '+esc(row.Linea)+' '+esc(marketNames[row.Mercato]||row.Mercato)+'</div></div></div>'+
 '<div class="pick-values"><div><small>QUOTA</small><strong>'+esc(fmtOdd(row.Quota))+'</strong></div>'+
 '<div><small>STIMA</small><strong>'+esc(row['Prob. stimata %'])+'%</strong></div></div></article>';
}
function render(){
 const request=++pickProfileRequest;
 const summary=$('quote-summary');
 summary.hidden=!data||document.querySelector('nav button.active')?.dataset.tab==='player';
 if(data){
  const saved=data.saved_at?new Date(data.saved_at):null;
  const valid=saved&&!Number.isNaN(saved.getTime());
  $('quote-updated').textContent=valid?'Ultimo aggiornamento dati e quote salvati: '+saved.toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'Orario ultimo aggiornamento quote non disponibile';
 }

 if(!data){
  $('metrics').innerHTML='';
  $('picks').innerHTML='<div class="panel"><h2>Pronostici</h2><p>Nessuna quota ancora disponibile per la data selezionata.</p></div>';
  $('rows').innerHTML='';return;
 }
 const rows=data.results||[];
 $('metrics').innerHTML=[['PARTITE',data.fixture_count],['GIOCATORI',data.player_count],['QUOTE',rows.length]]
 .map(([label,value])=>'<div class="metric"><small>'+label+'</small><strong>'+fmt(value)+'</strong></div>').join('');
 const groups=[['Singola',1,1.70,2.00],['Doppia',2,1.40,1.69],['Tripla',3,1.20,1.39]];
 const pending=[];
 $('picks').innerHTML=groups.map(([title,count,min,max])=>{
  const chosen=pickCandidates(rows,min,max,count);
  const complete=chosen.length===count;
  const combined=chosen.reduce((product,r)=>product*number(r.Quota),1);
  const combinedProb=chosen.reduce((product,r)=>product*number(r['Prob. stimata %'])/100,1);
  const groupIndex=pending.length;
  pending.push(chosen);
  return '<section class="panel pick-group"><h2>'+title+'</h2><p class="pick-group-range">'+count+' selezion'+(count===1?'e':'i')+' · quote '+fmtOdd(min)+'–'+fmtOdd(max)+'</p>'+
  (complete?'<div class="pick-group-items">'+chosen.map(pickCard).join('')+'</div>'+
  (count>1?'<div class="pick-combined"><span>Quota totale <strong>'+fmtOdd(combined)+'</strong></span><span>Stima combinata indicativa <strong>'+Math.round(combinedProb*1000)/10+'%</strong></span></div>':''):
  '<p>'+esc(pickEmptyReason(rows,min,max,count,chosen.length))+'</p>')+
  '</section>';
 }).join('');
 $('picks').querySelectorAll('.pick-group').forEach((group,i)=>{
  group.querySelectorAll('.pick-selection').forEach((card,j)=>enrichPickProfile(pending[i][j],card,request));
 });
 renderFinder();
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
const nbaTeams={
 ATL:'ATL',BOS:'BOS',BKN:'BKN',BRK:'BKN',CHA:'CHA',CHI:'CHI',CLE:'CLE',DAL:'DAL',DEN:'DEN',DET:'DET',GSW:'GSW',GS:'GSW',HOU:'HOU',IND:'IND',LAC:'LAC',LAL:'LAL',MEM:'MEM',MIA:'MIA',MIL:'MIL',MIN:'MIN',NOP:'NOP',NO:'NOP',NYK:'NYK',NY:'NYK',OKC:'OKC',ORL:'ORL',PHI:'PHI',PHX:'PHX',PHO:'PHX',POR:'POR',SAC:'SAC',SAS:'SAS',SA:'SAS',TOR:'TOR',UTA:'UTA',UTAH:'UTA',WAS:'WAS',
 'ATLANTA HAWKS':'ATL','BOSTON CELTICS':'BOS','BROOKLYN NETS':'BKN','CHARLOTTE HORNETS':'CHA','CHICAGO BULLS':'CHI','CLEVELAND CAVALIERS':'CLE','DALLAS MAVERICKS':'DAL','DENVER NUGGETS':'DEN','DETROIT PISTONS':'DET','GOLDEN STATE WARRIORS':'GSW','HOUSTON ROCKETS':'HOU','INDIANA PACERS':'IND','LOS ANGELES CLIPPERS':'LAC','LA CLIPPERS':'LAC','LOS ANGELES LAKERS':'LAL','LA LAKERS':'LAL','MEMPHIS GRIZZLIES':'MEM','MIAMI HEAT':'MIA','MILWAUKEE BUCKS':'MIL','MINNESOTA TIMBERWOLVES':'MIN','NEW ORLEANS PELICANS':'NOP','NEW YORK KNICKS':'NYK','OKLAHOMA CITY THUNDER':'OKC','ORLANDO MAGIC':'ORL','PHILADELPHIA 76ERS':'PHI','PHOENIX SUNS':'PHX','PORTLAND TRAIL BLAZERS':'POR','PORTLAND TRAIL BLAZERS':'POR','SACRAMENTO KINGS':'SAC','SAN ANTONIO SPURS':'SAS','TORONTO RAPTORS':'TOR','UTAH JAZZ':'UTA','WASHINGTON WIZARDS':'WAS'
};
function teamAbbrev(team){const key=String(team||'').trim().toUpperCase().replace(/\s+/g,' ');return nbaTeams[key]||(/^[A-Z]{3}$/.test(key)?key:'—')}
function renderFinder(){$('rows').innerHTML=eligible().slice(0,500).map(r=>`<tr><td>${esc(r.Giocatore)}</td><td>${esc(teamAbbrev(r.Squadra))}</td><td>${esc(r.Mercato)}</td><td>${r.Linea}</td><td>${esc(fmtOdd(r.Quota))}</td><td class="good">${fmt(r['Prob. stimata %'])}</td><td>${esc(r['Ultime 20'])}</td><td>${fmt(r['Value stimato %'])}</td></tr>`).join('');syncFinderScrollWidth()}
// Value Finder filters affect only its own table; dashboard picks are independent.
function syncFinderScrollWidth(){
 const bottom=$('finder-scroll'),top=$('finder-top-scroll'),content=$('finder-top-scroll-content');
 if(!bottom||!top||!content)return;
 content.style.width=bottom.scrollWidth+'px';
 top.hidden=bottom.scrollWidth<=bottom.clientWidth+1;
}
function initFinderTopScroll(){
 const top=$('finder-top-scroll'),bottom=$('finder-scroll');
 let syncing=false;
 const sync=(from,to)=>{if(syncing)return;syncing=true;to.scrollLeft=from.scrollLeft;syncing=false};
 top.addEventListener('scroll',()=>sync(top,bottom),{passive:true});
 bottom.addEventListener('scroll',()=>sync(bottom,top),{passive:true});
 if('ResizeObserver' in window){const observer=new ResizeObserver(syncFinderScrollWidth);observer.observe(bottom);observer.observe(bottom.querySelector('table'));}
 window.addEventListener('resize',syncFinderScrollWidth);
 syncFinderScrollWidth();
}
initFinderTopScroll();
function initFinderSelects(){
 const odds=Array.from({length:179},(_,i)=>(1.10+i*0.05).toFixed(2));
 for(const id of ['oddmin','oddmax']){
  const select=$(id);
  select.innerHTML=odds.map(v=>'<option value="'+v+'">'+fmtOdd(v)+'</option>').join('');
  select.value=id==='oddmin'?'1.10':'2.20';
 }
 const prob=$('probmin');
 prob.innerHTML=Array.from({length:21},(_,i)=>'<option value="'+(i*5)+'">'+(i*5)+'%</option>').join('');
 prob.value='0';
}
initFinderSelects();
['oddmin','oddmax','market','probmin'].forEach(id=>{
 $(id).addEventListener('change',renderFinder);
});
$('csv').onclick=async()=>{if(!jobId){if(!data?.results?.length)return;const rows=data.results,keys=Object.keys(rows[0]);const safe=v=>{const t=String(v??'');const guarded=/^[=+@\\-\\t\\r]/.test(t)?"'"+t:t;return '"'+guarded.replace(/"/g,'""')+'"'};const csv='\uFEFF'+[keys.map(safe).join(';'),...rows.map(r=>keys.map(k=>safe(r[k])).join(';'))].join('\r\n');const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nba_stats_4_salvato.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;}try{const r=await api('/api/scan/'+jobId+'/csv');const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nba_stats_4_completo.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch{alert('CSV non disponibile')}};
let playerGames=[],playerRequest=0,rosterRequest=0,activeRoster=[];
const playerLogCache=new Map(),playerLogPending=new Map(),rosterCache=new Map();
const PLAYER_CACHE_LIMIT=80;
const PLAYER_CACHE_TTL=15*60*1000;
function cachePlayerLog(key,payload){
 playerLogCache.delete(key);playerLogCache.set(key,payload);
 if(playerLogCache.size>PLAYER_CACHE_LIMIT)playerLogCache.delete(playerLogCache.keys().next().value);
 try{sessionStorage.setItem('nba-player-log:'+key,JSON.stringify({at:Date.now(),payload}))}catch(e){}
}
function getPlayerLogCache(key){
 if(playerLogCache.has(key))return playerLogCache.get(key);
 try{
  const raw=sessionStorage.getItem('nba-player-log:'+key);
  if(raw){const item=JSON.parse(raw);if(Date.now()-item.at<PLAYER_CACHE_TTL){playerLogCache.set(key,item.payload);return item.payload}sessionStorage.removeItem('nba-player-log:'+key)}
 }catch(e){}
 return null;
}
async function fetchPlayerLog(team,id,season){
 const key=[team,id,season].join(':');
 const hit=getPlayerLogCache(key);if(hit!==null)return hit;
 if(playerLogPending.has(key))return playerLogPending.get(key);
 const params=new URLSearchParams({team_id:team,athlete_id:id,season});
 const task=api('/api/players/log?'+params).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(payload=>{cachePlayerLog(key,payload);return payload}).finally(()=>playerLogPending.delete(key));
 playerLogPending.set(key,task);return task;
}

const playerNum=x=>Number(x)||0;
async function initPlayers(){
 const now=new Date(),year=now.getFullYear(),start=now.getMonth()>=9?year:year-1;
 $('playerseason').innerHTML=[start,start-1,start-2].map(y=>'<option value="'+y+'">'+y+'/'+String(y+1).slice(-2)+'</option>').join('');
 $('player-status').textContent='Caricamento delle 30 squadre NBA…';
 try{const payload=await(await api('/api/players/teams')).json();
 $('team').innerHTML=payload.teams.map(t=>'<option value="'+esc(t.id)+'">'+esc(t.name)+'</option>').join('');
 await changeTeam();
 }catch(e){$('player-status').textContent='Catalogo NBA non disponibile ('+e.message+'). Ricarica la pagina.';}
}
function setPlayerLoading(loading){
 $('player').classList.toggle('player-is-loading',loading);
 $('player-loading').hidden=!loading;
}
async function changeTeam(){
 const request=++rosterRequest;
 ++playerRequest;
 const team=$('team').value;
 $('playername').innerHTML='';
 $('player-profile').hidden=true;
 $('player-status').textContent='';
 if(!team){setPlayerLoading(false);return;}
 setPlayerLoading(true);
 try{
  const payload=await(await api('/api/players/roster?team_id='+encodeURIComponent(team))).json();
  if(request!==rosterRequest)return;
  activeRoster=payload.players||[];
  $('playername').innerHTML=activeRoster.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>').join('');
  await changePlayer();
 }catch(e){
  if(request===rosterRequest){
   setPlayerLoading(false);
   $('player-status').textContent='Roster non disponibile ('+e.message+')';
  }
 }
}
function renderPlayerSeason(){
 const mode=$('playermode').value;
 const games=playerGames.filter(g=>mode==='all'||String(g.SEASON_TYPE)===mode);
 const avg=stat=>games.length?(games.reduce((total,g)=>total+playerNum(g[stat]),0)/games.length).toFixed(1):'—';
 $('player-season-stats').innerHTML=[['PARTITE',games.length],['PTS',avg('PTS')],['REB',avg('REB')],['AST',avg('AST')]].map(([label,value])=>'<div class="season-stat"><small>'+label+'</small><strong>'+value+'</strong></div>').join('');
}
async function loadPlayerProfile(request,team,id){
 const selected=$('playername').selectedOptions[0];
 const name=selected?.textContent||'Giocatore NBA';
 $('player-profile').hidden=false;
 $('player-display-name').textContent=name;
 $('player-meta').textContent=$('team').selectedOptions[0]?.textContent||'';
 $('player-initials').textContent=name.trim().split(/\\s+/).slice(0,2).map(x=>x[0]||'').join('').toUpperCase();
 const avatar=$('player-photo').parentElement;
 const oldPhoto=$('player-photo');
 // Replace the node to discard callbacks from previously selected players.
 const photo=document.createElement('img');
 photo.id='player-photo';
 photo.alt='Foto di '+name;
 photo.loading='eager';
 photo.decoding='async';
 photo.referrerPolicy='no-referrer';
 photo.onerror=()=>{if(request===playerRequest){photo.remove();avatar.classList.remove('has-photo')}};
 photo.onload=()=>{if(request===playerRequest&&photo.naturalWidth>0)avatar.classList.add('has-photo')};
 avatar.classList.remove('has-photo');
 oldPhoto.replaceWith(photo);
 photo.fetchPriority='high';
 photo.src='/api/players/headshot/'+encodeURIComponent(id);
 const profile=activeRoster.find(p=>p.id===id);
 if(profile){$('player-meta').textContent=[$('team').selectedOptions[0]?.textContent,profile.position,profile.jersey?'#'+profile.jersey:'',profile.height].filter(Boolean).join(' · ')}
 renderPlayerSeason();
}
async function changePlayer(){
 const request=++playerRequest,team=$('team').value,id=$('playername').value,season=$('playerseason').value;
 playerGames=[];
 $('player-summary').innerHTML='';
 $('chart').innerHTML='';
 $('player-status').textContent='';
 if(!team||!id){$('player-profile').hidden=true;setPlayerLoading(false);return;}
 setPlayerLoading(true);
 loadPlayerProfile(request,team,id);
 try{
  const payload=await fetchPlayerLog(team,id,season);
  if(request!==playerRequest)return;
  playerGames=payload.games||[];
  renderPlayerSeason();
  changeLine();
  if(!playerGames.length)$('player-status').textContent='Nessuna partita disponibile per questa stagione. Prova la stagione precedente.';
 }catch(e){
  if(request===playerRequest)$('player-status').textContent='Game log non disponibile ('+e.message+')';
 }finally{
  if(request===playerRequest)setPlayerLoading(false);
 }
}
function changeLine(){
 const stat=$('stat').value,values=playerGames.map(g=>playerNum(g[stat])).sort((a,b)=>a-b);
 const median=values.length?values[Math.floor(values.length/2)]:10;
 const max=stat==='PTS'?79:stat==='REB'?39:29;
 const lines=Array.from({length:max+1},(_,i)=>i+0.5);
 $('line').innerHTML=lines.map(x=>'<option value="'+x+'">'+x+'</option>').join('');
 $('line').value=String(Math.min(max+.5,Math.max(.5,Math.floor(median)+.5)));
 drawPlayer();
}
function drawPlayer(){
 renderPlayerSeason();
 const mode=$('playermode').value,window=$('playerwindow').value,stat=$('stat').value,line=playerNum($('line').value);
 let games=playerGames.filter(g=>mode==='all'||String(g.SEASON_TYPE)===mode);
 games=games.slice().sort((a,b)=>String(b.GAME_DATE||'').localeCompare(String(a.GAME_DATE||'')));
 if(window!=='all')games=games.slice(0,Number(window));
 const hits=games.filter(g=>playerNum(g[stat])>line).length;
 const avg=games.length?games.reduce((n,g)=>n+playerNum(g[stat]),0)/games.length:0;
 $('player-chart-title').textContent='Prestazioni · '+(window==='all'?'stagione completa':'ultime '+window)+' partite';
 $('player-summary').innerHTML=[['Over '+line,hits+'/'+games.length],['Frequenza Over',games.length?(100*hits/games.length).toFixed(1)+'%':'—'],['Media '+stat,games.length?avg.toFixed(1):'—']].map(([a,b])=>'<div class="metric"><small>'+esc(a)+'</small><strong>'+esc(b)+'</strong></div>').join('');
 const max=Math.max(line+1,...games.map(g=>playerNum(g[stat])),1);
 $('chart').innerHTML=games.slice().reverse().map(g=>{const val=playerNum(g[stat]);return '<div class="barrow"><span>'+esc(String(g.GAME_DATE||'').slice(5,10))+'</span><div class="track"><div class="fill '+(val>line?'':'under')+'" style="width:'+Math.min(100,val/max*100)+'%"></div><div class="line" style="left:'+Math.min(100,line/max*100)+'%"></div></div><strong>'+val+'</strong></div>'}).join('')||'<p>Nessuna partita per i filtri selezionati.</p>';
}
$('team').onchange=changeTeam;$('playername').onchange=changePlayer;$('playerseason').onchange=changePlayer;$('stat').onchange=changeLine;$('line').onchange=drawPlayer;$('playermode').onchange=drawPlayer;$('playerwindow').onchange=drawPlayer;
async function initializeArchive(){
 $('status').textContent='Caricamento giornate disponibili…';
 try {
  const response=await api('/api/saved/dates');
  const payload=await response.json();
  const dates=(payload.dates||[]).map(item=>item.date);
  $('date').innerHTML=dates.map(date=>'<option value="'+esc(date)+'">'+new Date(date+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'long',year:'numeric'})+'</option>').join('');
  if(!dates.length){$('date').innerHTML='<option value="">Nessuna giornata disponibile</option>';renderDateStrip();$('status').textContent='Nessuna analisi archiviata';return;}
  const todayRome=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  $('date').value=dates.includes(todayRome)?todayRome:dates[0];
  renderDateStrip();
  if(!await loadCloudScan($('date').value))$('status').textContent='Impossibile caricare le analisi salvate';
 }catch(error){$('status').textContent='Archivio temporaneamente non disponibile · '+error.message;}
}
initializeArchive();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
