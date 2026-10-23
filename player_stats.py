"""Public NBA roster and independent ESPN player statistics. No OddsPapi calls."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import engine
import storage

logger = logging.getLogger(__name__)

def cached(key, hours, loader):
    try:
        hit = storage.cache_read(key, hours)
        if hit is not None:
            return hit
    except Exception:
        logger.warning("Player cache read unavailable", exc_info=True)
    result = loader()
    try:
        storage.cache_write(key, result)
    except Exception:
        logger.warning("Player cache write unavailable", exc_info=True)
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
        return sorted([{"id": a["id"], "name": a["displayName"], "team_id": team_id}
                       for a in players], key=lambda p: p["name"])
    return cached("nba:roster:v2:" + team_id, 12, build)

def player_log(team_id, athlete_id, season):
    if athlete_id not in {p["id"] for p in roster(team_id)}:
        raise ValueError("Giocatore non presente nel roster attuale")
    if not (season.isdigit() and len(season) == 4):
        raise ValueError("Stagione non valida")
    year = int(season)
    current = datetime.now(ZoneInfo("Europe/Rome")).year
    if year < current - 3 or year > current + 1:
        raise ValueError("Stagione fuori intervallo")
    def build():
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
    return cached("nba:log:v1:" + team_id + ":" + athlete_id + ":" + season,
                  6 if year >= current - 1 else 720, build)
