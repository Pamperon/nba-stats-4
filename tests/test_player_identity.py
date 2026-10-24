"""Player identity fallback tests; ESPN fixtures mocked, no network."""
import unittest
from unittest.mock import patch
import engine

class HistoricalIdentityTests(unittest.TestCase):
    def test_prior_roster_recovers_exact_missing_player(self):
        teams=[{"team":{"id":"1","displayName":"Example Team"}}]
        roster={"athletes":[{"id":"12345","displayName":"Sample Player",
                             "position":{"displayName":"Guard"}}]}
        with patch.object(engine,"espn_teams",return_value=teams), \
             patch.object(engine,"espn_roster",return_value=roster):
            found=engine.historical_player_index(2027,["Player, Sample"])
        self.assertEqual(found["sampleplayer"]["id"],"12345")

    def test_ambiguous_same_name_rejected(self):
        teams=[{"team":{"id":"1","displayName":"Team A"}},
               {"team":{"id":"2","displayName":"Team B"}}]
        def roster(team_id, year):
            return {"athletes":[{"id":team_id+"1234","displayName":"Sample Player",
                                 "position":{"displayName":"Guard"}}]}
        with patch.object(engine,"espn_teams",return_value=teams), \
             patch.object(engine,"espn_roster",side_effect=roster):
            found=engine.historical_player_index(2027,["Sample Player"])
        self.assertNotIn("sampleplayer",found)

if __name__=="__main__":
    unittest.main()
