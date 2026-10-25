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
