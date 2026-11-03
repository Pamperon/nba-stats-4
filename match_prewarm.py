"""Bounded background warming for upcoming matches; never scans paid odds."""
import logging
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import match_history

logger = logging.getLogger(__name__)
ROME = ZoneInfo('Europe/Rome')
_status_lock = threading.Lock()
_status = {'state': 'waiting', 'last_completed_at': None, 'warmed_dates': []}

def status():
    with _status_lock:
        return {**_status, 'warmed_dates': list(_status['warmed_dates']), 'odds_api_calls': 0}


def warm_upcoming(schedule, stop, now=None):
    now = now or datetime.now(ROME)
    warmed = []
    for offset in range(3):
        if stop.is_set(): break
        day = (now.date() + timedelta(days=offset)).isoformat()
        try:
            games = schedule(day).get('games', [])
            upcoming = []
            for game in games:
                try:
                    start = datetime.fromisoformat(game.get('start_at', '').replace('Z', '+00:00'))
                    if game.get('upcoming') is True and start.tzinfo and now < start <= now + timedelta(hours=72):
                        upcoming.append(game)
                except (ValueError, TypeError):
                    continue
            if upcoming and not stop.is_set():
                _, failed = match_history.load_window(now.date() + timedelta(days=offset))
                if not failed: warmed.append(day)
        except Exception:
            logger.warning('Upcoming history warmup unavailable for %s', day, exc_info=True)
    return warmed

def run(stop, schedule):
    # Wait until the process is listening. Startup/health checks never wait for ESPN.
    if stop.wait(30): return
    while not stop.is_set():
        with _status_lock:
            _status['state'] = 'running'
        try:
            warmed = warm_upcoming(schedule, stop)
        except Exception:
            logger.exception('History warmup cycle failed')
            with _status_lock:
                _status['state'] = 'error'
            if stop.wait(600): return
            continue
        with _status_lock:
            _status.update(state='idle', last_completed_at=datetime.now(ROME).isoformat(), warmed_dates=warmed)
        logger.info('Match history warmup complete: %s', ','.join(warmed) or 'no upcoming window')
        if stop.wait(600): return
