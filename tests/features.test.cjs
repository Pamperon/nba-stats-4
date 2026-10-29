/* Footer information pages and daily archive integration, without network. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const response=value=>({ok:true,json:async()=>value});
function app(fetch,mobile=false,hash=''){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'web/index.html'),'utf8'),{url:'https://basket.invalid/'+hash,runScripts:'outside-only',pretendToBeVisual:true});
 dom.window.fetch=fetch;dom.window.matchMedia=()=>typeof mobile==='object'?mobile:({matches:mobile});dom.window.scrollTo=()=>{};
 dom.window.localStorage.setItem('basketlab:favorites:v1','[{"id":"123","name":"Old favorite"}]');
 dom.window.localStorage.setItem('unrelated-data','keep');
 for(const file of ['app.js','features.js'])dom.window.eval(fs.readFileSync(path.join(root,'web',file),'utf8'));
 return dom;
}
function base(url){
 if(url==='/api/saved/dates')return {dates:[{date:'2099-01-01'}],default_date:'2099-01-01'};
 if(url.startsWith('/api/saved/status'))return {state:'done',last_saved:null};
 if(url.startsWith('/api/saved/latest'))return {date:'2099-01-01',results:[]};
 return {};
}
const ticket=(name,price=1.74,status='won')=>({status,combined_odds:price,legs:[{Giocatore:name,Partita:'A - B',Scelta:'Over',Linea:19.5,Mercato:'PTS',Quota:price,actual:status==='won'?22:null,win:status==='won'?true:null}]});

test('only archive and about links remain, in the footer rather than the main navigation',async()=>{
 const dom=app(async url=>response(base(url)));
 try{
  await tick();const d=dom.window.document;
  assert.equal(d.querySelector('.utility-nav'),null);
  assert.equal(d.querySelectorAll('footer [data-extra]').length,2);
  assert.equal(d.querySelectorAll('[data-extra="favorites"],[data-extra="movements"],#favorite-player,#finder-favorites,#history-version').length,0);
  assert.equal(dom.window.localStorage.getItem('basketlab:favorites:v1'),null);
  assert.equal(dom.window.localStorage.getItem('unrelated-data'),'keep');
  d.querySelector('footer [data-extra="about"]').click();
  assert.equal(d.getElementById('app').hidden,true);
  assert.equal(d.getElementById('extra-about').hidden,false);
  assert.match(d.getElementById('extra-about').textContent,/14:30/);
  d.querySelector('#extra-about [data-return-site]').click();
  assert.equal(d.getElementById('app').hidden,false);
  assert.equal(d.getElementById('extra-about').hidden,true);
 }finally{dom.window.close();}
});

test('archive displays all distinct daily tickets without a scan selector or invented combinations',async()=>{
 const calls=[];
 const dom=app(async(url,options={})=>{
  calls.push({url,method:options.method||'GET'});
  if(url==='/api/history/dates')return response({dates:[{date:'2026-10-27'}]});
  if(url.startsWith('/api/history?'))return response({date:'2026-10-27',groups:{Singola:[ticket('Original Player'),ticket('Other Player',1.8,'unresolved')],Doppia:[],Tripla:[]}});
  return response(base(url));
 });
 try{
  await tick();const d=dom.window.document;d.querySelector('footer [data-extra="history"]').click();await tick();await tick();
  assert.match(d.getElementById('history-tickets').textContent,/Original Player/);
  assert.match(d.getElementById('history-tickets').textContent,/Other Player/);
  assert.match(d.getElementById('history-tickets').textContent,/1,74/);
  assert.equal(d.querySelectorAll('.history-ticket').length,2);
  assert.equal(d.querySelectorAll('#extra-history select').length,1);
  assert.match(d.getElementById('history-status').textContent,/2 pronostici distinti/);
  assert.ok(calls.every(call=>call.method==='GET'&&!call.url.startsWith('/api/odds/')));
 }finally{dom.window.close();}
});

test('missing archive and request errors have retryable empty states',async()=>{
 for(const failed of [false,true]){
  const dom=app(async url=>url==='/api/history/dates'?(failed?{ok:false,status:503}:response({dates:[]})):response(base(url)));
  try{
   await tick();const d=dom.window.document;d.querySelector('footer [data-extra="history"]').click();await tick();await tick();
   assert.match(d.getElementById('history-status').textContent,failed?/temporaneamente non disponibile/:/Non ci sono ancora/);
   assert.equal(d.getElementById('history-tickets').children.length,0);
  }finally{dom.window.close();}
 }
});

test('archive names are escaped and a direct footer-page URL opens the correct page',async()=>{
 const dom=app(async url=>response(url==='/api/history/dates'?{dates:[{date:'2026-10-27'}]}:url.startsWith('/api/history?')?{date:'2026-10-27',groups:{Singola:[ticket('<img src=x onerror=alert(1)>')]}}:base(url)),false,'#archivio');
 try{
  await tick();await tick();const d=dom.window.document;
  assert.equal(d.getElementById('extra-history').hidden,false);
  assert.equal(d.querySelector('#history-tickets img'),null);
  assert.match(d.getElementById('history-tickets').textContent,/<img/);
 }finally{dom.window.close();}
});

test('mobile quote pagination and reset remain available after removing favorites',async()=>{
 const rows=Array.from({length:250},(_,i)=>({Giocatore:'Player '+i,'ESPN ID':String(100+i),Squadra:'A',Mercato:'PTS',Linea:9.5,Quota:1.8,'Stato analisi':'Valutabile (stima empirica)','Prob. stimata %':80}));
 const dom=app(async url=>response(url.startsWith('/api/saved/latest')?{date:'2099-01-01',results:rows}:base(url)),true);
 try{
  await tick();const d=dom.window.document;
  assert.equal(d.querySelectorAll('.finder-card').length,100);
  d.getElementById('finder-more').click();assert.equal(d.querySelectorAll('.finder-card').length,200);
  d.getElementById('finder-search').value='Player 249';d.getElementById('finder-search').dispatchEvent(new dom.window.Event('input'));
  assert.equal(d.querySelectorAll('.finder-card').length,1);
  d.getElementById('finder-reset').click();assert.equal(d.querySelectorAll('.finder-card').length,100);
 }finally{dom.window.close();}
});

test('loading more quotes preserves expanded details and moves focus to the added batch',async()=>{
 const rows=Array.from({length:350},(_,i)=>({Giocatore:'Player '+i,Squadra:'A',Mercato:'PTS',Linea:9.5,Quota:1.8,'Stato analisi':'Valutabile (stima empirica)','Prob. stimata %':80}));
 const calls=[];
 const dom=app(async url=>{calls.push(url);return response(url.startsWith('/api/saved/latest')?{date:'2099-01-01',results:rows}:base(url));},true);
 try{
  await tick();const d=dom.window.document;
  d.querySelector('[data-tab="finder"]').click();
  const first=d.querySelector('.finder-card');
  first.querySelector('.finder-details-toggle').click();
  const before=calls.length;
  d.getElementById('finder-more').click();
  assert.equal(d.querySelector('.finder-card'),first);
  assert.equal(first.querySelector('.finder-extra').hidden,false);
  assert.equal(first.querySelector('.finder-details-toggle').getAttribute('aria-expanded'),'true');
  assert.equal(d.activeElement,d.querySelectorAll('.finder-card')[100].querySelector('.finder-player'));
  assert.equal(d.querySelectorAll('.finder-card').length,200);
  assert.equal(d.querySelectorAll('#rows tr').length,200);
  assert.equal(calls.length,before);
  d.getElementById('finder-search').value='Player';
  d.getElementById('finder-search').dispatchEvent(new dom.window.Event('input'));
  assert.equal(d.querySelectorAll('.finder-card').length,100);
 }finally{dom.window.close();}
});

test('switching between desktop and mobile reuses saved quotes with the correct batch size',async()=>{
 let changed;const media={matches:true,addEventListener:(event,fn)=>{assert.equal(event,'change');changed=fn;}};
 const rows=Array.from({length:550},(_,i)=>({Giocatore:'Player '+i,Squadra:'A',Mercato:'PTS',Linea:9.5,Quota:1.8,'Stato analisi':'Valutabile (stima empirica)','Prob. stimata %':80}));
 const calls=[];
 const dom=app(async url=>{calls.push(url);return response(url.startsWith('/api/saved/latest')?{date:'2099-01-01',results:rows}:base(url));},media);
 try{
  await tick();const d=dom.window.document,before=calls.length;
  assert.equal(d.querySelectorAll('.finder-card').length,100);
  media.matches=false;changed();
  assert.equal(d.querySelectorAll('#rows tr').length,500);
  media.matches=true;changed();
  assert.equal(d.querySelectorAll('.finder-card').length,100);
  assert.equal(calls.length,before);
 }finally{dom.window.close();}
});

const statsPayload=url=>url==='/api/players/teams'?{teams:[{id:'1',name:'Boston Celtics'},{id:'2',name:'Miami Heat'}]}:url.startsWith('/api/players/roster')?{players:[{id:url.endsWith('2')?'22':'11',name:url.endsWith('2')?'José Player':'First Player'}]}:url.startsWith('/api/players/log?')?{games:[]}:base(url);
const quoteRow=(name,match)=>({Giocatore:name,'ESPN ID':'11',Squadra:'Boston Celtics',Partita:match,Mercato:'PTS',Scelta:'Over',Linea:9.5,Quota:1.8,'Stato analisi':'Valutabile (stima empirica)','Prob. stimata %':80});

test('fixture filter combines with player and market search without changing forecasts or requesting data',async()=>{
 const rows=[quoteRow('First Player','Boston Celtics - Miami Heat'),quoteRow('Other Player','A < B - C')],calls=[];let returnedRows=rows;
 const dom=app(async url=>{calls.push(url);return response(url.startsWith('/api/saved/latest')?{date:'2099-01-01',results:returnedRows}:base(url));},true);
 try{
  await tick();const d=dom.window.document,picks=d.getElementById('picks').innerHTML,before=calls.length;
  const filter=d.getElementById('finder-fixture');assert.equal(filter.options.length,3);assert.equal(filter.options[1].textContent,'A < B - C');
  filter.value='Boston Celtics - Miami Heat';filter.dispatchEvent(new dom.window.Event('change'));
  assert.equal(d.querySelectorAll('.finder-card').length,1);assert.match(d.querySelector('.finder-card').textContent,/First Player/);
  d.getElementById('finder-search').value='Other';d.getElementById('finder-search').dispatchEvent(new dom.window.Event('input'));
  assert.equal(d.querySelectorAll('.finder-card').length,0);
  assert.equal(d.getElementById('picks').innerHTML,picks);assert.equal(calls.length,before);
  d.getElementById('finder-reset').click();assert.equal(filter.value,'');assert.equal(d.querySelectorAll('.finder-card').length,2);
  filter.value='A < B - C';returnedRows=[];d.getElementById('date').dispatchEvent(new dom.window.Event('change'));await tick();await tick();assert.equal(filter.value,'');assert.equal(filter.options.length,1);
 }finally{dom.window.close();}
});

test('direct NBA search loads its directory once, ignores accents and selects the exact player and team',async()=>{
 const calls=[];let release;
 const dom=app(async url=>{
  calls.push(url);
  if(url==='/api/players/directory')return new Promise(resolve=>{release=()=>resolve(response({players:[{id:'11',name:'First Player',team_id:'1',team:'Boston Celtics'},{id:'22',name:'José Player',team_id:'2',team:'Miami Heat'}]}));});
  return response(statsPayload(url));
 });
 try{
  await tick();const w=dom.window,d=w.document;assert.equal(calls.includes('/api/players/directory'),false);
  d.getElementById('area-stats').click();await tick();await tick();
  const input=d.getElementById('player-search');
  d.getElementById('player-search-activate').click();input.value='jo';input.dispatchEvent(new w.Event('input'));input.value='PLAYER jose';input.dispatchEvent(new w.Event('input'));
  assert.equal(calls.filter(url=>url==='/api/players/directory').length,1);release();await tick();await tick();
  const results=d.querySelectorAll('[data-player-result]');assert.equal(results.length,1);assert.match(results[0].textContent,/José PlayerMiami Heat/);
  results[0].click();await tick();await tick();await tick();
  assert.equal(d.getElementById('team').value,'2');assert.equal(d.getElementById('playername').value,'22');
  assert.equal(d.getElementById('player-search-results').hidden,true);
  d.getElementById('player-search-activate').click();input.value='Jose';input.dispatchEvent(new w.Event('input'));await tick();assert.equal(calls.filter(url=>url==='/api/players/directory').length,1);
  assert.ok(calls.every(url=>!url.includes('odds')&&!url.startsWith('/api/scan')));
 }finally{dom.window.close();}
});

test('player search failures can retry and old results cannot overwrite a cleared query',async()=>{
 let failed=true,release;
 const dom=app(async url=>url==='/api/players/directory'?(failed?{ok:false,status:503}:new Promise(resolve=>{release=()=>resolve(response({players:[{id:'11',name:'First Player',team:'Boston Celtics'}]}));})):response(statsPayload(url)));
 try{
  await tick();const w=dom.window,d=w.document,input=d.getElementById('player-search');
  d.getElementById('player-search-activate').click();input.value='First';input.dispatchEvent(new w.Event('input'));await tick();await tick();
  assert.match(d.getElementById('player-search-status').textContent,/temporaneamente non disponibile/);
  failed=false;d.querySelector('#player-search-results button').click();
  input.value='';input.dispatchEvent(new w.Event('input'));release();await tick();await tick();
  assert.equal(d.querySelectorAll('[data-player-result]').length,0);assert.equal(d.querySelectorAll('[data-player-result]').length,0);
 }finally{dom.window.close();}
});

test('returning from statistics restores quote position, filters, loaded batches and expanded details',async()=>{
 const match='Boston Celtics - Miami Heat',rows=Array.from({length:230},()=>quoteRow('First Player',match));
 const dom=app(async url=>response(url.startsWith('/api/saved/latest')?{date:'2099-01-01',results:rows,season:'2026-27'}:statsPayload(url)),true);
 try{
  await tick();const w=dom.window,d=w.document,moves=[];
  Object.defineProperty(w,'scrollY',{value:0,writable:true});w.scrollTo=options=>{moves.push(options.top);w.scrollY=options.top;};
  d.querySelector('[data-tab=finder]').click();
  d.getElementById('finder-fixture').value=match;d.getElementById('finder-fixture').dispatchEvent(new w.Event('change'));
  d.getElementById('finder-search').value='First';d.getElementById('finder-search').dispatchEvent(new w.Event('input'));
  d.getElementById('finder-more').click();
  const first=d.querySelector('.finder-card');first.querySelector('.finder-details-toggle').click();
  d.getElementById('finder-scroll').scrollLeft=120;w.scrollY=1234;
  first.querySelector('.finder-player').click();await tick();await tick();
  assert.equal(w.scrollY,0);d.getElementById('back-to-picks').click();await new Promise(resolve=>setTimeout(resolve,35));
  assert.equal(moves.at(-1),1234);assert.equal(d.getElementById('finder-scroll').scrollLeft,120);
  assert.equal(d.getElementById('finder-fixture').value,match);assert.equal(d.getElementById('finder-search').value,'First');
  assert.equal(d.querySelectorAll('.finder-card').length,200);assert.equal(first.querySelector('.finder-extra').hidden,false);
  w.scrollY=1600;d.getElementById('area-stats').click();await tick();d.getElementById('area-quotes').click();await new Promise(resolve=>setTimeout(resolve,35));assert.equal(moves.at(-1),1600);
 }finally{dom.window.close();}
});

test('the existing player field supports both team dropdown and typing without a separate search panel',async()=>{
 const calls=[];
 const dom=app(async url=>{calls.push(url);return response(url==='/api/players/directory'?{players:[{id:'22',name:'José Player',team:'Miami Heat',team_id:'2'}]}:statsPayload(url));});
 try{
  await tick();const w=dom.window,d=w.document;d.getElementById('area-stats').click();await tick();await tick();
  const input=d.getElementById('player-search');
  assert.equal(d.querySelector('.player-search'),null);
  assert.ok(d.querySelector('#player .filters .player-picker').contains(input));
  assert.equal(d.getElementById('playername').hidden,true);assert.equal(input.getAttribute('role'),'combobox');
  d.getElementById('player-picker-toggle').click();await tick();
  assert.equal(input.getAttribute('aria-expanded'),'true');assert.match(d.getElementById('player-search-results').textContent,/First Player/);
  assert.equal(calls.includes('/api/players/directory'),false);
  input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));
  assert.ok(input.getAttribute('aria-activedescendant'));
  input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));await tick();
  assert.equal(input.value,'First Player');assert.equal(input.getAttribute('aria-expanded'),'false');
  d.getElementById('player-search-activate').click();input.value='j';input.dispatchEvent(new w.Event('input'));await tick();await tick();
  assert.match(d.getElementById('player-search-results').textContent,/José Player/);
  input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(input.getAttribute('aria-expanded'),'false');assert.equal(input.value,'First Player');
  d.getElementById('player-picker-toggle').click();await tick();d.body.click();assert.equal(input.getAttribute('aria-expanded'),'false');
 }finally{dom.window.close();}
});

test('keyboard is enabled only by the search icon and global team wording is restored on cancel or selection',async()=>{
 const calls=[];
 const dom=app(async url=>{calls.push(url);return response(url==='/api/players/directory'?{players:[{id:'22',name:'José Player',team:'Miami Heat',team_id:'2'}]}:statsPayload(url));});
 try{
  await tick();const w=dom.window,d=w.document;d.getElementById('area-stats').click();await tick();await tick();
  const input=d.getElementById('player-search'),team=d.getElementById('team');
  assert.equal(input.readOnly,true);assert.equal(input.getAttribute('inputmode'),'none');
  input.click();await tick();
  assert.equal(input.readOnly,true);assert.equal(input.getAttribute('aria-expanded'),'true');assert.equal(calls.includes('/api/players/directory'),false);
  d.getElementById('player-search-activate').click();
  assert.equal(input.readOnly,false);assert.equal(d.activeElement,input);assert.equal(team.selectedOptions[0].textContent,'Tutte le squadre');assert.equal(team.value,'1');
  assert.equal(calls.includes('/api/players/directory'),false);
  input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(input.readOnly,true);assert.equal(team.selectedOptions[0].textContent,'Boston Celtics');assert.equal(input.value,'First Player');assert.notEqual(d.activeElement,input);
  d.getElementById('player-search-activate').click();input.value='Jose';input.dispatchEvent(new w.Event('input'));await tick();await tick();
  d.querySelector('[data-player-result]').click();await tick();await tick();await tick();
  assert.equal(team.value,'2');assert.equal(team.selectedOptions[0].textContent,'Miami Heat');assert.equal(input.value,'José Player');assert.equal(input.readOnly,true);assert.notEqual(d.activeElement,input);
 }finally{dom.window.close();}
});
