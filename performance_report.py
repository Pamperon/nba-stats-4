"""Read-only performance from settled daily aggregates; no bookmaker calls."""
from collections import defaultdict

def report(rows):
    groups = defaultdict(lambda: dict(n=0, wins=0, sum_p=0.0, sum_brier=0.0))
    for r in rows:
        n = int(r["n"])
        if n <= 0:
            continue
        market, date = str(r["market"]), str(r["date"])
        for key in (("all", "all"), ("market", market), ("date", date),
                    ("market_bin", market + ":" + str(r["probability_bin"]))):
            a = groups[key]
            a["n"] += n
            a["wins"] += int(r["wins"])
            a["sum_p"] += float(r["sum_p"])
            a["sum_brier"] += float(r["sum_brier"])
    def serialize(group):
        out = []
        for (kind, label), v in sorted(groups.items()):
            if kind != group:
                continue
            n = v["n"]
            out.append({"label": label, "n": n, "wins": v["wins"],
                        "hit_rate": v["wins"]/n, "predicted_rate": v["sum_p"]/n,
                        "calibration_gap": (v["wins"]-v["sum_p"])/n,
                        "brier": v["sum_brier"]/n})
        return out
    return {"overall": serialize("all"), "by_market": serialize("market"),
            "by_date": serialize("date"), "by_market_probability_bin": serialize("market_bin"),
            "combination_backtest_available": False,
            "combination_note": "Daily bins do not retain individual picks, odds or joint outcomes; ROI of singles/doubles/triples cannot be reconstructed reliably.",
            "odds_api_calls": 0}
