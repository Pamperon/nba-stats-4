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
  if(section==='history')loadHistory();
 }
 document.querySelectorAll('[data-extra]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();show(link.dataset.extra);}));
 for(const id of ['area-quotes','area-stats'])el(id).addEventListener('click',()=>show(''));
 document.querySelectorAll('[data-return-site]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();el('area-quotes').click();window.scrollTo({top:0});}));
 window.addEventListener('hashchange',()=>show(Object.keys(routes).find(key=>'#'+routes[key]===location.hash)||'',false));
 async function read(url){const result=await fetch(url,{headers:{Accept:'application/json'}});if(!result.ok)throw Error('Dati non disponibili');return result.json();}
 async function loadHistory(){
  const request=++historyRequest;
  el('history-status').textContent='Caricamento dei pronostici del giorno…';el('history-tickets').replaceChildren();el('history-summary').replaceChildren();
  try{
   if(!el('history-date').value){
    const payload=await read('/api/history/dates');if(request!==historyRequest)return;
    el('history-date').innerHTML=payload.dates.map(item=>'<option value="'+escape(item.date)+'">'+escape(day(item.date))+'</option>').join('');
   }
   const date=el('history-date').value;
   if(!date){el('history-status').textContent='Non ci sono ancora pronostici giornalieri archiviati.';return;}
   const payload=await read('/api/history?date='+encodeURIComponent(date));if(request!==historyRequest||date!==el('history-date').value)return;
   renderHistory(payload);
  }catch{if(request===historyRequest)el('history-status').textContent='Archivio temporaneamente non disponibile. Usa “Ricarica archivio” per riprovare.';}
 }
 const statusNames={won:'Centrato',lost:'Non centrato',unresolved:'Da verificare'};
 function renderHistory(payload){
  const groups=payload.groups||{},tickets=Object.values(groups).flat();
  const won=tickets.filter(ticket=>ticket.status==='won').length,lost=tickets.filter(ticket=>ticket.status==='lost').length;
  el('history-status').textContent=tickets.length?tickets.length+' pronostici distinti del '+day(payload.date)+'.':'Nessun pronostico completo salvato per questa giornata.';
  el('history-summary').innerHTML=[['Centrati',won],['Non centrati',lost],['Da verificare',tickets.length-won-lost]].map(([label,value])=>'<div><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');
  const labels={Singola:'Singole',Doppia:'Doppie',Tripla:'Triple'};
  el('history-tickets').innerHTML=Object.entries(groups).filter(([,items])=>items.length).map(([name,items])=>'<section class="daily-group"><h2>'+escape(labels[name]||name)+'</h2><div class="history-grid">'+items.map((ticket,index)=>'<article class="history-ticket"><div class="ticket-heading"><h3>'+escape(name)+' '+(index+1)+'</h3><span class="outcome outcome-'+escape(ticket.status)+'">'+escape(statusNames[ticket.status]||'Da verificare')+'</span></div>'+ticket.legs.map(row=>'<div class="history-leg"><h4>'+escape(row.Giocatore)+'</h4><p>'+escape(row.Partita)+'</p><div class="leg-selection">'+escape(row.Scelta)+' '+escape(row.Linea)+' '+escape(row.Mercato)+' <span>Quota <b>'+odd(row.Quota)+'</b></span></div><p class="leg-result">'+(row.actual==null?'Risultato non ancora verificato':'Risultato finale: <strong>'+escape(row.actual)+'</strong> · '+(row.win===true?'Centrato':row.win===false?'Non centrato':'Da verificare'))+'</p></div>').join('')+(ticket.combined_odds!=null&&ticket.legs.length>1?'<p class="ticket-total">Prodotto delle quote originali <strong>'+odd(ticket.combined_odds)+'</strong></p>':'')+'</article>').join('')+'</div></section>').join('');
 }
 el('history-date').onchange=loadHistory;el('history-retry').onclick=loadHistory;
 el('back-to-top').onclick=()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 window.addEventListener('scroll',()=>{el('back-to-top').hidden=window.scrollY<700;},{passive:true});
 const initial=Object.keys(routes).find(name=>'#'+routes[name]===location.hash);
 if(initial)show(initial,false);
 else if(location.hash)show('',false);
})();
