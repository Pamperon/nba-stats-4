"""Read-only ESPN history transport, separate from all NBA model calculations."""
import logging
import threading
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from cachetools import TTLCache
import storage
from player_stats import persist_cache

logger=logging.getLogger(__name__)
_daily=TTLCache(maxsize=90,ttl=7200)
_windows=TTLCache(maxsize=8,ttl=1800)
_guard=threading.RLock()
# Fixed-size locks prevent duplicate cold requests without an unbounded lock map.
_day_locks=[threading.Lock() for _ in range(32)]
_window_locks=[threading.Lock() for _ in range(8)]

def compact_event(event):
    """Keep every field used by form/H2H; drop media and unrelated feed data."""
    result = {key: event[key] for key in ('id', 'date') if key in event}
    if 'status' in event:
        kind = (event.get('status') or {}).get('type') or {}
        result['status'] = {'type': {key: kind[key] for key in ('state', 'completed') if key in kind}}
    if 'competitions' in event:
        result['competitions'] = [{'competitors': [
            {'team': {'displayName': (c.get('team') or {}).get('displayName', '')},
             **({'score': c['score']} if 'score' in c else {})}
            for c in competition.get('competitors') or []]}
            for competition in event.get('competitions') or []]
    return result


def daily_events(day):
    key=day.strftime('%Y%m%d')
    with _guard:
        if key in _daily:return _daily[key]
    with _day_locks[hash(key)%len(_day_locks)]:
        with _guard:
            if key in _daily:return _daily[key]
        response=requests.get('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',params={'dates':key},timeout=9)
        response.raise_for_status()
        events=[compact_event(event) for event in response.json().get('events',[])]
        with _guard:_daily[key]=events
        return events

def load_window(target):
    key='nba:match-history:21d:v1:'+target.isoformat()
    with _guard:
        if key in _windows:return _windows[key],0
    with _window_locks[hash(key)%len(_window_locks)]:
        with _guard:
            if key in _windows:return _windows[key],0
        if storage.configured():
            try:
                saved=storage.cache_read(key,max_age_hours=0.5)
                if isinstance(saved,dict) and saved.get('date')==target.isoformat() and saved.get('complete') is True and isinstance(saved.get('events'),list):
                    events=[compact_event(event) for event in saved['events']]
                    with _guard:_windows[key]=events
                    return events,0
            except Exception:logger.warning('Match history cache unavailable',exc_info=True)
        events=[];failed=0
        days=[target-timedelta(days=offset) for offset in range(1,22)]
        with ThreadPoolExecutor(max_workers=7) as pool:
            futures={pool.submit(daily_events,day):day for day in days}
            for future in as_completed(futures):
                try:events.extend(future.result())
                except requests.RequestException:
                    failed+=1
                    logger.warning('ESPN scoreboard unavailable for %s',futures[future])
        # Never preserve a partial response as a complete historical sample.
        if not failed:
            with _guard:_windows[key]=events
            if storage.configured():persist_cache(key,{'date':target.isoformat(),'complete':True,'events':events})
        return events,failed
