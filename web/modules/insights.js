/* Descriptive observations only. Reuses loaded ESPN data; never changes forecasts. */
(function(w){
 'use strict';
 const num=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v))?Number(v):null;
 const fmt=v=>v.toLocaleString('it-IT',{maximumFractionDigits:1,minimumFractionDigits:1});
 const signed=v=>(v>0?'+':'')+fmt(v);
 function record(value){const m=String(value||'').match(/^(\d+)\s*-\s*(\d+)$/);if(!m)return null;const wins=Number(m[1]),losses=Number(m[2]);return wins+losses?{wins,losses,games:wins+losses,label:wins+'–'+losses}:null;}
 function team(t){
  if(!t)return [];
  const wins=num(t.wins),losses=num(t.losses),games=wins!==null&&losses!==null?wins+losses:0,items=[];
  const pf=num(t.points_for),pa=num(t.points_against);
  if(games>=3&&pf!==null&&pa!==null&&pf>=0&&pa>=0){const diff=pf-pa;
   items.push({kind:games>=5&&diff>=3?'strength':'watch',tag:games>=5&&diff>=3?'Punto di forza':'Da osservare',title:diff>=3?'Un margine positivo sugli avversari':diff<=-3?'Il saldo punti resta negativo':'Partite mediamente in equilibrio',value:signed(diff),unit:'punti di differenziale medio',text:'Segna '+fmt(pf)+' punti e ne subisce '+fmt(pa)+' a partita. '+(diff<=-3?'Gli avversari hanno segnato di più nel campione disponibile.':'Il saldo descrive il percorso stagionale, non il risultato della prossima partita.'),evidence:games+' gare di stagione. Differenza tra medie non arrotondate, senza correzioni per possessi o forza degli avversari.'});
  }
  const recent=record(t.last_ten);
  if(recent&&recent.games>=3){const positive=recent.wins/recent.games>=.7;
   const streak=String(t.streak||'').match(/^([WL])(\d+)$/);
   items.push({kind:positive?'strength':'watch',tag:'Forma recente',title:positive?'Continuità nei risultati':recent.wins/recent.games<=.3?'Una fase difficile nei risultati':'Un bilancio recente da seguire',value:recent.label,unit:'nelle ultime '+recent.games+' partite',text:(positive?'Una fase positiva nei risultati.':'Il bilancio recente aiuta a contestualizzare la stagione.')+(streak&&Number(streak[2])>0?' La serie attuale è di '+Number(streak[2])+' '+(streak[1]==='W'?'vittorie':'sconfitte')+' consecutive.':''),evidence:'Bilancio recente e serie riportati nella classifica ESPN. Questo campione si sovrappone a quello stagionale; non è una prova indipendente.'});
  }
  const home=record(t.home_record),away=record(t.away_record);
  if(home&&away&&home.games>=3&&away.games>=3){
   items.push({kind:'watch',tag:'Da osservare',title:'Il confronto casa e trasferta',value:home.label+' / '+away.label,unit:'in casa / in trasferta',text:'Bilanci su '+home.games+' gare in casa e '+away.games+' fuori. '+(Math.min(home.games,away.games)<5?'Il campione è ancora ridotto: è presto per parlare di una tendenza stabile.':'Calendari e avversari diversi: il confronto non isola da solo l’effetto del campo.'),evidence:'Vittorie e sconfitte interne ed esterne dalla classifica ESPN. Nessuna debolezza viene dedotta automaticamente dal solo bilancio.'});
  }
  return items.slice(0,3);
 }
 function sample(t,date){
  // Defence in depth: discard same-day and later results, including in incomplete payloads.
  const rows=Array.isArray(t?.results)?t.results.filter(g=>/^\d{4}-\d{2}-\d{2}$/.test(g.date||'')&&(!date||g.date<date)&&num(g.scored)!==null&&num(g.allowed)!==null&&num(g.scored)>=0&&num(g.allowed)>=0).slice(0,5):[];
  if(rows.length<3)return null;
  const points=rows.reduce((s,g)=>s+num(g.scored),0)/rows.length,allowed=rows.reduce((s,g)=>s+num(g.allowed),0)/rows.length;
  return {n:rows.length,wins:rows.filter(g=>num(g.scored)>num(g.allowed)).length,points,allowed,margin:points-allowed,rows};
 }
 function match(names,data,date){
  if(!Array.isArray(names)||names.length!==2)return [];
  const stats=names.map(name=>(data?.teams||[]).find(t=>t.team===name));
  const [a,b]=stats.map(t=>sample(t,date));if(!a||!b)return [];
  const context='Ultime '+a.n+' e '+b.n+' gare disponibili prima del '+date.split('-').reverse().join('/')+', entro '+(num(data.window_days)||21)+' giorni. Campioni in ordine '+names.join(' / ')+'.'+(data.history_complete===false?' Storico ESPN parziale: confronti provvisori.':'');
  const lead=a.margin>b.margin?0:1,gap=Math.abs(a.margin-b.margin),pct=[a.wins/a.n,b.wins/b.n];
  const items=[{kind:'match',tag:'01 / Differenziale recente',title:gap<.05?'Saldi punti molto vicini':names[lead]+' ha il saldo punti migliore',value:signed(a.margin)+' / '+signed(b.margin),unit:names.join(' / '),text:'Differenza media tra punti segnati e subiti nelle gare osservate. Non è lo scarto previsto di questa partita.',evidence:context},
   {kind:'match',tag:'02 / Forma recente',title:Math.abs(pct[0]-pct[1])<.001?'Bilanci recenti simili':'Due percorsi recenti a confronto',value:a.wins+'–'+(a.n-a.wins)+' / '+b.wins+'–'+(b.n-b.wins),unit:names.join(' / '),text:'Vittorie e sconfitte aiutano a leggere il momento delle squadre. '+(a.n!==b.n?'I campioni hanno dimensioni diverse e vanno confrontati con prudenza.':'Non tengono conto da sole della forza degli avversari.'),evidence:context}];
  const h2h=(data.h2h||[]).filter(g=>/^\d{4}-\d{2}-\d{2}$/.test(g.date||'')&&g.date<date&&Array.isArray(g.teams)&&g.teams.length===2&&names.every(n=>g.teams.includes(n))&&Array.isArray(g.scores)&&g.scores.length===2&&g.scores.every(s=>num(s)!==null));
  if(h2h.length){const hw=names.map(name=>h2h.filter(g=>num(g.scores[g.teams.indexOf(name)])>num(g.scores[1-g.teams.indexOf(name)])).length);
   items.push({kind:'match',tag:'03 / Scontri diretti',title:'I precedenti nel periodo disponibile',value:hw.join('–'),unit:'vittorie · '+names.join(' / '),text:h2h.length+' '+(h2h.length===1?'precedente disponibile: troppo poco per una tendenza.':'precedenti disponibili: non determinano l’esito della prossima sfida.'),evidence:context+' Date: '+h2h.map(g=>g.date.split('-').reverse().join('/')).join(', ')+'.'});
  }else items.push({kind:'match',tag:'03 / Punti concessi',title:'Cosa hanno segnato gli avversari',value:fmt(a.allowed)+' / '+fmt(b.allowed),unit:'punti subiti · '+names.join(' / '),text:'Le medie indicano i punti concessi per gara. Senza il numero di possessi non equivalgono a una misura di efficienza difensiva.',evidence:context});
  return items;
 }
 function render(node,title,items,note){
  if(!node)return;node.replaceChildren();node.className='bl-insights';
  const d=node.ownerDocument,el=(tag,cls,text)=>{const n=d.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;};
  const heading=el('h2','bl-insights-title',title);node.append(heading);
  if(!items.length){node.append(el('p','bl-insights-empty','Dati insufficienti per una lettura attendibile. Le osservazioni appariranno quando il campione sarà disponibile.'));return;}
  const list=el('div','bl-insights-list');
  for(const item of items){const card=el('article','bl-insight bl-insight-'+item.kind);card.append(el('span','bl-insight-tag',item.tag),el('h3','',item.title));const metric=el('div','bl-insight-metric');metric.append(el('strong','',item.value),el('small','',item.unit));card.append(metric,el('p','',item.text));const details=el('details','');details.append(el('summary','','Da quali dati nasce'),el('p','',item.evidence));card.append(details);list.append(card);}
  node.append(list,el('p','bl-insights-note',note));
 }
 w.BasketLabInsights={team,match,render};
})(window);
