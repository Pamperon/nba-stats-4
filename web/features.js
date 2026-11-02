/* Secondary footer pages. Archive reads saved PostgreSQL data only. */
(() => {
 'use strict';
 const el=id=>document.getElementById(id);
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const odd=value=>value==null?'—':Number(value).toFixed(2).replace('.',',');
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
  const payload=window.__basketHistoryPayload;
  if(payload)renderHistoryStrip(payload);
 }
 function renderHistoryStrip(payload){
  const mode=document.querySelector('[data-history-mode].active')?.dataset.historyMode||'single';
  const lines=mode==='single'?(payload.single_archive?.published?[{status:payload.single_archive.outcome?.status||'unresolved'}]:[]):payload.official_lines||[];
  const won=lines.filter(x=>x.status==='won').length,lost=lines.filter(x=>x.status==='lost').length;
  el('history-day-strip').innerHTML='<span>▣ <b>'+escape(day(payload.date))+'</b></span><span><b>'+lines.length+'</b> selezioni</span><span class="history-won">✓ '+won+' Vinte</span><span class="history-lost">✕ '+lost+' Perse</span><span class="history-pending">⌛ '+(lines.length-won-lost)+' Da verificare</span>';
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
   renderHistory(payload);
  }catch{if(request===historyRequest)el('history-status').textContent='Archivio temporaneamente non disponibile. Riprova tra poco.';}
 }
 const statusNames={won:'Centrato',lost:'Non centrato',unresolved:'Da verificare'};
 function renderHistory(payload){
  window.__basketHistoryPayload=payload;
  const single=payload.single_archive||{published:false};
  const selection=single.selection;
  const outcome=single.outcome||{};
  const state=single.published?(outcome.status||'unresolved'):'not_published';
  const singleWon=state==='won'?1:0;
  const singleLost=state==='lost'?1:0;
  const singleSettled=singleWon+singleLost;
  const singleOdds=selection?Number(selection.Quota):NaN;
  const singleRoi=singleSettled&&Number.isFinite(singleOdds)&&singleOdds>1
    ?((singleWon?singleOdds-1:-1)*100).toFixed(1).replace('.',',')+'%':'—';
  el('history-single-summary').innerHTML=[['Pubblicate',single.published?1:0],['Vinte',singleWon],['Perse',singleLost],['Da verificare',single.published&&!singleSettled?1:0],['Successo',singleSettled?(singleWon*100)+'%':'—']]
    .map(([label,value])=>'<div><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');
  el('history-single-tickets').innerHTML=selection
    ?'<section class="daily-group"><div class="history-grid"><article class="history-ticket"><div class="ticket-heading"><h3>'+escape(selection.Giocatore)+'</h3><span class="outcome outcome-'+escape(state)+'">'+escape(statusNames[state]||'Da verificare')+'</span></div><div class="history-leg"><p>'+escape(selection.Partita)+'</p><div class="leg-selection">'+escape(selection.Scelta)+' '+escape(selection.Linea)+' '+escape(selection.Mercato)+' <span>Quota <b>'+odd(selection.Quota)+'</b></span></div><p>Probabilità prepartita: '+escape(selection['Prob. stimata %'])+'%</p><p class="leg-result">'+(outcome.actual==null?'Risultato non ancora verificato':'Risultato finale: <strong>'+escape(outcome.actual)+'</strong>')+'</p></div></article></div></section>'
    :'<p class="feature-note">Nessuna Singola ufficiale pubblicata per questa giornata.</p>';
  const lines=payload.official_lines||[];
  const legacy=payload.other_lines||[];
  const won=lines.filter(line=>line.status==='won').length;
  const lost=lines.filter(line=>line.status==='lost').length;
  const resolved=won+lost;
  const rate=resolved?(100*won/resolved).toFixed(1).replace('.',',')+'%':'—';
  const scored=lines.filter(line=>(line.status==='won'||line.status==='lost')&&line['Prob. stimata %']!=null&&line['Prob. stimata %']!==''&&Number.isFinite(Number(line['Prob. stimata %']))&&Number(line['Prob. stimata %'])>=0&&Number(line['Prob. stimata %'])<=100);
  const brier=scored.length?(scored.reduce((total,line)=>total+(Number(line['Prob. stimata %'])/100-(line.status==='won'?1:0))**2,0)/scored.length).toFixed(3).replace('.',','):'—';
  const priced=lines.filter(line=>(line.status==='won'||line.status==='lost')&&Number.isFinite(Number(line.Quota))&&Number(line.Quota)>1);
  const unitProfit=priced.reduce((total,line)=>total+(line.status==='won'?Number(line.Quota)-1:-1),0);
  const roi=priced.length?(100*unitProfit/priced.length).toFixed(1).replace('.',',')+'%':'—';
  const avgOdds=priced.length?(priced.reduce((total,line)=>total+Number(line.Quota),0)/priced.length).toFixed(2).replace('.',','):'—';
  el('history-status').textContent='';
  el('history-summary').innerHTML=[['Vinte',won],['Perse',lost],['Da verificare',lines.length-resolved],['Successo',rate],['Quota media',avgOdds]].map(([label,value])=>'<div><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');
  el('history-tickets').innerHTML=lines.length?'<section class="daily-group"><h2>Top 5 ufficiale</h2><div class="history-grid">'+lines.map(row=>'<article class="history-ticket"><div class="ticket-heading"><h3>'+escape(row.Giocatore)+'</h3><span class="outcome outcome-'+escape(row.status)+'">'+escape(statusNames[row.status]||'Da verificare')+'</span></div><div class="history-leg"><p>'+escape(row.Partita)+'</p><div class="leg-selection">'+escape(row.Scelta)+' '+escape(row.Linea)+' '+escape(row.Mercato)+' <span>Quota <b>'+odd(row.Quota)+'</b></span></div><p>Probabilità prepartita: '+escape(row['Prob. stimata %'])+'%</p><p class="leg-result">'+(row.actual==null?'Risultato non ancora verificato':'Risultato finale: <strong>'+escape(row.actual)+'</strong>')+'</p></div></article>').join('')+'</div></section>':'';
  if(legacy.length){
   const section=document.createElement('section');section.className='daily-group';
   const details=document.createElement('details');
   const summary=document.createElement('summary');summary.textContent='Archivio storico e altre linee ('+legacy.length+') — escluse dalle statistiche ufficiali';details.append(summary);
   const grid=document.createElement('div');grid.className='history-grid';
   grid.innerHTML=legacy.map(row=>'<article class="history-ticket"><div class="ticket-heading"><h3>'+escape(row.Giocatore)+'</h3><span class="outcome outcome-'+escape(row.status)+'">'+escape(statusNames[row.status]||'Da verificare')+'</span></div><div class="history-leg"><p>'+escape(row.Partita)+'</p><div class="leg-selection">'+escape(row.Scelta)+' '+escape(row.Linea)+' '+escape(row.Mercato)+' <span>Quota <b>'+odd(row.Quota)+'</b></span></div><p>Probabilità prepartita: '+escape(row['Prob. stimata %'])+'%</p><p class="leg-result">'+(row.actual==null?'Risultato non ancora verificato':'Risultato finale: <strong>'+escape(row.actual)+'</strong>')+'</p></div></article>').join('');
   details.append(grid);section.append(details);el('history-tickets').append(section);
  }

  // Compact every official and historical ticket without changing archived data.
  document.querySelectorAll('#extra-history .history-ticket').forEach(ticket=>{
   const heading=ticket.querySelector('.ticket-heading');
   const leg=ticket.querySelector('.history-leg');
   const matchup=leg?.querySelector(':scope > p:not(.leg-result)');
   const result=leg?.querySelector('.leg-result');
   const selection=leg?.querySelector('.leg-selection');
   if(heading&&matchup){
    matchup.classList.add('history-matchup');
    heading.querySelector('h3')?.insertAdjacentElement('afterend',matchup);
   }
   if(result&&selection){
    if(result.textContent.includes('Risultato finale:')){
     result.classList.add('history-inline-result');
     (selection.querySelector('span')||selection).append(result);
    }else result.remove();
   }
  });
 }

 el('history-date').onchange=()=>{historyWeekStart=null;loadHistory();};
 el('back-to-top').onclick=()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 window.addEventListener('scroll',()=>{el('back-to-top').hidden=window.scrollY<700;},{passive:true});
 const initial=Object.keys(routes).find(name=>'#'+routes[name]===location.hash);
 if(initial)show(initial,false);
 else if(location.hash)show('',false);
})();
