"""Persistent OddsPapi response reuse, shared across dates and process restarts."""
import threading
import time
from cachetools import TTLCache
import storage

_LOCK = threading.RLock()
_MEMORY = TTLCache(maxsize=12, ttl=48 * 3600)


def cached_payload(key, max_age_seconds, loader):
    """Read before HTTP; preserve the original download time on every cache hit."""
    # Three stable database rows (calendar/catalog/feed), not a growing row per slot/day.
    persistent_key = key.split(":v1:", 1)[0] + ":v1" if ":v1:" in key else key
    with _LOCK:
        # Retain only the latest calendar/catalog/feed in RAM, as in PostgreSQL.
        # Logical identity still forces a fresh download for every new slot.
        envelope = _MEMORY.get(persistent_key)
        if (envelope is None or envelope.get('identity', key) != key
                or not 0 <= time.time() - envelope.get('fetched_at', 0) < max_age_seconds) and storage.configured():
            envelope = storage.cache_read(persistent_key, max_age_hours=48)
        if isinstance(envelope, dict) and envelope.get("identity", key) == key:
            age = time.time() - envelope.get("fetched_at", 0)
            if 0 <= age < max_age_seconds and "data" in envelope:
                _MEMORY[persistent_key] = envelope
                return {**envelope, "source": "cache"}
        data = loader()  # Validators run inside the loader before persistence.
        envelope = {"data": data, "fetched_at": time.time(), "identity": key}
        if storage.configured():
            storage.cache_write(persistent_key, envelope)
        _MEMORY[persistent_key] = envelope
        return {**envelope, "source": "api"}


def fixture_rows(payload):
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and payload.get("fixtureId"):
        rows = [payload]
    elif isinstance(payload, dict):
        rows = payload.get("fixtures", payload.get("data", payload.get("events")))
        if isinstance(rows, dict):
            rows = list(rows.values())
    else:
        rows = None
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get("fixtureId") for row in rows):
        raise ValueError("Formato calendario/quote per torneo inatteso")
    return rows


def slim_tournament(payload, market_ids):
    """Retain all wanted player lines and bookmaker flags; omit unrelated markets."""
    result = {}
    for fixture in fixture_rows(payload):
        if str(fixture.get("tournamentId")) != "132":
            continue
        book = (fixture.get("bookmakerOdds") or {}).get("bet365.it")
        clean = {k: v for k, v in fixture.items() if k != "bookmakerOdds"}
        clean["bookmakerOdds"] = {}
        if isinstance(book, dict):
            clean["bookmakerOdds"]["bet365.it"] = {
                **book, "markets": {str(mid): value for mid, value in (book.get("markets") or {}).items()
                                   if str(mid) in market_ids}}
        result[str(fixture["fixtureId"])] = clean
    return result
