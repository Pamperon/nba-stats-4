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
