"""Offline integration tests for ESPN settlement; no API keys or network."""
import unittest
from unittest.mock import patch
import settle_espn

def event(team_a="Boston Celtics",team_b="New York Knicks"):
    return {"id":"100","date":"2026-10-24T23:00:00Z","status":{"type":{"completed":True}},
            "competitions":[{"competitors":[{"team":{"displayName":team_a}},
                                          {"team":{"displayName":team_b}}]}]}

def summary():
    return {"boxscore":{"players":[
        {"team":{"displayName":"Boston Celtics"},"statistics":[
            {"labels":["MIN","PTS","REB","AST"],"athletes":[
                {"athlete":{"id":"111","displayName":"Jayson Tatum"},"stats":["34","27","8","6"]},
                {"athlete":{"displayName":"DNP"},"didNotPlay":True,"stats":[]}
            ]}]},
        {"team":{"displayName":"New York Knicks"},"statistics":[
            {"labels":["MIN","PTS","REB","AST"],"athletes":[
                {"athlete":{"id":"222","displayName":"Jalen Brunson"},"stats":["34","25","3","9"]}
            ]}]}
    ]}}

class SettlementTests(unittest.TestCase):
    def test_matches_player_team_and_fixture(self):
        snapshot={"scan_finished_at":"2026-10-24T12:00:00+00:00","results":[
            {"Partita":"Boston Celtics - New York Knicks","Squadra":"Boston Celtics",
             "Giocatore":"Tatum, Jayson","Mercato":"PTS","Linea":24.5,"Scelta":"Over",
             "Prob. stimata %":70},
            {"Partita":"Boston Celtics - New York Knicks","Squadra":"New York Knicks",
             "Giocatore":"Brunson, Jalen","Mercato":"AST","Linea":7.5,"Scelta":"Over",
             "Prob. stimata %":60},
            {"Partita":"Boston Celtics - New York Knicks","Squadra":"Boston Celtics",
             "Giocatore":"Brunson, Jalen","Mercato":"PTS","Linea":20.5,"Scelta":"Over",
             "Prob. stimata %":70}
        ]}
        with patch.object(settle_espn,"final_events",return_value=[event()]), \
             patch.object(settle_espn,"fetch",return_value=summary()):
            verified,n=settle_espn.settle_archive(snapshot,"2026-10-24")
        self.assertEqual(n,3)
        self.assertEqual(len(verified),2)
        self.assertEqual([x["actual"] for x in verified],[27,9])

    def test_id_matching_and_legacy_fallback(self):
        stats = settle_espn.player_stats(summary())
        team = settle_espn.engine.normalized_name("Boston Celtics")
        self.assertEqual(stats[(team, "id:111")]["PTS"], 27)
        self.assertEqual(stats[(team, settle_espn.engine.espn_player_key("Tatum, Jayson"))]["REB"], 8)

    def test_missing_archived_fixture_rejected(self):
        snapshot={"scan_finished_at":"2026-10-24T12:00:00+00:00",
                  "results":[{"Partita":"Boston Celtics - New York Knicks",
                              "Squadra":"Boston Celtics","Giocatore":"Tatum, Jayson",
                              "Mercato":"PTS","Linea":20.5,"Scelta":"Over",
                              "Prob. stimata %":70},
                             {"Partita":"Miami Heat - Orlando Magic",
                              "Squadra":"Miami Heat","Giocatore":"Test, Player",
                              "Mercato":"PTS","Linea":10.5,"Scelta":"Over",
                              "Prob. stimata %":70}]}
        with patch.object(settle_espn,"final_events",return_value=[event()]), \
             patch.object(settle_espn,"fetch",return_value=summary()):
            with self.assertRaisesRegex(ValueError,"missing 1 archived fixtures"):
                settle_espn.settle_archive(snapshot,"2026-10-24")

    def test_malformed_archived_fixture_rejected(self):
        snapshot={"scan_finished_at":"2026-10-24T12:00:00+00:00",
                  "results":[{"Partita":"Boston Celtics","Squadra":"Boston Celtics",
                              "Giocatore":"Tatum, Jayson","Mercato":"PTS",
                              "Linea":20.5,"Scelta":"Over","Prob. stimata %":70}]}
        with patch.object(settle_espn,"final_events",return_value=[event()]), \
             patch.object(settle_espn,"fetch",return_value=summary()):
            with self.assertRaisesRegex(ValueError,"Malformed archived fixture"):
                settle_espn.settle_archive(snapshot,"2026-10-24")

    def test_post_tipoff_snapshot_rejected(self):
        snapshot={"scan_finished_at":"2026-10-25T00:00:00+00:00",
                  "results":[{"Partita":"Boston Celtics - New York Knicks"}]}
        with patch.object(settle_espn,"final_events",return_value=[event()]), \
             patch.object(settle_espn,"fetch",return_value=summary()):
            with self.assertRaisesRegex(ValueError,"after at least one"):
                settle_espn.settle_archive(snapshot,"2026-10-24")

    def test_nonfinal_rejected(self):
        with patch.object(settle_espn,"fetch",return_value={
            "events":[{"status":{"type":{"completed":False}}}]}):
            with self.assertRaises(ValueError):
                settle_espn.final_events("2026-10-24")

if __name__=="__main__":
    unittest.main()
