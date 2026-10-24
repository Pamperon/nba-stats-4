"""Read-only real ESPN integration smoke test. No database, odds API, or writes."""
import argparse
import json
import settle_espn

def run(date):
    events = settle_espn.final_events(date)
    games = []
    for event in events:
        summary = settle_espn.fetch(settle_espn.BASE+"/summary",event=event["id"])
        stats = settle_espn.player_stats(summary)
        competitors = (event.get("competitions") or [{}])[0].get("competitors",[])
        team_names = [(c.get("team") or {}).get("displayName") for c in competitors]
        if len(team_names) != 2 or not all(team_names) or not stats:
            raise RuntimeError("ESPN incomplete boxscore for "+event["id"])
        games.append({"id":event["id"],"teams":team_names,"players":len(stats),
                      "completed":True})
    report={"rome_date":date,"games":len(games),"players_total":sum(g["players"] for g in games),
            "details":games,"odds_api_calls":0,"database_writes":0}
    print(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True,help="Rome date YYYY-MM-DD")
    args=parser.parse_args()
    run(args.date)
