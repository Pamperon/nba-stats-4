function setArchiveStatus(message,kind='info'){
 const status=$('status');
 status.textContent=message;
 status.hidden=kind==='info';
 status.setAttribute('role',kind==='error'?'alert':'status');
}
const $=id=>document.getElementById(id);let token='',jobId='',data=null;const savedKey='nba-stats-4-last-scan';const dbName='nba-stats-4-local-results';
function scanDB(){return new Promise((resolve,reject)=>{if(!('indexedDB'in window))return reject(new Error('Archivio browser non disponibile'));const r=indexedDB.open(dbName,1);r.onupgradeneeded=()=>r.result.createObjectStore('scans');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}
async function saveLocalScan(j){try{const db=await scanDB();await new Promise((resolve,reject)=>{const tx=db.transaction('scans','readwrite');tx.objectStore('scans').put(j,j.date);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});db.close();$('status').textContent+=' · copia salvata nel browser';}catch(e){$('status').textContent+=' · salvataggio locale non riuscito';}}
async function readLocalScan(date){const db=await scanDB();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('scans','readonly');const r=tx.objectStore('scans').get(date);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}finally{db.close()}}
async function showLocalScan(date){try{const j=await readLocalScan(date);if(!j)return false;data=j;jobId='';render();setArchiveStatus(updatedStatus(j,true),'notice');return true}catch{return false}}
function updatedStatus(snapshot,local=false){
 const saved=snapshot?.saved_at;
 const when=saved?new Date(saved):null;
 const formatted=when&&!Number.isNaN(when.getTime())?when.toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'orario non disponibile';
 return 'Ultimo aggiornamento effettuato: '+formatted+(local?' · copia locale':'');
}
const fmtOdd=x=>x==null||x===''?'—':Number.isFinite(Number(x))?Number(x).toFixed(2).replace('.',','):String(x);
const fmt=x=>x==null?'—':x;
async function api(path,options={}){let r=await fetch(path,{...options,headers:{...options.headers}});if(!r.ok)throw new Error('HTTP '+r.status);return r}
async function loadCloudScan(date=null){try{const r=await api('/api/saved/latest'+(date?'?date='+encodeURIComponent(date):''));const j=await r.json();data=j;jobId='';render();setArchiveStatus(updatedStatus(j));return true}catch{return false}}
let playerStatsInitialized=false;
let pickNavigationRequest=0;
let returnPick=null;
let returnOrigin='dashboard';
let lastQuoteTab='dashboard';
function syncArea(tab){
 const stats=tab==='player';
 document.body.classList.toggle('statistics-area',stats);
 $('date-area').hidden=stats;
 $('quote-tabs').classList.toggle('stats-mode',stats);
 for(const [id,active] of [['area-quotes',!stats],['area-stats',stats]]){
  $(id).classList.toggle('active',active);$(id).setAttribute('aria-pressed',String(active));
 }
 if(!stats)lastQuoteTab=tab;
}
$('area-quotes').onclick=()=>{returnPick=null;document.querySelector('nav button[data-tab="'+lastQuoteTab+'"]').click();};
$('area-stats').onclick=()=>{returnPick=null;document.querySelector('nav button[data-tab="player"]').click();};
$('back-to-picks').onclick=()=>{document.querySelector('nav button[data-tab="'+returnOrigin+'"]').click();if(returnPick?.isConnected)returnPick.focus({preventScroll:true});returnPick?.scrollIntoView?.({block:'center'});returnPick=null;};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active');syncArea(b.dataset.tab);if(b.dataset.tab!=='player')$('back-to-picks').hidden=true;if(b.dataset.tab==='player'&&!returnPick)$('back-to-picks').hidden=true;if(b.dataset.tab!=='player'){++pickNavigationRequest;++rosterRequest;++playerRequest;++seasonPrefetchGeneration;clearTimeout(seasonPrefetchTimer);setPlayerLoading(false);if(!activeRoster.length)playerStatsInitialized=false}if(b.dataset.tab==='player'){if(!playerStatsInitialized){playerStatsInitialized=true;initPlayers();}else if($('team').value&&activeRoster.length){prepareTeamLogs($('team').value,$('playerseason').value);if($('playername').value)preloadPlayerSeasons($('team').value,$('playername').value)}}document.querySelectorAll('.tab').forEach(x=>x.hidden=x.id!==b.dataset.tab);$('quote-summary').hidden=!data||b.dataset.tab==='player'});
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
let scanStatusTimer=0;
const scanStateNames={waiting:'In attesa di aggiornamento',queued:'In coda',running:'In elaborazione',done:'Completata',partial:'Parziale',error:'Fallita',save_failed:'Salvataggio fallito',interrupted:'Interrotta'};
async function loadScanStatus(date,request,previousState=null){
 try{
  const payload=await(await api('/api/saved/status?date='+encodeURIComponent(date))).json();
  if(request!==dateSelectionRequest||$('date').value!==date)return;
  if(!Object.hasOwn(scanStateNames,payload.state))throw Error('Stato non disponibile');
  const finished=['done','partial'].includes(payload.state);
  const newerSave=payload.last_saved?.job_id&&data?.job_id&&payload.last_saved.job_id!==data.job_id;
  if(previousState!==null&&finished&&(previousState!==payload.state||newerSave)){
   // The only refresh here reads a saved snapshot. Never starts a paid scan.
   $('date').dispatchEvent(new Event('change',{bubbles:true}));
   return;
  }
  scanStatusTimer=setTimeout(()=>loadScanStatus(date,request,payload.state),['queued','running'].includes(payload.state)?15000:60000);
 }catch(error){
  if(request!==dateSelectionRequest||$('date').value!==date)return;
  scanStatusTimer=setTimeout(()=>loadScanStatus(date,request,previousState),60000);
 }
}
let dateSelectionRequest=0;
function setDateLoading(loading){
 $('app').classList.toggle('date-is-loading',loading);
 $('date-loading').hidden=!loading;
 if(loading){
  // Clear the previous day's snapshot immediately; never show stale counts or picks.
  data=null;jobId='';
  ++pickProfileRequest;
  $('quote-summary').hidden=true;
  $('metrics').replaceChildren();
  $('quote-updated').textContent='';
  $('picks').replaceChildren();
  $('rows').replaceChildren();
  $('finder-cards').replaceChildren();$('finder-count').textContent='';
 }
}
$('date').addEventListener('change',async()=>{
 const selected=$('date').value;
 renderDateStrip();
 const request=++dateSelectionRequest;
 clearTimeout(scanStatusTimer);
 loadScanStatus(selected,request);
 // Android Chrome can retain the native focus ring after the date menu closes.
 $('date').blur();
 setDateLoading(true);
 setArchiveStatus('Caricamento archivio del '+selected+'…');
 try{
  const response=await api('/api/saved/latest?date='+encodeURIComponent(selected));
  const saved=await response.json();
  if(request!==dateSelectionRequest||$('date').value!==selected)return;
  data=saved;jobId='';render();
  setArchiveStatus(updatedStatus(saved));
 }catch(error){
  if(request!==dateSelectionRequest||$('date').value!==selected)return;
  if(error.message==='HTTP 404'){
   // Read local data without letting an outdated request overwrite a newer date.
   let local=null;
   try{local=await readLocalScan(selected)}catch(e){}
   if(request!==dateSelectionRequest||$('date').value!==selected)return;
   if(local){
    data=local;jobId='';render();setArchiveStatus(updatedStatus(local,true),'notice');
   }else{
    data=null;jobId='';render();
    setArchiveStatus('');
   }
  }else{
   data=null;jobId='';render();
   setArchiveStatus('Archivio temporaneamente non disponibile per il '+selected+' · riprova più tardi','error');
  }
 }finally{
  if(request===dateSelectionRequest&&$('date').value===selected)setDateLoading(false);
 }
});
const number=x=>Number(x)||0;const normalizeFinder=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();function eligible(){const words=normalizeFinder($('finder-search').value).trim().split(/\s+/).filter(Boolean);return (data?.results||[]).filter(r=>words.every(word=>normalizeFinder(r.Giocatore).includes(word))&&r['Stato analisi']==='Valutabile (stima empirica)'&&number(r['Quota'])>=number($('oddmin').value)&&number(r['Quota'])<=number($('oddmax').value)&&number(r['Prob. stimata %'])>=number($('probmin').value)&&($('market').value==='Tutti'||r.Mercato===$('market').value)).sort((a,b)=>number(b['Prob. stimata %'])-number(a['Prob. stimata %']))}
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
 if(games>=15&&recent<0.75*minutes&&minutes-recent>=5)reasons.push('forte calo del minutaggio');
 if(['out','doubtful','questionable','day-to-day','suspension'].includes(row['Disponibilità ESPN']))reasons.push('assenza o disponibilità incerta segnalata');
 if(row['Disponibilità ESPN']==='unknown')reasons.push('disponibilità non verificata');
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
 if(inRange.every(r=>r['Disponibilità ESPN']==='unknown'))return 'Disponibilità dei giocatori non verificata: proposte temporaneamente sospese.';
 const rejected=inRange.filter(r=>!reliablePick(r));
 if(found<count)return 'Nessuna selezione completa: '+found+' di '+count+' giocatori idonei ('+rejected.length+' esclusi dai controlli sui dati)';
 return '';
}
function pickExplanation(row){
 const isUnder=String(row.Scelta||'Over').toLowerCase()==='under';
 const line=Number(row.Linea),market=row.Mercato;
 const units={PTS:'punti',REB:'rimbalzi',AST:'assist'};
 const unit=units[market]||String(market||'');
 const threshold=(isUnder?'meno di ':'più di ')+esc(row.Linea)+' '+esc(unit);
 const num=x=>x===null||x===undefined||x===''?null:(Number.isFinite(Number(x))?Number(x):null);
 const display=x=>String(Math.round(x*10)/10).replace('.',',');
 const ratio=x=>{const m=String(x||'').match(/^(\d+)\s*\/\s*(\d+)$/);return m&&+m[2]>0&&+m[1]<=+m[2]?{hits:+m[1],total:+m[2]}:null};
 const match=val=>isUnder?val<line:val>line;
 const saved=data?.player_logs?.[row.Giocatore];
 const history=Array.isArray(saved)?saved.filter(g=>g&&/^\d{4}-\d{2}-\d{2}/.test(String(g.GAME_DATE||''))).slice().sort((a,b)=>String(b.GAME_DATE).localeCompare(String(a.GAME_DATE))):[];
 const valid=history.filter(g=>num(g[market])!==null);
 const games=num(row.Partite),season=num(row['Stagione %']);
 const historicHits=valid.filter(g=>match(num(g[market]))).length;
 const verified=Number.isFinite(line)&&games!==null&&valid.length===games&&season!==null&&Math.abs(100*historicHits/games-season)<0.11;
 const recent=ratio(row['Ultime 20']),last5=ratio(row['Ultime 5']);
 const sections=[];
 if(recent){
  let message='Ha fatto '+threshold+' in <strong>'+recent.hits+' delle ultime '+recent.total+' partite</strong> considerate.';
  if(verified&&games>0)message+=' Nello storico utilizzato: <strong>'+historicHits+' su '+games+'</strong>.';
  else if(season!==null&&games>0)message+=' Nello storico utilizzato: <strong>'+display(season)+'% su '+games+' partite</strong>.';
  sections.push('<p><b>📊 Il rendimento sulla linea</b>'+message+'</p>');
 }
 const avg=num(row['Minuti medi']),recentMin=num(row['Minuti ultime 5']);
 if(avg!==null&&recentMin!==null){
  const diff=recentMin-avg;
  const title=diff<=-2?'Sta giocando meno del solito':diff>=2?'Sta giocando più del solito':'Minutaggio recente simile alla media';
  sections.push('<p><b>⏱️ '+title+'</b>Nelle ultime 5 partite ha giocato in media <strong>'+display(recentMin)+' minuti</strong>, rispetto ai <strong>'+display(avg)+' minuti</strong> dello storico.</p>');
 }
 const probability=num(row['Prob. stimata %']),odd=num(row.Quota);
 if(probability!==null&&odd!==null&&odd>1){
  const implied=100/odd,relation=probability>implied?'più alta':probability<implied?'più bassa':'uguale';
  sections.push('<p><b>💡 Come valutiamo la quota</b>Il sistema stima una probabilità del <strong>'+display(probability)+'%</strong>. La quota '+fmtOdd(odd)+' corrisponde a circa il <strong>'+display(implied)+'%</strong>: secondo il modello la probabilità è '+relation+' di quella implicita nella quota.</p>');
 }
 const warnings=[];
 // A sequence is only reported when each of the latest observations has a
 // valid value and a distinct, ordered date. Do not use fresh post-scan logs.
 if(Number.isFinite(line)&&history.length>=2&&history.every(g=>num(g[market])!==null)&&new Set(history.map(g=>String(g.GAME_DATE).slice(0,10))).size===history.length){
  let misses=0;for(const g of history){if(match(num(g[market])))break;misses++}
  if(misses>=2)warnings.push('Nelle ultime <strong>'+misses+' partite consecutive</strong> non ha fatto '+threshold+'.');
 }
 if(!warnings.length&&last5&&last5.total>=5&&last5.hits<=2)warnings.push('Nelle ultime '+last5.total+' partite ha fatto '+threshold+' <strong>'+last5.hits+' volte</strong>.');
 const current=num(row['Stagione attuale (n)']);
 if(current!==null&&current<5){
  const previous=num(row['Stagione precedente (n)']);
  warnings.push('Nella stagione attuale sono disponibili '+current+' partite.'+(previous!==null&&previous>0?' La valutazione include anche '+previous+' partite della stagione precedente.':''));
 }
 if(warnings.length)sections.push('<p class="pick-explanation-warning"><b>⚠️ Da tenere d’occhio</b>'+warnings.join(' ')+'</p>');
 if(!sections.length)sections.push('<p>Dettagli non disponibili per questa scansione.</p>');
 return '<details class="pick-explanation"><summary>Perché questo pronostico?</summary><div class="pick-explanation-body">'+sections.join('')+'</div></details>';
}
function fixtureCard(match){
 const sides=String(match||'').split(' - ');
 if(sides.length!==2)return match?'<div class="pick-fixture">'+esc(match)+'</div>':'';
 const aliases={GSW:'gs',NOP:'no',NYK:'ny',SAS:'sa',UTA:'utah',WAS:'wsh'};
 const team=label=>{const code=teamAbbrev(label);const logo=aliases[code]||code.toLowerCase();
  return '<span class="fixture-team">'+(code==='—'?'':'<span class="team-logo"><img src="https://a.espncdn.com/i/teamlogos/nba/500/'+esc(logo)+'.png" alt="" loading="lazy" referrerpolicy="no-referrer"><span>'+esc(code)+'</span></span>')+'<span class="fixture-team-name"><span class="fixture-name-full">'+esc(label)+'</span><span class="fixture-name-short" aria-hidden="true">'+esc(code==='—'?label:code)+'</span></span></span>';};
 return '<div class="pick-fixture" data-match="'+esc(match)+'">'+team(sides[0])+'<span class="fixture-vs">VS</span>'+team(sides[1])+'<time class="fixture-time" hidden></time></div>';
}
function pickCard(row){
 return '<article class="pick-selection"><div class="pick-profile">'+candidateAvatar(row)+
 '<div class="pick-profile-info"><h3><button type="button" class="pick-player-link" aria-label="Apri le statistiche di '+esc(row.Giocatore)+'">'+esc(row.Giocatore)+'</button></h3><p class="pick-player-meta">'+esc(row.Squadra||'')+'</p></div></div>'+
 fixtureCard(row.Partita)+'<div class="pick-market">'+esc(row.Scelta||'Over').toUpperCase()+' '+esc(row.Linea)+' '+esc(marketNames[row.Mercato]||row.Mercato)+'</div>'+
 '<div class="pick-values"><div><small>QUOTA</small><strong>'+esc(fmtOdd(row.Quota))+'</strong></div>'+
 '<div><small>STIMA DEL MODELLO</small><strong>'+esc(row['Prob. stimata %'])+'%</strong></div></div><button type="button" class="pick-stats-button">Vedi statistiche <span aria-hidden="true">›</span></button>'+pickExplanation(row)+'</article>';
}
async function enrichSavedFixtureInfo(snapshot,request){
 if(!snapshot?.date||!snapshot.saved_at)return;
 try{
  const info=await(await api('/api/saved/time?date='+encodeURIComponent(snapshot.date))).json();
  if(request!==pickProfileRequest||data!==snapshot||$('date').value!==snapshot.date)return;
  const saved=new Date(snapshot.saved_at);
  if(Number.isNaN(saved.getTime()))return;
  const stamp=new Intl.DateTimeFormat('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(saved).replace(',','');
  if(stamp!==info.saved_at_italy)return;
  const labels={completa:'Copertura completa',in_attesa_quote:'Quote parziali o in attesa',errore_o_dati_incompleti:'Copertura incompleta'};
  if(labels[info.coverage_status])$('quote-updated').textContent+=' · '+labels[info.coverage_status];
  const reports=Array.isArray(info.fixture_reports)?info.fixture_reports:[];
  for(const fixture of $('picks').querySelectorAll('.pick-fixture[data-match]')){
   const matches=reports.filter(r=>r.partita===fixture.dataset.match&&r.inizio_italia);
   if(matches.length!==1)continue;
   const at=new Date(matches[0].inizio_italia);if(Number.isNaN(at.getTime()))continue;
   const el=fixture.querySelector('.fixture-time');el.textContent=at.toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});el.dateTime=at.toISOString();el.hidden=false;
  }
 }catch(error){/* The forecast remains usable when saved details are unavailable. */}
}

function render(){
 const request=++pickProfileRequest;
 const summary=$('quote-summary');
 summary.hidden=!data||document.querySelector('nav button.active')?.dataset.tab==='player';
 if(data){
  const saved=data.saved_at?new Date(data.saved_at):null;
  const valid=saved&&!Number.isNaN(saved.getTime());
  $('quote-updated').textContent=valid?((data.results||[]).length?'Aggiornato ':'Ultimo controllo: ')+saved.toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):'';
 }

 if(!data){
  $('metrics').innerHTML='';
  $('picks').innerHTML='<div class="panel"><h2>Pronostici</h2><p>Nessuna quota ancora disponibile per la data selezionata.</p></div>';
  $('rows').innerHTML='';$('finder-cards').innerHTML='';$('finder-count').textContent='';return;
 }
 const rows=data.results||[];
 $('metrics').innerHTML=[['PARTITE',data.fixture_count],['GIOCATORI',data.player_count],['QUOTE',rows.length]]
 .map(([label,value])=>'<div class="metric"><small>'+label+'</small><strong>'+fmt(value)+'</strong></div>').join('');
 const groups=[['Singola',1,1.70,2.00],['Doppia',2,1.40,1.69],['Tripla',3,1.20,1.39]];
 const pending=[];
 $('picks').innerHTML=groups.map(([title,count,min,max])=>{
  // Keep the exact versioned selections archived at scan time. Never replace
  // a started/removed leg with a different pick under the same saved ticket.
  const stored=data.recommendations?.groups?.[title];
  const chosen=stored?stored.legs.filter(p=>rows.some(r=>r.Giocatore===p.Giocatore&&r.Partita===p.Partita&&r.Mercato===p.Mercato&&r.Linea===p.Linea&&r.Scelta===p.Scelta)):pickCandidates(rows,min,max,count);
  const complete=chosen.length===count;
  const combined=chosen.reduce((product,r)=>product*number(r.Quota),1);
  const combinedProb=chosen.reduce((product,r)=>product*number(r['Prob. stimata %'])/100,1);
  const distinctGames=chosen.every(r=>r.Partita)&&new Set(chosen.map(r=>String(r.Partita).trim().toLowerCase())).size===chosen.length;
  const groupIndex=pending.length;
  pending.push(chosen);
  return '<section id="pick-'+title.toLowerCase()+'" class="panel pick-group pick-group-'+count+'" tabindex="-1"><div class="pick-group-heading"><h2>'+title+'</h2></div>'+ 
  (complete?'<div class="pick-group-items">'+chosen.map(pickCard).join('')+'</div>'+
  (count>1?'<div class="pick-combined"><span>Quota totale'+(distinctGames?'':' indicativa')+' <strong>'+fmtOdd(combined)+'</strong></span><span>Stima combinata indicativa <strong>'+Math.round(combinedProb*1000)/10+'%</strong></span>'+(distinctGames?'':'<p class="pick-combined-warning">Calcolo senza correlazioni. Verifica la quota sul bookmaker.</p>')+'</div>':''):
  '<p>'+esc(pickEmptyReason(rows,min,max,count,chosen.length))+'</p>')+
  '</section>';
 }).join('');
 $('picks').querySelectorAll('.pick-group').forEach((group,i)=>{
  group.querySelectorAll('.pick-selection').forEach((card,j)=>{
   const row=pending[i][j],open=()=>{returnOrigin='dashboard';returnPick=card.querySelector('.pick-stats-button');openPickStats(row);};
   card.querySelector('.pick-player-link').onclick=open;
   card.querySelector('.pick-stats-button').onclick=open;
   const avatar=card.querySelector('.pick-avatar');
   avatar.setAttribute('role','button');avatar.tabIndex=0;
   avatar.setAttribute('aria-label','Apri le statistiche di '+row.Giocatore);
   avatar.onclick=open;avatar.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}};
   card.querySelectorAll('.team-logo img').forEach(img=>{img.onload=()=>img.parentElement.classList.add('has-logo');img.onerror=()=>img.remove();});
   enrichPickProfile(row,card,request);
  });
 });
 enrichSavedFixtureInfo(data,request);
 renderFinder();
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
const nbaTeams={
 ATL:'ATL',BOS:'BOS',BKN:'BKN',BRK:'BKN',CHA:'CHA',CHI:'CHI',CLE:'CLE',DAL:'DAL',DEN:'DEN',DET:'DET',GSW:'GSW',GS:'GSW',HOU:'HOU',IND:'IND',LAC:'LAC',LAL:'LAL',MEM:'MEM',MIA:'MIA',MIL:'MIL',MIN:'MIN',NOP:'NOP',NO:'NOP',NYK:'NYK',NY:'NYK',OKC:'OKC',ORL:'ORL',PHI:'PHI',PHX:'PHX',PHO:'PHX',POR:'POR',SAC:'SAC',SAS:'SAS',SA:'SAS',TOR:'TOR',UTA:'UTA',UTAH:'UTA',WAS:'WAS',
 'ATLANTA HAWKS':'ATL','BOSTON CELTICS':'BOS','BROOKLYN NETS':'BKN','CHARLOTTE HORNETS':'CHA','CHICAGO BULLS':'CHI','CLEVELAND CAVALIERS':'CLE','DALLAS MAVERICKS':'DAL','DENVER NUGGETS':'DEN','DETROIT PISTONS':'DET','GOLDEN STATE WARRIORS':'GSW','HOUSTON ROCKETS':'HOU','INDIANA PACERS':'IND','LOS ANGELES CLIPPERS':'LAC','LA CLIPPERS':'LAC','LOS ANGELES LAKERS':'LAL','LA LAKERS':'LAL','MEMPHIS GRIZZLIES':'MEM','MIAMI HEAT':'MIA','MILWAUKEE BUCKS':'MIL','MINNESOTA TIMBERWOLVES':'MIN','NEW ORLEANS PELICANS':'NOP','NEW YORK KNICKS':'NYK','OKLAHOMA CITY THUNDER':'OKC','ORLANDO MAGIC':'ORL','PHILADELPHIA 76ERS':'PHI','PHOENIX SUNS':'PHX','PORTLAND TRAIL BLAZERS':'POR','PORTLAND TRAIL BLAZERS':'POR','SACRAMENTO KINGS':'SAC','SAN ANTONIO SPURS':'SAS','TORONTO RAPTORS':'TOR','UTAH JAZZ':'UTA','WASHINGTON WIZARDS':'WAS'
};
function teamAbbrev(team){const key=String(team||'').trim().toUpperCase().replace(/\s+/g,' ');return nbaTeams[key]||(/^[A-Z]{3}$/.test(key)?key:'—')}
function renderFinder(){
 const all=eligible(),items=all.slice(0,500);
 $('finder-count').textContent=all.length>500?'Primi 500 di '+all.length+' risultati':all.length+' risultat'+(all.length===1?'o':'i');
 $('rows').innerHTML=items.map((r,i)=>`<tr><td><button type="button" class="finder-player" data-index="${i}">${esc(r.Giocatore)}</button></td><td>${esc(teamAbbrev(r.Squadra))}</td><td>${esc(r.Mercato)}</td><td>${esc(r.Linea)}</td><td>${esc(fmtOdd(r.Quota))}</td><td class="good">${esc(fmt(r['Prob. stimata %']))}</td><td>${esc(r['Ultime 20'])}</td><td>${esc(fmt(r['Value stimato %']))}</td></tr>`).join('');
 $('finder-cards').innerHTML=items.map((r,i)=>`<article class="finder-card"><div class="finder-card-top"><div class="finder-card-identity"><strong>${esc(r.Giocatore)}</strong><div class="finder-card-subline"><span class="finder-card-team">${esc(teamAbbrev(r.Squadra))}</span><span class="finder-card-market">${esc(String(r.Scelta||'Over').toUpperCase())} ${esc(r.Linea)} ${esc(marketNames[r.Mercato]||r.Mercato)}</span></div></div><button type="button" class="finder-player" data-index="${i}">Vedi statistiche</button></div><div class="finder-card-values"><span><small>Quota</small><b>${esc(fmtOdd(r.Quota))}</b></span><span><small>Stima</small><b>${esc(fmt(r['Prob. stimata %']))}%</b></span></div><button type="button" class="finder-details-toggle" aria-expanded="false" aria-controls="finder-extra-${i}">Altri dati</button><div class="finder-extra" id="finder-extra-${i}" hidden>Ultime 20: <b>${esc(r['Ultime 20']||'—')}</b> · Value: <b>${esc(fmt(r['Value stimato %']))}%</b></div></article>`).join('')||'<p class="finder-empty">Nessuna quota corrisponde ai filtri selezionati.</p>';
 for(const button of document.querySelectorAll('#finder .finder-details-toggle'))button.onclick=()=>{const extra=document.getElementById(button.getAttribute('aria-controls'));if(!extra)return;extra.hidden=!extra.hidden;button.setAttribute('aria-expanded',String(!extra.hidden));};
 for(const button of document.querySelectorAll('#finder .finder-player'))button.onclick=()=>{const row=items[Number(button.dataset.index)];if(!row)return;returnOrigin='finder';returnPick=button;openPickStats(row);};
 syncFinderScrollWidth();
}

// Value Finder filters affect only its own table; dashboard picks are independent.
function syncFinderScrollWidth(){
 const bottom=$('finder-scroll'),top=$('finder-top-scroll'),content=$('finder-top-scroll-content');
 if(!bottom||!top||!content)return;
 content.style.width=bottom.scrollWidth+'px';
 top.hidden=bottom.scrollWidth<=bottom.clientWidth+1;
}
function initFinderTopScroll(){
 const top=$('finder-top-scroll'),bottom=$('finder-scroll');
 // Batch mirroring to one animation frame instead of forcing a second scroll
 // event and layout calculation for every touch-move event.
 let pending=null,frame=0;
 const mirror=(source,target)=>{
  pending={source,target};
  if(frame)return;
  frame=requestAnimationFrame(()=>{
   frame=0;
   if(!pending)return;
   const {source,target}=pending;pending=null;
   if(Math.abs(target.scrollLeft-source.scrollLeft)>1)target.scrollLeft=source.scrollLeft;
  });
 };
 top.addEventListener('scroll',()=>mirror(top,bottom),{passive:true});
 bottom.addEventListener('scroll',()=>mirror(bottom,top),{passive:true});
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
$('finder-search').addEventListener('input',renderFinder);
['oddmin','oddmax','market','probmin'].forEach(id=>{
 $(id).addEventListener('change',renderFinder);
});
function csvCell(value){
 const text=String(value??'');
 const guarded=/^[=+@\-\t\r]/.test(text)||/^\d+\/\d+$/.test(text)?"'"+text:text;
 return '"'+guarded.replace(/"/g,'""')+'"';
}
$('csv').onclick=async()=>{if(!jobId){if(!data?.results?.length)return;const rows=data.results,keys=Object.keys(rows[0]);const safe=csvCell;const csv='\uFEFF'+[keys.map(safe).join(';'),...rows.map(r=>keys.map(k=>safe(r[k])).join(';'))].join('\r\n');const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='basketlab_salvato.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;}try{const r=await api('/api/scan/'+jobId+'/csv');const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='basketlab_completo.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch{alert('CSV non disponibile')}};
let playerGames=[],playerRequest=0,rosterRequest=0,activeRoster=[];
const playerLogCache=new Map(),playerLogPending=new Map(),rosterCache=new Map();
const PLAYER_CACHE_LIMIT=80;
const PLAYER_CACHE_TTL=15*60*1000;
function currentPlayerSeason(){const now=new Date();return now.getMonth()>=9?now.getFullYear():now.getFullYear()-1}
function historicalPlayerKey(key){const year=Number(key.split(':').pop());return Number.isInteger(year)&&year>=2000&&year<currentPlayerSeason()}
function playerCacheTTL(key){return historicalPlayerKey(key)?24*60*60*1000:PLAYER_CACHE_TTL}
function persistHistoricalLog(key,item){
 try{
  const prefix='nba-player-history:',keys=[];
  for(let i=0;i<localStorage.length;i++){const name=localStorage.key(i);if(name?.startsWith(prefix))keys.push(name)}
  const entries=keys.map(name=>{try{return {name,at:JSON.parse(localStorage.getItem(name)).at||0}}catch(e){return {name,at:0}}}).sort((a,b)=>a.at-b.at);
  while(entries.length>=24)localStorage.removeItem(entries.shift().name);
  localStorage.setItem(prefix+key,JSON.stringify(item));
 }catch(e){}
}
function rememberPlayerLog(key,item){
 playerLogCache.delete(key);playerLogCache.set(key,item);
 if(playerLogCache.size>PLAYER_CACHE_LIMIT)playerLogCache.delete(playerLogCache.keys().next().value);
}
function cachePlayerLog(key,payload){
 const item={at:Date.now(),payload};
 rememberPlayerLog(key,item);
 try{sessionStorage.setItem('nba-player-log:'+key,JSON.stringify(item))}catch(e){}
 if(historicalPlayerKey(key))persistHistoricalLog(key,item);
}
function getPlayerLogCache(key){
 const fresh=item=>item&&Number.isFinite(item.at)&&Date.now()-item.at>=0&&Date.now()-item.at<playerCacheTTL(key);
 const memory=playerLogCache.get(key);
 if(fresh(memory))return memory.payload;
 playerLogCache.delete(key);
 try{
  const raw=sessionStorage.getItem('nba-player-log:'+key);
  if(raw){
   const item=JSON.parse(raw);
   if(fresh(item)){rememberPlayerLog(key,item);return item.payload}
   sessionStorage.removeItem('nba-player-log:'+key);
  }
 }catch(e){}
 if(historicalPlayerKey(key)){
  try{
   const name='nba-player-history:'+key,item=JSON.parse(localStorage.getItem(name));
   if(fresh(item)){rememberPlayerLog(key,item);return item.payload}
   localStorage.removeItem(name);
  }catch(e){}
 }
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

// Catalog and roster revisits need no round trip while their cache is fresh.
async function playerCatalog(path){
 const key='nba-player-catalog:'+path,now=Date.now();
 let item=rosterCache.get(path);
 if(!item){try{item=JSON.parse(sessionStorage.getItem(key))}catch(e){}}
 if(item&&Number.isFinite(item.at)&&now>=item.at&&now-item.at<PLAYER_CACHE_TTL){
  rosterCache.set(path,item);return item.payload;
 }
 const payload=await(await api(path)).json();
 item={at:Date.now(),payload};rosterCache.set(path,item);
 try{sessionStorage.setItem(key,JSON.stringify(item))}catch(e){}
 return payload;
}
const teamLogBatches=new Map();
function prepareTeamLogs(team,season){
 const players=activeRoster.slice();
 clearTimeout(seasonPrefetchTimer);
 const key=team+':'+season;
 let batch=teamLogBatches.get(key);
 if(!batch||Date.now()-batch.at>=PLAYER_CACHE_TTL){
  batch={at:Date.now(),task:api('/api/players/team-logs?'+new URLSearchParams({team_id:team,season})).then(r=>r.json()).then(data=>{
   for(const [id,payload] of Object.entries(data.logs||{})){
    if(players.some(p=>p.id===id)&&payload.athlete_id===id&&payload.season===season&&!getPlayerLogCache([team,id,season].join(':'))){cachePlayerLog([team,id,season].join(':'),payload)}
   }
  }).catch(()=>{teamLogBatches.delete(key)})};
  teamLogBatches.set(key,batch);
 }
 // Read saved team logs only. Never start unrelated ESPN season downloads
 // while a visitor is waiting for the selected player's statistics.
 return batch.task;
}
let seasonPrefetchTimer,seasonPrefetchGeneration=0,seasonPrefetchTask=Promise.resolve();
function preloadPlayerSeasons(team,id){
 clearTimeout(seasonPrefetchTimer);
 const generation=++seasonPrefetchGeneration;
 const seasons=[...$('playerseason').options].map(o=>o.value);
 const active=()=>generation===seasonPrefetchGeneration&&$('team').value===team&&$('playername').value===id&&document.querySelector('nav button.active')?.dataset.tab==='player';
 seasonPrefetchTimer=setTimeout(()=>{
  seasonPrefetchTask=seasonPrefetchTask.catch(()=>{}).then(async()=>{
  for(const season of seasons){
   if(!active())return;
   if(getPlayerLogCache([team,id,season].join(':'))!==null)continue;
   try{await fetchPlayerLog(team,id,season)}catch(e){/* Optional preload; selection can retry. */}
  }
  });
 },150);
}

const playerNum=x=>Number(x)||0;
async function openPickStats(row){
 const navigation=++pickNavigationRequest;
 syncArea('player');
 $('back-to-picks').textContent=returnOrigin==='finder'?'← Torna ad Analisi quote':'← Torna ai pronostici';
 $('back-to-picks').hidden=false;
 ++rosterRequest;++playerRequest;++seasonPrefetchGeneration;
 clearTimeout(seasonPrefetchTimer);
 document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.tab==='player'));
 document.querySelectorAll('.tab').forEach(tab=>tab.hidden=tab.id!=='player');
 $('quote-summary').hidden=true;
 playerStatsInitialized=true;setPlayerLoading(true);
 $('player-profile').hidden=true;$('chart').replaceChildren();$('player-summary').replaceChildren();
 $('player-status').textContent='Apertura statistiche di '+row.Giocatore+'…';
 const selection={id:String(row['ESPN ID']||''),team:row.Squadra,market:row.Mercato,line:Number(row.Linea),season:String(data?.season||'').slice(0,4),navigation};
 try{
  if(!/^\d{1,12}$/.test(selection.id)){
   const profile=await(await api('/api/players/resolve?name='+encodeURIComponent(row.Giocatore))).json();
   if(navigation!==pickNavigationRequest)return;
   selection.id=String(profile.id||'');selection.team=profile.team||selection.team;
  }
  if(navigation!==pickNavigationRequest)return;
  await initPlayers(selection);
 }catch(error){
  if(navigation===pickNavigationRequest){setPlayerLoading(false);$('player-status').textContent='Statistiche del giocatore non disponibili. Riprova dal pronostico.';}
 }
}
async function initPlayers(selection=null){
 const navigation=pickNavigationRequest;
 const now=new Date(),year=now.getFullYear(),start=now.getMonth()>=9?year:year-1;
 $('playerseason').innerHTML=[start,start-1,start-2].map(y=>'<option value="'+y+'">'+y+'/'+String(y+1).slice(-2)+'</option>').join('');
 $('player-status').textContent='Caricamento delle 30 squadre NBA…';
 try{const payload=await playerCatalog('/api/players/teams');
 if(navigation!==pickNavigationRequest)return;
 $('team').innerHTML=payload.teams.map(t=>'<option value="'+esc(t.id)+'">'+esc(t.name)+'</option>').join('');
 if(selection){
  const abbreviation=teamAbbrev(selection.team);
  const team=payload.teams.find(t=>t.name===selection.team||(abbreviation!=='—'&&teamAbbrev(t.name)===abbreviation));
  if(!team)throw Error('Squadra del pronostico non trovata');
  $('team').value=String(team.id);
  if([...$('playerseason').options].some(o=>o.value===selection.season))$('playerseason').value=selection.season;
  $('stat').value=selection.market;$('playermode').value='2';$('playerwindow').value='20';
 }
 await changeTeam(selection);
 }catch(e){if(navigation!==pickNavigationRequest)return;playerStatsInitialized=false;setPlayerLoading(false);$('player-status').textContent='Statistiche non disponibili ('+e.message+'). Riprova dal pronostico o riapri la scheda.';}
}
function setPlayerLoading(loading){
 $('player').classList.toggle('player-is-loading',loading);
 $('player-loading').hidden=!loading;
}
async function changeTeam(selection=null){
 const request=++rosterRequest;
 ++playerRequest;
 const team=$('team').value;
 $('playername').innerHTML='';
 $('player-profile').hidden=true;
 $('player-status').textContent='';
 if(!team){setPlayerLoading(false);return;}
 setPlayerLoading(true);
 try{
  const payload=await playerCatalog('/api/players/roster?team_id='+encodeURIComponent(team));
  if(request!==rosterRequest)return;
  if(selection?.navigation&&selection.navigation!==pickNavigationRequest)return;
  activeRoster=payload.players||[];
  $('playername').innerHTML=activeRoster.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>').join('');
  if(selection?.id){
   if(!activeRoster.some(p=>String(p.id)===selection.id))throw Error('Giocatore del pronostico non presente nel roster');
   $('playername').value=selection.id;
  }
  prepareTeamLogs(team,$('playerseason').value);
  await changePlayer(selection);
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
 $('player-initials').textContent=name.trim().split(/\s+/).slice(0,2).map(x=>x[0]||'').join('').toUpperCase();
 const avatar=$('player-photo').parentElement;
 const oldPhoto=$('player-photo');
 // Replace the node to discard callbacks from previously selected players.
 const photo=document.createElement('img');
 photo.id='player-photo';
 photo.alt='Foto di '+name;
 photo.loading='eager';
 photo.decoding='async';
 photo.referrerPolicy='no-referrer';
 photo.onerror=()=>{if(request===playerRequest){photo.hidden=true;avatar.classList.remove('has-photo')}};
 photo.onload=()=>{if(request===playerRequest&&photo.naturalWidth>0)avatar.classList.add('has-photo')};
 avatar.classList.remove('has-photo');
 oldPhoto.replaceWith(photo);
 photo.fetchPriority='high';
 photo.src='/api/players/headshot/'+encodeURIComponent(id);
 const profile=activeRoster.find(p=>p.id===id);
 if(profile){$('player-meta').textContent=[$('team').selectedOptions[0]?.textContent,profile.position,profile.jersey?'#'+profile.jersey:'',profile.height].filter(Boolean).join(' · ')}
 renderPlayerSeason();
}
async function changePlayer(selection=null,preserveLine=false){
 clearTimeout(seasonPrefetchTimer);++seasonPrefetchGeneration;
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
  preloadPlayerSeasons(team,id);
  renderPlayerSeason();
  changeLine(preserveLine);
  if(selection?.id===id&&selection.market===$('stat').value&&Number.isFinite(selection.line)){
   const value=String(selection.line);
   if(![...$('line').options].some(o=>o.value===value))$('line').add(new Option(value,value));
   $('line').value=value;drawPlayer();
  }
  if(!playerGames.length)$('player-status').textContent='Nessuna partita disponibile per questa stagione. Prova la stagione precedente.';
 }catch(e){
  if(request===playerRequest)$('player-status').textContent='Game log non disponibile ('+e.message+')';
 }finally{
  if(request===playerRequest)setPlayerLoading(false);
 }
}
function changeLine(preserveSelected=false){
 const selected=preserveSelected?$('line').value:null;
 const stat=$('stat').value,values=playerGames.map(g=>playerNum(g[stat])).sort((a,b)=>a-b);
 const median=values.length?values[Math.floor(values.length/2)]:10;
 const max=stat==='PTS'?79:stat==='REB'?39:29;
 const lines=Array.from({length:max+1},(_,i)=>i+0.5);
 $('line').innerHTML=lines.map(x=>'<option value="'+x+'">'+x+'</option>').join('');
 if(selected!==null&&selected!==''&&!lines.some(x=>String(x)===selected))$('line').add(new Option(selected,selected));
 $('line').value=selected!==null&&selected!==''?selected:String(Math.min(max+.5,Math.max(.5,Math.floor(median)+.5)));
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
$('team').onchange=()=>{++pickNavigationRequest;changeTeam()};$('playername').onchange=()=>{++pickNavigationRequest;changePlayer()};$('playerseason').onchange=()=>{++pickNavigationRequest;changePlayer(null,true)};$('stat').onchange=()=>changeLine();$('line').onchange=drawPlayer;$('playermode').onchange=drawPlayer;$('playerwindow').onchange=drawPlayer;
async function initializeArchive(){
 setArchiveStatus('Caricamento giornate disponibili…');
 try {
  const response=await api('/api/saved/dates');
  const payload=await response.json();
  const dates=(payload.dates||[]).map(item=>item.date);
  $('date').innerHTML=dates.map(date=>'<option value="'+esc(date)+'">'+new Date(date+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'long',year:'numeric'})+'</option>').join('');
  if(!dates.length){$('date').innerHTML='<option value="">Nessuna giornata disponibile</option>';renderDateStrip();setArchiveStatus('Nessuna analisi archiviata','notice');return;}
  const todayRome=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  $('date').value=dates.includes(payload.default_date)?payload.default_date:(dates.includes(todayRome)?todayRome:dates[0]);
  renderDateStrip();
  $('date').dispatchEvent(new Event('change',{bubbles:true}));
 }catch(error){setArchiveStatus('Archivio temporaneamente non disponibile · riprova più tardi','error');}
}
initializeArchive();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
