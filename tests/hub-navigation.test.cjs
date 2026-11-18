'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(root,'web/index.html'),'utf8');
const windows=[];
test.afterEach(()=>{for(const window of windows.splice(0))window.close()});
const script=fs.readFileSync(path.join(root,'web/hub-nav.js'),'utf8');
function setup(hash='',fetchImpl,prepare){
 const dom=new JSDOM(html,{url:'https://basketlab.it/'+hash,runScripts:'outside-only'});
 const {window}=dom,doc=window.document;windows.push(window);
 if(fetchImpl)window.fetch=fetchImpl;
 if(prepare)prepare(window);
 window.scrollTo=()=>{};
 window.HTMLElement.prototype.scrollIntoView=function(){};
 for(const b of doc.querySelectorAll('#quote-tabs [data-tab]'))b.addEventListener('click',()=>{for(const x of doc.querySelectorAll('#quote-tabs [data-tab]'))x.classList.toggle('active',x===b)});
 for(const b of doc.querySelectorAll('[data-extra]'))b.addEventListener('click',()=>{doc.querySelector('#app').hidden=true;doc.querySelector('#extra-history').hidden=b.dataset.extra!=='history';doc.querySelector('#extra-about').hidden=b.dataset.extra!=='about'});
 window.eval(fs.readFileSync(path.join(root,'web/modules/router.js'),'utf8'));
 for(const file of ['insights','match-charts','match-data','calendar-data','boxscore-view','match-players','nba-hub'])window.eval(fs.readFileSync(path.join(root,'web/modules/'+file+'.js'),'utf8'));
 window.eval(script);
 window.eval(fs.readFileSync(path.join(root,'web/modules/team-links.js'),'utf8'));
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
 assert.equal(doc.querySelector('.bl-data-odd strong').textContent,'1,86');
 assert.equal(doc.querySelector('.bl-data-prob strong').textContent,'67.5%');
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
 assert.equal(buttons.length,7);
 [...buttons].find(b=>b.getAttribute('aria-label')==='3 novembre 2026').click();
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

test('Pronostici share Home cards and retain analysis actions across navigation',async()=>{
 const {window,doc}=setup();
 const singlePanel=doc.querySelector('.hub-single-section'),topPanel=doc.querySelector('.hub-featured');
 const homeParent=singlePanel.parentElement;
 const source=(name)=>'<article class="pick-selection"><div class="pick-profile"><div class="pick-avatar"><span>NBA</span></div><button class="pick-player-link">'+name+'</button></div><div class="pick-market">OVER 4.5 REB</div><div class="pick-values"><div><small>QUOTA</small><strong>1,80</strong></div><div><small>STIMA DEL MODELLO</small><strong>75%</strong></div></div><button class="pick-stats-button">Statistiche</button></article>';
 doc.querySelector('#picks').innerHTML='<section class="pick-group" aria-label="La scelta del Lab"><h2>La scelta del Lab</h2><div class="pick-group-items">'+source('Single Player')+'</div></section><section id="pick-giorno"><div class="pick-group-items">'+source('Top Player')+'</div></section>';
 let singleClicks=0,topClicks=0;
 const actions=doc.querySelectorAll('#picks .pick-stats-button');
 actions[0].onclick=()=>singleClicks++;actions[1].onclick=()=>topClicks++;
 await new Promise(resolve=>setImmediate(resolve));
 const card=singlePanel.querySelector('.bl-broadcast');
 doc.querySelector('.hub-sidebar [data-hub="picks"]').click();
 assert.equal(singlePanel.parentElement.id,'picks-showcase');
 assert.equal(topPanel.parentElement.id,'picks-showcase');
 assert.equal(singlePanel.querySelector('.bl-broadcast'),card);
 assert.equal(doc.querySelector('#picks-showcase').hidden,false);
 assert.equal(doc.querySelector('#app').hidden,true);
 assert.equal(singlePanel.hidden,false);assert.equal(topPanel.hidden,false);
 assert.match(singlePanel.querySelector('.bl-broadcast-action').textContent,/Scopri l’analisi/);
 singlePanel.querySelector('.bl-broadcast-action').click();
 assert.equal(doc.body.dataset.hubView,'single');
 assert.equal(doc.querySelector('#single-analysis-page').hidden,false);
 assert.equal(doc.querySelector('#picks-showcase').hidden,true);
 topPanel.querySelector('.bl-datalab-card').click();
 assert.equal(singleClicks,0);assert.equal(topClicks,1);
 assert.equal(doc.body.dataset.hubView,'stats');
 assert.equal(doc.querySelector('#app').hidden,false);
 assert.equal(doc.querySelector('#picks-showcase').hidden,true);
 assert.match(topPanel.textContent,/Top Player/);
 assert.doesNotMatch(topPanel.textContent,/Single Player/);
 doc.querySelector('.hub-mobile-bar [data-hub="home"]').click();
 assert.equal(singlePanel.parentElement,homeParent);
 assert.equal(topPanel.parentElement,homeParent);
 assert.equal(doc.querySelector('#picks-showcase').hidden,true);
 assert.equal(doc.querySelectorAll('.hub-single-section').length,1);
 assert.match(singlePanel.querySelector('.bl-broadcast-action').textContent,/Scopri l’analisi/);
 doc.querySelector('.hub-sidebar [data-hub="stats"]').click();
 assert.equal(singlePanel.hidden,true);assert.equal(topPanel.hidden,true);
});

test('an empty Top 5 does not repeat the Single as a ranked analysis',async()=>{
 const {doc}=setup();
 doc.querySelector('#picks').innerHTML='<section class="pick-group" aria-label="La scelta del Lab"><article class="pick-selection"><button class="pick-player-link">Only Single</button></article></section><section id="pick-giorno"><div class="pick-group-items"></div></section>';
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(doc.querySelectorAll('#hub-featured-list .bl-datalab-card').length,0);
 assert.match(doc.querySelector('#hub-featured-list').textContent,/Nessuna analisi/);
});

test('calendar opens analysis before a changed-day quote feed resolves',async()=>{
 const {window,doc}=setup();
 const date=doc.querySelector('#date');
 date.innerHTML='<option value="2026-11-02">2</option><option value="2026-11-03">3</option>';date.value='2026-11-02';
 let quoteChanges=0;date.addEventListener('change',()=>quoteChanges++);
 window.fetch=async url=>({ok:true,json:async()=>url.includes('/fixtures')?{games:[{away:'Boston Celtics',home:'Atlanta Hawks',upcoming:true,start_at:'2026-11-03T23:00:00Z'}]}:{fixtures:[]}});
 doc.querySelector('[data-hub="calendar"]').click();
 [...doc.querySelectorAll('#hub-calendar-dates button')].find(b=>b.getAttribute('aria-label')==='3 novembre 2026').click();
 await new Promise(r=>setImmediate(r));
 doc.querySelector('.hub-calendar-match').click();
 assert.equal(quoteChanges,1);
 assert.equal(date.value,'2026-11-03');
 assert.equal(doc.querySelector('#hub-match-detail').hidden,false);
 assert.ok(doc.body.classList.contains('hub-match-open'));
 assert.match(doc.querySelector('#hub-match-title').textContent,/Boston Celtics/);
 // A delayed feed for another day must not change the open fixture.
 window.document.dispatchEvent(new window.CustomEvent('basketlab:quotes-loaded',{detail:{date:'2026-11-02'}}));
 assert.match(doc.querySelector('#hub-match-title').textContent,/Boston Celtics/);
 doc.querySelector('[data-hub="home"]').click();
 window.document.dispatchEvent(new window.CustomEvent('basketlab:quotes-loaded',{detail:{date:'2026-11-03'}}));
 assert.equal(doc.body.dataset.hubView,'home');
 assert.ok(!doc.body.classList.contains('hub-match-open'));
});

test('SPA paths support direct links, navigation and browser Back',async()=>{
 const {window,doc}=setup('pronostici');
 assert.equal(doc.body.dataset.hubView,'picks');
 doc.querySelector('[data-hub="history"]').click();
 await new Promise(r=>setImmediate(r));
 assert.equal(window.location.pathname,'/archivio');
 doc.querySelector('[data-hub="home"]').click();
 await new Promise(r=>setImmediate(r));
 assert.equal(window.location.pathname,'/');
 window.history.back();
 await new Promise(r=>setTimeout(r,30));
 assert.equal(window.location.pathname,'/archivio');
 assert.equal(doc.body.dataset.hubView,'history');
 assert.equal(doc.querySelector('#extra-history').hidden,false);
});

test('direct match route opens without quote options and preserves date and teams',()=>{
 const {window,doc}=setup('analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks');
 assert.equal(doc.querySelector('#date').value,'2026-11-05');
 assert.ok(doc.body.classList.contains('hub-match-open'));
 assert.match(doc.querySelector('#hub-match-title').textContent,/Boston Celtics/);
 assert.equal(window.BasketLabRouter.read(window.location).date,'2026-11-05');
});

test('match request cache shares in-flight loads and retries incomplete histories',async()=>{
 const {window}=setup();
 let calls=0,release;
 const read=window.BasketLabMatchData(()=>{calls++;return new Promise(r=>release=()=>r({ok:true,json:async()=>({history_complete:false,teams:[]})}));});
 const first=read('2026-11-05',['A','B']),second=read('2026-11-05',['A','B']);
 assert.equal(calls,1);assert.equal(first,second);
 release();await first;
 const retry=read('2026-11-05',['A','B']);
 assert.equal(calls,2);release();await retry;
});

test('successful match data renders attack, defense and verified history without duplicate summaries',async()=>{
 const {window,doc}=setup('analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks');
 const team=(name,wins,points)=>({team:name,games:5,wins,losses:5-wins,avg_points:points,results:['2026-11-01','2026-11-02','2026-11-03'].map(date=>({date,scored:points,allowed:100,opponent:'Other'}))});
 window.fetch=async url=>({ok:true,json:async()=>url.includes('/match/form')?{teams:[team('Boston Celtics',4,110),team('Atlanta Hawks',2,100)],window_days:21,moneyline_odds:[1.8,2.1],h2h:[]}:{games:[]}});
 doc.querySelector('[data-match-tab="analysis"]').click();
 await new Promise(r=>setImmediate(r));
 assert.match(doc.querySelector('#hub-match-charts').textContent,/Media punti segnati/);
 assert.match(doc.querySelector('#hub-match-charts').textContent,/110/);
 assert.match(doc.querySelector('.sheet-comparison').textContent,/Media punti subiti/);
 assert.match(doc.querySelector('.sheet-comparison').textContent,/Differenza punti/);
 assert.equal(doc.querySelector('.hub-match-summary'),null);
 assert.match(doc.querySelector('#hub-match-h2h-chart').textContent,/Nessuno scontro diretto/);
 assert.equal(doc.querySelectorAll('#hub-match-insights article').length,3);
 assert.match(doc.querySelector('#hub-match-insights').textContent,/Le chiavi della partita/);
 assert.match(doc.querySelector('#hub-match-insights').textContent,/05\/11\/2026/);
});

test('invalid URL dates cannot crash calendar or open a match under a different day',()=>{
 const {window}=setup();
 for(const date of ['2026-99-99','2026-02-30','invalid']){
  const route=window.BasketLabRouter.read(new URL('https://basketlab.it/analisi-partita?data='+date+'&trasferta=Boston&casa=Atlanta'));
  assert.equal(route.date,'');assert.equal(route.match,'');
 }
 assert.equal(window.BasketLabRouter.read(new URL('https://basketlab.it/partite?data=2026-11-05')).date,'2026-11-05');
});

test('daily quote loading cannot hide the independent match analysis',()=>{
 const {window,doc}=setup('analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks');
 window.fetch=()=>new Promise(()=>{});
 doc.querySelector('[data-match-tab="analysis"]').click();
 const styles=doc.createElement('style');
 styles.textContent=fs.readFileSync(path.join(root,'web/style.css'),'utf8')+'\n'+fs.readFileSync(path.join(root,'web/hub.css'),'utf8');
 doc.head.append(styles);
 doc.querySelector('#app').classList.add('date-is-loading');
 assert.equal(window.getComputedStyle(doc.querySelector('#finder')).display,'block');
 assert.equal(window.getComputedStyle(doc.querySelector('#date-loading')).display,'none');
 assert.match(doc.querySelector('#hub-match-charts').textContent,/Caricamento/);
});

test('general quote route exits a match and browser Back restores its dedicated URL',async()=>{
 const {window,doc}=setup('analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks');
 doc.querySelector('.hub-sidebar [data-hub="finder"]').click();
 await new Promise(r=>setImmediate(r));
 assert.equal(window.location.pathname,'/analisi-quote');
 assert.ok(!doc.body.classList.contains('hub-match-open'));
 assert.equal(doc.querySelector('#hub-match-detail').hidden,true);
 window.history.back();await new Promise(r=>setTimeout(r,30));
 assert.equal(window.location.pathname,'/analisi-partita');
 assert.ok(doc.body.classList.contains('hub-match-open'));
 assert.equal(doc.querySelector('#hub-match-detail').hidden,false);
});

 test('leaving About hides its content on every primary destination',async()=>{
  const {window,doc}=setup();
  window.fetch=async()=>({ok:true,json:async()=>({games:[],articles:[]})});
  for(const destination of ['home','picks','stats','finder','calendar','news']){
   doc.querySelector('.hub-menu-drawer [data-hub="about"]').click();
   assert.equal(doc.querySelector('#extra-about').hidden,false);
   assert.equal(doc.querySelector('#app').hidden,true);
   doc.querySelector('.hub-menu-drawer [data-hub="'+destination+'"]').click();
   assert.equal(doc.body.dataset.hubView,destination);
   assert.equal(doc.querySelector('#extra-about').hidden,true,destination);
   assert.equal(doc.querySelector('#extra-history').hidden,true,destination);
   await new Promise(resolve=>window.queueMicrotask(resolve));
  }
 });

test('single analysis has one stable route and hides other page panels',async()=>{
 const {window,doc}=setup('analisi-singola');
 assert.equal(window.BasketLabRouter.url({view:'single'}),'/analisi-singola');
 assert.equal(doc.body.dataset.hubView,'single');
 assert.equal(doc.querySelector('#single-analysis-page').hidden,false);
 assert.equal(doc.querySelector('#extra-about').hidden,true);
 doc.querySelector('.hub-mobile-bar [data-hub="home"]').click();
 assert.equal(doc.querySelector('#single-analysis-page').hidden,true);
 await new Promise(resolve=>window.queueMicrotask(resolve));
});

test('match filter reset restores market, search, team and default odds',()=>{
 const {doc}=setup();
 doc.querySelector('[data-market="AST"]').click();
 doc.querySelector('#hub-match-search').value='Test';
 doc.querySelector('#hub-match-odd-min').value='1.70';
 doc.querySelector('#hub-match-odd-max').value='1.90';
 doc.querySelector('#hub-match-filter-reset').click();
 assert.equal(doc.querySelector('#hub-match-search').value,'');
 assert.equal(doc.querySelector('#hub-match-odd-min').value,'1.20');
 assert.equal(doc.querySelector('#hub-match-odd-max').value,'2.20');
 assert.equal(doc.querySelector('[data-market="PTS"]').getAttribute('aria-pressed'),'true');
 assert.equal(doc.querySelector('[data-market="AST"]').getAttribute('aria-pressed'),'false');
});

test('invalid match odds range reports an error rather than displaying unfiltered odds',()=>{
 const {window,doc}=setup();
 doc.body.classList.add('hub-match-open');
 window.BasketLabMatchRows=()=>[{Squadra:'BOS',Giocatore:'Test',Mercato:'PTS',Linea:10.5,Quota:1.8}];
 const render=window.BasketLabMatchPlayers(doc,()=>({activeMatch:'BOS - NYK',matchMarket:'PTS',matchTeamFilter:''}),s=>s,String);
 doc.querySelector('#hub-match-odd-min').value='2.50';
 render();
 assert.equal(doc.querySelector('#hub-match-filter-error').hidden,false);
 assert.equal(doc.querySelector('#hub-match-player-list').children.length,0);
 assert.equal(doc.querySelector('#hub-match-odd-min').getAttribute('aria-invalid'),'true');
 doc.querySelector('#hub-match-odd-min').value='1.20';
 render();
 assert.equal(doc.querySelector('#hub-match-filter-error').hidden,true);
 assert.equal(doc.querySelectorAll('.hub-match-player-card').length,1);
});


test('brand link returns to home and closes the menu from another view',()=>{
 const {doc}=setup();
 doc.querySelector('.hub-sidebar [data-hub="about"]').click();
 doc.querySelector('.hub-menu-toggle').click();
 const brand=doc.querySelector('.app-header a.brand');
 assert.equal(brand.getAttribute('href'),'/');
 brand.click();
 assert.equal(doc.body.dataset.hubView,'home');
 assert.equal(doc.querySelector('#extra-about').hidden,true);
 assert.equal(doc.querySelector('#hub-menu-drawer').hidden,true);
});

test('calendar, home and daily picks omit venue icons',async()=>{
 const {window,doc}=setup();
 await new Promise(r=>setImmediate(r));
 window.fetch=async()=>({ok:true,json:async()=>({games:[{away:'Boston Celtics',home:'Atlanta Hawks',upcoming:true,start_at:new Date(Date.now()+3600000).toISOString()}]})});
 const team=name=>'<span class="fixture-team"><span class="fixture-team-name"><span class="fixture-name-full">'+name+'</span></span></span>';
 doc.querySelector('#picks').innerHTML='<section class="pick-group" aria-label="La scelta del Lab"><article class="pick-selection"><button class="pick-player-link">Test Player</button><div class="pick-profile-info"><p>Atlanta Hawks</p></div><div class="pick-fixture" data-match="Atlanta Hawks - Boston Celtics">'+team('Atlanta Hawks')+team('Boston Celtics')+'</div></article></section>';
 await new Promise(r=>setImmediate(r));
 const sides=doc.querySelectorAll('.bl-game-team');
 assert.equal(sides.length,2);
 assert.equal(doc.querySelectorAll('.hub-single-section .bl-venue-icon, #hub-games-showcase .bl-venue-icon').length,0);
 doc.querySelector('.hub-sidebar [data-hub=calendar]').click();
 await new Promise(r=>setImmediate(r));
 const icons=doc.querySelectorAll('.hub-calendar-match .bl-venue-icon');
 assert.equal(icons.length,0);
 window.close();
});

test('missing single stays hidden on Home and explains availability in Pronostici',async()=>{
 const {doc}=setup();const picks=doc.querySelector('#picks');picks.innerHTML='<section class="pick-group" aria-label="La scelta del Lab"></section><section id="pick-giorno"></section>';
 await new Promise(r=>setImmediate(r));assert.equal(doc.querySelector('.hub-single-section').hidden,true);
 doc.querySelector('.hub-sidebar [data-hub=picks]').click();assert.equal(doc.querySelector('.hub-single-section').hidden,false);assert.match(doc.querySelector('.bl-picks-empty').textContent,/Nessuna scelta del giorno disponibile per oggi/);
 picks.innerHTML='<section class="pick-group" aria-label="La scelta del Lab"><article class="pick-selection"><button class="pick-player-link">Test Player</button></article></section>';
 await new Promise(r=>setImmediate(r));doc.querySelector('.hub-mobile-bar [data-hub=home]').click();assert.equal(doc.querySelector('.hub-single-section').hidden,false);
 picks.innerHTML='';await new Promise(r=>setImmediate(r));assert.equal(doc.querySelector('.hub-single-section').hidden,true);
});
test('NBA week keeps its days stable and highlights today without an Oggi shortcut',async()=>{
 const {window,doc}=setup();window.fetch=async()=>({ok:true,json:async()=>({games:[],fixtures:[]})});doc.querySelector('.hub-sidebar [data-hub=calendar]').click();
 const today=doc.querySelector('.hub-calendar-date.today');assert.equal(today.getAttribute('aria-current'),'date');
 const dates=()=>[...doc.querySelectorAll('.hub-calendar-date')].map(b=>b.getAttribute('aria-label'));
 const week=dates();doc.querySelectorAll('.hub-calendar-date')[0].click();assert.deepEqual(dates(),week);
 doc.querySelector('#hub-calendar-next').click();assert.notDeepEqual(dates(),week);
 assert.equal(doc.querySelector('#hub-calendar-today'),null);
 assert.match(doc.querySelector('#hub-calendar-compact-date').textContent,/^[a-z]+ \d{4}$/);
 const toggle=doc.querySelector('#hub-calendar-collapse-toggle');toggle.click();assert.equal(doc.querySelector('#hub-calendar-picker').hidden,false);
 doc.querySelector('#hub-calendar-month-grid .hub-month-day').click();assert.equal(doc.querySelector('#hub-calendar-picker').hidden,true);
 window.close();
});
test('completed game URL restores its boxscore and contextual back removes only the game parameter',async()=>{
 const {window,doc}=setup();await new Promise(r=>setImmediate(r));
 window.fetch=async url=>({ok:true,json:async()=>String(url).includes('boxscore')?{teams:[{team:'Boston Celtics',players:[{id:'22',name:'Alex Test',points:25}]}]}:{games:[{event_id:'123456',away:'Boston Celtics',home:'Atlanta Hawks',state:'post',upcoming:false,start_at:'2026-11-12T01:00:00Z',away_score:110,home_score:100}],fixtures:[]}});
 window.history.pushState(null,'','/nba?data=2026-11-12&partita=123456');window.dispatchEvent(new window.PopStateEvent('popstate'));
 for(let n=0;n<6;n++)await new Promise(r=>setImmediate(r));assert.equal(doc.querySelector('#hub-calendar-boxscore').hidden,false);assert.equal(doc.querySelector('.hub-boxscore-player-link').getAttribute('href'),'/giocatori/alex-test-22');assert.equal(new URLSearchParams(window.location.search).get('partita'),'123456');
 doc.querySelector('.hub-boxscore-back').click();await new Promise(r=>setImmediate(r));assert.equal(doc.querySelector('#hub-calendar-boxscore').hidden,true);assert.equal(new URLSearchParams(window.location.search).has('partita'),false);assert.equal(new URLSearchParams(window.location.search).get('data'),'2026-11-12');
});
test('team result returns to its team instead of the calendar and preserves origin in its URL',async()=>{
 const {window,doc}=setup();await new Promise(r=>setImmediate(r));
 const game={event_id:'123456',away:'Boston Celtics',home:'Atlanta Hawks',state:'post',upcoming:false,start_at:'2026-11-12T01:00:00Z',calendar_date:'2026-11-12',away_score:110,home_score:100};
 window.fetch=async url=>({ok:true,json:async()=>String(url).includes('/teams/2')?{team:{id:'2',name:'Boston Celtics',color:'008348'},upcoming:[],recent:[game]}:String(url).includes('/standings')?{conferences:[]}:String(url).includes('/roster')?{players:[]}:String(url).includes('boxscore')?{teams:[]}:{games:[game],fixtures:[]}});
 window.history.pushState(null,'','/squadre/boston-celtics-2');window.dispatchEvent(new window.PopStateEvent('popstate'));for(let n=0;n<6;n++)await new Promise(r=>setImmediate(r));
 doc.querySelector('#nba-team-recent button').click();for(let n=0;n<4;n++)await new Promise(r=>setImmediate(r));
 assert.equal(new URLSearchParams(window.location.search).get('squadra'),'boston-celtics-2');assert.match(doc.querySelector('.hub-boxscore-back').textContent,/Torna alla squadra/);assert.equal(doc.querySelector('.nba-tabs').hidden,false);
 doc.querySelector('.hub-boxscore-back').click();for(let n=0;n<4;n++)await new Promise(r=>setImmediate(r));assert.equal(window.location.pathname,'/squadre/boston-celtics-2');assert.match(doc.querySelector('#nba-team-hero').textContent,/Boston Celtics/);assert.equal(doc.querySelector('.nba-tabs').hidden,true);
 doc.querySelector('[data-nba-back]').click();for(let n=0;n<4;n++)await new Promise(r=>setImmediate(r));assert.equal(window.location.pathname,'/nba/classifica');assert.equal(doc.querySelector('.nba-tabs').hidden,false);
});

 test('team name navigation clears match state and browser Back restores its match URL',async()=>{
 const {window,doc}=setup('analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks');
 window.fetch=async()=>({ok:true,json:async()=>({conferences:[],players:[],team:{name:'Boston Celtics',color:'008348'},upcoming:[],recent:[],teams:[]})});
 const node=doc.createElement('span');node.className='hub-match-team';node.textContent='Boston Celtics';doc.querySelector('main').append(node);window.BasketLabTeamLinks.enhance(node);node.querySelector('a').click();await new Promise(r=>setImmediate(r));
 assert.equal(window.location.pathname,'/squadre/boston-celtics-2');assert.equal(doc.body.dataset.hubView,'calendar');assert.equal(doc.body.classList.contains('hub-match-open'),false);
 window.history.back();await new Promise(r=>setTimeout(r,25));assert.equal(window.location.pathname,'/analisi-partita');assert.equal(doc.body.classList.contains('hub-match-open'),true);
 });


test('Home and Pronostici share only single results with explicit settled denominator and preserve section order',async()=>{
 let calls=0;
 const {doc}=setup('',async url=>{if(String(url).includes('/api/history/performance')){calls++;return {ok:true,json:async()=>({success_pct:64.7,published:124,won:77,single:{success_pct:87.5,published:10,verified:8,won:7,lost:1,not_played:1,pending:1}})}}return {ok:true,json:async()=>({games:[]})};});
 await new Promise(r=>setImmediate(r));
 const results=doc.querySelector('.hub-performance');
 assert.equal(results.querySelectorAll('.bl-results-card').length,1);
 assert.equal(results.querySelector('h3'),null);
 assert.equal(results.querySelector('.bl-results-footer'),null);
 assert.match(results.textContent,/87,5%/);
 assert.doesNotMatch(results.textContent,/64,7|Le migliori|affidabilità/i);
 assert.equal(results.querySelector('.bl-results-heading'),null);
 assert.match(results.querySelector('h2').textContent,/Rendimento del Lab/);
 assert.equal(results.querySelector('[data-outcome=not-played] dd').textContent,'1');
 assert.equal(results.querySelector('[data-outcome=pending] dd').textContent,'1');
 const single=doc.querySelector('.hub-single-section'),games=doc.querySelector('.hub-games-section'),choices=doc.querySelector('.hub-featured'),news=doc.querySelector('#hub-nba-updates-panel');
 const before=(a,b)=>!!(a.compareDocumentPosition(b)&4);
 assert.ok(before(results,single)&&before(single,games)&&before(games,choices)&&before(choices,news));
 doc.querySelector('.hub-sidebar [data-hub=picks]').click();
 assert.equal(results.hidden,false);
 assert.equal(results.parentElement.id,'picks-showcase');
 assert.ok(before(single,results)&&before(results,choices)&&before(choices,doc.querySelector('.hub-picks-archive')));
 doc.querySelector('.hub-sidebar [data-hub=home]').click();
 assert.ok(before(results,single)&&before(games,choices));
 assert.equal(doc.querySelectorAll('.hub-performance').length,1);
 assert.equal(calls,1);
 assert.equal(results.querySelector('[data-hub=history]'),null);
 doc.querySelector('.hub-sidebar [data-hub=history]').click();
 assert.equal(doc.body.dataset.hubView,'history');
 assert.equal(results.hidden,true);
});


test('calendar displays only explicit Live, preserves score ordering and drops quote coverage requests',async()=>{
 const calls=[];
 const fixtures=[
  {event_id:'1',away:'Boston Celtics',home:'Atlanta Hawks',state:'post',upcoming:false,away_score:123,home_score:117},
  {event_id:'2',away:'Chicago Bulls',home:'Miami Heat',state:'in',upcoming:false,away_score:0,home_score:0},
  {event_id:'3',away:'Denver Nuggets',home:'Phoenix Suns',state:'pre',upcoming:true},
  {event_id:'4',away:'Dallas Mavericks',home:'Houston Rockets',state:'pre',upcoming:false,status:'Postponed'}
 ].map(game=>({...game,start_at:'2026-11-05T01:00:00Z',calendar_date:'2026-11-05'}));
 const {doc}=setup('nba?data=2026-11-05',async url=>{calls.push(String(url));return {ok:true,json:async()=>({games:fixtures})};});
 for(let n=0;n<4;n++)await new Promise(r=>setImmediate(r));
 const cards=doc.querySelectorAll('.hub-calendar-match');assert.equal(cards.length,4);
 assert.equal(doc.querySelectorAll('.hub-calendar-odds').length,0);
 assert.equal(doc.querySelectorAll('.hub-calendar-state').length,1);
 assert.equal(doc.querySelector('.hub-calendar-state').textContent,'Live');
 assert.deepEqual([...cards[0].querySelectorAll('.hub-score-value')].map(x=>x.textContent),['123','117']);
 assert.equal(cards[0].querySelector('.is-winner').textContent,'123');
 assert.deepEqual([...cards[1].querySelectorAll('.hub-score-value')].map(x=>x.textContent),['0','0']);
 assert.equal(cards[2].querySelector('.hub-calendar-final-score'),null);
 assert.equal(cards[3].querySelector('.hub-calendar-state'),null);
 assert.ok(!calls.some(url=>url.includes('quote-coverage')));
 assert.equal(doc.querySelector('.hub-home-banner').hidden,true);
});


test('live calendar polls scores in place, catches up on visibility and updates its match action',async()=>{
 let tick,clock=0,hidden=false,calls=0;
 let game={event_id:'123456',away:'Boston Celtics',home:'Atlanta Hawks',state:'in',upcoming:false,start_at:'2026-11-18T00:00:00Z',away_score:20,home_score:18,period:1,display_clock:'6:00'};
 const {window:w,doc}=setup('nba?data=2026-11-18',async()=>{calls++;return {ok:true,json:async()=>{if(calls===1)clock=5;return {games:[{...game}]};}};},w=>{
  Object.defineProperty(w.document,'hidden',{get:()=>hidden});w.Date.now=()=>clock;
  w.setInterval=(fn,ms)=>{if(ms===30000)tick=fn;return 1;};
 });
 await new Promise(r=>setImmediate(r));
 const row=doc.querySelector('.hub-calendar-match'),dateButton=doc.querySelector('.hub-calendar-date.active');row.focus();
 assert.match(row.textContent,/20/);game={...game,away_score:24,display_clock:'5:30'};clock=30000;tick();
 await new Promise(r=>setImmediate(r));
 assert.equal(doc.querySelector('.hub-calendar-match'),row);assert.equal(doc.activeElement,row);assert.equal(doc.querySelector('.hub-calendar-date.active'),dateButton);
 assert.match(row.querySelector('.hub-calendar-final-score').textContent,/24/);assert.match(row.querySelector('.hub-calendar-time').textContent,/Q1 · 5:30/);
 const before=calls;hidden=true;clock=62000;tick();await new Promise(r=>setImmediate(r));assert.equal(calls,before);
 hidden=false;game={...game,state:'post',away_score:100,home_score:90};doc.dispatchEvent(new w.Event('visibilitychange'));await new Promise(r=>setImmediate(r));
 assert.equal(row.dataset.state,'post');assert.match(row.querySelector('.hub-calendar-final-score').textContent,/100/);
});

test('live boxscore refreshes header, totals and players without closing or losing scroll, then stops at final',async()=>{
 let tick,hidden=false,boxCalls=0,resolvePending;
 const game={event_id:'123456',away:'Boston Celtics',home:'Atlanta Hawks',state:'in',upcoming:false,start_at:'2026-11-18T00:00:00Z',away_score:20,home_score:18};
 let data={state:'in',game:{away_score:24,home_score:22,period:1,display_clock:'4:00'},quarters:[{label:'Q1',away:24,home:22}],teams:[{team:'Boston Celtics',players:[{id:'22',name:'Alex Test',points:10}]}]};
 let delayed=false,failed=false;
 const {window:w,doc}=setup('nba?data=2026-11-18&partita=123456',async url=>{
  if(String(url).includes('boxscore')){boxCalls++;if(delayed)return new Promise(r=>{resolvePending=r;});if(failed)throw Error('offline');return {ok:true,json:async()=>data};}
  return {ok:true,json:async()=>({games:[game]})};
 },w=>{Object.defineProperty(w.document,'hidden',{get:()=>hidden});w.setInterval=(fn,ms)=>{if(ms===30000)tick=fn;return 1;};});
 for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));
 const panel=doc.querySelector('#hub-calendar-boxscore'),back=panel.querySelector('.hub-boxscore-back');
 assert.equal(panel.hidden,false);assert.equal(panel.querySelector('.hub-boxscore-headline').textContent,'24 – 22');
 const scroll=panel.querySelector('.hub-boxscore-scroll');scroll.scrollLeft=87;panel.querySelector('.hub-boxscore-player-link').focus();
 data={...data,game:{away_score:30,home_score:26,period:2,display_clock:'10:00'},teams:[{team:'Boston Celtics',players:[{id:'22',name:'Alex Test',points:16}]}]};
 delayed=true;tick();tick();assert.equal(boxCalls,2);assert.equal(panel.querySelector('.hub-boxscore-back'),back);assert.equal(panel.querySelector('.hub-boxscore-headline').textContent,'24 – 22');
 resolvePending({ok:true,json:async()=>data});for(let i=0;i<3;i++)await new Promise(r=>setImmediate(r));delayed=false;
 assert.equal(panel.querySelector('.hub-boxscore-headline').textContent,'30 – 26');assert.equal(panel.querySelector('.hub-boxscore-scroll').scrollLeft,87);assert.equal(doc.activeElement.getAttribute('href'),'/giocatori/alex-test-22');
 assert.match(panel.querySelector('.hub-boxscore-table').textContent,/16/);assert.match(panel.querySelector('.hub-boxscore-period-table').textContent,/30/);
 failed=true;tick();await new Promise(r=>setImmediate(r));assert.equal(panel.querySelector('.hub-boxscore-headline').textContent,'30 – 26');assert.match(panel.textContent,/Aggiornamento in attesa/);failed=false;
 hidden=true;const before=boxCalls;tick();assert.equal(boxCalls,before);hidden=false;
 data={...data,state:'post',game:{away_score:110,home_score:100,period:4,display_clock:'0:00'}};
 doc.dispatchEvent(new w.Event('visibilitychange'));for(let i=0;i<3;i++)await new Promise(r=>setImmediate(r));
 assert.equal(panel.querySelector('.hub-boxscore-headline').textContent,'110 – 100');assert.equal(panel.querySelector('.hub-boxscore-live-status').textContent,'Finale');
 const finalCalls=boxCalls;tick();assert.equal(boxCalls,finalCalls);
});
