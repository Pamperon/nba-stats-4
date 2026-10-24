"""Incremental calibration statistics. No raw prediction retention required after settlement.

Safety: only finalized games, idempotent per date/snapshot, no automatic deletion.
"""
from datetime import datetime, timezone
import math
import psycopg
from psycopg.types.json import Jsonb
import storage

BINS = tuple(range(0, 100, 10))
MARKETS = ("PTS", "AST", "REB")

def initialize():
    with storage.connection() as conn:
        conn.execute("""
          CREATE TABLE IF NOT EXISTS nba_calibration_daily (
            scan_date DATE NOT NULL,
            snapshot_job_id TEXT NOT NULL,
            market TEXT NOT NULL,
            probability_bin INTEGER NOT NULL,
            n INTEGER NOT NULL,
            wins INTEGER NOT NULL,
            sum_p DOUBLE PRECISION NOT NULL,
            sum_brier DOUBLE PRECISION NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (scan_date, snapshot_job_id, market, probability_bin)
          )
        """)
        conn.execute("""
          CREATE TABLE IF NOT EXISTS nba_calibration_settled (
            scan_date DATE PRIMARY KEY,
            snapshot_job_id TEXT NOT NULL,
            prediction_count INTEGER NOT NULL,
            matched_count INTEGER NOT NULL,
            settled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
          )
        """)

def aggregate(rows):
    """rows: pregame prediction with independently verified actual statistic.

    Requires market, probability (0..100), line, choice, actual, played.
    No missing outcomes are imputed as losses.
    """
    out = {}
    for row in rows:
        try:
            market = str(row["Mercato"]).upper()
            p = float(row.get("Prob. grezza %", row["Prob. stimata %"])) / 100
            line = float(row["Linea"])
            actual = float(row["actual"])
            choice = str(row["Scelta"]).lower()
            if (market not in MARKETS or not math.isfinite(p)
                or not 0 <= p <= 1 or not math.isfinite(actual)
                or not math.isfinite(line) or choice not in ("over", "under")
                or row.get("played") is not True):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        win = int(actual > line) if choice == "over" else int(actual < line)
        if actual == line:
            continue  # push: not a binary result
        bucket = min(90, int(p * 10) * 10)
        key = (market, bucket)
        stat = out.setdefault(key, dict(n=0, wins=0, sum_p=0.0, sum_brier=0.0))
        stat["n"] += 1
        stat["wins"] += win
        stat["sum_p"] += p
        stat["sum_brier"] += (p-win)**2
    return out

def settle(scan_date, snapshot_job_id, rows, expected_count, min_coverage=0.90):
    """Atomic daily replacement. Caller must verify ESPN game completion and identities.

    Never deletes raw snapshots. Rejects insufficiently matched days.
    """
    if expected_count <= 0:
        raise ValueError("Empty archive cannot be settled")
    stats = aggregate(rows)
    matched = sum(x["n"] for x in stats.values())
    if matched / expected_count < min_coverage:
        raise ValueError(f"Insufficient verified coverage: {matched}/{expected_count}")
    with storage.connection() as conn:
        prior = conn.execute(
            "SELECT snapshot_job_id FROM nba_calibration_settled WHERE scan_date=%s",
            (scan_date,)).fetchone()
        if prior and prior[0] != snapshot_job_id:
            raise ValueError("Different snapshot already settled; manual review required")
        conn.execute("DELETE FROM nba_calibration_daily WHERE scan_date=%s", (scan_date,))
        for (market, bucket), v in stats.items():
            conn.execute("""
                INSERT INTO nba_calibration_daily
                (scan_date,snapshot_job_id,market,probability_bin,n,wins,sum_p,sum_brier)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (scan_date,snapshot_job_id,market,bucket,v["n"],v["wins"],v["sum_p"],v["sum_brier"]))
        conn.execute("""
            INSERT INTO nba_calibration_settled
            (scan_date,snapshot_job_id,prediction_count,matched_count)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT(scan_date) DO UPDATE SET
              snapshot_job_id=EXCLUDED.snapshot_job_id,
              prediction_count=EXCLUDED.prediction_count,
              matched_count=EXCLUDED.matched_count,
              settled_at=NOW()
        """, (scan_date,snapshot_job_id,expected_count,matched))
    return {"date": scan_date, "matched": matched, "expected": expected_count,
            "coverage": matched/expected_count, "odds_api_calls": 0}

def summary():
    with storage.connection() as conn:
        rows = conn.execute("""
            SELECT market,probability_bin,SUM(n),SUM(wins),SUM(sum_p),SUM(sum_brier)
            FROM nba_calibration_daily
            GROUP BY market,probability_bin ORDER BY market,probability_bin
        """).fetchall()
    return [{"market":m,"probability_bin":b,"n":n,"wins":w,
             "predicted":sp/n,"observed":w/n,"brier":sb/n}
            for m,b,n,w,sp,sb in rows if n]

def calibrated_probability(market, raw_probability, aggregates, min_samples=20,
                           prior_strength=200, max_adjustment=0.03):
    """Conservative shrinkage calibration. Returns unchanged p on sparse history.

    Offline candidate only: do not apply in live prediction engine until validated
    on later, unseen NBA dates. Input probabilities use [0, 1].
    """
    p = float(raw_probability)
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Probability must be between 0 and 1")
    bucket = min(90, int(p * 10) * 10)
    matching = [r for r in aggregates if r.get("market") == market
                and r.get("probability_bin") == bucket]
    if len(matching) != 1 or matching[0]["n"] < min_samples:
        pooled = [r for r in aggregates if r.get("market") == market]
        total = sum(r["n"] for r in pooled)
        if total < 50:
            return p
        observed = sum(r["observed"] * r["n"] for r in pooled) / total
        predicted = sum(r["predicted"] * r["n"] for r in pooled) / total
        adjustment = (observed - predicted) * total / (total + 500)
        return max(0.001, min(0.999, p + max(-max_adjustment, min(max_adjustment, adjustment))))
    r = matching[0]
    # Shrink observed hit rate toward the average forecast in the same bucket.
    adjustment = (r["observed"] - r["predicted"]) * r["n"] / (r["n"] + prior_strength)
    return max(0.001, min(0.999, p + max(-max_adjustment,
                                         min(max_adjustment, adjustment))))

def approved_adjustments(daily_rows, min_days=2, min_verified=100,
                         min_improvement=0.001):
    """Return historical calibration bins only after walk-forward improvement.

    Fail closed on insufficient samples, short history, or unvalidated lift.
    The latest day's labels are never used for predictions on that day.
    """
    from calibration_validation import walk_forward
    report = walk_forward(daily_rows)
    if (report["days"] < min_days or report["n"] < min_verified
            or report["adjusted_predictions"] < min_verified
            or report["brier_original"] is None
            or report["brier_candidate"] is None
            or report["brier_original"] - report["brier_candidate"] < min_improvement):
        return []
    by_bin = {}
    for r in daily_rows:
        key = (r["market"], int(r["probability_bin"]))
        stat = by_bin.setdefault(key, {"n":0,"wins":0,"sum_p":0.0})
        for field in ("n","wins","sum_p"):
            stat[field] += r[field]
    return [{"market":market,"probability_bin":bucket,
             "n":v["n"],"observed":v["wins"]/v["n"],
             "predicted":v["sum_p"]/v["n"]}
            for (market,bucket),v in by_bin.items() if v["n"]]
