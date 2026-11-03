const {test,expect}=require('@playwright/test');
const fs=require('node:fs');
const match='/analisi-partita?data=2026-11-05&trasferta=Boston+Celtics&casa=Atlanta+Hawks';
const api=[];
test.beforeEach(async({page})=>{
 api.length=0;
 await page.clock.setFixedTime(new Date('2026-11-03T14:00:00Z'));
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
 await page.goBack();await expect(page.locator('#hub-calendar')).toBeVisible();
 await page.goForward();await expect(page.locator('#hub-match-charts')).toContainText('110');
 await page.goto('/archivio');await page.locator('[data-history-mode="top5"]').click();await expect(page.locator('#history-tickets')).toContainText('Browser Fixture');
 expect(errors).toEqual([]);
});
test('match stays visible while the independent quote response is delayed',async({page})=>{
 await page.goto(match,{waitUntil:'domcontentloaded'});
 await expect(page.locator('#hub-match-title')).toBeVisible();
 await expect(page.locator('#hub-match-charts')).toContainText('Media punti segnati');
 expect(await page.locator('#hub-match-detail').isVisible()).toBe(true);
 await page.reload();await expect(page.locator('#hub-match-title')).toContainText('Boston Celtics');
});
test('measure mobile/desktop loading and API fanout',async({page,context},testInfo)=>{
 if(testInfo.project.name==='mobile'){
  const cdp=await context.newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  await cdp.send('Network.enable');
  await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:100000});
 }
 await page.addInitScript(()=>{window.__perf={lcp:0,cls:0};new PerformanceObserver(list=>{for(const entry of list.getEntries())window.__perf.lcp=entry.startTime;}).observe({type:'largest-contentful-paint',buffered:true});new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.__perf.cls+=entry.value;}).observe({type:'layout-shift',buffered:true});});
 const started=Date.now();await page.goto('/');await expect(page.locator('#hub-single-content')).toContainText('Browser Fixture');const picksReady=Date.now()-started;
 await page.waitForTimeout(1600);
 const metrics=await page.evaluate(()=>({...window.__perf,domReady:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd}));
 const record={project:testInfo.project.name,phase:process.env.BASKETLAB_BASELINE?'baseline':'optimized',picksReadyMs:picksReady,...metrics,apiRequests:api.slice()};
 console.log('BASKETLAB_METRIC '+JSON.stringify(record));
 await testInfo.attach('performance',{body:JSON.stringify(record,null,2),contentType:'application/json'});
 expect(picksReady).toBeLessThan(10000);expect(metrics.cls).toBeLessThan(0.3);
 if(!process.env.BASKETLAB_BASELINE){expect(api).not.toContain('/api/saved/latest');expect(api).not.toContain('/api/saved/dates');expect(api).not.toContain('/api/players/teams');}
});
