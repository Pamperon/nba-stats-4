/* URL codec and History API. No data, model or DOM dependencies. */
(function(root){
 'use strict';
 const paths={home:'/',picks:'/pronostici',calendar:'/partite',finder:'/analisi-quote',stats:'/statistiche',history:'/archivio',about:'/come-funziona',news:'/notizie',single:'/analisi-singola'};
 function validDay(value){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return '';
  const day=new Date(value+'T12:00:00Z');
  return Number.isFinite(day.getTime())&&day.toISOString().slice(0,10)===value?value:'';
 }
 function read(location){
  const path=location.pathname.replace(/\/$/,'')||'/';
  const query=new URLSearchParams(location.search);
  const view=path==='/analisi-partita'?'finder':Object.keys(paths).find(k=>paths[k]===path)||'home';
  const date=validDay(query.get('data'));
  const a=query.get('trasferta'),b=query.get('casa');
  return {view,date,match:path==='/analisi-partita'&&date&&a&&b&&a.length<=80&&b.length<=80?a+' - '+b:''};
 }
 function url(state){
  const params=new URLSearchParams();
  if(state.date&&(state.view==='calendar'||state.match))params.set('data',state.date);
  let path=paths[state.view]||'/';
  if(state.match){const teams=state.match.split(/\s+-\s+|\s+vs\.?\s+/i);if(teams.length===2){path='/analisi-partita';params.set('trasferta',teams[0]);params.set('casa',teams[1]);}}
  return path+(params.size?'?'+params:'');
 }
 function write(state,replace=false){
  const next=url(state);
  if(next!==root.location.pathname+root.location.search+root.location.hash)root.history[replace?'replaceState':'pushState']({basketlab:true},'',next);
 }
 root.BasketLabRouter={read,url,write,paths};
})(window);
