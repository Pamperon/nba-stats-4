const $=id=>document.getElementById(id);let token='',jobId='',data=null;const savedKey='nba-stats-4-last-scan';const dbName='nba-stats-4-local-results';
function scanDB(){return new Promise((resolve,reject)=>{if(!('indexedDB'in window))return reject(new Error('Archivio browser non disponibile'));const r=indexedDB.open(dbName,1);r.onupgradeneeded=()=>r.result.createObjectStore('scans');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}
async function saveLocalScan(j){try{const db=await scanDB();await new Promise((resolve,reject)=>{const tx=db.transaction('scans','readwrite');tx.objectStore('scans').put(j,j.date);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});db.close();$('status').textContent+=' · copia salvata nel browser';}catch(e){$('status').textContent+=' · salvataggio locale non riuscito';}}
async function readLocalScan(date){const db=await scanDB();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('scans','readonly');const r=tx.objectStore('scans').get(date);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}finally{db.close()}}
async function showLocalScan(date){try{const j=await readLocalScan(date);if(!j)return false;data=j;jobId='';render();$('status').textContent='Analisi salvata nel browser ('+date+') · '+j.results.length+' linee · nessuna chiamata API';return true}catch{return false}}
const fmt=x=>x==null?'—':x;
async function api(path,options={}){let r=await fetch(path,{...options,headers:{...options.headers}});if(!r.ok)throw new Error('HTTP '+r.status);return r}
async function loadCloudScan(date=null){try{const r=await api('/api/saved/latest'+(date?'?date='+encodeURIComponent(date):''));const j=await r.json();data=j;jobId='';render();$('status').textContent='Analisi cloud del '+(j.date||'giorno')+' · '+(j.results||[]).length+' linee · salvata '+(j.saved_at||'')+' · 0 chiamate OddsPapi';return true}catch{return false}}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.tab').forEach(x=>x.hidden=x.id!==b.dataset.tab)});
let dateSelectionRequest=0;
$('date').addEventListener('change',async()=>{
 const selected=$('date').value;
 const request=++dateSelectionRequest;
 $('status').textContent='Caricamento archivio del '+selected+'…';
 try{
  const response=await api('/api/saved/latest?date='+encodeURIComponent(selected));
  const saved=await response.json();
  if(request!==dateSelectionRequest||$('date').value!==selected)return;
  data=saved;jobId='';render();
  $('status').textContent='Analisi cloud del '+selected+' · '+(saved.results||[]).length+' linee · 0 chiamate OddsPapi';
 }catch(error){
  if(request!==dateSelectionRequest||$('date').value!==selected)return;
  if(error.message==='HTTP 404'){
   if(await showLocalScan(selected))return;
   data=null;jobId='';render();
   $('status').textContent='Nessuna quota ancora disponibile per il '+selected+' · 0 chiamate OddsPapi';
  }else{
   data=null;jobId='';render();
   $('status').textContent='Impossibile consultare Supabase per il '+selected+' ('+error.message+') · riprova più tardi';
  }
 }
});
const number=x=>Number(x)||0;function eligible(){return (data?.results||[]).filter(r=>r['Stato analisi']==='Valutabile (stima empirica)'&&number(r['Quota'])>=number($('oddmin').value)&&number(r['Quota'])<=number($('oddmax').value)&&number(r['Prob. stimata %'])>=number($('probmin').value)&&($('market').value==='Tutti'||r.Mercato===$('market').value)).sort((a,b)=>number(b['Prob. stimata %'])-number(a['Prob. stimata %']))}
function render(){if(!data){$('metrics').innerHTML='';$('pick').innerHTML='<h2>Singola del giorno</h2><p>Nessuna quota ancora disponibile per la data selezionata.</p>';$('rows').innerHTML='';return;}const rows=data.results||[];$('metrics').innerHTML=[['Partite',data.fixture_count],['Linee',rows.length],['Giocatori',data.player_count],['Aggiornamento',data.saved_at?new Date(data.saved_at).toLocaleString('it-IT'):'Salvato']].map(([a,b])=>`<div class="metric"><small>${a}</small><strong>${b}</strong></div>`).join('');let candidates=eligible().filter(r=>{let hit=s=>{let m=String(r['Ultime '+s]).match(/^(\d+)\/(\d+)$/);return m&&Number(m[2])===s&&Number(m[1])/s>=.8};return number(r['Prob. stimata %'])>=75&&number(r['Partite'])>=20&&number(r['Stagione %'])>=70&&hit(5)&&hit(10)&&hit(20)&&number(r['Minuti medi'])>=20&&number(r['Minuti ultime 5'])>=.8*number(r['Minuti medi'])&&number(r['Prob. stimata %'])-100/number(r['Quota'])>=3});let p=candidates[0];$('pick').innerHTML=p?`<h2>Prima candidata da verificare</h2><h3>${esc(p.Giocatore)} · Over ${p.Linea} ${p.Mercato}</h3><p>${esc(p.Partita)} · quota ${p.Quota} · stima ${p['Prob. stimata %']}% · ultime 20: ${p['Ultime 20']}</p><p class="note">Stima NON calibrata. Verifica disponibilità e minutaggio.</p>`:'<h2>Singola del giorno</h2><p>Nessuna candidata supera tutti i criteri nella fascia selezionata.</p>';renderFinder()}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderFinder(){$('rows').innerHTML=eligible().slice(0,500).map(r=>`<tr><td>${esc(r.Giocatore)}</td><td>${esc(r.Mercato)}</td><td>${r.Linea}</td><td>${r.Quota}</td><td class="good">${fmt(r['Prob. stimata %'])}</td><td>${esc(r['Ultime 20'])}</td><td>${fmt(r['Value stimato %'])}</td></tr>`).join('')}
['oddmin','oddmax','market','probmin'].forEach(id=>$(id).addEventListener('change',()=>{if(data){renderFinder();render()}}));
$('csv').onclick=async()=>{if(!jobId){if(!data?.results?.length)return;const rows=data.results,keys=Object.keys(rows[0]);const safe=v=>{const t=String(v??'');const guarded=/^[=+@\\-\\t\\r]/.test(t)?"'"+t:t;return '"'+guarded.replace(/"/g,'""')+'"'};const csv='\uFEFF'+[keys.map(safe).join(';'),...rows.map(r=>keys.map(k=>safe(r[k])).join(';'))].join('\r\n');const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nba_stats_4_salvato.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;}try{const r=await api('/api/scan/'+jobId+'/csv');const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nba_stats_4_completo.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch{alert('CSV non disponibile')}};
let playerGames=[],playerRequest=0,rosterRequest=0;
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
async function changeTeam(){
 const request=++rosterRequest;const team=$('team').value;
 $('playername').innerHTML='';$('player-status').textContent='Caricamento roster ESPN…';
 if(!team)return;
 try{const payload=await(await api('/api/players/roster?team_id='+encodeURIComponent(team))).json();
 if(request!==rosterRequest)return;
 $('playername').innerHTML=payload.players.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>').join('');
 await changePlayer();
 }catch(e){if(request===rosterRequest)$('player-status').textContent='Roster non disponibile ('+e.message+')';}
}
async function changePlayer(){
 const request=++playerRequest,team=$('team').value,id=$('playername').value,season=$('playerseason').value;
 playerGames=[];$('player-summary').innerHTML='';$('chart').innerHTML='';
 if(!team||!id)return;
 $('player-status').textContent='Caricamento game log ESPN…';
 try{const params=new URLSearchParams({team_id:team,athlete_id:id,season});
 const payload=await(await api('/api/players/log?'+params)).json();
 if(request!==playerRequest)return;
 playerGames=payload.games||[];
 changeLine();
 $('player-status').textContent=playerGames.length?'Statistiche ESPN · nessuna chiamata OddsPapi':'Nessuna partita disponibile per questa stagione. Prova la stagione precedente.';
 drawPlayer();
 }catch(e){if(request===playerRequest)$('player-status').textContent='Game log non disponibile ('+e.message+')';}
}
function changeLine(){const stat=$('stat').value,values=playerGames.map(g=>playerNum(g[stat])).sort((a,b)=>a-b);
 const median=values.length?values[Math.floor(values.length/2)]:10;
 const lines=[...new Set([0.5,2.5,4.5,6.5,9.5,12.5,14.5,16.5,19.5,24.5,29.5,34.5,39.5,Math.max(.5,Math.floor(median)+.5)])].sort((a,b)=>a-b);
 $('line').innerHTML=lines.map(x=>'<option value="'+x+'">'+x+'</option>').join('');
 $('line').value=String(Math.max(.5,Math.floor(median)+.5));drawPlayer();}
function drawPlayer(){
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
  if(!dates.length){$('date').innerHTML='<option value="">Nessuna giornata disponibile</option>';$('status').textContent='Nessuna analisi archiviata';return;}
  const todayRome=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  $('date').value=dates.includes(todayRome)?todayRome:dates[0];
  if(!await loadCloudScan($('date').value))$('status').textContent='Impossibile caricare le analisi salvate';
 }catch(error){$('status').textContent='Archivio temporaneamente non disponibile · '+error.message;}
}
initializeArchive();
initPlayers();
if('serviceWorker'in navigator)navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
