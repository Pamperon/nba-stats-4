/* Local team identities and progressively linked content. No requests or tracking. */
(function(w){
 'use strict';const d=w.document;
 const teams=[["milwaukee-bucks-15", ["Milwaukee Bucks", "Bucks", "MIL"]], ["chicago-bulls-4", ["Chicago Bulls", "Bulls", "CHI"]], ["brooklyn-nets-17", ["Brooklyn Nets", "Nets", "BKN"]], ["indiana-pacers-11", ["Indiana Pacers", "Pacers", "IND"]], ["washington-wizards-27", ["Washington Wizards", "Wizards", "WAS"]], ["charlotte-hornets-30", ["Charlotte Hornets", "Hornets", "CHA"]], ["orlando-magic-19", ["Orlando Magic", "Magic", "ORL"]], ["toronto-raptors-28", ["Toronto Raptors", "Raptors", "TOR"]], ["miami-heat-14", ["Miami Heat", "Heat", "MIA"]], ["cleveland-cavaliers-5", ["Cleveland Cavaliers", "Cavaliers", "CLE"]], ["new-york-knicks-18", ["New York Knicks", "Knicks", "NYK"]], ["atlanta-hawks-1", ["Atlanta Hawks", "Hawks", "ATL"]], ["detroit-pistons-8", ["Detroit Pistons", "Pistons", "DET"]], ["philadelphia-76ers-20", ["Philadelphia 76ers", "76ers", "PHI"]], ["boston-celtics-2", ["Boston Celtics", "Celtics", "BOS"]], ["utah-jazz-26", ["Utah Jazz", "Jazz", "UTA"]], ["sacramento-kings-23", ["Sacramento Kings", "Kings", "SAC"]], ["la-clippers-12", ["LA Clippers", "Clippers", "LAC", "Los Angeles Clippers", "L.A. Clippers"]], ["new-orleans-pelicans-3", ["New Orleans Pelicans", "Pelicans", "NOP"]], ["phoenix-suns-21", ["Phoenix Suns", "Suns", "PHX"]], ["denver-nuggets-7", ["Denver Nuggets", "Nuggets", "DEN"]], ["dallas-mavericks-6", ["Dallas Mavericks", "Mavericks", "DAL"]], ["memphis-grizzlies-29", ["Memphis Grizzlies", "Grizzlies", "MEM"]], ["golden-state-warriors-9", ["Golden State Warriors", "Warriors", "GSW"]], ["oklahoma-city-thunder-25", ["Oklahoma City Thunder", "Thunder", "OKC"]], ["portland-trail-blazers-22", ["Portland Trail Blazers", "Trail Blazers", "POR", "Blazers"]], ["minnesota-timberwolves-16", ["Minnesota Timberwolves", "Timberwolves", "MIN"]], ["houston-rockets-10", ["Houston Rockets", "Rockets", "HOU"]], ["san-antonio-spurs-24", ["San Antonio Spurs", "Spurs", "SAS"]], ["los-angeles-lakers-13", ["Los Angeles Lakers", "Lakers", "LAL", "LA Lakers", "L.A. Lakers"]]];
 const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().replace(/\s+/g,' ').toLowerCase();
 const lookup=new Map();for(const [slug,names] of teams)for(const name of names)lookup.set(normalize(name),slug);
 const fullNames=teams.flatMap(([,names])=>names.filter(n=>n.includes(' '))).sort((a,b)=>b.length-a.length);
 const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const pattern=new RegExp('(?<![\\p{L}\\p{N}])('+fullNames.map(escape).join('|')+')(?![\\p{L}\\p{N}])','giu');
 const forbidden='a,button,select,option,textarea,input,script,style,svg,canvas,[contenteditable],summary';
 const teamContext='.player-profile-team,.pick-player-meta,.pe-player-info small,.bl-broadcast-info,.fixture-name-full,.fixture-name-short,.bl-fixture-name,.bl-game-team,.hub-calendar-team,.hub-match-team,.hub-boxscore-match-team,.hub-boxscore-team h4,.hub-match-player-team,[data-team-name]';
 function url(name){const slug=lookup.get(normalize(name));return slug?'/squadre/'+slug:'';}
 function anchor(name,href){const a=d.createElement('a');a.className='bl-team-link';a.href=href;a.dataset.blTeam='';a.textContent=name;a.setAttribute('aria-label','Apri la pagina dei '+name.trim());return a;}
 function splitPlayerRow(old){
  const box=d.createElement('div');for(const a of old.attributes)if(a.name!=='href'&&a.name!=='target')box.setAttribute(a.name,a.value);box.setAttribute('role','group');
  while(old.firstChild)box.append(old.firstChild);
  const name=box.querySelector('.pe-player-info strong');if(name){const link=d.createElement('a');link.href=old.getAttribute('href');link.className='bl-player-card-link';name.replaceWith(link);link.append(name);}
  box.addEventListener('click',e=>{if(e.target.closest('.bl-team-link'))return;old.onclick?.call(old,e);});old.replaceWith(box);
 }
 function splitFixtureButton(old){
  const actionLabel=old.getAttribute('aria-label')||'Apri partita: '+old.textContent.trim();
  const box=d.createElement('div');for(const a of old.attributes)if(!['type','aria-label'].includes(a.name))box.setAttribute(a.name,a.value);box.setAttribute('role','group');box.classList.add('bl-linked-card');
  while(old.firstChild)box.append(old.firstChild);
  const action=d.createElement('button');action.type='button';action.className='bl-card-open';action.setAttribute('aria-label',actionLabel);action.addEventListener('click',()=>old.click());box.append(action);box.addEventListener('click',e=>{if(!e.target.closest('a,button'))old.click();});old.replaceWith(box);
 }
 function enhance(root){
  if(root.nodeType===3)root=root.parentElement;if(!root?.querySelectorAll||root.closest?.('script,style,svg,canvas,select'))return;
  const fixtures='button.hub-calendar-match,button.hub-match-row,button.nba-game';
  for(const row of [...(root.matches?.(fixtures)?[root]:[]),...root.querySelectorAll(fixtures)])splitFixtureButton(row);
  for(const row of [...(root.matches?.('a.pe-player-row')?[root]:[]),...root.querySelectorAll('a.pe-player-row')])splitPlayerRow(row);
  // A replacement root was detached above; its added sibling is handled by the observer.
  if(!root.isConnected)return;
  const walker=d.createTreeWalker(root,w.NodeFilter.SHOW_TEXT);const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  for(const text of nodes){const parent=text.parentElement;if(!parent||parent.closest(forbidden)||!text.nodeValue.trim())continue;
   const value=text.nodeValue,context=parent.closest(teamContext);const href=context?url(value):'';
   if(href){if(href!==w.location.pathname)text.replaceWith(anchor(value,href));continue;}
   pattern.lastIndex=0;const matches=[...value.matchAll(pattern)];if(!matches.length)continue;const fragment=d.createDocumentFragment();let from=0,changed=false;
   for(const match of matches){const target=url(match[0]);if(!target||target===w.location.pathname)continue;fragment.append(d.createTextNode(value.slice(from,match.index)),anchor(match[0],target));from=match.index+match[0].length;changed=true;}
   if(changed){fragment.append(d.createTextNode(value.slice(from)));text.replaceWith(fragment);}
  }
  for(const img of root.querySelectorAll('.hub-match-team img,.hub-boxscore-match-team img,.hub-calendar-team img,.fixture-team .team-logo img,.bl-game-team img,.hub-premium-logo img')){if(img.closest('a,button'))continue;const side=img.closest('.hub-match-team,.hub-boxscore-match-team,.hub-calendar-team,.fixture-team,.bl-game-team,.hub-premium-logo');const href=side?.querySelector('a.bl-team-link')?.getAttribute('href')||url(img.alt);if(href&&href!==w.location.pathname){const a=anchor('',href);a.setAttribute('aria-label','Apri la pagina della squadra');img.replaceWith(a);a.append(img);}}
 }
 d.addEventListener('click',e=>{const a=e.target.closest?.('a[data-bl-team]');if(!a)return;e.stopPropagation();if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button>0)return;if(typeof w.BasketLabOpenTeam==='function'){e.preventDefault();w.BasketLabOpenTeam(a.getAttribute('href').slice('/squadre/'.length));}},true);
 const pending=new Set();let queued=false;
 const observer=new MutationObserver(records=>{for(const r of records){if(r.type==='characterData')pending.add(r.target.parentElement);else for(const n of r.addedNodes)pending.add(n.nodeType===3?n.parentElement:n);}if(!queued){queued=true;queueMicrotask(()=>{queued=false;const roots=[...pending].filter(Boolean);pending.clear();for(const root of roots)if(root.isConnected&&!(root.parentElement?.closest('a,button,svg,script,style')))enhance(root);});}});
 w.BasketLabTeamLinks={url,enhance};if(d.querySelector('main')){observer.observe(d.querySelector('main'),{childList:true,subtree:true,characterData:true});enhance(d.querySelector('main'));}
})(window);
