"""Timezone boundary tests for ESPN calendar matching."""
import unittest
from unittest.mock import patch
import settle_espn

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

if __name__=="__main__":
    unittest.main()
