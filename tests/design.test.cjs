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

test('selected chart game has a readable date, expanded opponent and separate real metrics',()=>{
 const dom=new JSDOM('<div id="player-visual"></div>',{runScripts:'outside-only'});
 try{
  const w=dom.window;w.eval(fs.readFileSync('web/modules/design.js','utf8'));
  const games=[{GAME_DATE:'2026-10-25',PTS:7,MIN:37,MATCHUP:'vs NO'},{GAME_DATE:'2026-10-23',PTS:20,MIN:0,MATCHUP:'@ OKC'}];
  w.BasketLabDesign.playerChart(games,'PTS',15.5,25);
  const d=w.document,buttons=d.querySelectorAll('.bl-chart-column');buttons[1].click();
  assert.equal(d.querySelector('.bl-chart-detail-date').textContent,'25 ottobre 2026');
  assert.equal(d.querySelector('.bl-chart-detail-fixture').textContent,'In casa contro New Orleans Pelicans');
  assert.deepEqual([...d.querySelectorAll('.bl-chart-detail-metrics b')].map(n=>n.textContent),['7 punti','37','15,5']);
  assert.equal(d.querySelector('.bl-chart-detail-outcome').textContent,'Linea non superata');
  buttons[0].click();
  assert.equal(buttons[1].getAttribute('aria-pressed'),'false');assert.equal(buttons[0].getAttribute('aria-pressed'),'true');
  assert.equal(d.querySelector('.bl-chart-detail-fixture').textContent,'In trasferta contro Oklahoma City Thunder');
  assert.equal(d.querySelectorAll('.bl-chart-detail-metrics b')[1].textContent,'0');
  assert.equal(d.querySelector('.bl-chart-detail-outcome').textContent,'Linea superata');
 }finally{dom.window.close();}
});

test('minutes chart aligns games and does not treat missing minutes as zero',()=>{
 const dom=new JSDOM('<div id="player-visual"></div>',{runScripts:'outside-only'});
 try{const w=dom.window;w.eval(fs.readFileSync('web/modules/design.js','utf8'));
 w.BasketLabDesign.playerChart([{GAME_DATE:'2026-11-03',PTS:20,MIN:30},{GAME_DATE:'2026-11-02',PTS:10,MIN:null},{GAME_DATE:'2026-11-01',PTS:0,MIN:0}],'PTS',15.5,25);
 const d=w.document;assert.deepEqual([...d.querySelectorAll('.bl-minutes-cell span')].map(n=>n.textContent),['0','—','30']);
 assert.match(d.querySelector('.bl-minutes-heading').textContent,/media 15 \(2 partite\)/);
 assert.equal(d.querySelector('.bl-minutes-plot').style.minWidth,d.querySelector('.bl-chart-plot').style.minWidth);
 }finally{dom.window.close();}
});
