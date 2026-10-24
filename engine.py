"""NBA STATS 4.0 — statistical engine ported from supplied 3.5 app.py.
Model is a non-calibrated heuristic, not a verified prediction.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import lru_cache
from cachetools import TTLCache, cached
import os, re, requests, pandas as pd
import json, time, threading
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
BASE = "https://api.oddspapi.io/v4"
ROME_TZ = ZoneInfo("Europe/Rome")
API_KEY = os.getenv("ODDSPAPI_API_KEY", "")
MARKETS = {"Punti (PTS)": ("players-points",), "Rimbalzi (REB)": ("players-rebounds",), "Assist (AST)": ("players-assists",)}
STATS = {"Punti (PTS)": "PTS", "Rimbalzi (REB)": "REB", "Assist (AST)": "AST"}
BET365_ALT_LINES = {"PTS": {float(n)+0.5 for n in range(4,100,5)}, "REB": {2.5,4.5,6.5,9.5,12.5,14.5,16.5,19.5}, "AST": {2.5,4.5,6.5,9.5,12.5,14.5}}
ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
odds_cache = TTLCache(maxsize=200,ttl=86400)
# Store only usable responses; never cache a temporary empty or suspended feed.
# Optional local disk cache survives application process restarts when storage persists.
_CACHE_LOCK = threading.RLock()
_CACHE_DIR = Path(os.getenv("NBA_ODDS_CACHE_DIR", "/tmp/nba_stats_4_odds"))

def _cache_read(fid):
    with _CACHE_LOCK:
        cached_value = odds_cache.get(fid)
        if cached_value is not None:
            return cached_value, "memory"
        path = _CACHE_DIR / (re.sub(r"[^a-zA-Z0-9_-]", "", str(fid)) + ".json")
        try:
            if time.time() - path.stat().st_mtime > 86400:
                return None, "none"
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                odds_cache[fid] = obj
                return obj, "disk"
        except (OSError, ValueError, TypeError):
            pass
        return None, "none"

def _cache_write(fid, odds):
    with _CACHE_LOCK:
        odds_cache[fid] = odds
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _CACHE_DIR / (re.sub(r"[^a-zA-Z0-9_-]", "", str(fid)) + ".json")
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(odds), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass

def _odds_diagnostics(odds, catalog):
    books = odds.get("bookmakerOdds") or {} if isinstance(odds, dict) else {}
    book = books.get("bet365.it") or {}
    markets = book.get("markets") or {}
    result = {"bookmaker_presente": bool(book), "bookmaker_attivo": book.get("bookmakerIsActive"),
              "bookmaker_sospeso": book.get("suspended"), "mercati_totali": len(markets),
              "mercati_player_props": 0, "mercati_attivi": 0, "mercati_inattivi": 0,
              "mercati_senza_catalogo": 0, "giocatori_attivi": 0, "quote_valide": 0}
    wanted = {kind for kinds in MARKETS.values() for kind in kinds}
    for mid, market in markets.items():
        definition = catalog.get(str(mid))
        if definition is None:
            result["mercati_senza_catalogo"] += 1
            continue
        if definition.get("marketType") not in wanted:
            continue
        result["mercati_player_props"] += 1
        result["mercati_attivi" if market.get("marketActive") is True else "mercati_inattivi"] += 1
        for outcome in (market.get("outcomes") or {}).values():
            for player in (outcome.get("players") or {}).values():
                if player.get("active"):
                    result["giocatori_attivi"] += 1
                    if isinstance(player.get("price"), (int,float)) and player["price"] > 1:
                        result["quote_valide"] += 1
    return result

def bet365_line_allowed(row, stat):
    return (row.get("Tipo") == "Soglia +" and
            round(float(row["Linea"]), 2) in BET365_ALT_LINES[stat] and
            isinstance(row.get("Over"), (int, float)))

# A single process-wide gate spaces OddsPapi calls without affecting ESPN.
_ODDS_API_LOCK = threading.Lock()
_ODDS_API_NEXT_AT = 0.0
_ODDS_API_MIN_INTERVAL = 2.0

def get_json(path, **params):
    if not API_KEY:
        raise RuntimeError("Chiave OddsPapi assente nella configurazione del servizio.")
    global _ODDS_API_NEXT_AT
    # Only one bounded retry for 429. Never retry other errors or consume
    # an unbounded number of the remaining monthly API requests.
    for attempt in range(2):
        with _ODDS_API_LOCK:
            wait = max(0.0, _ODDS_API_NEXT_AT - time.monotonic())
            if wait:
                time.sleep(wait)
            _ODDS_API_NEXT_AT = time.monotonic() + _ODDS_API_MIN_INTERVAL
            try:
                resp = requests.get(
                    f"{BASE}/{path}",
                    params={**params, "apiKey": API_KEY, "language": "en"},
                    timeout=40,
                )
            except requests.RequestException:
                raise RuntimeError("OddsPapi: errore di connessione.") from None
            if resp.status_code == 429 and attempt == 0:
                header = resp.headers.get("Retry-After", "")
                try:
                    delay = max(2.0, min(float(header), 30.0))
                except (TypeError, ValueError):
                    delay = 8.0
                # Do not retry a long cooldown automatically.
                if delay >= 30.0:
                    raise RuntimeError("OddsPapi: HTTP 429 (attendere prima di riprovare).")
                _ODDS_API_NEXT_AT = max(_ODDS_API_NEXT_AT, time.monotonic() + delay)
                continue
            if not resp.ok:
                raise RuntimeError(f"OddsPapi: errore HTTP {resp.status_code}.")
            try:
                return resp.json()
            except ValueError:
                raise RuntimeError("OddsPapi: risposta JSON non valida.") from None
    raise RuntimeError("OddsPapi: HTTP 429 dopo il tentativo controllato.")

@cached(TTLCache(maxsize=512,ttl=21600))
def get_markets():
    data = get_json("markets")
    if not isinstance(data, list):
        raise ValueError("Formato catalogo mercati inatteso")
    return {str(m["marketId"]): m for m in data if str(m.get("sportId")) == "11"}

def fixture_start_rome(fixture):
    """Convert an OddsPapi ISO timestamp to Italian local time."""
    raw = fixture.get("startTime")
    if not raw:
        return None
    try:
        if isinstance(raw, (int, float)):
            timestamp = float(raw)
            if timestamp > 1e11:  # Unix milliseconds
                timestamp /= 1000
            instant = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            value = str(raw).strip()
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            instant = datetime.fromisoformat(value)
            # OddsPapi UTC timestamps may omit their explicit Z suffix.
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=timezone.utc)
        return instant.astimezone(ROME_TZ)
    except (ValueError, TypeError, OverflowError, OSError):
        return None

@cached(TTLCache(maxsize=512,ttl=1800))
def get_fixtures(day_string):
    # Calendar day is Europe/Rome, including daylight-saving transitions.
    local_start = datetime.strptime(day_string, "%Y-%m-%d").replace(tzinfo=ROME_TZ)
    local_end = (local_start + timedelta(days=1))
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)
    data = get_json("fixtures", sportId=11, **{
        "from": utc_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": (utc_end - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    if isinstance(data, dict):
        data = data.get("fixtures", data.get("data", []))
    if not isinstance(data, list):
        raise ValueError("Formato calendario inatteso")
    matches = []
    for fixture in data:
        if str(fixture.get("tournamentName", "")).casefold() != "nba":
            continue
        start_rome = fixture_start_rome(fixture)
        if start_rome is not None and start_rome.date().isoformat() == day_string:
            matches.append(fixture)
    return sorted(matches, key=lambda f: fixture_start_rome(f))

def fixture_is_completed(fixture):
    """Hide completed games, not games merely underway."""
    status = str(fixture.get("statusName") or "").strip().casefold()
    if status in {"finished", "final", "completed", "ended", "after overtime", "after extra time"}:
        return True
    if fixture.get("trueEndTime"):
        return True
    return False

def get_odds(fixture_id, refresh_version=0):
    return get_json("odds", fixtureId=fixture_id, bookmakers="bet365.it", verbosity=3)

def parse_odds(data, catalog, market_label):
    bookmaker = (data.get("bookmakerOdds") or {}).get("bet365.it") or {}
    if not bookmaker.get("bookmakerIsActive", False) or bookmaker.get("suspended", False):
        return [], {"Bookmaker": "Non attivo o sospeso"}
    rows = {}
    diag = {"Mercati nel feed Bet365": len(bookmaker.get("markets") or {}), "Mercati del tipo richiesto": 0,
            "Mercati alternativi (+)": 0, "Mercati alternativi attivi": 0,
            "Mercati alternativi inattivi": 0, "Mercati senza definizione": 0}
    for market_id, market_data in (bookmaker.get("markets") or {}).items():
        definition = catalog.get(str(market_id))
        if not definition:
            diag["Mercati senza definizione"] += 1
            continue
        kind = definition.get("marketType", "")
        if kind not in MARKETS[market_label]:
            continue
        diag["Mercati del tipo richiesto"] += 1
        # Never combine alternative '+' quotes with main Over/Under prices.
        active_market = market_data.get("marketActive") is True
        diag["Mercati alternativi (+)"] += 1
        diag["Mercati alternativi attivi" if active_market else "Mercati alternativi inattivi"] += 1
        if not active_market:
            diag.setdefault("Mercati inattivi esclusi", 0)
            diag["Mercati inattivi esclusi"] += 1
            continue
        names = {str(o.get("outcomeId")): str(o.get("outcomeName", "")) for o in definition.get("outcomes", [])}
        for outcome_id, outcome in (market_data.get("outcomes") or {}).items():
            name = names.get(str(outcome_id), "")
            match = re.fullmatch(r"\s*(\d+)\+\s*", name)
            if not match:
                continue
            line = int(match.group(1)) - 0.5
            for player_id, player in (outcome.get("players") or {}).items():
                if not player.get("active") or not player.get("playerName"):
                    continue
                price = player.get("price")
                if not isinstance(price, (int, float)) or price <= 1:
                    continue
                key = (str(player_id), line)
                rows[key] = {"Giocatore": player["playerName"], "Linea": line,
                             "Over": float(price), "Tipo": "Soglia +",
                             "Stato API": "Attivo"}
    return sorted(rows.values(), key=lambda r: (r["Giocatore"], r["Linea"])), diag

def espn_json(url, **params):
    # Public ESPN endpoints: no account, key or OddsPapi request involved.
    response = requests.get(url, params=params, headers={
        "User-Agent": "Mozilla/5.0 (compatible; NBAStats2/2.0)",
        "Accept": "application/json",
    }, timeout=(8, 22))
    response.raise_for_status()
    return response.json()

def normalized_name(name):
    import unicodedata
    name = unicodedata.normalize("NFKD", str(name))
    name = "".join(c for c in name if not unicodedata.combining(c))
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 2:
        name = parts[1] + " " + parts[0]
    return re.sub(r"[^a-z0-9]", "", name.casefold())

# Exact, reviewed OddsPapi -> ESPN aliases. Do not fuzzy-match different athletes.
PLAYER_NAME_ALIASES = {
    "morezjohnson": "morezjohnsonjr",
    "pjwashingtonjr": "pjwashington",
    "jabarismith": "jabarismithjr",
    "dariusacuff": "dariusacuffjr",
}


def espn_player_key(odds_name):
    key = normalized_name(odds_name)
    return normalized_name(PLAYER_NAME_ALIASES.get(key, key))

@cached(TTLCache(maxsize=512,ttl=21600))
def espn_teams():
    data = espn_json(f"{ESPN_SITE}/teams", limit=50)
    return (data.get("sports") or [{}])[0].get("leagues", [{}])[0].get("teams", [])

@cached(TTLCache(maxsize=512,ttl=21600))
def espn_roster(team_id, end_year=None):
    # ESPN's current roster does not need a season parameter. Some historical
    # season queries return HTTP 200 with an empty athletes list.
    params = {"season": end_year} if end_year is not None else {}
    return espn_json(f"{ESPN_SITE}/teams/{team_id}/roster", **params)

def roster_athletes(payload):
    """Extract actual ESPN athletes, never position/category metadata."""
    seen = set()

    def visit(node, athlete_context=False):
        if isinstance(node, list):
            for item in node:
                yield from visit(item, athlete_context)
            return
        if not isinstance(node, dict):
            return

        # ESPN roster payloads can group athletes by position. Group IDs and
        # labels (e.g. Guard, Center, Active) must never become player entries.
        wrapped = node.get("athlete")
        if isinstance(wrapped, dict):
            yield from visit(wrapped, True)

        athlete_id = node.get("id")
        name = node.get("displayName") or node.get("fullName")
        looks_like_athlete = athlete_context or (
            isinstance(node.get("position"), dict)
            or "jersey" in node or "headshot" in node
            or "dateOfBirth" in node or "birthPlace" in node
            or "height" in node or "weight" in node
        )
        if looks_like_athlete and athlete_id is not None and name and str(athlete_id).isdigit():
            key = str(athlete_id)
            if key not in seen:
                seen.add(key)
                yield {
                    "id": key,
                    "displayName": name,
                    "position": (node.get("position") or {}).get("displayName", "") if isinstance(node.get("position"), dict) else "",
                    "jersey": str(node.get("jersey") or ""),
                    "height": str(node.get("displayHeight") or ""),
                    "weight": str(node.get("displayWeight") or ""),
                }

        for key, value in node.items():
            if key != "athlete" and isinstance(value, (list, dict)):
                yield from visit(value, athlete_context=(key == "athletes"))

    yield from visit(payload.get("athletes") or payload.get("items") or [])

def espn_event_date(info):
    """Extract a real date only; never infer a date from row position."""
    if not isinstance(info, dict):
        return None
    for key in ("date", "gameDate", "startDate", "startTime"):
        if info.get(key):
            return info[key]
    for competition in info.get("competitions") or []:
        if isinstance(competition, dict):
            found = espn_event_date(competition)
            if found:
                return found
    return None

@cached(TTLCache(maxsize=512,ttl=21600))
def espn_team_schedule(team_id, end_year, season_type=2):
    """One ESPN schedule request supplies game dates for an entire season."""
    payload = espn_json(f"{ESPN_SITE}/teams/{team_id}/schedule", season=end_year, seasontype=season_type)
    dates = {}
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("id") or "")
        date = espn_event_date(event)
        if event_id and date:
            dates[event_id] = date
    return dates

def espn_log_to_frame(data, season_type=2):
    """Parse ESPN games, keeping their *actual* competition when identifiable."""
    labels = [str(x).strip().upper() for x in data.get("labels") or []]
    metadata = data.get("events") or {}
    if isinstance(metadata, list):
        metadata = {str(e.get("id")): e for e in metadata if isinstance(e, dict)}
    if not isinstance(metadata, dict):
        metadata = {}
    rows = []
    for group in data.get("seasonTypes") or []:
        if not isinstance(group, dict):
            continue
        raw_type = group.get("id") or group.get("type")
        if isinstance(raw_type, dict):
            raw_type = raw_type.get("id") or raw_type.get("value")
        group_name = str(group.get("displayName") or group.get("name") or "").lower()
        group_type = None
        if str(raw_type) in ("2", "3"):
            group_type = int(raw_type)
        elif "regular" in group_name:
            group_type = 2
        elif any(word in group_name for word in ("postseason", "post-season", "playoff")):
            group_type = 3
        # ESPN can ignore seasonType query. Never blindly label games as the requested type.
        for category in group.get("categories") or []:
            if not isinstance(category, dict) or str(category.get("type", "")).lower() == "total":
                continue
            local_labels = [str(x).strip().upper() for x in (category.get("labels") or labels)]
            if not all(x in local_labels for x in ("PTS", "REB", "AST")):
                continue
            for event in category.get("events") or []:
                if not isinstance(event, dict):
                    continue
                values = event.get("stats") or []
                if not isinstance(values, list) or len(values) != len(local_labels):
                    continue
                event_id = str(event.get("eventId") or event.get("id") or "")
                if not event_id:
                    continue
                info = metadata.get(event_id) or {}
                if not isinstance(info, dict):
                    info = {}
                opponent = info.get("opponent") or {}
                if not isinstance(opponent, dict):
                    opponent = {}
                opp = opponent.get("abbreviation") or opponent.get("displayName") or "?"
                rows.append({
                    "GAME_ID": event_id,
                    "SEASON_TYPE": group_type,
                    "GAME_DATE": espn_event_date(info) or espn_event_date(event),
                    "MATCHUP": f"{'@' if str(info.get('atVs', '')).strip() == '@' else 'vs'} {opp}",
                    "MIN": values[local_labels.index("MIN")] if "MIN" in local_labels else None,
                    "PTS": values[local_labels.index("PTS")],
                    "REB": values[local_labels.index("REB")],
                    "AST": values[local_labels.index("AST")],
                })
    frame = pd.DataFrame(rows, columns=["GAME_ID", "SEASON_TYPE", "GAME_DATE", "MATCHUP", "MIN", "PTS", "REB", "AST"])
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["GAME_ID"], keep="first")
    return frame

def prepare_game_log(log, team_id, season, require_dates=True):
    """Complete and verify dates before calculating last-N statistics."""
    log = log.copy()
    if log.empty:
        return log
    dates = pd.to_datetime(log["GAME_DATE"], errors="coerce", utc=True)
    if dates.isna().any() and team_id:
        schedule = {}
        for kind in sorted(set(log["SEASON_TYPE"].astype(int))) if "SEASON_TYPE" in log.columns else [2]:
            schedule.update(espn_team_schedule(team_id, int(season[:4]) + 1, kind))
        replacement = pd.to_datetime(log["GAME_ID"].astype(str).map(schedule), errors="coerce", utc=True)
        dates = dates.fillna(replacement)
    log["GAME_DATE"] = dates
    # Do not invent chronology. Missing dates do not prevent season-wide stats;
    # last-N comparisons are hidden until the complete order is known.
    for col in ("PTS", "REB", "AST"):
        log[col] = pd.to_numeric(log[col], errors="coerce")
    if log[["PTS", "REB", "AST"]].isna().any().any():
        raise ValueError("Statistiche ESPN incomplete o non numeriche: analisi sospesa.")
    if (log[["PTS", "REB", "AST"]] < 0).any().any():
        raise ValueError("Statistiche ESPN non valide: valori negativi.")
    return log.sort_values("GAME_DATE", ascending=False).reset_index(drop=True)

def analysis_row(title, data, stat, line):
    values = data[stat].dropna()
    n = len(values)
    over = int((values > line).sum())
    return {"Periodo": title, "Partite": n,
            "Over": f"{over}/{n}" if n else "—",
            "% Over": f"{over/n:.1%}" if n else "—",
            "Media": f"{values.mean():.1f}" if n else "—",
            "Media - linea": f"{values.mean()-line:+.1f}" if n else "—"}

def _espn_competition_type(event):
    """Read competition type from explicit ESPN event metadata only."""
    if not isinstance(event, dict):
        return None
    candidates = [event.get("season"), event.get("seasonType"),
                  event.get("season_type"), event.get("type")]
    for comp in event.get("competitions") or []:
        if isinstance(comp, dict):
            candidates.extend([comp.get("season"), comp.get("seasonType")])
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = candidate.get("type") or candidate.get("id") or candidate.get("value")
        if str(candidate) in ("2", "3"):
            return int(candidate)
        if isinstance(candidate, str):
            value = candidate.lower()
            if "regular" in value:
                return 2
            if "playoff" in value or "postseason" in value:
                return 3
    return None

@cached(TTLCache(maxsize=512,ttl=21600))
def espn_schedule_competition_ids(team_id, end_year):
    """Resolve event types from ESPN schedules; ignore season-type query if ESPN ignores it."""
    sources = {}
    for requested_type in (2, 3):
        payload = espn_json(f"{ESPN_SITE}/teams/{team_id}/schedule", season=end_year, seasontype=requested_type)
        for event in payload.get("events") or []:
            if not isinstance(event, dict) or not event.get("id"):
                continue
            event_id = str(event["id"])
            explicit_type = _espn_competition_type(event)
            record = sources.setdefault(event_id, {"explicit": set(), "requests": set()})
            if explicit_type:
                record["explicit"].add(explicit_type)
            record["requests"].add(requested_type)
    result = {}
    for event_id, record in sources.items():
        if len(record["explicit"]) == 1:
            result[event_id] = next(iter(record["explicit"]))
        elif not record["explicit"] and len(record["requests"]) == 1:
            # Trust schedule membership only if the requested filters disagree.
            result[event_id] = next(iter(record["requests"]))
    return result

@cached(TTLCache(maxsize=512,ttl=21600))
def espn_event_competition_type(event_id):
    """Fallback: one free ESPN event summary when schedule lacks type metadata."""
    payload = espn_json(f"{ESPN_SITE}/summary", event=event_id)
    header = payload.get("header") or {}
    return _espn_competition_type(header) or _espn_competition_type(payload.get("gameInfo"))

@cached(TTLCache(maxsize=512,ttl=21600))
def espn_classified_game_log(athlete_id, season, team_id):
    """Classify using ESPN game-log groups first, then independent evidence.

    An unclassified game is never silently called a playoff game.
    """
    end_year = int(season[:4]) + 1
    # ESPN regular/all and playoff feeds are independent: fetch concurrently.
    from concurrent.futures import ThreadPoolExecutor
    def fetch_log(requested_type):
        params = {"season": end_year}
        if requested_type is not None:
            params["seasonType"] = requested_type
        return espn_log_to_frame(espn_json(f"{ESPN_WEB}/athletes/{athlete_id}/gamelog", **params))
    def fetch_schedule():
        if not team_id:
            return {}
        try:
            return espn_schedule_competition_ids(team_id, end_year)
        except (requests.RequestException, ValueError, TypeError):
            return {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        all_future = pool.submit(fetch_log, None)
        playoff_future = pool.submit(fetch_log, 3)
        schedule_future = pool.submit(fetch_schedule)
        frames = [frame for frame in (all_future.result(), playoff_future.result()) if not frame.empty]
        schedule_types = schedule_future.result()
    membership = {2: set(), 3: set()}
    columns = ["GAME_ID", "SEASON_TYPE", "GAME_DATE", "MATCHUP", "MIN", "PTS", "REB", "AST"]
    if not frames:
        return pd.DataFrame(columns=columns)

    # Prefer explicit season type attached to the individual log row.
    games = pd.concat(frames, ignore_index=True)
    explicit = {}
    for _, row in games.iterrows():
        event_id = str(row["GAME_ID"])
        kind = row["SEASON_TYPE"]
        if pd.notna(kind) and int(kind) in (2, 3):
            explicit.setdefault(event_id, set()).add(int(kind))
    games = games.drop_duplicates(subset=["GAME_ID"], keep="first").reset_index(drop=True)
    conflicting = {event_id for event_id, types in explicit.items() if len(types) > 1}
    known = {event_id: next(iter(types)) for event_id, types in explicit.items() if len(types) == 1}

    # An ESPN event reported as both regular and playoff must not be resolved
    # by a schedule fallback. Exclude it until independent evidence is audited.
    for event_id, kind in schedule_types.items():
        if event_id not in known and event_id not in conflicting and kind in (2, 3):
            known[event_id] = kind

    # Last resort: ask for an event summary, but only for unresolved games.
    for event_id in games["GAME_ID"].astype(str):
        if event_id in known or event_id in conflicting:
            continue
        try:
            kind = espn_event_competition_type(event_id)
        except (requests.RequestException, ValueError, TypeError):
            kind = None
        if kind in (2, 3):
            known[event_id] = kind

    games["SEASON_TYPE"] = games["GAME_ID"].astype(str).map(known)
    # Do not raise for unknown classification: expose the uncertainty and exclude
    # those games from mode-specific analyses to avoid false Over/Under results.
    games.attrs["unclassified"] = int(games["SEASON_TYPE"].isna().sum())
    games.attrs["conflicting"] = len(conflicting)
    if conflicting:
        logger.warning("ESPN conflicting season classification athlete=%s season=%s events=%s",
                       athlete_id, season, sorted(conflicting))
    return games

def selected_game_log(athlete_id, season, mode, team_id=None):
    games = espn_classified_game_log(athlete_id, season, team_id)
    if mode == "Regular season":
        unknown = int(games["SEASON_TYPE"].isna().sum())
        if unknown:
            logger.warning("ESPN excluded %d unclassified games for athlete=%s season=%s team=%s",
                           unknown, athlete_id, season, team_id)
        return games.loc[games["SEASON_TYPE"] == 2].copy()
    if mode == "Playoff":
        return games.loc[games["SEASON_TYPE"] == 3].copy()
    if mode == "Regular season + Playoff":
        return games.loc[games["SEASON_TYPE"].isin([2, 3])].copy()
    raise ValueError("Modalità competizione non riconosciuta")

def auto_filter_suspicious_lines(player_rows):
    """Remove a lower threshold if its Over price exceeds the next higher Over.

    Compare adjacent alternative Over quotes, repeating after each removal.
    A monotonic feed is not proof that Bet365 currently offers the quote.
    """
    ordered = sorted(player_rows, key=lambda r: r["Linea"])
    kept = list(ordered)
    excluded = []
    while True:
        over_rows = [r for r in kept if isinstance(r.get("Over"), (int, float))]
        bad = next((prev for prev, following in zip(over_rows, over_rows[1:])
                    if prev["Over"] > following["Over"] + 0.005), None)
        if bad is None:
            break
        kept.remove(bad)
        excluded.append(bad)
    return kept, excluded

def finder_estimate_probability(log, stat, line, side):
    """Stima empirica regolarizzata per ciascuna soglia; NON calibrata.

    Prior di Jeffreys Beta(0.5, 0.5), anziche' 24 pseudopartite al 50%.
    Una frequenza 0/N resta bassa, N/N resta alta; nessuna garanzia predittiva.
    La finestra recente e' parte della stagione: il suo peso (20%) e' una
    scelta provvisoria, da validare su giornate future senza riottimizzarla.
    """
    if log.empty or stat not in log.columns:
        return None
    log = log.copy()
    log[stat] = pd.to_numeric(log[stat], errors="coerce")
    log["GAME_DATE"] = pd.to_datetime(log["GAME_DATE"], errors="coerce", utc=True)
    log = log.dropna(subset=[stat, "GAME_DATE"]).sort_values("GAME_DATE", ascending=False)
    if len(log) < 15 or abs(line % 1 - 0.5) > 1e-6:
        return None
    values = log[stat]
    wins = (values > line) if side == "Over" else (values < line)
    recent = wins.head(min(20, len(wins)))
    season_rate = float(wins.mean())
    recent_rate = float(recent.mean())
    # Jeffreys smoothing: 0/20 -> 2.38%, 20/20 -> 97.62%.
    season_smoothed = (float(wins.sum()) + 0.5) / (len(wins) + 1.0)
    recent_smoothed = (float(recent.sum()) + 0.5) / (len(recent) + 1.0)
    estimate = 0.80 * season_smoothed + 0.20 * recent_smoothed
    return {"estimate": estimate, "season": season_rate, "recent": recent_rate,
            "n": len(wins), "n_recent": len(recent), "recent_hits": int(recent.sum()),
            "avg": float(values.mean())}

def finder_player_index(end_year):
    """Fetch team rosters with limited concurrency, preserving original team order."""
    from concurrent.futures import ThreadPoolExecutor
    teams = []
    for entry in espn_teams():
        team = entry.get("team", entry)
        team_id = str(team.get("id") or "")
        if team_id:
            teams.append((team_id, team))

    def fetch_roster(item):
        team_id, team = item
        try:
            return team_id, team, espn_roster(team_id, None)
        except requests.RequestException:
            return team_id, team, None

    index = {}
    # Executor.map returns in input order: duplicate-name handling is unchanged.
    # Four concurrent ESPN requests speed up startup without flooding the API.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for team_id, team, roster in pool.map(fetch_roster, teams):
            if roster is None:
                continue
            for athlete in roster_athletes(roster):
                index.setdefault(normalized_name(athlete["displayName"]),
                                 {"id": athlete["id"], "team_id": team_id,
                                  "full_name": athlete["displayName"],
                                  "team_name": team.get("displayName") or team.get("name") or f"Squadra ESPN {team_id}"})
    return index

def historical_player_index(end_year, missing_names):
    """Resolve missing athletes against previous-season rosters only.

    Never guess identities: ambiguous normalized names are excluded.
    Called only if the current-roster index failed, and uses ESPN, not OddsPapi.
    """
    from concurrent.futures import ThreadPoolExecutor
    wanted = {espn_player_key(name) for name in missing_names}
    if not wanted:
        return {}
    teams = []
    for entry in espn_teams():
        team = entry.get("team", entry)
        team_id = str(team.get("id") or "")
        if team_id:
            teams.append((team_id, team))
    def fetch_old(item):
        team_id, team = item
        try:
            return team_id, team, espn_roster(team_id, end_year - 1)
        except requests.RequestException:
            return team_id, team, {}
    matches = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for team_id, team, payload in pool.map(fetch_old, teams):
            for athlete in roster_athletes(payload):
                key = espn_player_key(athlete["displayName"])
                if key not in wanted:
                    continue
                matches.setdefault(key, {})[athlete["id"]] = {
                    "id":athlete["id"],"team_id":team_id,
                    "full_name":athlete["displayName"],
                    "team_name":team.get("displayName") or team.get("name") or team_id}
    return {key:next(iter(players.values())) for key,players in matches.items()
            if len(players)==1}


def odds_source_audit(odds, catalog, match_name):
    """Read bookmaker source fields already downloaded; NO extra API requests.

    'Attivo nel feed' is not a guarantee that Bet365 offers the selection.
    """
    bookmaker = (odds.get("bookmakerOdds") or {}).get("bet365.it") or {}
    result = []
    for market_id, market_data in (bookmaker.get("markets") or {}).items():
        definition = catalog.get(str(market_id))
        if not definition:
            continue
        kind = str(definition.get("marketType") or "")
        if kind not in {t for kinds in MARKETS.values() for t in kinds}:
            continue
        names = {str(o.get("outcomeId")): str(o.get("outcomeName", ""))
                 for o in definition.get("outcomes") or []}
        for outcome_id, outcome in (market_data.get("outcomes") or {}).items():
            label = names.get(str(outcome_id), "")
            if kind.startswith("players-"):
                match = re.fullmatch(r"\s*(\d+)\+\s*", label)
                if not match:
                    continue
                line = float(int(match.group(1)) - 0.5)
            else:
                if label.strip().lower() not in ("over", "under"):
                    continue
                try:
                    line = float(definition["handicap"])
                except (ValueError, TypeError, KeyError):
                    continue
            for player_id, player in (outcome.get("players") or {}).items():
                price = player.get("price")
                if not isinstance(price, (int, float)) or price <= 1:
                    continue
                result.append({
                    "Partita": match_name,
                    "Giocatore": str(player.get("playerName") or ""),
                    "Mercato API": kind,
                    "Nome mercato API": str(definition.get("marketName") or ""),
                    "Esito originale": label,
                    "Linea interpretata": line,
                    "Quota": price,
                    "Mercato attivo feed": market_data.get("marketActive"),
                    "Giocatore attivo feed": player.get("active"),
                    "Bookmaker attivo feed": bookmaker.get("bookmakerIsActive"),
                    "Mercato ID": str(market_id),
                    "Esito ID": str(outcome_id),
                    "Bookmaker market ID": str(market_data.get("bookmakerMarketId") or ""),
                    "Bookmaker outcome ID": str(player.get("bookmakerOutcomeId") or ""),
                    "Ultima variazione feed": str(player.get("changedAt") or ""),
                })
    return result

def finder_detailed_stats(log, stat, line):
    """Descrittori osservati, non un modello probabilistico validato."""
    frame = log.copy()
    frame[stat] = pd.to_numeric(frame[stat], errors="coerce")
    frame["GAME_DATE"] = pd.to_datetime(frame["GAME_DATE"], errors="coerce", utc=True)
    frame = frame.dropna(subset=[stat, "GAME_DATE"]).sort_values("GAME_DATE", ascending=False)
    if frame.empty:
        return {}
    vals = frame[stat]
    def hits(n):
        sub = vals.head(n)
        return f"{int((sub > line).sum())}/{len(sub)}"
    minutes = pd.to_numeric(frame["MIN"], errors="coerce") if "MIN" in frame else pd.Series(dtype=float)
    return {"Ultime 5": hits(5), "Ultime 10": hits(10), "Ultime 20": hits(20),
            "Stagione %": round(100 * float((vals > line).mean()), 1),
            "Partite": len(vals), "Media": round(float(vals.mean()), 1),
            "Scarto medio": round(float(vals.mean() - line), 1),
            "Dev. standard": round(float(vals.std(ddof=1)), 1) if len(vals) > 1 else None,
            "Minuti medi": round(float(minutes.mean()), 1) if minutes.notna().any() else None,
            "Minuti ultime 5": round(float(minutes.head(5).mean()), 1) if minutes.head(5).notna().any() else None}

def finder_scan(fixtures, catalog, season, min_games, odds_min, odds_max,
                min_value, progress_callback=None):
    """Esporta tutte le linee alternative attive ricevute, incluse non valutabili.

    Un'unica risposta OddsPapi per partita; se già presente in sessione la riusa.
    I filtri sono soltanto per la vista, mai per il CSV completo.
    """
    results, issues, raw_audit, filter_audit = [], [], [], []
    fixture_reports = []
    # All historical samples must precede the first fixture being predicted.
    starts = [fixture_start_rome(fixture) for fixture in fixtures]
    starts = [start for start in starts if start is not None]
    history_cutoff = min(starts) if starts else datetime.now(timezone.utc)
    history_cutoff = pd.Timestamp(history_cutoff).tz_convert("UTC")
    index = finder_player_index(int(season[:4]) + 1)
    props_by_player = {}
    player_logs = {}
    quote_count = 0
    for idx, fixture in enumerate(fixtures):
        fid = str(fixture["fixtureId"])
        match_name = f"{fixture.get('participant1Name', '?')} - {fixture.get('participant2Name', '?')}"
        if progress_callback:
            progress_callback(0.25 * idx / max(len(fixtures), 1), f"Quote: {match_name}")
        report = {"id": fid, "partita": match_name, "inizio_italia": (fixture_start_rome(fixture).isoformat() if fixture_start_rome(fixture) else None), "stato": "in_elaborazione", "linee": 0, "dettaglio": ""}
        fixture_reports.append(report)
        count_before = quote_count
        try:
            odds, source = _cache_read(fid)
            if odds is None:
                odds = get_odds(fid)
            report["origine"] = source if source != "none" else "api"
            report["diagnostica"] = _odds_diagnostics(odds, catalog)
            # Cache only validated, successfully parsed fixtures (after processing).
            raw_audit.extend(odds_source_audit(odds, catalog, match_name))
            for market_label in MARKETS:
                parsed, _ = parse_odds(odds, catalog, market_label)
                grouped = {}
                for row in parsed:
                    grouped.setdefault(row["Giocatore"], []).append(row)
                for player_name, group in grouped.items():
                    # Il controllo di coerenza non deve cancellare righe dall'esportazione.
                    eligible = [r for r in group if bet365_line_allowed(r, STATS[market_label])]
                    _, excluded = auto_filter_suspicious_lines(eligible)
                    bad_keys = {(r["Giocatore"], float(r["Linea"])) for r in excluded}
                    for row in group:
                        line = float(row["Linea"])
                        if not bet365_line_allowed(row, STATS[market_label]):
                            reason = "Soglia fuori schema configurato" if line != 0.5 else "Linea 0,5 esclusa dalla classifica"
                        elif (player_name, line) in bad_keys:
                            reason = "Quote incoerenti tra soglie: verificare su Bet365"
                        else:
                            reason = ""
                        if reason:
                            filter_audit.append({"Partita": match_name, "Giocatore": player_name,
                                                 "Mercato": STATS[market_label], "Linea": line,
                                                 "Motivo": reason})
                        price = float(row["Over"])
                        quote_count += 1
                        props_by_player.setdefault(player_name, []).append((match_name, market_label, line, price, reason))
            report["linee"] = quote_count - count_before
            report["stato"] = "ok" if report["linee"] else "vuota"
            if not report["linee"]:
                d = report["diagnostica"]
                report["dettaglio"] = (f"Feed: {d['mercati_totali']} mercati, "
                                     f"{d['mercati_player_props']} props, "
                                     f"{d['mercati_attivi']} attivi; "
                                     f"bookmaker attivo={d['bookmaker_attivo']}, "
                                     f"sospeso={d['bookmaker_sospeso']}")
                issues.append(f"{match_name}: nessuna linea Bet365 elaborabile")
            else:
                _cache_write(fid, odds)
        except Exception as exc:
            # Discard partial results for this fixture; avoid silently counting incomplete games.
            quote_count = count_before
            for name in list(props_by_player):
                props_by_player[name] = [v for v in props_by_player[name] if v[0] != match_name]
                if not props_by_player[name]:
                    del props_by_player[name]
            report.update(stato="errore", linee=0, dettaglio=f"{type(exc).__name__}: {str(exc)[:160]}")
            logger.exception("Quote fixture %s failed", fid)
            issues.append(f"{match_name}: {report['dettaglio']}")
    from concurrent.futures import ThreadPoolExecutor
    player_items = list(props_by_player.items())
    missing_names = [name for name,_ in player_items
                     if normalized_name(name) not in index
                     and espn_player_key(name) not in index]
    if missing_names:
        try:
            recovered = historical_player_index(int(season[:4]) + 1, missing_names)
            # Current-roster identities take precedence over historical matches.
            for key, athlete in recovered.items():
                index.setdefault(key, athlete)
            logger.info("Historical ESPN identity lookup: %d missing names, %d unique matches",
                        len(missing_names), len(recovered))
        except requests.RequestException:
            logger.warning("Historical ESPN roster lookup unavailable", exc_info=True)

    def load_player(item):
        player_name, _props = item
        athlete = index.get(normalized_name(player_name)) or index.get(espn_player_key(player_name))
        games = None
        error = "Giocatore non identificato su ESPN" if athlete is None else ""
        if athlete is not None:
            try:
                previous_season = f"{int(season[:4])-1}-{str(int(season[:4]))[-2:]}"
                parts = []
                for reference_season in (season, previous_season):
                    part = selected_game_log(athlete["id"], reference_season, "Regular season", athlete["team_id"])
                    if not part.empty:
                        part = prepare_game_log(part, athlete["team_id"], reference_season, require_dates=False)
                        part["ANNO_STAGIONE"] = reference_season
                        parts.append(part)
                if not parts:
                    error = "Nessuna partita ESPN nelle ultime due stagioni"
                else:
                    games = pd.concat(parts, ignore_index=True)
                    games["GAME_DATE"] = pd.to_datetime(games["GAME_DATE"], errors="coerce", utc=True)
                    # Never use a future or in-progress game to estimate a
                    # pregame probability, even if ESPN publishes partial stats.
                    cutoff = min(pd.Timestamp.now(tz="UTC"), history_cutoff)
                    future_count = int((games["GAME_DATE"] >= cutoff).sum())
                    if future_count:
                        logger.warning("ESPN excluded %d future/in-progress rows athlete=%s",
                                       future_count, athlete["id"])
                        games = games.loc[games["GAME_DATE"] < cutoff].copy()
                    if games["GAME_DATE"].isna().any():
                        error = "Date ESPN incomplete: cronologia non verificabile"
                        games = None
                    else:
                        games = (games.drop_duplicates(subset=["GAME_ID"], keep="first")
                                      .sort_values("GAME_DATE", ascending=False).reset_index(drop=True))
                        logger.info("ESPN history athlete=%s id=%s seasons=%s unique_games=%d",
                                    player_name, athlete["id"],
                                    {str(k): int(v) for k,v in games["ANNO_STAGIONE"].value_counts().items()},
                                    len(games))
            except Exception as exc:
                error = f"Dati ESPN non disponibili ({type(exc).__name__})"
                games = None
        return athlete, games, error

    # Concurrent ESPN I/O, but preserve deterministic result and progress order.
    with ThreadPoolExecutor(max_workers=4) as pool:
        player_data = pool.map(load_player, player_items)
        for idx, ((player_name, props), (athlete, games, error)) in enumerate(zip(player_items, player_data)):
            if progress_callback:
                progress_callback(0.25 + 0.75 * idx / max(len(player_items), 1),
                                  f"ESPN: {idx + 1}/{len(player_items)} — {player_name}")
            if games is not None:
                player_logs[player_name] = games
            if error:
                issues.append(f"{player_name}: {error}")
            for match_name, market_label, line, price, reason in props:
                stat = STATS[market_label]
                row = {"Partita": match_name, "Giocatore": player_name,
                       "ESPN ID": str(athlete.get("id", "")) if athlete else "",
                       "Squadra": athlete.get("team_name", "Squadra non identificata") if athlete else "Squadra non identificata",
                       "Mercato": stat,
                       "Scelta": "Over", "Linea": line, "Quota": price,
                       "Prob. stimata %": None, "Prob. implicita %": round(100 / price, 1),
                       "Value stimato %": None, "Ultime 5": "—", "Ultime 10": "—",
                       "Ultime 20": "—", "Stagione %": None, "Partite": 0, "Stagione attuale (n)": 0, "Stagione precedente (n)": 0,
                       "Media": None, "Scarto medio": None, "Dev. standard": None,
                       "Minuti medi": None, "Minuti ultime 5": None,
                       "Stato analisi": "Non valutabile", "Nota": reason or error}
                if games is not None and not games.empty:
                    details = finder_detailed_stats(games, stat, line)
                    row.update(details)
                    row["Stagione attuale (n)"] = int((games["ANNO_STAGIONE"] == season).sum())
                    row["Stagione precedente (n)"] = int((games["ANNO_STAGIONE"] != season).sum())
                    if len(games) < min_games:
                        by_season = games["ANNO_STAGIONE"].value_counts()
                        current_count = int(by_season.get(season, 0))
                        previous_count = len(games) - current_count
                        detail = (f"Solo {len(games)} partite ESPN (minimo {min_games}; "
                                  f"stagione attuale {current_count}, precedente {previous_count})")
                        row["Nota"] = "; ".join(filter(None, [reason, detail]))
                    elif not reason:
                        estimate = finder_estimate_probability(games, stat, line, "Over")
                        if estimate:
                            prob = estimate["estimate"]
                            row["Prob. stimata %"] = round(prob * 100, 1)
                            row["Value stimato %"] = round((prob * price - 1) * 100, 1)
                            row["Stato analisi"] = "Valutabile (stima empirica)"
                            row["Nota"] = "Stima empirica NON calibrata; verifica quota e disponibilità"
                results.append(row)
    if progress_callback:
        progress_callback(1.0, "Analisi completata")
    results.sort(key=lambda r: (r["Prob. stimata %"] is not None,
                                r["Prob. stimata %"] if r["Prob. stimata %"] is not None else -1), reverse=True)
    return results, issues, quote_count, len(props_by_player), raw_audit, filter_audit, player_logs, fixture_reports

def _ratio_hits(value):
    """Parse observed hit count; leave missing/malformed values unavailable."""
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", str(value))
    if not match:
        return None
    hits, total = map(int, match.groups())
    return (hits, total) if total > 0 and 0 <= hits <= total else None

def rank_single_candidates(frame, minimum_odds=1.50, maximum_odds=2.10):
    """Transparent screening, NOT a validated predictive model."""
    if frame.empty:
        return frame.copy()
    data = frame[frame["Stato analisi"] == "Valutabile (stima empirica)"].copy()
    for column in ("Quota", "Prob. stimata %", "Partite", "Stagione %", "Minuti medi", "Minuti ultime 5"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["Quota", "Prob. stimata %"])
    data = data[data["Quota"].between(minimum_odds, maximum_odds)].copy()
    if data.empty:
        return data
    for window in (5, 10, 20):
        data[f"_h{window}"] = data[f"Ultime {window}"].map(_ratio_hits)
        data[f"_p{window}"] = data[f"_h{window}"].map(lambda x: x[0]/x[1] if x and x[1] == window else float('nan'))
    data["Prob. pareggio %"] = (100 / data["Quota"]).round(1)
    data["Margine stimato pp"] = (data["Prob. stimata %"] - data["Prob. pareggio %"]).round(1)
    data["Minuti stabili"] = (
        data["Minuti medi"].notna() & (data["Minuti medi"] >= 20) &
        data["Minuti ultime 5"].notna() &
        (data["Minuti ultime 5"] >= 0.8 * data["Minuti medi"])
    )
    data["Criteri rispettati"] = (
        (data["Prob. stimata %"] >= 70).astype(int) +
        (data["_p5"] >= 0.8).astype(int) +
        (data["_p10"] >= 0.8).astype(int) +
        (data["_p20"] >= 0.8).astype(int) +
        (data["Stagione %"] >= 70).astype(int) +
        (data["Partite"] >= 20).astype(int) +
        data["Minuti stabili"].astype(int) +
        (data["Margine stimato pp"] >= 3).astype(int)
    )
    data["Esito screening"] = data.apply(
        lambda row: "Candidata da verificare" if (
            row["Criteri rispettati"] == 8 and row["Prob. stimata %"] >= 75
        ) else "Non supera tutti i criteri", axis=1
    )
    return data.sort_values(
        ["Criteri rispettati", "Prob. stimata %", "Margine stimato pp", "Partite"],
        ascending=[False, False, False, False]
    ).drop(columns=["_h5", "_h10", "_h20", "_p5", "_p10", "_p20"])

def csv_excel_friendly(frame):
    """Prevent Excel interpreting 5/5 as a date in exported CSV."""
    result = frame.copy()
    for column in ("Ultime 5", "Ultime 10", "Ultime 20"):
        if column in result:
            result[column] = result[column].map(
                lambda value: str(value).replace("/", " su ") if _ratio_hits(value) else value
            )
    return result.to_csv(index=False).encode("utf-8-sig")

def current_nba_season(day):
    start = day.year if day.month >= 10 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"
