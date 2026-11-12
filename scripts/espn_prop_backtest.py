"""Offline historical NBA prop audit. Never calls OddsPapi or changes database.

Run: python scripts/espn_prop_backtest.py --start 2026-10-23 --end 2026-10-30
Requires DATABASE_URL, requests, psycopg. Writes a local JSON report only.
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
from zoneinfo import ZoneInfo

import psycopg
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ET = ZoneInfo("America/New_York")
MARKETS = ("PTS", "AST", "REB")
BANDS = (("Tripla", 1.20, 1.39), ("Doppia", 1.40, 1.69), ("Singola", 1.70, 2.00))
TEAM_ALIASES = {"LA Clippers": "Los Angeles Clippers", "NY Knicks": "New York Knicks",
                "GS Warriors": "Golden State Warriors", "SA Spurs": "San Antonio Spurs"}
session = requests.Session()
session.headers.update({"User-Agent": "BasketLabHistoricalAudit/1.0 (public ESPN scoreboard)"})

def norm(value):
    s = unicodedata.normalize("NFKD", str(value or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())

def get_json(url, params=None):
    for attempt in range(3):
        try:
            response = session.get(url, params=params, timeout=22)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt * 2)

def dates(start, end):
    day = start
    while day <= end:
        yield day
        day += dt.timedelta(days=1)

def games_for_dates(start, end):
    """ESPN date is US Eastern; retrieve adjacent days for boundary coverage."""
    events = {}
    for day in dates(start - dt.timedelta(days=1), end + dt.timedelta(days=1)):
        data = get_json(BASE + "/scoreboard", {"dates": day.strftime("%Y%m%d"), "limit": 100})
        for event in data.get("events", []):
            events[str(event["id"])] = event
    return events

def teams_for_event(event):
    competitors = event.get("competitions", [{}])[0].get("competitors", [])
    return {norm(c.get("team", {}).get("displayName")) for c in competitors}

def parse_summary(event_id):
    data = get_json(BASE + "/summary", {"event": event_id})
    stats = {}
    for team in data.get("boxscore", {}).get("players", []):
        team_name = team.get("team", {}).get("displayName", "")
        for group in team.get("statistics", []):
            labels = [str(x).upper() for x in group.get("labels", [])]
            for entry in group.get("athletes", []):
                athlete = entry.get("athlete", {})
                values = entry.get("stats", [])
                if not isinstance(values, list) or not labels:
                    continue
                row = {}
                for market in MARKETS:
                    if market in labels:
                        try:
                            row[market] = float(values[labels.index(market)])
                        except (IndexError, TypeError, ValueError):
                            pass
                if len(row) == 3:
                    stats[(norm(team_name), norm(athlete.get("displayName")))] = row
    return stats

def load_predictions(conn, start, end):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.scan_date, s.payload->'results'
            FROM nba_scan_snapshots s
            JOIN nba_calibration_settled c ON c.snapshot_job_id = s.job_id
            WHERE s.scan_date BETWEEN %s AND %s
            ORDER BY s.scan_date
        """, (start, end))
        result = []
        for scan_date, rows in cur.fetchall():
            for row in rows or []:
                try:
                    odds = float(row["Quota"])
                    line = float(row["Linea"])
                    market = str(row["Mercato"]).upper()
                    choice = str(row["Scelta"]).lower()
                except (ValueError, TypeError, KeyError):
                    continue
                band = next((name for name, low, high in BANDS if low - 1e-8 <= odds <= high + 1e-8), None)
                if band is None or market not in MARKETS or choice not in ("over", "under"):
                    continue
                result.append((scan_date, row, band, line, market, choice, odds))
        return result

def identify_event(scan_date, row, events):
    fixture = norm(row.get("Partita"))
    # Require BOTH team names from the archived fixture, not just the player's team.
    candidates = []
    for event in events.values():
        if event.get("status", {}).get("type", {}).get("completed") is not True:
            continue
        event_day = dt.datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(ET).date()
        if abs((event_day - scan_date).days) > 1:
            continue
        comps = event.get("competitions", [{}])[0].get("competitors", [])
        names = [norm(c.get("team", {}).get("displayName")) for c in comps]
        if len(names) != 2 or not all(name and name in fixture for name in names):
            continue
        candidates.append(event)
    return candidates[0] if len(candidates) == 1 else None

def summarize(rows):
    groups = collections.defaultdict(list)
    for r in rows:
        for key in (("all", "all"), ("band", r["band"]), ("market", r["market"]),
                    ("minutes", r["minutes_group"]), ("band_minutes", r["band"] + "/" + r["minutes_group"]),
                    ("market_minutes", r["market"] + "/" + r["minutes_group"])):
            groups[key].append(r)
    report = {}
    for (kind, key), group in sorted(groups.items()):
        wins = sum(x["win"] for x in group)
        predictions = [x["predicted"] for x in group if x["predicted"] is not None]
        report.setdefault(kind, {})[key] = {
            "n": len(group), "wins": wins, "hit_rate": round(wins / len(group), 4),
            "avg_odds": round(sum(x["odds"] for x in group) / len(group), 3),
            "flat_stake_roi": round(sum(x["odds"] - 1 if x["win"] else -1 for x in group) / len(group), 4),
            "predicted_avg": round(sum(predictions) / len(predictions), 4) if predictions else None,
            "predicted_n": len(predictions)
        }
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--end", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--output", default="espn_prop_backtest_report.json")
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("end precedes start")
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10, sslmode="require") as conn:
        predictions = load_predictions(conn, args.start, args.end)
    events = games_for_dates(args.start, args.end)
    boxscores = {}
    outcomes, missing = [], collections.Counter()
    dedup = set()
    for scan_date, row, band, line, market, choice, odds in predictions:
        key = (scan_date.isoformat(), norm(row.get("Giocatore")), norm(row.get("Partita")), market, choice, line)
        if key in dedup:
            missing["duplicate"] += 1
            continue
        dedup.add(key)
        event = identify_event(scan_date, row, events)
        if not event:
            missing["fixture_unmatched_or_unfinished"] += 1
            continue
        event_id = str(event["id"])
        if event_id not in boxscores:
            try:
                boxscores[event_id] = parse_summary(event_id)
            except (requests.RequestException, ValueError):
                boxscores[event_id] = {}
                missing["boxscore_request_failed"] += 1
        team = norm(TEAM_ALIASES.get(str(row.get("Squadra")), row.get("Squadra")))
        player = norm(row.get("Giocatore"))
        if team == norm("Squadra non identificata"):
            missing["unknown_player_team"] += 1
            continue
        candidates = [v for (t, p), v in boxscores[event_id].items()
                      if p == player and t == team]
        if len(candidates) != 1:
            missing["player_unmatched_or_dnp"] += 1
            continue
        actual = candidates[0][market]
        if actual == line:
            missing["push"] += 1
            continue
        try:
            avg = float(row["Minuti medi"])
            recent = float(row["Minuti ultime 5"])
            minutes_group = ("drop_25_plus" if avg > 0 and recent < avg * .75 else
                             "drop_10_to_25" if avg > 0 and recent < avg * .90 else
                             "drop_0_to_10" if recent < avg else "stable_or_rising")
        except (KeyError, ValueError, TypeError):
            missing["minutes_missing"] += 1
            continue
        try:
            predicted = float(row["Prob. stimata %"]) / 100
            if not 0 <= predicted <= 1:
                predicted = None
        except (ValueError, TypeError, KeyError):
            predicted = None
        outcomes.append({"date": scan_date.isoformat(), "player": row.get("Giocatore"),
                         "fixture": row.get("Partita"), "market": market, "choice": choice,
                         "line": line, "odds": odds, "actual": actual,
                         "win": int(actual > line if choice == "over" else actual < line),
                         "band": band, "minutes_group": minutes_group,
                         "minutes_average": avg, "minutes_last5": recent, "predicted": predicted,
                         "espn_event_id": event_id})
    report = {"period": [str(args.start), str(args.end)],
              "source": "ESPN public scoreboard and final boxscore; archived pregame Supabase snapshots",
              "odds_api_calls": 0, "database_writes": 0,
              "archive_lines": len(predictions), "unique_archive_lines": len(dedup),
              "verified_outcomes": len(outcomes), "excluded": dict(missing),
              "groups": summarize(outcomes), "outcomes": outcomes}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in report.items() if k != "outcomes"}, indent=2))
    coverage = len(outcomes) / len(dedup) if dedup else 0
    print(f"VERIFIED COVERAGE: {len(outcomes)}/{len(dedup)} ({coverage:.1%})")
    if coverage < .75:
        print("WARNING: LOW COVERAGE. Do not draw conclusions about minutes or betting ROI.", file=sys.stderr)
    if not outcomes:
        sys.exit("No verifiable outcomes; inspect fixture/team mapping before drawing conclusions")

if __name__ == "__main__":
    main()
