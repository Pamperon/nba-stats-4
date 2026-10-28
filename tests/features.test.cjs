/* Full DOM integration: every request is synthetic and read-only. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const response=value=>({ok:true,json:async()=>value});
function app(fetch,seed=null,mobile=false){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'web/index.html'),'utf8'),{url:'https://basket.invalid',runScripts:'outside-only',pretendToBeVisual:true});
 dom.window.fetch=fetch;
 dom.window.matchMedia=()=>({matches:mobile});
 if(seed!==null)dom.window.localStorage.setItem('basketlab:favorites:v1',seed);
 for(const file of ['app.js','features.js'])dom.window.eval(fs.readFileSync(path.join(root,'web',file),'utf8'));
 return dom;
}
function base(url){
 if(url==='/api/saved/dates'||url==='/api/odds/dates')return {dates:[{date:'2099-01-01'},{date:'2099-01-02'}],default_date:'2099-01-01'};
 if(url.startsWith('/api/saved/status'))return {state:'done',last_saved:null};
 if(url.startsWith('/api/saved/latest'))return {date:'2099-01-01',results:[]};
 return {};
}

test('favorites persist without an account, filter quotes and reopen the exact player',async()=>{
 const dom=app(async url=>response(base(url)));
 try{
  await tick();const w=dom.window,d=w.document;
  d.getElementById('team').innerHTML='<option value="1">Team A</option>';
  d.getElementById('playername').innerHTML='<option value="123">A Player</option>';
  d.getElementById('player-display-name').textContent='A Player';await tick();
  d.getElementById('favorite-player').click();
  assert.equal(w.basketLabFavorites.has('123'),true);
  assert.equal(JSON.parse(w.localStorage.getItem('basketlab:favorites:v1'))[0].id,'123');
  d.querySelector('[data-extra="favorites"]').click();
  assert.equal(d.getElementById('app').hidden,true);
  assert.match(d.getElementById('favorite-list').textContent,/A Player/);
  let selected;w.basketLab.openPlayer=row=>{selected=row;};
  d.querySelector('[data-open-favorite="123"]').click();
  assert.equal(selected['ESPN ID'],'123');
  assert.equal(d.getElementById('app').hidden,false);
  d.querySelector('[data-extra="favorites"]').click();
  d.querySelector('[data-remove-favorite="123"]').click();
  assert.equal(w.basketLabFavorites.has('123'),false);
 }finally{dom.window.close();}
});

test('corrupt favorite storage is ignored and saved names render as text',async()=>{
 for(const seed of ['{broken',JSON.stringify([{id:'123',name:'<img src=x onerror=alert(1)>',team:'A'}])]){
  const dom=app(async url=>response(base(url)),seed);
  try{await tick();dom.window.document.querySelector('[data-extra="favorites"]').click();assert.equal(dom.window.document.querySelector('#favorite-list img'),null);}
  finally{dom.window.close();}
 }
});

test('archive keeps versions separate and never substitutes selections or current prices',async()=>{
 const calls=[];
 const version=(id,price,name,status)=>({job_id:id,saved_at:'2026-10-27T10:00:00Z',groups:{Singola:{status,combined_odds:price,legs:[{Giocatore:name,Partita:'A - B',Scelta:'Over',Linea:19.5,Mercato:'PTS',Quota:price,actual:status==='won'?22:null,win:status==='won'?true:null}]}}});
 const dom=app(async(url,options={})=>{
  calls.push({url,method:options.method||'GET'});
  if(url==='/api/history/dates')return response({dates:[{date:'2026-10-27'}]});
  if(url.startsWith('/api/history?'))return response({versions:[version('latest',1.71,'Original Player','unresolved'),version('earlier',1.74,'Earlier Player','won')]});
  return response(base(url));
 });
 try{
  await tick();const d=dom.window.document;d.querySelector('[data-extra="history"]').click();await tick();await tick();
  assert.match(d.getElementById('history-tickets').textContent,/Original Player/);
  assert.match(d.getElementById('history-tickets').textContent,/1,71/);
  assert.doesNotMatch(d.getElementById('history-tickets').textContent,/Earlier Player/);
  d.getElementById('history-version').value='earlier';d.getElementById('history-version').dispatchEvent(new dom.window.Event('change'));
  assert.match(d.getElementById('history-tickets').textContent,/Earlier Player/);
  assert.match(d.getElementById('history-tickets').textContent,/1,74/);
  assert.ok(calls.every(call=>call.method==='GET'));
 }finally{dom.window.close();}
});

test('movement filters show original before/after odds and a clear missing-comparison state',async()=>{
 const dom=app(async url=>{
  if(url.startsWith('/api/odds/changes'))return response({versions:[{saved_at:'2026-10-28T13:30:00Z'},{saved_at:'2026-10-28T10:00:00Z'}],summary:{up:0,down:1,unchanged:2,added:1,removed:0,line_groups_changed:1,ambiguous:0},changes:[{player:'Brown',game:'A - B',market:'PTS',choice:'Over',line:19.5,kind:'down',before:1.74,after:1.71},{player:'Other',game:'C - D',market:'REB',choice:'Over',line:4.5,kind:'added',before:null,after:1.5}]});
  return response(base(url));
 });
 try{
  await tick();const d=dom.window.document;d.querySelector('[data-extra="movements"]').click();await tick();await tick();
  assert.match(d.getElementById('movements-list').textContent,/1,74/);assert.match(d.getElementById('movements-list').textContent,/1,71/);
  d.getElementById('movements-kind').value='down';d.getElementById('movements-kind').dispatchEvent(new dom.window.Event('change'));
  assert.match(d.getElementById('movements-list').textContent,/Brown/);assert.doesNotMatch(d.getElementById('movements-list').textContent,/Other/);
  d.getElementById('movements-search').value='Missing';d.getElementById('movements-search').dispatchEvent(new dom.window.Event('input'));
  assert.match(d.getElementById('movements-status').textContent,/Nessun movimento/);
 }finally{dom.window.close();}
 const empty=app(async url=>response(url.startsWith('/api/odds/changes')?{versions:[],summary:null,changes:[]}:base(url)));
 try{await tick();empty.window.document.querySelector('[data-extra="movements"]').click();await tick();await tick();assert.match(empty.window.document.getElementById('movements-status').textContent,/almeno due scansioni/);}
 finally{empty.window.close();}
});

test('mobile finder progressively loads rows and favorite/reset filters remain independent of picks',async()=>{
 const rows=Array.from({length:250},(_,i)=>({Giocatore:'Player '+i,'ESPN ID':String(100+i),Squadra:'A',Mercato:'PTS',Linea:9.5,Quota:1.8,'Stato analisi':'Valutabile (stima empirica)','Prob. stimata %':80}));
 const dom=app(async url=>response(url.startsWith('/api/saved/latest')?{date:'2099-01-01',results:rows}:base(url)),JSON.stringify([{id:'100',name:'Player 0',team:'A'}]),true);
 try{
  await tick();const d=dom.window.document;
  assert.equal(d.querySelectorAll('.finder-card').length,100);
  d.getElementById('finder-more').click();assert.equal(d.querySelectorAll('.finder-card').length,200);
  d.getElementById('finder-favorites').checked=true;d.getElementById('finder-favorites').dispatchEvent(new dom.window.Event('change'));
  assert.equal(d.querySelectorAll('.finder-card').length,1);
  d.getElementById('finder-reset').click();assert.equal(d.querySelectorAll('.finder-card').length,100);
  d.querySelector('[data-extra="about"]').click();assert.equal(d.getElementById('extra-about').hidden,false);
  assert.match(d.getElementById('extra-about').textContent,/14:30/);
  d.getElementById('area-quotes').click();assert.equal(d.getElementById('extra-about').hidden,true);assert.equal(d.getElementById('app').hidden,false);
 }finally{dom.window.close();}
});
