'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(root,'web/index.html'),'utf8');
const script=fs.readFileSync(path.join(root,'web/hub-nav.js'),'utf8');
function setup(hash=''){
 const dom=new JSDOM(html,{url:'https://basketlab.it/'+hash,runScripts:'outside-only'});
 const {window}=dom,doc=window.document;
 window.scrollTo=()=>{};
 window.HTMLElement.prototype.scrollIntoView=function(){};
 for(const b of doc.querySelectorAll('#quote-tabs [data-tab]'))b.addEventListener('click',()=>{for(const x of doc.querySelectorAll('#quote-tabs [data-tab]'))x.classList.toggle('active',x===b)});
 for(const b of doc.querySelectorAll('[data-extra]'))b.addEventListener('click',()=>{doc.querySelector('#app').hidden=true;doc.querySelector('#extra-history').hidden=b.dataset.extra!=='history';doc.querySelector('#extra-about').hidden=b.dataset.extra!=='about'});
 window.eval(script);
 return {window,doc};
}
test('desktop and mobile navigation are present',()=>{
 const {window,doc}=setup();
 for(const key of ['home','calendar','picks','stats'])assert.ok(doc.querySelector('.hub-mobile-bar [data-hub="'+key+'"]'));
 for(const key of ['home','picks','stats','finder','history','about'])assert.ok(doc.querySelector('.hub-sidebar [data-hub="'+key+'"]'));
 assert.equal(doc.querySelector('.hub-landing').hidden,false);
 window.close();
});
test('picks and finder hide home panels and activate existing tabs',()=>{
 const {window,doc}=setup();
 doc.querySelector('.hub-sidebar [data-hub="finder"]').click();
 assert.equal(doc.querySelector('.hub-landing').hidden,true);
 assert.ok(doc.querySelector('[data-tab="finder"]').classList.contains('active'));
 doc.querySelector('.hub-mobile-bar [data-hub="home"]').click();
 assert.equal(doc.querySelector('.hub-landing').hidden,false);
 assert.ok(doc.querySelector('[data-tab="dashboard"]').classList.contains('active'));
 window.close();
});
test('archive navigation hides landing and marks current destination',()=>{
 const {window,doc}=setup();
 doc.querySelector('.hub-menu-drawer [data-hub="history"]').click();
 assert.equal(doc.querySelector('.hub-landing').hidden,true);
 assert.equal(doc.querySelector('.hub-menu-drawer [data-hub="history"]').getAttribute('aria-current'),'page');
 window.close();
});
test('direct archive URL does not display home panels',()=>{
 const {window,doc}=setup('#archivio');
 assert.equal(doc.querySelector('.hub-landing').hidden,true);
 window.close();
});

test('homepage cards and metrics hide on other destinations',()=>{
 const {window,doc}=setup();
 assert.equal(doc.querySelector('.hub-featured').hidden,false);
 doc.querySelector('.hub-sidebar [data-hub="stats"]').click();
 assert.equal(doc.querySelector('.hub-featured').hidden,true);
 assert.equal(doc.querySelector('.hub-live-metrics').hidden,true);
 doc.querySelector('.hub-mobile-bar [data-hub="home"]').click();
 assert.equal(doc.querySelector('.hub-featured').hidden,false);
 window.close();
});
test('unified navigation has no old combination shortcuts',()=>{
 const {window,doc}=setup();
 assert.equal(doc.querySelectorAll('[data-pick-group]').length,0);
 doc.querySelector('.hub-mobile-bar [data-hub="picks"]').click();
 assert.equal(doc.querySelector('.hub-landing').hidden,true);
 window.close();
});

test('real pick cards populate featured section without fabricating values',async()=>{
 const {window,doc}=setup();
 const picks=doc.querySelector('#picks');
 picks.innerHTML='<section class="pick-group"><article class="pick-selection"><div class="pick-profile"><div class="pick-avatar"><img src="/static/icon-192.png"></div><button class="pick-player-link">Giocatore Test</button></div><div class="pick-market">OVER 10.5 PTS</div><div class="pick-values">QUOTA 1.80 STIMA DEL MODELLO 75%</div><button class="pick-stats-button">Vedi statistiche</button></article></section>';
 await new Promise(resolve=>window.queueMicrotask(resolve));
 assert.equal(doc.querySelector('#hub-total').textContent,'1');
 assert.equal(doc.querySelector('#hub-prob').textContent,'75%');
 assert.match(doc.querySelector('#hub-featured-list').textContent,/Giocatore Test/);
 assert.match(doc.querySelector('#hub-featured-list').textContent,/OVER 10.5 PTS/);
 window.close();
});
test('no live picks means no fabricated probabilities',async()=>{
 const {window,doc}=setup();
 doc.querySelector('#picks').replaceChildren();
 await new Promise(resolve=>window.queueMicrotask(resolve));
 assert.equal(doc.querySelector('#hub-prob').textContent,'—');
 assert.equal(doc.querySelector('#hub-total').textContent,'0');
 window.close();
});

test('homepage has a separate view state and internal navigation restores dashboard',()=>{
 const {window,doc}=setup();
 assert.equal(doc.body.dataset.hubView,'home');
 doc.querySelector('.hub-sidebar [data-hub="picks"]').click();
 assert.equal(doc.body.dataset.hubView,'picks');
 doc.querySelector('.hub-sidebar [data-hub="finder"]').click();
 assert.equal(doc.body.dataset.hubView,'finder');
 doc.querySelector('.hub-sidebar [data-hub="home"]').click();
 assert.equal(doc.body.dataset.hubView,'home');
 window.close();
});

test('fixture and trend panels reflect saved picks and hide outside home',async()=>{
 const {window,doc}=setup();
 doc.querySelector('#picks').innerHTML='<article class="pick-selection"><div class="pick-fixture" data-match="BOS - NYK"></div><div class="pick-market">OVER 12.5 PTS</div></article><article class="pick-selection"><div class="pick-fixture" data-match="BOS - NYK"></div><div class="pick-market">UNDER 5.5 REB</div></article>';
 await new Promise(resolve=>window.queueMicrotask(resolve));
 assert.match(doc.querySelector('#hub-games').textContent,/BOS - NYK/);
 assert.equal(doc.querySelectorAll('.hub-game').length,1);
 assert.match(doc.querySelector('#hub-trends').textContent,/Over nelle selezioni1/);
 assert.match(doc.querySelector('#hub-trends').textContent,/Under nelle selezioni1/);
 doc.querySelector('.hub-sidebar [data-hub="stats"]').click();
 assert.equal(doc.querySelector('.hub-insights').hidden,true);
 window.close();
});

test('featured cards display separate odds and probability values',async()=>{
 const {window,doc}=setup();
 doc.querySelector('#picks').innerHTML='<article class="pick-selection"><div class="pick-profile"><button class="pick-player-link">Player</button></div><div class="pick-market">OVER 4.5 REB</div><div class="pick-values"><div><small>QUOTA</small><strong>1,86</strong></div><div><small>STIMA DEL MODELLO</small><strong>67.5%</strong></div></div></article>';
 await new Promise(resolve=>window.queueMicrotask(resolve));
 const values=doc.querySelectorAll('.hub-featured-value');
 assert.equal(values.length,2);
 assert.equal(values[0].querySelector('strong').textContent,'1,86');
 assert.equal(values[1].querySelector('strong').textContent,'67.5%');
 window.close();
});

test('mobile navigation drawer opens, navigates and closes',()=>{
 const {window,doc}=setup();
 const toggle=doc.querySelector('.hub-menu-toggle'),drawer=doc.querySelector('#hub-menu-drawer');
 assert.ok(toggle);assert.ok(drawer);assert.equal(drawer.hidden,true);
 toggle.click();assert.equal(drawer.hidden,false);assert.equal(toggle.getAttribute('aria-expanded'),'true');
 drawer.querySelector('[data-hub="picks"]').click();assert.equal(drawer.hidden,true);assert.equal(doc.body.dataset.hubView,'picks');
 toggle.click();doc.dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert.equal(drawer.hidden,true);
 window.close();
});

test('calendar day navigation does not alter the prediction date or dashboard picks',async()=>{
 const {window,doc}=setup();
 const native=doc.querySelector('#date');
 native.innerHTML='<option value="2026-11-02">2 novembre 2026</option><option value="2026-11-03">3 novembre 2026</option>';
 native.value='2026-11-02';
 const strip=doc.querySelector('#date-strip');
 strip.innerHTML='<button type="button">2 NOV</button><button type="button">3 NOV</button>';
 let dateChanges=0;
 native.addEventListener('change',()=>dateChanges++);
 window.fetch=async()=>({ok:true,json:async()=>({games:[]})});
 doc.querySelector('.hub-mobile-bar [data-hub="calendar"]').click();
 const buttons=doc.querySelectorAll('#hub-calendar-dates button');
 assert.equal(buttons.length,2);
 buttons[1].click();
 assert.equal(native.value,'2026-11-02','calendar must not change the shared predictions date');
 assert.equal(dateChanges,0,'calendar must not trigger predictions reload');
 assert.equal(doc.querySelector('#hub-calendar-day-summary strong').textContent,'3 novembre 2026');
 window.close();
});

test('monthly calendar browses historical and future dates without changing prediction session',async()=>{
 const {window,doc}=setup();
 const native=doc.querySelector('#date');
 native.innerHTML='<option value="2026-11-02">2 novembre 2026</option><option value="2026-11-03">3 novembre 2026</option>';
 native.value='2026-11-02';
 doc.querySelector('#date-strip').innerHTML='<button type="button">2 NOV</button><button type="button">3 NOV</button>';
 let changes=0;native.addEventListener('change',()=>changes++);
 window.fetch=async()=>({ok:true,json:async()=>({games:[]})});
 doc.querySelector('.hub-mobile-bar [data-hub="calendar"]').click();
 assert.match(doc.querySelector('#hub-calendar-month-label').textContent,/Novembre 2026/);
 doc.querySelector('#hub-calendar-month-prev').click();
 assert.match(doc.querySelector('#hub-calendar-month-label').textContent,/Ottobre 2026/);
 const historical=[...doc.querySelectorAll('#hub-calendar-month-grid .hub-month-day')].find(b=>b.textContent==='25');
 historical.click();
 assert.match(doc.querySelector('#hub-calendar-day-summary strong').textContent,/25 ottobre 2026/);
 assert.equal(native.value,'2026-11-02');
 assert.equal(changes,0);
 doc.querySelector('#hub-calendar-month-next').click();
 assert.match(doc.querySelector('#hub-calendar-month-label').textContent,/Novembre 2026/);
 window.close();
});
