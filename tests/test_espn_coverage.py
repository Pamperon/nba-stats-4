"""Unclassified ESPN games must never be counted as regular season."""
import unittest
from unittest.mock import patch
import pandas as pd
import engine

class CompetitionCoverageTests(unittest.TestCase):
    def test_unknown_competition_excluded_and_reported(self):
        games=pd.DataFrame({"GAME_ID":["a","b","c"],"SEASON_TYPE":[2,None,3]})
        with patch.object(engine,"espn_classified_game_log",return_value=games), \
             self.assertLogs(engine.logger,level="WARNING") as logs:
            selected=engine.selected_game_log("99","2026-27","Regular season","1")
        self.assertEqual(selected["GAME_ID"].tolist(),["a"])
        self.assertTrue(any("1 unclassified games" in line for line in logs.output))

if __name__=="__main__":
    unittest.main()
