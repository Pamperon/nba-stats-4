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

class CurrentIdentityTests(unittest.TestCase):
    def test_known_odds_names_match_espn_roster_names(self):
        self.assertEqual(engine.espn_player_key('Carrington, Carlton'), engine.normalized_name('Bub Carrington'))
        self.assertEqual(engine.espn_player_key('Sarr, Alexandre'), engine.normalized_name('Alex Sarr'))
        for given, official in [('Johnson, Morez','Morez Johnson Jr.'),('Washington Jr., PJ','PJ Washington'),('Smith, Jabari','Jabari Smith Jr.'),('Acuff, Darius','Darius Acuff Jr.'),('Brown, Mikel','Mikel Brown Jr.')]:
            self.assertEqual(engine.espn_player_key(given),engine.normalized_name(official))

    def test_current_roster_index_uses_both_official_names_and_rejects_duplicates(self):
        teams=[{'team':{'id':'27','displayName':'Washington Wizards'}}, {'team':{'id':'1','displayName':'Other Team'}}]
        rosters={'27':{'athletes':[{'id':'4845374','displayName':'Bub Carrington','fullName':'Carlton Carrington','position':{}}, {'id':'5160992','displayName':'Alex Sarr','fullName':'Alex Sarr','position':{}}, {'id':'101','displayName':'Same Player','position':{}}]},
                 '1':{'athletes':[{'id':'102','displayName':'Same Player','position':{}}]}}
        with patch.object(engine,'espn_teams',return_value=teams), patch.object(engine,'espn_roster',side_effect=lambda tid, year=None:rosters[tid]):
            index=engine.finder_player_index(2027)
        self.assertEqual(index[engine.espn_player_key('Carrington, Carlton')]['id'],'4845374')
        self.assertEqual(index[engine.espn_player_key('Sarr, Alexandre')]['id'],'5160992')
        self.assertEqual(index[engine.normalized_name('Carlton Carrington')]['id'],'4845374')
        self.assertIsNone(index['sameplayer'])
