"""Walk-forward evaluation of candidate probability calibration.

Each test day is evaluated using ONLY earlier daily aggregates.
Uses exact Brier delta identity; no per-prediction retention needed.
"""
from collections import defaultdict
from calibration import calibrated_probability

def walk_forward(daily_rows, min_samples=200, prior_strength=400, max_adjustment=0.08):
    """Daily rows: date, market, probability_bin, n, wins, sum_p, sum_brier.

    This evaluates a constant per-bin additive correction. Each date must have
    exactly one aggregate per market/bin. Test day is never used for its training.
    """
    dates = sorted({str(r["date"]) for r in daily_rows})
    prior = defaultdict(lambda: dict(n=0, wins=0, sum_p=0.0, sum_brier=0.0))
    total_n = 0
    base_brier = 0.0
    candidate_brier = 0.0
    adjusted_n = 0
    daily = []
    for day in dates:
        today = [r for r in daily_rows if str(r["date"]) == day]
        day_n = day_base = day_candidate = day_adjusted = 0
        for r in today:
            n = int(r["n"])
            if n <= 0:
                continue
            market = r["market"]
            bucket = int(r["probability_bin"])
            key = (market, bucket)
            prev = prior[key]
            mean_p = float(r["sum_p"]) / n
            if prev["n"]:
                aggregates = [{"market":market,"probability_bin":bucket,
                               "n":prev["n"],"observed":prev["wins"]/prev["n"],
                               "predicted":prev["sum_p"]/prev["n"]}]
            else:
                aggregates = []
            # Use center of probability bucket solely to look up the adjustment.
            # The additive correction is identical for every p in that bucket.
            center = (bucket+5)/100
            delta = calibrated_probability(market,center,aggregates,
                         min_samples,prior_strength,max_adjustment)-center
            base = float(r["sum_brier"])
            # Exact for additive delta without clipping; skip bins near boundaries
            # where per-prediction clipping could invalidate the identity.
            if bucket == 0 or bucket == 90:
                delta = 0.0
            candidate = base + 2*delta*(float(r["sum_p"])-int(r["wins"])) + n*delta**2
            day_n += n
            day_base += base
            day_candidate += candidate
            if abs(delta)>1e-12:
                day_adjusted += n
        if day_n:
            daily.append({"date":day,"n":day_n,"brier_original":day_base/day_n,
                          "brier_candidate":day_candidate/day_n,
                          "adjusted_predictions":day_adjusted})
            total_n += day_n
            base_brier += day_base
            candidate_brier += day_candidate
            adjusted_n += day_adjusted
        for r in today:
            key=(r["market"],int(r["probability_bin"]))
            for field in ("n","wins","sum_p","sum_brier"):
                prior[key][field] += r[field]
    return {"days":len(daily),"n":total_n,"adjusted_predictions":adjusted_n,
            "brier_original":base_brier/total_n if total_n else None,
            "brier_candidate":candidate_brier/total_n if total_n else None,
            "improved":candidate_brier < base_brier if adjusted_n else False,
            "daily":daily}
