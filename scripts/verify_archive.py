"""Read-only end-to-end archive verification against finalized ESPN results.

Usage: python -m scripts.verify_archive --file archive.json --date 2026-10-24
Never connects to PostgreSQL or OddsPapi and never writes predictions.
"""
import argparse
import json
from pathlib import Path

import calibration
import settle_espn


def run(path, date):
    archive = json.loads(Path(path).read_text(encoding="utf-8"))
    if archive.get("date") != date:
        raise ValueError("Archive date does not match requested ESPN date")
    verified, eligible = settle_espn.settle_archive(archive, date)
    aggregates = calibration.aggregate(verified)
    matched = sum(item["n"] for item in aggregates.values())
    coverage = matched / eligible if eligible else 0.0
    report = {
        "date": date,
        "archived_predictions": len(archive.get("results", [])),
        "eligible_predictions": eligible,
        "verified_predictions": matched,
        "coverage": round(coverage, 4),
        "markets": {
            market: sum(v["n"] for (m, _), v in aggregates.items() if m == market)
            for market in calibration.MARKETS
        },
        "ready_for_settlement": eligible > 0 and coverage >= 0.90,
        "odds_api_calls": 0,
        "database_writes": 0,
    }
    print(json.dumps(report, indent=2))
    if not report["ready_for_settlement"]:
        raise ValueError(f"Insufficient archive coverage: {matched}/{eligible}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    run(args.file, args.date)
