"""Read-only pregame single/double/triple candidate backtest.

This is an explicit proposed selection policy, NOT a claim that it matches
the current web UI. Never use ESPN outcomes when choosing picks.
"""
import math
import settle_espn
from scripts.archive_performance import eligible

CATEGORIES = (("singola", 1, 1.70, 2.01),
              ("doppia", 2, 1.40, 1.70),
              ("tripla", 3, 1.20, 1.40))

def player_key(row):
    athlete_id = str(row.get("ESPN ID") or "").strip()
    return (str(row.get("Partita") or ""), str(row.get("Squadra") or ""),
            athlete_id or settle_espn.engine.espn_player_key(row.get("Giocatore", "")))

def line_key(row):
    return (player_key(row), str(row.get("Mercato") or ""),
            str(row.get("Scelta") or "").lower(), str(row.get("Linea") or ""))

def select_pregame(rows):
    """Max estimated value within each price band, one pick per player."""
    output = {}
    for label, count, low, high in CATEGORIES:
        candidates = []
        for row in rows:
            if not eligible(row):
                continue
            if str(row.get("Stato analisi", "")).strip().lower() == "non valutabile":
                continue
            try:
                price = float(row["Quota"])
                probability = float(row["Prob. stimata %"]) / 100
                line = float(row["Linea"])
                if not all(map(math.isfinite, (price, probability, line))):
                    continue
                if not low <= price < high:
                    continue
            except (KeyError, ValueError, TypeError):
                continue
            estimated_ev = probability * price - 1
            if estimated_ev <= 0:
                continue
            candidates.append((estimated_ev, probability, row))
        candidates.sort(key=lambda item: (item[0], item[1],
                                          str(item[2].get("Giocatore", "")),
                                          str(item[2].get("Linea", ""))), reverse=True)
        # Prefer distinct games as well as distinct players. When there are
        # insufficient independent fixtures, allow another player from a used
        # fixture rather than silently return an incomplete ticket.
        chosen, used_players, used_games = [], set(), set()
        for distinct_games_only in (True, False):
            for _, _, row in candidates:
                key = player_key(row)
                game = str(row.get("Partita") or "")
                if key in used_players or (distinct_games_only and game in used_games):
                    continue
                chosen.append(row)
                used_players.add(key)
                used_games.add(game)
                if len(chosen) == count:
                    break
            if len(chosen) == count:
                break
        output[label] = chosen
    return output

def evaluate(archive_rows, verified_rows):
    """Report unresolved legs explicitly; never replace with other lines."""
    lookup = {line_key(row): row for row in verified_rows}
    report = {}
    for category, chosen in select_pregame(archive_rows).items():
        legs = []
        combined_odds = 1.0
        for row in chosen:
            verified = lookup.get(line_key(row))
            price = float(row["Quota"])
            combined_odds *= price
            actual = None if verified is None else float(verified["actual"])
            line = float(row["Linea"])
            win = None if actual is None or actual == line else (
                actual > line if str(row["Scelta"]).lower() == "over" else actual < line)
            legs.append({"player": row.get("Giocatore"), "market": row.get("Mercato"),
                         "choice": row.get("Scelta"), "line": line, "odds": price,
                         "estimated_probability": row.get("Prob. stimata %"),
                         "actual": actual, "win": win})
        complete = len(legs) == next(c for name,c,_,_ in CATEGORIES if name == category)
        settled = complete and all(leg["win"] is not None for leg in legs)
        profit = (combined_odds - 1 if all(leg["win"] for leg in legs) else -1) if settled else None
        report[category] = {"legs": legs, "complete": complete,
                            "settled": settled, "combined_odds": round(combined_odds, 4),
                            "unit_profit": None if profit is None else round(profit, 4)}
    return report

def main():
    """Inspect a dated saved archive without bookmaker requests or database writes."""
    import argparse
    import json
    import requests
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    from datetime import date
    from zoneinfo import ZoneInfo
    from datetime import datetime
    endpoint = ("archive" if date.fromisoformat(args.date) < datetime.now(ZoneInfo("Europe/Rome")).date()
                else "latest")
    response = requests.get(
        f"https://nba-stats-4.onrender.com/api/saved/{endpoint}",
        params={"date": args.date}, timeout=100)
    response.raise_for_status()
    archive = response.json()
    if archive.get("date") not in (None, args.date):
        raise ValueError("Archive date mismatch")
    rows = archive.get("results") or []
    if not rows:
        raise ValueError("No saved pregame rows for requested date")
    proposals = {}
    for label, picks in select_pregame(rows).items():
        proposals[label] = [
            {"player": row.get("Giocatore"), "team": row.get("Squadra"),
             "match": row.get("Partita"), "market": row.get("Mercato"),
             "choice": row.get("Scelta"), "line": row.get("Linea"),
             "odds": row.get("Quota"),
             "estimated_probability": row.get("Prob. stimata %"),
             "estimated_value": row.get("Value stimato %"),
             "analysis_status": row.get("Stato analisi")}
            for row in picks]
    print(json.dumps({"date": args.date, "archive_rows": len(rows),
                      "proposals": proposals, "odds_api_calls": 0,
                      "database_writes": 0}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
