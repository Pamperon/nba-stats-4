const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const {JSDOM}=require('jsdom');
const root=path.join(__dirname,'..'),html=fs.readFileSync(path.join(root,'web/index.html'),'utf8'),tick=()=>new Promise(r=>setImmediate(r));
const row={'ESPN ID':'22',Giocatore:'Test, Alex',Squadra:'Boston Celtics',Partita:'Boston Celtics - Atlanta Hawks',Mercato:'PTS',Linea:10.5,Scelta:'Over',Quota:1.9};
function setup(url='https://basketlab.it/giocatori',options={}){
 const dom=new JSDOM(html,{url,runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,d=w.document,calls=[];w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=function(){};
 w.BasketLabSections={register(){},wants(){return false}};
 w.fetch=async u=>{calls.push(String(u));let p={};if(u==='/api/players/explorer'&&options.quoteError)throw Error('Quotes offline');if(u==='/api/players/explorer')p={date:'2026-11-05',rows:options.rows||[row],logs:{'Test, Alex':[{GAME_DATE:'2026-11-01',PTS:20},{GAME_DATE:'2026-10-30',PTS:8}]}};
 else if(u==='/api/players/directory')p={players:[{id:'22',name:'Alex Test',team:'Boston Celtics',team_id:'2'},{id:'33',name:'Other Player',team:'Boston Celtics',team_id:'2'}]};
 else if(u==='/api/players/teams')p={teams:[{id:'2',name:'Boston Celtics'}]};
 else if(String(u).startsWith('/api/players/roster'))p={players:[{id:'22',name:'Alex Test'},{id:'33',name:'Other Player'}]};
 else if(String(u).startsWith('/api/players/team-logs'))p={logs:{}};
 else if(String(u).startsWith('/api/players/log?'))p={games:[{GAME_DATE:'2026-11-01',PTS:20,REB:5,AST:2,MIN:30,SEASON_TYPE:2,MATCHUP:'vs ATL'},{GAME_DATE:'2026-10-30',PTS:8,REB:3,AST:5,MIN:28,SEASON_TYPE:2,MATCHUP:'@ ATL'}]};
 return {ok:true,json:async()=>p};};
 for(const file of ['web/modules/router.js','web/modules/design.js','web/app.js','web/modules/match-charts.js','web/modules/match-data.js','web/modules/calendar-data.js','web/modules/player-explorer.js','web/hub-nav.js'])w.eval(fs.readFileSync(path.join(root,file),'utf8'));
 return {dom,w,d,calls};
}
test('directory opens real player route, keeps exact line, and returns to filtered list',async()=>{const {dom,w,d,calls}=setup();try{
 for(let n=0;n<12;n++)await tick();
 assert.equal(d.querySelector('#app').hidden,true);assert.equal(d.querySelector('#players-explorer').hidden,false);
 assert.equal(d.querySelectorAll('.pe-player-row').length,2);assert.equal(d.querySelectorAll('.pe-catalog-row').length,1);assert.equal(d.querySelector('#pe-include-unpriced'),null);assert.equal(d.querySelectorAll('.pe-spark i').length,2);
 d.querySelector('.pe-player-row').click();for(let n=0;n<15;n++)await tick();
 assert.match(w.location.pathname,/\/giocatori\/alex-test-22$/);assert.equal(d.querySelector('#line').value,'10.5');assert.equal(d.querySelector('#players-explorer').hidden,true);assert.equal(d.querySelector('#player').hidden,false);
 assert.equal(d.querySelectorAll('.pe-quote-option').length,1);assert.equal(d.querySelector('#player-season-stats').parentElement.id,'player-profile');assert.equal(d.querySelector('#player-profile').textContent.includes(row.Partita),false);assert.match(d.querySelector('.pe-quote-fixture').textContent,/Boston Celtics - Atlanta Hawks/);assert.match(d.querySelector('[data-player-window="5"]').textContent,/50%/);
 assert.equal(calls.filter(x=>x.startsWith('/api/players/log?')).length,1);
 d.querySelector('#pe-personal-heading [data-hub="stats"]').click();for(let n=0;n<5;n++)await tick();assert.equal(w.location.pathname,'/giocatori');assert.equal(d.querySelector('#players-explorer').hidden,false);
 }finally{dom.window.close();}});
test('direct personal URL restores verified player and filters without an arbitrary roster default',async()=>{const {dom,w,d}=setup('https://basketlab.it/giocatori/alex-test-22?mercato=AST&linea=2.5&periodo=5');try{for(let n=0;n<20;n++)await tick();assert.equal(d.querySelector('#playername').value,'22');assert.equal(d.querySelector('#stat').value,'AST');assert.equal(d.querySelector('#line').value,'2.5');assert.equal(d.querySelector('#playerwindow').value,'5');assert.match(d.querySelector('#player-summary').textContent,/1\/2/);assert.match(w.location.pathname,/alex-test-22/);}finally{dom.window.close();}});
test('missing quote history stays empty and full directory search opens players without quotes',async()=>{const {dom,w,d}=setup();try{for(let n=0;n<10;n++)await tick();d.querySelector('#pe-search').value='Other';d.querySelector('#pe-search').dispatchEvent(new w.Event('input'));for(let n=0;n<6;n++)await tick();assert.equal(d.querySelectorAll('.pe-player-row:not(.pe-catalog-row)').length,0);assert.match(d.querySelector('.pe-catalog-row').textContent,/Other Player/);d.querySelector('.pe-catalog-row').click();for(let n=0;n<15;n++)await tick();assert.equal(d.querySelector('#playername').value,'33');assert.match(d.querySelector('#pe-player-quotes').textContent,/Nessuna quota disponibile/);}finally{dom.window.close();}});
test('player codec uses stable identity, filters and legacy statistics URL',()=>{const {dom,w}=setup();try{const route=w.BasketLabRouter.read(new URL('https://basketlab.it/giocatori/alex-test-22?mercato=REB&linea=4.5'));assert.equal(route.view,'stats');assert.equal(route.player,'alex-test-22');assert.equal(w.BasketLabRouter.url(route),'/giocatori/alex-test-22?mercato=REB&linea=4.5');assert.equal(w.BasketLabRouter.read(new URL('https://basketlab.it/statistiche')).view,'stats');}finally{dom.window.close();}});


test('selecting a match clears an unrelated team and restricts choices to both participants',async()=>{
 const extra={...row,'ESPN ID':'44',Giocatore:'Player, Hornets',Squadra:'Charlotte Hornets',Partita:'Charlotte Hornets - Brooklyn Nets'};
 const {dom,w,d}=setup(undefined,{rows:[row,extra]});try{for(let n=0;n<10;n++)await tick();
 const team=d.querySelector('#pe-team'),match=d.querySelector('#pe-match');team.value='Charlotte Hornets';team.dispatchEvent(new w.Event('change'));await tick();
 assert.equal(d.querySelectorAll('.pe-player-row').length,1);
 match.value=row.Partita;match.dispatchEvent(new w.Event('change'));await tick();assert.equal(team.value,'');
 assert.deepEqual([...team.options].map(o=>o.value),['','Boston Celtics','Atlanta Hawks']);
 assert.equal(d.querySelectorAll('.pe-player-row').length,2);assert.match(d.querySelector('.pe-player-row').textContent,/Alex Test/);
 }finally{dom.window.close();}
});
test('default directory works with no saved quotes and loads no player histories until selection',async()=>{
 const {dom,w,d,calls}=setup(undefined,{rows:[]});try{for(let n=0;n<10;n++)await tick();
 assert.equal(d.querySelector('#pe-include-unpriced'),null);
 assert.equal(d.querySelectorAll('.pe-catalog-row').length,2);assert.match(d.querySelector('#pe-status').textContent,/2 senza quota/);
 assert.equal(calls.some(u=>u.startsWith('/api/players/log?')),false);
 d.querySelectorAll('.pe-catalog-row')[1].click();for(let n=0;n<15;n++)await tick();assert.equal(d.querySelector('#playername').value,'33');d.querySelector('#line').value='10.5';d.querySelector('#line').dispatchEvent(new w.Event('change'));assert.match(d.querySelector('#player-summary').textContent,/1\/2/);
 }finally{dom.window.close();}
});
test('unavailable quote service does not block the statistics directory',async()=>{
 const {dom,d,calls}=setup(undefined,{quoteError:true});try{for(let n=0;n<12;n++)await tick();
 assert.equal(d.querySelector('#pe-include-unpriced'),null);assert.equal(d.querySelectorAll('.pe-catalog-row').length,2);
 assert.match(d.querySelector('#pe-status').textContent,/statistiche NBA accessibili/);assert.equal(calls.some(u=>u.startsWith('/api/players/log?')),false);
 }finally{dom.window.close();}
});
