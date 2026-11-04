/* A+C UI navigation, delegating to original Basket Lab controls. */
(()=>{'use strict';
const $=s=>document.querySelector(s);
const landing=$('.hub-landing'),tiles=$('.hub-tiles'),metrics=$('.hub-live-metrics'),trust=$('.hub-trust-strip'),featured=$('.hub-featured'),insights=$('.hub-insights'),gamesShowcase=$('.hub-games-section'),singleShowcase=$('.hub-single-section'),performance=$('.hub-performance'),methodLink=$('.hub-method-link');
if(!landing||!tiles)return;
// Share the actual presentation nodes so Home and Pronostici cannot drift.
const singleHomeAnchor=document.createComment('home-single');
const featuredHomeAnchor=document.createComment('home-featured');
singleShowcase?.before(singleHomeAnchor);featured?.before(featuredHomeAnchor);
const picksPresentation=document.createElement('section');
picksPresentation.id='picks-showcase';picksPresentation.hidden=true;
picksPresentation.setAttribute('aria-label','Pronostici del giorno');
$('#app')?.before(picksPresentation);
const singleAnalysisPage=document.createElement('section');singleAnalysisPage.id='single-analysis-page';singleAnalysisPage.hidden=true;singleAnalysisPage.setAttribute('aria-label','Analisi della Singola');$('#app')?.before(singleAnalysisPage);
let singleAnalysisReturn='picks';
function loadSingleAnalysis(){
 singleAnalysisPage.innerHTML='<p class="status">Caricamento dell’analisi…</p>';
 return (window.BasketLabAssets?window.BasketLabAssets.load('single-analysis'):Promise.reject(new Error('Module unavailable'))).then(()=>window.BasketLabSingleAnalysis.open(singleAnalysisPage,()=>{go[singleAnalysisReturn]();select(singleAnalysisReturn);},singleAnalysisReturn==='home'?'← Torna alla Home':'← Torna ai pronostici')).catch(()=>{singleAnalysisPage.innerHTML='<p class="status">Analisi temporaneamente non disponibile.</p>';const retry=document.createElement('button');retry.type='button';retry.textContent='Riprova';retry.onclick=loadSingleAnalysis;singleAnalysisPage.append(retry);});
}
function openSingleAnalysis(){singleAnalysisReturn=document.body.dataset.hubView==='home'?'home':'picks';go.single();select('single');}

const nbaUpdatesMatch=document.createElement('section');
nbaUpdatesMatch.className='hub-nba-updates';
nbaUpdatesMatch.hidden=true;
$('#hub-match-analysis')?.append(nbaUpdatesMatch);
let nbaUpdatesRequest;
let nbaUpdatesExpires=0;
function nbaUpdates(){
 if(!nbaUpdatesRequest||Date.now()>=nbaUpdatesExpires){
  nbaUpdatesExpires=Date.now()+300000;
  nbaUpdatesRequest=Promise.resolve().then(()=>fetch('/api/nba/updates')).then(response=>{
   if(!response.ok)throw new Error('ESPN unavailable');
   return response.json();
  }).catch(()=>null);
 }
 return nbaUpdatesRequest;
}
function paintNbaUpdates(panel,payload,teams){
 if(!panel)return;
 const labels={out:'Assente',doubtful:'In forte dubbio',questionable:'In dubbio','day-to-day':'Da valutare',suspension:'Sospeso'};
 const normalize=name=>String(name).toLowerCase().replace(/^la /,'los angeles ');
 const updates=(payload?.updates||[]).filter(item=>labels[item.status]&&(!teams||teams.includes(normalize(item.team))));
 panel.replaceChildren();
 panel.hidden=!updates.length;
 if(panel.hidden)return;
 const heading=document.createElement('h3');
 heading.textContent=teams?'Disponibilità giocatori':'Ultimi aggiornamenti NBA';
 const source=document.createElement('small');
 source.textContent='Fonte ESPN · '+new Date(payload.report_at).toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
 const groups=new Map();
 for(const item of updates.slice(0,teams?updates.length:5)){
  if(!groups.has(item.team))groups.set(item.team,[]);
  groups.get(item.team).push(item);
 }
 const grid=document.createElement('div');
 grid.className='availability-teams';
 for(const [team,players] of groups){
  const group=document.createElement('section');
  const title=document.createElement('h4');
  title.textContent=team;
  const list=document.createElement('ul');
  for(const item of players){
   const row=document.createElement('li');
   const name=document.createElement('span');
   name.textContent=item.player;
   const status=document.createElement('span');
   status.className='availability-status';
   status.dataset.status=item.status;
   status.textContent=labels[item.status];
   row.append(name,status);
   list.append(row);
  }
  group.append(title,list);
  grid.append(group);
 }
 panel.append(heading,grid,source);
}
const nbaUpdatesPanel=$('#hub-nba-updates-panel');
const newsPage=$('#nba-news-page'),newsList=$('#nba-news-list'),newsPreview=$('#nba-news-preview');
let newsRequest,newsExpires=0;
function loadNews(target,limit){
 if(!target)return;
 target.textContent='Caricamento notizie…';
 if(!newsRequest||Date.now()>=newsExpires){
  newsExpires=Date.now()+300000;
  newsRequest=fetch('/api/nba/news').then(response=>{
   if(!response.ok)throw new Error('News unavailable');
   return response.json();
  }).catch(()=>{newsRequest=null;return null});
 }
 newsRequest.then(payload=>{
  const articles=payload?.articles?.slice(0,limit)||[];
  target.replaceChildren();
  if(!articles.length){
   target.textContent=payload?'Nessuna notizia disponibile.':'Notizie Pianeta Basket temporaneamente non disponibili.';
   return;
  }
  for(const item of articles){
   const article=document.createElement('article');article.className='nba-news-card';
   const link=document.createElement('a');link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';
   const copy=document.createElement('div');
   const title=document.createElement('h3');title.textContent=item.title;
   const meta=document.createElement('small');meta.textContent=payload.source;
   const stamp=new Date(item.published||'');
   if(!Number.isNaN(stamp.getTime()))meta.textContent+=' · '+stamp.toLocaleString('it-IT',{timeZone:'Europe/Rome',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});
   copy.append(meta,title);link.append(copy);
   if(item.image){const img=document.createElement('img');img.src=item.image;img.alt='';img.loading='lazy';link.append(img)}
   article.append(link);target.append(article);
  }
 });
}
function observeNewsPreview(){
 if(!nbaUpdatesPanel||!window.IntersectionObserver)return;
 const observer=new IntersectionObserver(entries=>{
  if(entries.some(entry=>entry.isIntersecting)&&document.body.dataset.hubView==='home'){
   observer.disconnect();loadNews(newsPreview,4);
  }
 });
 observer.observe(nbaUpdatesPanel);
 for(const event of ['wheel','touchstart','keydown'])window.removeEventListener(event,observeNewsPreview);
}
for(const event of ['wheel','touchstart','keydown'])window.addEventListener(event,observeNewsPreview,{passive:true});
const menuToggle=$('.hub-menu-toggle'),menuDrawer=$('#hub-menu-drawer');
function closeMenu(){if(!menuDrawer)return;menuDrawer.hidden=true;menuToggle?.setAttribute('aria-expanded','false');menuToggle?.setAttribute('aria-label','Apri menu di navigazione')}
menuToggle?.addEventListener('click',()=>{const opening=menuDrawer.hidden;menuDrawer.hidden=!opening;menuToggle.setAttribute('aria-expanded',String(opening));menuToggle.setAttribute('aria-label',opening?'Chiudi menu di navigazione':'Apri menu di navigazione')});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu()});
document.addEventListener('click',event=>{if(menuDrawer&&!menuDrawer.hidden&&!event.target.closest('.hub-menu-drawer,.hub-menu-toggle'))closeMenu()});
const tab=name=>$('[data-tab="'+name+'"]');
const go={
 single(){loadSingleAnalysis();window.scrollTo(0,0);},
 news(){loadNews(newsList,24);window.scrollTo(0,0);},
 home(){ $('#area-quotes')?.click();tab('dashboard')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 picks(){ $('#area-quotes')?.click();tab('dashboard')?.click();tab('dashboard')?.scrollIntoView({block:'start',behavior:'smooth'});},
 stats(){ playerReturn=null;$('#area-stats')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 finder(){ document.body.classList.remove('hub-match-open');const detail=$('#hub-match-detail');if(detail)detail.hidden=true;$('#area-quotes')?.click();tab('finder')?.click();$('#quote-tabs')?.scrollIntoView({block:'start',behavior:'smooth'});},
 history(){ $('[data-extra="history"]')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 about(){ $('[data-extra="about"]')?.click();window.scrollTo({top:0,behavior:'smooth'});},
 calendar(){renderCalendar();window.scrollTo({top:0,behavior:'smooth'});}
};
let home=true;let calendar=false;let playerReturn=null;
let routerReady=false,applyingRoute=false,routeQueued=false;
function syncRoute(){
 if(!routerReady||applyingRoute||routeQueued||!window.BasketLabRouter)return;
 routeQueued=true;queueMicrotask(()=>{routeQueued=false;if(applyingRoute)return;window.BasketLabRouter.write({view:document.body.dataset.hubView||'home',date:calendarSelectedDate,match:document.body.classList.contains('hub-match-open')?activeMatch:''});});
}
const HUB_STATE_KEY='basketlab-hub-view-v1';
function saveHubState(){
 try{sessionStorage.setItem(HUB_STATE_KEY,JSON.stringify({view:document.body.dataset.hubView||'home',date:calendarSelectedDate||'',match:document.body.classList.contains('hub-match-open')?activeMatch||'':'',boxscore:activeCalendarBoxscore?.event_id||'',scrollY:window.scrollY}))}catch(_){}
}
window.addEventListener('pagehide',saveHubState);

function mark(key){document.querySelectorAll('[data-hub]').forEach(el=>{if(el.dataset.hub===key)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')})}
function display(){
 const view=document.body.dataset.hubView||'home';
 // The active route owns visibility, including transitions that bypass area tabs.
 for(const name of ['history','about']){const panel=$('#extra-'+name);if(panel)panel.hidden=view!==name;}
 const calendarPanel=$('#hub-calendar');if(calendarPanel)calendarPanel.hidden=!calendar;
 const extra=view==='history'||view==='about';
 singleAnalysisPage.hidden=view!=='single';
 const picksView=document.body.dataset.hubView==='picks'&&!extra;
 picksPresentation.hidden=!picksView;
 if(picksView&&!picksPresentation.querySelector('.hub-picks-archive')){
  const link=document.createElement('button');
  link.type='button';link.className='bl-back hub-picks-archive';link.dataset.hub='history';link.textContent='Archivio esiti →';
  picksPresentation.prepend(link);
 }

 if(picksView){
  for(const panel of [singleShowcase,featured])if(panel&&panel.parentElement!==picksPresentation)picksPresentation.append(panel);
 }else{
  if(singleShowcase&&singleShowcase.previousSibling!==singleHomeAnchor)singleHomeAnchor.after(singleShowcase);
  if(featured&&featured.previousSibling!==featuredHomeAnchor)featuredHomeAnchor.after(featured);
 }
 const newsView=document.body.dataset.hubView==='news';
 if(newsPage)newsPage.hidden=!newsView;
 const shell=$('#app');if(shell)shell.hidden=extra||calendar||picksView||newsView||view==='single';
 landing.hidden=!home||extra;tiles.hidden=!home||extra;
 if(metrics)metrics.hidden=!home||extra;if(trust)trust.hidden=!home||extra;
 if(featured)featured.hidden=!(home||picksView)||extra;
 if(singleShowcase)singleShowcase.hidden=!(home||picksView)||extra;
 if(insights)insights.hidden=!home||extra;if(gamesShowcase)gamesShowcase.hidden=!home||extra;
 if(nbaUpdatesPanel)nbaUpdatesPanel.hidden=!home||extra;
 if(performance)performance.hidden=!home||extra;if(methodLink)methodLink.hidden=!home||extra;
 const singleAction=singleShowcase?.querySelector('.bl-broadcast-action');
 if(singleAction)singleAction.textContent='Apri analisi →';
}
function select(key){if(key==='stats'&&!playerReturn){const back=$('#back-to-picks');if(back){back.hidden=false;back.textContent='← Torna alla Home';}}calendar=key==='calendar';home=key==='home';if(key!=='finder')document.body.classList.remove('hub-match-open');mark(key==='single'?'picks':key);document.body.dataset.hubView=key;display();saveHubState();syncRoute();document.dispatchEvent(new CustomEvent('basketlab:view',{detail:{view:key}}));}

document.addEventListener('basketlab:player-open',()=>{
 playerReturn={view:document.body.dataset.hubView||'picks',match:document.body.classList.contains('hub-match-open')?activeMatch:'',date:$('#date')?.value||calendarSelectedDate};
 queueMicrotask(()=>{select('stats');const back=$('#back-to-picks');if(back){back.hidden=false;back.textContent=playerReturn?.match?'← Torna all’analisi':playerReturn?.view==='home'?'← Torna alla Home':playerReturn?.view==='finder'?'← Torna ad Analisi quote':'← Torna ai pronostici';}});
});
$('#back-to-picks')?.addEventListener('click',event=>{
 if(!playerReturn){if(document.body.dataset.hubView==='stats'){event.preventDefault();event.stopImmediatePropagation();go.home();select('home');}return;}
 event.preventDefault();event.stopImmediatePropagation();
 const target=playerReturn;playerReturn=null;
 if(target.match){calendarSelectedDate=target.date;openFixtureDetails(target.match);}
 else{const key=target.view==='stats'?'home':target.view;go[key]?.();select(key);if(key==='finder')window.restoreQuotePosition?.('finder');}
},true);
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
async function loadModelPerformance(){
 const body=performance?.querySelector('.hub-performance-body');
 if(!body)return;
 try{
  const response=await fetch('/api/history/performance',{headers:{Accept:'application/json'}});
  if(!response.ok)throw new Error('Performance unavailable');
  const stats=await response.json();
  const groups=[['Singola',stats.single],['Top 10',stats]];
  const number=value=>Number.isFinite(value)?value.toLocaleString('it-IT'):'—';
  body.innerHTML='<div class="bl-results-grid">'+groups.map(([label,group])=>{
   const rate=Number.isFinite(group?.success_pct)?group.success_pct:null;
   const sweep=Math.min(100,Math.max(0,rate??0));
   return '<article class="bl-results-card"><h3>'+label+'</h3>'+
    '<div class="bl-results-ring" style="--success:'+sweep+'%"><strong>'+
    (rate===null?'—':number(rate)+'%')+'</strong></div>'+
    '<p><strong>'+number(group?.published)+'</strong> analisi pubblicate</p>'+
    '<dl><div><dt>Centrate</dt><dd>'+number(group?.won)+'</dd></div>'+
    '<div><dt>Non centrate</dt><dd>'+number(group?.lost)+'</dd></div>'+
    '<div><dt>Da verificare</dt><dd>'+number(group?.pending)+'</dd></div></dl></article>';
  }).join('')+'</div><p class="bl-results-note">Dal 1° novembre 2026 · Percentuale sulle analisi verificate.</p>';
 }catch(_){body.innerHTML='<div><strong>Risultati temporaneamente non disponibili</strong><p>Consulta l’archivio per le singole giornate. Nessun dato viene stimato o inventato.</p></div>'}
}
if(!window.BasketLabSections)loadModelPerformance();
if(metricTarget){new MutationObserver(refresh).observe(metricTarget,{childList:true,subtree:true,characterData:true})}
if(updated){new MutationObserver(refresh).observe(updated,{childList:true,subtree:true,characterData:true})}
if($('#picks'))new MutationObserver(refresh).observe($('#picks'),{childList:true,subtree:true});
document.querySelectorAll('[data-pick-group]').forEach(b=>b.addEventListener('click',()=>{go.picks();select('picks');$('#pick-'+b.dataset.pickGroup)?.scrollIntoView({block:'start',behavior:'smooth'});closeMenu()}));
function hubCardName(raw){const s=String(raw||'').trim();return s.replace(/^([^,]+),\s*(.+)$/,'$2 $1')}
function hubCardMetric(source,term){const blocks=[...source.querySelectorAll('.pick-values > div')];const match=blocks.find(el=>term.test(el.querySelector('small')?.textContent||''));return match?.querySelector('strong')?.textContent?.trim()||''}
function hubCardPhoto(source){const image=source.querySelector('.pick-avatar img');const frame=document.createElement('div');frame.className='bl-player-photo';if(image){const img=image.cloneNode(true);img.removeAttribute('id');img.loading='lazy';frame.append(img)}else{const fallback=document.createElement('span');fallback.textContent=source.querySelector('.pick-avatar span')?.textContent?.trim()||'NBA';frame.append(fallback)}return frame}
function featuredPicks(){
 const list=$('#hub-featured-list'),picks=$('#picks');if(!list||!picks)return;
 const heading=featured?.querySelector('h2');
 if(heading)heading.textContent='🔥 Le scelte del Lab';
 const badge=$('#hub-choices-state'),publication=picks.querySelector('#pick-giorno')?.dataset.publicationState;
 if(badge){badge.dataset.state=publication||'waiting';badge.textContent=publication==='official'?'Ufficiali':publication==='preview'?'Conferma alle 18:00':'In attesa';}
 const sources=[...picks.querySelectorAll('#pick-giorno .pick-group-items > .pick-selection, .pick-group-daily[aria-label="Analisi preliminari"] .pick-group-items > .pick-selection')].slice(0,10);
 const selected=sources.length||picks.querySelector('#pick-giorno')?sources:[...picks.querySelectorAll('.pick-selection')].slice(0,10);
 list.replaceChildren();
 for(const [index,source] of selected.entries()){
  const card=document.createElement('button');card.type='button';card.className='bl-datalab-card';
  const rank=document.createElement('span');rank.className='bl-rank';rank.textContent=String(index+1).padStart(2,'0');
  const photo=hubCardPhoto(source);
  const body=document.createElement('div');body.className='bl-data-body';
  const name=document.createElement('strong');name.className='bl-data-name';name.textContent=hubCardName(source.querySelector('.pick-player-link')?.textContent||'Analisi NBA');
  const market=document.createElement('span');market.className='bl-data-market';market.textContent=source.querySelector('.pick-market')?.textContent?.trim()||'';
  const stats=document.createElement('div');stats.className='bl-data-stats';
  const prob=hubCardMetric(source,/stima|probabilit/i),odd=hubCardMetric(source,/quota/i);
  const probBox=document.createElement('div');probBox.className='bl-data-prob';
  const probLabel=document.createElement('small');probLabel.textContent='STIMA MODELLO';
  const probValue=document.createElement('strong');probValue.textContent=prob||'—';
  const track=document.createElement('div');track.className='bl-prob-track';
  const fill=document.createElement('span');const n=Number(prob.replace('%','').replace(',','.'));fill.style.width=Number.isFinite(n)?Math.max(0,Math.min(100,n))+'%':'0%';track.append(fill);probBox.append(probLabel,probValue,track);
  const oddBox=document.createElement('div');oddBox.className='bl-data-odd';const oddLabel=document.createElement('small');oddLabel.textContent='QUOTA';const oddValue=document.createElement('strong');oddValue.textContent=odd||'—';oddBox.append(oddLabel,oddValue);
  stats.append(probBox,oddBox);body.append(name,market,stats);
  const arrow=document.createElement('span');arrow.className='bl-data-arrow';arrow.textContent='›';arrow.setAttribute('aria-hidden','true');
  card.append(rank,photo,body,arrow);
  card.addEventListener('click',()=>{go.picks();select('picks');source.querySelector('.pick-stats-button')?.click();select('stats')});
  list.append(card);
 }
 if(!selected.length)list.textContent='Nessuna analisi disponibile per questa giornata.';
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
const matchTeamCodes={'Orlando Magic':'orl','Boston Celtics':'bos','Brooklyn Nets':'bkn','Indiana Pacers':'ind','Atlanta Hawks':'atl','Charlotte Hornets':'cha','Chicago Bulls':'chi','Cleveland Cavaliers':'cle','Dallas Mavericks':'dal','Denver Nuggets':'den','Detroit Pistons':'det','Golden State Warriors':'gs','Houston Rockets':'hou','Los Angeles Clippers':'lac','LA Clippers':'lac','L.A. Clippers':'lac','Los Angeles Lakers':'lal','Memphis Grizzlies':'mem','Miami Heat':'mia','Milwaukee Bucks':'mil','Minnesota Timberwolves':'min','New Orleans Pelicans':'no','New York Knicks':'ny','Oklahoma City Thunder':'okc','Philadelphia 76ers':'phi','Phoenix Suns':'phx','Portland Trail Blazers':'por','Sacramento Kings':'sac','San Antonio Spurs':'sa','Toronto Raptors':'tor','Utah Jazz':'utah','Washington Wizards':'wsh'};
const nbaTeamPalette={
 'atl':['#e03a3e','#c1d32f'],'bos':['#007a33','#ba9653'],'bkn':['#343b45','#111111'],'cha':['#00788c','#a1a1a4'],'chi':['#ce1141','#111111'],'cle':['#860038','#fdbb30'],'dal':['#00538c','#b8c4ca'],'den':['#0e2240','#fec524'],'det':['#c8102e','#1d42ba'],'gs':['#1d428a','#ffc72c'],'hou':['#ce1141','#25282a'],'ind':['#002d62','#fdbb30'],'lac':['#c8102e','#1d428a'],'lal':['#552583','#fdb927'],'mem':['#5d76a9','#5d76a9'],'mia':['#98002e','#f9a01b'],'mil':['#00471b','#eee1c6'],'min':['#0c2340','#78be20'],'no':['#0c2340','#c8102e'],'ny':['#006bb6','#f58426'],'okc':['#007ac1','#ef3b24'],'orl':['#0077c0','#c4ced4'],'phi':['#006bb6','#ed174c'],'phx':['#1d1160','#e56020'],'por':['#e03a3e','#171717'],'sac':['#5a2d81','#63727a'],'sa':['#626e7b','#c4ced4'],'tor':['#ce1141','#111111'],'utah':['#2b5134','#f9a01b'],'wsh':['#002b5c','#e31837']};
function fixtureTeamGradient(row,away,home){
 const a=nbaTeamPalette[matchTeamCodes[away]]||['#173e72','#3565a1'];
 const b=nbaTeamPalette[matchTeamCodes[home]]||['#4a315a','#704f8c'];
 row.style.setProperty('--team-away',a[0]);row.style.setProperty('--team-away-accent',a[1]);
 row.style.setProperty('--team-home',b[0]);row.style.setProperty('--team-home-accent',b[1]);
}
let activeMatch='',matchMarket='PTS',matchFormRequest=0,matchTeamFilter='';
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
 matchTeamFilter='';
 const quick=$('#hub-match-team-quick');if(quick){quick.replaceChildren();const choices=[{label:'Tutti',value:''},...match.split(/\s+-\s+|\s+vs\.?\s+/i).map(team=>({label:team.trim().split(' ').slice(-1)[0],value:team.trim()}))];choices.forEach(choice=>{const button=document.createElement('button');button.type='button';button.textContent=choice.label;button.dataset.team=choice.value;button.setAttribute('aria-pressed',String(!choice.value));button.classList.toggle('active',!choice.value);button.addEventListener('click',()=>{matchTeamFilter=choice.value;syncMatchQuickTeams();renderMatchPlayers()});quick.append(button)})}
 const filterPanel=$('#hub-match-filter-panel');if(filterPanel)filterPanel.hidden=true;const filterToggle=$('#hub-match-filter-toggle');if(filterToggle)filterToggle.setAttribute('aria-expanded','false');
 const meta=$('#hub-match-fixture-meta');if(meta){const selected=$('#date')?.value;meta.textContent=selected?selected.split('-').reverse().join('/'):'Partita NBA'}
 const oddMin=$('#hub-match-odd-min'),oddMax=$('#hub-match-odd-max');if(oddMin)oddMin.value='1.20';if(oddMax)oddMax.value='2.20';
 syncMatchQuickTeams();syncMatchOddsRange();
 matchMarket='PTS';document.querySelectorAll('#hub-match-market-buttons button').forEach(b=>b.classList.toggle('active',b.dataset.market==='PTS'));$('#hub-match-search').value='';setMatchTab('analysis');renderMatchPlayers();
 saveHubState();syncRoute();
 panel?.scrollIntoView({block:'start',behavior:'smooth'});
}
const {renderMatchCharts,renderMatchH2H}=window.BasketLabMatchCharts(document,matchTeamCodes,displayNum);
const getMatchFormData=window.BasketLabMatchData((...args)=>fetch(...args));
async function loadMatchForm(match){
 const request=++matchFormRequest;
 nbaUpdatesMatch.hidden=true;
 const updateTeams=match.split(/\s+-\s+|\s+vs\.?\s+/i).map(team=>team.trim().toLowerCase().replace(/^la /,'los angeles '));
 nbaUpdates().then(payload=>{
  if(request===matchFormRequest&&activeMatch===match)paintNbaUpdates(nbaUpdatesMatch,payload,updateTeams);
 });

 const teams=match.split(/\s+-\s+|\s+vs\.?\s+/i).map(x=>x.trim());
 const panel=$('#hub-match-analysis');if(!panel||teams.length!==2)return;
 const boxes=panel.querySelectorAll('.hub-match-data-block');
 const facts=panel.querySelectorAll('.hub-match-facts>div');
 const summary=panel.querySelector('.hub-match-summary p');
 const chart=$('#hub-match-charts');if(chart)chart.textContent='Caricamento delle statistiche verificate…';
 $('#hub-match-h2h-chart')?.replaceChildren();
 for(const block of boxes){block.querySelector('strong').textContent='Caricamento…';block.querySelector('p').textContent='Consultazione risultati ESPN verificati'}
 for(const fact of facts)fact.querySelector('small').textContent='Caricamento…';
 try{
  const date=$('#date')?.value;
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date||''))throw new Error('Data non disponibile');
  const data=await getMatchFormData(date,teams);
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
  panel.dataset.historyComplete=String(data.history_complete!==false);
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
  if(summary){
   const lines=[];
   const gamesA=Number(a.games)||0,gamesB=Number(b.games)||0;
   const winsA=Number(a.wins)||0,winsB=Number(b.wins)||0;
   if(gamesA&&gamesB){
    if(winsA===winsB)lines.push('Forma recente equilibrata: '+winsA+' vittorie a testa nelle gare disponibili.');
    else{const leader=winsA>winsB?0:1;lines.push(teams[leader]+' ha un bilancio recente migliore ('+winsA+'-'+(gamesA-winsA)+' contro '+winsB+'-'+(gamesB-winsB)+' in ordine '+teams[0]+' / '+teams[1]+').')}
   }else lines.push('Forma recente: campione insufficiente per confrontare le squadre.');
   if(a.avg_points!=null&&b.avg_points!=null){
    const diff=Math.abs(Number(a.avg_points)-Number(b.avg_points));
    if(diff<0.05)lines.push('Le medie punti segnati sono sostanzialmente uguali.');
    else lines.push(teams[Number(a.avg_points)>Number(b.avg_points)?0:1]+' segna in media '+diff.toLocaleString('it-IT',{maximumFractionDigits:1})+' punti in più nelle gare osservate.');
   }
   if(h2h.length){
    const h2hWins=teams.map(team=>h2h.filter(game=>{const index=game.teams.indexOf(team);return index>=0&&Number(game.scores[index])>Number(game.scores[1-index])}).length);
    if(h2hWins[0]!==h2hWins[1])lines.push('Scontri diretti nel periodo: '+teams[h2hWins[0]>h2hWins[1]?0:1]+' avanti '+Math.max(...h2hWins)+'-'+Math.min(...h2hWins)+'.');
    else lines.push('Scontri diretti nel periodo: parità '+h2hWins[0]+'-'+h2hWins[1]+'.');
   }
   if(data.history_complete===false)lines.push('Storico ESPN parzialmente disponibile: riprova per completare il campione.');
   summary.textContent=lines.join(' ')+' Dati descrittivi, non una previsione del risultato.';
  }
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
  renderMatchMarketStats();
  if(activeMatch)loadMatchForm(activeMatch);
 }else{renderMatchPlayers();players?.scrollIntoView({block:'nearest',behavior:'smooth'})}
}

// Refresh the dedicated match cards when asynchronous saved daily quotes finish loading.
const finderCount=$('#finder-count');
if(finderCount)new MutationObserver(()=>{if(activeMatch&&document.body.classList.contains('hub-match-open')){renderMatchPlayers();renderMatchMarketStats()}}).observe(finderCount,{childList:true,characterData:true,subtree:true});
function syncMatchQuickTeams(){
 const selected=matchTeamFilter;
 document.querySelectorAll('#hub-match-team-quick button').forEach(button=>{const active=button.dataset.team===selected;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active))});
}
function syncMatchOddsRange(){
 const min=$('#hub-match-odd-min')?.value||'1.20',max=$('#hub-match-odd-max')?.value||'2.20';
 const label=$('#hub-match-range-label');if(label)label.textContent='Quote '+min.replace('.',',')+'–'+max.replace('.',',');
}
let matchPlayerView=null,matchPlayerModule=null;
function renderMatchPlayers(){
 if(!document.body.classList.contains('hub-match-open')||$('#hub-match-player-section')?.hidden)return;
 if(!matchPlayerView){
  if(window.BasketLabMatchPlayers)matchPlayerView=window.BasketLabMatchPlayers(document,()=>({activeMatch,matchMarket,matchTeamFilter}),cleanName,displayNum);
  else{
   if(!matchPlayerModule){
    const list=$('#hub-match-player-list');if(list)list.textContent='Caricamento giocatori e quote…';
    matchPlayerModule=window.BasketLabAssets.load('match-players').then(()=>{matchPlayerModule=null;renderMatchPlayers();}).catch(()=>{matchPlayerModule=null;if(list)list.textContent='Interfaccia temporaneamente non disponibile. Riapri Giocatori e quote per riprovare.';});
   }
   return;
  }
 }
 matchPlayerView();
}
document.querySelectorAll('[data-match-tab]').forEach(button=>button.addEventListener('click',()=>setMatchTab(button.dataset.matchTab)));
$('#hub-match-search')?.addEventListener('input',renderMatchPlayers);
 for(const id of ['hub-match-odd-min','hub-match-odd-max'])$('#'+id)?.addEventListener('change',()=>{syncMatchQuickTeams();syncMatchOddsRange();renderMatchPlayers()});
 $('#hub-match-filter-toggle')?.addEventListener('click',()=>{const panel=$('#hub-match-filter-panel'),button=$('#hub-match-filter-toggle');if(!panel||!button)return;panel.hidden=!panel.hidden;button.setAttribute('aria-expanded',String(!panel.hidden));const arrow=$('#hub-match-filter-chevron');if(arrow)arrow.textContent=panel.hidden?'▾':'▴'});

document.querySelectorAll('#hub-match-market-buttons button').forEach(button=>button.addEventListener('click',()=>{matchMarket=button.dataset.market;document.querySelectorAll('#hub-match-market-buttons button').forEach(b=>b.classList.toggle('active',b===button));renderMatchPlayers()}));
$('#hub-match-back')?.addEventListener('click',()=>{document.body.classList.remove('hub-match-open');$('#hub-match-detail').hidden=true;if(calendarSelectedDate){go.calendar();select('calendar')}else{go.home();select('home')}});
let calendarRefreshTimer=null;
function scheduleCalendarRefresh(){
 if(!calendar)return;
 clearTimeout(calendarRefreshTimer);
 calendarRefreshTimer=setTimeout(()=>{if(calendar)renderCalendar()},100);
}
const MINUTE=60*1000;
const fetchNbaFixtures=window.BasketLabCalendarData((...args)=>fetch(...args));
function italyDay(value){
 return new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(value);
}
function sessionDay(){
 const now=new Date(),hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Rome',hour:'2-digit',hourCycle:'h23'}).format(now));
 if(hour>=12)return italyDay(now);
 return italyDay(new Date(now.getTime()-12*60*60*1000));
}
function fixtureKey(match){
 const aliases={'la clippers':'los angeles clippers','l.a. clippers':'los angeles clippers'};
 return String(match||'').split(/\s+-\s+|\s+vs\.?\s+|\s+@\s+/i).map(t=>{const v=t.trim().toLowerCase();return aliases[v]||v}).sort().join('|');
}
function matchingFixtureOption(match){
 const opts=[...($('#finder-fixture')?.options||[])].map(o=>o.value).filter(Boolean);
 const key=fixtureKey(match);
 return opts.find(v=>fixtureKey(v)===key)||'';
}
let pendingCalendarFixture=0;
let pendingCalendarListener=null;
function openFixtureDetails(match){
 if(pendingCalendarListener){document.removeEventListener('basketlab:quotes-loaded',pendingCalendarListener);pendingCalendarListener=null;}
 const date=$('#date');
 const target=calendarSelectedDate;
 const current=date?.value||'';
 const request=++pendingCalendarFixture;
 const dateChanged=!!(date&&target&&target!==current);
 // Open the analysis immediately; the quote feed must never block navigation.
 if(dateChanged){if(![...date.options].some(o=>o.value===target))date.add(new Option(target,target));date.value=target;}
 const available=dateChanged?'':matchingFixtureOption(match);
 openMatchQuotes(available||match);
 if(dateChanged){
  const meta=$('#hub-match-fixture-meta');
  if(meta)meta.textContent='Caricamento quote della giornata…';
  const onLoaded=event=>{
   if(request!==pendingCalendarFixture||event.detail?.date!==target)return;
   document.removeEventListener('basketlab:quotes-loaded',onLoaded);
   pendingCalendarListener=null;
   if(!document.body.classList.contains('hub-match-open')||date?.value!==target||fixtureKey(activeMatch)!==fixtureKey(match))return;
   const resolved=matchingFixtureOption(match);
   if(resolved){
    const fixture=$('#finder-fixture');
    if(fixture&&fixture.value!==resolved){fixture.value=resolved;fixture.dispatchEvent(new Event('change',{bubbles:true}))}
    renderMatchPlayers();renderMatchMarketStats();
   }else{
    const area=$('#hub-match-fixture-meta');
    if(area)area.textContent='Nessuna quota disponibile per questa partita nella giornata selezionata.';
   }
  };
  pendingCalendarListener=onLoaded;
  document.addEventListener('basketlab:quotes-loaded',onLoaded);
  date.dispatchEvent(new Event('change',{bubbles:true}));
 }else if(!available){
  const area=$('#hub-match-fixture-meta');
  if(area)area.textContent='Nessuna quota disponibile per questa partita nella giornata selezionata.';
 }
}
function fixtureName(game){return String(game.away||'')+' - '+String(game.home||'')}
function fixtureTime(game){
 if(!game.start_at)return game.time||'';
 const start=new Date(game.start_at);
 return Number.isNaN(start.getTime())?game.time||'':new Intl.DateTimeFormat('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(start);
}
let calendarRequest=0;
let calendarSelectedDate='';
let calendarWeekStart='';
let calendarVisibleMonth='';
function calendarIsoOffset(iso,days){const d=new Date(iso+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10)}
function calendarMonday(iso){return calendarIsoOffset(iso,-((new Date(iso+'T12:00:00Z').getUTCDay()+6)%7))}
function calendarSelectDate(iso){calendarSelectedDate=iso;calendarWeekStart=calendarIsoOffset(iso,-3);calendarVisibleMonth=iso.slice(0,7);renderCalendar();saveHubState();syncRoute()}

let activeCalendarBoxscore=null;
let calendarBoxscoreRequest=0;
async function openCalendarBoxscore(game,refresh=false){
 if(!refresh){activeCalendarBoxscore=game;document.body.classList.add('hub-boxscore-open')}
 const request=++calendarBoxscoreRequest;
 const panel=$('#hub-calendar-boxscore'),games=$('#hub-calendar-games');
 if(!panel||!games)return;
 games.hidden=true;panel.hidden=false;panel.replaceChildren();
 const back=document.createElement('button');back.type='button';back.className='hub-boxscore-back';back.textContent='‹ Torna alle partite';
 back.onclick=()=>{activeCalendarBoxscore=null;calendarBoxscoreRequest++;document.body.classList.remove('hub-boxscore-open');panel.hidden=true;games.hidden=false;panel.replaceChildren();renderCalendar()};
 panel.append(back);
 const header=document.createElement('div');header.className='hub-boxscore-match-header';
 const matchup=document.createElement('div');matchup.className='hub-boxscore-matchup';
 for(const team of [game.away,game.home]){
  const side=document.createElement('div');side.className='hub-boxscore-match-team';
  const code=matchTeamCodes[team]||matchTeamCodes[team.replace(/^LA /,'Los Angeles ')];
  if(code){const logo=document.createElement('img');logo.src='https://a.espncdn.com/i/teamlogos/nba/500/'+code+'.png';logo.alt='Logo '+team;logo.loading='lazy';logo.addEventListener('error',()=>{logo.hidden=true});side.append(logo)}
  const name=document.createElement('span');name.textContent=team;side.append(name);matchup.append(side);
 }
 header.append(matchup);
 const score=document.createElement('div');score.className='hub-boxscore-headline';score.textContent=String(game.away_score??'')+' – '+String(game.home_score??'');matchup.insertBefore(score,matchup.lastElementChild);
 const date=document.createElement('div');date.className='hub-boxscore-match-date';date.textContent=fixtureTime(game);header.append(date);
 panel.append(header);
 const loading=document.createElement('p');loading.textContent='Caricamento tabellino ESPN…';panel.append(loading);
 const rendererReady=window.BasketLabBoxscoreView?Promise.resolve():window.BasketLabAssets.load('boxscore-view');
 rendererReady.catch(()=>{});
 try{
  const response=await fetch('/api/nba/boxscore?event_id='+encodeURIComponent(game.event_id));
  if(!response.ok)throw new Error('Tabellino non disponibile');
  const data=await response.json();if(request!==calendarBoxscoreRequest)return;
  await rendererReady;if(request!==calendarBoxscoreRequest)return;loading.remove();
  window.BasketLabBoxscoreView(document,panel,game,data);
 }catch(error){if(request===calendarBoxscoreRequest)loading.textContent='Impossibile caricare il tabellino ESPN in questo momento.'}
}
function renderCalendar(){
 const dates=$('#hub-calendar-dates'),games=$('#hub-calendar-games'),summary=$('#hub-calendar-day-summary');
 const boxscore=$('#hub-calendar-boxscore');if(boxscore){boxscore.hidden=true;boxscore.replaceChildren()}if(games)games.hidden=false;activeCalendarBoxscore=null;calendarBoxscoreRequest++;document.body.classList.remove('hub-boxscore-open');
 if(!dates||!games)return;
 const source=$('#date-strip'),nativeDate=$('#date'),fixture=$('#finder-fixture');
 const dayButtons=[...(source?.querySelectorAll('button')||[])];
 const selectedValue=calendarSelectedDate||nativeDate?.value||italyDay(new Date());
 const options=[...(nativeDate?.options||[])].filter(o=>o.value);
 let index=options.findIndex(o=>o.value===selectedValue);
 if(index<0||index>=dayButtons.length){
  index=dayButtons.findIndex(b=>b.getAttribute('aria-selected')==='true'||b.getAttribute('aria-pressed')==='true'||b.classList.contains('active')||b.classList.contains('selected'));
 }
 if(index<0)index=0;
 const matches=[...new Set([...(fixture?.options||[])].map(o=>o.value).filter(Boolean))];
 const requestedDate=calendarSelectedDate||options[index]?.value||selectedValue;
 const compactDate=$('#hub-calendar-compact-date');if(compactDate&&requestedDate){const d=new Date(requestedDate+'T12:00:00Z');compactDate.textContent=new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(d)}
 if(requestedDate)calendarSelectedDate=requestedDate;
 if(!calendarWeekStart&&/^\d{4}-\d{2}-\d{2}$/.test(requestedDate))calendarWeekStart=calendarIsoOffset(requestedDate,-3);
 if(!calendarVisibleMonth&&/^\d{4}-\d{2}-\d{2}$/.test(requestedDate))calendarVisibleMonth=requestedDate.slice(0,7);
 const calendarToken=++calendarRequest;
 const isEspnCalendar=!!(requestedDate&&/^\d{4}-\d{2}-\d{2}$/.test(requestedDate));
 if(isEspnCalendar){
  // Paint the fixture list as soon as ESPN responds; quote coverage is an independent enhancement.
  const coveragePromise=fetch('/api/nba/quote-coverage?date='+encodeURIComponent(requestedDate))
   .then(r=>r.ok?r.json():{fixtures:[]}).catch(()=>({fixtures:[]}));
  fetchNbaFixtures(requestedDate).then(fixtures=>{
   const coverage={fixtures:[]};


   if(calendarToken!==calendarRequest||!calendar||calendarSelectedDate!==requestedDate)return;
   const quoted=new Set((coverage.fixtures||[]).map(fixtureKey));
   games.replaceChildren();
   if(summary){const count=summary.querySelector('span');if(count)count.textContent=fixtures.length+' '+(fixtures.length===1?'partita':'partite')}
   if(!fixtures.length){games.textContent='Nessuna partita NBA in programma per questa data.';return}
   for(const [gameIndex,game] of fixtures.entries()){
    const match=fixtureName(game),hasOdds=quoted.has(fixtureKey(match));
    const row=document.createElement('button');row.type='button';row.className='hub-calendar-match hub-calendar-gradient';row.dataset.fixtureKey=fixtureKey(match);row.dataset.theme=String(gameIndex%4);fixtureTeamGradient(row,game.away,game.home);
    const names=[game.away,game.home];
    names.forEach((team,i)=>{
     if(i){const vs=document.createElement('span');vs.className='hub-calendar-versus';vs.textContent='VS';row.append(vs)}
     const side=document.createElement('span');side.className='hub-calendar-team';
     const code=matchTeamCodes[team];
     if(code){const img=document.createElement('img');img.src='https://a.espncdn.com/i/teamlogos/nba/500/'+code+'.png';img.alt='';img.loading='lazy';side.append(img)}
     const label=document.createElement('span');label.textContent=team||'NBA';side.append(label);row.append(side)
    });
    const info=document.createElement('div');info.className='hub-calendar-match-arrow';
    const time=document.createElement('span');time.className='hub-calendar-time';time.textContent=fixtureTime(game);
    const state=document.createElement('span');state.className='hub-calendar-state';const finished=game.state==='post'||(!game.upcoming&&/final|terminat|conclus|finished|completed/i.test(String(game.status||'')));state.textContent=game.upcoming?'Da giocare':finished?'Terminata':'Live';if(!game.upcoming&&!finished)state.classList.add('live');
    // Display only actual scores provided by the NBA fixture feed; never infer them.
    const scorePair=Array.isArray(game.scores)?game.scores:null;
    const awayScore=game.away_score??game.awayScore??scorePair?.[0];
    const homeScore=game.home_score??game.homeScore??scorePair?.[1];
    const hasFinalScore=!game.upcoming&&awayScore!=null&&homeScore!=null&&String(awayScore)!==''&&String(homeScore)!=='';
    if(hasFinalScore){
     const score=document.createElement('strong');score.className='hub-calendar-final-score';
     score.textContent=String(awayScore)+' – '+String(homeScore);
     info.append(score);
    }
    if(hasOdds){const odds=document.createElement('span');odds.className='hub-calendar-odds';odds.textContent='Quote disponibili';row.append(odds)}
    row.append(state);
    info.append(time);row.append(info);
    row.addEventListener('click',()=>game.upcoming?openFixtureDetails(match):game.event_id?openCalendarBoxscore(game):openFixtureDetails(match));row.setAttribute('aria-label',match+(!game.upcoming?' · Apri tabellino partita':' · Apri dettagli partita'));
    games.append(row)
   }
   coveragePromise.then(latest=>{
    if(calendarToken!==calendarRequest||!calendar||calendarSelectedDate!==requestedDate)return;
    const quoted=new Set((latest.fixtures||[]).map(fixtureKey));
    games.querySelectorAll('.hub-calendar-match[data-fixture-key]').forEach(row=>{
     const hasOdds=quoted.has(row.dataset.fixtureKey);
     let badge=row.querySelector('.hub-calendar-odds');
     if(hasOdds&&!badge){badge=document.createElement('span');badge.className='hub-calendar-odds';badge.textContent='Quote disponibili';row.append(badge)}
     else if(!hasOdds&&badge)badge.remove();
    });
   });
  }).catch(()=>{if(calendarToken===calendarRequest&&calendar)games.dataset.fixtureFallback='true'});
 }

 const monthGrid=$('#hub-calendar-month-grid'),monthLabel=$('#hub-calendar-month-label');
 if(monthGrid&&/^\d{4}-\d{2}-\d{2}$/.test(requestedDate)){
  const [year,month]=((calendarVisibleMonth||requestedDate.slice(0,7))+'-01').split('-').map(Number);
  const first=new Date(Date.UTC(year,month-1,1));
  const monthName=new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric',timeZone:'UTC'}).format(first);
  if(monthLabel)monthLabel.textContent=monthName.charAt(0).toUpperCase()+monthName.slice(1);
  monthGrid.replaceChildren();
  for(const label of ['L','M','M','G','V','S','D']){const head=document.createElement('span');head.className='hub-month-weekday';head.textContent=label;monthGrid.append(head)}
  const offset=(first.getUTCDay()+6)%7;
  const daysInMonth=new Date(Date.UTC(year,month,0)).getUTCDate();
  for(let blank=0;blank<offset;blank++){const space=document.createElement('span');space.className='hub-month-empty';monthGrid.append(space)}
  const today=italyDay(new Date());
  for(let day=1;day<=daysInMonth;day++){
   const iso=year+'-'+String(month).padStart(2,'0')+'-'+String(day).padStart(2,'0');
   const button=document.createElement('button');button.type='button';button.textContent=String(day);button.className='hub-month-day'+(iso===requestedDate?' active':'')+(iso===today?' today':'');
   button.setAttribute('aria-label',new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(iso+'T12:00:00Z')));
   button.setAttribute('aria-pressed',String(iso===requestedDate));
   button.addEventListener('click',()=>{calendarSelectDate(iso);const picker=$('#hub-calendar-picker'),toggle=$('#hub-calendar-collapse-toggle');if(picker)picker.hidden=true;if(toggle)toggle.setAttribute('aria-expanded','false')});
   monthGrid.append(button);
  }
 }
 dates.replaceChildren();games.replaceChildren();
 const weekStart=calendarWeekStart||calendarMonday(requestedDate);
 for(let i=0;i<7;i++){
  const dateValue=calendarIsoOffset(weekStart,i);
  const dayDate=new Date(dateValue+'T12:00:00Z');
  const button=document.createElement('button');button.type='button';
  const weekday=new Intl.DateTimeFormat('it-IT',{weekday:'short',timeZone:'UTC'}).format(dayDate).replace('.','').toUpperCase();
  const top=document.createElement('small');top.textContent=weekday;button.append(top);
  const number=document.createElement('strong');number.textContent=String(dayDate.getUTCDate());button.append(number);
  const dot=document.createElement('span');dot.className='hub-calendar-date-dot';dot.setAttribute('aria-hidden','true');button.append(dot);
  button.className='hub-calendar-date'+(dateValue===requestedDate?' active':'');
  button.setAttribute('aria-pressed',String(dateValue===requestedDate));
  button.setAttribute('aria-label',new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(dayDate));
  button.addEventListener('click',()=>calendarSelectDate(dateValue));
  dates.append(button);
 }
 const weekLabel=$('#hub-calendar-week-label');
 if(weekLabel){const mid=new Date(calendarIsoOffset(weekStart,3)+'T12:00:00Z');weekLabel.textContent=new Intl.DateTimeFormat('it-IT',{month:'long',year:'numeric',timeZone:'UTC'}).format(mid)}
 const loading=$('#date-loading')?.hidden===false||fixture?.disabled;
 if(summary){
  const label=/^\d{4}-\d{2}-\d{2}$/.test(requestedDate)?new Intl.DateTimeFormat('it-IT',{timeZone:'UTC',day:'numeric',month:'long',year:'numeric'}).format(new Date(requestedDate+'T12:00:00Z')):(options[index]?.textContent.trim()||'Giornata selezionata');
  summary.replaceChildren();
  const title=document.createElement('strong');title.textContent=label;
  const count=document.createElement('span');count.textContent=isEspnCalendar?'Caricamento calendario NBA…':loading?'Caricamento…':matches.length+' '+(matches.length===1?'partita':'partite');
  summary.append(title,count)
 }
 if(isEspnCalendar){games.textContent='Caricamento calendario NBA…';return}
 if(loading){
  const empty=document.createElement('div');empty.className='hub-calendar-empty';empty.textContent='Caricamento delle partite in corso…';games.append(empty);return
 }
 if(!matches.length){
  const empty=document.createElement('div');empty.className='hub-calendar-empty';empty.textContent='Nessuna partita con quote disponibili per questa giornata.';games.append(empty);return
 }
 for(const [matchIndex,match] of matches.entries()){
  const row=document.createElement('button');row.type='button';row.className='hub-calendar-match hub-calendar-gradient';row.dataset.theme=String(matchIndex%4);
  const teams=match.split(/\s+-\s+|\s+vs\.?\s+/i).map(x=>x.trim());
  if(teams.length===2){
   fixtureTeamGradient(row,teams[0],teams[1]);
   teams.forEach((team,i)=>{
    if(i){const center=document.createElement('span');center.className='hub-calendar-versus';center.textContent='VS';row.append(center)}
    const side=document.createElement('span');side.className='hub-calendar-team';
    const code=matchTeamCodes[team]||matchTeamCodes[team.replace(/^LA /,'Los Angeles ')];
    if(code){const logo=document.createElement('img');logo.src='https://a.espncdn.com/i/teamlogos/nba/500/'+code+'.png';logo.alt='';logo.loading='lazy';logo.addEventListener('error',()=>{logo.hidden=true});side.append(logo)}
    const label=document.createElement('span');label.textContent=team;side.append(label);row.append(side)
   });
  }else{const label=document.createElement('strong');label.textContent=match;row.append(label)}
  const arrow=document.createElement('span');arrow.className='hub-calendar-match-arrow';arrow.textContent='›';row.append(arrow);
  row.setAttribute('aria-label',match+' · Apri analisi e quote');
  row.addEventListener('click',()=>openMatchQuotes(match));games.append(row)
 }
}
// Refresh the visible calendar without changing the prediction date or OddsPapi data.
const calendarLiveTimer=setInterval(()=>{
 if(!calendar||document.hidden||document.body.dataset.hubView!=='calendar')return;
 if(activeCalendarBoxscore){if(activeCalendarBoxscore.state==='in')openCalendarBoxscore(activeCalendarBoxscore,true);return}
 const selected=calendarSelectedDate||$('#date')?.value||italyDay(new Date());
 const cached=nbaFixtureCache.get('date:'+selected);
 if(!cached||cached.expires<=Date.now())renderCalendar();
},MINUTE);
document.addEventListener('visibilitychange',()=>{
 if(!document.hidden&&calendar&&document.body.dataset.hubView==='calendar')scheduleCalendarRefresh();
});
$('#date')?.addEventListener('change',()=>{scheduleCalendarRefresh();setTimeout(scheduleCalendarRefresh,500);setTimeout(scheduleCalendarRefresh,1600)});
const fixtureObserverTarget=$('#finder-fixture');
if(fixtureObserverTarget)new MutationObserver(scheduleCalendarRefresh).observe(fixtureObserverTarget,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','value','selected']});
const dayStripTarget=$('#date-strip');
if(dayStripTarget)new MutationObserver(scheduleCalendarRefresh).observe(dayStripTarget,{childList:true,subtree:true,attributes:true,attributeFilter:['class','aria-selected','aria-pressed']});
function shiftCalendarMonth(delta){
 const current=calendarVisibleMonth||calendarSelectedDate.slice(0,7)||italyDay(new Date()).slice(0,7);
 const [year,month]=current.split('-').map(Number);
 calendarVisibleMonth=new Date(Date.UTC(year,month-1+delta,1)).toISOString().slice(0,7);
 renderCalendar();
}
const calendarToggle=$('#hub-calendar-collapse-toggle'),calendarPicker=$('#hub-calendar-picker');
calendarToggle?.addEventListener('click',()=>{
 if(!calendarPicker)return;
 const expanded=calendarToggle.getAttribute('aria-expanded')==='true';
 calendarPicker.hidden=expanded;calendarToggle.setAttribute('aria-expanded',String(!expanded));
});
$('#hub-calendar-month-prev')?.addEventListener('click',()=>shiftCalendarMonth(-1));
$('#hub-calendar-month-next')?.addEventListener('click',()=>shiftCalendarMonth(1));
for(const [id,offset] of [['hub-calendar-yesterday',-1],['hub-calendar-today',0],['hub-calendar-tomorrow',1]]){
 $('#'+id)?.addEventListener('click',()=>{
  const today=italyDay(new Date());
  const date=new Date(today+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+offset);
  calendarSelectDate(date.toISOString().slice(0,10));
 });
}
function shiftCalendarWeek(delta){calendarSelectDate(calendarIsoOffset(calendarSelectedDate||italyDay(new Date()),delta*7))}
$('#hub-calendar-prev')?.addEventListener('click',()=>shiftCalendarWeek(-1));
$('#hub-calendar-next')?.addEventListener('click',()=>shiftCalendarWeek(1));
const calendarWeekStrip=$('#hub-calendar-dates');let calendarTouchStart=null;
calendarWeekStrip?.addEventListener('touchstart',event=>{calendarTouchStart={x:event.changedTouches[0].clientX,y:event.changedTouches[0].clientY}},{passive:true});
calendarWeekStrip?.addEventListener('touchend',event=>{if(!calendarTouchStart)return;const dx=event.changedTouches[0].clientX-calendarTouchStart.x,dy=event.changedTouches[0].clientY-calendarTouchStart.y;calendarTouchStart=null;if(Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy)*1.3)shiftCalendarWeek(dx<0?1:-1)},{passive:true});
let homeFixturesRequest=0;
function refreshShowcase(){
 const picks=$('#picks'),single=$('#hub-single-content'),state=$('#hub-single-state'),games=$('#hub-games-showcase');
 if(!picks)return;
 if(single){
  const group=picks.querySelector('.pick-group[aria-label="Singola del giorno"]');
  const pick=group?.querySelector('.pick-selection');
  single.replaceChildren();
  if(pick){
   const broadcast=document.createElement('div');broadcast.className='bl-broadcast';
   const hero=document.createElement('div');hero.className='bl-broadcast-hero';
   const photo=hubCardPhoto(pick);hero.append(photo);
   const intro=document.createElement('div');intro.className='bl-broadcast-intro';
   const player=document.createElement('strong');player.className='bl-broadcast-name';player.textContent=hubCardName(pick.querySelector('.pick-player-link')?.textContent||'Giocatore NBA');
   const info=document.createElement('p');info.className='bl-broadcast-info';info.textContent=pick.querySelector('.pick-profile-info p')?.textContent?.trim()||'';
   const fixture=document.createElement('div');fixture.className='bl-broadcast-fixture';
   const teams=[...pick.querySelectorAll('.pick-fixture .fixture-team')];
   const abbreviations=['CLE','OKC','BOS','MIL','PHI','NYK','LAL','LAC','GSW','SAC','DEN','MIN','DAL','HOU','SAS','MIA','ORL','ATL','CHI','DET','IND','CHA','WAS','BKN','TOR','MEM','NOP','UTA','POR','PHX'];
   const matchup=document.createElement('div');matchup.className='bl-game-strip';
   const stripTitle=document.createElement('span');stripTitle.className='bl-game-strip-title';stripTitle.textContent='LA PARTITA';matchup.append(stripTitle);
   const matchupTeams=document.createElement('div');matchupTeams.className='bl-game-teams';
   for(const [index,team] of teams.entries()){
    if(index){const vs=document.createElement('span');vs.className='bl-game-vs';vs.textContent='VS';matchupTeams.append(vs)}
    const item=document.createElement('div');item.className='bl-game-team';
    const logo=team.querySelector('.team-logo img');if(logo){const img=logo.cloneNode(true);img.removeAttribute('id');img.alt='';item.append(img)}
    const raw=(team.querySelector('.fixture-team-name')?.textContent||'').replace(/\s+/g,' ').trim();
    const abbr=abbreviations.find(code=>raw.toUpperCase().endsWith(code))||'';
    const full=abbr?raw.slice(0,-abbr.length).trim():raw;
    const name=document.createElement('span');name.textContent=full||abbr||'Squadra';item.append(name);
    matchupTeams.append(item);
   }
   matchup.append(matchupTeams);
   const fixtureDate=pick.querySelector('.pick-fixture time, .pick-game-time, .fixture-time, [data-game-time]');
   if(fixtureDate){const when=document.createElement('span');when.className='bl-game-when';when.textContent=fixtureDate.textContent?.trim()||'';if(when.textContent)matchup.append(when)}
   const palette={ATL:['#c8102e','#fdb927'],BOS:['#007a33','#ba9653'],BKN:['#202020','#777'],CHA:['#1d1160','#00788c'],CHI:['#ce1141','#101820'],CLE:['#6f263d','#ffb81c'],DAL:['#00538c','#002b5e'],DEN:['#0e2240','#fec524'],DET:['#c8102e','#1d42ba'],GSW:['#1d428a','#ffc72c'],HOU:['#ce1141','#222'],IND:['#002d62','#fdbb30'],LAC:['#c8102e','#1d428a'],LAL:['#552583','#fdb927'],MEM:['#5d76a9','#12173f'],MIA:['#98002e','#f9a01b'],MIL:['#00471b','#eee1c6'],MIN:['#0c2340','#236192'],NOP:['#0c2340','#c8102e'],NYK:['#006bb6','#f58426'],OKC:['#007ac1','#ef3b24'],ORL:['#0077c0','#151f36'],PHI:['#006bb6','#ed174c'],PHX:['#1d1160','#e56020'],POR:['#e03a3e','#111'],SAC:['#5a2d81','#63727a'],SAS:['#5a5f66','#151719'],TOR:['#ce1141','#171717'],UTA:['#4a2784','#6cace4'],WAS:['#002b5c','#e31837']};
   const own=teams.find(t=>{const label=(t.querySelector('.fixture-team-name')?.textContent||'').toLowerCase();return info.textContent.toLowerCase().split(' ').filter(w=>w.length>3).some(w=>label.includes(w))})||teams[teams.length-1];
   const ownLabel=(own?.querySelector('.fixture-team-name')?.textContent||'').toUpperCase();
   const ownCode=abbreviations.find(code=>ownLabel.endsWith(code))||'';
   const [primary,secondary]=palette[ownCode]||['#19334e','#436483'];
   hero.style.setProperty('--bl-team-primary',primary);hero.style.setProperty('--bl-team-secondary',secondary);
   const ownLogo=own?.querySelector('.team-logo img');
   if(ownLogo){const emblem=ownLogo.cloneNode(true);emblem.removeAttribute('id');emblem.className='bl-team-emblem';emblem.alt='';emblem.setAttribute('aria-hidden','true');hero.append(emblem)}
   intro.append(player,info);hero.append(intro);
   const market=document.createElement('div');market.className='bl-broadcast-line';
   const label=document.createElement('small');label.textContent='LINEA SELEZIONATA';
   const line=document.createElement('strong');line.textContent=pick.querySelector('.pick-market')?.textContent?.trim()||'';
   market.append(label,line);
   const metrics=document.createElement('div');metrics.className='bl-broadcast-metrics';
   for(const [title,value,extra] of [['QUOTA',hubCardMetric(pick,/quota/i),''],['PROBABILITÀ STIMATA',hubCardMetric(pick,/stima|probabilit/i),'bl-metric-green']]){
    const box=document.createElement('div');box.className='bl-broadcast-metric '+extra;const small=document.createElement('small');small.textContent=title;const strong=document.createElement('strong');strong.textContent=value||'—';box.append(small,strong);metrics.append(box)
   }
   const probabilityValue=hubCardMetric(pick,/stima|probabilit/i);const percentage=Number(probabilityValue.replace('%','').replace(',','.'));
   if(Number.isFinite(percentage)){const target=metrics.querySelector('.bl-metric-green');if(target){const bar=document.createElement('div');bar.className='bl-classic-prob-track';const fill=document.createElement('span');fill.style.width=Math.max(0,Math.min(100,percentage))+'%';bar.append(fill);target.append(bar)}}
   broadcast.append(hero);if(teams.length)broadcast.append(matchup);broadcast.append(market,metrics);single.append(broadcast);
   const action=document.createElement('button');action.type='button';action.className='bl-broadcast-action';action.textContent='Apri analisi →';action.addEventListener('click',openSingleAnalysis);single.append(action);
  }else{const empty=document.createElement('p');empty.textContent=group?.querySelector('p:last-child')?.textContent||'Nessuna Singola idonea disponibile per questa giornata.';single.append(empty)}
  if(state){const publication=group?.dataset.publicationState||'waiting';state.classList.add('bl-publication-badge');state.dataset.state=publication;state.textContent=publication==='official'?'Ufficiale':publication==='preview'?'Conferma alle 18:00':'In attesa';state.title=publication==='preview'?(group.dataset.publicationLabel||'Selezione provvisoria: non ancora ufficiale'):'Stato della selezione';state.setAttribute('aria-label',state.textContent+(publication==='preview'?'. '+state.title:''));}
 }
 if(games&&(!window.BasketLabSections||window.BasketLabSections.wants('home'))){
  // Homepage always previews the next NBA session, not yesterday's overnight window.
  const day=italyDay(new Date());
  const homeToken=++homeFixturesRequest;
  fetchNbaFixtures(day,true).then(fixtures=>{
   if(homeToken!==homeFixturesRequest)return;
   games.replaceChildren();
   const now=Date.now();
   fixtures=fixtures.filter(game=>game.upcoming===true && game.start_at && new Date(game.start_at).getTime()>now).sort((a,b)=>new Date(a.start_at)-new Date(b.start_at));
   const remaining=fixtures.length;
   fixtures=fixtures.slice(0,4);
   if(!fixtures.length){games.textContent='Nessun’altra partita da iniziare in questa sessione. Consulta il calendario NBA per gli incontri in corso e conclusi.';return}
   for(const [index,game] of fixtures.entries()){
    const match=fixtureName(game);
    const hasOdds=!!matchingFixtureOption(match);
    const row=document.createElement('button');
    row.type='button';
    row.className='hub-match-row hub-premium-fixture';
    row.dataset.theme=String(index%4);
    fixtureTeamGradient(row,game.away,game.home);
    row.setAttribute('aria-label',match+' · '+fixtureTime(game)+' · Apri dettagli');
    const matchup=document.createElement('div');matchup.className='hub-premium-matchup';
    const away=document.createElement('span');away.className='hub-premium-logo';
    const home=document.createElement('span');home.className='hub-premium-logo';
    for(const [node,team] of [[away,game.away],[home,game.home]]){
      const code=matchTeamCodes[team];
      if(code){const logo=document.createElement('img');logo.src='https://a.espncdn.com/i/teamlogos/nba/500/'+code+'.png';logo.alt=team||'';logo.loading='lazy';logo.width=44;logo.height=44;node.append(logo)}
    }
    const center=document.createElement('span');center.className='hub-premium-center';
    const names=document.createElement('strong');names.className='hub-premium-names';
    // Always use the franchise nickname for every team: never mix full and shortened names.
    const nicknames={'Orlando Magic':'Magic','Boston Celtics':'Celtics','Brooklyn Nets':'Nets','Indiana Pacers':'Pacers','Atlanta Hawks':'Hawks','Charlotte Hornets':'Hornets','Chicago Bulls':'Bulls','Cleveland Cavaliers':'Cavaliers','Dallas Mavericks':'Mavericks','Denver Nuggets':'Nuggets','Detroit Pistons':'Pistons','Golden State Warriors':'Warriors','Houston Rockets':'Rockets','Los Angeles Clippers':'Clippers','LA Clippers':'Clippers','L.A. Clippers':'Clippers','Los Angeles Lakers':'Lakers','Memphis Grizzlies':'Grizzlies','Miami Heat':'Heat','Milwaukee Bucks':'Bucks','Minnesota Timberwolves':'Timberwolves','New Orleans Pelicans':'Pelicans','New York Knicks':'Knicks','Oklahoma City Thunder':'Thunder','Philadelphia 76ers':'76ers','Phoenix Suns':'Suns','Portland Trail Blazers':'Blazers','Sacramento Kings':'Kings','San Antonio Spurs':'Spurs','Toronto Raptors':'Raptors','Utah Jazz':'Jazz','Washington Wizards':'Wizards'};
    const shortName=t=>nicknames[String(t||'').trim()]||String(t||'NBA').trim().split(' ').slice(-1)[0];
    names.textContent=shortName(game.away)+' vs '+shortName(game.home);
    const stamp=new Date(game.start_at);
    const dateTime=document.createElement('span');dateTime.className='hub-premium-timing';
    dateTime.textContent=new Intl.DateTimeFormat('it-IT',{timeZone:'Europe/Rome',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}).format(stamp);
    center.append(names,dateTime);
    const arrow=document.createElement('span');arrow.className='hub-premium-arrow';arrow.textContent='›';arrow.setAttribute('aria-hidden','true');
    matchup.append(away,center,home,arrow);
    row.append(matchup);
    row.addEventListener('click',()=>{calendarSelectedDate=game.calendar_date||italyDay(new Date(game.start_at));openFixtureDetails(match)});
    games.append(row)
   }
   if(remaining>4){
    const note=document.createElement('p');note.className='hub-games-more-note';
    note.textContent='Stai visualizzando le prime 4 di '+remaining+' partite in programma';
    games.append(note);
    const more=document.createElement('button');more.type='button';more.className='hub-games-more';
    more.textContent='Vedi altre '+(remaining-4)+' partite ›';
    more.addEventListener('click',()=>{go.calendar();select('calendar')});
    games.append(more);
   }
  }).catch(()=>{if(homeToken===homeFixturesRequest)games.textContent='Calendario NBA temporaneamente non disponibile. Apri Tutte le partite per riprovare.'});
  games.replaceChildren();
  games.textContent='Caricamento delle prossime partite NBA…';
  return;
 }
}
if($('#picks'))new MutationObserver(()=>{featuredPicks();updateInsights();refreshShowcase()}).observe($('#picks'),{childList:true});
/* Restore the active section after a mobile pull-to-refresh, without changing prediction dates. */
try{
 const saved=JSON.parse(sessionStorage.getItem(HUB_STATE_KEY)||'null');
 if(location.pathname==='/'&&!location.hash&&saved&&['home','calendar','picks','stats','finder','history','about'].includes(saved.view)){
  if(/^\d{4}-\d{2}-\d{2}$/.test(saved.date||'')){calendarSelectedDate=saved.date;calendarWeekStart=calendarIsoOffset(saved.date,-3);calendarVisibleMonth=saved.date.slice(0,7)}
  if(saved.view==='calendar'){select('calendar');renderCalendar()}
  else if(saved.match&&saved.view==='finder'){openMatchQuotes(saved.match)}
  else if(saved.view==='home')select('home');
  else{go[saved.view]?.();select(saved.view)}
  if(Number.isFinite(saved.scrollY)&&saved.scrollY>0)setTimeout(()=>window.scrollTo(0,saved.scrollY),250);
 }
}catch(_){}
function applyRoute(){
 const route=window.BasketLabRouter.read(location);
 applyingRoute=true;
 try{
  if(route.date){calendarSelectedDate=route.date;calendarWeekStart=calendarIsoOffset(route.date,-3);calendarVisibleMonth=route.date.slice(0,7)}
  if(route.match){
   const picker=$('#date');
   if(route.date&&picker&&![...picker.options].some(o=>o.value===route.date))picker.add(new Option(route.date,route.date));
   openFixtureDetails(route.match);
  }else{go[route.view]?.();select(route.view)}
 }finally{applyingRoute=false}
}
if(window.BasketLabRouter){
 routerReady=true;
 window.addEventListener('popstate',applyRoute);
 if(location.pathname!=='/')applyRoute();
 // Explicit paths override session restoration. Existing hash links stay valid.
 if(location.hash==='#archivio'){go.history();select('history')}
 else if(location.hash==='#come-funziona'){go.about();select('about')}
}
if(window.BasketLabSections)window.BasketLabSections.register('home',()=>{loadModelPerformance();refreshShowcase();});
refresh();featuredPicks();updateInsights();refreshShowcase();
})();