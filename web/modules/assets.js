/* Named local UI modules. One download per asset; failures remain retryable. */
(function(root){
 'use strict';
 const files={'single-analysis':'single-analysis.js?v=lab-names-18','archive-view':'archive-view.js?v=lab-names-18','boxscore-view':'boxscore-view.js?v=player-panel-1','match-players':'match-players.js?v=3'};
 let versions={};try{versions=JSON.parse(document.getElementById('bl-asset-versions')?.textContent||'{}');}catch{}
 const pending=new Map();
 function load(name){
  if(!Object.hasOwn(files,name))return Promise.reject(new Error('Unknown UI module'));
  if(pending.has(name))return pending.get(name);
  const task=new Promise((resolve,reject)=>{
   const script=document.createElement('script');script.src=versions[name]||'/static/modules/'+files[name];script.async=true;
   script.onload=()=>resolve();script.onerror=()=>{pending.delete(name);script.remove();reject(new Error('Interfaccia temporaneamente non disponibile'));};
   document.head.append(script);
  });pending.set(name,task);return task;
 }
 function style(name){
  if(name!=='detail-sheets'||document.getElementById('bl-detail-styles'))return;
  const link=document.createElement('link');link.id='bl-detail-styles';link.rel='stylesheet';link.href=versions[name]||'/static/detail-sheets.css?v=1';
  link.onerror=()=>link.remove();document.head.append(link);
 }
 root.BasketLabAssets={load,style};
})(window);
