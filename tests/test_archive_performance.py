"""Offline regression tests for pregame selection and correlated alternate lines."""
import unittest
from scripts.archive_performance import summarize, summarize_unique_opportunities

def row(line, odds, p, actual=25, name="Player One"):
    return {"Partita":"Team A - Team B", "Squadra":"Team A",
            "Giocatore":name, "Mercato":"PTS", "Linea":line,
            "Quota":odds, "Prob. stimata %":p, "Scelta":"Over",
            "actual":actual, "played":True}

class ArchivePerformanceTests(unittest.TestCase):
    def test_all_lines_retained_in_full_view(self):
        rows=[row(19.5,1.3,80),row(24.5,1.8,60)]
        self.assertEqual(summarize(rows)["overall"]["n"],2)

    def test_best_value_selected_before_result_matching(self):
        # The higher-value 24.5 line is missing from ESPN settlement.
        # The lower-value line must not be substituted using hindsight.
        archive=[row(19.5,1.3,80),row(24.5,1.8,70)]
        verified=[archive[0]]
        result=summarize_unique_opportunities(verified,archive)
        self.assertEqual(result["unique_player_market_games"],1)
        self.assertEqual(result["verified_selections"],0)
        self.assertEqual(result["groups"],{})

    def test_over_and_under_are_distinct_opportunities(self):
        over = row(24.5, 1.8, 60)
        under = dict(over, Scelta="Under", **{"Prob. stimata %": 65})
        archive = [over, under]
        result = summarize_unique_opportunities(archive, archive)
        self.assertEqual(result["unique_player_market_games"], 2)
        self.assertEqual(result["verified_selections"], 2)

    def test_distinct_players_remain_distinct(self):
        archive=[row(19.5,1.3,80),row(24.5,1.8,70),
                 row(19.5,1.4,80,name="Player Two")]
        result=summarize_unique_opportunities(archive,archive)
        self.assertEqual(result["unique_player_market_games"],2)
        self.assertEqual(result["verified_selections"],2)

if __name__=="__main__":
    unittest.main()
