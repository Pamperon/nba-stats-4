"""Read-only NBA standings and team schedules. No odds-provider calls."""
from datetime import datetime, timezone
from concurrent.futures import Future
import threading
import requests
from cachetools import TTLCache
from fastapi import APIRouter, HTTPException
from zoneinfo import ZoneInfo

router = APIRouter(prefix='/api/nba')
_cache = TTLCache(maxsize=40, ttl=300)
_lock = threading.RLock()
_pending = {}
BASE = 'https://site.api.espn.com/apis'


def fetch(path):
    with _lock:
        if path in _cache:
            return _cache[path]
        pending = _pending.get(path)
        owner = pending is None
        if owner:
            pending = _pending[path] = Future()
    if not owner:
        return pending.result(timeout=15)
    try:
        response = requests.get(BASE + path, timeout=12)
        response.raise_for_status()
        result = response.json()
        with _lock:
            _cache[path] = result
        pending.set_result(result)
        return result
    except Exception as exc:
        pending.set_exception(exc)
        raise
    finally:
        with _lock:
            _pending.pop(path, None)


def standings_data(payload):
    conferences = []
    for group in payload.get('children', []):
        standings = group.get('standings', {})
        teams = []
        for entry in standings.get('entries', []):
            team = entry.get('team', {})
            if not str(team.get('id', '')).isdigit():
                continue
            stats = {s['name']: s for s in entry.get('stats', [])}
            number = lambda name: stats.get(name, {}).get('value')
            display = lambda name: stats.get(name, {}).get('displayValue', '—')
            teams.append({'id': str(team['id']), 'name': team.get('displayName', ''),
                          'abbreviation': team.get('abbreviation', ''),
                          'logo': (team.get('logos') or [{}])[0].get('href', ''),
                          'rank': number('playoffSeed'), 'wins': number('wins'),
                          'losses': number('losses'), 'win_percent': number('winPercent'),
                          'games_behind': display('gamesBehind'), 'streak': display('streak'),
                          'home_record': display('Home'), 'away_record': display('Road'),
                          'last_ten': display('Last Ten Games'),
                          'points_for': number('avgPointsFor'), 'points_against': number('avgPointsAgainst')})
        teams.sort(key=lambda t: (t['rank'] if t['rank'] is not None else 99, -(t['win_percent'] or 0), t['name']))
        if teams:
            conferences.append({'name': group.get('name', ''), 'abbreviation': group.get('abbreviation', ''),
                                'season': standings.get('seasonDisplayName', ''), 'teams': teams})
    if len(conferences) != 2 or sum(len(c['teams']) for c in conferences) != 30:
        raise ValueError('Incomplete NBA standings')
    return {'conferences': conferences, 'source': 'ESPN', 'odds_api_calls': 0}


@router.get('/standings')
def standings():
    try:
        return standings_data(fetch('/v2/sports/basketball/nba/standings'))
    except Exception as exc:
        raise HTTPException(503, 'Classifica ESPN temporaneamente non disponibile') from exc


def schedule_data(payload, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload.get('events'), list) or not payload.get('team', {}).get('id'):
        raise ValueError('Invalid ESPN team schedule')
    games = []
    for event in payload.get('events', []):
        competition = (event.get('competitions') or [{}])[0]
        status = competition.get('status', event.get('status', {})).get('type', {})
        competitors = competition.get('competitors', [])
        home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away = next((c for c in competitors if c.get('homeAway') == 'away'), None)
        if not home or not away or not event.get('date'):
            continue
        start = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        def score(side):
            value = side.get('score')
            return value.get('displayValue', value.get('value')) if isinstance(value, dict) else value
        games.append({'event_id': str(event['id']), 'home': home['team']['displayName'],
                      'away': away['team']['displayName'], 'start_at': start.isoformat(),
                      'calendar_date': start.astimezone(ZoneInfo('Europe/Rome')).date().isoformat(),
                      'time_valid': competition.get('timeValid', event.get('timeValid', True)),
                      'state': status.get('state', ''), 'upcoming': status.get('state') == 'pre',
                      'status': status.get('description', ''), 'home_score': score(home), 'away_score': score(away)})
    games.sort(key=lambda g: g['start_at'])
    upcoming = [g for g in games if g['state'] == 'in' or (g['upcoming'] and datetime.fromisoformat(g['start_at']) >= now)]
    recent = [g for g in games if g['state'] == 'post']
    team = payload.get('team', {})
    color = team.get('color', '')
    return {'team': {'id': str(team.get('id', '')), 'name': team.get('displayName', ''),
                     'logo': team.get('logo', ''), 'color': color if len(color) == 6 and all(c in '0123456789abcdefABCDEF' for c in color) else '243b59',
                     'record': team.get('recordSummary', ''), 'season': team.get('seasonSummary', '')},
            'upcoming': upcoming[:5], 'recent': list(reversed(recent[-5:])), 'source': 'ESPN', 'odds_api_calls': 0}


@router.get('/teams/{team_id}')
def team_details(team_id: str):
    import nba_teams
    if team_id not in nba_teams.TEAMS:
        raise HTTPException(404, 'Squadra NBA non trovata')
    try:
        return schedule_data(fetch('/site/v2/sports/basketball/nba/teams/' + team_id + '/schedule'))
    except Exception as exc:
        raise HTTPException(503, 'Calendario della squadra temporaneamente non disponibile') from exc
