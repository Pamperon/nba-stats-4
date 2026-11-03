"""Current ESPN injury report, checked once per scan. No bookmaker requests.

Not appearing in this report is not a guarantee of playing. Never use this
current feed to annotate past snapshots or to backtest an injury filter.
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def athlete_id(athlete):
    direct = str(athlete.get("id") or "")
    if direct.isdigit():
        return direct
    ids = set()
    for link in athlete.get("links") or []:
        url = urlparse(str(link.get("href") or ""))
        if url.hostname not in ("www.espn.com", "espn.com"):
            continue
        match = re.search(r"/nba/player/(?:stats/|gamelog/|splits/)?_/id/(\d+)(?:/|$)", url.path)
        if match:
            ids.add(match[1])
    return next(iter(ids)) if len(ids) == 1 else None


def annotate(rows, payload, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, dict):
        payload = {}
    checked = now.isoformat()
    try:
        stamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
        age = (now - stamp).total_seconds()
        valid = (payload.get("status") == "success" and 0 <= age <= 1800
                 and isinstance(payload.get("injuries"), list))
    except (KeyError, TypeError, ValueError):
        valid = False
    statuses = {}
    if valid:
        for team in payload["injuries"]:
            if not isinstance(team, dict) or not isinstance(team.get("injuries"), list):
                valid = False
                break
            for entry in team.get("injuries") or []:
                if not isinstance(entry, dict) or not isinstance(entry.get("athlete"), dict):
                    valid = False
                    break
                identifier = athlete_id(entry.get("athlete") or {})
                status = str(entry.get("status") or "").strip().lower()
                # Unknown or conflicting reports must never imply clearance.
                normalized = status if status in {"out", "doubtful", "questionable", "day-to-day", "suspension"} else "unknown"
                if identifier:
                    old = statuses.get(identifier)
                    statuses[identifier] = normalized if old in (None, normalized) else "unknown"
                else:
                    valid = False
                    break
    result = []
    for row in rows:
        identifier = str(row.get("ESPN ID") or "")
        status = statuses.get(identifier, "not-listed") if valid and identifier.isdigit() else "unknown"
        result.append({**row, "Disponibilità ESPN": status,
                       "Disponibilità verificata alle": checked})
    return result, {"source": "ESPN", "checked_at": checked,
                    "report_at": payload.get("timestamp") if isinstance(payload, dict) else None,
                    "verified": valid, "odds_api_calls": 0}


def check(rows):
    if not rows:
        return annotate(rows, {})
    try:
        response = requests.get(URL, timeout=12)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            payload = {}
    except (requests.RequestException, ValueError):
        payload = {}
    return annotate(rows, payload)
