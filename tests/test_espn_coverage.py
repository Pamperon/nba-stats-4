"""Unclassified ESPN games must never be counted as regular season."""
import unittest
from unittest.mock import patch
import pandas as pd
import engine

class CompetitionCoverageTests(unittest.TestCase):
    def test_venue_is_unknown_when_espn_does_not_identify_it(self):
        payload = {
            "labels": ["MIN", "PTS", "REB", "AST"],
            "events": {"1": {"atVs": "vs", "opponent": {"abbreviation": "BOS"}},
                       "2": {"atVs": "@", "opponent": {"abbreviation": "NYK"}},
                       "3": {"opponent": {"abbreviation": "LAL"}}},
            "seasonTypes": [{"id": "2", "categories": [{"type": "game", "events": [
                {"eventId": str(i), "stats": ["28", "10", "4", "2"]} for i in (1, 2, 3)]}]}],
        }
        games = engine.espn_log_to_frame(payload)
        self.assertEqual(games["MATCHUP"].tolist(), ["vs BOS", "@ NYK", "? LAL"])

    def test_unknown_competition_excluded_and_reported(self):
        games=pd.DataFrame({"GAME_ID":["a","b","c"],"SEASON_TYPE":[2,None,3]})
        with patch.object(engine,"espn_classified_game_log",return_value=games), \
             self.assertLogs(engine.logger,level="WARNING") as logs:
            selected=engine.selected_game_log("99","2026-27","Regular season","1")
        self.assertEqual(selected["GAME_ID"].tolist(),["a"])
        self.assertTrue(any("1 unclassified games" in line for line in logs.output))

if __name__=="__main__":
    unittest.main()
