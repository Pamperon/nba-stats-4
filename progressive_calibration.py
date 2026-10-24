"""Safely apply validated historical calibration to future scan rows.

Read-only: the caller owns persistence. Fail closed when validation is sparse.
"""
import math
import calibration

def apply(rows, daily_rows):
    aggregates = calibration.approved_adjustments(daily_rows)
    if not aggregates:
        return rows, {"active": False, "adjusted": 0}
    adjusted = 0
    output = []
    for original in rows:
        row = dict(original)
        try:
            raw = float(row["Prob. stimata %"])
            market = str(row["Mercato"]).upper()
            if market not in calibration.MARKETS or not math.isfinite(raw) or not 0 <= raw <= 100:
                output.append(row)
                continue
            candidate = calibration.calibrated_probability(market, raw / 100, aggregates) * 100
            row["Prob. grezza %"] = raw
            row["Prob. stimata %"] = round(candidate, 1)
            price = float(row["Quota"])
            if math.isfinite(price) and price > 1:
                row["Value stimato %"] = round((candidate / 100 * price - 1) * 100, 1)
            if abs(candidate - raw) > 0.0001:
                adjusted += 1
        except (KeyError, ValueError, TypeError):
            pass
        output.append(row)
    return output, {"active": True, "adjusted": adjusted}
