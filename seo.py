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
    '/': ('Basket Lab | Statistiche e analisi NBA', 'Statistiche NBA, analisi dei giocatori, quote e pronostici basati sui dati delle partite.'),
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


def render(path, players=None):
    if players is None:
        players = saved_players() if path.startswith('/giocatori/') else ()
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
    document = document.replace('</head>', extra + '</head>', 1)
    document = crawlable_navigation(document)
    def versioned(match):
        asset = match[2]
        file = Path('web') / asset
        if not file.is_file():
            return match[0]
        stat = file.stat()
        return match[1] + '?v=' + _asset_version(asset, stat.st_mtime_ns, stat.st_size)
    document = re.sub(r'(/static/([^"?\s]+\.(?:css|js)))\?v=[^"\s]+', versioned, document)
    return document


def sitemap(players=()):
    paths = [p for p in PAGES if p != '/analisi-singola']
    from nba_teams import TEAMS
    paths += ['/squadre/' + player_slug(name, tid) for tid, name in TEAMS.items()]
    paths += ['/giocatori/' + player_slug(p['name'], p['id']) for p in players]
    urls = ''.join('<url><loc>' + html.escape(SITE + p) + '</loc></url>' for p in dict.fromkeys(paths))
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + '</urlset>'
