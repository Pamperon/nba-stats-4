/* Secondary footer pages. Archive reads saved PostgreSQL data only. */
(() => {
 'use strict';
 const el=id=>document.getElementById(id);
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const odd=value=>value==null?'—':Number(value).toFixed(2).replace('.',',');
 const day=value=>new Date(value+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'long',year:'numeric'});
 const routes={history:'archivio',about:'come-funziona'};
 let historyRequest=0;
 // Remove the retired feature's local data without touching other browser data.
 try{localStorage.removeItem('basketlab:favorites:v1');}catch{}
 function show(section,focus=true){
  el('app').hidden=!!section;
  for(const name of Object.keys(routes))el('extra-'+name).hidden=name!==section;
  document.querySelectorAll('[data-extra]').forEach(link=>{
   if(link.dataset.extra===section)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
  });
  if(section){
   for(const id of ['area-quotes','area-stats']){el(id).classList.remove('active');el(id).setAttribute('aria-pressed','false');}
   if(focus){const title=el(section==='history'?'history-title':'about-title');title.focus();title.scrollIntoView?.({block:'start'});}
  }
  const hash=section?'#'+routes[section]:location.pathname+location.search;
  if((section&&location.hash!==hash)||(!section&&location.hash))history.replaceState(null,'',hash);
  if(section==='history')loadHistory(true);
 }
 document.querySelectorAll('[data-extra]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();show(link.dataset.extra);}));
 for(const id of ['area-quotes','area-stats'])el(id).addEventListener('click',()=>show(''));
 document.querySelectorAll('[data-return-site]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();el('area-quotes').click();window.scrollTo({top:0});}));
 window.addEventListener('hashchange',()=>show(Object.keys(routes).find(key=>'#'+routes[key]===location.hash)||'',false));
 async function read(url){const result=await fetch(url,{headers:{Accept:'application/json'}});if(!result.ok)throw Error('Dati non disponibili');return result.json();}
 async function loadHistory(refreshDates=false){
  const selected=el('history-date').value;
  const request=++historyRequest;
  el('history-status').textContent='Caricamento dei pronostici del giorno…';el('history-tickets').replaceChildren();el('history-summary').replaceChildren();
  try{
   if(refreshDates||!selected){
    const payload=await read('/api/history/dates');if(request!==historyRequest)return;
    el('history-date').innerHTML=payload.dates.map(item=>'<option value="'+escape(item.date)+'">'+escape(day(item.date))+'</option>').join('');
    if(payload.dates.some(item=>item.date===selected))el('history-date').value=selected;
   }
   const date=el('history-date').value;
   if(!date){el('history-status').textContent='Non ci sono ancora pronostici giornalieri archiviati.';return;}
   const payload=await read('/api/history?date='+encodeURIComponent(date));if(request!==historyRequest||date!==el('history-date').value)return;
   renderHistory(payload);
  }catch{if(request===historyRequest)el('history-status').textContent='Archivio temporaneamente non disponibile. Usa “Ricarica archivio” per riprovare.';}
 }
 const statusNames={won:'Centrato',lost:'Non centrato',unresolved:'Da verificare'};
 function renderHistory(payload){
  const lines=payload.lines||[];
  const won=lines.filter(line=>line.status==='won').length;
  const lost=lines.filter(line=>line.status==='lost').length;
  const resolved=won+lost;
  const rate=resolved?(100*won/resolved).toFixed(1).replace('.',',')+'%':'—';
  const scored=lines.filter(line=>(line.status==='won'||line.status==='lost')&&Number.isFinite(Number(line['Prob. stimata %']))&&Number(line['Prob. stimata %'])>=0&&Number(line['Prob. stimata %'])<=100);
  const brier=scored.length?(scored.reduce((total,line)=>total+(Number(line['Prob. stimata %'])/100-(line.status==='won'?1:0))**2,0)/scored.length).toFixed(3).replace('.',','):'—';
  el('history-status').textContent=lines.length?lines.length+' linee distinte pubblicate il '+day(payload.date)+'.':'Nessuna linea pubblicata per questa giornata.';
  el('history-summary').innerHTML=[['Vinte',won],['Perse',lost],['Da verificare',lines.length-resolved],['Successo',rate],['Brier Score',brier]].map(([label,value])=>'<div><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');
  el('history-tickets').innerHTML=lines.length?'<section class="daily-group"><h2>Selezioni individuali</h2><div class="history-grid">'+lines.map(row=>'<article class="history-ticket"><div class="ticket-heading"><h3>'+escape(row.Giocatore)+'</h3><span class="outcome outcome-'+escape(row.status)+'">'+escape(statusNames[row.status]||'Da verificare')+'</span></div><div class="history-leg"><p>'+escape(row.Partita)+'</p><div class="leg-selection">'+escape(row.Scelta)+' '+escape(row.Linea)+' '+escape(row.Mercato)+' <span>Quota <b>'+odd(row.Quota)+'</b></span></div><p>Probabilità prepartita: '+escape(row['Prob. stimata %'])+'%</p><p class="leg-result">'+(row.actual==null?'Risultato non ancora verificato':'Risultato finale: <strong>'+escape(row.actual)+'</strong>')+'</p></div></article>').join('')+'</div></section>':'';
 }

 el('history-date').onchange=()=>loadHistory();el('history-retry').onclick=()=>loadHistory(true);
 el('back-to-top').onclick=()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 window.addEventListener('scroll',()=>{el('back-to-top').hidden=window.scrollY<700;},{passive:true});
 const initial=Object.keys(routes).find(name=>'#'+routes[name]===location.hash);
 if(initial)show(initial,false);
 else if(location.hash)show('',false);
})();
