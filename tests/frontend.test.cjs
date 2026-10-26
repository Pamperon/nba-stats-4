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
  dom.window.eval(source + '\nwindow.__audit = {getData: () => data, getPlayerInit: () => playerStatsInitialized, setPlayerInit: value => {playerStatsInitialized = value;}};');
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
  const handlers = serviceWorker(null, {
    keys: async () => ['nba-stats-4-shell-v2', 'nba-stats-4-shell-v3', 'other-app-cache'],
    delete: async key => deleted.push(key),
  });
  let task;
  handlers.activate({waitUntil: promise => {task = promise;}});
  await task;
  assert.deepEqual(deleted, ['nba-stats-4-shell-v2']);
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
    assert.equal(w.sessionStorage.getItem('nba-player-log:player'), null);
  } finally {dom.window.close();}
});

test('restoring session cache does not restart its fifteen minute lifetime', () => {
  const dom = browser(async () => response({dates: []}));
  try {
    const w = dom.window, at = 1000000000000;
    let now = at + 14 * 60 * 1000;
    w.Date.now = () => now;
    w.sessionStorage.setItem('nba-player-log:player', JSON.stringify({at, payload: {games: []}}));
    assert.ok(w.getPlayerLogCache('player'));
    now = at + 15 * 60 * 1000;
    assert.equal(w.getPlayerLogCache('player'), null);
    w.sessionStorage.setItem('nba-player-log:bad', JSON.stringify({at: 'invalid', payload: {}}));
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
