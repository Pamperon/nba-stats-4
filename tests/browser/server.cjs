const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(process.env.WEB_ROOT||'web');
const row={Giocatore:'Browser Fixture',Squadra:'BOS',Partita:'Boston Celtics - Atlanta Hawks',Mercato:'PTS',Scelta:'Over',Linea:19.5,Quota:1.8,'Prob. stimata %':75,'ESPN ID':'123','Stato analisi':'Valutabile (stima empirica)'};
const game={event_id:'123',away:'Boston Celtics',home:'Atlanta Hawks',upcoming:true,state:'pre',start_at:new Date(Date.now()+2*86400000).toISOString(),status:'Scheduled'};
const team=(team,wins,avg_points)=>({team,games:5,wins,losses:5-wins,avg_points,results:[{date:'2026-11-01',scored:110,allowed:100,opponent:'Fixture'}]});
const payload=url=>{
 if(url.pathname==='/api/saved/dates')return {dates:[{date:'2026-11-05'}],default_date:'2026-11-05',session_picks_enabled:true};
 if(url.pathname==='/api/saved/latest')return {date:url.searchParams.get('date'),results:[row],recommendations:{lines:[]},saved_at:'2026-11-03T13:00:00Z'};
 if(url.pathname==='/api/saved/status')return {state:'waiting',fixture_reports:[]};
 if(url.pathname==='/api/picks/session')return {date:'2026-11-03',publication_date:'2026-11-03',saved_at:'2026-11-03T13:00:00Z',results:[],recommendations:{policy:'fixed-1800-v1',lines:[]},preliminary_top5:[],preliminary_single:row,official_top5_pending:true,fixture_count:1,player_count:1,quote_count:1};
 if(url.pathname==='/api/nba/fixtures'||url.pathname==='/api/nba/publication-session')return {date:'2026-11-05',games:[game],source:'ESPN',odds_api_calls:0};
 if(url.pathname==='/api/nba/quote-coverage')return {fixtures:[row.Partita]};
 if(url.pathname==='/api/match/form')return {source:'ESPN',window_days:21,history_complete:true,teams:[team('Boston Celtics',4,110),team('Atlanta Hawks',2,100)],h2h:[],moneyline_odds:[1.8,2.1]};
 if(url.pathname==='/api/history/dates')return {dates:[{date:'2026-11-03'}]};
 if(url.pathname==='/api/history/performance')return {published:0};
 if(url.pathname==='/api/history')return {official_lines:[{...row,status:'won',actual:22}],other_lines:[],single_archive:{published:false}};
 if(url.pathname==='/api/players/teams')return {teams:[]};
 return {};
};
http.createServer((req,res)=>{
 const url=new URL(req.url,'http://127.0.0.1');
 if(url.pathname.startsWith('/api/')){
  if(req.method!=='GET'){res.writeHead(204);return res.end();}
  const delay=url.pathname==='/api/saved/latest'?1200:url.pathname==='/api/match/form'?400:40;
  return setTimeout(()=>{res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(payload(url)));},delay);
 }
 const file=url.pathname.startsWith('/static/')?url.pathname.slice(8):'index.html';
 const target=path.resolve(root,file);if(!target.startsWith(root+path.sep)){res.writeHead(403);return res.end();}
 fs.readFile(target,(error,data)=>{if(error){res.writeHead(404);return res.end();}const type={'.js':'text/javascript','.css':'text/css','.html':'text/html','.png':'image/png','.svg':'image/svg+xml','.webmanifest':'application/manifest+json'}[path.extname(target)]||'application/octet-stream';res.writeHead(200,{'Content-Type':type});res.end(data);});
}).listen(4173,'127.0.0.1');
