"""No-network tests: picks must be selected before actuals are available."""
import unittest
from scripts.recommendation_backtest import select_pregame, evaluate

def pick(name, line, odds, probability, actual=None):
    row = {"Partita":"A - B","Squadra":"A","Giocatore":name,"Mercato":"PTS",
           "Scelta":"Over","Linea":line,"Quota":odds,"Prob. stimata %":probability}
    if actual is not None:
        row.update(actual=actual,played=True)
    return row

class RecommendationBacktestTests(unittest.TestCase):
    def test_distinct_players_and_best_value(self):
        rows=[pick("Alpha",19.5,1.8,70),pick("Alpha",24.5,1.8,60),
              pick("Beta",19.5,1.55,75),pick("Beta",24.5,1.55,60),
              pick("Gamma",9.5,1.55,70)]
        selected=select_pregame(rows)
        self.assertEqual(len(selected["singola"]),1)
        self.assertEqual(selected["singola"][0]["Linea"],19.5)
        self.assertEqual(len(selected["doppia"]),2)
        self.assertEqual({r["Giocatore"] for r in selected["doppia"]},{"Beta","Gamma"})

    def test_missing_settlement_is_not_replaced(self):
        archive=[pick("Alpha",19.5,1.8,70),pick("Beta",19.5,1.8,55)]
        result=evaluate(archive,[pick("Beta",19.5,1.8,55,25)])
        self.assertFalse(result["singola"]["settled"])
        self.assertIsNone(result["singola"]["unit_profit"])

    def test_correct_settlement(self):
        archive=[pick("Alpha",19.5,1.8,70)]
        result=evaluate(archive,[pick("Alpha",19.5,1.8,70,25)])
        self.assertTrue(result["singola"]["settled"])
        self.assertAlmostEqual(result["singola"]["unit_profit"],0.8)

if __name__=="__main__":
    unittest.main()
