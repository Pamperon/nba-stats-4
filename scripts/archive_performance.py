"""Read-only ESPN archive performance, by market and odds bands.
No database or bookmaker API calls. No model changes.
"""
import argparse
import collections
import json
import math
import requests
import settle_espn

BANDS = ((1.20, 1.40, "tripla"), (1.40, 1.70, "doppia"),
         (1.70, 2.01, "singola"))

def eligible(row):
    try:
        p = float(row.get("Prob. stimata %"))
        return (row.get("Mercato") in ("PTS", "AST", "REB")
                and str(row.get("Scelta", "")).lower() in ("over", "under")
                and math.isfinite(p) and 0 <= p <= 100)
    except (ValueError, TypeError):
        return False

def summarize(rows):
    groups = collections.defaultdict(list)
    for row in rows:
        if not eligible(row):
            continue
        try:
            line = float(row["Linea"])
            actual = float(row["actual"])
            price = float(row["Quota"])
            p = float(row["Prob. stimata %"]) / 100
            if not all(map(math.isfinite, (line, actual, price, p))) or price <= 1:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        if actual == line:
            continue
        win = actual > line if row["Scelta"].lower() == "over" else actual < line
        entry = (int(win), price, p)
        groups["overall"].append(entry)
        groups["market:" + row["Mercato"]].append(entry)
        for lo, hi, label in BANDS:
            if lo <= price < hi:
                groups["odds:" + label].append(entry)
                groups["market:" + row["Mercato"] + ":odds:" + label].append(entry)
                break
    result = {}
    for key, entries in sorted(groups.items()):
        n = len(entries)
        wins = sum(w for w, _, _ in entries)
        profit = sum((odds - 1) if w else -1 for w, odds, _ in entries)
        result[key] = {
            "n": n, "wins": wins, "losses": n - wins,
            "win_rate": round(wins / n, 4),
            "mean_predicted": round(sum(p for _, _, p in entries) / n, 4),
            "brier": round(sum((p-w)**2 for w, _, p in entries) / n, 4),
            "flat_stake_roi": round(profit / n, 4),
            "flat_stake_units": round(profit, 2),
        }
    return result


def summarize_unique_opportunities(rows, candidate_rows=None):
    """One highest-value line per athlete, market and fixture.

    Multiple thresholds remain in the full report; this view prevents
    correlated alternate lines from being treated as independent samples.
    """
    best = {}
    for row in (candidate_rows if candidate_rows is not None else rows):
        if not eligible(row):
            continue
        try:
            price = float(row["Quota"])
            probability = float(row["Prob. stimata %"]) / 100
            line = float(row["Linea"])
            if not all(map(math.isfinite, (price, probability, line))) or price <= 1:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        identity = str(row.get("ESPN ID") or "").strip()
        if not identity:
            identity = settle_espn.engine.espn_player_key(row.get("Giocatore", ""))
        key = (str(row.get("Partita", "")), str(row.get("Squadra", "")),
               identity, str(row.get("Mercato", "")))
        value = probability * price - 1
        tie = (value, probability, -line)
        if key not in best or tie > best[key][0]:
            best[key] = (tie, row)
    matched = {}
    for row in rows:
        key = (str(row.get("Partita", "")), str(row.get("Squadra", "")),
               str(row.get("ESPN ID") or "").strip() or settle_espn.engine.espn_player_key(row.get("Giocatore", "")),
               str(row.get("Mercato", "")), str(row.get("Scelta", "")).lower(), str(row.get("Linea", "")))
        matched[key] = row
    selected = []
    for _, original in best.values():
        key = (str(original.get("Partita", "")), str(original.get("Squadra", "")),
               str(original.get("ESPN ID") or "").strip() or settle_espn.engine.espn_player_key(original.get("Giocatore", "")),
               str(original.get("Mercato", "")), str(original.get("Scelta", "")).lower(), str(original.get("Linea", "")))
        if key in matched:
            selected.append(matched[key])
    return {"unique_player_market_games": len(best), "verified_selections": len(selected),
            "selection_rule": "highest pregame estimated expected value per player-market-game",
            "groups": summarize(selected)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-10-24")
    args = parser.parse_args()
    url = "https://nba-stats-4.onrender.com/api/saved/archive"
    response = requests.get(url, params={"date": args.date}, timeout=100)
    response.raise_for_status()
    archive = response.json()
    if archive.get("date") != args.date:
        raise ValueError("Archive date mismatch")
    verified, count = settle_espn.settle_archive(archive, args.date)
    report = {"date": args.date, "eligible": count, "verified": len(verified),
              "groups": summarize(verified),
              "one_line_per_player_market": summarize_unique_opportunities(verified, archive["results"]),
              "odds_api_calls": 0, "database_writes": 0}
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
