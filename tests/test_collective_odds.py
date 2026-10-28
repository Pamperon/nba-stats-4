"""Collective-feed, restart, date and failure regressions; no real network."""
import datetime as dt
import unittest
from unittest.mock import Mock, patch
import engine
import odds_feed


class CollectiveOddsTests(unittest.TestCase):
    def setUp(self):
        odds_feed._MEMORY.clear()
        self.addCleanup(odds_feed._MEMORY.clear)
        db = patch.object(odds_feed.storage, "configured", return_value=False)
        db.start()
        self.addCleanup(db.stop)

    def test_two_dates_share_one_calendar_download(self):
        today = dt.datetime.now(engine.ROME_TZ).date()
        days = [today, today + dt.timedelta(days=1)]
        fixtures = [{"fixtureId": str(i), "tournamentName": "NBA",
                     "startTime": dt.datetime.combine(day, dt.time(19), tzinfo=engine.ROME_TZ).isoformat()}
                    for i, day in enumerate(days)]
        with patch.object(engine, "get_json", return_value=fixtures) as paid:
            self.assertEqual(engine.get_fixtures(days[0].isoformat()), [fixtures[0]])
            self.assertEqual(engine.get_fixtures(days[1].isoformat()), [fixtures[1]])
        self.assertEqual(paid.call_count, 1)

    def test_calendar_download_keeps_rome_dst_boundaries(self):
        with patch.object(engine, "get_json", return_value=[]) as paid:
            engine.get_fixtures("2026-10-25")
        params = paid.call_args.kwargs
        self.assertEqual(params["from"], "2026-10-24T22:00:00Z")
        self.assertEqual(params["to"], "2026-10-26T22:59:59Z")

    def test_new_feed_metadata_reschedules_without_another_calendar_request(self):
        today = dt.datetime.now(engine.ROME_TZ).date()
        tomorrow = today + dt.timedelta(days=1)
        fixture = {"fixtureId": "f", "tournamentName": "NBA", "participant1Name": "A",
                   "startTime": dt.datetime.combine(today, dt.time(19), tzinfo=engine.ROME_TZ).isoformat()}
        moved = dt.datetime.combine(tomorrow, dt.time(19), tzinfo=engine.ROME_TZ).isoformat()
        batch = {"data": {"f": {"fixtureId": "f", "startTime": moved}}}
        with patch.object(engine, "get_json", return_value=[fixture]) as paid:
            self.assertEqual(engine.get_fixtures(today.isoformat(), batch), [])
            rows = engine.get_fixtures(tomorrow.isoformat(), batch)
        self.assertEqual(rows[0]["participant1Name"], "A")
        self.assertEqual(paid.call_count, 1)

    def test_persistent_cache_survives_restart_without_extending_download_time(self):
        saved = {}
        loader = Mock(return_value=[])
        with patch.object(odds_feed.storage, "configured", return_value=True), \
             patch.object(odds_feed.storage, "cache_read", side_effect=lambda key,**kw:saved.get(key)), \
             patch.object(odds_feed.storage, "cache_write", side_effect=lambda key,value:saved.update({key:value})), \
             patch.object(odds_feed.time, "time", return_value=1000):
            original = odds_feed.cached_payload("slot", 100, loader)
            odds_feed._MEMORY.clear()
            restored = odds_feed.cached_payload("slot", 100, loader)
        self.assertEqual(original["fetched_at"], restored["fetched_at"])
        self.assertEqual(restored["source"], "cache")
        loader.assert_called_once()  # Empty successful responses are reusable too.
        with patch.object(odds_feed.time, "time", return_value=1101):
            odds_feed.cached_payload("slot", 100, loader)
        self.assertEqual(loader.call_count, 2)

    def test_failed_download_is_not_cached_and_database_failure_prevents_http(self):
        loader = Mock(side_effect=RuntimeError("provider unavailable"))
        with self.assertRaises(RuntimeError):
            odds_feed.cached_payload("slot", 100, loader)
        self.assertNotIn("slot", odds_feed._MEMORY)
        with patch.object(odds_feed.storage, "configured", return_value=True), \
             patch.object(odds_feed.storage, "cache_read", side_effect=RuntimeError("db down")):
            with self.assertRaises(RuntimeError):
                odds_feed.cached_payload("slot", 100, loader)
        self.assertEqual(loader.call_count, 1)

    def test_one_bulk_request_per_slot_keeps_all_wanted_lines(self):
        catalog = {"m": {"marketType": "players-points"}}
        data = [{"fixtureId": fid, "tournamentId": 132, "bookmakerOdds": {"bet365.it": {
            "bookmakerIsActive": True, "markets": {"m": {"outcomes": {}}, "unrelated": {}}}}}
            for fid in ("today", "tomorrow")]
        with patch.object(engine, "get_json", return_value=data) as paid:
            first = engine.get_tournament_odds("2026-10-28T12:00", catalog)
            second = engine.get_tournament_odds("2026-10-28T12:00", catalog)
            third = engine.get_tournament_odds("2026-10-28T17:00", catalog)
        self.assertEqual(paid.call_count, 2)
        self.assertEqual(paid.call_args.args[0], "odds-by-tournaments")
        self.assertEqual(set(first["data"]), {"today", "tomorrow"})
        self.assertEqual(set(first["data"]["today"]["bookmakerOdds"]["bet365.it"]["markets"]), {"m"})
        self.assertEqual(second["source"], "cache")
        self.assertEqual(third["source"], "api")

    def test_missing_collective_fixture_never_falls_back_to_single_or_old_cache(self):
        fixture = {"fixtureId": "missing", "participant1Name": "A", "participant2Name": "B",
                   "startTime": "2026-10-29T01:00:00Z"}
        batch = {"data": {}, "source": "api", "fetched_at": 1000}
        with patch.object(engine, "finder_player_index", return_value={}), \
             patch.object(engine, "_cache_read", side_effect=AssertionError("old per-fixture cache")), \
             patch.object(engine, "get_odds", side_effect=AssertionError("single-fixture HTTP")):
            result = engine.finder_scan([fixture], {}, "2026-27", 15, 1.01, 20, -100, odds_batch=batch)
        self.assertEqual(result[-1][0]["stato"], "vuota")
        self.assertEqual(result[-1][0]["origine"], "tournament")

    def test_bulk_slimming_preserves_existing_player_parser(self):
        catalog = {"m": {"marketType": "players-points", "outcomes": [{"outcomeId": "o", "outcomeName": "10+"}]}}
        fixture = {"fixtureId": "f", "tournamentId": 132, "bookmakerOdds": {"bet365.it": {
            "bookmakerIsActive": True, "markets": {"m": {"marketActive": True, "outcomes": {
                "o": {"players": {"p": {"active": True, "playerName": "A Player", "price": 1.8}}}}}}}}}
        slim = odds_feed.slim_tournament([fixture], {"m"})["f"]
        self.assertEqual(engine.parse_odds(fixture, catalog, "Punti (PTS)"),
                         engine.parse_odds(slim, catalog, "Punti (PTS)"))

    def test_new_days_and_slots_replace_fixed_database_rows(self):
        saved = {}
        loader = Mock(return_value=[])
        with patch.object(odds_feed.storage, "configured", return_value=True), \
             patch.object(odds_feed.storage, "cache_read", side_effect=lambda key,**kw:saved.get(key)), \
             patch.object(odds_feed.storage, "cache_write", side_effect=lambda key,value:saved.update({key:value})):
            odds_feed.cached_payload("odds:fixtures:v1:2026-10-28", 1000, loader)
            odds_feed._MEMORY.clear()
            odds_feed.cached_payload("odds:fixtures:v1:2026-10-29", 1000, loader)
        self.assertEqual(loader.call_count, 2)
        self.assertEqual(list(saved), ["odds:fixtures:v1"])
