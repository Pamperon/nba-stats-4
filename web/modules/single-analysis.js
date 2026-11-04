/* One current-selection page. No generated commentary or new provider calls. */
(function(root){
 'use strict';
 let generation=0;
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=value=>value===null||value===undefined||value===''?null:Number.isFinite(Number(value))?Number(value):null;
 const fmt=(value,digits=1)=>number(value)===null?'—':Number(value).toLocaleString('it-IT',{maximumFractionDigits:digits});
 const date=value=>{const at=new Date(value);return Number.isNaN(at.getTime())?'—':at.toLocaleDateString('it-IT',{day:'numeric',month:'short',timeZone:'Europe/Rome'});};
 const unit={PTS:'punti',REB:'rimbalzi',AST:'assist'};
 function chart(games,market,line,under){
  if(!games.length)return '<p class="sa-empty">Storico salvato non disponibile per questa selezione.</p>';
  const rows=games.slice().reverse(),w=Math.max(340,rows.length*34),h=230,left=20,right=w-16,top=25,bottom=190;
  const max=Math.max(line,...rows.map(g=>Number(g[market])))*1.22||1;
  const y=v=>bottom-(v/max)*(bottom-top),step=(right-left)/rows.length,bw=Math.min(30,step*.64);
  const bars=rows.map((g,i)=>{const v=Number(g[market]),x=left+step*(i+.5),hit=under?v<line:v>line;const color=v===line?'#dcb54c':hit?'#1dc987':'#bf6d87';return '<g><title>'+escape(date(g.GAME_DATE)+': '+fmt(v)+' '+unit[market]+(g.MATCHUP?' · '+g.MATCHUP:''))+'</title><rect x="'+(x-bw/2)+'" y="'+y(v)+'" width="'+bw+'" height="'+(bottom-y(v))+'" rx="4" fill="'+color+'"/><text x="'+x+'" y="'+(y(v)-7)+'" text-anchor="middle" class="sa-chart-value">'+fmt(v)+'</text>'+(rows.length<=10||i%3===0||i===rows.length-1?'<text x="'+x+'" y="210" text-anchor="middle" class="sa-chart-date">'+escape(date(g.GAME_DATE))+'</text>':'')+'</g>';}).join('');
  return '<svg viewBox="0 0 '+w+' '+h+'" style="min-width:'+w+'px" role="img" aria-label="'+escape('Ultime '+rows.length+' prestazioni: '+unit[market]+', linea '+fmt(line))+'"><line x1="'+left+'" y1="'+bottom+'" x2="'+right+'" y2="'+bottom+'" stroke="#385668"/>'+bars+'<line x1="'+left+'" y1="'+y(line)+'" x2="'+right+'" y2="'+y(line)+'" stroke="#ffab58" stroke-width="2" stroke-dasharray="5 4"/><text x="'+right+'" y="'+(y(line)-7)+'" text-anchor="end" class="sa-chart-line">Linea '+fmt(line)+'</text></svg>';
 }
 function render(panel,payload,back,backLabel='← Torna ai pronostici'){
  const r=payload.selection;
  panel.innerHTML='<button type="button" class="bl-back sa-back">← Torna ai pronostici</button>';
  panel.querySelector('.sa-back').textContent=backLabel;
  panel.querySelector('.sa-back').onclick=back;
  if(!r){panel.insertAdjacentHTML('beforeend','<div class="sa-card"><h1>Analisi della Singola</h1><p>Nessuna Singola idonea disponibile per questa giornata.</p></div>');return;}
  const official=payload.state==='official',market=r.Mercato,line=number(r.Linea),prob=number(r['Prob. stimata %']),odd=number(r.Quota),under=String(r.Scelta).toLowerCase()==='under';
  const implied=odd>1?100/odd:null,value=prob!==null&&odd!==null?prob*odd-100:null;
  const name=String(r.Giocatore||'').replace(/^([^,]+),\s*(.+)$/,'$2 $1');
  const logs=Array.isArray(payload.games)?payload.games.filter(g=>number(g[market])!==null):[];
  const avg=number(r['Minuti medi']),recent=number(r['Minuti ultime 5']);
  const availability={ 'not-listed':'Nessuna assenza segnalata',out:'Assente',questionable:'In dubbio',doubtful:'In forte dubbio','day-to-day':'Da valutare',suspension:'Sospeso',unknown:'Disponibilità non verificata'}[r['Disponibilità ESPN']]||'Dato non disponibile';
  panel.insertAdjacentHTML('beforeend','<header class="sa-heading"><div><p class="sa-eyebrow">IL LAB SPIEGA · '+escape(date(payload.date+'T12:00:00Z'))+'</p><h1>Analisi della Singola</h1></div><span class="bl-publication-badge" data-state="'+(official?'official':'preview')+'">'+(official?'Ufficiale':'Conferma alle 18:00')+'</span></header>'+
   '<section class="sa-hero"><div class="sa-identity">'+(/^\d+$/.test(String(r['ESPN ID']))?'<img src="/api/players/headshot/'+escape(r['ESPN ID'])+'" alt="" width="100" height="100">':'')+'<div><p class="sa-eyebrow">SINGOLA DEL GIORNO</p><h2>'+escape(name)+'</h2><p>'+escape(r.Partita)+'</p></div></div><div class="sa-selection">'+escape(r.Scelta)+' '+fmt(line)+' '+escape(unit[market]||market)+'</div><div class="sa-metrics"><div><small>Quota selezionata</small><strong>'+fmt(odd,2)+'</strong></div><div><small>Stima del modello</small><strong>'+fmt(prob)+'%</strong></div><div><small>Value stimato</small><strong>'+fmt(value)+'%</strong></div></div><p class="sa-caption">'+(official?'Quota e stima fissate alla pubblicazione.':'Selezione provvisoria: può cambiare con i prossimi aggiornamenti.')+'</p></section>'+
   '<section class="sa-card"><p class="sa-eyebrow">LA LOGICA DELLA SCELTA</p><h2>Perché questa selezione</h2><p>La regola della Singola confronta le linee idonee e privilegia il <strong>value stimato più alto</strong>, con la probabilità come criterio di spareggio.</p><div class="sa-reasons"><div><span>Quota nel range</span><strong>1,70–1,90</strong></div><div><span>Probabilità richiesta</span><strong>Oltre il 70%</strong></div><div><span>Margine sulla probabilità implicita</span><strong>'+fmt(prob!==null&&implied!==null?prob-implied:null)+' punti</strong></div></div><p class="sa-caption">La quota '+fmt(odd,2)+' implica il '+fmt(implied)+'%. Il value è calcolato come probabilità × quota − 1: dipende dall’attendibilità della stima.</p></section>'+
   '<section class="sa-card"><div class="sa-chart-heading"><div><p class="sa-eyebrow">LE PRESTAZIONI SALVATE</p><h2>'+escape(unit[market]||market)+' nelle ultime partite</h2></div><div class="sa-period" role="group" aria-label="Numero di partite">'+[5,10,20].map(n=>'<button type="button" data-period="'+n+'" aria-pressed="'+(n===20)+'">'+n+'</button>').join('')+'</div></div><div class="sa-history-summary"></div><div class="sa-chart-scroll"></div><p class="sa-caption">Verde: linea '+(under?'non raggiunta':'superata')+' · Rosa: selezione non centrata. Scorri il grafico per vedere tutte le partite.</p></section>'+
   '<div class="sa-details"><section class="sa-card"><p class="sa-eyebrow">IL RUOLO</p><h2>Minutaggio</h2><div class="sa-minutes"><div><strong>'+fmt(recent)+'</strong><span>ultime 5</span></div><div><strong>'+fmt(avg)+'</strong><span>media storica</span></div></div><p class="sa-caption">Controlliamo che il minutaggio recente non presenti un calo rilevante rispetto allo storico.</p></section><section class="sa-card"><p class="sa-eyebrow">IL CAMPIONE</p><h2>Da quali dati nasce</h2><p><strong>'+fmt(r.Partite,0)+' partite</strong> nello storico della stima.</p><p class="sa-caption">Stagione attuale: '+fmt(r['Stagione attuale (n)'],0)+' · Precedente: '+fmt(r['Stagione precedente (n)'],0)+'. Lo storico può riflettere ruoli diversi da quello attuale.</p></section></div>'+
   '<section class="sa-card sa-availability"><div><p class="sa-eyebrow">DISPONIBILITÀ ESPN</p><h2>'+escape(availability)+'</h2></div><p class="sa-caption">Report salvato'+(r['Disponibilità verificata alle']?' il '+escape(date(r['Disponibilità verificata alle'])):'')+'. L’assenza di segnalazioni non conferma la partecipazione.</p></section><p class="sa-footnote">Stima empirica non ancora calibrata. Il grafico descrive lo storico salvato e non garantisce il risultato della prossima partita.</p>');
  const paint=n=>{
   const sample=logs.slice(0,n),hits=sample.filter(g=>under?Number(g[market])<line:Number(g[market])>line).length;
   panel.querySelector('.sa-chart-scroll').innerHTML=chart(sample,market,line,under);
   panel.querySelector('.sa-history-summary').innerHTML=sample.length?'<strong>'+hits+'/'+sample.length+'</strong><span>linea centrata nelle partite disponibili · '+fmt(hits*100/sample.length)+'%</span>':'<span>Nessun dato storico salvato disponibile.</span>';
   panel.querySelectorAll('[data-period]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.period)===n)));
  };
  panel.querySelectorAll('[data-period]').forEach(b=>b.onclick=()=>paint(Number(b.dataset.period)));paint(20);
 }
 async function open(panel,back,backLabel){
  const request=++generation;
  const response=await fetch('/api/picks/single-analysis',{cache:'no-store'});
  if(!response.ok)throw Error('Analysis unavailable');
  const payload=await response.json();if(request===generation)render(panel,payload,back,backLabel);
 }
 root.BasketLabSingleAnalysis={open,render};
})(window);
