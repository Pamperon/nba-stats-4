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
# Frequent heartbeat recovers missed GitHub cron launches. Supabase ensures
# each Rome-time slot is executed at most once (except explicit failure retry).
SLOTS = (0, 10, 14, 18, 22)
MAX_DELAY = dt.timedelta(hours=3)

def due_slot(now):
    candidates = []
    for days_back in (0, 1):
        day = now.date() - dt.timedelta(days=days_back)
        for hour in SLOTS:
            target = dt.datetime.combine(day, dt.time(hour), tzinfo=ROME)
            delay = now.astimezone(dt.timezone.utc) - target.astimezone(dt.timezone.utc)
            if dt.timedelta(0) <= delay <= MAX_DELAY:
                candidates.append(target)
    return max(candidates) if candidates else None

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
    manual = os.environ.get("NBA_STATS_MANUAL_SCAN") == "1"
    slot = None
    if not manual:
        slot = due_slot(now)
        if slot is None:
            print("SKIPPED: no recent Rome-time slot", now.isoformat(), flush=True)
            return
        slot_key = slot.strftime("%Y-%m-%dT%H:00")
        reservation = call("/api/storage/slot/claim?slot=" + urllib.parse.quote(slot_key),
                           method="POST")
        if not reservation.get("claimed"):
            print("SKIPPED: slot already processed or running:", slot_key, flush=True)
            return
        print("CLAIMED slot:", slot_key, "actual:", now.isoformat(), flush=True)
    print("Starting NBA scan at Rome time:", now.isoformat(), flush=True)
    try:
        execute_scan(now, slot, manual)
    except BaseException:
        if slot is not None:
            call("/api/storage/slot/finish?slot=" + urllib.parse.quote(slot_key) +
                 "&success=false", method="POST")
        raise
    else:
        if slot is not None:
            call("/api/storage/slot/finish?slot=" + urllib.parse.quote(slot_key) +
                 "&success=true", method="POST")

def execute_scan(now, slot, manual):
    # Cleanup runs even when there are no upcoming games, using only Supabase.
    # A temporary DB issue must not prevent the scheduled NBA scan.
    try:
        cleanup = call("/api/storage/cleanup", method="POST")
        print("Archive cleanup:", cleanup, flush=True)
    except Exception as exc:
        print("Archive cleanup failed (scans continue):", exc, flush=True)
    # Delay of a scheduled GitHub Actions run is expected; local-hour gate handles DST.
    scan_day = slot.date() if not manual else now.date()
    for offset in (0, 1):
        date = (scan_day + dt.timedelta(days=offset)).isoformat()
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
