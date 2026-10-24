"""Read-only historical minutes shadow evaluation; no OddsPapi or writes."""
import argparse
import collections
import json
import requests
import minutes_shadow
import settle_espn
from scripts.archive_performance import summarize, summarize_unique_opportunities

def evaluate(archive, verified):
    original = archive["results"]
    flags = collections.Counter(minutes_shadow.assess(r) for r in original)
    groups = {}
    for flag in ("normal", "watch", "unknown"):
        sample = [r for r in verified if minutes_shadow.assess(r) == flag]
        groups[flag] = {"verified_lines":len(sample),
                        "all_lines":summarize(sample).get("overall"),
                        "unique_opportunities":summarize_unique_opportunities(sample)["groups"].get("overall")}
    return {"archived_lines":len(original),"flags":dict(flags),
            "verified_lines":len(verified),"by_minutes":groups,
            "odds_api_calls":0,"database_writes":0,
            "note":"Correlated alternate lines; descriptive only, not proof of filter benefit"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dates",nargs="+",default=["2026-10-23","2026-10-24"])
    args=parser.parse_args()
    for day in args.dates:
        try:
            response=requests.get("https://nba-stats-4.onrender.com/api/saved/archive",
                                  params={"date":day},timeout=100)
            response.raise_for_status()
            archive=response.json()
            if archive.get("date") != day:
                raise ValueError("Archive date mismatch")
            verified, _=settle_espn.settle_archive(archive,day)
            print("MINUTES_BACKTEST "+json.dumps({"date":day,**evaluate(archive,verified)},ensure_ascii=False),flush=True)
        except Exception as exc:
            print("MINUTES_BACKTEST_ERROR "+json.dumps({"date":day,"error":str(exc)}),flush=True)
            raise

if __name__=="__main__":
    main()
