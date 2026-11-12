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
  const sample=games.slice(0,20).reverse();plot.style.minWidth=Math.max(280,sample.length*60)+'px';
  const threshold=d.createElement('div');threshold.className='bl-chart-threshold';threshold.style.bottom=(100*line/max)+'%';const label=d.createElement('span');label.textContent='Linea '+line.toLocaleString('it-IT');threshold.append(label);plot.append(threshold);
  const detail=d.createElement('div');detail.className='bl-chart-detail';detail.setAttribute('aria-live','polite');detail.textContent='Tocca una barra per vedere i dettagli.';
  for(const game of sample){
   const value=Number(game[stat]),column=d.createElement('button');column.type='button';column.className='bl-chart-column';column.setAttribute('aria-pressed','false');
   const bar=d.createElement('div');bar.className='bl-chart-bar'+(value>line?' is-over':value<line?' is-under':'');bar.style.height=(100*value/max)+'%';
   const number=d.createElement('b');number.textContent=value.toLocaleString('it-IT');bar.append(number);
   const date=d.createElement('small');date.textContent=String(game.GAME_DATE).slice(5,10).split('-').reverse().join('/');const opponent=d.createElement('span');opponent.className='pe-chart-opponent';opponent.textContent=game.MATCHUP||'';date.append(d.createElement('br'),opponent);
   column.addEventListener('click',()=>{
    plot.querySelectorAll('.bl-chart-column').forEach(b=>b.setAttribute('aria-pressed',String(b===column)));
    const names={ATL:'Atlanta Hawks',BOS:'Boston Celtics',BKN:'Brooklyn Nets',CHA:'Charlotte Hornets',CHI:'Chicago Bulls',CLE:'Cleveland Cavaliers',DAL:'Dallas Mavericks',DEN:'Denver Nuggets',DET:'Detroit Pistons',GS:'Golden State Warriors',GSW:'Golden State Warriors',HOU:'Houston Rockets',IND:'Indiana Pacers',LAC:'Los Angeles Clippers',LAL:'Los Angeles Lakers',MEM:'Memphis Grizzlies',MIA:'Miami Heat',MIL:'Milwaukee Bucks',MIN:'Minnesota Timberwolves',NO:'New Orleans Pelicans',NOP:'New Orleans Pelicans',NY:'New York Knicks',NYK:'New York Knicks',OKC:'Oklahoma City Thunder',ORL:'Orlando Magic',PHI:'Philadelphia 76ers',PHX:'Phoenix Suns',POR:'Portland Trail Blazers',SAC:'Sacramento Kings',SA:'San Antonio Spurs',SAS:'San Antonio Spurs',TOR:'Toronto Raptors',UTAH:'Utah Jazz',UTA:'Utah Jazz',WSH:'Washington Wizards',WAS:'Washington Wizards'};
    const matchup=String(game.MATCHUP||'').trim(),match=matchup.match(/(@|vs\.?)\s*(.+)$/i),opponent=match?(names[match[2].toUpperCase()]||match[2]):'';
    const day=new Date(String(game.GAME_DATE).slice(0,10)+'T12:00:00Z');
    const heading=d.createElement('strong');heading.className='bl-chart-detail-date';heading.textContent=Number.isNaN(day.getTime())?'Data non disponibile':new Intl.DateTimeFormat('it-IT',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(day);
    const fixture=d.createElement('p');fixture.className='bl-chart-detail-fixture';fixture.textContent=opponent?(match[1]==='@'?'In trasferta contro ':'In casa contro ')+opponent:'Avversario non disponibile';
    const metrics=d.createElement('div');metrics.className='bl-chart-detail-metrics';
    const unit={PTS:'punti',REB:'rimbalzi',AST:'assist'}[stat]||stat;
    for(const [label,text] of [['Prestazione',value.toLocaleString('it-IT')+' '+unit],['Minuti giocati',game.MIN==null||game.MIN===''?'Non disponibili':String(game.MIN)],['Linea',Number(line).toLocaleString('it-IT')]]){
     const cell=d.createElement('div'),caption=d.createElement('small'),metric=d.createElement('b');caption.textContent=label;metric.textContent=text;cell.append(caption,metric);metrics.append(cell);
    }
    const outcome=d.createElement('p');outcome.className='bl-chart-detail-outcome';outcome.dataset.result=value>line?'over':value<line?'under':'equal';outcome.textContent=value>line?'Linea superata':value<line?'Linea non superata':'Prestazione pari alla linea';
    detail.classList.add('has-selection');detail.replaceChildren(heading,fixture,metrics,outcome);
   });
   column.setAttribute('aria-label',String(game.GAME_DATE).slice(0,10)+': '+value+' '+stat);column.append(bar,date);plot.append(column);
  }
  scroll.append(plot);
  area.append(scroll,detail);
 }
 function playerTheme(code){const colors={BOS:'#006c40',ATL:'#812335',LAL:'#452a70',PHX:'#56301b',PHI:'#164f78',DET:'#66314b',NYK:'#234d76',GSW:'#1b4978',MIL:'#135343',DEN:'#203f63',CLE:'#683541',MIA:'#722c42',DAL:'#164f67',OKC:'#185478',SAS:'#35434c',SAC:'#4e326b',POR:'#702b3d',TOR:'#6c2839',MEM:'#314e70',MIN:'#1a4c66',NOP:'#344c56',UTA:'#3a3c60',WAS:'#344f6e',CHA:'#1e5863',CHI:'#702b3a',BKN:'#354454',IND:'#374a69',ORL:'#214f73',LAC:'#6c314c',HOU:'#742638'};const profile=byId('player-profile');if(!profile)return;profile.style.setProperty('--player-team-color',colors[code]||'#174b56');const secondary={ATL:'#fdb927',BOS:'#ba9653',BKN:'#808080',CHA:'#00788c',CHI:'#101820',CLE:'#ffb81c',DAL:'#8fbded',DEN:'#fec524',DET:'#1d42ba',GSW:'#ffc72c',HOU:'#aaaaaa',IND:'#fdbb30',LAC:'#1d428a',LAL:'#fdb927',MEM:'#7dbce8',MIA:'#f9a01b',MIL:'#eee1c6',MIN:'#78be20',NOP:'#c8102e',NYK:'#f58426',OKC:'#ef3b24',ORL:'#c4ced4',PHI:'#ed174c',PHX:'#e56020',POR:'#aaaaaa',SAC:'#a9a9b1',SAS:'#c4ced4',TOR:'#ce1141',UTA:'#6cace4',WAS:'#e31837'};profile.style.setProperty('--player-team-secondary',secondary[code]||'#347f9c');const aliases={GSW:'gs',NOP:'no',NYK:'ny',SAS:'sa',UTA:'utah',WAS:'wsh'};profile.style.setProperty('--player-team-emblem',colors[code]?'url("https://a.espncdn.com/i/teamlogos/nba/500/'+(aliases[code]||code.toLowerCase())+'.png")':'none');}
 root.BasketLabDesign={playerChart,syncMarket,playerTheme};
})(window);
