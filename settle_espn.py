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

def final_events(scan_date):
    # NBA games can cross midnight UTC; ESPN dates use league schedule dates.
    data = fetch(BASE + "/scoreboard", dates=scan_date.replace("-", ""), limit=100)
    events = data.get("events", [])
    if not events:
        raise ValueError("ESPN has no events for requested date")
    if any(not (e.get("status",{}).get("type",{}).get("completed") is True) for e in events):
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
    return found

def settle_archive(snapshot, scan_date):
    """Returns verified rows + counts; caller decides whether to persist."""
    events = final_events(scan_date)
    lookup = {}
    for event in events:
        summary = fetch(BASE + "/summary", event=event["id"])
        stats = player_stats(summary)
        competitors = (event.get("competitions") or [{}])[0].get("competitors",[])
        teams = [(c.get("team") or {}).get("displayName","") for c in competitors]
        if len(teams) != 2 or not stats:
            raise ValueError("Missing ESPN teams or player boxscore")
        for team in teams:
            key = engine.normalized_name(team)
            if key in lookup:
                raise ValueError("Duplicate team across ESPN games")
            lookup[key] = (frozenset(engine.normalized_name(t) for t in teams),stats)
    saved_at = snapshot.get("scan_finished_at") or snapshot.get("saved_at")
    if not saved_at:
        raise ValueError("Snapshot has no verifiable pregame timestamp")
    from datetime import timezone
    snapshot_time = datetime.fromisoformat(str(saved_at).replace("Z","+00:00"))
    if snapshot_time.tzinfo is None:
        raise ValueError("Timezone missing from snapshot timestamp")
    snapshot_time = snapshot_time.astimezone(timezone.utc)
    for event in events:
        start = event.get("date")
        if not start:
            raise ValueError("ESPN event start time unavailable")
        tipoff = datetime.fromisoformat(start.replace("Z","+00:00"))
        if snapshot_time >= tipoff:
            raise ValueError("Snapshot saved after at least one game's tipoff")
    rows = snapshot.get("results",[])
    if not rows:
        raise ValueError("No archived predictions")
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
