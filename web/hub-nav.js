/* A+C navigation shell. Existing app controls remain the source of truth. */
(()=>{const $=s=>document.querySelector(s);
const destinations={home:()=>{$('#area-quotes')?.click();$('[data-tab="dashboard"]')?.click();window.scrollTo({top:0,behavior:'smooth'})},picks:()=>{$('#area-quotes')?.click();$('[data-tab="dashboard"]')?.click();$('#quote-tabs')?.scrollIntoView({behavior:'smooth',block:'start'})},stats:()=>{$('#area-stats')?.click();window.scrollTo({top:0,behavior:'smooth'})},finder:()=>{$('#area-quotes')?.click();$('[data-tab="finder"]')?.click();$('#quote-tabs')?.scrollIntoView({behavior:'smooth',block:'start'})},history:()=>{const a=$('[data-extra="history"]');a?.click();window.scrollTo({top:0,behavior:'smooth'})},about:()=>{const a=$('[data-extra="about"]');a?.click();window.scrollTo({top:0,behavior:'smooth'})}};
function active(key){document.querySelectorAll('[data-hub]').forEach(el=>{if(el.dataset.hub===key)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')})}
document.addEventListener('click',e=>{const b=e.target.closest('[data-hub]');if(!b)return;const key=b.dataset.hub;if(!destinations[key])return;e.preventDefault();destinations[key]();active(key)});
const shell=$('.hub-shell');if(!shell)return;
const nav=$('#quote-tabs');if(nav)nav.addEventListener('click',e=>{const b=e.target.closest('[data-tab]');if(b)active(b.dataset.tab==='finder'?'finder':b.dataset.tab==='player'?'stats':'picks')});
$('#area-stats')?.addEventListener('click',()=>active('stats'));
document.querySelectorAll('[data-extra]').forEach(el=>el.addEventListener('click',()=>active(el.dataset.extra==='history'?'history':'about')));
document.querySelectorAll('[data-return-site]').forEach(el=>el.addEventListener('click',()=>active('picks')));
active('home');
})();
