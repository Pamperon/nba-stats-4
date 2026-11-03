const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('web/modules/sections.js','utf8');
const tick=()=>new Promise(r=>setImmediate(r));
test('only visible section loaders run, shared views reuse recent data',async()=>{
 const dom=new JSDOM('<body data-hub-view="history">',{url:'https://basketlab.it/archivio',runScripts:'outside-only'});
 try{
  const w=dom.window;w.eval(source);const calls=[];
  for(const name of ['picks','quotes','home'])w.BasketLabSections.register(name,async()=>calls.push(name));
  await tick();assert.deepEqual(calls,[]);
  w.document.body.dataset.hubView='home';w.document.dispatchEvent(new w.Event('basketlab:view'));await tick();
  assert.deepEqual(calls,['picks','home']);
  w.document.body.dataset.hubView='picks';w.document.dispatchEvent(new w.Event('basketlab:view'));await tick();
  assert.deepEqual(calls,['picks','home']);
  w.document.body.dataset.hubView='finder';w.document.dispatchEvent(new w.Event('basketlab:view'));await tick();
  assert.deepEqual(calls,['picks','home','quotes']);
 }finally{dom.window.close();}
});
test('an in-flight loader is shared and a failed loader can retry',async()=>{
 const dom=new JSDOM('<body data-hub-view="home">',{url:'https://basketlab.it',runScripts:'outside-only'});
 try{
  const w=dom.window;w.eval(source);let calls=0,release;
  w.BasketLabSections.register('picks',()=>{calls++;return new Promise((resolve,reject)=>release=reject);});
  await tick();w.BasketLabSections.run('picks');assert.equal(calls,1);
  release(new Error('temporary'));await tick();
  w.BasketLabSections.run('picks');await tick();assert.equal(calls,2);
  release(new Error('temporary'));await tick();
 }finally{dom.window.close();}
});
