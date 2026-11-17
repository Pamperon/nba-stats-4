"""League-wide ESPN form, refreshed by a bounded background worker."""
import math
import logging
from concurrent.futures import ThreadPoolExecutor
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from cachetools import TTLCache
import player_stats
import storage

ROME = ZoneInfo('Europe/Rome')
MARKETS = ('PTS', 'REB', 'AST')
_cache = TTLCache(maxsize=1, ttl=300)
_lock = threading.Lock()
logger = logging.getLogger(__name__)
_status_lock = threading.Lock()
_status = {'state': 'waiting', 'checked_players': 0, 'roster_players': 0, 'failed_players': 0}


def status():
    with _status_lock:
        return {**_status, 'odds_api_calls': 0}


def season_for(now):
    return str(now.year if now.month >= 10 else now.year - 1)


def snapshot_key(now):
    return 'nba:form:league:v1:' + season_for(now)


def roster():
    # A transferred athlete must not occupy two places in the comparison.
    players = list({str(p['id']): p for p in player_stats.directory()}.values())
    if not players:
        raise ValueError('Roster NBA non disponibile')
    return players


def log_key(player, now):
    return 'nba:log:final-v4:' + player['team_id'] + ':' + player['id'] + ':' + season_for(now)



def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def summarize(games, now):
    """Require complete regular-season samples, known dates and actual appearances."""
    season_start = now.year if now.month >= 10 else now.year - 1
    start = datetime(season_start, 10, 1, tzinfo=ROME).date()
    seen, valid = set(), []
    for game in games:
        if str(game.get('SEASON_TYPE')) not in ('2', '2.0'):
            continue
        minutes = number(game.get('MIN'))
        if minutes == 0:
            continue
        try:
            day = datetime.fromisoformat(str(game.get('GAME_DATE')).replace('Z', '+00:00'))
            day = day.astimezone(ROME).date() if day.tzinfo else day.date()
        except (ValueError, TypeError):
            return None
        if not start <= day <= now.date():
            continue
        # Missing minutes cannot qualify a player.
        values = {key: number(game.get(key)) for key in MARKETS}
        identity = str(game.get('GAME_ID') or day.isoformat())
        if identity in seen:
            continue
        seen.add(identity)
        if minutes is None or minutes > 100 or any(v is None for v in values.values()):
            return None
        valid.append({'day': day, 'minutes': minutes, **values})
    valid.sort(key=lambda g: g['day'], reverse=True)
    if len(valid) < 10 or valid[0]['day'] < now.date() - timedelta(days=7):
        return None
    recent = valid[:5]
    return {'games': len(valid), 'last_played': valid[0]['day'].isoformat(), 'stats': {
        key: {'recent_average': sum(g[key] for g in recent) / 5,
              'season_average': sum(g[key] for g in valid) / len(valid),
              'delta': sum(g[key] for g in recent) / 5 - sum(g[key] for g in valid) / len(valid),
              'recent_values': [g[key] for g in reversed(recent)]}
        for key in MARKETS}}


def project(players, summaries, now, *, failed=0, refreshing=False):
    ranked = {key: [] for key in MARKETS}
    eligible = 0
    for player in players:
        summary = summaries.get(player['id'])
        if summary is None:
            continue
        eligible += 1
        for market in MARKETS:
            ranked[market].append({**player, 'games': summary['games'],
                                   'last_played': summary['last_played'], **summary['stats'][market]})
    markets = {}
    for market, rows in ranked.items():
        up = sorted((r for r in rows if r['delta'] >= .05), key=lambda r: (-r['delta'], -r['recent_average'], r['id']))
        down = sorted((r for r in rows if r['delta'] <= -.05), key=lambda r: (r['delta'], -r['season_average'], r['id']))
        markets[market] = {'up': up[:3], 'down': down[:3]}
    season = season_for(now)
    return {'season': season + '–' + str(int(season) + 1)[-2:], 'generated_at': now.isoformat(),
            'eligible_players': eligible, 'roster_players': len(players),
            'checked_players': len(summaries), 'failed_players': failed,
            'coverage_complete': len(summaries) == len(players), 'refreshing': refreshing,
            'markets': markets, 'source': 'ESPN', 'odds_api_calls': 0}


def saved_summaries(players, now):
    keys = {log_key(p, now): p for p in players}
    saved = storage.cache_read_many(keys, 6)
    return {keys[key]['id']: summarize(payload.get('games') or [], now)
            for key, payload in saved.items() if key in keys and isinstance(payload, dict)}


def build(now=None):
    """Cold-start fallback reads saved data only; visitors never fetch league logs."""
    now = now or datetime.now(ROME)
    players = roster()
    return project(players, saved_summaries(players, now), now, refreshing=True)


def publish(players, summaries, now, *, failed=0, refreshing=False):
    result = project(players, summaries, now, failed=failed, refreshing=refreshing)
    storage.cache_write(snapshot_key(now), result)
    with _lock:
        _cache.clear()
    with _status_lock:
        _status.update(state='running' if refreshing else 'partial' if failed else 'idle',
                       checked_players=len(summaries), roster_players=len(players), failed_players=failed)
    return result


def refresh(stop, now=None, busy=lambda: False):
    """Check every roster member. Reuse fresh logs and fetch the rest two at a time."""
    if stop.is_set():
        return None
    now = now or datetime.now(ROME)
    players = roster()
    summaries = saved_summaries(players, now)
    missing = [p for p in players if p['id'] not in summaries]
    failed = 0
    publish(players, summaries, now, refreshing=bool(missing))

    def fetch_summary(player):
        if stop.is_set():
            return False, None
        try:
            payload = player_stats.player_log(player['team_id'], player['id'], season_for(now))
            return True, summarize(payload.get('games') or [], now)
        except Exception:
            logger.warning('League form history unavailable for athlete %s', player['id'], exc_info=True)
            return False, None

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='nba-form') as pool:
        for offset in range(0, len(missing), 2):
            if stop.is_set():
                return None
            # Give prediction scans priority without delaying health or page requests.
            while busy():
                if stop.wait(10):
                    return None
            batch = missing[offset:offset+2]
            futures = [(p, pool.submit(fetch_summary, p)) for p in batch]
            for player, future in futures:
                success, summary = future.result()
                if success:
                    summaries[player['id']] = summary
                elif not stop.is_set():
                    failed += 1
            if stop.is_set():
                return None
            if (offset+len(batch)) % 50 == 0:
                publish(players, summaries, now, failed=failed, refreshing=True)
    if stop.is_set():
        return None
    result = publish(players, summaries, now, failed=failed)
    logger.info('League form updated: checked=%s roster=%s eligible=%s failed=%s',
                result['checked_players'], len(players), result['eligible_players'], failed)
    return result


def run(stop, busy=lambda: False):
    # Startup opens its listening port before any league statistics work begins.
    if stop.wait(30):
        return
    while not stop.is_set():
        wait = 600
        try:
            now = datetime.now(ROME)
            saved = storage.cache_read(snapshot_key(now), 6)
            if not isinstance(saved, dict) or not saved.get('coverage_complete'):
                result = refresh(stop, now, busy)
                if result and not result['coverage_complete']:
                    wait = 120
            else:
                with _status_lock:
                    _status.update(state='idle', checked_players=saved['checked_players'],
                                   roster_players=saved['roster_players'], failed_players=0)
        except Exception:
            logger.exception('League form refresh unavailable')
            with _status_lock:
                _status['state'] = 'error'
            wait = 120
        if stop.wait(wait):
            return


def read():
    with _lock:
        now = datetime.now(ROME)
        day = now.date().isoformat()
        if day not in _cache:
            saved = storage.cache_read(snapshot_key(now), 24)
            _cache[day] = saved if isinstance(saved, dict) and 'markets' in saved else build(now)
        return _cache[day]
