/* URL codec and History API. No data, model or DOM dependencies. */
(function(root){
 'use strict';
 const paths={home:'/',picks:'/pronostici',calendar:'/nba',finder:'/analisi-quote',stats:'/giocatori',history:'/archivio',about:'/come-funziona',news:'/notizie',single:'/analisi-singola'};
 function validDay(value){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return '';
  const day=new Date(value+'T12:00:00Z');
  return Number.isFinite(day.getTime())&&day.toISOString().slice(0,10)===value?value:'';
 }
 function read(location){
  const path=location.pathname.replace(/\/$/,'')||'/';
  const query=new URLSearchParams(location.search);
  const player=path.match(/^\/giocatori\/([a-z0-9-]+-\d{1,12})$/);
  const team=path.match(/^\/squadre\/([a-z0-9-]+-\d{1,8})$/);
  const view=team||path==='/partite'||path==='/nba/classifica'?'calendar':player||path==='/statistiche'?'stats':path==='/analisi-partita'?'finder':Object.keys(paths).find(k=>paths[k]===path)||'home';
  const date=validDay(query.get('data'));
  const a=query.get('trasferta'),b=query.get('casa');
  const result={view,date,match:path==='/analisi-partita'&&date&&a&&b&&a.length<=80&&b.length<=80?a+' - '+b:''};
  if(view==='calendar'){const boxscore=query.get('partita');result.boxscore=/^\d{1,12}$/.test(boxscore||'')?boxscore:'';result.nbaTab=team||path==='/nba/classifica'?'standings':'calendar';result.team=team?team[1]:'';}
  if(player){result.player=player[1];result.filters={market:query.get('mercato'),line:query.get('linea'),window:query.get('periodo'),season:query.get('stagione'),venue:query.get('campo'),mode:query.get('competizione')};}
  return result;
 }
 function url(state){
  const params=new URLSearchParams();
  if(state.date&&(state.view==='calendar'||state.match))params.set('data',state.date);
  let path=paths[state.view]||'/';
  if(state.view==='calendar'){if(state.team&&/^[a-z0-9-]+-\d{1,8}$/.test(state.team)){path='/squadre/'+state.team;params.delete('data');}else if(state.nbaTab==='standings'){path='/nba/classifica';params.delete('data');}}
  if(state.view==='calendar'&&state.boxscore&&/^\d{1,12}$/.test(state.boxscore)&&params.has('data')&&!state.team&&state.nbaTab!=='standings')params.set('partita',state.boxscore);
  if(state.view==='stats'&&/^[a-z0-9-]+-\d{1,12}$/.test(state.player||'')){
   path='/giocatori/'+state.player;
   const keys={market:'mercato',line:'linea',window:'periodo',season:'stagione',venue:'campo',mode:'competizione'};
   for(const [key,param] of Object.entries(keys))if(state.filters?.[key])params.set(param,state.filters[key]);
  }
  if(state.match){const teams=state.match.split(/\s+-\s+|\s+vs\.?\s+/i);if(teams.length===2){path='/analisi-partita';params.set('trasferta',teams[0]);params.set('casa',teams[1]);}}
  return path+(params.size?'?'+params:'');
 }
 let metadataPath=root.location.pathname;
 function updateMetadata(){
  const document=root.document,config=document?.getElementById('bl-seo-routes');
  if(!config||metadataPath===root.location.pathname)return;
  metadataPath=root.location.pathname;
  let pages;try{pages=JSON.parse(config.textContent)}catch{return}
  const path=root.location.pathname.replace(/\/$/,'')||'/';
  let info=pages[path],canonical='https://basketlab.it'+path,robots='index,follow';
  const player=path.match(/^\/giocatori\/([a-z0-9-]+)-[0-9]{1,12}$/);
  if(player){const name=player[1].split('-').map(s=>s.charAt(0).toUpperCase()+s.slice(1)).join(' ');info=[name+': statistiche NBA e grafici | Basket Lab','Statistiche NBA di '+name+': punti, rimbalzi, assist, medie e grafici delle ultime partite. Consulta le linee disponibili e le frequenze osservate.']}
  const team=path.match(/^\/squadre\/([a-z0-9-]+)-[0-9]{1,8}$/);
  if(team){const name=team[1].split('-').map(s=>s.charAt(0).toUpperCase()+s.slice(1)).join(' ');info=[name+': rosa, calendario e statistiche NBA | Basket Lab','Classifica, prossime partite, risultati e rosa dei '+name+'.'];}
  if(!info){info=['Analisi partita NBA | Basket Lab','Statistiche e analisi delle partite NBA.'];canonical='https://basketlab.it/partite';robots='noindex,follow'}
  document.title=info[0];
  const values={'meta[name="description"]':['content',info[1]],'link[rel="canonical"]':['href',canonical],'meta[property="og:title"]':['content',info[0]],'meta[property="og:description"]':['content',info[1]],'meta[property="og:url"]':['content',canonical],'meta[name="twitter:title"]':['content',info[0]],'meta[name="twitter:description"]':['content',info[1]],'meta[name="robots"]':['content',robots]};
  for(const [selector,[attribute,value]] of Object.entries(values))document.querySelector(selector)?.setAttribute(attribute,value);
  const schema=document.getElementById('bl-page-schema');
  if(schema){try{const page=JSON.parse(schema.textContent);Object.assign(page,{'@id':canonical+'#webpage',url:canonical,name:info[0],description:info[1]});schema.textContent=JSON.stringify(page)}catch{}}
 }
 root.addEventListener('popstate',updateMetadata);
 function write(state,replace=false){
  const next=url(state);
  if(next!==root.location.pathname+root.location.search+root.location.hash){root.history[replace?'replaceState':'pushState']({basketlab:true},'',next);updateMetadata();}
 }
 root.BasketLabRouter={read,url,write,paths};
})(window);
