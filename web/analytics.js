/* Optional GA4 measurement. No Google requests before analytics consent. */
(() => {
 'use strict';
 const id='G-ZV8770T2E7',key='bl-analytics-consent-v1';
 let enabled=false,loaded=false,lastPath='',banner;
 const blocked=navigator.doNotTrack==='1'||navigator.globalPrivacyControl;
 window.dataLayer=window.dataLayer||[];
 function gtag(){window.dataLayer.push(arguments);}
 window.gtag=gtag;
 gtag('consent','default',{analytics_storage:'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
 function cleanURL(){return location.origin+location.pathname;}
 function page(){
  if(!enabled||lastPath===location.pathname)return;
  lastPath=location.pathname;
  gtag('event','page_view',{page_location:cleanURL(),page_title:document.title,page_referrer:document.referrer?new URL(document.referrer).origin:''});
 }
 function activate(){
  if(blocked)return;
  enabled=true;window['ga-disable-'+id]=false;
  gtag('consent','update',{analytics_storage:'granted'});
  if(!loaded){
   loaded=true;gtag('js',new Date());
   gtag('config',id,{send_page_view:false,page_location:cleanURL(),allow_google_signals:false,allow_ad_personalization_signals:false,ignore_referrer:false});
   const tag=document.createElement('script');tag.async=true;tag.src='https://www.googletagmanager.com/gtag/js?id='+id;document.head.append(tag);
  }
  lastPath='';page();
 }
 function removeCookies(){
  for(const cookie of document.cookie.split(';')){
   const name=cookie.split('=')[0].trim();if(!/^_ga(?:_|$)/.test(name))continue;
   for(const domain of ['',location.hostname,'.'+location.hostname])
    document.cookie=name+'=; Max-Age=0; path=/'+(domain?'; domain='+domain:'')+'; SameSite=Lax';
  }
 }
 function choose(accepted){
  try{localStorage.setItem(key,JSON.stringify({accepted,at:Date.now()}));}catch{}
  if(accepted)activate();
  else {enabled=false;window['ga-disable-'+id]=true;gtag('consent','update',{analytics_storage:'denied'});removeCookies();}
  banner.hidden=true;
 }
 function show(){
  if(!banner){
   banner=document.createElement('section');banner.setAttribute('role','region');banner.setAttribute('aria-label','Preferenze statistiche');
   banner.style.cssText='position:fixed;bottom:82px;left:12px;right:12px;max-width:560px;margin:auto;padding:16px;background:#14243a;color:#fff;border:1px solid #63758c;border-radius:14px;box-shadow:0 8px 32px #0008;z-index:10000;font:14px/1.5 system-ui';
   banner.innerHTML='<strong>Statistiche di Basket Lab</strong><p style="margin:8px 0">Con il tuo consenso usiamo Google Analytics e cookie per misurare visite e pagine consultate. Puoi rifiutare e continuare a usare il sito. <a href="/come-funziona" style="color:#ffb05e">Informazioni</a></p><div style="display:flex;gap:12px"><button type="button" data-choice="no">Rifiuta</button><button type="button" data-choice="yes">Accetta statistiche</button></div>';
   for(const button of banner.querySelectorAll('button'))button.style.cssText='flex:1;padding:10px;border:1px solid #8495ab;border-radius:8px;background:#14243a;color:white;cursor:pointer;font:inherit';
   banner.querySelector('[data-choice=no]').onclick=()=>choose(false);
   banner.querySelector('[data-choice=yes]').onclick=()=>choose(true);
   document.body.append(banner);
  }
  banner.hidden=false;
 }
 const control=document.createElement('button');control.type='button';control.textContent='Preferenze statistiche';control.style.cssText='background:none;color:inherit;border:0;text-decoration:underline;padding:12px;cursor:pointer;font:inherit';
 control.onclick=show;document.querySelector('footer')?.append(control);
 let saved;try{saved=JSON.parse(localStorage.getItem(key));}catch{}
 if(saved&&Date.now()-saved.at<180*86400000){if(saved.accepted&&!blocked)activate();}
 else if(!blocked)show();
 const push=history.pushState,replace=history.replaceState;
 history.pushState=function(...args){const result=push.apply(this,args);setTimeout(page,0);return result;};
 history.replaceState=function(...args){const result=replace.apply(this,args);setTimeout(page,0);return result;};
 window.addEventListener('popstate',()=>setTimeout(page,0));
})();
