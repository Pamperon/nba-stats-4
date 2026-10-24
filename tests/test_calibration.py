"""Run: python -m unittest tests.test_calibration"""
import unittest
from calibration import aggregate

class CalibrationTests(unittest.TestCase):
    def test_over_under_and_missing(self):
        base = {"Mercato":"PTS","Prob. stimata %":70,"Linea":19.5,
                "Scelta":"Over","actual":22,"played":True}
        rows = [base, {**base,"Scelta":"Under"},
                {**base,"Prob. stimata %":None},
                {**base,"played":False},
                {**base,"Mercato":"REB","Prob. stimata %":85,"Linea":8.5,
                 "actual":6,"Scelta":"Under"}]
        result = aggregate(rows)
        self.assertEqual(result[("PTS",70)]["n"],2)
        self.assertEqual(result[("PTS",70)]["wins"],1)
        self.assertEqual(result[("REB",80)]["wins"],1)
        self.assertEqual(sum(x["n"] for x in result.values()),3)

    def test_push_excluded(self):
        row = {"Mercato":"AST","Prob. stimata %":50,"Linea":5,
               "Scelta":"Over","actual":5,"played":True}
        self.assertEqual(aggregate([row]),{})

if __name__=="__main__":
    unittest.main()
