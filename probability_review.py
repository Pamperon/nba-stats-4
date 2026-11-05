"""Descriptive review of frozen published probabilities; never adjusts predictions."""
import math


def summarize(lines):
    valid = []
    for row in lines:
        if row.get('status') not in ('won', 'lost'):
            continue
        raw = row.get('Prob. stimata %', row.get('estimated_probability'))
        if isinstance(raw, bool):
            continue
        try:
            p = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(p) and 0 <= p <= 100:
            valid.append((p, row['status'] == 'won'))
    def group(sample):
        n = len(sample)
        return {'n': n, 'estimated_pct': round(sum(p for p, _ in sample)/n, 1) if n else None,
                'observed_pct': round(100*sum(win for _, win in sample)/n, 1) if n else None}
    return {**group(valid), 'bins': [dict(label=f'{low}–{low+10}%', **group([
        item for item in valid if low <= item[0] < low+10 or low == 90 and item[0] == 100
    ])) for low in range(0, 100, 10) if any(low <= p < low+10 or low == 90 and p == 100 for p, _ in valid)]}
