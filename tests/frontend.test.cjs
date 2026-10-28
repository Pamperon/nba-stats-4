/* Offline DOM regressions. All fetches are synthetic; no server is contacted. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'web/app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'web/index.html'), 'utf8');
const response = payload => ({ok: true, json: async () => payload});
const tick = () => new Promise(resolve => setImmediate(resolve));
function browser(fetch) {
  const dom = new JSDOM(html, {url: 'https://nba.invalid', runScripts: 'outside-only', pretendToBeVisual: true});
  dom.window.fetch = fetch;
  dom.window.eval(source + '\nwindow.__audit = {getData: () => data, getPlayerInit: () => playerStatsInitialized, setPlayerInit: value => {playerStatsInitialized = value;}, setPlayerGames: value => {playerGames = value;}};');
  return dom;
}

// Regression: removing the failed <img> made the next selection dereference null.
test('missing player portrait does not break the next player selection', async () => {
  const dom = browser(async url => response(url === '/api/saved/dates' ? {dates: []} : {}));
  try {
    const w = dom.window, d = w.document;
    d.getElementById('team').innerHTML = '<option value="1">Team</option>';
    d.getElementById('playername').innerHTML = '<option value="1">First Player</option>';
    await w.loadPlayerProfile(0, '1', '1');
    const first = d.getElementById('player-photo');
    first.onerror();
    assert.ok(d.getElementById('player-photo'));
    assert.equal(d.getElementById('player-initials').textContent, 'FP');
    d.getElementById('playername').innerHTML = '<option value="2">Second Player</option>';
    await w.loadPlayerProfile(0, '1', '2');
    assert.notEqual(d.getElementById('player-photo'), first);
    assert.equal(d.getElementById('player-photo').hidden, false);
    assert.equal(d.getElementById('player-initials').textContent, 'SP');
  } finally {dom.window.close();}
});

test('initial archive response cannot overwrite a newly selected day', async () => {
  const pending = new Map();
  const dom = browser(url => {
    if (url === '/api/saved/dates') return Promise.resolve(response({dates: [{date: '2099-01-01'}, {date: '2099-01-02'}]}));
    return new Promise(resolve => pending.set(url, resolve));
  });
  try {
    await tick();
    const w = dom.window, d = w.document;
    d.getElementById('date').value = '2099-01-02';
    d.getElementById('date').dispatchEvent(new w.Event('change'));
    const snapshot = date => ({date, results: [], fixture_count: 0, player_count: 0, saved_at: date + 'T12:00:00Z'});
    pending.get('/api/saved/latest?date=2099-01-02')(response(snapshot('2099-01-02')));
    await tick();
    pending.get('/api/saved/latest?date=2099-01-01')(response(snapshot('2099-01-01')));
    await tick();
    assert.equal(w.__audit.getData().date, '2099-01-02');
    assert.equal(d.getElementById('date-loading').hidden, true);
  } finally {dom.window.close();}
});

test('catalog failure can be retried by reopening the statistics tab', async () => {
  const dom = browser(async url => {
    if (url === '/api/saved/dates') return response({dates: []});
    throw new Error('offline');
  });
  try {
    dom.window.__audit.setPlayerInit(true);
    await dom.window.initPlayers();
    assert.equal(dom.window.__audit.getPlayerInit(), false);
  } finally {dom.window.close();}
});

function serviceWorker(fetch, caches) {
  const handlers = {};
  const context = {self: {location: {origin: 'https://nba.invalid'}, addEventListener: (name, fn) => {handlers[name] = fn;}}, fetch, caches, URL, Response};
  vm.runInNewContext(fs.readFileSync(path.join(root, 'web/sw.js'), 'utf8'), context);
  return handlers;
}
test('service worker registers lifecycle and preserves unrelated caches', async () => {
  const deleted = [];
  const current = fs.readFileSync(path.join(root, 'web/sw.js'), 'utf8').match(/const CACHE = '([^']+)'/)[1];
  const handlers = serviceWorker(null, {
    keys: async () => ['nba-stats-4-shell-v2', 'nba-stats-4-shell-v46', current, 'other-app-cache'],
    delete: async key => deleted.push(key),
  });
  let task;
  handlers.activate({waitUntil: promise => {task = promise;}});
  await task;
  assert.deepEqual(deleted, ['nba-stats-4-shell-v2', 'nba-stats-4-shell-v46']);
  assert.ok(handlers.install);
});
test('service worker excludes API traffic and resolves versioned shell assets offline', async () => {
  let seen;
  const handlers = serviceWorker(async () => {throw new Error('offline');}, {match: async (request, options) => {seen = options; return {cached: true};}});
  const event = url => ({request: {method: 'GET', url}, respondWith: () => {throw new Error('API must not be intercepted');}});
  handlers.fetch(event('https://nba.invalid/api/saved/latest'));
  let result;
  handlers.fetch({request: {method: 'GET', url: 'https://nba.invalid/static/app.js?v=updated'}, respondWith: promise => {result = promise;}});
  assert.deepEqual(await result, {cached: true});
  assert.equal(seen.ignoreSearch, true);
});

test('CSV preserves names and last-N ratios while neutralizing formulas', () => {
  const dom = browser(async () => response({dates: []}));
  try {
    const cell = dom.window.csvCell;
    assert.equal(cell('team player'), '"team player"');
    assert.equal(cell('5/5'), '"\'5/5"');
    assert.equal(cell('=1+1'), '"\'=1+1"');
    assert.equal(cell('a"b'), '"a""b"');
  } finally {dom.window.close();}
});


test('player statistics expire in memory after fifteen minutes', () => {
  const dom = browser(async () => response({dates: []}));
  try {
    const w = dom.window;
    let now = 1000000000000;
    w.Date.now = () => now;
    w.cachePlayerLog('player', {games: [{PTS: 10}]});
    now += 14 * 60 * 1000;
    assert.equal(w.getPlayerLogCache('player').games[0].PTS, 10);
    now += 2 * 60 * 1000;
    assert.equal(w.getPlayerLogCache('player'), null);
    assert.equal(w.sessionStorage.getItem('nba-player-log-v2:player'), null);
  } finally {dom.window.close();}
});

test('restoring session cache does not restart its fifteen minute lifetime', () => {
  const dom = browser(async () => response({dates: []}));
  try {
    const w = dom.window, at = 1000000000000;
    let now = at + 14 * 60 * 1000;
    w.Date.now = () => now;
    w.sessionStorage.setItem('nba-player-log-v2:player', JSON.stringify({at, payload: {games: []}}));
    assert.ok(w.getPlayerLogCache('player'));
    now = at + 15 * 60 * 1000;
    assert.equal(w.getPlayerLogCache('player'), null);
    w.sessionStorage.setItem('nba-player-log-v2:bad', JSON.stringify({at: 'invalid', payload: {}}));
    assert.equal(w.getPlayerLogCache('bad'), null);
  } finally {dom.window.close();}
});

test('initial archive outage shows a visible error', async () => {
  const dom = browser(async () => ({ok: false, status: 503}));
  try {
    await tick();
    const status = dom.window.document.getElementById('status');
    assert.equal(status.hidden, false);
    assert.equal(status.getAttribute('role'), 'alert');
    assert.match(status.textContent, /Archivio temporaneamente non disponibile/);
  } finally {dom.window.close();}
});

test('day-load outage is visible and clears after a successful retry', async () => {
  let fail = true;
  const dom = browser(async url => {
    if (url === '/api/saved/dates') return response({dates: [{date: '2099-01-01'}]});
    if (fail) return {ok: false, status: 503};
    return response({date: '2099-01-01', results: [], saved_at: '2099-01-01T12:00:00Z'});
  });
  try {
    await tick();
    const w = dom.window, d = w.document, status = d.getElementById('status');
    assert.equal(status.hidden, false);
    assert.equal(status.getAttribute('role'), 'alert');
    fail = false;
    d.getElementById('date').dispatchEvent(new w.Event('change'));
    await tick();
    assert.equal(status.hidden, true);
    assert.equal(status.getAttribute('role'), 'status');
    assert.equal(d.getElementById('date-loading').hidden, true);
    assert.equal(w.__audit.getData().date, '2099-01-01');
  } finally {dom.window.close();}
});

test('status polling stays invisible and ignores delayed responses for an old date', async () => {
  const pending=new Map();
  const dom=browser(async url=>{
    if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'},{date:'2099-01-02'}]});
    if(url.startsWith('/api/saved/status'))return new Promise(resolve=>pending.set(url,resolve));
    return response({results:[],date:url.includes('2099-01-02')?'2099-01-02':'2099-01-01'});
  });
  try{
    await tick();const w=dom.window,d=w.document;
    d.getElementById('date').value='2099-01-02';d.getElementById('date').dispatchEvent(new w.Event('change'));
    pending.get('/api/saved/status?date=2099-01-02')(response({state:'done',last_saved:{state:'done',saved_at:'2099-01-02T12:00:00Z'}}));
    await tick();
    pending.get('/api/saved/status?date=2099-01-01')(response({state:'error'}));await tick();
    assert.equal(d.getElementById('scan-status'),null);
  }finally{dom.window.close();}
});

test('status polling only reads saved endpoints and refreshes a newly completed snapshot', async () => {
  const calls=[],timers=[];let state='running';
  const dom=browser(async(url,options={})=>{
    calls.push({url,method:options.method||'GET'});
    if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
    if(url.startsWith('/api/saved/status'))return response({state,latest_attempt:{state,started_at:'2099-01-01T12:00:00Z'},last_saved:null});
    return response({date:'2099-01-01',state,results:[]});
  });
  try{
    dom.window.setTimeout=(fn)=>{timers.push(fn);return timers.length};
    await tick();assert.equal(timers.length,1);
    state='done';await timers[0]();await tick();
    assert.equal(dom.window.document.getElementById('scan-status'),null);
    assert.equal(dom.window.__audit.getData().state,'done');
    assert.ok(calls.filter(c=>c.url.startsWith('/api/saved/latest')).length>=2);
    assert.ok(calls.every(c=>c.method==='GET'&&c.url.startsWith('/api/saved/')));
  }finally{dom.window.close();}
});

test('status endpoint outage does not hide a successfully loaded snapshot', async () => {
  const dom=browser(async url=>{
    if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
    if(url.startsWith('/api/saved/status'))return {ok:false,status:503};
    return response({date:'2099-01-01',results:[]});
  });
  try{
    await tick();
    assert.equal(dom.window.__audit.getData().date,'2099-01-01');
    assert.equal(dom.window.document.getElementById('scan-status'),null);
  }finally{dom.window.close();}
});

test('a completed saved job retries a failed snapshot read without waiting for another scan', async () => {
 const timers=[],calls=[];let reads=0;
 const dom=browser(async(url,options={})=>{
  calls.push({url,method:options.method||'GET'});
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/status'))return response({state:'done',last_saved:{job_id:'saved'}});
  if(url.startsWith('/api/saved/latest')){
   if(++reads===1)return {ok:false,status:503};
   return response({job_id:'saved',date:'2099-01-01',results:[]});
  }
  return response({});
 });
 try{
  dom.window.setTimeout=fn=>{timers.push(fn);return timers.length};
  await tick();assert.equal(dom.window.__audit.getData(),null);
  await timers[0]();await tick();
  assert.equal(reads,2);
  assert.equal(dom.window.__audit.getData().job_id,'saved');
  assert.ok(calls.every(c=>c.method==='GET'&&c.url.startsWith('/api/saved/')));
 }finally{dom.window.close();}
});

test('an open page rechecks started games even when the saved job never changes', async () => {
 const timers=[],calls=[];let reads=0;
 const dom=browser(async(url,options={})=>{
  calls.push({url,method:options.method||'GET'});
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/status'))return response({state:'done',last_saved:{job_id:'same'}});
  if(url.startsWith('/api/saved/latest'))return response({job_id:'same',date:'2099-01-01',results:[],
   fixture_count:++reads===1?2:1,visibility_valid_until:reads===1?'2000-01-01T00:00:00Z':'2099-01-01T00:00:00Z'});
  return response({});
 });
 try{
  dom.window.setTimeout=fn=>{timers.push(fn);return timers.length};
  await tick();assert.equal(dom.window.__audit.getData().fixture_count,2);
  await timers[0]();await tick();
  assert.equal(reads,2);
  assert.equal(dom.window.__audit.getData().fixture_count,1);
  assert.ok(calls.every(c=>c.method==='GET'&&c.url.startsWith('/api/saved/')));
 }finally{dom.window.close();}
});

test('returning to an expired page refreshes immediately without recursive reloads', async () => {
 let reads=0;
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/status'))return response({state:'done',last_saved:{job_id:'same'}});
  if(url.startsWith('/api/saved/latest'))return response({job_id:'same',date:'2099-01-01',results:[],
   fixture_count:++reads===1?2:1,visibility_valid_until:reads===1?'2000-01-01T00:00:00Z':'2099-01-01T00:00:00Z'});
  return response({});
 });
 try{
  await tick();assert.equal(reads,1);
  dom.window.dispatchEvent(new dom.window.Event('focus'));await tick();
  assert.equal(reads,2);
  assert.equal(dom.window.__audit.getData().fixture_count,1);
 }finally{dom.window.close();}
});

test('an open page checks again after completion to detect the next scheduled scan', async () => {
  const timers=[];let state='done';
  const dom=browser(async url=>{
    if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
    if(url.startsWith('/api/saved/status'))return response({state,latest_attempt:{state,started_at:'2099-01-01T12:00:00Z'},last_saved:null});
    return response({date:'2099-01-01',state,results:[]});
  });
  try{
    dom.window.setTimeout=(fn,delay)=>{timers.push({fn,delay});return timers.length};
    await tick();assert.equal(timers[0].delay,60000);
    state='running';await timers[0].fn();await tick();
    assert.equal(dom.window.document.getElementById('scan-status'),null);
    assert.equal(timers[1].delay,15000);
  }finally{dom.window.close();}
});


test('missing quotes keep the previous simple layout without duplicate notices', async () => {
  const dom=browser(async url=>{
    if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
    if(url.startsWith('/api/saved/status'))return response({state:'waiting',last_saved:null});
    return {ok:false,status:404};
  });
  try{
    await tick();await tick();const d=dom.window.document;
    assert.equal(d.getElementById('scan-status'),null);
    assert.equal(d.getElementById('status').hidden,true);
    assert.match(d.getElementById('picks').textContent,/Nessuna quota ancora disponibile/);
    assert.equal(d.getElementById('quote-summary').hidden,false);
    assert.equal(d.getElementById('quote-updated').textContent,'Dati non ancora disponibili');
    assert.deepEqual([...d.querySelectorAll('#metrics .metric strong')].map(x=>x.textContent),['—','—','—']);
  }finally{dom.window.close();}
});


test('initial page selects the next upcoming NBA day instead of a completed calendar day', async () => {
  const dom=browser(async url=>{
    if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'},{date:'2099-01-02'}],default_date:'2099-01-02'});
    if(url.startsWith('/api/saved/status'))return response({state:'partial',last_saved:null});
    return response({date:'2099-01-02',results:[],fixture_count:9,player_count:0,saved_at:'2099-01-02T06:34:00Z'});
  });
  try{
    await tick();const d=dom.window.document;
    assert.equal(d.getElementById('date').value,'2099-01-02');
    assert.equal(dom.window.__audit.getData().date,'2099-01-02');
    assert.match(d.getElementById('metrics').textContent,/PARTITE9/);
    assert.match(d.getElementById('quote-updated').textContent,/^Ultimo controllo:/);
  }finally{dom.window.close();}
});

test('catalog revisits avoid requests and expired catalog reloads', async()=>{
 let calls=0;
 const dom=browser(async url=>{
  if(url==='/api/players/teams'){calls++;return response({teams:[]})}
  return response({dates:[]});
 });
 try{
  const w=dom.window;let now=1000000000000;w.Date.now=()=>now;
  await w.playerCatalog('/api/players/teams');
  await w.playerCatalog('/api/players/teams');
  assert.equal(calls,1);
  now+=15*60*1000;
  await w.playerCatalog('/api/players/teams');
  assert.equal(calls,2);
 }finally{dom.window.close()}
});

test('concurrent player loads share one request and return cached data on revisit', async()=>{
 let calls=0,resolve;
 const dom=browser(url=>{
  if(url.startsWith('/api/players/log')){calls++;return new Promise(r=>{resolve=r})}
  return Promise.resolve(response({dates:[]}));
 });
 try{
  const w=dom.window;
  const a=w.fetchPlayerLog('1','123','2026'),b=w.fetchPlayerLog('1','123','2026');
  assert.equal(calls,1);
  resolve(response({games:[{PTS:20}]}));
  await Promise.all([a,b]);
  assert.equal((await w.fetchPlayerLog('1','123','2026')).games[0].PTS,20);
  assert.equal(calls,1);
 }finally{dom.window.close()}
});

test('team batch makes a nonadjacent player available without a log request', async () => {
  const calls=[];
  const dom=browser(async url=>{
    calls.push(url);
    if(url==='/api/saved/dates')return response({dates:[]});
    if(url==='/api/players/teams')return response({teams:[{id:'1',name:'Team'}]});
    if(url.startsWith('/api/players/roster'))return response({players:[{id:'1',name:'First'},{id:'2',name:'Second'},{id:'3',name:'Third'}]});
    if(url.startsWith('/api/players/team-logs'))return response({logs:{'3':{athlete_id:'3',season:String(new Date().getMonth()>=9?new Date().getFullYear():new Date().getFullYear()-1),games:[{PTS:25,REB:3,AST:4,SEASON_TYPE:2}]}}});
    return response({games:[]});
  });
  try{
    const w=dom.window,d=w.document;
    d.querySelector('nav button.active').classList.remove('active');
    d.querySelector('[data-tab="player"]').classList.add('active');
    await w.initPlayers();await tick();
    const before=calls.length;
    d.getElementById('playername').value='3';await w.changePlayer();
    assert.equal(calls.length,before);
    assert.match(d.getElementById('player-season-stats').textContent,/25\.0/);
    assert.equal(d.getElementById('player-loading').hidden,true);
  }finally{dom.window.close()}
});

test('background team preparation stops before loading players after leaving statistics', async () => {
  const calls=[];
  const dom=browser(async url=>{
    calls.push(url);
    if(url==='/api/saved/dates')return response({dates:[]});
    if(url==='/api/players/teams')return response({teams:[{id:'1',name:'Team'}]});
    if(url.startsWith('/api/players/roster'))return response({players:[{id:'1',name:'First'},{id:'2',name:'Second'}]});
    if(url.startsWith('/api/players/team-logs'))return response({logs:{}});
    return response({games:[]});
  });
  try{
    await dom.window.initPlayers();
    await new Promise(resolve=>setTimeout(resolve,450));
    assert.equal(calls.filter(url=>url.startsWith('/api/players/log?')).length,1);
  }finally{dom.window.close()}
});

test('risk screening rejects falling minutes and unavailable players without changing estimates', async () => {
 const dom=browser(async()=>response({dates:[]}));
 try{
  const base={'Stato analisi':'Valutabile (stima empirica)','Prob. stimata %':80,Quota:1.8,Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29};
  assert.equal(dom.window.reliablePick(base),true);
  assert.equal(dom.window.reliablePick({...base,'Minuti ultime 5':21}),false);
  assert.equal(dom.window.reliablePick({...base,'Disponibilità ESPN':'out'}),false);
  assert.equal(dom.window.reliablePick({...base,'Disponibilità ESPN':'unknown'}),false);
  assert.equal(base['Prob. stimata %'],80);
 }finally{dom.window.close()}
});

test('saved suggestions remain exact and started legs are not replaced', async () => {
 const base={Giocatore:'Saved Player',Partita:'A - B',Squadra:'A',Mercato:'PTS',Scelta:'Over',Linea:9.5,Quota:1.8,'Prob. stimata %':80,'Value stimato %':44,'Stato analisi':'Valutabile (stima empirica)',Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29};
 const alternate={...base,Giocatore:'Higher Player','Prob. stimata %':90};
 let snapshot={date:'2099-01-01',results:[base,alternate],fixture_count:1,player_count:2,recommendations:{policy:'risk-screen-v1',groups:{Singola:{complete:true,legs:[base]},Doppia:{complete:false,legs:[]},Tripla:{complete:false,legs:[]}}}};
 const dom=browser(async url=>response(url==='/api/saved/dates'?{dates:[{date:'2099-01-01'}]}:url.startsWith('/api/saved/latest')?snapshot:{}));
 try{
  await tick();await tick();
  const d=dom.window.document;
  assert.match(d.getElementById('picks').textContent,/Saved Player/);
  assert.doesNotMatch(d.getElementById('picks').textContent,/Higher Player/);
  snapshot={...snapshot,results:[alternate]};
  d.getElementById('date').dispatchEvent(new dom.window.Event('change'));await tick();await tick();
  assert.doesNotMatch(d.getElementById('picks').textContent,/Higher Player/);
  assert.doesNotMatch(d.getElementById('picks').textContent,/Saved Player/);
 }finally{dom.window.close()}
});

test('clicking a suggested player opens exactly that player market and line without unrelated logs', async () => {
 const calls=[];
 const pick={Giocatore:'Second Player','ESPN ID':'22',Squadra:'Boston Celtics',Partita:'Boston Celtics - Miami Heat',Mercato:'AST',Scelta:'Over',Linea:4.5,Quota:1.8,'Prob. stimata %':80,'Value stimato %':44,'Stato analisi':'Valutabile (stima empirica)',Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29};
 const dom=browser(async url=>{
  calls.push(url);
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/latest'))return response({date:'2099-01-01',results:[pick],season:'2026-27'});
  if(url==='/api/players/teams')return response({teams:[{id:'1',name:'Atlanta Hawks'},{id:'2',name:'Boston Celtics'}]});
  if(url.startsWith('/api/players/roster'))return response({players:[{id:'11',name:'First Player'},{id:'22',name:'Second Player'}]});
  if(url.startsWith('/api/players/log?'))return response({games:[{AST:6,PTS:20,REB:3,SEASON_TYPE:2,GAME_DATE:'2026-10-25'}]});
  return response({logs:{}});
 });
 try{
  await tick();await tick();
  dom.window.document.querySelector('.pick-player-link').click();
  await tick();await tick();await tick();
  const d=dom.window.document;
  assert.equal(d.getElementById('player').hidden,false);
  assert.equal(d.getElementById('dashboard').hidden,true);
  assert.equal(d.getElementById('team').value,'2');
  assert.equal(d.getElementById('playername').value,'22');
  assert.equal(d.getElementById('stat').value,'AST');
  assert.equal(d.getElementById('line').value,'4.5');
  assert.equal(d.getElementById('playermode').value,'2');
  assert.match(d.getElementById('player-summary').textContent,/Over 4.5/);
  assert.equal(calls.filter(x=>x.startsWith('/api/players/log?')).length,1);
  assert.ok(calls.find(x=>x.startsWith('/api/players/log?')).includes('athlete_id=22'));
 }finally{dom.window.close()}
});

test('the statistics button opens exactly that player market and line without unrelated logs', async () => {
 const calls=[];
 const pick={Giocatore:'Second Player','ESPN ID':'22',Squadra:'Boston Celtics',Partita:'Boston Celtics - Miami Heat',Mercato:'AST',Scelta:'Over',Linea:4.5,Quota:1.8,'Prob. stimata %':80,'Value stimato %':44,'Stato analisi':'Valutabile (stima empirica)',Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29};
 const dom=browser(async url=>{
  calls.push(url);
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/latest'))return response({date:'2099-01-01',results:[pick],season:'2026-27'});
  if(url==='/api/players/teams')return response({teams:[{id:'1',name:'Atlanta Hawks'},{id:'2',name:'Boston Celtics'}]});
  if(url.startsWith('/api/players/roster'))return response({players:[{id:'11',name:'First Player'},{id:'22',name:'Second Player'}]});
  if(url.startsWith('/api/players/log?'))return response({games:[{AST:6,PTS:20,REB:3,SEASON_TYPE:2,GAME_DATE:'2026-10-25'}]});
  return response({logs:{}});
 });
 try{
  await tick();await tick();
  dom.window.document.querySelector('.pick-stats-button').click();
  await tick();await tick();await tick();
  const d=dom.window.document;
  assert.equal(d.getElementById('player').hidden,false);
  assert.equal(d.getElementById('dashboard').hidden,true);
  assert.equal(d.getElementById('team').value,'2');
  assert.equal(d.getElementById('playername').value,'22');
  assert.equal(d.getElementById('stat').value,'AST');
  assert.equal(d.getElementById('line').value,'4.5');
  assert.equal(d.getElementById('playermode').value,'2');
  assert.match(d.getElementById('player-summary').textContent,/Over 4.5/);
  assert.equal(calls.filter(x=>x.startsWith('/api/players/log?')).length,1);
  assert.ok(calls.find(x=>x.startsWith('/api/players/log?')).includes('athlete_id=22'));
 }finally{dom.window.close()}
});

test('a slower first pick cannot overwrite the second selected player', async () => {
 let release;
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[]});
  if(url==='/api/players/teams')return new Promise(resolve=>{release=()=>resolve(response({teams:[{id:'2',name:'Boston Celtics'}]}))});
  if(url.startsWith('/api/players/roster'))return response({players:[{id:'11',name:'First'},{id:'22',name:'Second'}]});
  if(url.startsWith('/api/players/log?'))return response({games:[]});
  return response({logs:{}});
 });
 try{
  const w=dom.window;
  const a=w.openPickStats({Giocatore:'First','ESPN ID':'11',Squadra:'Boston Celtics',Mercato:'PTS',Linea:19.5});
  const firstRelease=release;
  const b=w.openPickStats({Giocatore:'Second','ESPN ID':'22',Squadra:'Boston Celtics',Mercato:'REB',Linea:6.5});
  release();await b;firstRelease();await a;
  assert.equal(w.document.getElementById('playername').value,'22');
  assert.equal(w.document.getElementById('stat').value,'REB');
  assert.equal(w.document.getElementById('line').value,'6.5');
 }finally{dom.window.close()}
});

test('other seasons of the selected player preload once and switching years needs no request', async () => {
 const calls=[];
 const dom=browser(async url=>{
  calls.push(url);
  if(url==='/api/saved/dates')return response({dates:[]});
  if(url==='/api/players/teams')return response({teams:[{id:'2',name:'Boston Celtics'}]});
  if(url.startsWith('/api/players/roster'))return response({players:[{id:'11',name:'Other Player'},{id:'22',name:'Chosen Player'}]});
  if(url.startsWith('/api/players/log?')){
   const season=new URLSearchParams(url.split('?')[1]).get('season');
   return response({season,athlete_id:'22',games:[{PTS:Number(season)%100,AST:2,REB:3,SEASON_TYPE:2,GAME_DATE:season+'-11-01'}]});
  }
  return response({logs:{}});
 });
 try{
  const w=dom.window,d=w.document;
  await w.openPickStats({Giocatore:'Chosen Player','ESPN ID':'22',Squadra:'Boston Celtics',Mercato:'PTS',Linea:9.5});
  await new Promise(resolve=>setTimeout(resolve,220));
  const logs=calls.filter(url=>url.startsWith('/api/players/log?'));
  assert.equal(logs.length,3);
  assert.ok(logs.every(url=>url.includes('athlete_id=22')));
  const before=calls.length;
  d.getElementById('playerseason').selectedIndex=1;
  d.getElementById('playerseason').dispatchEvent(new w.Event('change'));
  await tick();
  assert.equal(calls.length,before);
  assert.equal(d.getElementById('line').value,'9.5');
  assert.match(d.getElementById('player-summary').textContent,/Over 9.5/);
  assert.equal(d.getElementById('player-loading').hidden,true);
  assert.ok(d.getElementById('player-season-stats').textContent.includes((Number(d.getElementById('playerseason').value)%100).toFixed(1)));
 }finally{dom.window.close()}
});

test('completed seasons survive browser session reload without renewing their lifetime', async () => {
 const dom=browser(async()=>response({dates:[]}));
 try{
  const w=dom.window,key='2:22:2025',at=Date.now()-60*60*1000;
  w.localStorage.setItem('nba-player-history-v2:'+key,JSON.stringify({at,payload:{games:[{PTS:23}]}}));
  assert.equal(w.getPlayerLogCache(key).games[0].PTS,23);
  assert.equal(JSON.parse(w.localStorage.getItem('nba-player-history-v2:'+key)).at,at);
  w.localStorage.setItem('nba-player-history-v2:2:22:2024',JSON.stringify({at:Date.now()-25*60*60*1000,payload:{games:[]}}));
  assert.equal(w.getPlayerLogCache('2:22:2024'),null);
  assert.equal(w.localStorage.getItem('nba-player-history-v2:2:22:2024'),null);
 }finally{dom.window.close()}
});

test('same-game combinations show indicative products and warn about dependence', async () => {
 const base={Squadra:'A',Partita:'A - B',Mercato:'PTS',Scelta:'Over',Linea:9.5,Quota:1.5,'Prob. stimata %':80,'Value stimato %':20,'Stato analisi':'Valutabile (stima empirica)',Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29};
 const picks=[{...base,Giocatore:'First','ESPN ID':'1'},{...base,Giocatore:'Second','ESPN ID':'2'}];
 const dom=browser(async url=>response(url==='/api/saved/dates'?{dates:[{date:'2099-01-01'}]}:url.startsWith('/api/saved/latest')?{date:'2099-01-01',results:picks}:{}));
 try{
  await tick();await tick();
  const text=dom.window.document.getElementById('picks').textContent;
  const d=dom.window.document;
  const cards=d.querySelectorAll('#pick-doppia .pick-selection');
  assert.equal(cards.length,2);
  for(const card of cards){assert.match(card.textContent,/QUOTA\s*1,50/);assert.match(card.textContent,/STIMA DEL MODELLO\s*80%/)}
  assert.equal(d.querySelectorAll('.pick-group-range').length,0);
  assert.match(text,/Calcolo senza correlazioni/);
  assert.match(text,/Quota totale indicativa\s*2,25/);
  assert.match(text,/Stima combinata indicativa\s*64%/);
  assert.match(text,/Verifica la quota sul bookmaker/);
 }finally{dom.window.close()}
});

 test('season switches preserve a manually selected line even with no games', async () => {
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[]});
  if(url==='/api/players/teams')return response({teams:[{id:'2',name:'Boston Celtics'}]});
  if(url.startsWith('/api/players/roster'))return response({players:[{id:'22',name:'Chosen Player'}]});
  if(url.startsWith('/api/players/log?'))return response({games:[]});
  return response({logs:{}});
 });
 try{
  const w=dom.window,d=w.document;
  await w.openPickStats({Giocatore:'Chosen Player','ESPN ID':'22',Squadra:'Boston Celtics',Mercato:'AST',Linea:4.5});
  d.getElementById('line').value='12.5';
  d.getElementById('line').dispatchEvent(new w.Event('change'));
  for(const index of [1,2,0]){
   d.getElementById('playerseason').selectedIndex=index;
   d.getElementById('playerseason').dispatchEvent(new w.Event('change'));
   await tick();await tick();
   assert.equal(d.getElementById('line').value,'12.5');
   assert.equal(d.getElementById('stat').value,'AST');
  }
  d.getElementById('stat').value='REB';
  d.getElementById('stat').dispatchEvent(new w.Event('change'));
  assert.equal(d.getElementById('line').value,'10.5');
 }finally{dom.window.close()}
});


test('explanation shows saved statistics and consecutive misses without changing picks', async () => {
 const pick={Giocatore:'Player',Partita:'A - B',Squadra:'A',Mercato:'PTS',Scelta:'Over',Linea:19.5,Quota:1.8,'Prob. stimata %':75,'Value stimato %':19,'Stato analisi':'Valutabile (stima empirica)',Partite:5,'Stagione %':60,'Ultime 20':'3/5','Ultime 5':'3/5','Minuti medi':30,'Minuti ultime 5':28,'Stagione attuale (n)':5};
 const games=[18,19,25,24,23].map((PTS,i)=>({GAME_DATE:`2026-10-${25-i}`,PTS}));
 const snapshot={date:'2099-01-01',results:[pick],player_logs:{Player:games},recommendations:{groups:{Singola:{complete:true,legs:[pick]},Doppia:{legs:[]},Tripla:{legs:[]}}}};
 const dom=browser(async url=>response(url==='/api/saved/dates'?{dates:[{date:'2099-01-01'}]}:url.startsWith('/api/saved/latest')?snapshot:{}));
 try {
  await tick();await tick();const d=dom.window.document,details=d.querySelector('.pick-explanation');
  assert.ok(details);assert.equal(details.querySelector('summary').textContent,'Dettagli pronostico');assert.ok(details.closest('.pick-actions').querySelector('.pick-stats-button'));assert.equal(details.open,false);details.querySelector('summary').click();assert.equal(details.open,true);
  assert.match(details.textContent,/3 delle ultime 5 partite/);assert.match(details.textContent,/3 su 5/);
  assert.match(details.textContent,/ultime 2 partite consecutive/);assert.match(details.textContent,/55,6%/);
  assert.match(details.textContent,/28 minuti/);assert.equal(details.querySelector('.pick-implied-help'),null);assert.match(details.textContent,/📊 Ultime partite/);assert.match(details.textContent,/💡 Stima e quota/);assert.doesNotMatch(details.textContent,/La stima usa le partite precedenti/);
  assert.equal(d.querySelectorAll('.pick-selection').length,1);
 } finally {dom.window.close()}
});

test('explanation never invents streaks or historic counts when data are missing or ambiguous', async () => {
 const dom=browser(async()=>response({dates:[]}));
 try {
  const w=dom.window;
  const pick={Giocatore:'Player',Mercato:'PTS',Scelta:'Over',Linea:19.5,Quota:1.8,'Prob. stimata %':75,Partite:20,'Stagione %':70,'Ultime 20':'14/20','Ultime 5':'3/5','Minuti medi':30,'Minuti ultime 5':30};
  w.eval('data = '+JSON.stringify({player_logs:{Player:[{GAME_DATE:'2026-10-25',PTS:18},{GAME_DATE:'2026-10-25',PTS:19}]}}));
  const html=w.pickExplanation(pick);
  assert.doesNotMatch(html,/partite consecutive/);assert.doesNotMatch(html,/2 su 20/);assert.match(html,/70% su 20 partite/);
  w.eval('data = {}');assert.doesNotMatch(w.pickExplanation(pick),/partite consecutive/);
 } finally {dom.window.close()}
});

test('match details use only the matching saved scan and keep a readable logo fallback', async () => {
 const pick={Giocatore:'Test Player','ESPN ID':'22',Squadra:'Boston Celtics',Partita:'Boston Celtics - Miami Heat',Mercato:'AST',Scelta:'Over',Linea:4.5,Quota:1.8,'Prob. stimata %':80,'Stato analisi':'Valutabile (stima empirica)',Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29};
 const saved={date:'2099-01-01',saved_at:'2099-01-01T12:00:00Z',results:[pick],fixture_count:1,player_count:1};
 let timestamp='01/01/2099 13:00:01';
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/latest'))return response(saved);
  if(url.startsWith('/api/saved/time'))return response({saved_at_italy:timestamp,coverage_status:'completa',fixture_reports:[{partita:pick.Partita,inizio_italia:'2099-01-02T01:30:00+01:00'}]});
  return response({state:'waiting'});
 });
 try{
  await tick();await tick();await tick();
  const d=dom.window.document;
  assert.equal(d.querySelector('.fixture-time').hidden,true);
  assert.doesNotMatch(d.getElementById('quote-updated').textContent,/Copertura completa/);
  const img=d.querySelector('.team-logo img');img.onerror();
  assert.match(d.querySelector('.team-logo').textContent,/BOS/);
  timestamp='01/01/2099 13:00:00';
  dom.window.render();await tick();await tick();
  assert.equal(d.querySelector('.fixture-time').hidden,false);
  assert.match(d.querySelector('.fixture-time').textContent,/01:30/);
  assert.doesNotMatch(d.getElementById('quote-updated').textContent,/Copertura completa/);
 }finally{dom.window.close()}
});

test('return from a pick preserves the selected date and returns to forecasts', async () => {
 const pick={Giocatore:'Second Player','ESPN ID':'22',Squadra:'Boston Celtics',Partita:'Boston Celtics - Miami Heat',Mercato:'AST',Scelta:'Over',Linea:4.5,Quota:1.8,'Prob. stimata %':80,'Stato analisi':'Valutabile (stima empirica)',Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29};
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/latest'))return response({date:'2099-01-01',results:[pick],season:'2026-27'});
  if(url==='/api/players/teams')return response({teams:[{id:'2',name:'Boston Celtics'}]});
  if(url.startsWith('/api/players/roster'))return response({players:[{id:'22',name:'Second Player'}]});
  if(url.startsWith('/api/players/log?'))return response({games:[]});
  return response({state:'waiting'});
 });
 try{
  await tick();await tick();const d=dom.window.document;
  d.querySelector('.pick-stats-button').click();await tick();
  assert.equal(d.getElementById('back-to-picks').hidden,false);
  assert.equal(d.getElementById('date-area').hidden,true);
  assert.equal(d.getElementById('area-stats').getAttribute('aria-pressed'),'true');
  d.getElementById('back-to-picks').click();
  assert.equal(d.getElementById('date-area').hidden,false);
  assert.equal(d.getElementById('area-quotes').getAttribute('aria-pressed'),'true');
  assert.equal(d.getElementById('dashboard').hidden,false);
  assert.equal(d.getElementById('date').value,'2099-01-01');
  assert.equal(d.getElementById('back-to-picks').hidden,true);
 }finally{dom.window.close()}
});

test('primary navigation keeps forecast date and last quote tab when switching areas', async () => {
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/latest'))return response({date:'2099-01-01',results:[],fixture_count:0,player_count:0});
  if(url==='/api/players/teams')return response({teams:[]});
  return response({state:'waiting',players:[]});
 });
 try{
  await tick();await tick();const d=dom.window.document;
  d.querySelector('nav button[data-tab="finder"]').click();
  d.getElementById('area-stats').click();
  assert.equal(d.getElementById('date-area').hidden,true);
  assert.equal(d.getElementById('area-stats').getAttribute('aria-pressed'),'true');
  assert.equal(d.getElementById('player').hidden,false);
  assert.equal(d.getElementById('quote-summary').hidden,true);
  d.getElementById('area-quotes').click();
  assert.equal(d.getElementById('date-area').hidden,false);
  assert.equal(d.getElementById('finder').hidden,false);
  assert.equal(d.getElementById('date').value,'2099-01-01');
  assert.equal(d.getElementById('area-quotes').getAttribute('aria-pressed'),'true');
 }finally{dom.window.close()}
});

test('forecast controls precede the date picker and date changes preserve the quote tab', async () => {
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'},{date:'2099-01-02'}]});
  if(url.startsWith('/api/saved/latest'))return response({date:url.includes('2099-01-02')?'2099-01-02':'2099-01-01',results:[],fixture_count:0,player_count:0});
  return response({state:'waiting'});
 });
 try{
  await tick();await tick();const d=dom.window.document;
  assert.ok(d.getElementById('quote-tabs').compareDocumentPosition(d.getElementById('date-area')) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING);
  d.querySelector('nav button[data-tab="finder"]').click();
  d.getElementById('date').value='2099-01-02';d.getElementById('date').dispatchEvent(new dom.window.Event('change'));
  await tick();await tick();
  assert.equal(d.getElementById('finder').hidden,false);
  assert.equal(d.getElementById('date').value,'2099-01-02');
  assert.match(d.getElementById('date-month').textContent,/2099/);
 }finally{dom.window.close()}
});

test('quote search filters only finder results and returns from statistics with filters intact', async () => {
 const base={Squadra:'Boston Celtics',Partita:'Boston Celtics - Miami Heat',Mercato:'AST',Scelta:'Over',Linea:4.5,Quota:1.8,'Prob. stimata %':80,'Value stimato %':44,'Stato analisi':'Valutabile (stima empirica)',Partite:30,'Stagione %':80,'Minuti medi':30,'Minuti ultime 5':29,'Ultime 20':'12/20','Ultime 5':'3/5'};
 const rows=[{...base,Giocatore:'Second Player','ESPN ID':'22'},{...base,Giocatore:'Another Player','ESPN ID':'23'}];
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'}]});
  if(url.startsWith('/api/saved/latest'))return response({date:'2099-01-01',results:rows,season:'2026-27'});
  if(url==='/api/players/teams')return response({teams:[{id:'2',name:'Boston Celtics'}]});
  if(url.startsWith('/api/players/roster'))return response({players:[{id:'22',name:'Second Player'},{id:'23',name:'Another Player'}]});
  if(url.startsWith('/api/players/log?'))return response({games:[{AST:6,PTS:20,REB:3,SEASON_TYPE:2,GAME_DATE:'2026-10-25'}]});
  return response({state:'waiting',logs:{}});
 });
 try{
  await tick();await tick();const d=dom.window.document;
  const picksBefore=d.getElementById('picks').textContent;
  d.querySelector('nav button[data-tab="finder"]').click();
  const search=d.getElementById('finder-search');search.value='PLAYER second';search.dispatchEvent(new dom.window.Event('input'));
  assert.equal(d.querySelectorAll('#finder-cards .finder-card').length,1);
  assert.match(d.getElementById('finder-count').textContent,/1 risultato/);
  assert.match(d.querySelector('#finder-cards .finder-card').textContent,/Second Player/);
  const toggle=d.querySelector('.finder-details-toggle'),extra=d.getElementById(toggle.getAttribute('aria-controls'));
  assert.equal(extra.hidden,true);toggle.click();assert.equal(extra.hidden,false);assert.equal(toggle.getAttribute('aria-expanded'),'true');
  assert.match(extra.textContent,/Ultime 5: 3\/5/);assert.match(extra.textContent,/Storico linea: 80% \(30 partite\)/);assert.match(extra.textContent,/Minuti medi: 30/);assert.doesNotMatch(extra.textContent,/Minuti ultime 5/);
  assert.ok(d.querySelector('.finder-heading .finder-guide summary[aria-label="Come leggere i dati"]'));
  toggle.click();assert.equal(extra.hidden,true);assert.equal(toggle.getAttribute('aria-expanded'),'false');
  assert.equal(d.getElementById('picks').textContent,picksBefore);
  d.querySelector('#finder-cards .finder-player').click();await tick();await tick();await tick();
  assert.equal(d.getElementById('playername').value,'22');assert.equal(d.getElementById('stat').value,'AST');assert.equal(d.getElementById('line').value,'4.5');
  assert.match(d.getElementById('back-to-picks').textContent,/Analisi quote/);
  d.getElementById('back-to-picks').click();
  assert.equal(d.getElementById('finder').hidden,false);assert.equal(search.value,'PLAYER second');
  assert.equal(d.querySelectorAll('#finder-cards .finder-card').length,1);
 }finally{dom.window.close()}
});

test('no saved data clears mobile finder results on date change', async () => {
 const row={Giocatore:'Test Player',Squadra:'Boston Celtics',Partita:'Boston Celtics - Miami Heat',Mercato:'PTS',Linea:9.5,Quota:1.8,'Prob. stimata %':80,'Stato analisi':'Valutabile (stima empirica)'};
 const dom=browser(async url=>{
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'},{date:'2099-01-02'}]});
  if(url.includes('latest?date=2099-01-02'))return {ok:false,status:404};
  if(url.startsWith('/api/saved/latest'))return response({date:'2099-01-01',results:[row]});
  return response({state:'waiting'});
 });
 try{
  await tick();await tick();const d=dom.window.document;
  assert.equal(d.querySelectorAll('#finder-cards .finder-card').length,1);
  d.getElementById('date').value='2099-01-02';d.getElementById('date').dispatchEvent(new dom.window.Event('change'));
  await tick();await tick();assert.equal(d.querySelectorAll('#finder-cards .finder-card').length,0);
 }finally{dom.window.close()}
});

test('date wheel selects available days with buttons and keyboard without starting scans', async () => {
 const calls=[];
 const dom=browser(async url=>{
  calls.push(url);
  if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'},{date:'2099-01-02'},{date:'2099-01-04'}]});
  if(url.startsWith('/api/saved/latest'))return response({date:(new URL(url,'https://nba.invalid')).searchParams.get('date'),results:[],fixture_count:0,player_count:0});
  return response({state:'waiting'});
 });
 try{
  await tick();await tick();const d=dom.window.document;
  assert.equal(d.getElementById('date').value,'2099-01-01');
  assert.equal(d.getElementById('date-prev').disabled,true);
  assert.equal(d.querySelector('.wheel-previous'),null);
  d.getElementById('date-next').click();await tick();await tick();
  assert.equal(d.getElementById('date').value,'2099-01-02');
  assert.equal(d.querySelector('.wheel-previous').dataset.date,'2099-01-01');
  assert.equal(d.querySelector('.wheel-selected').dataset.date,'2099-01-02');
  assert.equal(d.querySelector('.wheel-selected .day-month').textContent,'GEN');
  assert.equal(d.querySelector('.wheel-selected .day-name').textContent,'VENERDÌ');
  assert.equal(d.querySelector('.wheel-next').dataset.date,'2099-01-04');
  d.getElementById('date-strip').dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));await tick();await tick();
  assert.equal(d.getElementById('date').value,'2099-01-04');
  assert.equal(d.getElementById('date-next').disabled,true);
  assert.equal(d.querySelector('.wheel-next'),null);
  assert.ok(calls.every(url=>!url.includes('/api/scan')));
 }finally{dom.window.close()}
});


test('horizontal swipes change only available saved dates and leave vertical gestures alone', async () => {
 const calls=[];const dom=browser(async url=>{calls.push(url);if(url==='/api/saved/dates')return response({dates:[{date:'2099-01-01'},{date:'2099-01-02'}]});if(url.startsWith('/api/saved/latest'))return response({results:[],fixture_count:0,player_count:0});return response({state:'waiting'});});
 try{await tick();await tick();const d=dom.window.document,area=d.querySelector('#date-area .wheel-panel');
 const gesture=(x1,y1,x2,y2)=>{for(const [type,x,y] of [['pointerdown',x1,y1],['pointerup',x2,y2]]){const e=new dom.window.Event(type,{bubbles:true});Object.assign(e,{pointerId:1,pointerType:'touch',clientX:x,clientY:y});area.dispatchEvent(e);}};
 gesture(150,100,80,105);await tick();await tick();assert.equal(d.getElementById('date').value,'2099-01-02');
 gesture(80,100,90,160);assert.equal(d.getElementById('date').value,'2099-01-02');
 gesture(80,100,150,105);await tick();await tick();assert.equal(d.getElementById('date').value,'2099-01-01');
 assert.ok(calls.every(url=>!url.includes('/api/scan')));
 }finally{dom.window.close()}
});

test('statistics venue filters, game details and recent denominators use known dated games', async () => {
 const dom=browser(async url=>response(url==='/api/saved/dates'?{dates:[]}:{}));
 try{
  const w=dom.window,d=w.document;
  w.__audit.setPlayerGames([
   {GAME_DATE:'2026-10-25',SEASON_TYPE:2,MATCHUP:'vs BOS',PTS:15,REB:3,AST:2,MIN:28},
   {GAME_DATE:'2026-10-24',SEASON_TYPE:2,MATCHUP:'@ NYK',PTS:8,REB:2,AST:1,MIN:31.5},
   {GAME_DATE:'2026-10-23',SEASON_TYPE:2,MATCHUP:'? LAL',PTS:20,REB:4,AST:2,MIN:null},
   {GAME_DATE:null,SEASON_TYPE:2,MATCHUP:'vs CHI',PTS:25,REB:2,AST:1,MIN:20}
  ]);
  d.getElementById('line').innerHTML='<option value="9.5">9.5</option>';d.getElementById('line').value='9.5';
  d.getElementById('playerwindow').value='20';w.drawPlayer();
  assert.match(d.getElementById('player-summary').textContent,/2\/3/);
  assert.match(d.getElementById('player-trends').textContent,/2\/3/);
  assert.match(d.getElementById('player-trends').textContent,/1 partita senza data/);
  assert.match(d.getElementById('chart').textContent,/vs BOS · 28 min/);
  assert.match(d.getElementById('chart').textContent,/@ NYK · 31.5 min/);
  assert.match(d.getElementById('chart').textContent,/LAL · min n.d./);
  d.getElementById('player-venue').value='home';w.drawPlayer();
  assert.match(d.getElementById('player-summary').textContent,/1\/1/);
  assert.doesNotMatch(d.getElementById('chart').textContent,/NYK|LAL/);assert.match(d.getElementById('player-trends').textContent,/campo non verificato/);
  d.getElementById('player-venue').value='away';w.drawPlayer();
  assert.match(d.getElementById('player-summary').textContent,/0\/1/);
  assert.doesNotMatch(d.getElementById('chart').textContent,/BOS|LAL/);
 }finally{dom.window.close()}
});
