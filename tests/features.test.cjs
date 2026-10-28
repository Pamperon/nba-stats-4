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
