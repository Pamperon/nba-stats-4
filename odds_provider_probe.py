"""Explicit, authenticated, one-shot compatibility probe. No scan/cache/model changes."""
import time
from datetime import datetime, timedelta, timezone
import requests
import storage
import scan_tracking
from psycopg.types.json import Jsonb

TEST_ID = "nba-tournament-compatibility-v1"
BASE = "https://api.oddspapi.io/v4"
KINDS = {"players-points", "players-assists", "players-rebounds"}
MAX_CALLS = 5


class ProbeError(RuntimeError):
    pass


def fixtures_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if payload.get("fixtureId"):
            return [payload]
        for key in ("fixtures", "data", "events"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
    raise ProbeError("Unexpected fixture response structure")


def account_summary(payload):
    # Never return keys, subscription IDs, email or billing details.
    if not isinstance(payload, dict):
        return {}
    current = payload.get("current_subscription_id")
    for item in payload.get("subscriptions") or []:
        if item.get("subscription_id") == current or (not current and item.get("is_active")):
            book = (item.get("bookmakers") or {}).get("bet365.it") or {}
            return {key: item.get(key) for key in ("request_count", "request_limit", "valid_from", "valid_until")} | {
                "bet365_it_player_props": book.get("has_player_props"),
                "nba_sport_allowed": 11 in (item.get("sport_ids") or [])}
    return {}


def selections(fixture, catalog):
    book = (fixture.get("bookmakerOdds") or {}).get("bet365.it") or {}
    found = {}
    if not book.get("bookmakerIsActive") or book.get("suspended"):
        return found
    for mid, market in (book.get("markets") or {}).items():
        definition = catalog.get(str(mid), {})
        kind = definition.get("marketType")
        if kind not in KINDS or market.get("marketActive") is not True:
            continue
        for oid, outcome in (market.get("outcomes") or {}).items():
            for pid, player in (outcome.get("players") or {}).items():
                price = player.get("price")
                if player.get("active") and player.get("playerName") and isinstance(price, (int, float)) and price > 1:
                    found[(str(mid), str(oid), str(pid), kind)] = float(price)
    return found


def coverage(fixture, catalog):
    values = selections(fixture, catalog)
    return {"fixture_id": str(fixture.get("fixtureId", "")),
            "bookmaker_present": "bet365.it" in (fixture.get("bookmakerOdds") or {}),
            "active_selections": len(values),
            "by_market_type": {kind: sum(k[3] == kind for k in values) for kind in sorted(KINDS)}}


def compare(bulk, single, catalog):
    a, b = selections(bulk, catalog), selections(single, catalog)
    common = a.keys() & b.keys()
    return {"bulk": coverage(bulk, catalog), "single": coverage(single, catalog),
            "common": len(common), "missing_from_bulk": len(b.keys() - a.keys()),
            "extra_in_bulk": len(a.keys() - b.keys()),
            "price_differences": sum(abs(a[k] - b[k]) > 1e-8 for k in common),
            "note": "Prices may move during sequential requests."}


class Caller:
    def __init__(self, api_key, limit=MAX_CALLS, job_id=TEST_ID):
        self.api_key = api_key
        self.limit = limit
        self.job_id = job_id
        self.count = 0
        self.history = []
        self.next_at = 0

    def get(self, endpoint, **params):
        if endpoint not in ("account", "fixtures", "markets", "odds-by-tournaments", "odds"):
            raise ProbeError("Endpoint not allowed")
        billable = endpoint != "account"
        if billable and self.count >= self.limit:
            raise ProbeError("Request budget reached")
        time.sleep(max(0, self.next_at - time.monotonic()))
        self.next_at = time.monotonic() + 1.2
        request_id = None
        if billable:
            request_id = scan_tracking.start_request(self.job_id, endpoint)
            self.count += 1
        response = None
        entry = {"endpoint": endpoint}
        self.history.append(entry)
        try:
            # No retry, request URL logging or exception text containing keys.
            response = requests.get(BASE + "/" + endpoint,
                params={**params, "apiKey": self.api_key, "language": "en"}, timeout=(10, 45))
            entry["http_status"] = response.status_code
            if not response.ok:
                raise ProbeError("OddsPapi " + endpoint + " HTTP " + str(response.status_code))
            return response.json()
        except (requests.RequestException, ValueError):
            raise ProbeError("OddsPapi " + endpoint + " transport or JSON error") from None
        finally:
            if request_id:
                scan_tracking.finish_request(request_id, response.status_code if response is not None else None)


def run_once(api_key):
    with storage.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_provider_probe (
                test_id TEXT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                result JSONB NOT NULL DEFAULT '{}'::jsonb)
        """)
        # An interrupted reservation is never automatically rerun.
        existing = conn.execute("SELECT result FROM nba_provider_probe WHERE test_id=%s", (TEST_ID,)).fetchone()
        if existing:
            return {"reused": True, **existing[0]}
        active = conn.execute("""
            SELECT COUNT(*) FROM nba_scan_attempts WHERE state IN ('queued','running')
            AND heartbeat_at > NOW()-INTERVAL '2 minutes'
        """).fetchone()[0]
        if active:
            raise ProbeError("Automatic scan active; probe not started")
        reserved = conn.execute("""
            INSERT INTO nba_provider_probe(test_id,result) VALUES(%s,%s)
            ON CONFLICT DO NOTHING RETURNING test_id
        """, (TEST_ID, Jsonb({"state": "reserved", "billable_request_budget": MAX_CALLS}))).fetchone()
        if not reserved:
            return {"reused": True, "state": "reserved"}
    caller = Caller(api_key)
    report = {"test_id": TEST_ID, "state": "running", "billable_request_budget": MAX_CALLS}
    try:
        now = datetime.now(timezone.utc)
        fixtures = fixtures_list(caller.get("fixtures", sportId=11, **{
            "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": (now + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")}))
        nba = [f for f in fixtures if str(f.get("tournamentName", "")).casefold() == "nba"
               and f.get("tournamentId") is not None]
        if not nba:
            raise ProbeError("No NBA fixtures in next 48 hours; bulk request not made")
        tournament_ids = sorted({str(f["tournamentId"]) for f in nba})
        markets = caller.get("markets")
        if not isinstance(markets, list):
            raise ProbeError("Unexpected markets response")
        catalog = {str(m["marketId"]): m for m in markets if str(m.get("sportId")) == "11"}
        before = account_summary(caller.get("account"))
        payload = caller.get("odds-by-tournaments", tournamentIds=",".join(tournament_ids),
                             bookmakers="bet365.it", verbosity=3)
        after = account_summary(caller.get("account"))
        bulk = fixtures_list(payload)
        by_id = {str(f.get("fixtureId")): f for f in bulk if isinstance(f, dict)}
        report.update({"tournament_ids": tournament_ids, "nba_fixtures_next_48h": len(nba),
            "bulk_fixture_count": len(bulk), "account_before_bulk": before, "account_after_bulk": after,
            "bulk_request_count_delta": (after["request_count"] - before["request_count"]
                if isinstance(after.get("request_count"), int) and isinstance(before.get("request_count"), int) else None),
            "missing_fixture_ids": [str(f["fixtureId"]) for f in nba if str(f["fixtureId"]) not in by_id],
            "bulk_coverage": [coverage(by_id.get(str(f["fixtureId"]), {}), catalog) |
                {"expected_fixture_id": str(f["fixtureId"]), "start_time": f.get("startTime")} for f in nba]})
        candidates = sorted(nba, key=lambda f: (not bool(selections(by_id.get(str(f["fixtureId"]), {}), catalog)),
                                                str(f.get("startTime", ""))))
        report["comparisons"] = []
        for fixture in candidates[:2]:
            fid = str(fixture["fixtureId"])
            single = caller.get("odds", fixtureId=fid, bookmakers="bet365.it", verbosity=3)
            if not isinstance(single, dict):
                raise ProbeError("Unexpected single-fixture odds response")
            report["comparisons"].append(compare(by_id.get(fid, {}), single, catalog))
        report["account_final"] = account_summary(caller.get("account"))
        report["state"] = "done"
        report["free_plan_compatibility"] = "Not proven by a paid-account test"
    except ProbeError as exc:
        report.update(state="error", error=str(exc))
    except Exception:
        report.update(state="error", error="Internal probe error; no automatic retry")
    finally:
        report.update(billable_http_attempts=caller.count, requests=caller.history)
        with storage.connection() as conn:
            conn.execute("UPDATE nba_provider_probe SET result=%s WHERE test_id=%s", (Jsonb(report), TEST_ID))
    return {"reused": False, **report}


def check_missing_once(api_key):
    """Only inspect the missing fixtures recorded by the primary test, at most three."""
    key = TEST_ID + "-missing"
    with storage.connection() as conn:
        existing = conn.execute("SELECT result FROM nba_provider_probe WHERE test_id=%s", (key,)).fetchone()
        if existing:
            return {"reused": True, **existing[0]}
        parent = conn.execute("SELECT result FROM nba_provider_probe WHERE test_id=%s", (TEST_ID,)).fetchone()
        if not parent or parent[0].get("state") != "done":
            raise ProbeError("Primary test not completed")
        missing = parent[0].get("missing_fixture_ids", [])
        if not isinstance(missing, list) or len(missing) > 3:
            raise ProbeError("Supplementary test requires at most three recorded missing fixtures")
        active = conn.execute("""
            SELECT COUNT(*) FROM nba_scan_attempts WHERE state IN ('queued','running')
            AND heartbeat_at > NOW()-INTERVAL '2 minutes'
        """).fetchone()[0]
        if active:
            raise ProbeError("Automatic scan active; probe not started")
        reserved = conn.execute("""
            INSERT INTO nba_provider_probe(test_id,result) VALUES(%s,%s)
            ON CONFLICT DO NOTHING RETURNING test_id
        """, (key, Jsonb({"state": "reserved", "billable_request_budget": 3}))).fetchone()
        if not reserved:
            return {"reused": True, "state": "reserved"}
    caller = Caller(api_key, limit=3, job_id=key)
    report = {"test_id": key, "state": "running", "fixtures": [], "billable_request_budget": 3}
    try:
        for fid in missing:
            fixture = caller.get("odds", fixtureId=fid, bookmakers="bet365.it", verbosity=3)
            book = (fixture.get("bookmakerOdds") or {}).get("bet365.it") or {}
            markets = book.get("markets") or {}
            active_players = sum(
                bool(p.get("active") and p.get("playerName") and isinstance(p.get("price"), (int, float))
                     and p["price"] > 1)
                for m in markets.values() if m.get("marketActive") is True
                for o in (m.get("outcomes") or {}).values()
                for p in (o.get("players") or {}).values())
            report["fixtures"].append({"fixture_id": fid,
                "bookmaker_present": "bet365.it" in (fixture.get("bookmakerOdds") or {}),
                "bookmaker_active": book.get("bookmakerIsActive"), "suspended": book.get("suspended"),
                "markets_total": len(markets), "active_player_outcomes_all_markets": active_players})
        account = caller.get("account")
        report["account_final"] = account_summary(account)
        report["observed_free_subscriptions"] = [
            {"request_limit": s.get("request_limit"), "is_active": s.get("is_active"),
             "bet365_it_player_props": ((s.get("bookmakers") or {}).get("bet365.it") or {}).get("has_player_props"),
             "nba_sport_allowed": 11 in (s.get("sport_ids") or [])}
            for s in account.get("subscriptions", []) if s.get("request_limit") == 250]
        report["state"] = "done"
    except ProbeError as exc:
        report.update(state="error", error=str(exc))
    except Exception:
        report.update(state="error", error="Internal supplementary probe error; no automatic retry")
    finally:
        report.update(billable_http_attempts=caller.count, requests=caller.history)
        with storage.connection() as conn:
            conn.execute("UPDATE nba_provider_probe SET result=%s WHERE test_id=%s", (Jsonb(report), key))
    return {"reused": False, **report}
