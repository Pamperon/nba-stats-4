/* Aggregate counters only: no cookies, storage, visitor ID or search contents. */
(() => {
 'use strict';
 if(navigator.doNotTrack==='1'||navigator.globalPrivacyControl||navigator.webdriver)return;
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
 function start(){if(!started&&document.visibilityState!=='hidden'){started=true;count('apertura');flush();}}
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
 setInterval(flush,5000);start();
})();
