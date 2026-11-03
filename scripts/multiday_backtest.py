"""Read-only multi-day ticket evaluation against saved pregame snapshots.

No bookmaker requests, no database writes. Only historical dates with a
saved snapshot and settled ESPN results contribute to performance.
"""
import argparse
import json
import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
import settle_espn
from scripts.recommendation_backtest import evaluate

URL = "https://nba-stats-4.onrender.com/api/saved/archive"

def aggregate(day_reports):
    groups = {}
    for day in day_reports:
        for name, ticket in day["proposals"].items():
            entry = groups.setdefault(name, {"complete": 0, "settled": 0,
                                             "wins": 0, "profit_units": 0.0,
                                             "missing_results": 0, "verified_legs": 0,
                                             "sum_brier": 0.0, "sum_abs_error": 0.0,
                                             "sum_outcomes": 0, "sum_probabilities": 0.0})
            entry["complete"] += int(ticket["complete"])
            entry["missing_results"] += ticket["missing_results"]
            for leg in ticket.get("legs", []):
                try:
                    probability = float(leg["estimated_probability"]) / 100
                    outcome = leg["win"]
                    if outcome is None or not math.isfinite(probability) or not 0 <= probability <= 1:
                        continue
                    entry["verified_legs"] += 1
                    entry["sum_outcomes"] += int(outcome)
                    entry["sum_probabilities"] += probability
                    entry["sum_brier"] += (probability - int(outcome)) ** 2
                    entry["sum_abs_error"] += abs(probability - int(outcome))
                except (KeyError, ValueError, TypeError):
                    continue
            if ticket["settled"]:
                entry["settled"] += 1
                entry["wins"] += int(ticket["unit_profit"] > 0)
                entry["profit_units"] += ticket["unit_profit"]
    for entry in groups.values():
        n = entry["verified_legs"]
        entry["brier_score"] = round(entry["sum_brier"] / n, 4) if n else None
        entry["mean_absolute_error"] = round(entry["sum_abs_error"] / n, 4) if n else None
        entry["actual_hit_rate"] = round(entry["sum_outcomes"] / n, 4) if n else None
        entry["mean_predicted_probability"] = round(entry["sum_probabilities"] / n, 4) if n else None
        entry["calibration_gap"] = (round(entry["mean_predicted_probability"] - entry["actual_hit_rate"], 4)
                                    if n else None)
        entry["sample_sufficient"] = n >= 200
        del entry["sum_outcomes"]
        del entry["sum_probabilities"]
        del entry["sum_brier"]
        del entry["sum_abs_error"]
        entry["profit_units"] = round(entry["profit_units"], 4)
        entry["roi"] = (round(entry["profit_units"] / entry["settled"], 4)
                        if entry["settled"] else None)
    return groups

def analyze_dates(dates, session=requests):
    reports, skipped = [], []
    today = datetime.now(ZoneInfo("Europe/Rome")).date()
    for day in dates:
        parsed = date.fromisoformat(day)
        if parsed > today:
            skipped.append({"date": day, "reason": "future_date"})
            continue
        try:
            response = session.get(URL, params={"date": day}, timeout=100)
            if response.status_code in (400, 404):
                skipped.append({"date": day, "reason": "archive_unavailable",
                                "http_status": response.status_code})
                continue
            response.raise_for_status()
            archive = response.json()
            if archive.get("date") != day:
                raise ValueError("Archive date mismatch")
            rows = archive.get("results") or []
            if not rows:
                skipped.append({"date": day, "reason": "empty_archive"})
                continue
            verified, eligible_count = settle_espn.settle_archive(archive, day)
            reports.append({"date": day, "saved_at": archive.get("saved_at"),
                            "archive_rows": len(rows), "eligible": eligible_count,
                            "verified": len(verified),
                            "proposals": evaluate(rows, verified)})
        except (requests.RequestException, ValueError, KeyError) as exc:
            skipped.append({"date": day, "reason": "verification_error",
                            "error": str(exc)[:160]})
    return {"days_checked": len(dates), "days_evaluated": len(reports),
            "days_skipped": skipped, "daily": reports,
            "summary": aggregate(reports),
            "odds_api_calls": 0, "database_writes": 0}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="+", required=True)
    args = parser.parse_args()
    print(json.dumps(analyze_dates(args.dates), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
