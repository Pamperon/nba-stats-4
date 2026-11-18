/* Verified boxscore values. Sort preferences survive live refreshes per event/team. */
(function(){
const preferences=new Map();
const numeric=value=>value!==null&&value!==undefined&&String(value).trim()!==''&&Number.isFinite(Number(value))?Number(value):null;
function minutes(value){if(/^\d+:\d{2}$/.test(String(value))){const [m,s]=String(value).split(':').map(Number);return m+s/60;}return numeric(value);}
const fields=['name','minutes','points','rebounds','assists'];
let drawer=null,selected=null,snapshot=null,returnFocus=null,returnScroll=0,restoreOnClose=true;
const identity=game=>String(game.event_id||[game.away,game.home].join('|'));
function ensureDrawer(document){
 if(drawer)return drawer;
 const make=(tag,cls,text)=>{const node=document.createElement(tag);if(cls)node.className=cls;if(text!=null)node.textContent=text;return node;};
 drawer=make('dialog','bl-game-player-dialog');drawer.id='bl-game-player-panel';drawer.setAttribute('aria-labelledby','bl-game-player-name');drawer.setAttribute('aria-describedby','bl-game-player-match');
 const close=make('button','bl-game-player-close','×');close.type='button';close.setAttribute('aria-label','Chiudi statistiche giocatore');close.autofocus=true;close.onclick=closeDrawer;
 const label=make('p','bl-game-player-eyebrow','Statistiche della partita');
 const header=make('div','bl-game-player-header'),avatar=make('div','bl-game-player-avatar'),initials=make('span','bl-game-player-initials');initials.setAttribute('aria-hidden','true');
 const photo=make('img','bl-game-player-photo');photo.alt='';photo.decoding='async';photo.onerror=()=>{photo.hidden=true;initials.hidden=false;};photo.onload=()=>{if(photo.naturalWidth){photo.hidden=false;initials.hidden=true;}};
 avatar.append(initials,photo);
 const bio=make('div','bl-game-player-bio'),name=make('h2','');name.id='bl-game-player-name';
 const team=make('p','bl-game-player-team'),status=make('p','bl-game-player-status');bio.append(name,team,status);header.append(avatar,bio);
 const match=make('p','bl-game-player-match');match.id='bl-game-player-match';
 const stats=make('dl','bl-game-player-stats');
 for(const [key,text] of [['points','Punti'],['rebounds','Rimbalzi'],['assists','Assist'],['minutes','Minuti']]){const item=make('div',''),term=make('dt','',text),value=make('dd','','—');value.dataset.gamePlayerStat=key;item.append(term,value);stats.append(item);}
 const unavailable=make('p','bl-game-player-unavailable','Statistiche del giocatore non ancora disponibili.');unavailable.hidden=true;
 const link=make('a','bl-game-player-profile','Apri il profilo completo →');link.onclick=event=>{if(!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey)closeDrawer(false);};
 drawer.append(close,label,header,match,stats,unavailable,link);document.body.append(drawer);
 drawer.addEventListener('click',event=>{if(event.target!==drawer)return;const rect=drawer.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)closeDrawer();});
 drawer.addEventListener('close',()=>{
  selected=null;document.documentElement.classList.remove('bl-game-player-open');
  const target=returnFocus&&[...document.querySelectorAll('.hub-boxscore-player-link')].find(a=>a.getAttribute('href')===returnFocus.href&&a.closest('.hub-boxscore-team')?.dataset.team===returnFocus.team);
  if(restoreOnClose){target?.focus({preventScroll:true});if(window.scrollY!==returnScroll)window.scrollTo({top:returnScroll,behavior:'instant'});}returnFocus=null;
 });
 document.addEventListener('basketlab:view',()=>closeDrawer(false));window.addEventListener('popstate',()=>closeDrawer(false));window.addEventListener('pagehide',()=>closeDrawer(false));
 return drawer;
}
function closeDrawer(restore=true){if(!drawer?.open)return;restoreOnClose=restore!==false;if(typeof drawer.close==='function')drawer.close();else{drawer.removeAttribute('open');drawer.dispatchEvent(new Event('close'));}}
function paintDrawer(){
 if(!selected||!snapshot)return;
 const {game,data}=snapshot,team=(data.teams||[]).find(t=>t.team===selected.team),player=team?.players?.find(p=>String(p.id)===selected.id);
 if(!player)return;
 drawer.querySelector('#bl-game-player-name').textContent=player.name||'Giocatore';drawer.querySelector('.bl-game-player-team').textContent=team.team;
 const period=Number(game.period)||0,state=data.state||game.state;
 drawer.querySelector('.bl-game-player-status').textContent=state==='post'?'Finale':state==='in'?['Live',period>4?'OT '+(period-4):period?'Q'+period:'',game.display_clock||''].filter(Boolean).join(' · '):'Statistiche della gara';
 drawer.querySelector('.bl-game-player-match').textContent=[game.away,game.home].filter(Boolean).join(' – ');
 for(const field of fields.slice(1)){const value=player[field];drawer.querySelector('[data-game-player-stat='+field+']').textContent=value===null||value===undefined||String(value).trim()===''?'—':String(value);}
 drawer.querySelector('.bl-game-player-unavailable').hidden=fields.slice(1).some(field=>numeric(player[field])!==null||field==='minutes'&&/^\d+:\d{2}$/.test(String(player[field])));
 const photo=drawer.querySelector('img'),initials=drawer.querySelector('.bl-game-player-initials');initials.textContent=String(player.name||'').trim().split(/\s+/).slice(0,2).map(n=>n[0]||'').join('');
 const src='/api/players/headshot/'+selected.id;if(photo.getAttribute('src')!==src){photo.hidden=false;initials.hidden=false;photo.src=src;}
 drawer.querySelector('.bl-game-player-profile').href=selected.href;
}
function openDrawer(document,link,player,team){
 ensureDrawer(document);selected={event:identity(snapshot.game),id:String(player.id),team,href:link.getAttribute('href')};returnFocus={href:selected.href,team};returnScroll=window.scrollY;restoreOnClose=true;
 paintDrawer();document.documentElement.classList.add('bl-game-player-open');if(typeof drawer.showModal==='function')drawer.showModal();else drawer.setAttribute('open','');
}
window.BasketLabBoxscoreView=function(document,panel,game,data){
  snapshot={game,data};if(drawer?.open){if(selected?.event!==identity(game))closeDrawer(false);else paintDrawer();}
  if(Array.isArray(data.quarters)&&data.quarters.length){
   const periods=document.createElement('section');periods.className='hub-boxscore-periods';
   const caption=document.createElement('h4');caption.textContent='Risultato per quarto';periods.append(caption);
   const scroll=document.createElement('div');scroll.className='hub-boxscore-period-scroll';
   const table=document.createElement('table');table.className='hub-boxscore-period-table';
   const thead=document.createElement('thead'),headrow=document.createElement('tr');
   ['Squadra',...data.quarters.map(q=>q.label),'TOT'].forEach(label=>{const th=document.createElement('th');th.textContent=label;headrow.append(th)});
   thead.append(headrow);table.append(thead);
   const tbody=document.createElement('tbody');
   for(const [side,name,total] of [['away',game.away,game.away_score],['home',game.home,game.home_score]]){
    const tr=document.createElement('tr');
    [name,...data.quarters.map(q=>q[side]??'—'),total??'—'].forEach(value=>{const td=document.createElement('td');td.textContent=String(value);tr.append(td)});
    tbody.append(tr);
   }
   table.append(tbody);scroll.append(table);periods.append(scroll);panel.append(periods);
  }
  if(!data.teams?.some(team=>team.players?.length)){const empty=document.createElement('p');empty.textContent='ESPN non ha ancora pubblicato le statistiche dei giocatori.';panel.append(empty);return}
  const leaders=data.teams.flatMap(team=>(team.players||[]).map(player=>({...player,team:team.team}))).filter(p=>numeric(p.points)!==null).sort((a,b)=>Number(b.points)-Number(a.points)).slice(0,3);
  if(leaders.length){
   const section=document.createElement('section');section.className='sheet-leaders';
   const heading=document.createElement('h4');heading.textContent='In evidenza';const note=document.createElement('p');note.textContent='I migliori realizzatori della partita';section.append(heading,note);
   const list=document.createElement('div');list.className='sheet-leader-list';
   for(const player of leaders){
    const card=document.createElement('div');card.className='sheet-leader';const name=document.createElement('strong');name.textContent=player.name||'—';const team=document.createElement('small');team.textContent=player.team;
    const stats=document.createElement('p');for(const [key,label] of [['points','PTS'],['rebounds','REB'],['assists','AST']]){const cell=document.createElement('span'),value=document.createElement('b');value.textContent=player[key]??'—';cell.append(value,document.createTextNode(' '+label));stats.append(cell);}
    card.append(name,team,stats);list.append(card);
   }section.append(list);panel.append(section);
  }
  for(const team of data.teams){
   const section=document.createElement('section');section.className='hub-boxscore-team';section.dataset.team=team.team;
   const title=document.createElement('h4');title.textContent=team.team;section.append(title);
   const scroll=document.createElement('div');scroll.className='hub-boxscore-scroll';
   const table=document.createElement('table');table.className='hub-boxscore-table';
   const head=document.createElement('thead'),tr=document.createElement('tr');
   const key=String(game.event_id||[game.away,game.home].join('|'))+':'+team.team;
   let sort=preferences.get(key)||null;
   const headers=[];
   ['Giocatore','MIN','PTS','REB','AST'].forEach((label,index)=>{
    const th=document.createElement('th');th.scope='col';const button=document.createElement('button');button.type='button';button.textContent=label;button.dataset.boxscoreSort=fields[index];button.setAttribute('aria-label','Ordina per '+label);th.append(button);headers.push(th);tr.append(th);
    button.onclick=()=>{sort={field:fields[index],direction:sort?.field===fields[index]&&sort.direction==='descending'?'ascending':'descending'};preferences.set(key,sort);if(preferences.size>60)preferences.delete(preferences.keys().next().value);applySort();};
   });head.append(tr);table.append(head);
   const body=document.createElement('tbody');
   const rows=[];
   for(const [index,player] of (team.players||[]).entries()){
    const line=document.createElement('tr'),name=document.createElement('td');
    if(/^\d{1,12}$/.test(String(player.id||''))){
     const link=document.createElement('a');const slug=String(player.name||'giocatore').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'giocatore';
     link.href='/giocatori/'+slug+'-'+player.id;link.className='hub-boxscore-player-link';link.textContent=player.name||'Giocatore';link.setAttribute('aria-label','Statistiche di '+(player.name||'questo giocatore'));link.setAttribute('aria-haspopup','dialog');link.setAttribute('aria-controls','bl-game-player-panel');link.onclick=event=>{if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button>0)return;event.preventDefault();openDrawer(document,link,player,team.team);};name.append(link);
    }else name.textContent=player.name||'—';
    line.append(name);[player.minutes,player.points,player.rebounds,player.assists].forEach(value=>{const cell=document.createElement('td');cell.textContent=value??'—';line.append(cell)});body.append(line);rows.push({line,player,index});
   }
   function applySort(){
    headers.forEach((th,index)=>th.setAttribute('aria-sort',sort?.field===fields[index]?sort.direction:'none'));
    const ordered=rows.slice();if(sort)ordered.sort((a,b)=>{
     const field=sort.field;
     if(field==='name')return (sort.direction==='ascending'?1:-1)*String(a.player.name||'').localeCompare(String(b.player.name||''),'it')||a.index-b.index;
     const value=p=>field==='minutes'?minutes(p[field]):numeric(p[field]),av=value(a.player),bv=value(b.player);
     if(av===null||bv===null)return av===bv?a.index-b.index:av===null?1:-1;
     return (sort.direction==='ascending'?av-bv:bv-av)||a.index-b.index;
    });body.replaceChildren(...ordered.map(row=>row.line));
   }
   applySort();table.append(body);scroll.append(table);section.append(scroll);panel.append(section);
  }
};

})();
