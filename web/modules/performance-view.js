/* Published archive aggregates only; opening this panel makes no data requests. */
(function(root){
 'use strict';
 const d=root.document,labels={PTS:'Punti',REB:'Rimbalzi',AST:'Assist'};
 let drawer,data,tab='single',returnFocus,retry;
 const make=(tag,className,text)=>{const n=d.createElement(tag);if(className)n.className=className;if(text!=null)n.textContent=text;return n;};
 const number=n=>Number.isFinite(n)?n.toLocaleString('it-IT'):'—';
 const rate=group=>Number.isFinite(group?.success_pct)?number(group.success_pct)+'%':'—';
 function close(){if(!drawer?.open)return;if(drawer.close)drawer.close();else{drawer.removeAttribute('open');drawer.dispatchEvent(new Event('close'));}}
 function ensure(){
  if(drawer)return;
  drawer=make('dialog','bl-performance-dialog');drawer.setAttribute('aria-labelledby','bl-performance-title');
  const header=make('header','bl-performance-header'),heading=make('h2',null,'Rendimento del Lab');heading.id='bl-performance-title';
  const dismiss=make('button','bl-performance-close','×');dismiss.type='button';dismiss.setAttribute('aria-label','Chiudi il rendimento del Lab');dismiss.onclick=close;
  header.append(heading,dismiss);
  const tabs=make('div','bl-performance-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Tipo di analisi');
  for(const [key,label] of [['single','Scelta del giorno'],['others','Altre selezioni']]){
   const b=make('button',null,label);b.type='button';b.id='bl-performance-tab-'+key;b.dataset.group=key;b.setAttribute('role','tab');b.setAttribute('aria-controls','bl-performance-panel');
   b.onclick=()=>{tab=key;render();};tabs.append(b);
  }
  tabs.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();tab=event.key==='Home'?'single':event.key==='End'?'others':tab==='single'?'others':'single';render();tabs.querySelector('[data-group='+tab+']').focus();};
  const panel=make('section','bl-performance-panel');panel.id='bl-performance-panel';panel.setAttribute('role','tabpanel');panel.tabIndex=0;
  drawer.append(header,tabs,panel);d.body.append(drawer);
  drawer.addEventListener('close',()=>{d.documentElement.classList.remove('bl-performance-modal-open');if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});returnFocus=null;});
  drawer.addEventListener('click',event=>{if(event.target!==drawer)return;const r=drawer.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)close();});
  d.addEventListener('basketlab:view',close);root.addEventListener('popstate',close);
 }
 function counts(group){
  const list=make('dl','bl-performance-counts');
  for(const [key,label] of [['won','Centrate'],['lost','Non centrate'],['not_played','Non ha giocato'],['pending','Da verificare']]){
   const cell=make('div');cell.dataset.outcome=key;cell.append(make('dt',null,label),make('dd',null,number(group[key])));list.append(cell);
  }
  return list;
 }
 function render(){
  if(!drawer)return;
  for(const b of drawer.querySelectorAll('[role=tab]')){const active=b.dataset.group===tab;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1;}
  const panel=drawer.querySelector('#bl-performance-panel');panel.setAttribute('aria-labelledby','bl-performance-tab-'+tab);panel.replaceChildren();panel.setAttribute('aria-busy',String(data===undefined));
  if(data===undefined){panel.append(make('p','bl-performance-message','Caricamento dei risultati…'));return;}
  const group=data?.breakdown?.[tab];
  if(!group){
   panel.append(make('p','bl-performance-message','Dettaglio temporaneamente non disponibile.'));
   const button=make('button','bl-performance-retry','Riprova');button.type='button';button.onclick=()=>retry?.();panel.append(button);return;
  }
  const summary=make('div','bl-performance-summary'),percentage=make('strong',null,rate(group));
  const description=make('div');description.append(make('p',null,number(group.won)+' centrate su '+number(group.verified)+' verificate'),make('small',null,number(group.published)+' analisi pubblicate'));
  summary.append(percentage,description);panel.append(summary);
  if(!group.published)panel.append(make('p','bl-performance-message',tab==='single'?'Nessuna scelta del giorno pubblicata.':'Nessun’altra selezione pubblicata.'));
  const markets=make('div','bl-performance-markets');
  for(const [key,label] of Object.entries(labels)){
   const item=group.by_market?.[key];if(!item)continue;
   const card=make('article','bl-performance-market'),heading=make('div','bl-performance-market-heading');heading.append(make('h3',null,label),make('strong',null,rate(item)));
   card.append(heading,make('p','bl-performance-sample',number(item.won)+' su '+number(item.verified)+' verificate'));
   if(!item.published)card.append(make('p','bl-performance-empty','Nessuna analisi pubblicata'));
   else card.append(counts(item));
   markets.append(card);
  }
  panel.append(markets);
  if(group.unclassified)panel.append(make('p','bl-performance-note',number(group.unclassified)+' analisi senza mercato classificato incluse nel totale.'));
  panel.append(make('p','bl-performance-note','Percentuali calcolate su centrate e non centrate. Chi non ha giocato e gli esiti da verificare sono esclusi dal calcolo.'));
  panel.append(make('p','bl-performance-period','Dal 1 novembre 2026 · '+(tab==='single'?'Scelte del giorno effettivamente pubblicate.':'Selezioni pubblicate, esclusa l’eventuale scelta del giorno già conteggiata.')));
 }
 root.BasketLabPerformance={open(stats,source,onRetry){root.BasketLabAssets?.style('performance-panel');ensure();data=stats;retry=onRetry;tab='single';render();if(!drawer.open){returnFocus=source;d.documentElement.classList.add('bl-performance-modal-open');if(drawer.showModal)drawer.showModal();else drawer.setAttribute('open','');}drawer.querySelector('.bl-performance-close').focus();},update(stats){data=stats;if(drawer?.open)render();}};
})(window);
