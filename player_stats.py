"""Public NBA roster and independent ESPN player statistics. No OddsPapi calls."""
import logging
import math
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from cachetools import TTLCache
from datetime import datetime
from zoneinfo import ZoneInfo
import engine
import storage

logger = logging.getLogger(__name__)

_memory_cache = TTLCache(maxsize=250, ttl=1800)
_historical_cache = TTLCache(maxsize=160, ttl=86400)
_memory_lock = threading.RLock()
_pending = {}

# Optional persistence must not delay a response. Bound both workers and queue.
_cache_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="player-cache")
_cache_write_slots = threading.BoundedSemaphore(16)

def persist_cache(key, result):
    if not _cache_write_slots.acquire(blocking=False):
        return
    def write():
        try:
            storage.cache_write(key, result)
        except Exception:
            logger.warning("Player cache write unavailable", exc_info=True)
        finally:
            _cache_write_slots.release()
    try:
        _cache_writer.submit(write)
    except RuntimeError:
        _cache_write_slots.release()

def cached(key, hours, loader):
    memory = _historical_cache if hours >= 720 else _memory_cache
    with _memory_lock:
        if key in memory:
            return memory[key]
        # Concurrent visitors share one provider/database load.
        pending = _pending.get(key)
        owner = pending is None
        if owner:
            pending = _pending[key] = Future()
    if not owner:
        return pending.result()
    try:
        try:
            hit = storage.cache_read(key, hours)
        except Exception:
            logger.warning("Player cache read unavailable", exc_info=True)
            hit = None
        result = hit if hit is not None else loader()
        with _memory_lock:
            memory[key] = result
        if hit is None:
            persist_cache(key, result)
        pending.set_result(result)
        return result
    except BaseException as exc:
        pending.set_exception(exc)
        raise
    finally:
        with _memory_lock:
            _pending.pop(key, None)

def catalog():
    def build():
        teams = []
        for entry in engine.espn_teams():
            team = entry.get("team", entry)
            tid = str(team.get("id", ""))
            if tid.isdigit():
                teams.append({"id": tid, "name": team.get("displayName") or team.get("name") or tid})
        return sorted(teams, key=lambda t: t["name"])
    return cached("nba:teams:v1", 24, build)

def roster(team_id):
    teams = catalog()
    if team_id not in {t["id"] for t in teams}:
        raise ValueError("Squadra NBA non valida")
    def build():
        players = engine.roster_athletes(engine.espn_roster(team_id))
        return sorted([{"id": a["id"], "name": a["displayName"], "team_id": team_id,
                        "position": a.get("position", ""), "jersey": a.get("jersey", ""),
                        "height": a.get("height", ""), "weight": a.get("weight", "")}
                       for a in players], key=lambda p: p["name"])
    return cached("nba:roster:v3:" + team_id, 12, build)

def directory():
    """Current NBA players for name search; reuse roster caches, never game logs."""
    def build():
        teams = catalog()
        if not teams:
            raise ValueError("Catalogo NBA non disponibile")
        def team_players(team):
            return [{"id": str(player["id"]), "name": player["name"],
                     "team_id": team["id"], "team": team["name"]}
                    for player in roster(team["id"])]
        # A failed roster must not become a cached, incomplete search directory.
        with ThreadPoolExecutor(max_workers=4) as pool:
            players = [player for group in pool.map(team_players, teams) for player in group]
        return sorted(players, key=lambda player: (player["name"].casefold(), player["team_id"], player["id"]))
    return cached("nba:player-directory:v1", 6, build)

def validate_season(season):
    if not (season.isdigit() and len(season) == 4):
        raise ValueError("Stagione non valida")
    year = int(season)
    current = datetime.now(ZoneInfo("Europe/Rome")).year
    if year < current - 3 or year > current + 1:
        raise ValueError("Stagione fuori intervallo")
    return year, current

def log_cache_hours(year):
    now = datetime.now(ZoneInfo('Europe/Rome'))
    current_start = now.year if now.month >= 10 else now.year - 1
    return 6 if year >= current_start else 720

def player_log(team_id, athlete_id, season):
    year, current = validate_season(season)
    def build():
        # A cached log was already validated when built. Avoid loading teams and
        # roster from the database again on every cold-process cache hit.
        if athlete_id not in {p["id"] for p in roster(team_id)}:
            raise ValueError("Giocatore non presente nel roster attuale")
        season_key = str(year) + "-" + str(year + 1)[-2:]
        frame = engine.selected_game_log(athlete_id, season_key, "Regular season + Playoff", team_id)
        if frame.empty:
            return {"games": [], "season": season, "athlete_id": athlete_id}
        frame = engine.prepare_game_log(frame, team_id, season_key)
        records = []
        for _, row in frame.iterrows():
            date = row.get("GAME_DATE")
            if hasattr(date, "isoformat") and not str(date) == "NaT":
                date = date.isoformat()
            else:
                date = None
            raw_minutes = row.get("MIN")
            try:
                value = str(raw_minutes).strip()
                if ":" in value:
                    parts = value.split(":")
                    minutes = int(parts[0]) + int(parts[1]) / 60 if len(parts) == 2 and 0 <= int(parts[1]) < 60 else None
                else:
                    minutes = float(value)
                if minutes is not None and (not math.isfinite(minutes) or minutes < 0 or minutes > 100):
                    minutes = None
            except (TypeError, ValueError, OverflowError):
                minutes = None
            records.append({"GAME_ID": str(row.get("GAME_ID", "")), "GAME_DATE": date, "MIN": minutes, "PTS": float(row["PTS"]),
                            "REB": float(row["REB"]), "AST": float(row["AST"]),
                            "SEASON_TYPE": int(row["SEASON_TYPE"]),
                            "MATCHUP": str(row.get("MATCHUP", ""))})
        return {"games": records, "season": season, "athlete_id": athlete_id}
    return cached("nba:log:final-v4:" + team_id + ":" + athlete_id + ":" + season,
                  log_cache_hours(year), build)

def team_cached_logs(team_id, season):
    """Small batch of already saved logs, scoped to the current roster/season."""
    year, current = validate_season(season)
    hours = log_cache_hours(year)
    memory = _historical_cache if hours >= 720 else _memory_cache
    batch_key = "nba:team-logs:v3:" + team_id + ":" + season
    with _memory_lock:
        if batch_key in memory:
            return memory[batch_key]
    players = roster(team_id)
    keys = {"nba:log:final-v4:" + team_id + ":" + p["id"] + ":" + season: p["id"]
            for p in players}
    logs = {}
    with _memory_lock:
        for key, athlete_id in keys.items():
            if key in memory:
                logs[athlete_id] = memory[key]
    missing = [key for key, athlete_id in keys.items() if athlete_id not in logs]
    try:
        saved = storage.cache_read_many(missing, hours)
        with _memory_lock:
            for key, payload in saved.items():
                if key in keys:
                    memory[key] = payload
                    logs[keys[key]] = payload
            if logs:
                memory[batch_key] = logs
    except Exception:
        # Optional acceleration: individual log requests still work on failure.
        logger.warning("Team log cache unavailable", exc_info=True)
    return logs

def player_profile(team_id, athlete_id):
    """Player portrait from the official ESPN CDN; no fragile profile API call."""
    athletes = roster(team_id)
    athlete = next((p for p in athletes if p["id"] == athlete_id), None)
    if athlete is None:
        raise ValueError("Giocatore non presente nel roster attuale")
    # ESPN player IDs are numeric and the CDN has a stable headshot URL.
    # Missing portraits are handled by the frontend's initials fallback.
    return {
        "id": athlete_id,
        "name": athlete["name"],
        "position": athlete.get("position", ""),
        "jersey": athlete.get("jersey", ""),
        "headshot": f"https://a.espncdn.com/i/headshots/nba/players/full/{athlete_id}.png",
        "height": athlete.get("height", ""),
        "weight": athlete.get("weight", ""),
    }


def game_details(event_id):
    """Fetch final score only on an explicit game-detail request; retain no box score."""
    def build():
        payload = engine.espn_json(f"{engine.ESPN_SITE}/summary", event=event_id)
        header = payload.get('header') if isinstance(payload, dict) else None
        if not isinstance(header, dict) or str(header.get('id')) != event_id:
            raise ValueError('Partita ESPN non verificabile')
        if engine.espn_event_completed(header) is not True:
            raise ValueError('Risultato finale non ancora verificato')
        competitions = header.get('competitions')
        if not isinstance(competitions, list) or len(competitions) != 1:
            raise ValueError('Partita ESPN ambigua')
        competitors = competitions[0].get('competitors', [])
        teams = {}
        for competitor in competitors:
            side = competitor.get('homeAway')
            team = competitor.get('team') or {}
            score = competitor.get('score')
            if isinstance(score, dict):
                score = score.get('displayValue')
            value = str(score)
            if side not in ('home', 'away') or side in teams or not value.isdigit():
                raise ValueError('Punteggio ESPN non verificabile')
            if not team.get('id') or not team.get('abbreviation') or not 0 <= int(value) <= 1000:
                raise ValueError('Squadra o punteggio ESPN mancante')
            teams[side] = {'id': str(team['id']), 'name': str(team.get('displayName') or team['abbreviation']),
                           'abbreviation': str(team['abbreviation']), 'score': int(value)}
        if len(competitors) != 2 or set(teams) != {'home', 'away'} or teams['home']['id'] == teams['away']['id']:
            raise ValueError('Squadre ESPN non verificabili')
        if teams['home']['score'] == teams['away']['score']:
            raise ValueError('Punteggio finale ESPN incoerente')
        return {'event_id': event_id, 'final': True, **teams}
    return cached('nba:game-details:v1:' + event_id, 720, build)
