/* Homepage discovery from one compact, saved-data endpoint. */
(function(w){
 'use strict';
 const d=w.document,panel=d.getElementById('player-form');if(!panel)return;
 const results=d.getElementById('pf-results'),coverage=d.getElementById('pf-coverage');
 const labels={PTS:'punti',REB:'rimbalzi',AST:'assist'};
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=n=>Number(n).toLocaleString('it-IT',{minimumFractionDigits:1,maximumFractionDigits:1});
 const slug=(name,id)=>name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'-'+id;
 let market='PTS',direction='up',data=null,pending=null,loadedAt=0;
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
   link.innerHTML='<span class="pf-avatar"><span aria-hidden="true">'+esc(initials)+'</span><img loading="lazy" decoding="async" src="/api/players/headshot/'+player.id+'" alt=""></span><span class="pf-identity"><strong>'+esc(player.name)+'</strong><small>'+esc(player.team)+'</small><span class="pf-baseline">Stagione <b>'+num(player.season_average)+'</b> · '+esc(player.games)+' presenze</span></span><span class="pf-figures"><strong>'+num(player.recent_average)+'</strong><small>'+labels[market]+' · ultime 5</small><span class="pf-delta">'+(player.delta>0?'+':'−')+num(Math.abs(player.delta))+' <span class="pf-delta-label">sulla media</span></span></span><span class="pf-card-arrow" aria-hidden="true">›</span>';
   link.querySelector('img').addEventListener('error',e=>{e.target.hidden=true;});
   results.append(link);
  });
  const stamp=new Date(data.generated_at);
  const time=Number.isFinite(stamp.getTime())?' · '+new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}).format(stamp):'';
  coverage.textContent='ESPN · '+data.season+' · '+data.eligible_players+' giocatori confrontabili'+time;
 }
 async function load(){
  if(pending)return pending;
  if(data&&Date.now()-loadedAt<300000){render();return;}
  results.setAttribute('aria-busy','true');
  pending=(async()=>{
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
   try{
    const response=await fetch('/api/players/form',{signal:controller.signal});if(!response.ok)throw Error();
    const next=await response.json();if(!next.markets)throw Error();data=next;loadedAt=Date.now();render();
   }catch{
    if(data){render();coverage.textContent+=' · Aggiornamento temporaneamente non disponibile';}
    else{results.innerHTML='<p class="pf-message">Trend temporaneamente non disponibili.</p><button type="button" class="pf-retry">Riprova</button>';results.querySelector('button').onclick=()=>load();}
   }finally{clearTimeout(timer);results.setAttribute('aria-busy','false');pending=null;}
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
