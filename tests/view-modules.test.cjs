const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
test('boxscore module preserves verified quarters, totals and player values',()=>{
 const dom=new JSDOM('<div id="panel"></div>',{runScripts:'outside-only'});
 try{
  dom.window.eval(fs.readFileSync('web/modules/boxscore-view.js','utf8'));
  const panel=dom.window.document.getElementById('panel');
  dom.window.BasketLabBoxscoreView(dom.window.document,panel,{away:'A',home:'B',away_score:110,home_score:100},{quarters:[{label:'Q1',away:30,home:20}],teams:[{team:'A',players:[{name:'Player',minutes:'31',points:22,rebounds:7,assists:4}]}]});
  assert.deepEqual([...panel.querySelector('.hub-boxscore-period-table tbody tr').children].map(x=>x.textContent),['A','30','110']);
  assert.deepEqual([...panel.querySelector('.hub-boxscore-table tbody tr').children].map(x=>x.textContent),['Player','31','22','7','4']);
 }finally{dom.window.close();}
});
test('calendar module shares requests and retries failures instead of caching them',async()=>{
 const dom=new JSDOM('',{runScripts:'outside-only'});
 try{
  dom.window.eval(fs.readFileSync('web/modules/calendar-data.js','utf8'));
  let calls=0;
  const read=dom.window.BasketLabCalendarData(async()=>{calls++;if(calls===1)throw Error('offline');return {ok:true,json:async()=>({games:[{upcoming:true,start_at:'2099-01-01T00:00:00Z'}]})};});
  await assert.rejects(read('2026-11-05'));
  const a=read('2026-11-05'),b=read('2026-11-05');
  assert.equal(calls,2);assert.deepEqual(await a,await b);
 }finally{dom.window.close();}
});
test('boxscore players link by ESPN identity without inventing missing identities',()=>{
 const dom=new JSDOM('<div id="panel"></div>',{url:'https://basketlab.it/nba',runScripts:'outside-only'}),w=dom.window;
 try{w.eval(fs.readFileSync('web/modules/boxscore-view.js','utf8'));const panel=w.document.getElementById('panel');w.BasketLabBoxscoreView(w.document,panel,{}, {teams:[{team:'A',players:[{id:'22',name:'Álex Test',points:0},{name:'Missing Identity',points:5}]}]});assert.equal(panel.querySelector('a').getAttribute('href'),'/giocatori/alex-test-22');assert.equal(panel.querySelectorAll('a').length,1);assert.match(panel.textContent,/Missing Identity/);assert.match(panel.querySelector('a').getAttribute('aria-label'),/Statistiche/);}finally{w.close();}
});
test('boxscore sorts numbers and minutes, keeps missing last and restores event/team sort on refresh',()=>{
 const dom=new JSDOM('<div id="panel"></div>',{runScripts:'outside-only'}),w=dom.window;
 try{
  w.eval(fs.readFileSync('web/modules/boxscore-view.js','utf8'));const panel=w.document.getElementById('panel');
  const game={event_id:'123',away:'A',home:'B'},data={teams:[{team:'A',players:[{name:'Ten',points:'10',minutes:'9:59'},{name:'Two',points:'2',minutes:'10:01'},{name:'Missing',points:'—',minutes:'—'}]}]};
  const names=()=>[...panel.querySelectorAll('.hub-boxscore-table tbody tr')].map(row=>row.firstChild.textContent);
  w.BasketLabBoxscoreView(w.document,panel,game,data);
  panel.querySelector('[data-boxscore-sort=points]').click();assert.deepEqual(names(),['Ten','Two','Missing']);
  panel.querySelector('[data-boxscore-sort=points]').click();assert.deepEqual(names(),['Two','Ten','Missing']);
  assert.equal(panel.querySelectorAll('th[aria-sort=ascending]').length,1);
  panel.replaceChildren();w.BasketLabBoxscoreView(w.document,panel,game,data);assert.deepEqual(names(),['Two','Ten','Missing']);
  panel.querySelector('[data-boxscore-sort=minutes]').click();assert.deepEqual(names(),['Two','Ten','Missing']);
  panel.replaceChildren();w.BasketLabBoxscoreView(w.document,panel,{...game,event_id:'456'},data);assert.deepEqual(names(),['Ten','Two','Missing']);
 }finally{w.close();}
});
test('prematch shows missing statistics as unavailable and H2H scores in their original team order',()=>{
 const dom=new JSDOM('<section id="hub-match-analysis"><div id="hub-match-charts"></div><section id="hub-match-h2h-chart"></section></section>',{runScripts:'outside-only'}),w=dom.window;
 try{
  w.eval(fs.readFileSync('web/modules/match-charts.js','utf8'));
  const charts=w.BasketLabMatchCharts(w.document,{},String);
  charts.renderMatchCharts(['A','B'],{games:0,wins:0,losses:0,avg_points:null,results:[]},{games:1,wins:1,losses:0,avg_points:110,results:[{scored:110,allowed:100}]},21,null);
  const rows=w.document.querySelectorAll('.sheet-comparison-row');assert.equal(rows[1].firstChild.textContent,'—');assert.equal(rows[2].firstChild.textContent,'—');assert.equal(rows[3].lastChild.textContent,'10');
  charts.renderMatchH2H(['A','B'],[{date:'2026-11-01',teams:['B','A'],scores:[110,100]}],21);
  const result=w.document.querySelector('.sheet-h2h-result');assert.equal(result.textContent,'01/11/2026B110A100');
 }finally{w.close();}
});
test('game player panel uses loaded stats, updates in place and restores focus after row replacement',()=>{
 const dom=new JSDOM('<div id="panel"></div>',{url:'https://basketlab.it/nba?partita=123',runScripts:'outside-only'}),w=dom.window;
 try{
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  w.eval(fs.readFileSync('web/modules/boxscore-view.js','utf8'));
  const panel=w.document.getElementById('panel'),game={event_id:'123',away:'A',home:'B',state:'in',period:2,display_clock:'5:00'};
  const data=points=>({teams:[{team:'A',players:[{id:'22',name:'Alex Test',minutes:'20',points,rebounds:7,assists:4}]}]});
  w.BasketLabBoxscoreView(w.document,panel,game,data(10));const link=panel.querySelector('.hub-boxscore-player-link');
  link.dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true}));const drawer=w.document.querySelector('dialog');
  assert.equal(drawer.open,true);assert.equal(drawer.querySelector('[data-game-player-stat=points]').textContent,'10');assert.match(drawer.textContent,/Live · Q2/);assert.equal(w.location.search,'?partita=123');
  drawer.querySelector('img').dispatchEvent(new w.Event('error'));assert.equal(drawer.querySelector('img').hidden,true);assert.equal(drawer.querySelector('.bl-game-player-initials').textContent,'AT');
  const close=drawer.querySelector('button');close.focus();panel.replaceChildren();w.BasketLabBoxscoreView(w.document,panel,game,data(16));
  assert.equal(drawer.open,true);assert.equal(drawer.querySelector('[data-game-player-stat=points]').textContent,'16');assert.equal(w.document.activeElement,close);assert.equal(drawer.querySelector('.bl-game-player-profile').getAttribute('href'),'/giocatori/alex-test-22');
  close.click();assert.equal(drawer.open,false);assert.equal(w.document.documentElement.classList.contains('bl-game-player-open'),false);assert.equal(w.document.activeElement,panel.querySelector('.hub-boxscore-player-link'));
  panel.querySelector('.hub-boxscore-player-link').click();w.document.dispatchEvent(new w.CustomEvent('basketlab:view',{detail:{view:'home'}}));assert.equal(drawer.open,false);
 }finally{w.close();}
});
test('game player panel preserves native modified links and never treats missing stats as zero',()=>{
 const dom=new JSDOM('<div id="panel"></div>',{url:'https://basketlab.it/nba',runScripts:'outside-only'}),w=dom.window;
 try{
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  w.eval(fs.readFileSync('web/modules/boxscore-view.js','utf8'));const panel=w.document.getElementById('panel');
  w.BasketLabBoxscoreView(w.document,panel,{event_id:'123',state:'post'},{teams:[{team:'A',players:[{id:'22',name:'Alex Test',points:null,minutes:'—'}]}]});
  const link=panel.querySelector('.hub-boxscore-player-link'),event=new w.MouseEvent('click',{ctrlKey:true,cancelable:true});link.dispatchEvent(event);assert.equal(event.defaultPrevented,false);assert.equal(w.document.querySelector('dialog'),null);
  link.click();const drawer=w.document.querySelector('dialog');assert.equal(drawer.querySelector('[data-game-player-stat=points]').textContent,'—');assert.equal(drawer.querySelector('.bl-game-player-unavailable').hidden,false);assert.match(drawer.textContent,/Finale/);
  panel.replaceChildren();w.BasketLabBoxscoreView(w.document,panel,{event_id:'456'},{teams:[]});assert.equal(drawer.open,false);
 }finally{w.close();}
});
