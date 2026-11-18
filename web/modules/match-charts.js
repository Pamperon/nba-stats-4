/* Presentation only: existing chart formulas and visual identity. */
window.BasketLabMatchCharts=function(document,matchTeamCodes,displayNum){
const $=s=>document.querySelector(s);
const matchTeamPalette={atl:'#e03a3e',bos:'#007a33',bkn:'#c5c5c5',cha:'#1d8cab',chi:'#ce1141',cle:'#b58a43',dal:'#0053bc',den:'#fdb927',det:'#c8102e',gs:'#ffc72c',hou:'#ce1141',ind:'#fdbb30',lac:'#c8102e',lal:'#fdb927',mem:'#5d76a9',mia:'#98002e',mil:'#00471b',min:'#236192',no:'#b4975a',ny:'#f58426',okc:'#007ac1',orl:'#0077c0',phi:'#006bb6',phx:'#e56020',por:'#e03a3e',sac:'#5a2d81',sa:'#a5acaf',tor:'#ce1141',utah:'#753bbd',wsh:'#e31837'};
function renderMatchCharts(teams,a,b,windowDays,matchOdds){
 const area=$('#hub-match-charts');if(!area)return;area.replaceChildren();
 const colors=teams.map(t=>matchTeamPalette[matchTeamCodes[t]]||'#4388b9');
 const panel=$('#hub-match-analysis');if(panel){panel.style.setProperty('--match-team-a',colors[0]);panel.style.setProperty('--match-team-b',colors[1]);}
 const make=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e};
 const card=make('div','hub-match-chart-card bl-match-v2');
 const win=make('section','bl-match-v2-section');win.append(make('strong','bl-match-v2-heading','Probabilità di vittoria'));
 const validOdds=Array.isArray(matchOdds)&&matchOdds.length===2&&matchOdds.every(x=>Number.isFinite(Number(x))&&Number(x)>1);
 if(validOdds){
  const implied=matchOdds.map(x=>1/Number(x)),total=implied[0]+implied[1],pct=implied.map(x=>100*x/total);
  const labels=make('div','bl-match-v2-labels');
  teams.forEach((team,i)=>{const side=make('div','bl-match-v2-side');side.append(make('b','',pct[i].toLocaleString('it-IT',{maximumFractionDigits:1})+'%'),make('small','',team));labels.append(side)});
  const bar=make('div','bl-match-v2-split');bar.setAttribute('role','img');bar.setAttribute('aria-label',teams.map((t,i)=>t+': '+pct[i].toFixed(1)+'%').join(', '));
  pct.forEach((n,i)=>{const seg=make('span','');seg.style.width=n+'%';seg.style.background=colors[i];bar.append(seg)});
  win.append(labels,bar);
  win.append(make('small','bl-match-v2-note','Probabilità implicite normalizzate dalle quote disponibili'));
 }else win.append(make('p','hub-match-win-unavailable','Quote vincente partita non disponibili'));
 card.append(win);
 area.append(card);
 const comparison=make('section','sheet-comparison');
 comparison.append(make('h3','','Il confronto'),make('p','sheet-caption','Ultime 5 disponibili · risultati precedenti alla partita · finestra di '+windowDays+' giorni'));
 const table=make('div','sheet-comparison-table');
 const head=make('div','sheet-comparison-row sheet-comparison-head');head.append(make('strong','',teams[0]),make('span','',''),make('strong','',teams[1]));table.append(head);
 const number=value=>value!==null&&value!==undefined&&value!==''&&Number.isFinite(Number(value))?Number(value):null;
 const average=(team,select)=>{const values=(team.results||[]).map(select).filter(v=>v!==null);return values.length?values.reduce((sum,n)=>sum+n,0)/values.length:null;};
 const allowed=team=>average(team,g=>number(g.allowed));
 const margin=team=>average(team,g=>number(g.scored)!==null&&number(g.allowed)!==null?Number(g.scored)-Number(g.allowed):null);
 const stats=[a,b].map(team=>({points:number(team.avg_points),allowed:allowed(team)}));
 for(const [label,values] of [['Media punti segnati',stats.map(x=>x.points)],['Media punti subiti',stats.map(x=>x.allowed)],['Differenza punti',[a,b].map(margin)]]){
  const row=make('div','sheet-comparison-row');
  row.append(make('b','',values[0]===null?'—':values[0].toLocaleString('it-IT',{maximumFractionDigits:1})),make('span','',label),make('b','',values[1]===null?'—':values[1].toLocaleString('it-IT',{maximumFractionDigits:1})));table.append(row);
 }
 comparison.append(table);area.append(comparison);
 const form=make('section','bl-match-v2-form');const formHead=make('div','bl-match-v2-form-head');formHead.append(make('strong','','Forma (ultime 5)'),make('small','',teams.map((t,i)=>t.split(' ').slice(-1)[0]+' '+[a,b][i].wins+'-'+[a,b][i].losses).join(' · ')));form.append(formHead);
 const streak=make('div','hub-match-form-streak bl-match-v2-streak');
 teams.forEach((team,i)=>{const group=make('div','');group.append(make('small','',team));const dots=make('div','hub-match-form-dots bl-match-v2-results');
 for(const game of [a,b][i].results||[]){const won=Number(game.scored)>Number(game.allowed);const chip=make('span',won?'won':'lost',won?'V':'P');chip.title=game.date+' · '+game.scored+'-'+game.allowed+' vs '+game.opponent;chip.setAttribute('aria-label',won?'Vittoria':'Sconfitta');dots.append(chip)}
 group.append(dots);streak.append(group)});form.append(streak);area.append(form);
}
function renderMatchH2H(teams,games,windowDays=21){
 const area=$('#hub-match-analysis');
 if(!area)return;
 let widget=$('#hub-match-h2h-chart');
 if(!widget){widget=document.createElement('div');widget.id='hub-match-h2h-chart';widget.className='hub-match-h2h-chart';area.append(widget)}
 widget.replaceChildren();
 const heading=document.createElement('strong');heading.textContent='Scontri diretti';widget.append(heading);
 if(!games.length){const empty=document.createElement('p');empty.textContent='Nessuno scontro diretto nel periodo esaminato';widget.append(empty);return}
 const wins=teams.map(team=>games.filter(game=>{const index=game.teams.indexOf(team);return index>=0&&Number(game.scores[index])>Number(game.scores[1-index])}).length);
 const names=document.createElement('div');names.className='hub-match-h2h-names';
 teams.forEach((team,i)=>{const side=document.createElement('span');side.textContent=team+' · '+wins[i];names.append(side)});widget.append(names);
 const bar=document.createElement('div');bar.className='hub-match-h2h-bar';
 const colors=teams.map(team=>matchTeamPalette[matchTeamCodes[team]]||'#4388b9');
 wins.forEach((count,i)=>{const segment=document.createElement('span');segment.style.width=(100*count/games.length)+'%';segment.style.background=colors[i];bar.append(segment)});widget.append(bar);
 const note=document.createElement('small');note.textContent=games.length+' '+(games.length===1?'partita':'partite')+' negli ultimi '+windowDays+' giorni';widget.append(note);
 const list=document.createElement('div');list.className='sheet-h2h-results';
 for(const game of games){
  const row=document.createElement('div');row.className='sheet-h2h-result';
  const date=document.createElement('small');date.textContent=String(game.date||'').split('-').reverse().join('/');
  row.append(date);
  (game.teams||[]).forEach((team,i)=>{const side=document.createElement('span');side.textContent=team;const score=document.createElement('b');score.textContent=game.scores?.[i]??'—';side.append(score);row.append(side);});list.append(row);
 }widget.append(list);
}

return {renderMatchCharts,renderMatchH2H};
};
