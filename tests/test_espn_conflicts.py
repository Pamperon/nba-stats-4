"""Conflicting ESPN season labels must not leak into historical stats."""
import unittest
from unittest.mock import patch
import pandas as pd
import engine

class ESPNConflictingLabelsTests(unittest.TestCase):
    def test_conflicting_event_stays_unclassified(self):
        conflicting=pd.DataFrame([
            {"GAME_ID":"a","SEASON_TYPE":2},
            {"GAME_ID":"a","SEASON_TYPE":3},
            {"GAME_ID":"b","SEASON_TYPE":2},
        ])
        empty=pd.DataFrame(columns=conflicting.columns)
        def log_response(_data):
            return conflicting if log_response.calls == 0 else empty
        log_response.calls=0
        def parse(data):
            result=conflicting if parse.calls == 0 else empty
            parse.calls+=1
            return result
        parse.calls=0
        with patch.object(engine,"espn_json",return_value={}), \
             patch.object(engine,"espn_log_to_frame",side_effect=parse), \
             patch.object(engine,"espn_schedule_competition_ids",return_value={"a":2}), \
             patch.object(engine,"espn_event_competition_type",return_value=2):
            result=engine.espn_classified_game_log.__wrapped__("42","2026-27","1") if hasattr(engine.espn_classified_game_log,"__wrapped__") else engine.espn_classified_game_log("42","2026-27","1")
        row=result.set_index("GAME_ID")
        self.assertTrue(pd.isna(row.loc["a","SEASON_TYPE"]))
        self.assertEqual(row.loc["b","SEASON_TYPE"],2)

if __name__=="__main__":
    unittest.main()
