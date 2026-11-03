/* Verified quarter and player boxscore values; no calculations. */
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
  for(const team of data.teams){
   const section=document.createElement('section');section.className='hub-boxscore-team';
   const title=document.createElement('h4');title.textContent=team.team;section.append(title);
   const scroll=document.createElement('div');scroll.className='hub-boxscore-scroll';
   const table=document.createElement('table');table.className='hub-boxscore-table';
   const head=document.createElement('thead'),tr=document.createElement('tr');
   ['Giocatore','MIN','PTS','REB','AST'].forEach(label=>{const th=document.createElement('th');th.textContent=label;tr.append(th)});head.append(tr);table.append(head);
   const body=document.createElement('tbody');
   for(const player of team.players){const line=document.createElement('tr');[player.name,player.minutes,player.points,player.rebounds,player.assists].forEach(value=>{const cell=document.createElement('td');cell.textContent=value??'—';line.append(cell)});body.append(line)}
   table.append(body);scroll.append(table);section.append(scroll);panel.append(section);
  }
};
