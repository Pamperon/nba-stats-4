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
              "groups": summarize(verified), "odds_api_calls": 0, "database_writes": 0}
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
