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
let activeMatch='',matchMarket='PTS',matchFormRequest=0;
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
 const teamSelect=$('#hub-match-team-filter');if(teamSelect){teamSelect.replaceChildren();const both=document.createElement('option');both.value='';both.textContent='Entrambe le squadre';teamSelect.append(both);for(const teamName of match.split(/\s+-\s+|\s+vs\.?\s+/i)){const option=document.createElement('option');option.value=teamName.trim();option.textContent=teamName.trim();teamSelect.append(option)}}
 const meta=$('#hub-match-fixture-meta');if(meta){const selected=$('#date')?.value;meta.textContent=selected?selected.split('-').reverse().join('/'):'Partita NBA'}
 const oddMin=$('#hub-match-odd-min'),oddMax=$('#hub-match-odd-max');if(oddMin)oddMin.value='1.20';if(oddMax)oddMax.value='2.20';if($('#hub-match-sort'))$('#hub-match-sort').value='team';
 matchMarket='PTS';document.querySelectorAll('#hub-match-market-buttons button').forEach(b=>b.classList.toggle('active',b.dataset.market==='PTS'));$('#hub-match-search').value='';setMatchTab('analysis');renderMatchPlayers();
 panel?.scrollIntoView({block:'start',behavior:'smooth'});
}
const matchTeamPalette={atl:'#e03a3e',bos:'#007a33',bkn:'#c5c5c5',cha:'#1d8cab',chi:'#ce1141',cle:'#b58a43',dal:'#0053bc',den:'#fdb927',det:'#c8102e',gs:'#ffc72c',hou:'#ce1141',ind:'#fdbb30',lac:'#c8102e',lal:'#fdb927',mem:'#5d76a9',mia:'#98002e',mil:'#00471b',min:'#236192',no:'#b4975a',ny:'#f58426',okc:'#007ac1',orl:'#0077c0',phi:'#006bb6',phx:'#e56020',por:'#e03a3e',sac:'#5a2d81',sa:'#a5acaf',tor:'#ce1141',utah:'#753bbd',wsh:'#e31837'};
function renderMatchCharts(teams,a,b,windowDays,matchOdds){
 const area=$('#hub-match-charts');if(!area)return;area.replaceChildren();
 const colors=teams.map(t=>matchTeamPalette[matchTeamCodes[t]]||'#4388b9');
 const panel=$('#hub-match-analysis');if(panel){panel.style.setProperty('--match-team-a',colors[0]);panel.style.setProperty('--match-team-b',colors[1]);}
 const card=document.createElement('div');card.className='hub-match-chart-card hub-match-comparison';
 const win=document.createElement('div');win.className='hub-match-compare-column';
 const winTitle=document.createElement('strong');winTitle.className='hub-match-compare-title';winTitle.textContent='Probabilità di vittoria';win.append(winTitle);
 const validOdds=Array.isArray(matchOdds)&&matchOdds.length===2&&matchOdds.every(x=>Number.isFinite(Number(x))&&Number(x)>1);
 if(validOdds){const implied=matchOdds.map(x=>1/Number(x));const total=implied[0]+implied[1];teams.forEach((team,i)=>{const pct=implied[i]/total*100;const row=document.createElement('div');row.className='hub-match-win-row';const heading=document.createElement('div');heading.className='hub-match-win-label';const name=document.createElement('span');name.textContent=team;const number=document.createElement('b');number.textContent=pct.toLocaleString('it-IT',{maximumFractionDigits:1})+'%';heading.append(name,number);const track=document.createElement('div');track.className='hub-match-chart-track';const fill=document.createElement('div');fill.className='hub-match-chart-fill';fill.style.width=pct+'%';fill.style.background=colors[i];track.append(fill);row.append(heading,track);win.append(row)})}
 else{const unavailable=document.createElement('p');unavailable.className='hub-match-win-unavailable';unavailable.textContent='Quote vincente partita non disponibili';win.append(unavailable);}
 const points=document.createElement('div');points.className='hub-match-compare-column';
 const ptsTitle=document.createElement('strong');ptsTitle.className='hub-match-compare-title';ptsTitle.textContent='Media punti segnati';points.append(ptsTitle);
 teams.forEach((team,i)=>{const row=document.createElement('div');row.className='hub-match-points-row';const name=document.createElement('span');name.textContent=team;const value=document.createElement('b');value.textContent=[a,b][i].avg_points==null?'—':displayNum([a,b][i].avg_points);row.append(name,value);points.append(row)});
 card.append(win,points);area.append(card);
 const form=document.createElement('div');form.className='hub-match-quick-tile';const label=document.createElement('strong');label.textContent='Forma (ultime 5)';const value=document.createElement('span');value.textContent=teams.map((team,i)=>team.split(' ').slice(-1)[0]+' '+[a,b][i].wins+'-'+[a,b][i].losses).join(' · ');form.append(label,value);area.append(form);
 const streak=document.createElement('div');streak.className='hub-match-form-streak';teams.forEach((team,i)=>{const group=document.createElement('div');const name=document.createElement('small');name.textContent=team;group.append(name);const dots=document.createElement('div');dots.className='hub-match-form-dots';for(const game of [a,b][i].results||[]){const dot=document.createElement('span');dot.className=game.scored>game.allowed?'won':'lost';dot.title=game.date+' · '+game.scored+'-'+game.allowed+' vs '+game.opponent;dot.setAttribute('aria-label',game.scored>game.allowed?'Vittoria':'Sconfitta');dots.append(dot)}group.append(dots);streak.append(group)});area.append(streak);
 const note=document.createElement('p');note.className='hub-match-chart-note';note.textContent='Fonte ESPN · Ultime 5 gare disponibili negli ultimi '+windowDays+' giorni. Medie osservate, non punti attesi.';area.append(note);
}
function renderMatchH2H(teams,games){
 const facts=$('#hub-match-analysis .hub-match-facts');
 if(!facts)return;
 let widget=$('#hub-match-h2h-chart');
 if(!widget){widget=document.createElement('div');widget.id='hub-match-h2h-chart';widget.className='hub-match-h2h-chart';facts.insertAdjacentElement('afterend',widget)}
 widget.replaceChildren();
 const heading=document.createElement('strong');heading.textContent='Scontri diretti';widget.append(heading);
 if(!games.length){const empty=document.createElement('p');empty.textContent='Nessuno scontro diretto nel periodo esaminato';widget.append(empty);return}
 const wins=teams.map(team=>games.filter(game=>{const index=game.teams.indexOf(team);return index>=0&&Number(game.scores[index])>Number(game.scores[1-index])}).length);
 const names=document.createElement('div');names.className='hub-match-h2h-names';
 teams.forEach((team,i)=>{const side=document.createElement('span');side.textContent=team+' · '+wins[i];names.append(side)});widget.append(names);
 const bar=document.createElement('div');bar.className='hub-match-h2h-bar';
 const colors=teams.map(team=>matchTeamPalette[matchTeamCodes[team]]||'#4388b9');
 wins.forEach((count,i)=>{const segment=document.createElement('span');segment.style.width=(100*count/games.length)+'%';segment.style.background=colors[i];bar.append(segment)});widget.append(bar);
 const note=document.createElement('small');note.textContent=games.length+' '+(games.length===1?'partita':'partite')+' negli ultimi 21 giorni';widget.append(note);
}
async function loadMatchForm(match){
 const request=++matchFormRequest;
 const teams=match.split(/\s+-\s+|\s+vs\.?\s+/i).map(x=>x.trim());
 const panel=$('#hub-match-analysis');if(!panel||teams.length!==2)return;
 const boxes=panel.querySelectorAll('.hub-match-data-block');
 const facts=panel.querySelectorAll('.hub-match-facts>div');
 const summary=panel.querySelector('.hub-match-summary p');
 for(const block of boxes){block.querySelector('strong').textContent='Caricamento…';block.querySelector('p').textContent='Consultazione risultati ESPN verificati'}
 for(const fact of facts)fact.querySelector('small').textContent='Caricamento…';
 try{
  const date=$('#date')?.value;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date||''))throw new Error('Data non disponibile');
  const url='/api/match/form?date='+encodeURIComponent(date)+'&team_a='+encodeURIComponent(teams[0])+'&team_b='+encodeURIComponent(teams[1]);
  const response=await fetch(url);
  if(!response.ok)throw new Error('ESPN temporaneamente non disponibile');
  const data=await response.json();
  if(request!==matchFormRequest||activeMatch!==match)return;
  const fixtureMeta=$('#hub-match-fixture-meta');
  if(fixtureMeta){
   const dateLabel=date.split('-').reverse().join('/');
   const time=data.fixture_time?new Date(data.fixture_time):null;
   const clock=time&&!Number.isNaN(time.getTime())?time.toLocaleTimeString('it-IT',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Rome'}):null;
   fixtureMeta.textContent=dateLabel+(clock?' · ore '+clock:'');
  }
  const [a,b]=data.teams||[];
  if(!a||!b)throw new Error('Dati incompleti');
  renderMatchCharts(teams,a,b,data.window_days,data.moneyline_odds);
  boxes[0].querySelector('small').textContent='Forma recente · ultime 5 disponibili';
  boxes[0].querySelector('strong').textContent=teams[0]+': '+a.wins+'V / '+a.losses+'P';
  boxes[0].querySelector('p').textContent=teams[1]+': '+b.wins+'V / '+b.losses+'P · Campione: '+a.games+' e '+b.games+' partite negli ultimi '+data.window_days+' giorni';
  boxes[1].querySelector('small').textContent='Media punti segnati · ultime 5';
  boxes[1].querySelector('strong').textContent=(a.avg_points??'—')+' vs '+(b.avg_points??'—');
  boxes[1].querySelector('p').textContent='Medie osservate, non previsioni del risultato finale';
  facts[0].querySelector('small').textContent=a.games&&b.games?teams[0]+': '+a.wins+'/'+a.games+' · '+teams[1]+': '+b.wins+'/'+b.games:'Campione storico insufficiente';
  const h2h=data.h2h||[];
  renderMatchH2H(teams,h2h);
  facts[1].querySelector('small').textContent=h2h.length?h2h.length+' scontri diretti analizzati':'Nessuno scontro diretto';
  facts[2].querySelector('small').textContent=a.avg_points!=null&&b.avg_points!=null?'Medie segnate: '+a.avg_points+' / '+b.avg_points:'Dati insufficienti';
  if(summary){const delta=a.avg_points!=null&&b.avg_points!=null?Math.abs(Number(a.avg_points)-Number(b.avg_points)).toLocaleString('it-IT',{maximumFractionDigits:1}):null;summary.textContent=(a.wins===b.wins?'Le due squadre hanno lo stesso numero di vittorie recenti.':(a.wins>b.wins?teams[0]:teams[1])+' ha ottenuto più vittorie nelle ultime cinque partite.')+(delta!==null?' '+(Number(a.avg_points)>Number(b.avg_points)?teams[0]:teams[1])+' segna in media '+delta+' punti in più.':'')+' Sono indicatori descrittivi, non una previsione della partita.';}
 }catch(error){
  if(request!==matchFormRequest)return;
  $('#hub-match-charts')?.replaceChildren();
  boxes[0].querySelector('strong').textContent='Dati non disponibili';
  boxes[0].querySelector('p').textContent='Risultati ESPN non accessibili in questo momento';
  boxes[1].querySelector('strong').textContent='—';
  boxes[1].querySelector('p').textContent='Nessuna stima inventata';
  for(const fact of facts)fact.querySelector('small').textContent='Dati temporaneamente non disponibili';
 }
}
function renderMatchMarketStats(){
 const analysis=$('#hub-match-analysis');if(!analysis)return;
 const rows=window.BasketLabMatchRows?.(activeMatch)||[];
 const markets=['PTS','REB','AST'].map(m=>({market:m,count:rows.filter(row=>row.Mercato===m).length}));
 let statsPanel=$('#hub-match-market-distribution');
 if(!statsPanel){statsPanel=document.createElement('div');statsPanel.id='hub-match-market-distribution';statsPanel.className='hub-match-market-distribution';analysis.append(statsPanel)}
 statsPanel.replaceChildren();
 const heading=document.createElement('strong');heading.textContent='Statistiche delle linee disponibili';statsPanel.append(heading);
 const overview=document.createElement('p');overview.textContent=rows.length+' linee analizzate · '+markets.filter(m=>m.count).length+' mercati su 3';statsPanel.append(overview);
 const track=document.createElement('div');track.className='hub-match-market-track';
 for(const m of markets){if(!m.count)continue;const seg=document.createElement('span');seg.className='market-'+m.market.toLowerCase();seg.style.width=(m.count/rows.length*100)+'%';seg.title=m.market+': '+m.count;track.append(seg)}
 statsPanel.append(track);
 const legend=document.createElement('div');legend.className='hub-match-market-legend';
 markets.forEach(m=>{const item=document.createElement('span');item.textContent=m.market+' · '+m.count;legend.append(item)});statsPanel.append(legend);

}
function setMatchTab(tab){
 if(tab!=='players')tab='analysis';
 document.querySelectorAll('[data-match-tab]').forEach(button=>{button.classList.toggle('active',button.dataset.matchTab===tab);button.setAttribute('aria-selected',String(button.dataset.matchTab===tab))});
 const analysis=$('#hub-match-analysis'),players=$('#hub-match-player-section');
 document.body.classList.remove('hub-match-stats-tab');
 if(analysis){analysis.hidden=tab==='players';analysis.classList.toggle('hub-match-chart-mode',tab==='analysis')}
 if(players)players.hidden=tab!=='players';
 const charts=$('#hub-match-charts');if(charts)charts.hidden=false;
 if(tab==='analysis'){
  const title=analysis?.querySelector('h3');if(title)title.textContent='Analisi partita';
  renderMatchMarketStats();
  if(activeMatch)loadMatchForm(activeMatch);
 }else{renderMatchPlayers();players?.scrollIntoView({block:'nearest',behavior:'smooth'})}
}

// Refresh the dedicated match cards when asynchronous saved daily quotes finish loading.
const finderCount=$('#finder-count');
if(finderCount)new MutationObserver(()=>{if(activeMatch&&document.body.classList.contains('hub-match-open')){renderMatchPlayers();renderMatchMarketStats()}}).observe(finderCount,{childList:true,characterData:true,subtree:true});
function renderMatchPlayers(){
 if(!document.body.classList.contains('hub-match-open'))return;
 const list=$('#hub-match-player-list'),count=$('#hub-match-player-count');if(!list)return;
 const rows=typeof window.BasketLabMatchRows==='function'?window.BasketLabMatchRows(activeMatch):[];
 const q=($('#hub-match-search')?.value||'').toLowerCase().trim();
 const groups=new Map();
 const teamFilter=$('#hub-match-team-filter')?.value||'';
 const sortBy=$('#hub-match-sort')?.value||'team';
 const oddMin=Number(($('#hub-match-odd-min')?.value||'1.20').replace(',','.'));
 const oddMax=Number(($('#hub-match-odd-max')?.value||'2.20').replace(',','.'));
 const rangeValid=Number.isFinite(oddMin)&&Number.isFinite(oddMax)&&oddMin>=1.01&&oddMax>=oddMin;
 for(const row of rows){
  if(teamFilter&&row.Squadra!==teamFilter)continue;
  if(q&&!cleanName(row.Giocatore).toLowerCase().includes(q)&&!String(row.Giocatore).toLowerCase().includes(q))continue;
  if(matchMarket!=='ALL'&&row.Mercato!==matchMarket)continue;
  const key=JSON.stringify([row.Squadra,row['ESPN ID']||row.Giocatore]);
  if(!groups.has(key))groups.set(key,{name:cleanName(row.Giocatore),team:row.Squadra,espnId:row['ESPN ID'],rows:[]});
  groups.get(key).rows.push(row);
 }
 list.replaceChildren();if(count)count.textContent=groups.size+' giocatori · '+[...groups.values()].reduce((sum,g)=>sum+g.rows.length,0)+' linee';
 if(!groups.size){const d=window.BasketLabMatchDiagnostics?.(activeMatch);list.textContent=rows.length?'Nessun giocatore corrisponde al mercato o alla ricerca.':d?.matching?'Sono presenti '+d.matching+' analisi per questa partita, ma nessuna quota valida salvata.':'Nessuna linea giocatore salvata per questa partita nella data '+(d?.date||'selezionata')+'. Le statistiche ESPN sono indipendenti dalle quote.';return}
 const ordered=[...groups.values()].sort((a,b)=>sortBy==='name'?a.name.localeCompare(b.name,'it'):sortBy==='lines'?b.rows.length-a.rows.length||a.name.localeCompare(b.name,'it'):a.team.localeCompare(b.team,'it')||a.name.localeCompare(b.name,'it'));
 let lastTeam='';
 for(const group of ordered){
  if(sortBy==='team'&&group.team!==lastTeam){const heading=document.createElement('h4');heading.className='hub-match-team-heading';heading.textContent=group.team;list.append(heading);lastTeam=group.team}
  const card=document.createElement('article');card.className='hub-match-player-card';
  const header=document.createElement('div');header.className='hub-match-player-identity';
  const info=document.createElement('div');if(/^\d+$/.test(String(group.espnId||''))){const photo=document.createElement('img');photo.className='hub-match-player-photo';photo.src='https://a.espncdn.com/i/headshots/nba/players/full/'+group.espnId+'.png';photo.alt='';photo.loading='lazy';photo.onerror=()=>{photo.hidden=true};header.append(photo)}const name=document.createElement('strong');name.textContent=group.name;
  const team=document.createElement('small');team.textContent=group.team||'';info.append(name,team);header.append(info);
  const stats=document.createElement('button');stats.type='button';stats.textContent='Statistiche ›';stats.onclick=()=>window.BasketLabMatchPlayerStats?.(group.rows[0]);header.append(stats);card.append(header);
  const markets=document.createElement('div');markets.className='hub-match-player-markets compact';
  for(const market of ['PTS','REB','AST']){
   const subset=group.rows.filter(row=>row.Mercato===market);
   if(!subset.length)continue;
   const block=document.createElement('div');block.className='hub-match-player-market compact';
   const details=document.createElement('details');details.className='hub-match-odds-dropdown';
   const summary=document.createElement('summary');const label=document.createElement('span');label.textContent=({PTS:'Punti',REB:'Rimbalzi',AST:'Assist'})[market]+' · '+subset.length+' linee';const chevron=document.createElement('span');chevron.textContent='Apri quote ▾';details.addEventListener('toggle',()=>{chevron.textContent=details.open?'Chiudi quote ▴':'Apri quote ▾'});summary.append(label,chevron);details.append(summary);
   const head=document.createElement('div');head.className='hub-match-odds-head';['Linea','Scelta','Quota','Stima'].forEach(text=>{const el=document.createElement('span');el.textContent=text;head.append(el)});details.append(head);
   const sorted=subset.sort((a,b)=>Number(a.Linea)-Number(b.Linea)||String(a.Scelta).localeCompare(String(b.Scelta)));
   const visible=sorted.filter(row=>rangeValid&&Number(row.Quota)>=oddMin&&Number(row.Quota)<=oddMax);
   for(const row of sorted){
    const entry=document.createElement('div');entry.className='hub-match-odds-row';if(rangeValid&& !visible.includes(row))entry.classList.add('hub-match-odds-extra');
    const values=[displayNum(row.Linea),String(row.Scelta||'—').toUpperCase(),displayNum(row.Quota),row['Prob. stimata %']==null||row['Prob. stimata %']===''?'—':displayNum(row['Prob. stimata %'])+'%'];
    values.forEach((value,i)=>{const cell=document.createElement('span');cell.textContent=value;if(i===2)cell.className='hub-match-odds-price';if(i===3)cell.className='hub-match-odds-prob';entry.append(cell)});details.append(entry);
   }
   if(rangeValid&&visible.length<sorted.length){const toggle=document.createElement('button');toggle.type='button';toggle.className='hub-match-all-lines';toggle.textContent='Mostra tutte le '+sorted.length+' linee';toggle.onclick=()=>{const expanded=details.classList.toggle('show-all-lines');toggle.textContent=expanded?'Mostra solo quote nel filtro':'Mostra tutte le '+sorted.length+' linee'};details.append(toggle)}
   block.append(details);markets.append(block);
  }
  card.append(markets);list.append(card);
 }
}
document.querySelectorAll('[data-match-tab]').forEach(button=>button.addEventListener('click',()=>setMatchTab(button.dataset.matchTab)));
$('#hub-match-search')?.addEventListener('input',renderMatchPlayers);
 for(const id of ['hub-match-team-filter','hub-match-sort','hub-match-odd-min','hub-match-odd-max'])$('#'+id)?.addEventListener('change',renderMatchPlayers);
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