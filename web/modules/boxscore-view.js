/* Verified boxscore values. Sort preferences survive live refreshes per event/team. */
(function(){
const preferences=new Map();
const numeric=value=>value!==null&&value!==undefined&&String(value).trim()!==''&&Number.isFinite(Number(value))?Number(value):null;
function minutes(value){if(/^\d+:\d{2}$/.test(String(value))){const [m,s]=String(value).split(':').map(Number);return m+s/60;}return numeric(value);}
const fields=['name','minutes','points','rebounds','assists'];
window.BasketLabBoxscoreView=function(document,panel,game,data){
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
     link.href='/giocatori/'+slug+'-'+player.id;link.className='hub-boxscore-player-link';link.textContent=player.name||'Giocatore';link.setAttribute('aria-label','Statistiche di '+(player.name||'questo giocatore'));name.append(link);
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
