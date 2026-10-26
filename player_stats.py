"""Public NBA roster and independent ESPN player statistics. No OddsPapi calls."""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache
from datetime import datetime
from zoneinfo import ZoneInfo
import engine
import storage

logger = logging.getLogger(__name__)

_memory_cache = TTLCache(maxsize=250, ttl=1800)
_memory_lock = threading.RLock()

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
    with _memory_lock:
        if key in _memory_cache:
            return _memory_cache[key]
    try:
        hit = storage.cache_read(key, hours)
        if hit is not None:
            with _memory_lock:
                _memory_cache[key] = hit
            return hit
    except Exception:
        logger.warning("Player cache read unavailable", exc_info=True)
    result = loader()
    with _memory_lock:
        _memory_cache[key] = result
    persist_cache(key, result)
    return result

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

def player_log(team_id, athlete_id, season):
    if not (season.isdigit() and len(season) == 4):
        raise ValueError("Stagione non valida")
    year = int(season)
    current = datetime.now(ZoneInfo("Europe/Rome")).year
    if year < current - 3 or year > current + 1:
        raise ValueError("Stagione fuori intervallo")
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
            records.append({"GAME_DATE": date, "PTS": float(row["PTS"]),
                            "REB": float(row["REB"]), "AST": float(row["AST"]),
                            "SEASON_TYPE": int(row["SEASON_TYPE"]),
                            "MATCHUP": str(row.get("MATCHUP", ""))})
        return {"games": records, "season": season, "athlete_id": athlete_id}
    return cached("nba:log:final-v2:" + team_id + ":" + athlete_id + ":" + season,
                  6 if year >= current - 1 else 720, build)

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
