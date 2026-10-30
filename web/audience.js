/* Aggregate counters; a rotating daily browser ID only after optional consent. */
(() => {
 'use strict';
 const choiceKey='basketlab:audience-choice:v1',idKey='basketlab:audience-day:v1';
 const preferences=document.getElementById('audience-preferences');
 const settings=document.getElementById('audience-settings');
 if(navigator.doNotTrack==='1'||navigator.globalPrivacyControl||navigator.webdriver){
  try{localStorage.removeItem(idKey);}catch{}
  return;
 }
 let choice=null;
 try{const saved=JSON.parse(localStorage.getItem(choiceKey));if(saved&&['yes','no'].includes(saved.value)&&saved.at<=Date.now()&&Date.now()-saved.at<180*86400000)choice=saved.value;}catch{}
 if(choice!=='yes'){try{localStorage.removeItem(idKey);}catch{}}
 if(settings){settings.hidden=false;settings.addEventListener('click',()=>{preferences.hidden=!preferences.hidden;settings.setAttribute('aria-expanded',String(!preferences.hidden));});}
 if(preferences)preferences.hidden=choice!==null;
 if(settings)settings.setAttribute('aria-expanded',String(preferences&&!preferences.hidden));
 function choose(value){
  choice=value;
  try{localStorage.setItem(choiceKey,JSON.stringify({value,at:Date.now()}));if(value==='no')localStorage.removeItem(idKey);}catch{}
  if(preferences)preferences.hidden=true;
  if(settings){settings.setAttribute('aria-expanded','false');settings.focus();}
  if(value==='yes')countUnique();
 }
 document.getElementById('audience-accept')?.addEventListener('click',()=>choose('yes'));
 document.getElementById('audience-decline')?.addEventListener('click',()=>choose('no'));
 let source='diretto';
 const sources=['instagram','facebook','tiktok','whatsapp','telegram','google','bing'];
 const aliases={ig:'instagram',fb:'facebook',wa:'whatsapp'};
 try{
  const utm=new URL(location.href).searchParams.get('utm_source');
  const host=document.referrer?new URL(document.referrer).hostname.toLowerCase():'';
  if(utm){const value=utm.toLowerCase();source=aliases[value]||(sources.includes(value)?value:'altro');}
  else if(host&&host!==location.hostname){
   const domains={instagram:['instagram.com'],facebook:['facebook.com','fb.com'],tiktok:['tiktok.com'],whatsapp:['whatsapp.com'],telegram:['t.me','telegram.org'],google:['google.com','google.it'],bing:['bing.com']};
   source=Object.keys(domains).find(key=>domains[key].some(domain=>host===domain||host.endsWith('.'+domain)))||'altro';
  }
 }catch{}
 let started=false,sent=0,queue=[];
 let uniqueDay='';
 function romeDay(){
  const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
  const part=name=>parts.find(p=>p.type===name).value;
  return part('year')+'-'+part('month')+'-'+part('day');
 }
 async function countUnique(){
  if(choice!=='yes'||!started||document.visibilityState==='hidden')return;
  const day=romeDay();if(uniqueDay===day)return;
  const collect=()=>{
   if(choice!=='yes'||document.visibilityState==='hidden'||day!==romeDay()||uniqueDay===day)return;
   try{
    let saved=JSON.parse(localStorage.getItem(idKey));
    if(!saved||saved.day!==day||!/^[0-9a-f]{32}$/.test(saved.id)){
     const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
     saved={day,id:Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('')};
     localStorage.setItem(idKey,JSON.stringify(saved));
    }
    // If storage is blocked, omit uniques rather than inventing one per refresh.
    uniqueDay=day;
    fetch('/api/audience/unique',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(saved),keepalive:true,credentials:'omit',cache:'no-store'}).catch(()=>{});
   }catch{}
  };
  try{if(navigator.locks?.request)await navigator.locks.request('basketlab-audience-day',collect);else collect();}catch{}
 }
 const last=new Map();
 function flush(){
  if(!queue.length)return;
  const events=queue.splice(0,10),body=JSON.stringify({source,events});
  // No retries: an ambiguous response must not duplicate a counted batch.
  fetch('/api/audience/event',{method:'POST',headers:{'Content-Type':'application/json'},body,keepalive:true,credentials:'omit',cache:'no-store'}).catch(()=>{});
 }
 function count(event){
  if(document.visibilityState==='hidden'||sent>=60)return;
  const now=Date.now();if(last.has(event)&&now-last.get(event)<5000)return;
  last.set(event,now);sent++;queue.push(event);if(queue.length>=10)flush();
 }
 function start(){if(document.visibilityState==='hidden')return;if(!started){started=true;count('apertura');flush();}countUnique();}
 document.addEventListener('click',event=>{
  const target=event.target.closest?.('button,a,summary,[role=option]');if(!target)return;
  const tab=target.dataset.tab;
  if(tab)count(({dashboard:'pronostici',finder:'quote',player:'statistiche'})[tab]);
  else if(target.dataset.extra)count(target.dataset.extra==='history'?'archivio':'informazioni');
  else if(target.matches('#player-search-results [role=option]'))count('scelta_giocatore');
  else if(target.matches('.pick-explanation>summary')&&!target.parentElement.open)count('dettagli');
  else if(target.matches('.finder-details-toggle')&&target.getAttribute('aria-expanded')==='true')count('dettagli');
  else if(target.id==='csv')count('csv');
 });
 document.addEventListener('change',event=>{
  if(event.target.matches('#finder input,#finder select'))count('filtro_quote');
  else if(event.target.id==='playername')count('scelta_giocatore');
 });
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flush();else start();});
 window.addEventListener('pagehide',flush);
 window.addEventListener('storage',event=>{
  if(event.key===choiceKey){
   try{const saved=JSON.parse(event.newValue);choice=saved?.value==='yes'&&saved.at<=Date.now()&&Date.now()-saved.at<180*86400000?'yes':'no';}catch{choice='no';}
   if(choice!=='yes'){try{localStorage.removeItem(idKey);}catch{}}
  }
 });
 setInterval(()=>{flush();countUnique();},5000);start();
})();
