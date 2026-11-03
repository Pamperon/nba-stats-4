"""Read-only Basket Lab calibration audit. No odds API calls or database writes.

Run: python scripts/audit_calibration.py
Requires the same database environment variables as the application.
"""
from collections import defaultdict
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage


def summarize(rows):
    groups = defaultdict(lambda: {"n": 0, "wins": 0, "sum_p": 0.0, "sum_brier": 0.0})
    for market, bucket, n, wins, sum_p, sum_brier in rows:
        for key in ((market, "all"), (market, str(bucket))):
            group = groups[key]
            group["n"] += n
            group["wins"] += wins
            group["sum_p"] += sum_p
            group["sum_brier"] += sum_brier
    result = []
    for (market, bucket), value in sorted(groups.items()):
        n = value["n"]
        if not n:
            continue
        result.append({
            "market": market, "probability_bin": bucket,
            "n": n, "wins": value["wins"],
            "estimated_pct": round(100 * value["sum_p"] / n, 2),
            "observed_pct": round(100 * value["wins"] / n, 2),
            "gap_percentage_points": round(100 * (value["sum_p"] - value["wins"]) / n, 2),
            "brier": round(value["sum_brier"] / n, 5),
            "sample_warning": n < 100,
        })
    return result


def main():
    with storage.connection() as conn:
        bins = conn.execute("""
            SELECT d.market, d.probability_bin,
                   SUM(d.n), SUM(d.wins), SUM(d.sum_p), SUM(d.sum_brier)
            FROM nba_calibration_daily d
            JOIN nba_calibration_settled s
              ON s.scan_date=d.scan_date
             AND s.snapshot_job_id=d.snapshot_job_id
            GROUP BY d.market, d.probability_bin
            ORDER BY d.market, d.probability_bin
        """).fetchall()
        days = conn.execute("""
            SELECT scan_date, prediction_count, matched_count
            FROM nba_calibration_settled ORDER BY scan_date
        """).fetchall()
    coverage = [
        {"date": str(day), "expected": expected, "matched": matched,
         "missing": expected - matched,
         "coverage_pct": round(100 * matched / expected, 2) if expected else None}
        for day, expected, matched in days
    ]
    print(json.dumps({
        "read_only": True,
        "notes": [
            "All lines, not only published recommendations.",
            "One snapshot per settled day; not necessarily independent player outcomes.",
            "A missing match is not automatically a losing prediction.",
            "Do not fit a production correction on these same observations without held-out validation.",
        ],
        "markets_and_bins": summarize(bins),
        "settlement_coverage": coverage,
    }, indent=2))


if __name__ == "__main__":
    main()
