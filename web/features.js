/* Archive, personal favorites and saved-quote movements. GET requests only. */
(() => {
 'use strict';
 const el=id=>document.getElementById(id);
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const odd=value=>value==null?'—':Number(value).toFixed(2).replace('.',',');
 const stamp=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'Orario non disponibile':date.toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});};
 const day=value=>new Date(value+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'long',year:'numeric'});
 async function read(url){const result=await fetch(url,{headers:{Accept:'application/json'}});if(!result.ok)throw Error('Dati temporaneamente non disponibili');return result.json();}
 const routes={history:'archivio',favorites:'preferiti',movements:'movimenti',about:'come-funziona'};
 let active='',historyRequest=0,movementRequest=0,historyVersions=[],movementData=null,movementLimit=60;
 function show(section,focus=true){
  active=section;
  el('app').hidden=!!section;
  for(const name of Object.keys(routes))el('extra-'+name).hidden=name!==section;
  document.querySelectorAll('[data-extra]').forEach(button=>{const selected=button.dataset.extra===section;button.classList.toggle('active',selected);button.setAttribute('aria-pressed',String(selected));});
  if(section){
   for(const id of ['area-quotes','area-stats']){el(id).classList.remove('active');el(id).setAttribute('aria-pressed','false');}
   if(focus)el(section==='history'?'history-title':section==='favorites'?'favorites-title':section==='movements'?'movements-title':'about-title').focus({preventScroll:true});
  }
  const hash=section?'#'+routes[section]:location.pathname+location.search;
  if((section&&location.hash!==hash)||(!section&&location.hash))history.replaceState(null,'',hash);
  if(section==='history')loadHistory();
  if(section==='favorites')renderFavorites();
  if(section==='movements')loadMovements();
 }
 document.querySelectorAll('[data-extra]').forEach(button=>button.addEventListener('click',()=>show(button.dataset.extra)));
 for(const id of ['area-quotes','area-stats'])el(id).addEventListener('click',()=>show(''));
 window.addEventListener('hashchange',()=>show(Object.keys(routes).find(key=>'#'+routes[key]===location.hash)||'',false));

 // No account is created: only a small validated list is stored in this browser.
 const key='basketlab:favorites:v1';
 let favorites=new Map();
 function restore(){
  try{
   const rows=JSON.parse(localStorage.getItem(key)||'[]');
   favorites=new Map((Array.isArray(rows)?rows:[]).filter(row=>row&&/^\d{1,12}$/.test(String(row.id))&&typeof row.name==='string'&&row.name.length<=100&&typeof row.team==='string'&&row.team.length<=100).slice(0,100).map(row=>[String(row.id),{id:String(row.id),name:row.name,team:row.team}]));
  }catch{favorites=new Map();}
 }
 restore();
 window.basketLabFavorites={has:id=>favorites.has(String(id))};
 function persist(){
  try{localStorage.setItem(key,JSON.stringify([...favorites.values()]));el('favorites-status').textContent='';}
  catch{el('favorites-status').textContent='Il browser non permette il salvataggio: la lista resta disponibile solo in questa sessione.';}
 }
 function toggle(player){
  if(!/^\d{1,12}$/.test(String(player?.id)))return;
  if(favorites.has(String(player.id)))favorites.delete(String(player.id));
  else if(favorites.size<100)favorites.set(String(player.id),{id:String(player.id),name:String(player.name).slice(0,100),team:String(player.team||'').slice(0,100)});
  else{el('favorites-status').textContent='Hai raggiunto 100 preferiti. Rimuovine uno per aggiungere altri giocatori.';return;}
  persist();renderFavorites();decoratePicks();profileStar();window.basketLab.refreshFinder();
 }
 function currentPlayer(){return {id:el('playername').value,name:el('playername').selectedOptions[0]?.textContent||'',team:el('team').selectedOptions[0]?.textContent||''};}
 function profileStar(){const player=currentPlayer(),button=el('favorite-player'),selected=favorites.has(player.id);button.disabled=!/^\d{1,12}$/.test(player.id);button.textContent=selected?'★ Giocatore seguito':'☆ Segui giocatore';button.setAttribute('aria-pressed',String(selected));}
 el('favorite-player').onclick=()=>toggle(currentPlayer());
 new MutationObserver(profileStar).observe(el('player-display-name'),{childList:true,subtree:true});
 new MutationObserver(profileStar).observe(el('player-profile'),{attributes:true,attributeFilter:['hidden']});
 document.addEventListener('change',event=>{if(['playername','team'].includes(event.target.id))profileStar();});
 function decoratePicks(){
  const rows=window.basketLab.snapshot()?.results||[];
  for(const card of document.querySelectorAll('.pick-selection')){
   const name=card.querySelector('.pick-player-link')?.textContent;
   const row=rows.find(item=>item.Giocatore===name&&/^\d{1,12}$/.test(String(item['ESPN ID']||'')));
   if(!row)continue;
   let button=card.querySelector('.pick-favorite');
   if(!button){button=document.createElement('button');button.type='button';button.className='pick-favorite';card.querySelector('.pick-profile').append(button);}
   const selected=favorites.has(String(row['ESPN ID']));
   button.textContent=selected?'★':'☆';button.setAttribute('aria-label',(selected?'Non seguire più ':'Segui ')+row.Giocatore);button.setAttribute('aria-pressed',String(selected));
   button.onclick=()=>toggle({id:row['ESPN ID'],name:row.Giocatore,team:row.Squadra});
  }
 }
 document.addEventListener('basketlab:render',decoratePicks);
 function renderFavorites(){
  el('favorite-list').innerHTML=[...favorites.values()].map(player=>'<article class="favorite-card"><div><h2>'+escape(player.name)+'</h2><p>'+escape(player.team)+'</p></div><div class="favorite-actions"><button type="button" data-open-favorite="'+escape(player.id)+'">Vedi statistiche</button><button type="button" class="quiet-button" data-remove-favorite="'+escape(player.id)+'" aria-label="Rimuovi '+escape(player.name)+' dai preferiti">Rimuovi</button></div></article>').join('')||'<div class="feature-empty"><strong>La tua lista inizia da un giocatore.</strong><p>Apri le sue statistiche e tocca “Segui giocatore”, oppure usa la stella su un pronostico.</p></div>';
  for(const button of el('favorite-list').querySelectorAll('[data-remove-favorite]'))button.onclick=()=>toggle(favorites.get(button.dataset.removeFavorite));
  for(const button of el('favorite-list').querySelectorAll('[data-open-favorite]'))button.onclick=()=>{
   const player=favorites.get(button.dataset.openFavorite);if(!player)return;show('');
   window.basketLab.openPlayer({'ESPN ID':player.id,Giocatore:player.name,Squadra:player.team,Mercato:'PTS',Linea:9.5});
  };
 }
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null){restore();renderFavorites();decoratePicks();profileStar();window.basketLab.refreshFinder();}});
 el('favorites-explore').onclick=()=>el('area-stats').click();
 el('finder-favorites').onchange=()=>window.basketLab.refreshFinder();
 el('finder-reset').onclick=()=>{el('finder-search').value='';el('market').value='Tutti';el('oddmin').value='1.10';el('oddmax').value='2.20';el('probmin').value='0';el('finder-favorites').checked=false;window.basketLab.refreshFinder();};

 async function loadHistory(){
  const request=++historyRequest;
  el('history-status').textContent='Caricamento dell’archivio…';el('history-tickets').replaceChildren();el('history-summary').replaceChildren();
  try{
   if(!el('history-date').value){
    const payload=await read('/api/history/dates');if(request!==historyRequest)return;
    el('history-date').innerHTML=payload.dates.map(item=>'<option value="'+escape(item.date)+'">'+escape(day(item.date))+'</option>').join('');
   }
   const date=el('history-date').value;
   if(!date){el('history-status').textContent='Non ci sono ancora pronostici archiviati con selezioni salvate.';el('history-version').replaceChildren();return;}
   const payload=await read('/api/history?date='+encodeURIComponent(date));if(request!==historyRequest||date!==el('history-date').value)return;
   const previous=el('history-version').value;historyVersions=payload.versions;
   el('history-version').innerHTML=historyVersions.map(item=>'<option value="'+escape(item.job_id)+'">'+escape(stamp(item.saved_at))+'</option>').join('');
   if(historyVersions.some(item=>item.job_id===previous))el('history-version').value=previous;
   renderHistory();
  }catch{if(request===historyRequest){el('history-status').textContent='Archivio temporaneamente non disponibile. Usa “Ricarica archivio” per riprovare.';el('history-version').replaceChildren();}}
 }
 const statusNames={won:'Verificato: centrato',lost:'Verificato: non centrato',unresolved:'Da verificare',incomplete:'Nessuna proposta completa'};
 function renderHistory(){
  const version=historyVersions.find(item=>item.job_id===el('history-version').value);
  if(!version){el('history-status').textContent='Nessuna selezione salvata per questa giornata.';el('history-tickets').replaceChildren();return;}
  const groups=Object.entries(version.groups),complete=groups.filter(([,group])=>group.status!=='incomplete');
  const won=complete.filter(([,group])=>group.status==='won').length,lost=complete.filter(([,group])=>group.status==='lost').length;
  el('history-status').textContent='Versione salvata il '+stamp(version.saved_at)+'. Esiti statistici delle selezioni originali.';
  el('history-summary').innerHTML=metrics([['Centrate',won],['Non centrate',lost],['Da verificare',complete.length-won-lost]]);
  el('history-tickets').innerHTML=groups.map(([name,group])=>'<article class="history-ticket"><div class="ticket-heading"><h2>'+escape(name)+'</h2><span class="outcome outcome-'+escape(group.status)+'">'+escape(statusNames[group.status]||'Da verificare')+'</span></div>'+group.legs.map(row=>'<div class="history-leg"><h3>'+escape(row.Giocatore)+'</h3><p>'+escape(row.Partita)+'</p><div class="leg-selection">'+escape(row.Scelta)+' '+escape(row.Linea)+' '+escape(row.Mercato)+' <span>Quota <b>'+odd(row.Quota)+'</b></span></div><p class="leg-result">'+(row.actual==null?'Risultato non ancora verificato':'Risultato finale: <strong>'+escape(row.actual)+'</strong> · '+(row.win===true?'Centrato':row.win===false?'Non centrato':'Da verificare'))+'</p></div>').join('')+(group.combined_odds!=null&&group.legs.length>1?'<p class="ticket-total">Prodotto delle quote salvate <strong>'+odd(group.combined_odds)+'</strong></p>':'')+'</article>').join('');
 }
 function metrics(items){return items.map(([label,value])=>'<div><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');}
 el('history-date').onchange=()=>{el('history-version').replaceChildren();loadHistory();};el('history-version').onchange=renderHistory;el('history-retry').onclick=loadHistory;

 async function loadMovements(){
  const request=++movementRequest;movementData=null;movementLimit=60;
  el('movements-list').replaceChildren();el('movements-summary').replaceChildren();el('movements-times').textContent='';el('movements-more').hidden=true;
  el('movements-status').textContent='Confronto degli aggiornamenti salvati…';
  try{
   const dates=await read('/api/odds/dates');if(request!==movementRequest)return;
   const selected=el('movements-date').value||window.basketLab.snapshot()?.date||dates.default_date;
   el('movements-date').innerHTML=dates.dates.map(item=>'<option value="'+escape(item.date)+'">'+escape(day(item.date))+'</option>').join('');
   if(dates.dates.some(item=>item.date===selected))el('movements-date').value=selected;
   const date=el('movements-date').value;
   if(!date){el('movements-status').textContent='Non ci sono giornate disponibili.';return;}
   const payload=await read('/api/odds/changes?date='+encodeURIComponent(date));if(request!==movementRequest||el('movements-date').value!==date)return;
   movementData=payload;
   if(!payload.summary){el('movements-status').textContent='Servono almeno due scansioni salvate della stessa giornata per il confronto.';return;}
   const s=payload.summary;
   el('movements-summary').innerHTML=metrics([['Salite',s.up],['Scese',s.down],['Invariate',s.unchanged],['Aggiunte',s.added],['Rimosse',s.removed]]);
   el('movements-times').textContent='Quote rilevate: '+stamp(payload.versions[1].odds_at||payload.versions[1].saved_at)+' → '+stamp(payload.versions[0].odds_at||payload.versions[0].saved_at)+'. Gruppi giocatore/mercato con linee diverse: '+s.line_groups_changed+'.'+(s.ambiguous?' Selezioni ambigue escluse: '+s.ambiguous+'.':'')+(payload.truncated?' Elenco limitato ai primi 1.000 movimenti.':'');
   renderMovements();
  }catch{if(request===movementRequest)el('movements-status').textContent='Confronto temporaneamente non disponibile. Usa “Ricarica confronto” per riprovare.';}
 }
 const kindNames={up:'↑ Quota salita',down:'↓ Quota scesa',added:'＋ Selezione aggiunta',removed:'− Selezione rimossa'};
 function renderMovements(){
  if(!movementData?.summary)return;
  const search=el('movements-search').value.trim().toLocaleLowerCase('it'),kind=el('movements-kind').value;
  const rows=movementData.changes.filter(row=>(kind==='all'||row.kind===kind)&&String(row.player).toLocaleLowerCase('it').includes(search));
  el('movements-status').textContent=rows.length?rows.length+' movimenti corrispondenti ai filtri.':'Nessun movimento per i filtri selezionati.';
  el('movements-list').innerHTML=rows.slice(0,movementLimit).map(row=>'<article class="movement-card"><div><span class="movement-kind movement-'+escape(row.kind)+'">'+escape(kindNames[row.kind])+'</span><h2>'+escape(row.player)+'</h2><p>'+escape(row.game)+'</p><strong>'+escape(row.choice)+' '+escape(row.line)+' '+escape(row.market)+'</strong></div><div class="movement-prices"><span><small>Prima</small>'+odd(row.before)+'</span><b aria-hidden="true">→</b><span><small>Dopo</small>'+odd(row.after)+'</span></div></article>').join('');
  el('movements-more').hidden=rows.length<=movementLimit;
 }
 el('movements-date').onchange=loadMovements;el('movements-retry').onclick=loadMovements;
 for(const id of ['movements-search','movements-kind'])el(id).addEventListener(id.endsWith('search')?'input':'change',()=>{movementLimit=60;renderMovements();});
 el('movements-more').onclick=()=>{movementLimit+=60;renderMovements();};
 el('back-to-top').onclick=()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 window.addEventListener('scroll',()=>{el('back-to-top').hidden=window.scrollY<700;},{passive:true});
 renderFavorites();profileStar();decoratePicks();
 const initial=Object.keys(routes).find(name=>'#'+routes[name]===location.hash);
 if(initial)show(initial,false);
})();
