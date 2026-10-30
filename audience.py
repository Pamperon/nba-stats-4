"""Aggregate usage and optional daily browser counts, without request metadata."""
from datetime import datetime, timedelta
import hashlib
import re
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
        conn.execute('''CREATE TABLE IF NOT EXISTS nba_audience_unique_daily (
            day DATE PRIMARY KEY, total BIGINT NOT NULL DEFAULT 0
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS nba_audience_unique_seen (
            day DATE NOT NULL, visitor_hash TEXT NOT NULL,
            PRIMARY KEY(day, visitor_hash)
        )''')
        # Preserve the first activation date, including days with no opt-ins.
        conn.execute('''INSERT INTO nba_audience_unique_daily(day,total)
            VALUES((NOW() AT TIME ZONE 'Europe/Rome')::date,0)
            ON CONFLICT(day) DO NOTHING''')


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


def validate_unique(payload):
    if not isinstance(payload, dict) or set(payload) != {'day', 'id'}:
        raise ValueError('Invalid daily browser payload')
    day, identifier = payload['day'], payload['id']
    if (not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day)
            or not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier)):
        raise ValueError('Invalid daily browser identifier')
    return day, identifier


def record_unique(day, identifier):
    today = datetime.now(ZoneInfo('Europe/Rome')).date()
    # Client clock/midnight races must not assign a browser to another day.
    if day != today.isoformat():
        return
    digest = hashlib.sha256((day + ':' + identifier).encode()).hexdigest()
    with storage.connection() as conn:
        conn.execute('DELETE FROM nba_audience_unique_seen WHERE day < %s',
                     (today - timedelta(days=1),))
        # One transaction: concurrent tabs/reloads increment only for a new ID.
        inserted = conn.execute('''INSERT INTO nba_audience_unique_seen(day,visitor_hash)
            VALUES(%s,%s) ON CONFLICT(day,visitor_hash) DO NOTHING
            RETURNING day''', (today, digest)).fetchone()
        if inserted:
            conn.execute('''INSERT INTO nba_audience_unique_daily(day,total)
                VALUES(%s,1) ON CONFLICT(day)
                DO UPDATE SET total=nba_audience_unique_daily.total+1''', (today,))


def report(days):
    with storage.connection() as conn:
        conn.execute("DELETE FROM nba_audience_unique_seen WHERE day < (NOW() AT TIME ZONE 'Europe/Rome')::date - 1")
        rows = conn.execute('''SELECT day,event,source,total FROM nba_audience_daily
            WHERE day >= (NOW() AT TIME ZONE 'Europe/Rome')::date - (%s - 1)
            ORDER BY day DESC,event,source''', (days,)).fetchall()
        unique_rows = conn.execute('''SELECT day,total FROM nba_audience_unique_daily
            WHERE day >= (NOW() AT TIME ZONE 'Europe/Rome')::date - (%s - 1)
            ORDER BY day DESC''', (days,)).fetchall()
        since = conn.execute('SELECT MIN(day) FROM nba_audience_unique_daily').fetchone()[0]
    return {'days': days, 'timezone': 'Europe/Rome',
            'metric': 'Aperture, azioni e browser unici giornalieri consenzienti; non persone uniche.',
            'unique_since': str(since) if since else None,
            'unique_daily': [{'day': str(day), 'total': total} for day, total in unique_rows],
            'rows': [{'day': str(day), 'event': event, 'source': source, 'total': total}
                     for day, event, source, total in rows]}
