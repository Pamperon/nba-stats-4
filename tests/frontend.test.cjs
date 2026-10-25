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

test('failed attempt shows previous saved data time and uncertain API attempts separately', () => {
  const dom = browser(async () => response({dates: []}));
  try {
    dom.window.renderScanStatus({state:'error',latest_attempt:{state:'error',started_at:'2026-10-25T16:00:00Z',api_requests:{logged:5,responded:4,uncertain:1}},last_saved:{state:'done',saved_at:'2026-10-25T11:48:00Z'}});
    const d=dom.window.document;
    assert.equal(d.getElementById('scan-state').textContent,'Fallita');
    assert.match(d.getElementById('scan-attempt').textContent,/17:00/);
    assert.match(d.getElementById('scan-saved').textContent,/12:48/);
    assert.match(d.getElementById('scan-usage').textContent,/5 · 1 da verificare/);
  } finally {dom.window.close();}
});

test('running and partial status remain distinct from a completed update', () => {
  const dom = browser(async () => response({dates: []}));
  try {
    const w=dom.window,d=w.document;
    w.renderScanStatus({state:'running',latest_attempt:{state:'running',progress:45,started_at:'2026-10-25T16:00:00Z',api_requests:{logged:2,responded:1,uncertain:1}},last_saved:null});
    assert.equal(d.getElementById('scan-state').textContent,'In elaborazione');
    assert.match(d.getElementById('scan-attempt').textContent,/45%/);
    assert.doesNotMatch(d.getElementById('scan-usage').textContent,/da verificare/);
    w.renderScanStatus({state:'partial',last_saved:{state:'partial',saved_at:'2026-10-25T16:10:00Z',api_requests:4}});
    assert.equal(d.getElementById('scan-state').textContent,'Parziale');
    assert.match(d.getElementById('scan-saved').textContent,/parziali/);
  } finally {dom.window.close();}
});

test('delayed status for an old date cannot replace the selected date status', async () => {
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
    assert.equal(d.getElementById('scan-state').textContent,'Completata');
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
    assert.equal(dom.window.document.getElementById('scan-state').textContent,'Completata');
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
    assert.equal(dom.window.document.getElementById('scan-state').textContent,'Stato temporaneamente non disponibile');
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
    assert.equal(dom.window.document.getElementById('scan-state').textContent,'In elaborazione');
    assert.equal(timers[1].delay,15000);
  }finally{dom.window.close();}
});
