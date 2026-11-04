/* Match quote presentation; reads existing saved rows and probabilities. */
window.BasketLabMatchPlayers=function(document,getState,cleanName,displayNum){
const window=document.defaultView;const $=s=>document.querySelector(s);
return function renderMatchPlayers(){
 const {activeMatch,matchMarket,matchTeamFilter}=getState();
 if(!document.body.classList.contains('hub-match-open'))return;
 const list=$('#hub-match-player-list'),count=$('#hub-match-player-count');if(!list)return;
 const rows=typeof window.BasketLabMatchRows==='function'?window.BasketLabMatchRows(activeMatch):[];
 const q=($('#hub-match-search')?.value||'').toLowerCase().trim();
 const groups=new Map();
 const teamFilter=matchTeamFilter;
 const sortBy='team';
 const oddMin=Number(($('#hub-match-odd-min')?.value||'1.20').replace(',','.'));
 const oddMax=Number(($('#hub-match-odd-max')?.value||'2.20').replace(',','.'));
 const rangeValid=Number.isFinite(oddMin)&&Number.isFinite(oddMax)&&oddMin>=1.01&&oddMax>=oddMin;
 const error=$('#hub-match-filter-error');
 if(error){error.hidden=rangeValid;error.textContent=rangeValid?'':'Inserisci quote valide: la minima deve essere almeno 1,01 e non superare la massima.';}
 for(const id of ['hub-match-odd-min','hub-match-odd-max'])$('#'+id)?.setAttribute('aria-invalid',String(!rangeValid));
 if(!rangeValid){list.replaceChildren();if(count)count.textContent='Intervallo quote da correggere';return;}
 for(const row of rows){
  if(teamFilter&&row.Squadra!==teamFilter)continue;
  if(q&&!cleanName(row.Giocatore).toLowerCase().includes(q)&&!String(row.Giocatore).toLowerCase().includes(q))continue;
  if(matchMarket!=='ALL'&&row.Mercato!==matchMarket)continue;
  const key=JSON.stringify([row.Squadra,row['ESPN ID']||row.Giocatore]);
  if(!groups.has(key))groups.set(key,{name:cleanName(row.Giocatore),team:row.Squadra,espnId:row['ESPN ID'],rows:[]});
  groups.get(key).rows.push(row);
 }
 list.replaceChildren();if(count)count.textContent=groups.size+' giocatori · '+[...groups.values()].reduce((sum,g)=>sum+g.rows.length,0)+' linee';
 if(!groups.size){const d=window.BasketLabMatchDiagnostics?.(activeMatch);list.textContent=rows.length?'Nessun giocatore corrisponde al mercato o alla ricerca.':d?.matching?'Sono presenti '+d.matching+' analisi per questa partita, ma nessuna quota valida salvata.':'Quote giocatori non disponibili nel feed salvato per questa partita nella data '+(d?.date||'selezionata')+'. Le statistiche ESPN sono indipendenti dalle quote.';return}
 const ordered=[...groups.values()].sort((a,b)=>sortBy==='name'?a.name.localeCompare(b.name,'it'):sortBy==='lines'?b.rows.length-a.rows.length||a.name.localeCompare(b.name,'it'):a.team.localeCompare(b.team,'it')||a.name.localeCompare(b.name,'it'));
 let lastTeam='';
 for(const group of ordered){
  if(sortBy==='team'&&group.team!==lastTeam){const heading=document.createElement('h4');heading.className='hub-match-team-heading';heading.textContent=group.team;list.append(heading);lastTeam=group.team}
  const card=document.createElement('article');card.className='hub-match-player-card';
  const header=document.createElement('div');header.className='hub-match-player-identity';
  const info=document.createElement('div');if(/^\d+$/.test(String(group.espnId||''))){const photo=document.createElement('img');photo.className='hub-match-player-photo';photo.src='https://a.espncdn.com/i/headshots/nba/players/full/'+group.espnId+'.png';photo.alt='';photo.loading='lazy';photo.onerror=()=>{photo.hidden=true};header.append(photo)}const name=document.createElement('strong');name.textContent=group.name;
  const team=document.createElement('small');team.textContent=group.team||'';info.append(name,team);header.append(info);
  const stats=document.createElement('button');stats.type='button';stats.className='hub-match-player-stats-link';stats.textContent='Statistiche ›';stats.onclick=()=>window.BasketLabMatchPlayerStats?.(group.rows[0]);header.append(stats);card.append(header);
  const markets=document.createElement('div');markets.className='hub-match-player-markets compact';
  for(const market of ['PTS','REB','AST']){
   const subset=group.rows.filter(row=>row.Mercato===market);
   if(!subset.length)continue;
   const block=document.createElement('div');block.className='hub-match-player-market compact';
   const details=document.createElement('details');details.className='hub-match-odds-dropdown';
   const summary=document.createElement('summary');const label=document.createElement('span');label.textContent=({PTS:'Punti',REB:'Rimbalzi',AST:'Assist'})[market]+' · '+subset.length+' linee';const chevron=document.createElement('span');chevron.className='hub-match-quote-toggle-label';chevron.textContent='Vedi linee ▾';details.addEventListener('toggle',()=>{chevron.textContent=details.open?'Chiudi ▴':'Vedi linee ▾'});summary.append(label,chevron);details.append(summary);
   const head=document.createElement('div');head.className='hub-match-odds-head';['Linea','Scelta','Quota','Stima'].forEach(text=>{const el=document.createElement('span');el.textContent=text;head.append(el)});details.append(head);
   const sorted=[...subset].sort((a,b)=>Number(a.Linea)-Number(b.Linea)||String(a.Scelta).localeCompare(String(b.Scelta))||Number(a.Quota)-Number(b.Quota));
   const visible=sorted.filter(row=>rangeValid&&Number(row.Quota)>=oddMin&&Number(row.Quota)<=oddMax);
   for(const row of sorted){
    const entry=document.createElement('div');entry.className='hub-match-odds-row';if(rangeValid&& !visible.includes(row))entry.classList.add('hub-match-odds-extra');
    const values=[displayNum(row.Linea),String(row.Scelta||'—').toUpperCase(),displayNum(row.Quota),row['Prob. stimata %']==null||row['Prob. stimata %']===''?'—':displayNum(row['Prob. stimata %'])+'%'];
    values.forEach((value,i)=>{const cell=document.createElement('span');cell.textContent=value;if(i===2)cell.className='hub-match-odds-price';if(i===3)cell.className='hub-match-odds-prob';entry.append(cell)});details.append(entry);
   }
   if(rangeValid&&visible.length<sorted.length){const toggle=document.createElement('button');toggle.type='button';toggle.className='hub-match-all-lines';toggle.textContent='Mostra altre '+(sorted.length-visible.length)+' linee';toggle.onclick=()=>{const expanded=details.classList.toggle('show-all-lines');toggle.textContent=expanded?'Mostra solo quote nel filtro':'Mostra altre '+(sorted.length-visible.length)+' linee'};details.append(toggle)}
   block.append(details);markets.append(block);
  }
  card.append(markets);list.append(card);
 }
}
};
