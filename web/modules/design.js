/* Presentation only. Every chart value comes from the existing filtered game list. */
(function(root){
 'use strict';
 const d=root.document,byId=id=>d.getElementById(id);
 function syncMarket(){for(const button of d.querySelectorAll('[data-player-market]')){const active=button.dataset.playerMarket===byId('stat')?.value;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));}}
 for(const button of d.querySelectorAll('[data-player-market]'))button.addEventListener('click',()=>{const select=byId('stat');select.value=button.dataset.playerMarket;select.dispatchEvent(new Event('change',{bubbles:true}));syncMarket();});
 byId('stat')?.addEventListener('change',syncMarket);syncMarket();
 const windowSelect=byId('playerwindow');
 const windowButtons=[...d.querySelectorAll('[data-player-window]')];
 function syncWindow(){
  for(const button of windowButtons)button.setAttribute('aria-pressed',String(button.dataset.playerWindow===windowSelect.value));
 }
 for(const button of windowButtons)button.addEventListener('click',()=>{
  windowSelect.value=button.dataset.playerWindow;
  windowSelect.dispatchEvent(new Event('change',{bubbles:true}));
 });
 windowSelect?.addEventListener('change',syncWindow);syncWindow();
 function playerChart(games,stat,line,max){
  syncMarket();syncWindow();const area=byId('player-visual');if(!area)return;
  area.replaceChildren();area.hidden=!games.length;if(!games.length)return;
  const title=d.createElement('p');title.className='bl-chart-caption';title.textContent=games.length>20?'Ultime 20 mostrate · Tutte le partite nel dettaglio sotto':'Prestazioni per partita · '+({PTS:'Punti',REB:'Rimbalzi',AST:'Assist'}[stat]||stat);area.append(title);
  const scroll=d.createElement('div');scroll.className='bl-chart-scroll';scroll.tabIndex=0;scroll.setAttribute('role','region');scroll.setAttribute('aria-label','Grafico prestazioni, scorri per vedere le partite');
  const plot=d.createElement('div');plot.className='bl-chart-plot';
  const sample=games.slice(0,20).reverse();plot.style.minWidth=Math.max(280,sample.length*34)+'px';
  const threshold=d.createElement('div');threshold.className='bl-chart-threshold';threshold.style.bottom=(100*line/max)+'%';const label=d.createElement('span');label.textContent='Linea '+line.toLocaleString('it-IT');threshold.append(label);plot.append(threshold);
  const detail=d.createElement('p');detail.className='bl-chart-detail';detail.setAttribute('aria-live','polite');detail.textContent='Tocca una barra per vedere i dettagli.';
  for(const game of sample){
   const value=Number(game[stat]),column=d.createElement('button');column.type='button';column.className='bl-chart-column';
   const bar=d.createElement('div');bar.className='bl-chart-bar'+(value>line?' is-over':value<line?' is-under':'');bar.style.height=(100*value/max)+'%';
   const number=d.createElement('b');number.textContent=value.toLocaleString('it-IT');bar.append(number);
   const date=d.createElement('small');date.textContent=String(game.GAME_DATE).slice(5,10).split('-').reverse().join('/');
   column.addEventListener('click',()=>{
    const minutes=game.MIN==null||game.MIN===''?'Minuti n.d.':game.MIN+' min';
    detail.textContent=[date.textContent,game.MATCHUP||'Avversario n.d.',minutes,value+' '+stat].join(' · ');
   });
   column.setAttribute('aria-label',String(game.GAME_DATE).slice(0,10)+': '+value+' '+stat);column.append(bar,date);plot.append(column);
  }
  scroll.append(plot);area.append(scroll,detail);
 }
 function playerTheme(code){const colors={BOS:'#006c40',ATL:'#812335',LAL:'#452a70',PHX:'#56301b',PHI:'#164f78',DET:'#66314b',NYK:'#234d76',GSW:'#1b4978',MIL:'#135343',DEN:'#203f63',CLE:'#683541',MIA:'#722c42',DAL:'#164f67',OKC:'#185478',SAS:'#35434c',SAC:'#4e326b',POR:'#702b3d',TOR:'#6c2839',MEM:'#314e70',MIN:'#1a4c66',NOP:'#344c56',UTA:'#3a3c60',WAS:'#344f6e',CHA:'#1e5863',CHI:'#702b3a',BKN:'#354454',IND:'#374a69',ORL:'#214f73',LAC:'#6c314c',HOU:'#742638'};byId('player-profile')?.style.setProperty('--player-team-color',colors[code]||'#174b56');}
 root.BasketLabDesign={playerChart,syncMarket,playerTheme};
})(window);
