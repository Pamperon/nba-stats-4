'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
test('SPA navigation updates metadata, strips filter duplicates, and supports history',()=>{
 const html=fs.readFileSync('web/index.html','utf8');
 const dom=new JSDOM(html,{url:'https://basketlab.it/',runScripts:'outside-only'}),w=dom.window,d=w.document;
 const config=d.createElement('script');config.id='bl-seo-routes';config.type='application/json';config.textContent=JSON.stringify({'/':['Home title','Home description'],'/pronostici':['Picks title','Picks description'],'/giocatori':['Players title','Players description']});d.head.append(config);
 const robots=d.createElement('meta');robots.name='robots';d.head.append(robots);
 w.eval(fs.readFileSync('web/modules/router.js','utf8'));
 w.BasketLabRouter.write({view:'picks'});
 assert.equal(d.title,'Picks title');assert.equal(d.querySelector('[rel="canonical"]').href,'https://basketlab.it/pronostici');
 w.BasketLabRouter.write({view:'stats',player:'alex-test-22',filters:{market:'PTS',line:'14.5'}});
 assert.equal(d.title,'Alex Test: statistiche NBA e grafici | Basket Lab');
 assert.equal(d.querySelector('[rel="canonical"]').href,'https://basketlab.it/giocatori/alex-test-22');
 assert.equal(d.querySelector('[property="og:url"]').content,'https://basketlab.it/giocatori/alex-test-22');
 w.history.replaceState(null,'','/pronostici');w.dispatchEvent(new w.PopStateEvent('popstate'));
 assert.equal(d.title,'Picks title');
 dom.window.close();
});
