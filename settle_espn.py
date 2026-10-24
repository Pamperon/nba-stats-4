"""Verify archived player props against finalized ESPN box scores.

Read-only ESPN calls; never fetch bookmaker odds. Reject ambiguous identities.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
import engine

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

def fetch(url, **params):
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.json()

def final_events(scan_date, require_all_final=True):
    # NBA games can cross midnight UTC; ESPN dates use league schedule dates.
    from datetime import timedelta, date
    rome_day = date.fromisoformat(scan_date)
    events_by_id = {}
    for offset in (-1, 0, 1):
        espn_day = (rome_day + timedelta(days=offset)).strftime("%Y%m%d")
        data = fetch(BASE + "/scoreboard", dates=espn_day, limit=100)
        for event in data.get("events", []):
            start = event.get("date")
            if not start:
                continue
            utc_start = datetime.fromisoformat(start.replace("Z","+00:00"))
            if utc_start.astimezone(ZoneInfo("Europe/Rome")).date() == rome_day:
                events_by_id[event["id"]] = event
    events = list(events_by_id.values())
    if not events:
        raise ValueError("ESPN has no events for requested date")
    if require_all_final and any(not (e.get("status",{}).get("type",{}).get("completed") is True) for e in events):
        raise ValueError("Not all games on this ESPN date are final")
    return events

def player_stats(summary):
    """Return (team, normalized athlete) -> PTS/AST/REB, only when played."""
    found = {}
    for team in summary.get("boxscore",{}).get("players",[]):
        team_name = (team.get("team") or {}).get("displayName","")
        team_key = engine.normalized_name(team_name)
        for group in team.get("statistics",[]):
            labels = [str(x).upper() for x in group.get("labels",[])]
            if not all(k in labels for k in ("PTS","AST","REB")):
                continue
            for athlete in group.get("athletes",[]):
                if athlete.get("didNotPlay") or athlete.get("ejected") and not athlete.get("stats"):
                    continue
                name = (athlete.get("athlete") or {}).get("displayName","")
                stats = athlete.get("stats",[])
                if len(stats) != len(labels):
                    continue
                try:
                    nums = {key: float(stats[labels.index(key)]) for key in ("PTS","AST","REB")}
                except (TypeError, ValueError):
                    continue
                key = (team_key,engine.espn_player_key(name))
                if key in found:
                    raise ValueError("Duplicate athlete in ESPN boxscore")
                found[key] = nums
                athlete_id = str((athlete.get("athlete") or {}).get("id") or "").strip()
                if athlete_id.isdigit():
                    id_key = (team_key, "id:" + athlete_id)
                    if id_key in found:
                        raise ValueError("Duplicate ESPN athlete ID in boxscore")
                    found[id_key] = nums
    return found

def settle_archive(snapshot, scan_date):
    """Verify only the archived fixtures, never already-started unrelated games."""
    events = final_events(scan_date, require_all_final=False)
    rows = snapshot.get("results", [])
    if not rows:
        raise ValueError("No archived predictions")

    archived_fixtures = set()
    for row in rows:
        fixture = row.get("Partita", "")
        teams = frozenset(engine.normalized_name(t) for t in fixture.split(" - "))
        if len(teams) != 2 or not all(teams):
            raise ValueError("Malformed archived fixture")
        archived_fixtures.add(teams)

    saved_at = snapshot.get("scan_finished_at") or snapshot.get("saved_at")
    if not saved_at:
        raise ValueError("Snapshot has no verifiable pregame timestamp")
    from datetime import timezone
    snapshot_time = datetime.fromisoformat(str(saved_at).replace("Z", "+00:00"))
    if snapshot_time.tzinfo is None:
        raise ValueError("Timezone missing from snapshot timestamp")
    snapshot_time = snapshot_time.astimezone(timezone.utc)

    matched_events = {}
    for event in events:
        competitors = (event.get("competitions") or [{}])[0].get("competitors", [])
        teams = frozenset(engine.normalized_name(
            (c.get("team") or {}).get("displayName", "")) for c in competitors)
        if teams in archived_fixtures:
            if teams in matched_events:
                raise ValueError("Duplicate ESPN fixture on archive date")
            matched_events[teams] = event

    missing = archived_fixtures - set(matched_events)
    if missing:
        raise ValueError(f"ESPN missing {len(missing)} archived fixtures")

    lookup = {}
    for fixture, event in matched_events.items():
        if event.get("status", {}).get("type", {}).get("completed") is not True:
            raise ValueError("An archived ESPN game is not final")
        start = event.get("date")
        if not start:
            raise ValueError("ESPN event start time unavailable")
        tipoff = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if snapshot_time >= tipoff:
            raise ValueError("Snapshot saved after an archived game's tipoff")
        summary = fetch(BASE + "/summary", event=event["id"])
        stats = player_stats(summary)
        if not stats:
            raise ValueError("Missing ESPN player boxscore")
        for team in fixture:
            if team in lookup:
                raise ValueError("Duplicate team across ESPN games")
            lookup[team] = (fixture, stats)
    # Reject inconsistent archive dates: a prediction row must reference an
    # actual ESPN fixture, not merely a team that happened to play that day.
    verified = []
    for row in rows:
        team = engine.normalized_name(row.get("Squadra",""))
        game = lookup.get(team)
        if game is None:
            continue
        opponents, stats = game
        fixture = row.get("Partita","")
        fixture_teams = frozenset(engine.normalized_name(t) for t in fixture.split(" - "))
        if fixture_teams != opponents:
            continue
        player = engine.espn_player_key(row.get("Giocatore",""))
        athlete_id = str(row.get("ESPN ID") or "").strip()
        if athlete_id:
            # Fail closed: never substitute a name match for a mismatched ID.
            actuals = stats.get((team, "id:" + athlete_id)) if athlete_id.isdigit() else None
        else:
            # Backward compatibility for historical snapshots without IDs.
            actuals = stats.get((team,player))
        if actuals is None or row.get("Mercato") not in actuals:
            continue
        verified.append({**row,"actual":actuals[row["Mercato"]],"played":True})
    eligible = 0
    import math
    for row in rows:
        try:
            p = float(row.get("Prob. stimata %"))
            if (row.get("Mercato") in ("PTS","AST","REB")
                and str(row.get("Scelta","")).lower() in ("over","under")
                and math.isfinite(p) and 0 <= p <= 100):
                eligible += 1
        except (TypeError, ValueError):
            continue
    return verified,eligible
