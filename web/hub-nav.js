/* A+C UI navigation, delegating to original Basket Lab controls. */
(()=>{'use strict';
const $=s=>document.querySelector(s);
const landing=$('.hub-landing'),tiles=$('.hub-tiles'),metrics=$('.hub-live-metrics'),featured=$('.hub-featured');
if(!landing||!tiles)return;
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
function display(){const extra=!!$('.extra-panel:not([hidden])');landing.hidden=!home||extra;tiles.hidden=!home||extra;if(metrics)metrics.hidden=!home||extra;if(featured)featured.hidden=!home||extra;}
function select(key){home=key==='home';mark(key);display();}
document.addEventListener('click',event=>{const b=event.target.closest('[data-hub]');if(!b||!go[b.dataset.hub])return;event.preventDefault();go[b.dataset.hub]();select(b.dataset.hub)});
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
 if(count)count.textContent=cards?String(cards):'—';
 if(last)last.textContent=(updated?.textContent||'').trim().slice(0,26)||'—';
}
if(metricTarget){new MutationObserver(refresh).observe(metricTarget,{childList:true,subtree:true,characterData:true})}
if(updated){new MutationObserver(refresh).observe(updated,{childList:true,subtree:true,characterData:true})}
if($('#picks'))new MutationObserver(refresh).observe($('#picks'),{childList:true,subtree:true});
document.querySelectorAll('[data-pick-group]').forEach(b=>b.addEventListener('click',()=>{go.picks();select('picks');$('#pick-'+b.dataset.pickGroup)?.scrollIntoView({block:'start',behavior:'smooth'})}));
function featuredPicks(){
 const list=$('#hub-featured-list'),picks=$('#picks');
 if(!list||!picks)return;
 const sources=[...picks.querySelectorAll('.pick-selection')].slice(0,3);
 list.replaceChildren();
 for(const source of sources){
  const card=document.createElement('div');card.className='hub-featured-card';
  const content=document.createElement('div');content.className='hub-featured-summary';
  const name=document.createElement('strong');name.textContent=source.querySelector('.pick-player-link')?.textContent||'Analisi NBA';
  const market=document.createElement('p');market.textContent=source.querySelector('.pick-market')?.textContent||'';
  const values=document.createElement('p');values.textContent=(source.querySelector('.pick-values')?.textContent||'').replace(/\s+/g,' ').trim();
  const avatar=source.querySelector('.pick-avatar img');if(avatar){const img=document.createElement('img');img.src=avatar.src;img.alt='';img.loading='lazy';content.append(img)}
  content.append(name,market,values);card.append(content);
  const action=document.createElement('button');action.type='button';action.textContent='Apri statistiche →';
  action.addEventListener('click',()=>{go.picks();select('picks');source.querySelector('.pick-stats-button')?.click()});
  card.append(action);list.append(card);
 }
 if(!sources.length)list.textContent='Nessuna selezione disponibile per la giornata.';
}
if($('#picks'))new MutationObserver(featuredPicks).observe($('#picks'),{childList:true});
refresh();featuredPicks();
})();