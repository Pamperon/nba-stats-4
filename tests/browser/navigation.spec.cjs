const {test,expect}=require('@playwright/test');
const fs=require('node:fs');
const match='/analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks';
const api=[];
test.beforeEach(async({page})=>{
 api.length=0;
 page.on('request',request=>{if(request.url().includes('/api/'))api.push(new URL(request.url()).pathname);});
 await page.route('**/*',route=>route.request().url().startsWith('http://127.0.0.1:4173')?route.continue():route.abort());
});
test('single results remain distinct from selections on Home and direct Pronostici',async({page},testInfo)=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'Single-first presentation is verified on the candidate');
 await page.route('**/api/history/performance',route=>route.fulfill({json:{success_pct:64.7,published:124,single:{success_pct:87.5,published:10,verified:8,won:7,lost:1,not_played:1,pending:1}}}));
 await page.goto('/pronostici');
 await expect(page.locator('#picks-showcase .hub-performance')).toContainText('87,5%');
 await expect(page.locator('.hub-performance .bl-results-card')).toHaveCount(1);
 await expect(page.locator('.hub-performance')).not.toContainText('64,7');
 await expect(page.locator('.hub-performance [data-hub=history]')).toHaveCount(0);
 await expect(page.locator('.hub-single-section .bl-broadcast-reason')).toHaveCount(0);
 await expect(page.locator('.hub-single-section h2 .bl-lab-word')).toHaveCSS('color',await page.locator('.hub-single-section h2').evaluate(el=>getComputedStyle(el).color));
 await expect(page.locator('.hub-performance h3, .hub-performance .bl-results-footer')).toHaveCount(0);
 await expect(page.locator('.hub-performance h2')).toHaveText('Rendimento del Lab');
 await expect(page.locator('.hub-performance .bl-results-heading')).toHaveCount(0);
 await expect(page.locator('#hub-single-content')).toContainText('Browser Fixture');
 await expect(page.locator('.hub-single-section h2')).toHaveText('La scelta del Lab');
 await expect(page.locator('.hub-picks-archive')).toBeVisible();
 await expect(page.locator('.hub-featured h2')).toHaveText('Le altre analisi');
 await expect(page.locator('#picks-showcase > .hub-single-section + .hub-performance + .hub-featured + .hub-picks-archive')).toBeVisible();
 await page.locator((testInfo.project.name==='mobile'?'.hub-mobile-bar':'.hub-sidebar')+' [data-hub="home"]').click();
 await expect(page.locator('.hub-performance')).toBeVisible();
 expect(await page.evaluate(()=>{const selectors=['.hub-performance','.hub-single-section','.hub-games-section','.hub-featured','#hub-nba-updates-panel'];return selectors.every((selector,i)=>!i||document.querySelector(selectors[i-1]).getBoundingClientRect().bottom<=document.querySelector(selector).getBoundingClientRect().top+1)})).toBe(true);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
test('home, calendar, match, archive and history preserve data',async({page},testInfo)=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('#hub-single-content')).toContainText('Browser Fixture');
 await page.locator((testInfo.project.name==='mobile'?'.hub-mobile-bar':'.hub-sidebar')+' [data-hub="calendar"]').click();
 await expect(page.locator('.hub-calendar-match')).toBeVisible();
 await page.locator('.hub-calendar-match').click();
 await expect(page.locator('#hub-match-title')).toContainText('Boston Celtics');
 await expect(page.locator('#hub-match-charts')).toContainText('Media punti segnati');
 await expect(page).toHaveURL(/analisi-partita/);
 await page.locator('[data-match-tab="players"]').click();
 if(!process.env.BASKETLAB_BASELINE)await expect(page.locator('#hub-match-player-list')).toContainText('Browser Fixture');
 await page.locator('[data-match-tab="analysis"]').click();
 await page.goBack();await expect(page.locator('#hub-calendar')).toBeVisible();
 await page.goForward();await expect(page.locator('#hub-match-charts')).toContainText('110');
 await page.goto('/archivio');await page.locator('[data-history-mode="top5"]').click();await expect(page.locator('#history-tickets')).toContainText('Browser Fixture');
 if(!process.env.BASKETLAB_BASELINE)expect(errors).toEqual([]);else console.log('BASKETLAB_BASELINE_ERRORS '+JSON.stringify(errors));
});
test('match stays visible while the independent quote response is delayed',async({page})=>{
 let quoteDone=false;page.on('response',r=>{if(r.url().includes('/api/saved/latest'))quoteDone=true;});
 await page.goto(match,{waitUntil:'domcontentloaded'});
 await expect(page.locator('#hub-match-title')).toBeVisible();
 expect(quoteDone).toBe(false);
 await expect(page.locator('#hub-match-charts')).toContainText('Media punti segnati');
 expect(await page.locator('#hub-match-detail').isVisible()).toBe(true);
 await page.reload();await expect(page.locator('#hub-match-title')).toContainText('Boston Celtics');
});
for(let sample=0;sample<3;sample++)test('measure mobile/desktop loading and API fanout '+sample,async({page,context},testInfo)=>{
 if(testInfo.project.name==='mobile'){
  const cdp=await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:100000});
 }
 await page.addInitScript(()=>{window.__perf={lcp:0,cls:0};new PerformanceObserver(list=>{for(const entry of list.getEntries()){window.__perf.lcp=entry.startTime;window.__perf.lcpElement=entry.element?.outerHTML?.slice(0,500);}}).observe({type:'largest-contentful-paint',buffered:true});new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput){window.__perf.cls+=entry.value;(window.__shifts||(window.__shifts=[])).push({value:entry.value,sources:entry.sources.map(s=>({node:s.node?.id||s.node?.className,from:s.previousRect.y,to:s.currentRect.y}))});}}).observe({type:'layout-shift',buffered:true});});
 const started=Date.now();await page.goto('/');await expect(page.locator('#hub-single-content')).toContainText('Browser Fixture');const picksReady=Date.now()-started;
 await page.waitForTimeout(1600);
 const metrics=await page.evaluate(()=>({...window.__perf,domReady:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd}));
 const record={project:testInfo.project.name,sample,phase:process.env.BASKETLAB_BASELINE?'baseline':'optimized',picksReadyMs:picksReady,...metrics,apiRequests:api.slice()};
 console.log('BASKETLAB_METRIC '+JSON.stringify(record));
 if(!process.env.BASKETLAB_BASELINE&&metrics.cls>0.1)console.log('BASKETLAB_LAYOUT_SHIFTS '+JSON.stringify(await page.evaluate(()=>window.__shifts)));
 await testInfo.attach('performance',{body:JSON.stringify(record,null,2),contentType:'application/json'});
 expect(picksReady).toBeLessThan(10000);expect(metrics.cls).toBeLessThan(0.3);
 if(!process.env.BASKETLAB_BASELINE){expect(api.filter(path=>path==='/api/picks/session')).toHaveLength(1);expect(api).not.toContain('/api/saved/latest');expect(api).not.toContain('/api/saved/dates');expect(api).not.toContain('/api/players/teams');}
});

test('approved coordinated design: player charts, contextual back and responsive screens',async({page},testInfo)=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'New design is verified on the candidate; baseline keeps its original UI');
 await page.route('**/api/picks/session**',async route=>{const response=await route.fetch();const data=await response.json();data.preliminary_top5=Array.from({length:5},(_,i)=>({...data.preliminary_single,Giocatore:'Browser Fixture '+(i+1)}));await route.fulfill({response,json:data});});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.locator('#hub-single-content')).toContainText('Browser Fixture');
 await page.locator('[data-choice=no]').click();
 await expect(page.locator('#hub-featured-list .bl-datalab-card:visible')).toHaveCount(3);
 await expect(page.locator('.hub-trust-strip')).toBeVisible();
 await page.locator('.hub-featured-more').click();await expect(page).toHaveURL(/pronostici/);
 await expect(page.locator('#hub-featured-list .bl-datalab-card:visible')).toHaveCount(5);
 await page.locator((testInfo.project.name==='mobile'?'.hub-mobile-bar':'.hub-sidebar')+' [data-hub="home"]').click();
 await expect(page.locator('#hub-featured-list .bl-datalab-card:visible')).toHaveCount(3);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:testInfo.outputPath('home-redesign.png'),fullPage:true});
 await page.locator('.bl-broadcast-action').click();
 await expect(page).toHaveURL(/analisi-singola/);
 await expect(page.locator('#single-analysis-page')).toContainText('Browser Fixture');
 await expect(page.locator('.sa-chart-scroll svg')).toBeVisible();
 await expect(page.locator('.sa-heading h1, .sa-heading .sa-eyebrow')).toHaveCount(0);
 await expect(page.locator('#single-analysis-page > .sa-heading:first-child .bl-publication-badge')).toBeVisible();
 await page.locator('.sa-back').click();await expect(page).toHaveURL('http://127.0.0.1:4173/');
 await page.locator('.hub-premium-fixture').click();await expect(page).toHaveURL(/analisi-partita\?data=2026-11-05/);await expect(page.locator('#hub-match-charts')).toContainText('Media punti segnati');
 await expect(page.locator('.sheet-comparison')).toContainText('Media punti subiti');
 await expect(page.locator('#hub-match-insights,#hub-match-market-distribution')).toHaveCount(0);
 await expect(page.locator('#bl-detail-styles')).toHaveCount(1);
 await expect.poll(()=>page.evaluate(()=>Boolean(document.getElementById('bl-detail-styles')?.sheet))).toBe(true);
 if(testInfo.project.name==='mobile')expect((await page.locator('.sheet-comparison').boundingBox()).y).toBeLessThan((await page.locator('.bl-match-v2').boundingBox()).y);
 await page.screenshot({path:testInfo.outputPath('match-redesign.png'),fullPage:true});
 await page.locator('[data-match-tab="players"]').click();await expect(page.locator('.hub-match-player-card')).toBeVisible();
 await page.locator('.hub-match-player-stats-link').click();await expect(page).toHaveURL(/\/giocatori\/browser-fixture-123\?/);
 await page.locator('[data-player-window="10"]').click();
 await expect(page.locator('#player-visual .bl-chart-bar')).toHaveCount(10);
 await page.locator('[data-player-market="REB"]').click();await expect(page.locator('#stat')).toHaveValue('REB');
 await expect(page.locator('[data-player-market="REB"]')).toHaveAttribute('aria-pressed','true');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await expect(page.locator('#pe-next-match')).toContainText('Prossima partita della squadra');
 await expect(page.locator('#pe-next-match > a')).toHaveAttribute('href',/partita=123/);
 await expect(page.locator('#pe-share')).toHaveCount(0);
 await expect(page.locator('#player-summary .metric')).toHaveCount(2);
 await expect(page.locator('#player-summary')).not.toContainText('%');
 await expect(page.locator('#back-to-picks')).toHaveClass(/bl-nav-back/);
 await expect(page.locator('#back-to-picks')).toHaveCSS('background-color','rgba(0, 0, 0, 0)');
 expect((await page.locator('#back-to-picks').boundingBox()).height).toBeGreaterThanOrEqual(44);
 expect(await page.locator('.bl-player-controls').evaluate(el=>el.getBoundingClientRect().bottom<=document.getElementById('player-visual').getBoundingClientRect().top)).toBe(true);
 await expect.poll(()=>page.locator('.bl-chart-scroll').evaluate(el=>Math.abs(el.scrollWidth-el.clientWidth-el.scrollLeft))).toBeLessThanOrEqual(1);
 await page.screenshot({path:testInfo.outputPath('player-redesign.png'),fullPage:true});
 await expect(page.locator('#back-to-picks')).toContainText('Torna all’analisi');
 await page.locator('#back-to-picks').click();await expect(page).toHaveURL(/analisi-partita/);
 await expect(page.locator('#hub-match-title')).toContainText('Boston Celtics');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 expect(errors).toEqual([]);
});

test('Home fixtures without calendar_date use the Italian tipoff day',async({page})=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'The original Home link did not preserve dates');
 let expectedDay;
 await page.route('**/api/nba/publication-session**',async route=>{
  const response=await route.fetch(),data=await response.json();
  expectedDay=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(data.games[0].start_at));
  for(const game of data.games)delete game.calendar_date;
  await route.fulfill({response,json:data});
 });
 await page.goto('/');await page.locator('.hub-premium-fixture').click();
 expect(new URL(page.url()).searchParams.get('data')).toBe(expectedDay);
 await expect(page.locator('#hub-match-charts')).toContainText('Media punti segnati');
});


test('NBA compact fixtures, Live marker, standings and page alignment',async({page})=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'Compact NBA layout is checked on the current candidate');
 const games=[
  {event_id:'1',away:'Boston Celtics',home:'Atlanta Hawks',state:'post',upcoming:false,away_score:123,home_score:117},
  {event_id:'2',away:'Chicago Bulls',home:'Miami Heat',state:'in',upcoming:false,away_score:0,home_score:0},
  {event_id:'3',away:'Denver Nuggets',home:'Phoenix Suns',state:'pre',upcoming:true},
  {event_id:'4',away:'Dallas Mavericks',home:'Houston Rockets',state:'pre',upcoming:false,status:'Postponed'}
 ].map(game=>({...game,start_at:'2026-11-05T01:00:00Z',calendar_date:'2026-11-05'}));
 await page.route('**/api/nba/fixtures**',route=>route.fulfill({json:{games}}));
 await page.route('**/api/nba/standings',route=>route.fulfill({json:{conferences:[{name:'Eastern Conference',teams:[{id:'2',name:'Boston Celtics',rank:1,wins:10,losses:2,win_percent:10/12}]},{name:'Western Conference',teams:[{id:'7',name:'Denver Nuggets',rank:1,wins:9,losses:3,win_percent:.75}]}]}}));
 await page.goto('/pronostici');await expect(page.locator('#hub-single-content')).toContainText('Browser Fixture');
 const picksTop=await page.locator('.hub-single-section').evaluate(el=>el.getBoundingClientRect().top+window.scrollY);
 await page.goto('/nba?data=2026-11-05');
 await expect(page.locator('.hub-calendar-match')).toHaveCount(4);
 const calendarTop=await page.locator('#hub-calendar').evaluate(el=>el.getBoundingClientRect().top+window.scrollY);
 expect(Math.abs(calendarTop-picksTop)).toBeLessThanOrEqual(2);
 await expect(page.locator('.hub-calendar-odds')).toHaveCount(0);
 await expect(page.locator('.hub-calendar-state')).toHaveCount(1);
 await expect(page.locator('.hub-calendar-state')).toHaveText('Live');
 expect(await page.locator('.hub-calendar-state').evaluate(el=>getComputedStyle(el,'::before').backgroundColor)).toBe('rgb(255, 78, 102)');
 expect(await page.locator('.hub-calendar-match').evaluateAll(rows=>rows.every(el=>el.getBoundingClientRect().height<=96))).toBe(true);
 await expect(page.locator('.hub-calendar-match').first().locator('.is-winner')).toHaveText('123');
 await expect(page.locator('.hub-calendar-match').nth(1).locator('.hub-score-value')).toHaveText(['0','0']);
 expect(api).not.toContain('/api/nba/quote-coverage');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:'test-results/nba-calendar-compact-'+page.viewportSize().width+'.png',fullPage:true});
 await page.locator('[data-nba-tab=standings]').click();
 await expect(page.locator('.nba-conference')).toHaveCount(2);
 await expect(page.locator('.nba-standings').first()).toContainText('Boston Celtics');
 expect(await page.locator('#hub-calendar').evaluate(el=>el.getBoundingClientRect().top+window.scrollY)).toBe(calendarTop);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:'test-results/nba-standings-'+page.viewportSize().width+'.png',fullPage:true});
});

test('Home player form filters and player links stay compact and independent of predictions',async({page},testInfo)=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'Player form is verified on the candidate');
 const players=[{id:'123',name:'Browser Fixture',team:'Boston Celtics',team_id:'2'},{id:'124',name:'Second Player',team:'Atlanta Hawks',team_id:'1'},{id:'125',name:'Third Player',team:'Denver Nuggets',team_id:'7'}];
 const rows=(delta,market)=>players.map((p,i)=>({...p,games:14,recent_average:(market==='PTS'?28:8)-i,season_average:(market==='PTS'?28:8)-i-delta,delta,last_played:'2026-11-16'}));
 await page.route('**/api/players/form',route=>route.fulfill({json:{season:'2026–27',generated_at:'2026-11-17T18:00:00+01:00',eligible_players:42,roster_players:525,checked_players:525,coverage_complete:true,markets:{PTS:{up:rows(5,'PTS'),down:rows(-4,'PTS')},REB:{up:rows(2,'REB'),down:[]},AST:{up:[],down:[]}}}}));
 await page.route('**/api/players/directory',route=>route.fulfill({json:{players}}));
 await page.goto('/');
 await page.locator('#player-form').scrollIntoViewIfNeeded();
 await expect(page.locator('.pf-player')).toHaveCount(3);
 await expect(page.locator('#player-form details')).toHaveCount(0);
 await expect(page.locator('#pf-coverage')).toContainText('525 giocatori analizzati');
 await expect(page.locator('.pf-figures>strong').first()).toHaveText('28,0');
 await page.locator('[data-pf-market=REB]').click();
 await expect(page.locator('.pf-figures>strong').first()).toHaveText('8,0');
 await expect(page.locator('.pf-player').first()).toHaveAttribute('href',/mercato=REB/);
 await page.locator('[data-pf-direction=down]').click();await expect(page.locator('.pf-player')).toHaveCount(0);
 await page.locator('[data-pf-market=PTS]').click();await expect(page.locator('.pf-player')).toHaveCount(3);
 await expect(page.locator('.pf-delta').first()).toContainText('−4,0');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.locator('[data-pf-direction=up]').click();
 await page.locator('#player-form').screenshot({path:'test-results/player-form-'+testInfo.project.name+'.png'});
 const formCalls=api.filter(x=>x==='/api/players/form');expect(formCalls.length).toBe(1);
 await page.locator('.pf-player').first().click();await expect(page).toHaveURL(/\/giocatori\/browser-fixture-123/);
 await expect(page.locator('#player-form')).toBeHidden();
 await expect(page.locator('#stat')).toHaveValue('PTS');
});

test('live calendar and open boxscore update automatically through the final whistle',async({page},testInfo)=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'Live polling is verified on the candidate');
 await page.clock.install({time:new Date('2026-11-18T01:00:00+01:00')});
 let fixtureScore=20,away=24,home=22,points=10,state='in',boxCalls=0;
 const game=()=>({event_id:'123456',away:'Boston Celtics',home:'Atlanta Hawks',state:'in',upcoming:false,start_at:'2026-11-18T00:00:00Z',away_score:fixtureScore,home_score:18,period:1,display_clock:'6:00'});
 await page.route('**/api/nba/fixtures**',route=>route.fulfill({json:{games:[game()]}}));
 await page.route('**/api/nba/boxscore**',route=>{boxCalls++;return route.fulfill({json:{event_id:'123456',state,game:{state,away_score:away,home_score:home,period:state==='post'?4:2,display_clock:'5:00'},quarters:[{label:'Q1',away:24,home:22}],teams:[{team:'Boston Celtics',players:[{id:'22',name:'Alex Test',minutes:'20',points,rebounds:7,assists:4},{id:'23',name:'Second Player',minutes:'12',points:5,rebounds:2,assists:1}]}]}});});
 await page.goto('/nba?data=2026-11-18');
 await page.locator('[data-choice=no]').click();
 await expect(page.locator('.hub-calendar-final-score')).toContainText('20');
 fixtureScore=26;await page.clock.runFor(31000);
 await expect(page.locator('.hub-calendar-final-score')).toContainText('26');
 await page.locator('.hub-calendar-match').click();
 await expect(page.locator('.hub-boxscore-headline')).toHaveText('24 – 22');
 const sort=page.locator('[data-boxscore-sort=points]');await sort.click();await sort.click();
 await expect(page.locator('.hub-boxscore-table tbody tr').first()).toContainText('Second Player');
 const playerLink=page.locator('.hub-boxscore-player-link').filter({hasText:'Alex Test'});
 await playerLink.scrollIntoViewIfNeeded();
 const url=page.url(),top=await page.evaluate(()=>window.scrollY);
 await playerLink.click();const drawer=page.locator('#bl-game-player-panel');
 await expect(drawer).toBeVisible();await expect(drawer.locator('[data-game-player-stat=points]')).toHaveText('10');await expect(page).toHaveURL(url);
 await expect(drawer.getByRole('link',{name:'Apri il profilo completo →'})).toHaveAttribute('href','/giocatori/alex-test-22');
 await expect(drawer.getByRole('button',{name:'Chiudi statistiche giocatore'})).toBeFocused();
 away=30;home=26;points=16;
 await page.clock.runFor(30000);
 await expect(page.locator('.hub-boxscore-headline')).toHaveText('30 – 26');
 await expect(drawer).toBeVisible();await expect(drawer.locator('[data-game-player-stat=points]')).toHaveText('16');
 await expect(drawer.getByRole('button',{name:'Chiudi statistiche giocatore'})).toBeFocused();
 await page.screenshot({path:testInfo.outputPath('player-game-panel.png')});
 await drawer.press('Escape');await expect(drawer).toBeHidden();await expect(playerLink).toBeFocused();
 expect(Math.abs((await page.evaluate(()=>window.scrollY))-top)).toBeLessThanOrEqual(1);
 await expect(page).toHaveURL(url);
 await expect(page.locator('.hub-boxscore-table tbody tr').filter({hasText:'Alex Test'})).toContainText('16');
 await expect(page.locator('.hub-boxscore-table tbody tr').first()).toContainText('Second Player');
 await expect(sort.locator('..')).toHaveAttribute('aria-sort','ascending');
 await expect(page.locator('.sheet-leaders')).toContainText('Alex Test');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:testInfo.outputPath('live-detail.png'),fullPage:true});
 await expect(page.locator('.hub-boxscore-period-table tbody tr').first().locator('td').last()).toHaveText('30');
 await expect(page).toHaveURL(url);await expect(page.locator('.hub-boxscore-back')).toBeVisible();
 state='post';away=110;home=100;points=28;await page.clock.runFor(30000);
 await expect(page.locator('.hub-boxscore-headline')).toHaveText('110 – 100');
 await expect(page.locator('.hub-boxscore-live-status')).toHaveText('Finale');
 const done=boxCalls;await page.clock.runFor(60000);expect(boxCalls).toBe(done);
 await playerLink.click();await expect(drawer.locator('[data-game-player-stat=points]')).toHaveText('28');await expect(drawer.locator('.bl-game-player-status')).toHaveText('Finale');
 await drawer.getByRole('link',{name:'Apri il profilo completo →'}).click();await expect(page).toHaveURL(/\/giocatori\/alex-test-22/);
});

test('prematch without win odds uses one full comparison and a compact history note',async({page},testInfo)=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'Detail polish is verified on the candidate');
 if(testInfo.project.name==='mobile')await page.setViewportSize({width:360,height:800});
 await page.route('**/api/match/form**',async route=>{const response=await route.fetch(),data=await response.json();data.moneyline_odds=null;await route.fulfill({response,json:data});});
 await page.goto(match);await page.locator('[data-choice=no]').click();
 await expect(page.locator('.sheet-comparison')).toContainText('Media punti segnati');
 await expect(page.locator('.hub-match-win-unavailable,.bl-match-v2')).toHaveCount(0);
 await expect(page.locator('#hub-match-sample-note')).toContainText('Fonte ESPN');
 await expect.poll(()=>page.evaluate(()=>Boolean(document.getElementById('bl-detail-styles')?.sheet))).toBe(true);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 const widths=await page.locator('#hub-match-charts').evaluate(el=>({container:el.getBoundingClientRect().width,comparison:el.querySelector('.sheet-comparison').getBoundingClientRect().width}));
 expect(Math.abs(widths.container-widths.comparison)).toBeLessThanOrEqual(1);
 await page.screenshot({path:testInfo.outputPath('prematch-no-odds.png'),fullPage:true});
});

 test('direct player has one return to the directory',async({page})=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'Refined profile navigation');
 await page.route('**/api/players/directory',route=>route.fulfill({json:{players:[{id:'123',name:'Browser Fixture',team:'Boston Celtics',team_id:'2'}]}}));
 let releaseMetadata;const metadataGate=new Promise(r=>releaseMetadata=r);
 await page.route('**/api/players/teams',async route=>{await metadataGate;await route.continue();});
 await page.route('**/api/players/roster?*',async route=>{await metadataGate;await route.continue();});
 await page.goto('/giocatori/browser-fixture-123?mercato=PTS&linea=19.5&periodo=10');
 await expect(page.locator('#player-summary .metric')).toHaveCount(2);
 expect(api.filter(p=>p==='/api/players/log')).toHaveLength(1);
 expect(api).not.toContain('/api/players/directory');
 releaseMetadata();
 await expect(page.locator('#player-summary')).not.toContainText('%');
 await expect(page.locator('#back-to-picks')).toBeHidden();
 await expect(page.locator('#pe-personal-heading .bl-nav-back:visible')).toHaveCount(1);
 await page.locator('#pe-personal-heading [data-hub="stats"]').click();
 await expect(page).toHaveURL('/giocatori');
 await expect(page.locator('#players-explorer')).toBeVisible();
 });

test('player charts fit 5, 10 and 20 games and scroll the complete season',async({page},testInfo)=>{
 test.skip(!!process.env.BASKETLAB_BASELINE,'Adaptive charts are verified on the candidate');
 const games=Array.from({length:35},(_,i)=>({GAME_ID:String(400+i),GAME_DATE:new Date(Date.UTC(2026,10,18-i)).toISOString().slice(0,10),PTS:10+i%25,REB:5,AST:3,MIN:30,SEASON_TYPE:2,MATCHUP:'vs ATL'}));
 await page.route('**/api/players/log?*',route=>route.fulfill({json:{athlete_id:'123',season:'2026',games}}));
 if(testInfo.project.name==='mobile')await page.setViewportSize({width:360,height:800});
 await page.goto('/giocatori/browser-fixture-123?mercato=PTS&linea=19.5&periodo=20');
 await page.getByRole('button',{name:'Rifiuta',exact:true}).click();
 for(const count of [5,10,20]){
  await page.locator('[data-player-window="'+count+'"]').click();
  await expect(page.locator('.bl-chart-column')).toHaveCount(count);
  expect(await page.locator('.bl-chart-scroll').evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
  await expect(page.locator('.bl-chart-navigation')).toHaveCount(0);
 }
 await page.locator('.bl-chart-column').last().click();await expect(page.locator('.bl-chart-detail')).toContainText('10 punti');
 expect(await page.locator('.bl-chart-scroll').evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
 await page.locator('#player-visual').screenshot({path:testInfo.outputPath('player-chart-20.png')});
 await page.locator('[data-player-window="all"]').click();
 await expect(page.locator('.bl-chart-column')).toHaveCount(35);
 await expect(page.locator('#bl-chart-position')).toBeVisible();
 await expect.poll(()=>page.locator('.bl-chart-scroll').evaluate(el=>el.scrollLeft>0)).toBe(true);
 await page.locator('#bl-chart-position').focus();await page.locator('#bl-chart-position').press('Home');
 await expect.poll(()=>page.locator('.bl-chart-scroll').evaluate(el=>el.scrollLeft)).toBe(0);
 await page.locator('.bl-chart-column').first().click();await expect(page.locator('.bl-chart-detail')).toContainText('19 punti');
 await page.locator('#bl-chart-position').focus();await page.locator('#bl-chart-position').press('End');
 await expect.poll(()=>page.locator('.bl-chart-scroll').evaluate(el=>Math.abs(el.scrollWidth-el.clientWidth-el.scrollLeft))).toBeLessThanOrEqual(1);
 await page.locator('#player-visual').screenshot({path:testInfo.outputPath('player-chart-season.png')});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
