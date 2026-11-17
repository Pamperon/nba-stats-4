"""Descriptive player form from fresh saved ESPN histories; no provider requests."""
import math
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
    if sum(g['minutes'] for g in valid) / len(valid) < 15 or sum(g['minutes'] for g in recent) / 5 < 15:
        return None
    return {'games': len(valid), 'last_played': valid[0]['day'].isoformat(), 'stats': {
        key: {'recent_average': sum(g[key] for g in recent) / 5,
              'season_average': sum(g[key] for g in valid) / len(valid),
              'delta': sum(g[key] for g in recent) / 5 - sum(g[key] for g in valid) / len(valid),
              'recent_values': [g[key] for g in reversed(recent)]}
        for key in MARKETS}}


def build(now=None):
    now = now or datetime.now(ROME)
    season = str(now.year if now.month >= 10 else now.year - 1)
    players = player_stats.directory()
    keys = {'nba:log:final-v4:' + p['team_id'] + ':' + p['id'] + ':' + season: p for p in players}
    # One database read for saved histories; never start a scan or fetch player logs.
    saved = storage.cache_read_many(keys, 6)
    ranked = {key: [] for key in MARKETS}
    eligible, seen = 0, set()
    for key, payload in saved.items():
        player = keys.get(key)
        if not player or player['id'] in seen or not isinstance(payload, dict):
            continue
        summary = summarize(payload.get('games') or [], now)
        if summary is None:
            continue
        seen.add(player['id'])
        eligible += 1
        for market in MARKETS:
            ranked[market].append({**player, 'games': summary['games'],
                                   'last_played': summary['last_played'], **summary['stats'][market]})
    markets = {}
    for market, rows in ranked.items():
        # Exclude changes that round to zero in the displayed one-decimal figures.
        up = sorted((r for r in rows if r['delta'] >= .05), key=lambda r: (-r['delta'], -r['recent_average'], r['id']))
        down = sorted((r for r in rows if r['delta'] <= -.05), key=lambda r: (r['delta'], -r['season_average'], r['id']))
        markets[market] = {'up': up[:3], 'down': down[:3]}
    return {'season': season + '–' + str(int(season) + 1)[-2:], 'generated_at': now.isoformat(),
            'eligible_players': eligible, 'roster_players': len({p['id'] for p in players}),
            'markets': markets, 'source': 'ESPN', 'odds_api_calls': 0}


def read():
    with _lock:
        day = datetime.now(ROME).date().isoformat()
        if day not in _cache:
            _cache[day] = build()
        return _cache[day]
