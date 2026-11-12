const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const script=fs.readFileSync('web/modules/nba-hub.js','utf8'),router=fs.readFileSync('web/modules/router.js','utf8');
const standings={conferences:[{name:'Eastern Conference',season:'2026-27',teams:[{id:'2',name:'Boston Celtics',rank:1,wins:10,losses:2,win_percent:10/12,points_for:115,points_against:109}]},{name:'Western Conference',season:'2026-27',teams:[]}]};
const settle=()=>new Promise(r=>setTimeout(r,10));
test('standings, team links, independent roster failure and calendar return',async()=>{
 const dom=new JSDOM('<section id="hub-calendar"><div id="existing-calendar">Calendar</div></section>',{url:'https://basketlab.it/nba/classifica',runScripts:'outside-only'}),w=dom.window;w.scrollTo=()=>{};
 w.fetch=async url=>({ok:!url.includes('roster'),json:async()=>url.includes('standings')?standings:{team:{id:'2',name:'Boston Celtics',color:'008348',record:'10-2',season:'2026-27'},upcoming:[],recent:[]}});
 w.eval(script);let selects=0,calendars=0;w.BasketLabNBA.init({select(){selects++},calendar(){calendars++}});w.BasketLabNBA.apply({nbaTab:'standings'});await w.BasketLabNBA.show();
 assert.equal(w.document.querySelector('.nba-section-heading'),null);assert.match(w.document.querySelector('.nba-standings').textContent,/Boston Celtics/);assert.equal(w.document.querySelector('[data-nba-team]').getAttribute('href'),'/squadre/boston-celtics-2');
 w.document.querySelector('[data-nba-team]').click();await settle();assert.equal(w.document.querySelector('.nba-tabs').hidden,true);assert.match(w.document.querySelector('h1').textContent,/Boston/);assert.match(w.document.querySelector('#nba-team-roster').textContent,/temporaneamente/);assert.match(w.document.querySelector('#nba-team-next').textContent,/Nessuna prossima/);
 w.document.querySelector('[data-nba-tab=calendar]').click();assert.equal(w.document.querySelector('#nba-calendar-content').hidden,false);assert.equal(w.document.querySelector('.nba-tabs').hidden,false);assert.equal(calendars,1);assert.equal(selects,2);dom.window.close();
});
test('roster contains real player URL and team route round trips',async()=>{
 const dom=new JSDOM('<section id="hub-calendar"></section>',{url:'https://basketlab.it/squadre/boston-celtics-2',runScripts:'outside-only'}),w=dom.window;w.scrollTo=()=>{};
 w.fetch=async url=>({ok:true,json:async()=>url.includes('roster')?{players:[{id:'42',name:'Álex Test',position:'G',jersey:'7'}]}:url.includes('standings')?standings:{team:{name:'Boston Celtics',color:'008348'},upcoming:[],recent:[]}});
 w.eval(router);w.eval(script);const route=w.BasketLabRouter.read(w.location);assert.equal(route.view,'calendar');assert.equal(route.team,'boston-celtics-2');assert.equal(w.BasketLabRouter.url({...route,date:'2026-11-12'}),'/squadre/boston-celtics-2');w.BasketLabNBA.apply(route);await w.BasketLabNBA.show();assert.equal(w.document.querySelector('.nba-player').getAttribute('href'),'/giocatori/alex-test-42');assert.equal(w.BasketLabRouter.read(new URL('https://basketlab.it/partite')).view,'calendar');dom.window.close();
});
