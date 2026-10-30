const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const script=fs.readFileSync('web/audience.js','utf8');
function setup(options={}){
 const dom=new JSDOM('<button data-tab="finder">Quote</button><input id="finder-search"><div id="finder"><select id="market"><option>PTS</option></select></div>',{url:'https://basketlab.it/?utm_source=whatsapp',runScripts:'outside-only',pretendToBeVisual:true});
 const calls=[];dom.window.fetch=(url,config)=>{calls.push({url,config,body:JSON.parse(config.body)});return Promise.resolve({ok:true});};
 dom.window.setInterval=()=>0;
 if(options.dnt)Object.defineProperty(dom.window.navigator,'doNotTrack',{value:'1'});
 dom.window.eval(script);return {dom,calls};
}
test('aggregate payload excludes visitor identifiers and query content',()=>{
 const {dom,calls}=setup();assert.deepEqual(calls[0].body,{source:'whatsapp',events:['apertura']});
 dom.window.document.querySelector('button').click();dom.window.document.querySelector('button').click();
 dom.window.dispatchEvent(new dom.window.Event('pagehide'));
 assert.deepEqual(calls[1].body.events,['quote']);assert.equal(calls[1].config.credentials,'omit');
 assert.equal(dom.window.localStorage.length,0);assert.equal(dom.window.document.cookie,'');dom.window.close();
});
test('privacy opt-out suppresses collection',()=>{const {dom,calls}=setup({dnt:true});assert.equal(calls.length,0);dom.window.close();});
function privacySetup(options={}){
 const dom=new JSDOM('<button id="audience-settings" hidden></button><section id="audience-preferences" hidden><button id="audience-accept"></button><button id="audience-decline"></button></section>',{url:'https://basketlab.it/',runScripts:'outside-only',pretendToBeVisual:true});
 const calls=[];const w=dom.window;
 w.fetch=(url,config)=>{calls.push({url,body:JSON.parse(config.body)});return Promise.resolve({ok:true});};
 let timer;w.setInterval=fn=>{timer=fn;return 0;};
 if(options.choice)w.localStorage.setItem('basketlab:audience-choice:v1',JSON.stringify({value:options.choice,at:Date.now()}));
 if(options.saved)w.localStorage.setItem('basketlab:audience-day:v1',JSON.stringify(options.saved));
 if(options.dnt)Object.defineProperty(w.navigator,'doNotTrack',{value:'1'});
 if(options.blocked)w.Storage.prototype.setItem=()=>{throw Error('blocked');};
 w.eval(script);return {dom,calls,timer:()=>timer?.()};
}
function dayRome(){const p=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const get=t=>p.find(x=>x.type===t).value;return get('year')+'-'+get('month')+'-'+get('day');}
test('no daily identifier before consent; acceptance counts once and revocation removes it',()=>{
 const {dom,calls,timer}=privacySetup(),w=dom.window,d=w.document;
 assert.equal(calls.filter(c=>c.url.endsWith('/unique')).length,0);assert.equal(w.localStorage.length,0);assert.equal(d.getElementById('audience-preferences').hidden,false);
 d.getElementById('audience-accept').click();timer();
 const uniques=calls.filter(c=>c.url.endsWith('/unique'));assert.equal(uniques.length,1);assert.match(uniques[0].body.id,/^[0-9a-f]{32}$/);assert.equal(uniques[0].body.day,dayRome());
 d.getElementById('audience-settings').click();d.getElementById('audience-decline').click();timer();assert.equal(w.localStorage.getItem('basketlab:audience-day:v1'),null);assert.equal(calls.filter(c=>c.url.endsWith('/unique')).length,1);dom.window.close();
});
test('same-day reload retains ID; new Italian day rotates ID',()=>{
 const id='a'.repeat(32);
 for(const day of [dayRome(),'2020-01-01']){
  const {dom,calls}=privacySetup({choice:'yes',saved:{day,id}}),u=calls.find(c=>c.url.endsWith('/unique'));
  assert.ok(u);assert.equal(u.body.day,dayRome());if(day===dayRome())assert.equal(u.body.id,id);else assert.notEqual(u.body.id,id);dom.window.close();
 }
});
test('DNT overrides prior consent and blocked storage omits unique counts',()=>{
 for(const options of [{choice:'yes',dnt:true,saved:{day:dayRome(),id:'b'.repeat(32)}},{choice:'yes',blocked:true}]){
  const {dom,calls}=privacySetup(options);assert.equal(calls.filter(c=>c.url.endsWith('/unique')).length,0);assert.equal(dom.window.localStorage.getItem('basketlab:audience-day:v1'),null);dom.window.close();
 }
});
test('cross-tab revocation stops unique requests after midnight',()=>{
 const {dom,calls,timer}=privacySetup({choice:'yes'}),w=dom.window;
 w.dispatchEvent(new w.StorageEvent('storage',{key:'basketlab:audience-choice:v1',newValue:JSON.stringify({value:'no',at:Date.now()})}));
 timer();assert.equal(w.localStorage.getItem('basketlab:audience-day:v1'),null);assert.equal(calls.filter(c=>c.url.endsWith('/unique')).length,1);w.close();
});
test('admin separates daily unique sum from total opens and marks older dates unavailable',async()=>{
 const html=fs.readFileSync('web/audience-admin.html','utf8');const dom=new JSDOM(html,{url:'https://basketlab.it/admin/visite',runScripts:'outside-only'}),w=dom.window;
 w.fetch=async()=>({ok:true,json:async()=>({unique_since:'2026-10-30',unique_daily:[{day:'2026-10-30',total:2},{day:'2026-10-31',total:3}],rows:[{day:'2026-10-29',event:'apertura',source:'diretto',total:9},{day:'2026-10-30',event:'apertura',source:'google',total:7}]})});
 w.eval(fs.readFileSync('web/audience-admin.js','utf8'));w.document.getElementById('login').dispatchEvent(new w.Event('submit',{cancelable:true}));
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(w.document.getElementById('summary').textContent,/5 somma degli unici giornalieri.*16 aperture/);
 const rows=[...w.document.querySelectorAll('#uniques tr')].map(r=>r.textContent);assert.equal(rows.length,3);assert.match(rows[2],/2026-10-29—9/);assert.doesNotMatch(w.document.body.textContent,/undefined|NaN/);w.close();
});
