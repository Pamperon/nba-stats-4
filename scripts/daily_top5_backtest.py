"""Read-only Top-5 vs remaining daily lines evaluation from pregame snapshots.

Uses exactly the daily selection policy, never outcomes for selection.
No database writes or bookmaker requests.
"""
import argparse
import json
import math
import requests
import recommendations
import settle_espn


def score(chosen, verified):
    result = recommendations.evaluate({"policy": recommendations.DAILY_VERSION, "lines": chosen}, verified)
    settled = []
    for leg in result["lines"]:
        try:
            p = float(leg["estimated_probability"]) / 100
            odds = float(leg["odds"])
            if leg["win"] is None or not math.isfinite(p) or not 0 <= p <= 1 or not math.isfinite(odds) or odds <= 1:
                continue
        except (TypeError, ValueError):
            continue
        settled.append((int(leg["win"]), p, odds))
    n = len(settled)
    wins = sum(win for win, _, _ in settled)
    return {"selected": len(chosen), "resolved": n, "unresolved": len(chosen)-n,
            "wins": wins, "losses": n-wins,
            "hit_rate": round(wins/n, 4) if n else None,
            "mean_predicted": round(sum(p for _, p, _ in settled)/n, 4) if n else None,
            "brier": round(sum((p-win)**2 for win, p, _ in settled)/n, 4) if n else None,
            "mean_odds": round(sum(odds for _, _, odds in settled)/n, 4) if n else None,
            "flat_stake_roi": round(sum((odds-1 if win else -1) for win, _, odds in settled)/n, 4) if n else None}


def evaluate_day(archive, verified):
    rows = archive.get("results") or []
    # Use the archived pregame row set, never today's live lines or injuries.
    chosen = recommendations.select_daily(rows, screen_risks=False)["lines"]
    return {"date": archive["date"], "snapshot_job_id": archive.get("job_id"),
            "snapshot_saved_at": archive.get("saved_at"),
            "selection_origin": "reconstructed_from_pregame_snapshot",
            "risk_screen": "availability_and_minutes_watch_disabled_for_historical_reconstruction",
            "top5": score(chosen[:5], verified),
            "remaining": score(chosen[5:], verified),
            "total": score(chosen, verified)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="+", required=True)
    args = parser.parse_args()
    daily, skipped = [], []
    for day in args.dates:
        try:
            response = requests.get("https://nba-stats-4.onrender.com/api/saved/archive",
                                    params={"date": day}, timeout=100)
            response.raise_for_status()
            archive = response.json()
            if archive.get("date") != day:
                raise ValueError("Archive date mismatch")
            verified, _ = settle_espn.settle_archive(archive, day)
            daily.append(evaluate_day(archive, verified))
        except (requests.RequestException, ValueError, KeyError) as exc:
            skipped.append({"date": day, "reason": str(exc)[:180]})
    print(json.dumps({"daily": daily, "skipped": skipped,
                      "caution": "Retrospective reconstruction, not evidence of originally published picks. No future information may enter ranking.",
                      "odds_api_calls": 0, "database_writes": 0}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
