/* Shared calendar requests with bounded cache and live-aware freshness. */
window.BasketLabCalendarData=function(fetch){
const nbaFixtureCache=new Map();
const MINUTE=60*1000;
function fixtureCacheTtl(games){
 const list=Array.isArray(games)?games:[];
 const now=Date.now();
 // Live games need frequent refresh; newly completed games remain short-lived.
 if(list.some(game=>!game.upcoming&&!/final|terminat|conclus|finished|completed/i.test(String(game.status||''))))return MINUTE;
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
async function fetchNbaFixtures(date,session=false){
 const key=(session?'session:':'date:')+date;
 const cached=nbaFixtureCache.get(key);
 if(cached&&cached.expires>Date.now())return cached.promise;
 const url=session?'/api/nba/publication-session?date=':'/api/nba/fixtures?date=';
 const entry={expires:Date.now()+MINUTE,promise:null};
 entry.promise=fetch(url+encodeURIComponent(date)+(session?'&upcoming=true':'')).then(r=>{if(!r.ok)throw new Error('ESPN calendar unavailable');return r.json()}).then(d=>{
  const games=d.games||[];
  entry.expires=Date.now()+fixtureCacheTtl(games);
  return games;
 }).catch(error=>{if(nbaFixtureCache.get(key)===entry)nbaFixtureCache.delete(key);throw error});
 nbaFixtureCache.set(key,entry);
 if(nbaFixtureCache.size>60)nbaFixtureCache.delete(nbaFixtureCache.keys().next().value);
 return entry.promise;
}
return fetchNbaFixtures;
};
