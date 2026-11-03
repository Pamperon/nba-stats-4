const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
test('visual chart reuses filtered game values and threshold without modifying games',()=>{
 const dom=new JSDOM('<div id="player-visual" hidden></div><select id="stat"><option>PTS</option></select>',{runScripts:'outside-only'});
 try{
  const w=dom.window;w.eval(fs.readFileSync('web/modules/design.js','utf8'));
  const games=[{GAME_DATE:'2026-11-02',PTS:28},{GAME_DATE:'2026-11-01',PTS:20}],before=JSON.stringify(games);
  w.BasketLabDesign.playerChart(games,'PTS',24.5,30);
  const d=w.document;assert.equal(d.getElementById('player-visual').hidden,false);
  assert.deepEqual([...d.querySelectorAll('.bl-chart-bar b')].map(n=>n.textContent),['20','28']);
  assert.equal(d.querySelectorAll('.is-over').length,1);assert.match(d.querySelector('.bl-chart-threshold').textContent,/24,5/);
  assert.equal(JSON.stringify(games),before);w.BasketLabDesign.playerChart([],'PTS',24.5,30);assert.equal(d.getElementById('player-visual').hidden,true);
 }finally{dom.window.close();}
});
