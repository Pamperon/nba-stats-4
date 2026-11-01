/* A+C UI navigation, delegating to original Basket Lab controls. */
(()=>{'use strict';
const $=s=>document.querySelector(s);
const landing=$('.hub-landing'),tiles=$('.hub-tiles'),metrics=$('.hub-live-metrics'),featured=$('.hub-featured'),insights=$('.hub-insights');
if(!landing||!tiles)return;
const menuToggle=$('.hub-menu-toggle'),menuDrawer=$('#hub-menu-drawer');
function closeMenu(){if(!menuDrawer)return;menuDrawer.hidden=true;menuToggle?.setAttribute('aria-expanded','false');menuToggle?.setAttribute('aria-label','Apri menu di navigazione')}
menuToggle?.addEventListener('click',()=>{const opening=menuDrawer.hidden;menuDrawer.hidden=!opening;menuToggle.setAttribute('aria-expanded',String(opening));menuToggle.setAttribute('aria-label',opening?'Chiudi menu di navigazione':'Apri menu di navigazione')});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu()});
document.addEventListener('click',event=>{if(menuDrawer&&!menuDrawer.hidden&&!event.target.closest('.hub-menu-drawer,.hub-menu-toggle'))closeMenu()});
const tab=name=>$('[data-tab="'+name+'"]');
const go={
 home(){ $('#area-quotes')?.click();tab('dashboard')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 picks(){ $('#area-quotes')?.click();tab('dashboard')?.click();tab('dashboard')?.scrollIntoView({block:'start',behavior:'smooth'});},
 stats(){ $('#area-stats')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 finder(){ $('#area-quotes')?.click();tab('finder')?.click();$('#quote-tabs')?.scrollIntoView({block:'start',behavior:'smooth'});},
 history(){ $('[data-extra="history"]')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 about(){ $('[data-extra="about"]')?.click();window.scrollTo({top:0,behavior:'smooth'});}
};
let home=true;
function mark(key){document.querySelectorAll('[data-hub]').forEach(el=>{if(el.dataset.hub===key)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')})}
function display(){const extra=!!$('.extra-panel:not([hidden])');landing.hidden=!home||extra;tiles.hidden=!home||extra;if(metrics)metrics.hidden=!home||extra;if(featured)featured.hidden=!home||extra;if(insights)insights.hidden=!home||extra;}
function select(key){home=key==='home';mark(key);display();document.body.dataset.hubView=key;}
document.addEventListener('click',event=>{const b=event.target.closest('[data-hub]');if(!b||!go[b.dataset.hub])return;event.preventDefault();go[b.dataset.hub]();select(b.dataset.hub);closeMenu()});
$('#quote-tabs')?.addEventListener('click',event=>{const button=event.target.closest('[data-tab]');if(!button)return;const key=button.dataset.tab==='finder'?'finder':button.dataset.tab==='player'?'stats':'picks';select(key)});
$('#area-stats')?.addEventListener('click',()=>select('stats'));
document.querySelectorAll('[data-extra]').forEach(el=>el.addEventListener('click',()=>select(el.dataset.extra==='history'?'history':'about')));
document.querySelectorAll('[data-return-site]').forEach(el=>el.addEventListener('click',()=>select('picks')));
window.addEventListener('hashchange',()=>{if(location.hash==='#archivio')select('history');else if(location.hash==='#come-funziona')select('about');else display()});
if(location.hash==='#archivio')select('history');else if(location.hash==='#come-funziona')select('about');else select('home');
/* Populate homepage only from values rendered by the existing data engine. */
const metricTarget=$('#metrics'),updated=$('#quote-updated');
function refresh(){
 const count=$('#hub-total'),prob=$('#hub-prob'),last=$('#hub-update');
 const picks=$('#picks');
 const percentages=[...(picks?.querySelectorAll('.pick-values')||[])].map(el=>{const m=el.textContent.match(/STIMA DEL MODELLO\s*(\d+(?:[.,]\d+)?)%/);return m?Number(m[1].replace(',','.')):NaN}).filter(Number.isFinite);
 if(prob)prob.textContent=percentages.length?(percentages.reduce((a,b)=>a+b,0)/percentages.length).toLocaleString('it-IT',{maximumFractionDigits:1})+'%':'—';
 const cards=picks?.querySelectorAll('.pick-selection').length||0;
 if(count)count.textContent=cards?String(cards):'0';
 if(last){const raw=(updated?.textContent||'').trim();const stamp=raw.match(/(?:\d{1,2}:\d{2})(?::\d{2})?/);last.textContent=stamp?stamp[0]:'—';last.title=raw;}
}
if(metricTarget){new MutationObserver(refresh).observe(metricTarget,{childList:true,subtree:true,characterData:true})}
if(updated){new MutationObserver(refresh).observe(updated,{childList:true,subtree:true,characterData:true})}
if($('#picks'))new MutationObserver(refresh).observe($('#picks'),{childList:true,subtree:true});
document.querySelectorAll('[data-pick-group]').forEach(b=>b.addEventListener('click',()=>{go.picks();select('picks');$('#pick-'+b.dataset.pickGroup)?.scrollIntoView({block:'start',behavior:'smooth'});closeMenu()}));
function featuredPicks(){
 const list=$('#hub-featured-list'),picks=$('#picks');
 if(!list||!picks)return;
 const sources=[...picks.querySelectorAll('.pick-group-daily .pick-group-items > .pick-selection')].slice(0,5);
 const visibleSources=sources.length?sources:[...picks.querySelectorAll('.pick-selection')].slice(0,5);
 list.replaceChildren();
 for(const source of visibleSources){
  const card=document.createElement('div');card.className='hub-featured-card';
  const content=document.createElement('div');content.className='hub-featured-summary';
  const name=document.createElement('strong');name.textContent=source.querySelector('.pick-player-link')?.textContent||'Analisi NBA';
  const market=document.createElement('p');market.textContent=source.querySelector('.pick-market')?.textContent||'';
  const values=document.createElement('div');values.className='hub-featured-values';
  const blocks=[...source.querySelectorAll('.pick-values > div')];
  for(const block of blocks){const item=document.createElement('div');item.className='hub-featured-value';const label=document.createElement('small');label.textContent=block.querySelector('small')?.textContent||'';const number=document.createElement('strong');number.textContent=block.querySelector('strong')?.textContent||'';item.append(label,number);values.append(item)}
  if(!blocks.length){const fallback=document.createElement('span');fallback.textContent=(source.querySelector('.pick-values')?.textContent||'').replace(/\s+/g,' ').trim();values.append(fallback)}
  const avatar=source.querySelector('.pick-avatar');if(avatar){const clone=avatar.cloneNode(true);clone.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));clone.classList.add('hub-featured-avatar');content.append(clone)}
  content.append(name,market,values);card.append(content);
  const action=document.createElement('button');action.type='button';action.textContent='Statistiche giocatore →';
  action.addEventListener('click',()=>{go.picks();select('picks');source.querySelector('.pick-stats-button')?.click()});
  card.append(action);list.append(card);
 }
 if(!visibleSources.length)list.textContent='Nessuna selezione disponibile per la giornata.';
}
function updateInsights(){
 const picks=$('#picks'),games=$('#hub-games'),trends=$('#hub-trends');if(!picks||!games||!trends)return;
 const matches=[...new Set([...picks.querySelectorAll('.pick-fixture')].map(el=>el.dataset.match||el.textContent.trim()).filter(Boolean))];
 games.replaceChildren();
 if(!matches.length)games.textContent='Nessuna partita nelle selezioni della giornata.';
 for(const match of matches.slice(0,5)){const el=document.createElement('div');el.className='hub-game';el.textContent=match;games.append(el)}
 const markets=[...picks.querySelectorAll('.pick-market')].map(el=>el.textContent.trim()).filter(Boolean);
 trends.replaceChildren();
 if(!markets.length)trends.textContent='Nessuna selezione disponibile.';
 const counts=new Map();for(const market of markets){const type=market.toUpperCase().startsWith('UNDER')?'Under':'Over';counts.set(type,(counts.get(type)||0)+1)}
 for(const [type,count] of counts){const el=document.createElement('div');el.className='hub-trend';const label=document.createElement('span');label.textContent=type+' nelle selezioni';const value=document.createElement('strong');value.textContent=String(count);el.append(label,value);trends.append(el)}
}
if($('#picks'))new MutationObserver(()=>{featuredPicks();updateInsights()}).observe($('#picks'),{childList:true});
refresh();featuredPicks();updateInsights();
})();