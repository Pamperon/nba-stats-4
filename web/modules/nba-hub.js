/* NBA directory: standings, team schedules and current rosters. */
(function(w){
 'use strict';
 const panel=document.getElementById('hub-calendar');if(!panel)return;
 const calendar=document.createElement('div');calendar.id='nba-calendar-content';
 while(panel.firstChild)calendar.append(panel.firstChild);
 const nav=document.createElement('nav');nav.className='history-mode-tabs nba-tabs';nav.setAttribute('aria-label','Sezione NBA');
 nav.innerHTML='<a href="/nba" data-nba-tab="calendar">Calendario</a><a href="/nba/classifica" data-nba-tab="standings">Classifica</a>';
 const content=document.createElement('div');content.id='nba-content';content.hidden=true;panel.append(nav,calendar,content);
 let state={nbaTab:'calendar',team:''},callbacks={},request=0;
 try{const saved=JSON.parse(sessionStorage.getItem('bl-nba-view')||'null');if(saved&&['calendar','standings'].includes(saved.nbaTab))state=saved;}catch{}
 const cache=new Map();
 async function get(url){let item=cache.get(url);if(item&&Date.now()-item.at<300000)return item.promise;item={at:Date.now(),promise:fetch(url).then(r=>{if(!r.ok)throw Error();return r.json()}).catch(e=>{cache.delete(url);throw e;})};cache.set(url,item);if(cache.size>70)cache.delete(cache.keys().next().value);return item.promise;}
 function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
 function slug(name,id){return name.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'-'+id;}
 const teamURL=t=>'/squadre/'+slug(t.name,t.id);
 const number=(n,d=0)=>n==null?'—':Number(n).toLocaleString('it-IT',{maximumFractionDigits:d,minimumFractionDigits:d});
 function logo(src){return /^https:\/\/(?:a\.espncdn\.com|a[0-9]?\.espncdn\.com)\//.test(src||'')?'<img loading="lazy" src="'+esc(src)+'" alt="" onerror="this.hidden=true">':'';}
 function remember(){try{sessionStorage.setItem('bl-nba-view',JSON.stringify(state))}catch{}}
 function navigate(next){state=next;remember();callbacks.select?.();show();w.scrollTo({top:0,behavior:'instant'});}
 nav.addEventListener('click',e=>{const a=e.target.closest('[data-nba-tab]');if(!a||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();navigate({nbaTab:a.dataset.nbaTab,team:''});});
 content.addEventListener('click',e=>{
  const a=e.target.closest('[data-nba-team]');if(a&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey&&!e.altKey){e.preventDefault();navigate({nbaTab:'standings',team:a.dataset.nbaTeam});}
  if(e.target.closest('[data-nba-back]'))navigate({nbaTab:'standings',team:''});
  if(e.target.closest('[data-nba-retry]'))show();
 });
 function message(node,text){node.innerHTML='<p class="nba-message" role="status">'+esc(text)+'</p>';}
 async function show(){
  document.body.classList.remove('hub-boxscore-open');
  nav.hidden=!!state.team;
  const token=++request;calendar.hidden=state.nbaTab!=='calendar'||!!state.team;content.hidden=!calendar.hidden;
  for(const a of nav.querySelectorAll('a')){const active=a.dataset.nbaTab===state.nbaTab;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}
  if(!calendar.hidden){callbacks.calendar?.();return;}
  message(content,'Caricamento dati NBA…');
  if(state.team){await teamPage(state.team,token);return;}
  try{
   const data=await get('/api/nba/standings');if(token!==request)return;
   content.innerHTML='<p class="nba-legend"><span class="nba-dot playoff"></span> 1–6: zona playoff <span class="nba-dot playin"></span> 7–10: zona play-in</p><div class="nba-conferences">'+data.conferences.map(c=>'<section class="nba-conference"><h2>'+esc(c.name)+'</h2><div class="nba-table-scroll"><table class="nba-standings"><thead><tr><th scope="col">#</th><th scope="col">Squadra</th><th scope="col"><abbr title="Vittorie">V</abbr></th><th scope="col"><abbr title="Sconfitte">S</abbr></th><th scope="col">% V</th><th scope="col"><abbr title="Partite di distacco dalla prima">GB</abbr></th></tr></thead><tbody>'+c.teams.map(t=>'<tr class="'+(t.rank&&t.rank<=6?'nba-playoff':t.rank&&t.rank<=10?'nba-playin':'')+'"><td>'+number(t.rank)+'</td><th scope="row"><a href="'+teamURL(t)+'" data-nba-team="'+slug(t.name,t.id)+'">'+logo(t.logo)+'<span>'+esc(t.name)+'</span></a></th><td>'+number(t.wins)+'</td><td>'+number(t.losses)+'</td><td>'+number(t.win_percent==null?null:t.win_percent*100,1)+'</td><td>'+esc(t.games_behind)+'</td></tr>').join('')+'</tbody></table></div></section>').join('')+'</div><p class="nba-note">Posizioni attuali di regular season, non qualificazioni definitive. V: vittorie · S: sconfitte · GB: partite di distacco. Aggiornamento periodico.</p>';
  }catch{if(token===request)content.innerHTML='<p class="nba-message" role="status">Classifica temporaneamente non disponibile.</p><button class="bl-back" data-nba-retry>Riprova</button>';}
 }
 function gameList(node,games,empty){
  node.replaceChildren();if(!games.length){message(node,empty);return;}
  for(const g of games){
   const b=document.createElement('button');b.type='button';b.className='nba-game';
   const date=new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'short',...(g.time_valid?{hour:'2-digit',minute:'2-digit'}:{}),timeZone:'Europe/Rome'}).format(new Date(g.start_at));
   b.innerHTML='<span class="nba-game-date">'+esc(date)+(g.time_valid?'':' · orario da definire')+'</span><span class="nba-game-teams">'+esc(g.away)+' <span>vs</span> '+esc(g.home)+'</span><strong>'+(g.state==='post'?esc(g.away_score??'—')+' – '+esc(g.home_score??'—'):g.state==='in'?'LIVE':'›')+'</strong>';
   b.addEventListener('click',()=>callbacks.fixture?.(g));node.append(b);
  }
 }
 async function teamPage(teamSlug,token){
  const id=teamSlug.match(/-(\d{1,8})$/)?.[1];if(!id){message(content,'Squadra non trovata');return;}
  content.innerHTML='<button class="bl-back" type="button" data-nba-back>‹ Torna alla classifica</button><div id="nba-team-hero"><p class="nba-message">Caricamento squadra…</p></div><div class="nba-team-metrics" id="nba-team-metrics"></div><section class="nba-team-section"><h2>Prossime partite</h2><div id="nba-team-next" class="nba-game-list"><p role="status">Caricamento calendario…</p></div></section><section class="nba-team-section"><h2>Ultimi risultati</h2><div id="nba-team-recent" class="nba-game-list"></div></section><section class="nba-team-section"><h2>Rosa</h2><div id="nba-team-roster" class="nba-roster"><p role="status">Caricamento rosa…</p></div></section><p class="nba-note">Dati ESPN · Orari italiani · Rosa corrente, indipendente dalle quote disponibili.</p>';
  const find=s=>content.querySelector(s);
  await Promise.allSettled([
   get('/api/nba/teams/'+id).then(d=>{if(token!==request)return;const t=d.team;find('#nba-team-hero').innerHTML='<header class="nba-team-hero" style="--nba-team-color:#'+esc(t.color)+'"><div>'+logo(t.logo)+'</div><div><span class="nba-eyebrow">NBA · '+esc(t.season)+'</span><h1>'+esc(t.name)+'</h1><p>'+esc(t.record)+' · Vittorie / Sconfitte</p></div></header>';gameList(find('#nba-team-next'),d.upcoming,'Nessuna prossima partita disponibile nel calendario ESPN.');gameList(find('#nba-team-recent'),d.recent,'Nessun risultato disponibile per questa stagione.');}).catch(()=>{if(token!==request)return;message(find('#nba-team-hero'),'Dati squadra temporaneamente non disponibili.');message(find('#nba-team-next'),'Calendario temporaneamente non disponibile.');message(find('#nba-team-recent'),'Risultati temporaneamente non disponibili.');}),
   get('/api/nba/standings').then(d=>{if(token!==request)return;const conf=d.conferences.find(c=>c.teams.some(t=>t.id===id)),t=conf?.teams.find(t=>t.id===id);if(!t)return;find('#nba-team-metrics').innerHTML=[['Posizione',number(t.rank)+'ª',conf.name],['Vittorie',number(t.win_percent==null?null:t.win_percent*100,1)+'%',number(t.wins)+' V · '+number(t.losses)+' S'],['Punti segnati',number(t.points_for,1),'Media a partita'],['Punti subiti',number(t.points_against,1),'Media a partita'],['In casa',t.home_record,'Vittorie / Sconfitte'],['In trasferta',t.away_record,'Vittorie / Sconfitte'],['Ultime 10',t.last_ten,'Vittorie / Sconfitte'],['Serie',t.streak,'W: vittorie · L: sconfitte']].map(([label,value,note])=>'<div class="nba-metric"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong><small>'+esc(note)+'</small></div>').join('');}).catch(()=>{if(token===request)message(find('#nba-team-metrics'),'Classifica e medie temporaneamente non disponibili.');}),
   get('/api/players/roster?team_id='+id).then(d=>{if(token!==request)return;find('#nba-team-roster').innerHTML=d.players.length?d.players.map(p=>'<a class="nba-player" href="/giocatori/'+slug(p.name,p.id)+'"><img loading="lazy" src="/api/players/headshot/'+esc(p.id)+'" alt="" onerror="this.hidden=true"><span><strong>'+esc(p.name)+'</strong><small>'+esc(p.jersey?'#'+p.jersey+' · ':'')+esc(p.position||'Giocatore')+'</small></span><span aria-hidden="true">›</span></a>').join(''):'<p>Rosa non ancora disponibile.</p>';}).catch(()=>{if(token===request)message(find('#nba-team-roster'),'Rosa temporaneamente non disponibile.');})
  ]);
 }
 w.BasketLabNBA={init(c){callbacks=c;if(document.body.dataset.hubView==='calendar')show();},show,route(){return {...state}},apply(route){state={nbaTab:route.nbaTab||'calendar',team:route.team||''};remember();},resetCalendar(){nav.hidden=false;state={nbaTab:'calendar',team:''};remember();calendar.hidden=false;content.hidden=true;for(const a of nav.querySelectorAll('a')){const active=a.dataset.nbaTab==='calendar';a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');}}};
})(window);
