"""Read-only quality report for a saved NBA prediction archive.

Usage: python -m scripts.archive_audit /path/to/archive.json
No network access, bookmaker API calls, or database writes.
"""
import argparse
import collections
import json
import math

MARKETS = {"PTS","AST","REB"}

def audit(snapshot):
    rows = snapshot.get("results",[])
    fixtures = collections.Counter()
    markets = collections.Counter()
    eligible = 0
    excluded = collections.Counter()
    for row in rows:
        fixtures[row.get("Partita","")] += 1
        markets[row.get("Mercato","")] += 1
        try:
            p = float(row.get("Prob. stimata %"))
            if (row.get("Mercato") in MARKETS
                and str(row.get("Scelta","")).lower() in ("over","under")
                and math.isfinite(p) and 0 <= p <= 100):
                eligible += 1
                continue
        except (TypeError, ValueError):
            pass
        excluded[str(row.get("Stato analisi") or "unspecified")] += 1
    return {"date":snapshot.get("date"),"job_id":snapshot.get("job_id"),
            "saved_at":snapshot.get("saved_at") or snapshot.get("scan_finished_at"),
            "rows":len(rows),"fixtures":len(fixtures),"markets":dict(markets),
            "eligible":eligible,"excluded":len(rows)-eligible,
            "excluded_reasons":dict(excluded),
            "fixtures_detail":dict(sorted(fixtures.items())),
            "odds_api_calls":0,"database_writes":0}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("archive")
    args=parser.parse_args()
    with open(args.archive,encoding="utf-8") as file:
        snapshot=json.load(file)
    print(json.dumps(audit(snapshot),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
