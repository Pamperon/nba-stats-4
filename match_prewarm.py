"""Bounded background warming for upcoming matches; never scans paid odds."""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import match_history

logger = logging.getLogger(__name__)
ROME = ZoneInfo('Europe/Rome')

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
        warmed = warm_upcoming(schedule, stop)
        logger.info('Match history warmup complete: %s', ','.join(warmed) or 'no upcoming window')
        if stop.wait(600): return
