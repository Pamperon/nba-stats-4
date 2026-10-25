"""Timezone boundary tests for ESPN calendar matching."""
import unittest
from unittest.mock import patch
import settle_espn
import engine
import datetime as dt

class CalendarBoundaryTests(unittest.TestCase):
    def test_previous_us_day_is_next_rome_day(self):
        game = {"id":"game-1","date":"2026-10-23T23:30:00Z",
                "status":{"type":{"completed":True}}}
        with patch.object(settle_espn,"fetch",side_effect=[
            {"events":[game]},{"events":[game]},{"events":[]}]):
            result=settle_espn.final_events("2026-10-24")
        self.assertEqual([x["id"] for x in result],["game-1"])

    def test_rome_day_excludes_following_morning(self):
        game = {"id":"game-2","date":"2026-10-24T23:30:00Z",
                "status":{"type":{"completed":True}}}
        with patch.object(settle_espn,"fetch",return_value={"events":[game]}):
            with self.assertRaisesRegex(ValueError,"no events"):
                settle_espn.final_events("2026-10-24")

    def test_unfinished_game_is_rejected(self):
        game = {"id":"game-3","date":"2026-10-24T19:00:00Z",
                "status":{"type":{"completed":False}}}
        with patch.object(settle_espn,"fetch",return_value={"events":[game]}):
            with self.assertRaises(ValueError):
                settle_espn.final_events("2026-10-24")

class PregameFixtureTests(unittest.TestCase):
    def test_started_game_is_excluded(self):
        fixture = {"startTime": "2026-10-25T18:00:00Z"}
        with patch.object(engine, "fixture_start_rome", return_value=dt.datetime(2026, 10, 25, 19, tzinfo=engine.ROME_TZ)):
            self.assertFalse(engine.fixture_is_upcoming(fixture, dt.datetime(2026, 10, 25, 20, tzinfo=engine.ROME_TZ)))

    def test_future_game_is_included(self):
        fixture = {"startTime": "2026-10-25T21:00:00Z"}
        with patch.object(engine, "fixture_start_rome", return_value=dt.datetime(2026, 10, 25, 22, tzinfo=engine.ROME_TZ)):
            self.assertTrue(engine.fixture_is_upcoming(fixture, dt.datetime(2026, 10, 25, 21, tzinfo=engine.ROME_TZ)))


if __name__=="__main__":
    unittest.main()
