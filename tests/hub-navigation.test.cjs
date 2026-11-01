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
 for(const key of ['home','picks','stats','history'])assert.ok(doc.querySelector('.hub-mobile-bar [data-hub="'+key+'"]'));
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
 doc.querySelector('.hub-mobile-bar [data-hub="history"]').click();
 assert.equal(doc.querySelector('.hub-landing').hidden,true);
 assert.equal(doc.querySelector('.hub-mobile-bar [data-hub="history"]').getAttribute('aria-current'),'page');
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
test('category shortcuts target actual pick groups',()=>{
 const {window,doc}=setup();
 assert.equal(doc.querySelectorAll('[data-pick-group]').length,3);
 doc.querySelector('[data-pick-group="doppia"]').click();
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
