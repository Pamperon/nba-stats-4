/* Archived values and outcomes are rendered unchanged. */
window.BasketLabArchiveView=function(document){
 const el=id=>document.getElementById(id);
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const odd=value=>value==null?'—':Number(value).toFixed(2).replace('.',',');
 const statusNames={won:'Centrato',lost:'Non centrato',unresolved:'Da verificare',not_played:'Non ha giocato'};
 function renderHistory(payload){
  const day=/^\d{4}-\d{2}-\d{2}$/.test(payload.date||'')?new Date(payload.date+'T12:00:00Z'):null;
  const dayLabel=day&&!Number.isNaN(day.getTime())?day.toLocaleDateString('it-IT',{timeZone:'Europe/Rome',day:'numeric',month:'long'}):'';
  const single=payload.single_archive||{published:false};
  const selection=single.selection;
  const outcome=single.outcome||{};
  const state=single.published?(outcome.status||'unresolved'):'not_published';
  const singleWon=state==='won'?1:0;
  const singleLost=state==='lost'?1:0;
  const singleSettled=singleWon+singleLost;
  el('history-single-summary').innerHTML=[['Pubblicate',single.published?1:0],['Vinte',singleWon],['Perse',singleLost],['Da verificare',single.published&&state==='unresolved'?1:0],['Successo',singleSettled?(singleWon*100)+'%':'—']]
    .map(([label,value])=>'<div><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');
  el('history-single-tickets').innerHTML=selection
    ?'<section class="daily-group"><h2>Scelta'+(dayLabel?' del '+escape(dayLabel):' del giorno')+'</h2><div class="history-grid"><article class="history-ticket"><div class="ticket-heading"><h3>'+escape(selection.Giocatore)+'</h3><span class="outcome outcome-'+escape(state)+'">'+escape(statusNames[state]||'Da verificare')+'</span></div><div class="history-leg"><p>'+escape(selection.Partita)+'</p><div class="leg-selection">'+escape(selection.Scelta)+' '+escape(selection.Linea)+' '+escape(selection.Mercato)+' <span>Quota <b>'+odd(selection.Quota)+'</b></span></div><p>Probabilità prepartita: '+escape(selection['Prob. stimata %'])+'%</p><p class="leg-result">'+(outcome.actual==null?(state==='not_played'?'Giocatore non sceso in campo':'Risultato non ancora verificato'):'Risultato finale: <strong>'+escape(outcome.actual)+'</strong>')+'</p></div></article></div></section>'
    :'<p class="feature-note">Nessuna scelta ufficiale pubblicata per questa giornata.</p>';
  const lines=payload.official_lines||[];
  const legacy=payload.other_lines||[];
  const won=lines.filter(line=>line.status==='won').length;
  const lost=lines.filter(line=>line.status==='lost').length;
  const resolved=won+lost;
  const rate=resolved?(100*won/resolved).toFixed(1).replace('.',',')+'%':'—';
  const priced=lines.filter(line=>(line.status==='won'||line.status==='lost')&&Number.isFinite(Number(line.Quota))&&Number(line.Quota)>1);
  const avgOdds=priced.length?(priced.reduce((total,line)=>total+Number(line.Quota),0)/priced.length).toFixed(2).replace('.',','):'—';
  el('history-status').textContent='';
  el('history-summary').innerHTML=[['Vinte',won],['Perse',lost],['Da verificare',lines.filter(line=>line.status==='unresolved').length],['Successo',rate],['Quota media',avgOdds]].map(([label,value])=>'<div><strong>'+escape(value)+'</strong><span>'+escape(label)+'</span></div>').join('');
  el('history-tickets').innerHTML=lines.length?'<section class="daily-group"><h2>Le migliori 10'+(dayLabel?' del '+escape(dayLabel):' del giorno')+'</h2><div class="history-grid">'+lines.map(row=>'<article class="history-ticket"><div class="ticket-heading"><h3>'+escape(row.Giocatore)+'</h3><span class="outcome outcome-'+escape(row.status)+'">'+escape(statusNames[row.status]||'Da verificare')+'</span></div><div class="history-leg"><p>'+escape(row.Partita)+'</p><div class="leg-selection">'+escape(row.Scelta)+' '+escape(row.Linea)+' '+escape(row.Mercato)+' <span>Quota <b>'+odd(row.Quota)+'</b></span></div><p>Probabilità prepartita: '+escape(row['Prob. stimata %'])+'%</p><p class="leg-result">'+(row.actual==null?(row.status==='not_played'?'Giocatore non sceso in campo':'Risultato non ancora verificato'):'Risultato finale: <strong>'+escape(row.actual)+'</strong>')+'</p></div></article>').join('')+'</div></section>':'';
  if(legacy.length){
   const section=document.createElement('section');section.className='daily-group';
   const details=document.createElement('details');
   const summary=document.createElement('summary');summary.textContent='Archivio storico e altre linee ('+legacy.length+') — escluse dalle statistiche ufficiali';details.append(summary);
   const grid=document.createElement('div');grid.className='history-grid';
   grid.innerHTML=legacy.map(row=>'<article class="history-ticket"><div class="ticket-heading"><h3>'+escape(row.Giocatore)+'</h3><span class="outcome outcome-'+escape(row.status)+'">'+escape(statusNames[row.status]||'Da verificare')+'</span></div><div class="history-leg"><p>'+escape(row.Partita)+'</p><div class="leg-selection">'+escape(row.Scelta)+' '+escape(row.Linea)+' '+escape(row.Mercato)+' <span>Quota <b>'+odd(row.Quota)+'</b></span></div><p>Probabilità prepartita: '+escape(row['Prob. stimata %'])+'%</p><p class="leg-result">'+(row.actual==null?(row.status==='not_played'?'Giocatore non sceso in campo':'Risultato non ancora verificato'):'Risultato finale: <strong>'+escape(row.actual)+'</strong>')+'</p></div></article>').join('');
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
     const odds=selection.querySelector('span');
     if(odds){
      const value=result.querySelector('strong')?.textContent?.trim()||'';
      result.textContent='';
      result.append(document.createTextNode(' · Ris. '));
      const strong=document.createElement('strong');strong.textContent=value;result.append(strong);
      odds.append(result);
     }else selection.append(result);
    }else result.remove();
   }
  });
 }

 return renderHistory;
};
