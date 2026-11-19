const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const counts=(won,lost,dnp=0,pending=0)=>({published:won+lost+dnp+pending,verified:won+lost,won,lost,not_played:dnp,pending,success_pct:won+lost?100*won/(won+lost):null});
const group=(won,lost,dnp=1,pending=1)=>({...counts(won,lost,dnp,pending),unclassified:0,by_market:{PTS:counts(won,lost),REB:counts(0,0,dnp,pending),AST:counts(0,0)}});
test('performance panel separates categories, uses settled samples, and supports updates, empty and error states',()=>{
 const dom=new JSDOM('<button id="source">Rendimento</button>',{runScripts:'outside-only',pretendToBeVisual:true});
 try{
  const w=dom.window,d=w.document;let style=0,retries=0;
  w.fetch=()=>{throw Error('Panel must reuse aggregates')};w.BasketLabAssets={style:()=>style++};
  w.eval(fs.readFileSync('web/modules/performance-view.js','utf8'));
  const data={breakdown:{single:group(3,1),others:group(2,3)}};
  w.BasketLabPerformance.open(data,d.getElementById('source'),()=>retries++);
  assert.equal(style,1);assert.match(d.querySelector('.bl-performance-summary').textContent,/75%3 centrate su 4 verificate/);
  const tabs=d.querySelectorAll('[role=tab]');assert.equal(tabs[0].getAttribute('aria-selected'),'true');tabs[1].click();
  assert.match(d.querySelector('.bl-performance-summary').textContent,/40%2 centrate su 5 verificate/);
  assert.equal(d.querySelectorAll('.bl-performance-market').length,3);
  assert.match(d.querySelectorAll('.bl-performance-market')[1].textContent,/Rimbalzi—0 su 0 verificate/);
  assert.match(d.querySelectorAll('.bl-performance-market')[2].textContent,/Nessuna analisi pubblicata/);
  tabs[1].dispatchEvent(new w.KeyboardEvent('keydown',{key:'Home',bubbles:true}));assert.equal(d.activeElement,tabs[0]);
  w.BasketLabPerformance.update(undefined);assert.equal(d.querySelector('[role=tabpanel]').getAttribute('aria-busy'),'true');
  w.BasketLabPerformance.update(null);d.querySelector('.bl-performance-retry').click();assert.equal(retries,1);
  w.BasketLabPerformance.update({breakdown:{single:group(0,0,0,0),others:group(0,0,0,0)}});assert.match(d.querySelector('[role=tabpanel]').textContent,/Nessuna scelta del giorno pubblicata/);
  d.querySelector('.bl-performance-close').click();assert.equal(d.querySelector('dialog').hasAttribute('open'),false);assert.equal(d.activeElement.id,'source');assert.equal(d.documentElement.classList.contains('bl-performance-modal-open'),false);
 }finally{dom.window.close();}
});
