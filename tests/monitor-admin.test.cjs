const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const html=fs.readFileSync('web/monitor-admin.html','utf8');
const script=fs.readFileSync('web/monitor-admin.js','utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(fetch){const dom=new JSDOM(html,{url:'https://basketlab.it/admin/monitor',runScripts:'outside-only'});dom.window.fetch=fetch;dom.window.eval(script);return dom;}
const data={coverage:[{date:'2026-11-01',expected:10,matched:9,gap:1,coverage_pct:90}],calibration:[],scans:[{date:'2026-11-01',state:'partial',odds_fetched_at:null,odds_source:'cache',http_requests:1,quote_lines:250,timings:{},issues:['<img src=x onerror=alert(1)>']}],attempts:[],odds_requests_24h:{success:1},generated_at:'2026-11-02T12:00Z',calibration_note:'Osservazioni correlate'};
test('monitor protects credentials from storage, escapes diagnostics and clears data on logout',async()=>{
 let options;const dom=setup(async(url,opts)=>{assert.equal(url,'/api/admin/monitor');options=opts;return {ok:true,json:async()=>data};});
 try{const d=dom.window.document;d.getElementById('key').value='private-test';d.getElementById('login').dispatchEvent(new dom.window.Event('submit',{cancelable:true}));await tick();
 assert.equal(options.cache,'no-store');assert.equal(options.headers.Authorization,'Bearer private-test');
 assert.equal(d.getElementById('data').hidden,false);assert.equal(d.querySelector('#issues img'),null);assert.match(d.getElementById('issues').textContent,/<img/);
 assert.equal(dom.window.localStorage.length,0);assert.equal(dom.window.sessionStorage.length,0);
 d.getElementById('logout').click();assert.equal(d.getElementById('data').hidden,true);assert.equal(d.getElementById('key').value,'');assert.equal(d.getElementById('coverage').children.length,0);
 }finally{dom.window.close();}
});
test('logout prevents a late response from redisplaying private data',async()=>{
 let resolve;const dom=setup(()=>new Promise(r=>{resolve=r}));
 try{const d=dom.window.document;d.getElementById('key').value='test';d.getElementById('login').dispatchEvent(new dom.window.Event('submit',{cancelable:true}));d.getElementById('logout').click();resolve({ok:true,json:async()=>data});await tick();assert.equal(d.getElementById('data').hidden,true);assert.equal(d.getElementById('coverage').children.length,0);}finally{dom.window.close();}
});
