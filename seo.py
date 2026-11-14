"""Public page metadata and sitemap. Never calls an external data provider."""
import html
import hashlib
import json
import logging
import re
import time
import unicodedata
from functools import lru_cache
from pathlib import Path

SITE = 'https://basketlab.it'
PAGES = {
    '/': ('Basket Lab | Statistiche e analisi NBA', 'Statistiche NBA, calendario, risultati e classifiche. Esplora squadre e giocatori, confronta punti, rimbalzi e assist con grafici e dati delle partite. Scopri le analisi, i pronostici e le scelte quotidiane di Basket Lab.'),
    '/giocatori': ('Statistiche giocatori NBA: punti, rimbalzi e assist | Basket Lab', 'Esplora i giocatori NBA: statistiche, medie, grafici delle prestazioni e frequenze su punti, rimbalzi e assist, anche senza quote disponibili.'),
    '/nba': ('NBA: calendario, risultati e classifiche | Basket Lab', 'Calendario e classifiche NBA, risultati delle partite e schede delle squadre con rose e statistiche.'),
    '/nba/classifica': ('Classifica NBA: Eastern e Western Conference | Basket Lab', 'Classifiche NBA aggiornate: vittorie, sconfitte, percentuali e schede di tutte le squadre.'),
    '/partite': ('Calendario e risultati NBA | Basket Lab', 'Consulta il calendario NBA, gli orari italiani, i risultati e le analisi delle partite con i dati delle squadre e dei giocatori.'),
    '/pronostici': ('Pronostici NBA e Scelte del Lab | Basket Lab', 'Le Scelte del Lab e la Singola del giorno: analisi delle statistiche NBA, probabilità stimate e selezioni ufficializzate alle 18.'),
    '/analisi-quote': ('Quote giocatori NBA: punti, rimbalzi e assist | Basket Lab', 'Esplora linee e quote dei giocatori NBA per punti, rimbalzi e assist, con filtri per partita, giocatore e mercato.'),
    '/archivio': ('Archivio esiti dei pronostici NBA | Basket Lab', 'Consulta le selezioni NBA pubblicate da Basket Lab e i loro esiti verificati sui risultati delle partite.'),
    '/notizie': ('Notizie NBA e basket in italiano | Basket Lab', 'Le notizie NBA e di basket in italiano: aggiornamenti, titoli e collegamenti agli articoli delle fonti originali.'),
    '/come-funziona': ('Come funziona il modello statistico NBA | Basket Lab', 'Scopri il metodo Basket Lab: dati utilizzati, stime di probabilità, criteri di selezione, pubblicazione e verifica degli esiti.'),
    '/analisi-singola': ('Analisi della Singola del giorno NBA | Basket Lab', 'Approfondisci la Singola del giorno con statistiche del giocatore, grafici delle prestazioni e motivazioni della selezione.'),
}
NAV_PATHS = dict(home='/', picks='/pronostici', calendar='/nba', finder='/analisi-quote', stats='/giocatori', history='/archivio', about='/come-funziona', news='/notizie', single='/analisi-singola')


def player_slug(name, identifier):
    name = unicodedata.normalize('NFD', str(name))
    name = ''.join(c for c in name if not unicodedata.combining(c)).lower()
    return re.sub('[^a-z0-9]+', '-', name).strip('-') + '-' + str(identifier)


@lru_cache(maxsize=2)
def _directory(bucket):
    try:
        import storage
        rows = storage.cache_read('nba:player-directory:v1', max_age_hours=48)
        return tuple(p for p in (rows or []) if isinstance(p, dict)
                     and re.fullmatch(r'\d{1,12}', str(p.get('id', '')))
                     and isinstance(p.get('name'), str) and p['name'].strip())
    except Exception:
        logging.getLogger(__name__).warning('Saved player directory unavailable for SEO')
        return ()


def saved_players():
    return _directory(int(time.time() // 300))


def metadata(path, players=()):
    path = path.rstrip('/') or '/'
    if path in PAGES:
        return (*PAGES[path], SITE + path, 'index,follow')
    team_match = re.fullmatch(r'/squadre/[a-z0-9-]+-(\d{1,8})', path)
    if team_match:
        from nba_teams import TEAMS
        name = TEAMS.get(team_match[1])
        if name:
            return name + ': rosa, calendario e statistiche NBA | Basket Lab', 'Classifica, prossime partite, risultati e rosa dei ' + name + '.', SITE + '/squadre/' + player_slug(name, team_match[1]), 'index,follow'
    match = re.fullmatch(r'/giocatori/([a-z0-9-]+)-(\d{1,12})', path)
    if match:
        player = next((p for p in players if str(p['id']) == match[2]), None)
        name = player['name'] if player else match[1].replace('-', ' ').title()
        canonical = '/giocatori/' + player_slug(name, match[2]) if player else path
        title = name + ': statistiche NBA e grafici | Basket Lab'
        description = f'Statistiche NBA di {name}: punti, rimbalzi, assist, medie e grafici delle ultime partite. Consulta le linee disponibili e le frequenze osservate.'
        return title, description, SITE + canonical, 'index,follow'
    return 'Analisi partita NBA | Basket Lab', 'Statistiche e analisi delle partite NBA.', SITE + '/partite', 'noindex,follow'


def crawlable_navigation(document):
    def block(match):
        def link(button):
            attrs, body = button.groups()
            view = re.search(r'data-hub="([a-z]+)"', attrs)
            if not view or view[1] not in NAV_PATHS:
                return button[0]
            attrs = re.sub(r'\s+type="button"', '', attrs)
            return '<a href="' + NAV_PATHS[view[1]] + '"' + attrs + '>' + body + '</a>'
        return re.sub(r'<button([^>]*\bdata-hub="[a-z]+"[^>]*)>(.*?)</button>', link, match[0], flags=re.S)
    for pattern in (r'<aside class="hub-sidebar".*?</aside>', r'<nav class="hub-mobile-bar".*?</nav>', r'<nav aria-label="Menu Basket Lab".*?</nav>'):
        document = re.sub(pattern, block, document, flags=re.S)
    return document


@lru_cache(maxsize=128)
def _asset_version(asset, modified, size):
    return hashlib.sha256((Path('web') / asset).read_bytes()).hexdigest()[:12]


def asset_version(asset):
    """Fingerprint virtual bundles too, including ordered source membership."""
    root = Path('web')
    manifest = json.loads((root / 'bundles.json').read_text())
    sources = manifest.get(asset, [asset])
    versions = []
    for source in sources:
        file = root / source
        stat = file.stat()
        versions.append(source + ':' + _asset_version(source, stat.st_mtime_ns, stat.st_size))
    return hashlib.sha256('\n'.join(versions).encode()).hexdigest()[:12]


@lru_cache(maxsize=128)
def _saved_log(team_id, athlete_id, season, bucket):
    try:
        import storage
        # These are dated historical results, not live values. Retain a saved
        # table between player visits; the interactive app still refreshes it.
        payload = storage.cache_read('nba:log:final-v4:' + team_id + ':' + athlete_id + ':' + season, max_age_hours=168)
        return payload.get('games', []) if isinstance(payload, dict) else []
    except Exception:
        return []


def initial_content(path, players):
    """Progressive HTML for people and crawlers; no remote provider requests."""
    from nba_teams import TEAMS
    esc = lambda value: html.escape(str(value), quote=True)
    link = lambda url, label: '<a href="' + esc(url) + '">' + esc(label) + '</a>'
    team_links = lambda: '<ul>' + ''.join('<li>' + link('/squadre/' + player_slug(name, tid), name) + '</li>' for tid, name in sorted(TEAMS.items(), key=lambda item: item[1])) + '</ul>'
    title, description, _, _ = metadata(path, players)
    body = '<h1>' + esc(title.split(' | ')[0]) + '</h1><p>' + esc(description) + '</p>'
    match = re.fullmatch(r'/giocatori/[a-z0-9-]+-(\d{1,12})', path)
    player = next((p for p in players if str(p['id']) == match[1]), None) if match else None
    team_match = re.fullmatch(r'/squadre/[a-z0-9-]+-(\d{1,8})', path)
    if player:
        tid = str(player.get('team_id', ''))
        if tid in TEAMS:
            body += '<p>Squadra: ' + link('/squadre/' + player_slug(TEAMS[tid], tid), TEAMS[tid]) + '</p>'
        body += '<p>Confronta punti, rimbalzi e assist nelle ultime 5, 10, 20 e 30 partite. I grafici permettono di distinguere le prestazioni recenti dalle medie su un periodo più ampio.</p>'
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo('Europe/Rome'))
        season = str(now.year if now.month >= 10 else now.year - 1)
        games = _saved_log(tid, str(player['id']), season, int(time.time() // 300)) if tid in TEAMS else []
        if games:
            body += '<h2>Ultime prestazioni disponibili</h2><table><caption>Stagione ' + season + '/' + str(int(season) + 1)[-2:] + ' · Dati ESPN salvati</caption><thead><tr><th>Data</th><th>Partita</th><th>Punti</th><th>Rimbalzi</th><th>Assist</th></tr></thead><tbody>'
            for game in sorted(games, key=lambda g: str(g.get('GAME_DATE', '')), reverse=True)[:10]:
                body += '<tr>' + ''.join('<td>' + esc(game.get(key, '—')) + '</td>' for key in ('GAME_DATE', 'MATCHUP', 'PTS', 'REB', 'AST')) + '</tr>'
            body += '</tbody></table>'
        body += '<p>' + link('/giocatori', 'Tutti i giocatori NBA') + '</p>'
        teammates = [p for p in players if str(p.get('team_id', '')) == tid and p['id'] != player['id']][:8]
        if teammates:
            body += '<h2>Altri giocatori della squadra</h2><ul>' + ''.join('<li>' + link('/giocatori/' + player_slug(p['name'], p['id']), p['name']) + '</li>' for p in teammates) + '</ul>'
    elif team_match:
        tid = team_match[1]
        roster = [p for p in players if str(p.get('team_id', '')) == tid]
        if roster:
            body += '<h2>Giocatori dei ' + esc(TEAMS[tid]) + '</h2><ul>' + ''.join('<li>' + link('/giocatori/' + player_slug(p['name'], p['id']), p['name']) + '</li>' for p in roster) + '</ul>'
        body += '<p>' + link('/nba/classifica', 'Classifica NBA') + ' · ' + link('/nba', 'Calendario e risultati NBA') + '</p>'
    elif path == '/giocatori':
        body += '<p>Scegli un giocatore per consultare punti, rimbalzi, assist e andamento delle prestazioni. I filtri consentono di confrontare periodi diversi e partite in casa o in trasferta.</p><ul>'
        body += ''.join('<li>' + link('/giocatori/' + player_slug(p['name'], p['id']), p['name']) + ' — ' + esc(p.get('team', '')) + '</li>' for p in players) + '</ul>'
    elif path in ('/nba', '/nba/classifica', '/partite'):
        body += '<p>Il calendario mostra le date e gli orari italiani delle partite. Le classifiche separano Eastern e Western Conference; ogni squadra ha una scheda con prossimi incontri, risultati recenti e rosa.</p><p>' + link('/nba', 'Calendario NBA') + ' · ' + link('/nba/classifica', 'Classifica NBA') + '</p><h2>Le 30 squadre NBA</h2>' + team_links()
    elif path == '/pronostici':
        body += '<p>Le selezioni sono in anteprima prima delle 18 e diventano ufficiali alla pubblicazione serale. Le probabilità sono stime del modello, non garanzie di risultato.</p><p>' + link('/archivio', 'Verifica gli esiti delle selezioni precedenti') + ' · ' + link('/come-funziona', 'Scopri il metodo del Lab') + '</p>'
    elif path == '/archivio':
        body += '<p>Consulta le selezioni per giornata e confronta Singola e Top 10. Gli esiti distinguono le scelte centrate, non centrate, i giocatori che non hanno giocato e i risultati ancora da verificare.</p>'
    elif path == '/come-funziona':
        body += '<p>Basket Lab confronta le prestazioni NBA attraverso punti, rimbalzi, assist e minuti giocati. Le frequenze storiche descrivono ciò che è accaduto nel campione selezionato; le probabilità del modello sono stime e possono differire dai risultati futuri.</p>'
    body += '<nav aria-label="Approfondimenti NBA">' + link('/giocatori', 'Statistiche giocatori') + ' · ' + link('/nba/classifica', 'Squadre e classifica') + ' · ' + link('/come-funziona', 'Come funziona Basket Lab') + '</nav>'
    return '<section id="bl-initial-content" class="bl-panel" aria-label="Contenuti della pagina">' + body + '</section>'


def render(path, players=None):
    if players is None:
        players = saved_players() if path.startswith(('/giocatori', '/squadre/')) else ()
    title, description, canonical, robots = metadata(path, players)
    document = Path('web/index.html').read_text()
    document = re.sub(r'<title>.*?</title>', '<title>' + html.escape(title) + '</title>', document, count=1)
    values = {'name="description"': description, 'property="og:title"': title,
              'property="og:description"': description, 'property="og:url"': canonical,
              'name="twitter:title"': title, 'name="twitter:description"': description}
    for attribute, value in values.items():
        document = re.sub(r'(<meta ' + attribute + r' content=")[^"]*', lambda m: m[1] + html.escape(value, quote=True), document, count=1)
    document = re.sub(r'(<link rel="canonical" href=")[^"]*', lambda m: m[1] + html.escape(canonical, quote=True), document, count=1)
    page = {'@context':'https://schema.org', '@type':'WebPage', '@id':canonical+'#webpage', 'url':canonical, 'name':title, 'description':description, 'inLanguage':'it-IT', 'isPartOf':{'@type':'WebSite','name':'Basket Lab','url':SITE+'/'}}
    safe_json = lambda obj: json.dumps(obj, ensure_ascii=False).replace('<', '\\u003c')
    extra = '<meta name="robots" content="' + robots + '"><script type="application/ld+json" id="bl-page-schema">' + safe_json(page) + '</script><script type="application/json" id="bl-seo-routes">' + safe_json(PAGES) + '</script>'
    lazy = {name: '/static/modules/' + name + '.js?v=' + asset_version('modules/' + name + '.js')
            for name in ('single-analysis', 'archive-view', 'boxscore-view', 'match-players')}
    extra += '<script type="application/json" id="bl-asset-versions">' + safe_json(lazy) + '</script>'
    document = document.replace('</head>', extra + '</head>', 1)
    document = crawlable_navigation(document)
    if path != '/':
        document = document.replace('<main>', '<main>' + initial_content(path, players), 1)
        # The same fallback is served to all visitors, and replaced by the app
        # once navigation initializes. It remains usable if JavaScript fails.
        document = document.replace('</head>', '<style id="bl-initial-style">main > :not(#bl-initial-content){display:none!important}#bl-initial-content{padding:24px}#bl-initial-content a{color:inherit}</style></head>', 1)
    def versioned(match):
        asset = match[2]
        try:
            version = asset_version(asset)
        except FileNotFoundError:
            return match[0]
        return match[1] + '?v=' + version
    document = re.sub(r'(/static/([^"?\s]+\.(?:css|js)))\?v=[^"\s]+', versioned, document)
    if path != '/':
        # The hero belongs to Home; preloading it on every deep link competes
        # with the player's image and the selected page's data.
        document = re.sub(r'<link rel="preload" as="image" href="/static/home-lab-[^>]+>', '', document, count=1)
        document = document.replace('<img fetchpriority="high" decoding="async" src="/static/home-lab-',
                                    '<img loading="lazy" fetchpriority="low" decoding="async" src="/static/home-lab-', 1)
    return document


def sitemap(players=()):
    paths = [p for p in PAGES if p not in ('/analisi-singola', '/partite')]
    from nba_teams import TEAMS
    paths += ['/squadre/' + player_slug(name, tid) for tid, name in TEAMS.items()]
    paths += ['/giocatori/' + player_slug(p['name'], p['id']) for p in players]
    urls = ''.join('<url><loc>' + html.escape(SITE + p) + '</loc></url>' for p in dict.fromkeys(paths))
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + '</urlset>'
