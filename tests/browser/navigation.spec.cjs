const {test,expect}=require('@playwright/test');
const fs=require('node:fs');
const match='/analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks';
const api=[];
test.beforeEach(async({page})=>{
 api.length=0;
 page.on('request',request=>{if(request.url().includes('/api/'))api.push(new URL(request.url()).pathname);});
 await page.route('**/*',route=>route.request().url().startsWith('http://127.0.0.1:4173')?route.continue():route.abort());
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
 await page.addInitScript(()=>{window.__perf={lcp:0,cls:0};new PerformanceObserver(list=>{for(const entry of list.getEntries())window.__perf.lcp=entry.startTime;}).observe({type:'largest-contentful-paint',buffered:true});new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput){window.__perf.cls+=entry.value;(window.__shifts||(window.__shifts=[])).push({value:entry.value,sources:entry.sources.map(s=>({node:s.node?.id||s.node?.className,from:s.previousRect.y,to:s.currentRect.y}))});}}).observe({type:'layout-shift',buffered:true});});
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
 await expect(page.locator('#hub-featured-list .bl-datalab-card:visible')).toHaveCount(2);
 await expect(page.locator('.hub-trust-strip')).toBeVisible();
 await page.locator('.hub-featured-more').click();await expect(page).toHaveURL(/pronostici/);
 await expect(page.locator('#hub-featured-list .bl-datalab-card:visible')).toHaveCount(5);
 await page.locator((testInfo.project.name==='mobile'?'.hub-mobile-bar':'.hub-sidebar')+' [data-hub="home"]').click();
 await expect(page.locator('#hub-featured-list .bl-datalab-card:visible')).toHaveCount(2);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:testInfo.outputPath('home-redesign.png'),fullPage:true});
 await page.locator('.bl-broadcast-action').click();
 await expect(page).toHaveURL(/analisi-singola/);
 await expect(page.locator('#single-analysis-page')).toContainText('Browser Fixture');
 await expect(page.locator('.sa-chart-scroll svg')).toBeVisible();
 await page.locator('.sa-back').click();await expect(page).toHaveURL('http://127.0.0.1:4173/');
 await page.locator('.hub-premium-fixture').click();await expect(page).toHaveURL(/analisi-partita\?data=2026-11-05/);await expect(page.locator('#hub-match-charts')).toContainText('Media punti segnati');
 await page.screenshot({path:testInfo.outputPath('match-redesign.png'),fullPage:true});
 await page.locator('[data-match-tab="players"]').click();await expect(page.locator('.hub-match-player-card')).toBeVisible();
 await page.locator('.hub-match-player-stats-link').click();await expect(page).toHaveURL(/\/giocatori\/browser-fixture-123\?/);
 await page.locator('[data-player-window="10"]').click();
 await expect(page.locator('#player-visual .bl-chart-bar')).toHaveCount(10);
 await page.locator('[data-player-market="REB"]').click();await expect(page.locator('#stat')).toHaveValue('REB');
 await expect(page.locator('[data-player-market="REB"]')).toHaveAttribute('aria-pressed','true');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
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
