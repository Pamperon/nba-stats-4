/* Secondary footer pages. Archive reads saved PostgreSQL data only. */
(() => {
 'use strict';
 const el=id=>document.getElementById(id);
 const day=value=>new Date(value+'T12:00:00').toLocaleDateString('it-IT',{day:'numeric',month:'long',year:'numeric'});
 const routes={history:'archivio',about:'come-funziona'};
 let historyRequest=0;
 let availableHistoryDates=[];
 let historyWeekStart=null;
 function historyWeek(date){const d=new Date(date+'T12:00:00');d.setDate(d.getDate()-d.getDay());return d;}
 function isoDay(d){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
 function renderHistoryCalendar(){
  const selected=el('history-date').value;if(!selected)return;
  if(!historyWeekStart)historyWeekStart=historyWeek(selected);
  const middle=new Date(historyWeekStart);middle.setDate(middle.getDate()+3);
  el('history-month-label').textContent=middle.toLocaleDateString('it-IT',{month:'long',year:'numeric'});
  const weekdays=['Dom','Lun','Mar','Mer','Gio','Ven','Sab'];
  el('history-week-days').innerHTML=Array.from({length:7},(_,i)=>{const d=new Date(historyWeekStart);d.setDate(d.getDate()+i);const value=isoDay(d),active=value===selected,available=availableHistoryDates.includes(value);return '<button type="button" class="history-day'+(active?' active':'')+'" data-history-day="'+value+'" '+(!available?'disabled':'')+'><span>'+weekdays[d.getDay()]+'</span><strong>'+d.getDate()+'</strong></button>';}).join('');
  el('history-week-days').querySelectorAll('[data-history-day]').forEach(btn=>btn.addEventListener('click',()=>{el('history-date').value=btn.dataset.historyDay;loadHistory();}));
 }
 function selectHistoryMode(mode){
  for(const name of ['single','top5']){
   const tab=document.querySelector('[data-history-mode="'+name+'"]');
   tab.classList.toggle('active',name===mode);tab.setAttribute('aria-selected',String(name===mode));
   el('history-'+name+'-panel').hidden=name!==mode;
  }
 }
 document.querySelectorAll('[data-history-mode]').forEach(tab=>tab.addEventListener('click',()=>selectHistoryMode(tab.dataset.historyMode)));
 for(const [id,step] of [['history-prev-week',-7],['history-next-week',7]])el(id).addEventListener('click',()=>{if(!historyWeekStart)return;historyWeekStart.setDate(historyWeekStart.getDate()+step);renderHistoryCalendar();});
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
  if(!window.BasketLabRouter&&((section&&location.hash!==hash)||(!section&&location.hash)))history.replaceState(null,'',hash);
  if(section==='history')loadHistory(true);
 }
 document.querySelectorAll('[data-extra]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();show(link.dataset.extra);}));
 for(const id of ['area-quotes','area-stats'])el(id).addEventListener('click',()=>show(''));
 document.querySelectorAll('[data-return-site]').forEach(link=>link.addEventListener('click',event=>{event.preventDefault();el('area-quotes').click();window.scrollTo({top:0});}));
 window.addEventListener('hashchange',()=>show(Object.keys(routes).find(key=>'#'+routes[key]===location.hash)||'',false));
 async function read(url){const result=await fetch(url,{headers:{Accept:'application/json'}});if(!result.ok)throw Error('Dati non disponibili');return result.json();}
 async function loadHistory(refreshDates=false){
  const selected=el('history-date').value;
  const rendererReady=window.BasketLabArchiveView?Promise.resolve():window.BasketLabAssets.load('archive-view');
  rendererReady.catch(()=>{});
  const request=++historyRequest;
  el('history-status').textContent='Caricamento dei pronostici del giorno…';el('history-tickets').replaceChildren();el('history-summary').replaceChildren();el('history-single-tickets').replaceChildren();el('history-single-summary').replaceChildren();
  try{
   if(refreshDates||!selected){
    const payload=await read('/api/history/dates');if(request!==historyRequest)return;
    availableHistoryDates=payload.dates.map(item=>item.date).filter(date=>date>='2026-11-01').sort();
    const picker=el('history-date');
    picker.min=availableHistoryDates[0]||'';
    picker.max=availableHistoryDates[availableHistoryDates.length-1]||'';
    picker.value=availableHistoryDates.includes(selected)?selected:(availableHistoryDates[availableHistoryDates.length-1]||'');
    el('history-date-hint').textContent='';
   }
   const date=el('history-date').value;
   renderHistoryCalendar();
   if(!date){el('history-status').textContent='Non ci sono ancora pronostici giornalieri archiviati.';return;}
   if(date<'2026-11-01'||!availableHistoryDates.includes(date)){el('history-status').textContent='Nessuna analisi archiviata per il '+day(date)+'. Scegli una giornata disponibile.';return;}
   const payload=await read('/api/history?date='+encodeURIComponent(date));if(request!==historyRequest||date!==el('history-date').value)return;
   await rendererReady;
   if(request!==historyRequest||date!==el('history-date').value)return;
   window.BasketLabArchiveView(document)(payload);
  }catch{if(request===historyRequest)el('history-status').textContent='Archivio temporaneamente non disponibile. Riprova tra poco.';}
 }


 el('history-date').onchange=()=>{historyWeekStart=null;loadHistory();};
 el('back-to-top').onclick=()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 window.addEventListener('scroll',()=>{el('back-to-top').hidden=window.scrollY<700;},{passive:true});
 const initial=Object.keys(routes).find(name=>'#'+routes[name]===location.hash);
 if(initial)show(initial,false);
 else if(location.hash)show('',false);
})();
