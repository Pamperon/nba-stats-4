'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const html=fs.readFileSync('web/index.html','utf8'),script=fs.readFileSync('web/modules/player-form.js','utf8');
const player={id:'22',name:'Alex Test',team:'Boston Celtics',games:12,recent_average:25,season_average:20,delta:5};
const payload={season:'2026–27',eligible_players:42,generated_at:'2026-11-17T18:00:00+01:00',markets:{PTS:{up:[player],down:[{...player,delta:-3,recent_average:17}]},REB:{up:[{...player,recent_average:8,season_average:6,delta:2}],down:[]},AST:{up:[],down:[]}}};
const tick=()=>new Promise(r=>setImmediate(r));
function setup(fetch){const dom=new JSDOM(html,{url:'https://basketlab.it/',runScripts:'outside-only'});dom.window.fetch=fetch;return dom;}
test('form sits after fixtures, filters without refetching, and preserves native player links',async()=>{
 let calls=0;const dom=setup(async()=>{calls++;return {ok:true,json:async()=>payload};}),w=dom.window;
 try{w.eval(script);await tick();const d=w.document,panel=d.querySelector('#player-form');
 assert.ok(panel.previousElementSibling.classList.contains('hub-games-section'));assert.ok(panel.nextElementSibling.classList.contains('hub-featured'));assert.equal(panel.querySelector('details'),null);
 assert.match(d.querySelector('.pf-player').textContent,/25,0/);assert.match(d.querySelector('#pf-coverage').textContent,/42 confrontabili/);
 d.querySelector('[data-pf-market=REB]').click();assert.match(d.querySelector('.pf-player').getAttribute('href'),/mercato=REB/);assert.match(d.querySelector('.pf-player').textContent,/8,0/);
 d.querySelector('[data-pf-direction=down]').click();assert.equal(d.querySelectorAll('.pf-player').length,0);assert.match(d.querySelector('#pf-results').textContent,/Nessun calo/);
 d.querySelector('[data-pf-market=PTS]').click();assert.match(d.querySelector('.pf-delta').textContent,/−3,0/);assert.equal(calls,1);
 }finally{w.close();}
});
test('load is deferred while offscreen and handles retry without inventing players',async()=>{
 let observe,requests=0;const dom=setup(async()=>{requests++;return requests===1?{ok:false}:{ok:true,json:async()=>payload};}),w=dom.window;
 try{w.IntersectionObserver=class{constructor(cb){observe=cb;}observe(){}};w.eval(script);assert.equal(requests,0);
 observe([{isIntersecting:true}]);await tick();assert.equal(w.document.querySelectorAll('.pf-player').length,0);assert.ok(w.document.querySelector('.pf-retry'));
 w.document.querySelector('.pf-retry').click();await tick();assert.equal(w.document.querySelectorAll('.pf-player').length,1);
 }finally{w.close();}
});
