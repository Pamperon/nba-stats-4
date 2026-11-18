/* Shared calendar requests with bounded cache and live-aware freshness. */
window.BasketLabCalendarData=function(fetch){
const nbaFixtureCache=new Map();
const MINUTE=60*1000;
function fixtureCacheTtl(games){
 const list=Array.isArray(games)?games:[];
 const now=Date.now();
 // Live games need frequent refresh; newly completed games remain short-lived.
 if(list.some(game=>game.state==='in'||(!game.state&&!game.upcoming&&!/final|terminat|conclus|finished|completed/i.test(String(game.status||'')))))return 30*1000;
 if(list.some(game=>!game.upcoming&&/final|terminat|conclus|finished|completed/i.test(String(game.status||'')))){
  const recent=list.some(game=>{
   const started=Date.parse(game.start_at||'');
   return !Number.isFinite(started)||now-started<7*60*60*1000;
  });
  return recent?5*MINUTE:24*60*MINUTE;
 }
 const upcoming=list.filter(game=>game.upcoming);
 if(upcoming.length){
  const near=upcoming.some(game=>{
   const start=Date.parse(game.start_at||'');
   return Number.isFinite(start)&&start-now<60*MINUTE;
  });
  return near?MINUTE:15*MINUTE;
 }
 // Empty days and old schedules can be cached longer.
 return 24*60*MINUTE;
}
async function fetchNbaFixtures(date,session=false,force=false){
 const key=(session?'session:':'date:')+date;
 const cached=nbaFixtureCache.get(key);
 if(cached&&(cached.pending||(!force&&cached.expires>Date.now())))return cached.promise;
 const url=session?'/api/nba/publication-session?date=':'/api/nba/fixtures?date=';
 const entry={expires:Date.now()+MINUTE,promise:null,pending:true};
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),20000);
 entry.promise=fetch(url+encodeURIComponent(date)+(session?'&upcoming=true':''),{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('ESPN calendar unavailable');return r.json()}).then(d=>{
  const games=d.games||[];
  entry.live=games.some(game=>game.state==='in');
  entry.expires=Date.now()+fixtureCacheTtl(games);
  return games;
 }).catch(error=>{if(nbaFixtureCache.get(key)===entry)nbaFixtureCache.delete(key);throw error}).finally(()=>{clearTimeout(timeout);entry.pending=false;});
 nbaFixtureCache.set(key,entry);
 if(nbaFixtureCache.size>60)nbaFixtureCache.delete(nbaFixtureCache.keys().next().value);
 return entry.promise;
}
fetchNbaFixtures.isStale=function(date,session=false){const entry=nbaFixtureCache.get((session?'session:':'date:')+date);return !entry||(!entry.pending&&entry.expires<=Date.now());};
fetchNbaFixtures.hasLive=function(date,session=false){return nbaFixtureCache.get((session?'session:':'date:')+date)?.live===true;};
return fetchNbaFixtures;
};
