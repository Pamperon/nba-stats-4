"""Shared minutes risk assessment; this audit never changes probabilities.

The versioned recommendation policy may screen flagged rows separately.
"""
import math

def assess(row):
    try:
        average = float(row["Minuti medi"])
        recent = float(row["Minuti ultime 5"])
        if not all(map(math.isfinite, (average, recent))) or average <= 0 or recent < 0:
            return "unknown"
        if int(row.get("Partite", 0)) < 15:
            return "unknown"
        # A substantial recent reduction may invalidate the historical role.
        return "watch" if recent < average * 0.75 and average - recent >= 5 else "normal"
    except (KeyError, ValueError, TypeError):
        return "unknown"

def audit(rows):
    counts = {"watch": 0, "normal": 0, "unknown": 0}
    for row in rows:
        counts[assess(row)] += 1
    return {"mode": "shadow", "rows": len(rows), "counts": counts,
            "changes_to_probabilities": 0, "excluded_picks": 0, "odds_api_calls": 0}
