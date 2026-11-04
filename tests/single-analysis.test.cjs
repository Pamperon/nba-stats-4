'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const script=fs.readFileSync('web/modules/single-analysis.js','utf8');
const single=name=>({date:'2026-11-04',state:'preview',selection:{Giocatore:name,'ESPN ID':'1966',Partita:'A - B',Mercato:'PTS',Scelta:'Over',Linea:14.5,Quota:1.9,'Prob. stimata %':74,Partite:20,'Minuti medi':32,'Minuti ultime 5':33,'Disponibilità ESPN':'not-listed'},games:[{GAME_DATE:'2026-11-01',PTS:18},{GAME_DATE:'2026-11-02',PTS:12}]});
test('one analysis container replaces the previous player and keeps saved prices and graph',()=>{
 const dom=new JSDOM('<main id="analysis"></main>',{runScripts:'outside-only'});try{
  dom.window.eval(script);const panel=dom.window.document.querySelector('main');
  dom.window.BasketLabSingleAnalysis.render(panel,single('James, LeBron'),()=>{});
  assert.match(panel.textContent,/LeBron James/);assert.match(panel.textContent,/1,9/);assert.ok(panel.querySelector('svg'));assert.match(panel.querySelector('.sa-history-summary').textContent,/1\/2/);
  const next=single('Castle, Stephon');next.state='official';dom.window.BasketLabSingleAnalysis.render(panel,next,()=>{});
  assert.doesNotMatch(panel.textContent,/LeBron/);assert.match(panel.textContent,/Stephon Castle/);assert.equal(panel.querySelector('.bl-publication-badge').textContent,'Ufficiale');
 }finally{dom.window.close()}
});
test('missing history is disclosed instead of inventing performances',()=>{
 const dom=new JSDOM('<main></main>',{runScripts:'outside-only'});try{dom.window.eval(script);const p=single('<script>invalid</script>');p.games=[];const panel=dom.window.document.querySelector('main');dom.window.BasketLabSingleAnalysis.render(panel,p,()=>{});assert.equal(panel.querySelectorAll('script').length,0);assert.match(panel.textContent,/Storico salvato non disponibile/);assert.equal(panel.querySelector('svg'),null);}finally{dom.window.close()}
});
