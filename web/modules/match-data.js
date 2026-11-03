/* Bounded, per-date request deduplication. Rejected requests are never cached. */
window.BasketLabMatchData=function(fetch){
const matchFormCache=new Map();
const MATCH_FORM_TTL=5*60*1000;
function getMatchFormData(date,teams){
 const key=JSON.stringify([date,...teams]);
 const cached=matchFormCache.get(key);
 if(cached&&cached.expires>Date.now())return cached.promise;
 const url='/api/match/form?date='+encodeURIComponent(date)+'&team_a='+encodeURIComponent(teams[0])+'&team_b='+encodeURIComponent(teams[1]);
 const entry={expires:Date.now()+MATCH_FORM_TTL,promise:null};
 entry.promise=fetch(url).then(r=>{if(!r.ok)throw new Error('ESPN temporaneamente non disponibile');return r.json()}).catch(error=>{if(matchFormCache.get(key)===entry)matchFormCache.delete(key);throw error});
 matchFormCache.set(key,entry);
 if(matchFormCache.size>40)matchFormCache.delete(matchFormCache.keys().next().value);
 return entry.promise;
}
return getMatchFormData;
};
