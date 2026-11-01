/* A+C UI navigation, delegating to original Basket Lab controls. */
(()=>{'use strict';
const $=s=>document.querySelector(s);
const landing=$('.hub-landing'),tiles=$('.hub-tiles'),metrics=$('.hub-live-metrics');
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
function display(){const extra=!!$('.extra-panel:not([hidden])');landing.hidden=!home||extra;tiles.hidden=!home||extra;if(metrics)metrics.hidden=!home||extra;}
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
 const text=(metricTarget?.textContent||'').replace(/\\s+/g,' ').trim();
 const numbers=text.match(/\\d+(?:[.,]\\d+)?%/g);
 if(prob)prob.textContent=numbers?.[0]||'—';
 const picks=$('#picks');
 const cards=picks?.querySelectorAll('article').length||0;
 if(count)count.textContent=cards?String(cards):'—';
 if(last)last.textContent=(updated?.textContent||'').trim().slice(0,26)||'—';
}
if(metricTarget){new MutationObserver(refresh).observe(metricTarget,{childList:true,subtree:true,characterData:true})}
if(updated){new MutationObserver(refresh).observe(updated,{childList:true,subtree:true,characterData:true})}
if($('#picks'))new MutationObserver(refresh).observe($('#picks'),{childList:true,subtree:true});
refresh();
})();