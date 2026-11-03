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
