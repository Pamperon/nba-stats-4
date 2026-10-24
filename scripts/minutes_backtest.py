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
    bands = ((1.20,1.40,"tripla"),(1.40,1.70,"doppia"),(1.70,2.01,"singola"))
    by_category = {}
    for low,high,label in bands:
        def in_band(row):
            try:
                odds=float(row["Quota"])
                p=float(row["Prob. stimata %"])/100
                return low <= odds < high and p*odds > 1 and str(row.get("Stato analisi","")).lower() != "non valutabile"
            except (ValueError,TypeError,KeyError):
                return False
        sample=[row for row in verified if in_band(row)]
        by_category[label] = {}
        for flag in ("normal","watch","unknown"):
            flagged=[row for row in sample if minutes_shadow.assess(row)==flag]
            summary=summarize(flagged).get("overall")
            unique=summarize_unique_opportunities(flagged)["groups"].get("overall")
            by_category[label][flag]={"verified_lines":len(flagged),"all_lines":summary,"unique_opportunities":unique}
    return {"archived_lines":len(original),"flags":dict(flags),
            "verified_lines":len(verified),"by_minutes":groups,"by_category":by_category,
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
