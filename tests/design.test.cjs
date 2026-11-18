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

test('minutes stay in candle details without a separate chart',()=>{
 const dom=new JSDOM('<div id="player-visual"></div>',{runScripts:'outside-only'});
 try{const w=dom.window;w.eval(fs.readFileSync('web/modules/design.js','utf8'));
 w.BasketLabDesign.playerChart([{GAME_DATE:'2026-11-03',PTS:20,MIN:30},{GAME_DATE:'2026-11-02',PTS:10,MIN:null},{GAME_DATE:'2026-11-01',PTS:0,MIN:0}],'PTS',15.5,25);
 const d=w.document;assert.equal(d.querySelector('.bl-minutes-plot'),null);
 const bars=d.querySelectorAll('.bl-chart-column');bars[0].click();
 assert.equal(d.querySelectorAll('.bl-chart-detail-metrics b')[1].textContent,'0');
 bars[1].click();assert.equal(d.querySelectorAll('.bl-chart-detail-metrics b')[1].textContent,'Non disponibili');
 }finally{dom.window.close();}
});

test('20 games fit as one sample while full seasons retain every game and scrolling controls',()=>{
 const dom=new JSDOM('<div id="player-visual"></div>',{runScripts:'outside-only'});
 try{
  const w=dom.window,d=w.document;w.eval(fs.readFileSync('web/modules/design.js','utf8'));
  const games=Array.from({length:30},(_,i)=>({GAME_DATE:new Date(Date.UTC(2026,10,18-i)).toISOString().slice(0,10),PTS:i+1,MIN:30,MATCHUP:'vs BOS'})),before=JSON.stringify(games);
  w.BasketLabDesign.playerChart(games.slice(0,20),'PTS',15.5,31);
  assert.equal(d.querySelectorAll('.bl-chart-column').length,20);assert.ok(d.querySelector('.bl-chart-fit.bl-chart-dense'));
  assert.equal(d.querySelector('.bl-chart-plot').style.minWidth,'0px');assert.equal(d.querySelector('.bl-chart-navigation'),null);
  assert.equal(d.querySelectorAll('.bl-chart-date-secondary').length,15);
  w.BasketLabDesign.playerChart(games,'PTS',15.5,31);
  assert.equal(d.querySelectorAll('.bl-chart-column').length,30);assert.ok(d.querySelector('.bl-chart-wide'));
  assert.equal(d.querySelectorAll('.bl-chart-bar b')[0].textContent,'30');assert.equal(d.querySelectorAll('.bl-chart-bar b')[29].textContent,'1');
  assert.equal(d.querySelector('#bl-chart-position').getAttribute('aria-label'),'Scorri il grafico delle partite');
  d.querySelector('.bl-chart-column').click();assert.equal(d.querySelector('.bl-chart-detail-metrics b').textContent,'30 punti');
  assert.equal(JSON.stringify(games),before);
 }finally{dom.window.close();}
});
