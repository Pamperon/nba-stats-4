/* Homepage discovery from one compact, saved-data endpoint. */
(function(w){
 'use strict';
 const d=w.document,panel=d.getElementById('player-form');if(!panel)return;
 const results=d.getElementById('pf-results'),coverage=d.getElementById('pf-coverage');
 const labels={PTS:'punti',REB:'rimbalzi',AST:'assist'};
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=n=>Number(n).toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1});
 const slug=(name,id)=>name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'-'+id;
 let market='PTS',direction='up',data=null,pending=null,loadedAt=0,refreshTimer=null;
 function render(){
  panel.dataset.direction=direction;
  for(const b of panel.querySelectorAll('[data-pf-market]'))b.setAttribute('aria-pressed',String(b.dataset.pfMarket===market));
  for(const b of panel.querySelectorAll('[data-pf-direction]'))b.setAttribute('aria-pressed',String(b.dataset.pfDirection===direction));
  if(!data)return;
  const rows=data.markets?.[market]?.[direction]||[];
  results.setAttribute('aria-busy','false');results.replaceChildren();
  if(!rows.length){const p=d.createElement('p');p.className='pf-message';p.textContent=data.eligible_players?'Nessun '+(direction==='up'?'aumento':'calo')+' significativo nei '+labels[market]+' tra i giocatori con dati aggiornati.':'Non ci sono ancora abbastanza storici aggiornati per confrontare la forma.';results.append(p);}
  rows.forEach((player,index)=>{
   if(!/^\d{1,12}$/.test(String(player.id)))return;
   const link=d.createElement('a');link.className='pf-player';link.dataset.pfPlayer=slug(player.name,player.id);link.href='/giocatori/'+link.dataset.pfPlayer+'?mercato='+market+'&periodo=5&competizione=2';
   const initials=String(player.name).split(/\s+/).map(x=>x[0]).slice(0,2).join('');
   const change=(player.delta>0?'+':'−')+num(Math.abs(player.delta));
   link.innerHTML='<span class="pf-avatar"><span class="pf-initials" aria-hidden="true">'+esc(initials)+'</span><img loading="lazy" decoding="async" src="/api/players/headshot/'+player.id+'" alt=""><span class="pf-rank" aria-hidden="true">'+String(index+1).padStart(2,'0')+'</span></span><span class="pf-identity"><strong>'+esc(player.name)+'</strong><small>'+esc(player.team)+'</small></span><span class="pf-delta" aria-label="'+esc(change+' '+labels[market]+' rispetto alla media stagionale')+'"><span aria-hidden="true">'+(direction==='up'?'↗':'↘')+'</span> '+change+'</span><span class="pf-comparison"><span class="pf-season" aria-label="Media stagionale su '+esc(player.games)+' presenze"><small>Stagione</small><strong>'+num(player.season_average)+'</strong></span><svg class="pf-compare-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 12h16m-5-5 5 5-5 5"/></svg><span class="pf-figures"><small>Ultime 5 · '+labels[market]+'</small><strong>'+num(player.recent_average)+'</strong></span></span>';
   const photo=link.querySelector('img');
   photo.addEventListener('load',()=>{link.querySelector('.pf-initials').hidden=true;});
   photo.addEventListener('error',()=>{photo.hidden=true;});
   results.append(link);
  });
  const stamp=new Date(data.generated_at);
  const time=Number.isFinite(stamp.getTime())?new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(stamp):'';
  const checked=data.checked_players??data.eligible_players,roster=data.roster_players;
  const scope=roster?(data.coverage_complete?checked+' giocatori analizzati':checked+'/'+roster+' analizzati'):'';
  coverage.innerHTML='<span class="pf-scope"><span class="pf-source">NBA</span> '+esc(scope)+(scope?' · ':'')+esc(data.eligible_players)+' confrontabili</span>'+(time?'<time>'+esc(time)+'</time>':'')+(data.coverage_complete===false?'<span class="pf-update">'+(data.refreshing?'Aggiornamento in corso':'Alcuni dati in aggiornamento')+'</span>':'');

 }
 async function load(){
  if(pending)return pending;
  if(data&&Date.now()-loadedAt<(data.coverage_complete===false?30000:300000)){render();return;}
  results.setAttribute('aria-busy','true');
  pending=(async()=>{
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
   try{
    const response=await fetch('/api/players/form',{signal:controller.signal});if(!response.ok)throw Error();
    const next=await response.json();if(!next.markets)throw Error();data=next;loadedAt=Date.now();render();
   }catch{
    if(data){render();coverage.textContent+=' · Aggiornamento temporaneamente non disponibile';}
    else{results.innerHTML='<p class="pf-message">Trend temporaneamente non disponibili.</p><button type="button" class="pf-retry">Riprova</button>';results.querySelector('button').onclick=()=>load();}
   }finally{clearTimeout(timer);results.setAttribute('aria-busy','false');pending=null;clearTimeout(refreshTimer);if(data?.coverage_complete===false&&!panel.hidden)refreshTimer=setTimeout(()=>{if(!panel.hidden)load();},60000);}
  })();return pending;
 }
 panel.addEventListener('click',e=>{
  const filter=e.target.closest('[data-pf-market],[data-pf-direction]');
  if(filter){if(filter.dataset.pfMarket)market=filter.dataset.pfMarket;if(filter.dataset.pfDirection)direction=filter.dataset.pfDirection;render();}
  const a=e.target.closest('a[data-pf-player]');
  if(a&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&!e.altKey&&e.button===0&&w.BasketLabRouter){e.preventDefault();w.BasketLabRouter.write({view:'stats',player:a.dataset.pfPlayer,filters:{market,window:'5',mode:'2'}});w.dispatchEvent(new PopStateEvent('popstate'));}
 });
 // Keep discovery work off the critical path for the day's analysis.
 if(w.IntersectionObserver){const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&!panel.hidden)load();},{rootMargin:'160px'});observer.observe(panel);}
 else if(!panel.hidden)load();
 d.addEventListener('basketlab:view',e=>{if(e.detail?.view==='home'&&(!w.IntersectionObserver||data))load();});
})(window);
