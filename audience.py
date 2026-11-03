"""First-party aggregate usage counts. No visitor IDs or request metadata stored."""
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
import time
import storage

EVENTS = frozenset(('apertura', 'pronostici', 'quote', 'statistiche', 'archivio',
                    'informazioni', 'filtro_quote', 'scelta_giocatore', 'dettagli', 'csv'))
SOURCES = frozenset(('diretto', 'instagram', 'facebook', 'tiktok', 'whatsapp',
                     'telegram', 'google', 'bing', 'altro'))
_guard = threading.Lock()
_window = 0
_received = 0


def initialize():
    with storage.connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS nba_audience_daily (
            day DATE NOT NULL, event TEXT NOT NULL, source TEXT NOT NULL,
            total BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY(day, event, source)
        )''')


def allowed():
    """Bound global collection work without storing IPs or other visitor keys."""
    global _window, _received
    minute = int(time.monotonic() // 60)
    with _guard:
        if minute != _window:
            _window, _received = minute, 0
        _received += 1
        return _received <= 300


def validate(payload):
    if not isinstance(payload, dict) or set(payload) != {'source', 'events'}:
        raise ValueError('Invalid aggregate payload')
    source, events = payload['source'], payload['events']
    if not isinstance(source, str) or source not in SOURCES:
        raise ValueError('Invalid source')
    if not isinstance(events, list) or not 1 <= len(events) <= 10:
        raise ValueError('Invalid batch size')
    if any(not isinstance(event, str) or event not in EVENTS for event in events):
        raise ValueError('Invalid event')
    return source, events


def record(source, events):
    day = datetime.now(ZoneInfo('Europe/Rome')).date()
    with storage.connection() as conn:
        for event in sorted(set(events)):
            conn.execute('''INSERT INTO nba_audience_daily(day,event,source,total)
                VALUES(%s,%s,%s,%s) ON CONFLICT(day,event,source)
                DO UPDATE SET total=nba_audience_daily.total+EXCLUDED.total''',
                         (day, event, source, events.count(event)))


def report(days):
    with storage.connection() as conn:
        rows = conn.execute('''SELECT day,event,source,total FROM nba_audience_daily
            WHERE day >= (NOW() AT TIME ZONE 'Europe/Rome')::date - (%s - 1)
            ORDER BY day DESC,event,source''', (days,)).fetchall()
    return {'days': days, 'timezone': 'Europe/Rome',
            'metric': 'Aperture e azioni; non visitatori unici. Ricaricare conta una nuova apertura.',
            'rows': [{'day': str(day), 'event': event, 'source': source, 'total': total}
                     for day, event, source, total in rows]}
