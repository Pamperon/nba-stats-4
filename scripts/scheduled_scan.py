"""Scheduled NBA STATS scans. Requires NBA_STATS_ACCESS_TOKEN in GitHub Secrets."""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

BASE = "https://nba-stats-4.onrender.com"
TOKEN = os.environ.get("NBA_STATS_ACCESS_TOKEN", "")
ROME = ZoneInfo("Europe/Rome")
SLOTS = {0, 10, 14, 18, 21}

def call(path, method="GET", timeout=45):
    req = urllib.request.Request(
        BASE + path, method=method,
        headers={"Authorization": "Bearer " + TOKEN, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)

def run():
    if not TOKEN:
        raise RuntimeError("GitHub secret NBA_STATS_ACCESS_TOKEN is missing")
    now = dt.datetime.now(ROME)
    if os.environ.get("NBA_STATS_DRY_RUN") == "1":
        print("SAFE TEST: no OddsPapi calls and no scan jobs", flush=True)
        print("Rome time:", now.isoformat(), flush=True)
        session = call("/api/session")
        print("Authentication:", session.get("authenticated"), flush=True)
        print("Database configured:", session.get("database_configured"), flush=True)
        today = now.date().isoformat()
        schedule = call("/api/schedule?date=" + today)
        print("ESPN games for", today, ":", len(schedule.get("games", [])), flush=True)
        return
    if now.hour not in SLOTS:
        print("Not a Rome-time scan slot:", now.isoformat(), flush=True)
        return
    # Delay of a scheduled GitHub Actions run is expected; local-hour gate handles DST.
    for offset in (0, 1):
        date = (now.date() + dt.timedelta(days=offset)).isoformat()
        print("Checking", date, flush=True)
        try:
            schedule = call("/api/schedule?date=" + date)
        except Exception as exc:
            print("ESPN calendar unavailable; skip without OddsPapi:", exc, flush=True)
            continue
        upcoming = [g for g in schedule.get("games", []) if g.get("upcoming")]
        if not upcoming:
            print("No upcoming games; skipping paid scan", flush=True)
            continue
        print(len(upcoming), "upcoming games", flush=True)
        # Every scheduled slot refreshes today's/tomorrow's snapshot when games remain.
        try:
            job = call("/api/scan?date=" + date, method="POST")
            job_id = job["job_id"]
            print("Job", job_id, "reused:", job.get("reused"), flush=True)
            deadline = time.monotonic() + 1800
            while time.monotonic() < deadline:
                time.sleep(20)  # Keep Render Free awake during long scans.
                status = call("/api/scan/" + urllib.parse.quote(job_id))
                state = status.get("state")
                if state in ("done", "partial"):
                    print(date, state, "lines:", len(status.get("results", [])), flush=True)
                    break
                if state in ("error", "save_failed"):
                    raise RuntimeError(date + ": " + str(status.get("stage")))
            else:
                raise TimeoutError("Scan exceeded 30 minutes: " + date)
        except Exception as exc:
            print("Scan failed:", exc, flush=True)
            raise

if __name__ == "__main__":
    run()
