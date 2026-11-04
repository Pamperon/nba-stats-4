/* Player directory and personal-page navigation. Uses saved quotes and the existing ESPN engine. */
(function(w){
'use strict';
const d=w.document,$=id=>d.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={PTS:'Punti',REB:'Rimbalzi',AST:'Assist'},norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(),slug=(name,id)=>norm(name).replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'-'+id;
const panel=d.createElement('section');panel.id='players-explorer';panel.hidden=true;
panel.innerHTML='<header class="pe-heading"><div><p class="pe-eyebrow">BASKET LAB</p><h1>Giocatori</h1><p>Statistiche, linee e quote NBA</p></div></header><div class="pe-controls"><label class="pe-search">Cerca un giocatore<input id="pe-search" type="search" placeholder="Nome del giocatore…" autocomplete="off"></label><div class="bl-segments" role="group" aria-label="Mercato giocatori">'+Object.entries(labels).map(([k,v])=>'<button type="button" data-pe-market="'+k+'" aria-pressed="'+(k==='PTS')+'">'+v+'</button>').join('')+'</div><div class="pe-filter-row"><label>Partita<select id="pe-match"><option value="">Tutte le partite</option></select></label><label>Squadra<select id="pe-team"><option value="">Tutte le squadre</option></select></label></div></div><div class="pe-list-heading"><p id="pe-status" role="status"></p><button id="pe-reset" type="button">Ripristina</button></div><div id="pe-list"></div><button id="pe-more" type="button" hidden>Mostra altri giocatori</button>';
$('app')?.before(panel);
const personal=d.createElement('div');personal.id='pe-personal-heading';personal.innerHTML='<a href="/giocatori" data-hub="stats" class="bl-back">‹ Tutti i giocatori</a><button id="pe-share" type="button" class="bl-back">Copia link</button><p id="pe-share-status" role="status"></p>';
$('player')?.prepend(personal);
const quotes=d.createElement('section');quotes.id='pe-player-quotes';quotes.className='pe-quotes';quotes.setAttribute('aria-label','Quote del giocatore');
$('player-visual')?.after(quotes);
const profile=$('player-profile'),averages=$('player-season-stats');if(profile&&averages)profile.append(averages);
const periods=d.querySelector('.bl-window-tabs'),advanced=d.querySelector('.bl-player-advanced');
if(periods&&advanced){$('player-visual').after(periods);periods.after(advanced);advanced.after(quotes);}

let payload=null,pending=null,loadedAt=0,market='PTS',limit=30,request=0,selected=null,restoring=false,directoryScroll=0,catalog=null,quotesUnavailable=false;
const api={detailOpen:false,route:()=>selected?{player:slug(selected.name,selected.id),filters:filters()}: {},show:showDirectory,openRoute};w.BasketLabPlayers=api;
function filters(){return {market:$('stat')?.value,line:$('line')?.value,window:$('playerwindow')?.value,season:$('playerseason')?.value,venue:$('player-venue')?.value,mode:$('playermode')?.value};}
function changed(){d.dispatchEvent(new CustomEvent('basketlab:player-route'));}
async function load(){
 if(payload&&Date.now()-loadedAt<60000)return payload;
 if(!pending)pending=fetch('/api/players/explorer').then(r=>{if(!r.ok)throw Error('Quote non disponibili');return r.json()}).then(p=>{if(!Array.isArray(p.rows))throw Error('Dati non validi');payload=p;quotesUnavailable=false;loadedAt=Date.now();updateOptions();renderQuotes();return p;}).finally(()=>pending=null);
 return pending;
}
const teamKey=name=>norm(name).replace(/[^a-z0-9]/g,'').replace(/^laclippers$/,'losangelesclippers');
function fixtureTeams(fixture){return String(fixture||'').split(/\s+-\s+|\s+vs\.?\s+/i).map(s=>s.trim()).filter(Boolean);}
function updateOptions(){
 const match=$('pe-match'),previousMatch=match.value;
 const fixtures=[...new Set((payload?.rows||[]).map(r=>r.Partita).filter(Boolean))].sort();
 match.innerHTML='<option value="">Tutte le partite</option>'+fixtures.map(v=>'<option>'+esc(v)+'</option>').join('');match.value=fixtures.includes(previousMatch)?previousMatch:'';
 const node=$('pe-team'),previous=node.value;
 const teams=match.value?fixtureTeams(match.value):[...new Set([...(payload?.rows||[]).map(r=>r.Squadra),...(catalog?catalog.map(p=>p.team):[])].filter(Boolean))].sort();
 node.innerHTML='<option value="">'+(match.value?'Entrambe le squadre':'Tutte le squadre')+'</option>'+teams.map(v=>'<option>'+esc(v)+'</option>').join('');
 node.value=teams.find(t=>teamKey(t)===teamKey(previous))||'';
}
async function showDirectory(){
 api.detailOpen=false;selected=null;panel.hidden=false;$('pe-share-status').textContent='';const token=++request;
 try{$('pe-status').textContent='Caricamento giocatori…';await load();if(token!==request||api.detailOpen)return;await render();w.scrollTo(0,directoryScroll);}
 catch{if(token!==request)return;quotesUnavailable=true;payload=payload||{rows:[],logs:{}};updateOptions();await render();}
}
function chooseRow(rows){return [...rows].sort((a,b)=>Math.abs(Number(a.Quota)-1.9)-Math.abs(Number(b.Quota)-1.9)||Number(a.Linea)-Number(b.Linea))[0];}
function spark(games,line){const values=(games||[]).filter(g=>g[market]!=null&&g[market]!==''&&Number.isFinite(Number(g[market]))).slice(0,10).reverse();if(!values.length)return '<span class="pe-spark-empty">Storico nella scheda ›</span>';const max=Math.max(1,line,...values.map(g=>Number(g[market])));return '<span class="pe-spark" role="img" aria-label="Ultime '+values.length+' partite: '+values.map(g=>Number(g[market])).join(', ')+'"><span class="pe-spark-line" style="bottom:'+Math.min(100,line/max*100)+'%"></span>'+values.map(g=>'<i class="'+(Number(g[market])>line?'over':Number(g[market])===line?'equal':'under')+'" style="height:'+Math.max(2,Number(g[market])/max*100)+'%"></i>').join('')+'</span>';}
async function render(){
 const token=++request,q=norm($('pe-search').value.trim()),team=$('pe-team').value,fixture=$('pe-match').value;let unpricedCount=0;
 if(!payload)return;
 const groups=new Map();for(const row of payload.rows){if(row.Mercato!==market||team&&teamKey(row.Squadra)!==teamKey(team)||fixture&&row.Partita!==fixture)continue;const name=row.Giocatore||'';if(q&&!norm(name).includes(q)&&!norm(name.split(',').reverse().join(' ')).includes(q))continue;const key=String(row['ESPN ID']||name);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
 const rows=[...groups.values()].map(chooseRow).sort((a,b)=>String(a.Giocatore).split(',').reverse().join(' ').localeCompare(String(b.Giocatore).split(',').reverse().join(' '),'it'));
 const list=$('pe-list'),cards=[];list.replaceChildren();
 for(const row of rows){const name=String(row.Giocatore).split(',').reverse().map(s=>s.trim()).join(' '),id=String(row['ESPN ID']||'');const link=d.createElement('a');link.className='pe-player-row';link.href=/^\d+$/.test(id)?'/giocatori/'+slug(name,id):'/giocatori';link.innerHTML='<div class="pe-player-face">'+(/^\d+$/.test(id)?'<img src="/api/players/headshot/'+id+'" alt="" loading="lazy">':'')+'</div><div class="pe-player-info"><strong>'+esc(name)+'</strong><small>'+esc(row.Squadra)+'</small><span>'+esc(row.Scelta)+' '+esc(row.Linea)+' '+labels[market]+' <b>'+Number(row.Quota).toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})+'</b></span></div>'+spark(payload.logs?.[row.Giocatore],Number(row.Linea))+'<span class="pe-row-arrow">›</span>';link.onclick=event=>{if(event.ctrlKey||event.metaKey||event.shiftKey)return;event.preventDefault();directoryScroll=w.scrollY;w.BasketLabPlayerEngine.open(row);};cards.push(link);}
 {
  try{
   catalog=await w.BasketLabPlayerEngine.directory();if(token!==request)return;updateOptions();
   const already=new Set(rows.map(r=>String(r['ESPN ID']))),names=new Set(rows.map(r=>norm(String(r.Giocatore).split(',').reverse().join(' ').trim())));
   const participants=fixtureTeams(fixture).map(teamKey);
   const other=catalog.filter(p=>(!q||norm(p.name).includes(q))&&!already.has(String(p.id))&&!names.has(norm(p.name))&&(!team||teamKey(p.team)===teamKey(team))&&(!fixture||participants.includes(teamKey(p.team))));
   unpricedCount=other.length;
   for(const p of other){
    const link=d.createElement('a');link.className='pe-player-row pe-catalog-row';link.href='/giocatori/'+slug(p.name,p.id);
    const id=String(p.id);link.innerHTML='<div class="pe-player-face">'+(/^\d+$/.test(id)?'<img src="/api/players/headshot/'+id+'" alt="" loading="lazy">':'')+'</div><div class="pe-player-info"><strong>'+esc(p.name)+'</strong><small>'+esc(p.team)+'</small><span class="pe-unpriced-label">Statistiche disponibili · Senza quota</span></div><span class="pe-spark-empty">Apri statistiche</span><span class="pe-row-arrow">›</span>';
    link.onclick=e=>{if(e.ctrlKey||e.metaKey||e.shiftKey)return;e.preventDefault();directoryScroll=w.scrollY;w.BasketLabPlayerEngine.open({'ESPN ID':p.id,Giocatore:p.name,Squadra:p.team,Mercato:market});};cards.push(link);
   }
  }catch{if(token!==request)return;showCards(list,cards);$('pe-status').textContent='Catalogo NBA temporaneamente non disponibile. Puoi riprovare la ricerca.';return;}
 }
 showCards(list,cards);
 $('pe-status').textContent=(rows.length+unpricedCount)+' giocatori · '+rows.length+' con quote'+(unpricedCount?' · '+unpricedCount+' senza quota':'')+(payload.date?' · '+payload.date.split('-').reverse().join('/'):'')+(quotesUnavailable?' · Quote non disponibili: statistiche NBA accessibili':'');$('pe-more').hidden=rows.length+unpricedCount<=limit;
 if(!list.children.length)list.innerHTML='<p class="pe-empty">Nessun giocatore per questi filtri. Cerca un nome oppure cambia mercato.</p>';
}
function showCards(list,cards){
 cards.sort((a,b)=>(a.querySelector('.pe-player-info strong')?.textContent||'').localeCompare(b.querySelector('.pe-player-info strong')?.textContent||'','it'));
 list.replaceChildren(...cards.slice(0,limit));
}
function renderQuotes(){
 if(!api.detailOpen||!selected||!payload)return;
 const playerRows=payload.rows.filter(r=>String(r['ESPN ID'])===selected.id||norm(String(r.Giocatore).split(',').reverse().join(' '))===norm(selected.name));
 const rows=playerRows.filter(r=>r.Mercato===$('stat').value);
 const fixtures=[...new Set(playerRows.map(r=>r.Partita))];
 quotes.innerHTML='<div class="pe-quotes-heading"><h3>Linee e quote Bet365</h3><small>'+(payload.saved_at?'Aggiornamento '+new Date(payload.saved_at).toLocaleString('it-IT',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'')+'</small></div>'+(fixtures.length?'<div class="pe-quote-fixture">'+fixtures.map(match=>w.BasketLabPlayerEngine.fixture(match)).join('')+'</div>':'');
 for(const strip of quotes.querySelectorAll('.pick-fixture[data-match]')){
  const entries=[...strip.querySelectorAll('.fixture-team-name')].map(node=>[node,node.querySelector('.fixture-name-full')?.textContent||node.textContent]);
  w.BasketLabVenue?.mark(entries,strip.dataset.match,payload.date||new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Rome',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()),false);
 }
 if(!rows.length){quotes.innerHTML+='<p>Nessuna quota disponibile per questo mercato nelle prossime partite. Puoi comunque analizzare lo storico.</p>';return;}
 const table=d.createElement('div');table.className='pe-quote-options';for(const row of [...rows].sort((a,b)=>Number(a.Linea)-Number(b.Linea)||String(a.Scelta).localeCompare(String(b.Scelta)))){const button=d.createElement('button');button.type='button';const isOver=!/^under$/i.test(row.Scelta||'');button.className='pe-quote-option';button.setAttribute('aria-pressed',String(Number($('line').value)===Number(row.Linea)));button.innerHTML='<span>'+esc(row.Scelta)+' '+esc(row.Linea)+'</span><strong>'+Number(row.Quota).toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})+'</strong>';button.onclick=()=>{const line=$('line'),val=String(row.Linea);if(![...line.options].some(o=>o.value===val))line.add(new Option(val,val));line.value=val;line.dispatchEvent(new Event('change',{bubbles:true}));};if(!isOver)button.title='Il grafico mostra il superamento della linea (Over).';table.append(button);}quotes.append(table);
}
d.addEventListener('basketlab:player-open',event=>{++request;api.detailOpen=true;panel.hidden=true;const row=event.detail?.row;if(row){selected={id:String(row['ESPN ID']||''),name:String(row.Giocatore||'').split(',').reverse().map(s=>s.trim()).join(' ')};}load().catch(()=>{quotes.innerHTML='<p>Quote temporaneamente non disponibili.</p>';});});
d.addEventListener('basketlab:player-state',event=>{const p=event.detail;if(!p?.id)return;selected={...p,id:String(p.id)};api.detailOpen=true;panel.hidden=true;
 for(const b of d.querySelectorAll('[data-player-window]')){const n=b.dataset.playerWindow,summary=p.windows?.[n];b.dataset.hitRate=summary?.total?(100*summary.hits/summary.total<50?'low':'high'):'unknown';b.innerHTML='<span>'+(n==='all'?'Stagione':'Ultime '+n)+'</span>'+(summary?'<small>'+(summary.total?Math.round(100*summary.hits/summary.total)+'%':'—')+'</small>':'');}
 renderQuotes();if(!restoring)changed();});
async function openRoute(route){
 api.detailOpen=true;panel.hidden=true;const token=++request;restoring=true;
 for(const tab of d.querySelectorAll('.tab'))tab.hidden=tab.id!=='player';
 $('player-profile').hidden=true;$('player-summary').replaceChildren();$('chart').replaceChildren();$('player-trends').replaceChildren();$('player-visual').hidden=true;quotes.replaceChildren();$('player-status').textContent='Caricamento della scheda giocatore…';
 try{const id=route.player.match(/-(\d+)$/)?.[1];selected={id,name:route.player.replace(/-\d+$/,'').replace(/-/g,' ')};const directory=await w.BasketLabPlayerEngine.directory();if(token!==request)return;const player=directory.find(p=>String(p.id)===id);if(!player)throw Error('Giocatore non trovato');const f=route.filters||{};await w.BasketLabPlayerEngine.open({'ESPN ID':player.id,Giocatore:player.name,Squadra:player.team,Mercato:labels[f.market]?f.market:'PTS',...(f.line&&Number.isFinite(Number(f.line))&&Number(f.line)>=0&&Number(f.line)<=100?{Linea:Number(f.line)}:{})});
 // Selection loading uses its own cancellation checks. Only restore if this is still the URL's athlete.
 if(selected?.id!==id)return;
 for(const [key,control] of [['season','playerseason'],['window','playerwindow'],['venue','player-venue'],['mode','playermode']]){const node=$(control);if(f[key]&&[...node.options].some(o=>o.value===f[key])){node.value=f[key];node.dispatchEvent(new Event('change',{bubbles:true}));}}
 }catch(error){$('player-status').textContent=error.message||'Scheda non disponibile';}
 finally{restoring=false;changed();}
}
$('pe-search').oninput=()=>{limit=30;render();};$('pe-team').onchange=()=>{limit=30;render();};$('pe-match').onchange=()=>{limit=30;updateOptions();render();};
for(const b of panel.querySelectorAll('[data-pe-market]'))b.onclick=()=>{market=b.dataset.peMarket;limit=30;for(const x of panel.querySelectorAll('[data-pe-market]'))x.setAttribute('aria-pressed',String(x===b));render();};
$('pe-reset').onclick=()=>{$('pe-search').value='';$('pe-team').value='';$('pe-match').value='';limit=30;updateOptions();render();};$('pe-more').onclick=()=>{limit+=30;render();};
$('pe-share').onclick=async()=>{try{await navigator.clipboard.writeText(w.location.href);$('pe-share-status').textContent='Link copiato';}catch{$('pe-share-status').textContent='Puoi copiare l’indirizzo dalla barra del browser.';}};
})(window);
