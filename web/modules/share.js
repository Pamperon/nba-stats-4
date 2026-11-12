/* Share only after an explicit click. No third-party SDKs or automatic requests. */
(function(w){
 'use strict';
 const d=w.document;
 const footer=d.querySelector('footer');if(footer){const share=d.createElement('button');share.type='button';share.className='bl-back bl-footer-share';share.setAttribute('data-share-page','');share.textContent='Condividi questa pagina';footer.append(share);}
 function shareURL(){const url=new URL(w.location.href);url.hash='';for(const key of [...url.searchParams.keys()])if(!['data','partita','squadra','trasferta','casa','mercato','linea','periodo','stagione','campo','competizione'].includes(key))url.searchParams.delete(key);return url.href;}
 function close(){d.getElementById('bl-share-menu')?.remove();}
 function menu(button){
  close();const url=shareURL(),title=d.title.replace(/\s*\| Basket Lab$/,'');
  const box=d.createElement('dialog');box.id='bl-share-menu';box.className='bl-share-menu';box.setAttribute('aria-label','Condividi questa pagina');
  const heading=d.createElement('h2');heading.textContent='Condividi';box.append(heading);
  const links=d.createElement('div');links.className='bl-share-links';
  const destinations=[['WhatsApp','https://wa.me/?text='+encodeURIComponent(title+' '+url)],['Telegram','https://t.me/share/url?url='+encodeURIComponent(url)+'&text='+encodeURIComponent(title)],['Facebook','https://www.facebook.com/sharer/sharer.php?u='+encodeURIComponent(url)],['X','https://twitter.com/intent/tweet?url='+encodeURIComponent(url)+'&text='+encodeURIComponent(title)]];
  for(const [name,href] of destinations){const a=d.createElement('a');a.textContent=name;a.href=href;a.target='_blank';a.rel='noopener noreferrer';links.append(a);}
  box.append(links);const dismiss=d.createElement('button');dismiss.type='button';dismiss.className='bl-back';dismiss.textContent='Chiudi';dismiss.onclick=()=>{box.close?.();close();button.focus();};box.append(dismiss);
  box.addEventListener('click',e=>{if(e.target===box){const rect=box.getBoundingClientRect();if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom){box.close?.();close();button.focus();}}});
  box.addEventListener('close',()=>{close();button.focus()});d.body.append(box);
  if(typeof box.showModal==='function')box.showModal();else box.setAttribute('open','');dismiss.focus();
 }
 d.addEventListener('click',async e=>{const button=e.target.closest('[data-share-page]');if(!button)return;
  if(w.navigator.share){try{await w.navigator.share({title:d.title,url:shareURL()});return;}catch(error){if(error.name==='AbortError')return;}}
  menu(button);
 });
 w.addEventListener('popstate',close);d.addEventListener('basketlab:view',close);
})(window);
