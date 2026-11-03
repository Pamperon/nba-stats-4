/* Compare lab medians on the same runner; allow normal CI timing noise. */
const fs=require('node:fs'),assert=require('node:assert/strict');
function rows(file){const out=[];function visit(value){if(!value||typeof value!=='object')return;if(value.status==='passed'&&Array.isArray(value.stdout))for(const item of value.stdout)for(const line of (item.text||'').split('\n'))if(line.includes('BASKETLAB_METRIC '))out.push(JSON.parse(line.split('BASKETLAB_METRIC ')[1]));for(const [key,child] of Object.entries(value))if(key!=='stdout'){if(Array.isArray(child))child.forEach(visit);else visit(child);}}visit(JSON.parse(fs.readFileSync(file,'utf8')));return out;}
const baseline=rows(process.argv[2]),candidate=rows(process.argv[3]);
const median=values=>values.sort((a,b)=>a-b)[Math.floor(values.length/2)];
const results=[];
for(const profile of ['desktop','mobile']){
 const before=baseline.filter(x=>x.project===profile),after=candidate.filter(x=>x.project===profile);
 assert.equal(before.length,3,'Need three baseline samples for '+profile);assert.equal(after.length,3,'Need three candidate samples for '+profile);
 for(const metric of ['picksReadyMs','lcp']){
  const old=median(before.map(x=>x[metric])),now=median(after.map(x=>x[metric]));
  assert.ok(Number.isFinite(old)&&old>0&&Number.isFinite(now)&&now>0,'Missing real browser measurement');
  assert.ok(now<=old*1.25+250,`${profile} ${metric}: ${now} exceeds baseline ${old} + budget`);
  results.push({profile,metric,baseline:old,candidate:now});
 }
 assert.ok(after.every(x=>x.apiRequests.length<=4),'Unexpected Home API fanout');
}
console.log('BASKETLAB_BUDGET '+JSON.stringify(results));
