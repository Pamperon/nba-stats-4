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
function render(){if(!data){$('metrics').innerHTML='';$('pick').innerHTML='<h2>Singola del giorno</h2><p>Nessuna quota ancora disponibile per la data selezionata.</p>';$('rows').innerHTML='';$('team').innerHTML='<option>Tutte le squadre</option>';$('playername').innerHTML='';$('line').innerHTML='';$('player-summary').innerHTML='';$('chart').innerHTML='';return;}const rows=data.results||[];$('metrics').innerHTML=[['Partite',data.fixture_count],['Linee',rows.length],['Giocatori',data.player_count],['Aggiornamento',data.saved_at?new Date(data.saved_at).toLocaleString('it-IT'):'Salvato']].map(([a,b])=>`<div class="metric"><small>${a}</small><strong>${b}</strong></div>`).join('');let candidates=eligible().filter(r=>{let hit=s=>{let m=String(r['Ultime '+s]).match(/^(\d+)\/(\d+)$/);return m&&Number(m[2])===s&&Number(m[1])/s>=.8};return number(r['Prob. stimata %'])>=75&&number(r['Partite'])>=20&&number(r['Stagione %'])>=70&&hit(5)&&hit(10)&&hit(20)&&number(r['Minuti medi'])>=20&&number(r['Minuti ultime 5'])>=.8*number(r['Minuti medi'])&&number(r['Prob. stimata %'])-100/number(r['Quota'])>=3});let p=candidates[0];$('pick').innerHTML=p?`<h2>Prima candidata da verificare</h2><h3>${esc(p.Giocatore)} · Over ${p.Linea} ${p.Mercato}</h3><p>${esc(p.Partita)} · quota ${p.Quota} · stima ${p['Prob. stimata %']}% · ultime 20: ${p['Ultime 20']}</p><p class="note">Stima NON calibrata. Verifica disponibilità e minutaggio.</p>`:'<h2>Singola del giorno</h2><p>Nessuna candidata supera tutti i criteri nella fascia selezionata.</p>';renderFinder();initPlayers()}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderFinder(){$('rows').innerHTML=eligible().slice(0,500).map(r=>`<tr><td>${esc(r.Giocatore)}</td><td>${esc(r.Mercato)}</td><td>${r.Linea}</td><td>${r.Quota}</td><td class="good">${fmt(r['Prob. stimata %'])}</td><td>${esc(r['Ultime 20'])}</td><td>${fmt(r['Value stimato %'])}</td></tr>`).join('')}
['oddmin','oddmax','market','probmin'].forEach(id=>$(id).addEventListener('change',()=>{if(data){renderFinder();render()}}));
$('csv').onclick=async()=>{if(!jobId){if(!data?.results?.length)return;const rows=data.results,keys=Object.keys(rows[0]);const safe=v=>{const t=String(v??'');const guarded=/^[=+@\\-\\t\\r]/.test(t)?"'"+t:t;return '"'+guarded.replace(/"/g,'""')+'"'};const csv='\uFEFF'+[keys.map(safe).join(';'),...rows.map(r=>keys.map(k=>safe(r[k])).join(';'))].join('\r\n');const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nba_stats_4_salvato.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;}try{const r=await api('/api/scan/'+jobId+'/csv');const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nba_stats_4_completo.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch{alert('CSV non disponibile')}};
function initPlayers(){let teams=[...new Set(data.results.filter(r=>data.player_logs[r.Giocatore]).map(r=>r.Squadra))].sort();$('team').innerHTML='<option>Tutte le squadre</option>'+teams.map(x=>`<option>${esc(x)}</option>`).join('');changeTeam()}
function changeTeam(){let names=[...new Set(data.results.filter(r=>data.player_logs[r.Giocatore]&&($('team').value==='Tutte le squadre'||r.Squadra===$('team').value)).map(r=>r.Giocatore))].sort();$('playername').innerHTML=names.map(x=>`<option>${esc(x)}</option>`).join('');changePlayer()}
function changePlayer(){let lines=[...new Set(data.results.filter(r=>r.Giocatore===$('playername').value&&r.Mercato===$('stat').value).map(r=>r.Linea))].sort((a,b)=>a-b);$('line').innerHTML=(lines.length?lines:[9.5]).map(x=>`<option>${x}</option>`).join('');drawPlayer()}
function drawPlayer(){let logs=data?.player_logs?.[$('playername').value]||[],stat=$('stat').value,line=number($('line').value),list=logs.slice(0,20),hits=list.filter(g=>number(g[stat])>line).length;$('player-summary').innerHTML=`<div class="metric"><small>Over ultime 20</small><strong>${hits}/${list.length}</strong></div><div class="metric"><small>Frequenza osservata</small><strong>${list.length?(100*hits/list.length).toFixed(1)+'%':'—'}</strong></div>`;let max=Math.max(line+1,...list.map(g=>number(g[stat])),1);$('chart').innerHTML=list.slice().reverse().map(g=>{let val=number(g[stat]);return `<div class="barrow"><span>${esc((g.GAME_DATE||'').slice(5))}</span><div class="track"><div class="fill ${val>line?'':'under'}" style="width:${Math.min(100,val/max*100)}%"></div><div class="line" style="left:${Math.min(100,line/max*100)}%"></div></div><strong>${val}</strong></div>`}).join('')||'<p>Nessun game log disponibile</p>'}
$('team').onchange=changeTeam;$('playername').onchange=changePlayer;$('stat').onchange=changePlayer;$('line').onchange=drawPlayer;
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
if('serviceWorker'in navigator)navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
