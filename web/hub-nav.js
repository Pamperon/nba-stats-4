/* A+C UI navigation, delegating to original Basket Lab controls. */
(()=>{'use strict';
const $=s=>document.querySelector(s);
const landing=$('.hub-landing'),tiles=$('.hub-tiles'),metrics=$('.hub-live-metrics'),trust=$('.hub-trust-strip'),featured=$('.hub-featured'),insights=$('.hub-insights'),gamesShowcase=$('.hub-games-section'),singleShowcase=$('.hub-single-section'),performance=$('.hub-performance'),methodLink=$('.hub-method-link');
if(!landing||!tiles)return;
const menuToggle=$('.hub-menu-toggle'),menuDrawer=$('#hub-menu-drawer');
function closeMenu(){if(!menuDrawer)return;menuDrawer.hidden=true;menuToggle?.setAttribute('aria-expanded','false');menuToggle?.setAttribute('aria-label','Apri menu di navigazione')}
menuToggle?.addEventListener('click',()=>{const opening=menuDrawer.hidden;menuDrawer.hidden=!opening;menuToggle.setAttribute('aria-expanded',String(opening));menuToggle.setAttribute('aria-label',opening?'Chiudi menu di navigazione':'Apri menu di navigazione')});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu()});
document.addEventListener('click',event=>{if(menuDrawer&&!menuDrawer.hidden&&!event.target.closest('.hub-menu-drawer,.hub-menu-toggle'))closeMenu()});
const tab=name=>$('[data-tab="'+name+'"]');
const go={
 home(){ $('#area-quotes')?.click();tab('dashboard')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 picks(){ $('#area-quotes')?.click();tab('dashboard')?.click();tab('dashboard')?.scrollIntoView({block:'start',behavior:'smooth'});},
 stats(){ $('#area-stats')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 finder(){ $('#area-quotes')?.click();tab('finder')?.click();$('#quote-tabs')?.scrollIntoView({block:'start',behavior:'smooth'});},
 history(){ $('[data-extra="history"]')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 about(){ $('[data-extra="about"]')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 calendar(){renderCalendar();window.scrollTo({top:0,behavior:'smooth'});}
};
let home=true;let calendar=false;
function mark(key){document.querySelectorAll('[data-hub]').forEach(el=>{if(el.dataset.hub===key)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')})}
function display(){const calendarPanel=$('#hub-calendar');if(calendarPanel)calendarPanel.hidden=!calendar;const shell=$('#app');if(shell)shell.hidden=calendar;const extra=!!$('.extra-panel:not([hidden])');landing.hidden=!home||extra;tiles.hidden=!home||extra;if(metrics)metrics.hidden=!home||extra;if(trust)trust.hidden=!home||extra;if(featured)featured.hidden=!home||extra;if(insights)insights.hidden=!home||extra;if(gamesShowcase)gamesShowcase.hidden=!home||extra;if(singleShowcase)singleShowcase.hidden=!home||extra;if(performance)performance.hidden=!home||extra;if(methodLink)methodLink.hidden=!home||extra;}
function select(key){calendar=key==='calendar';home=key==='home';if(key!=='finder')document.body.classList.remove('hub-match-open');mark(key);display();document.body.dataset.hubView=key;}
document.addEventListener('click',event=>{const b=event.target.closest('[data-hub]');if(!b||!go[b.dataset.hub])return;event.preventDefault();go[b.dataset.hub]();select(b.dataset.hub);closeMenu()});
$('#quote-tabs')?.addEventListener('click',event=>{const button=event.target.closest('[data-tab]');if(!button)return;const key=button.dataset.tab==='finder'?'finder':button.dataset.tab==='player'?'stats':'picks';select(key)});
$('#area-stats')?.addEventListener('click',()=>select('stats'));
document.querySelectorAll('[data-extra]').forEach(el=>el.addEventListener('click',()=>select(el.dataset.extra==='history'?'history':'about')));
document.querySelectorAll('[data-return-site]').forEach(el=>el.addEventListener('click',()=>select('picks')));
window.addEventListener('hashchange',()=>{if(location.hash==='#archivio')select('history');else if(location.hash==='#come-funziona')select('about');else display()});
if(location.hash==='#archivio')select('history');else if(location.hash==='#come-funziona')select('about');else select('home');
/* Populate homepage only from values rendered by the existing data engine. */
const metricTarget=$('#metrics'),updated=$('#quote-updated');
function refresh(){
 const count=$('#hub-total'),prob=$('#hub-prob'),last=$('#hub-update');
 const picks=$('#picks');
 const percentages=[...(picks?.querySelectorAll('.pick-values')||[])].map(el=>{const m=el.textContent.match(/STIMA DEL MODELLO\s*(\d+(?:[.,]\d+)?)%/);return m?Number(m[1].replace(',','.')):NaN}).filter(Number.isFinite);
 if(prob)prob.textContent=percentages.length?(percentages.reduce((a,b)=>a+b,0)/percentages.length).toLocaleString('it-IT',{maximumFractionDigits:1})+'%':'—';
 const cards=picks?.querySelectorAll('.pick-selection').length||0;
 if(count)count.textContent=cards?String(cards):'0';
 if(last){const raw=(updated?.textContent||'').trim();const stamp=raw.match(/(?:\d{1,2}:\d{2})(?::\d{2})?/);last.textContent=stamp?stamp[0]:'—';last.title=raw;}
}
if(metricTarget){new MutationObserver(refresh).observe(metricTarget,{childList:true,subtree:true,characterData:true})}
if(updated){new MutationObserver(refresh).observe(updated,{childList:true,subtree:true,characterData:true})}
if($('#picks'))new MutationObserver(refresh).observe($('#picks'),{childList:true,subtree:true});
document.querySelectorAll('[data-pick-group]').forEach(b=>b.addEventListener('click',()=>{go.picks();select('picks');$('#pick-'+b.dataset.pickGroup)?.scrollIntoView({block:'start',behavior:'smooth'});closeMenu()}));
function featuredPicks(){
 const list=$('#hub-featured-list'),picks=$('#picks');
 if(!list||!picks)return;
 const sources=[...picks.querySelectorAll('#pick-giorno .pick-group-items > .pick-selection, .pick-group-daily[aria-label="Analisi preliminari"] .pick-group-items > .pick-selection')].slice(0,5);
 const visibleSources=sources.length?sources:[...picks.querySelectorAll('.pick-selection')].slice(0,5);
 list.replaceChildren();
 for(const source of visibleSources){
  const card=document.createElement('div');card.className='hub-featured-card';
  const content=document.createElement('div');content.className='hub-featured-summary';
  const name=document.createElement('strong');name.textContent=source.querySelector('.pick-player-link')?.textContent||'Analisi NBA';
  const market=document.createElement('p');market.textContent=source.querySelector('.pick-market')?.textContent||'';
  const values=document.createElement('div');values.className='hub-featured-values';
  const blocks=[...source.querySelectorAll('.pick-values > div')];
  for(const block of blocks){const item=document.createElement('div');item.className='hub-featured-value';const label=document.createElement('small');label.textContent=block.querySelector('small')?.textContent||'';const number=document.createElement('strong');number.textContent=block.querySelector('strong')?.textContent||'';item.append(label,number);values.append(item)}
  if(!blocks.length){const fallback=document.createElement('span');fallback.textContent=(source.querySelector('.pick-values')?.textContent||'').replace(/\s+/g,' ').trim();values.append(fallback)}
  const avatar=source.querySelector('.pick-avatar');if(avatar){const clone=avatar.cloneNode(true);clone.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));clone.classList.add('hub-featured-avatar');content.append(clone)}
  content.append(name,market,values);card.append(content);
  const action=document.createElement('button');action.type='button';action.textContent='Statistiche giocatore →';
  action.addEventListener('click',()=>{go.picks();select('picks');source.querySelector('.pick-stats-button')?.click()});
  card.append(action);list.append(card);
 }
 if(!visibleSources.length)list.textContent='Nessuna selezione disponibile per la giornata.';
}
function updateInsights(){
 const picks=$('#picks'),games=$('#hub-games'),trends=$('#hub-trends');if(!picks||!games||!trends)return;
 const matches=[...new Set([...picks.querySelectorAll('.pick-fixture')].map(el=>el.dataset.match||el.textContent.trim()).filter(Boolean))];
 games.replaceChildren();
 if(!matches.length)games.textContent='Nessuna partita nelle selezioni della giornata.';
 for(const match of matches.slice(0,5)){const el=document.createElement('div');el.className='hub-game';el.textContent=match;games.append(el)}
 const markets=[...picks.querySelectorAll('.pick-market')].map(el=>el.textContent.trim()).filter(Boolean);
 trends.replaceChildren();
 if(!markets.length)trends.textContent='Nessuna selezione disponibile.';
 const counts=new Map();for(const market of markets){const type=market.toUpperCase().startsWith('UNDER')?'Under':'Over';counts.set(type,(counts.get(type)||0)+1)}
 for(const [type,count] of counts){const el=document.createElement('div');el.className='hub-trend';const label=document.createElement('span');label.textContent=type+' nelle selezioni';const value=document.createElement('strong');value.textContent=String(count);el.append(label,value);trends.append(el)}
}
const matchTeamCodes={'Orlando Magic':'orl','Boston Celtics':'bos','Brooklyn Nets':'bkn','Indiana Pacers':'ind','Atlanta Hawks':'atl','Charlotte Hornets':'cha','Chicago Bulls':'chi','Cleveland Cavaliers':'cle','Dallas Mavericks':'dal','Denver Nuggets':'den','Detroit Pistons':'det','Golden State Warriors':'gs','Houston Rockets':'hou','Los Angeles Clippers':'lac','Los Angeles Lakers':'lal','Memphis Grizzlies':'mem','Miami Heat':'mia','Milwaukee Bucks':'mil','Minnesota Timberwolves':'min','New Orleans Pelicans':'no','New York Knicks':'ny','Oklahoma City Thunder':'okc','Philadelphia 76ers':'phi','Phoenix Suns':'phx','Portland Trail Blazers':'por','Sacramento Kings':'sac','San Antonio Spurs':'sa','Toronto Raptors':'tor','Utah Jazz':'utah','Washington Wizards':'wsh'};
let activeMatch='',matchMarket='ALL';
const cleanName=name=>String(name||'').split(',').reverse().map(x=>x.trim()).filter(Boolean).join(' ')||String(name||'');
const displayNum=value=>{const n=Number(String(value??'').replace(',','.'));return Number.isFinite(n)?n.toLocaleString('it-IT',{maximumFractionDigits:2}):'—'};
function openMatchQuotes(match){
 activeMatch=match;calendar=false;
 go.finder();select('finder');document.body.classList.add('hub-match-open');
 const panel=$('#hub-match-detail');if(panel)panel.hidden=false;
 const title=$('#hub-match-title');
 if(title){title.replaceChildren();const teams=match.split(/\s+-\s+|\s+vs\.?\s+/i);
  teams.forEach((team,i)=>{
   if(i){const vs=document.createElement('b');vs.textContent='VS';title.append(vs)}
   const wrap=document.createElement('div');wrap.className='hub-match-team';
   const code=matchTeamCodes[team.trim()];
   if(code){const img=document.createElement('img');img.src='https://a.espncdn.com/i/teamlogos/nba/500/'+code+'.png';img.alt='';img.loading='lazy';img.onerror=()=>{img.hidden=true};wrap.append(img)}
   const name=document.createElement('strong');name.textContent=team;wrap.append(name);title.append(wrap);
  });
 }
 const fixture=$('#finder-fixture');
 if(fixture){const available=[...fixture.options].map(option=>option.value);const norm=v=>String(v||'').toLowerCase().replace(/[^a-z0-9]/g,'');fixture.value=available.find(v=>v===match)||available.find(v=>norm(v)===norm(match))||'';fixture.dispatchEvent(new Event('change',{bubbles:true}))}
 matchMarket='ALL';$('#hub-match-search').value='';setMatchTab('analysis');renderMatchPlayers();
 panel?.scrollIntoView({block:'start',behavior:'smooth'});
}
function setMatchTab(tab){
 document.querySelectorAll('[data-match-tab]').forEach(button=>{button.classList.toggle('active',button.dataset.matchTab===tab);button.setAttribute('aria-selected',String(button.dataset.matchTab===tab))});
 const analysis=$('#hub-match-analysis'),players=$('#hub-match-player-section');
 if(analysis)analysis.hidden=tab==='players';
 if(players)players.hidden=tab==='stats';
 if(analysis){
  const title=analysis.querySelector('h3');
  if(tab==='stats'){
   title.textContent='Statistiche delle linee disponibili';
   const rows=window.BasketLabMatchRows?.()||[];
   const markets=['PTS','REB','AST'].map(m=>({market:m,count:rows.filter(row=>row.Mercato===m).length}));
   const boxes=analysis.querySelectorAll('.hub-match-data-block');
   if(boxes[0]){boxes[0].querySelector('small').textContent='Linee analizzate';boxes[0].querySelector('strong').textContent=String(rows.length);boxes[0].querySelector('p').textContent='Linee player props salvate per questa partita.'}
   if(boxes[1]){boxes[1].querySelector('small').textContent='Mercati disponibili';boxes[1].querySelector('strong').textContent=markets.filter(m=>m.count).length+' su 3';boxes[1].querySelector('p').textContent=markets.map(m=>m.market+': '+m.count).join(' · ')}
  }else{
   title.innerHTML='<span class="hub-accent-icon">▥</span> Analisi partita';
   const boxes=analysis.querySelectorAll('.hub-match-data-block');
   if(boxes[0]){boxes[0].querySelector('small').textContent='Probabilità di vittoria';boxes[0].querySelector('strong').textContent='Non disponibile';boxes[0].querySelector('p').textContent='Non viene calcolata dal modello player props.'}
   if(boxes[1]){boxes[1].querySelector('small').textContent='Punti attesi';boxes[1].querySelector('strong').textContent='Non disponibili';boxes[1].querySelector('p').textContent='Serve un modello dedicato ai punteggi di squadra.'}
  }
 }
 if(tab==='players')players?.scrollIntoView({block:'nearest',behavior:'smooth'});
}
function renderMatchPlayers(){
 if(!document.body.classList.contains('hub-match-open'))return;
 const list=$('#hub-match-player-list'),count=$('#hub-match-player-count');if(!list)return;
 const rows=typeof window.BasketLabMatchRows==='function'?window.BasketLabMatchRows():[];
 const q=($('#hub-match-search')?.value||'').toLowerCase().trim();
 const groups=new Map();
 for(const row of rows){
  if(q&&!cleanName(row.Giocatore).toLowerCase().includes(q)&&!String(row.Giocatore).toLowerCase().includes(q))continue;
  if(matchMarket!=='ALL'&&row.Mercato!==matchMarket)continue;
  const key=JSON.stringify([row.Squadra,row['ESPN ID']||row.Giocatore]);
  if(!groups.has(key))groups.set(key,{name:cleanName(row.Giocatore),team:row.Squadra,rows:[]});
  groups.get(key).rows.push(row);
 }
 list.replaceChildren();if(count)count.textContent=groups.size+' giocatori · '+rows.length+' linee';
 if(!groups.size){list.textContent='Nessuna linea disponibile con questi filtri.';return}
 for(const group of groups.values()){
  const card=document.createElement('article');card.className='hub-match-player-card';
  const header=document.createElement('div');header.className='hub-match-player-identity';
  const info=document.createElement('div');const name=document.createElement('strong');name.textContent=group.name;
  const team=document.createElement('small');team.textContent=group.team||'';info.append(name,team);header.append(info);
  const stats=document.createElement('button');stats.type='button';stats.textContent='Statistiche ›';stats.onclick=()=>window.BasketLabMatchPlayerStats?.(group.rows[0]);header.append(stats);card.append(header);
  const markets=document.createElement('div');markets.className='hub-match-player-markets';
  for(const market of ['PTS','REB','AST']){
   const subset=group.rows.filter(row=>row.Mercato===market);
   if(!subset.length)continue;
   const block=document.createElement('div');block.className='hub-match-player-market';
   const label=document.createElement('small');label.textContent=({PTS:'PUNTI',REB:'RIMBALZI',AST:'ASSIST'})[market];block.append(label);
   const featured=subset.find(row=>String(row.Scelta||'').toUpperCase()==='OVER')||subset[0];
   const line=document.createElement('strong');line.textContent=displayNum(featured.Linea);block.append(line);
   const quote=document.createElement('span');quote.textContent=String(featured.Scelta||'OVER').toUpperCase()+' '+displayNum(featured.Quota);block.append(quote);
   const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent=subset.length+' linee · Mostra tutte';details.append(summary);
   for(const row of subset){const entry=document.createElement('div');entry.className='hub-match-quote-line';entry.textContent=String(row.Scelta||'OVER').toUpperCase()+' '+displayNum(row.Linea)+' · quota '+displayNum(row.Quota)+' · stima '+displayNum(row['Prob. stimata %'])+'%';details.append(entry)}
   block.append(details);markets.append(block);
  }
  card.append(markets);list.append(card);
 }
}
document.querySelectorAll('[data-match-tab]').forEach(button=>button.addEventListener('click',()=>setMatchTab(button.dataset.matchTab)));
$('#hub-match-search')?.addEventListener('input',renderMatchPlayers);
document.querySelectorAll('#hub-match-market-buttons button').forEach(button=>button.addEventListener('click',()=>{matchMarket=button.dataset.market;document.querySelectorAll('#hub-match-market-buttons button').forEach(b=>b.classList.toggle('active',b===button));renderMatchPlayers()}));
$('#hub-match-back')?.addEventListener('click',()=>{document.body.classList.remove('hub-match-open');$('#hub-match-detail').hidden=true;go.home();select('home')});
function renderCalendar(){
 const dates=$('#hub-calendar-dates'),games=$('#hub-calendar-games');if(!dates||!games)return;
 dates.replaceChildren();games.replaceChildren();
 const source=$('#date-strip');
 const dayButtons=[...(source?.querySelectorAll('button')||[])];
 for(const day of dayButtons){
  const button=document.createElement('button');button.type='button';button.textContent=day.textContent.trim();button.className=day.className;
  button.addEventListener('click',()=>{day.click();setTimeout(renderCalendar,150)});
  dates.append(button);
 }
 const fixture=$('#finder-fixture');
 const matches=[...(fixture?.options||[])].map(o=>o.value).filter(Boolean);
 const unique=[...new Set(matches)];
 if(!unique.length){games.textContent='Nessuna partita con quote disponibili per la giornata selezionata.';return}
 for(const match of unique){
  const row=document.createElement('button');row.type='button';row.className='hub-calendar-match';row.textContent=match+' · Analisi e quote ›';
  row.addEventListener('click',()=>openMatchQuotes(match));games.append(row)
 }
}
function refreshShowcase(){
 const picks=$('#picks'),single=$('#hub-single-content'),state=$('#hub-single-state'),games=$('#hub-games-showcase');
 if(!picks)return;
 if(single){
  const group=picks.querySelector('.pick-group[aria-label="Singola del giorno"]');
  const pick=group?.querySelector('.pick-selection');
  single.replaceChildren();
  if(pick){
   const clone=pick.cloneNode(true);clone.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));
   clone.querySelectorAll('button,a').forEach(el=>{el.removeAttribute('href');el.setAttribute('tabindex','-1');el.setAttribute('aria-hidden','true')});
   single.append(clone);
   const action=document.createElement('button');action.type='button';action.className='hub-single-action';action.textContent='Apri analisi completa →';action.addEventListener('click',()=>{go.picks();select('picks');group.scrollIntoView({behavior:'smooth',block:'start'})});single.append(action);
  }else{const empty=document.createElement('p');empty.textContent=group?.querySelector('p:last-child')?.textContent||'Nessuna Singola idonea disponibile per questa giornata.';single.append(empty)}
  if(state)state.textContent=group?.querySelector('h2')?.textContent?.toLowerCase().includes('preliminare')?'Anteprima':'Ufficiale / in attesa';
 }
 if(games){
  const matches=[...new Set([...picks.querySelectorAll('.pick-fixture')].map(el=>el.dataset.match||el.textContent.trim()).filter(Boolean))];
  games.replaceChildren();
  if(!matches.length){games.textContent='Le partite della giornata compariranno con le analisi disponibili.';return}
  const teamCodes={'Atlanta Hawks':'atl','Boston Celtics':'bos','Brooklyn Nets':'bkn','Charlotte Hornets':'cha','Chicago Bulls':'chi','Cleveland Cavaliers':'cle','Dallas Mavericks':'dal','Denver Nuggets':'den','Detroit Pistons':'det','Golden State Warriors':'gs','Houston Rockets':'hou','Indiana Pacers':'ind','Los Angeles Clippers':'lac','LA Clippers':'lac','Los Angeles Lakers':'lal','Memphis Grizzlies':'mem','Miami Heat':'mia','Milwaukee Bucks':'mil','Minnesota Timberwolves':'min','New Orleans Pelicans':'no','New York Knicks':'ny','Oklahoma City Thunder':'okc','Orlando Magic':'orl','Philadelphia 76ers':'phi','Phoenix Suns':'phx','Portland Trail Blazers':'por','Sacramento Kings':'sac','San Antonio Spurs':'sa','Toronto Raptors':'tor','Utah Jazz':'utah','Washington Wizards':'wsh'};
  for(const match of matches.slice(0,6)){
   const row=document.createElement('button');row.type='button';row.className='hub-match-row';
   const teams=match.split(/\s+-\s+|\s+vs\.?\s+|\s+@\s+/i).map(x=>x.trim());
   const n=[...picks.querySelectorAll('.pick-fixture')].filter(el=>(el.dataset.match||el.textContent.trim())===match).length;
   const pair=document.createElement('div');pair.className='hub-match-teams';
   if(teams.length===2 && teams.every(t=>teamCodes[t])){
    for(let i=0;i<2;i++){
     const badge=document.createElement('span');badge.className='hub-team';
     const logo=document.createElement('img');logo.alt='';logo.loading='lazy';logo.width=32;logo.height=32;logo.src='https://a.espncdn.com/i/teamlogos/nba/500/'+teamCodes[teams[i]]+'.png';
     logo.addEventListener('error',()=>{logo.hidden=true});
     const label=document.createElement('strong');label.textContent=teams[i].split(' ').slice(-1)[0];
     badge.append(logo,label);pair.append(badge);
     if(i===0){const versus=document.createElement('small');versus.textContent='VS';pair.append(versus)}
    }
   }else{const name=document.createElement('strong');name.textContent=match;pair.append(name)}
   const count=document.createElement('span');count.className='hub-match-count';count.textContent='Quote e linee ›';
   row.append(pair,count);row.addEventListener('click',()=>openMatchQuotes(match));games.append(row);
  }
 }
}
if($('#picks'))new MutationObserver(()=>{featuredPicks();updateInsights();refreshShowcase()}).observe($('#picks'),{childList:true});
refresh();featuredPicks();updateInsights();refreshShowcase();
})();