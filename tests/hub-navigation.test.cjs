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
