/* Schedule only the data needed by the visible SPA section. */
(function(root){
 'use strict';
 const tasks=new Map();
 function view(){return document.body.dataset.hubView||root.BasketLabRouter?.read(root.location).view||'home';}
 const views={picks:['home','picks'],quotes:['finder'],home:['home']};
 function wants(name){return (views[name]||[]).includes(view());}
 function run(name,force=false){
  const task=tasks.get(name);if(!task||(!force&&!wants(name)))return Promise.resolve();
  if(task.pending)return task.pending;
  if(!force&&Date.now()<task.expires)return Promise.resolve();
  const pending=Promise.resolve().then(task.load).then(()=>{task.expires=Date.now()+task.ttl;}).finally(()=>{task.pending=null;});
  task.pending=pending;
  // A section failure must not prevent other views from opening; loaders own retry UI.
  pending.catch(()=>{});return pending;
 }
 function refresh(){for(const name of tasks.keys())if(wants(name))run(name);}
 function register(name,load,ttl=60000){tasks.set(name,{load,ttl,expires:0,pending:null});queueMicrotask(refresh);}
 document.addEventListener('basketlab:view',()=>queueMicrotask(refresh));
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
 root.BasketLabSections={register,run,wants};
})(window);
