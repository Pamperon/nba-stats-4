import unittest
from calibration_validation import walk_forward

class WalkForwardTests(unittest.TestCase):
    def test_future_does_not_train_past(self):
        rows=[
            {"date":"2026-10-20","market":"PTS","probability_bin":70,
             "n":300,"wins":150,"sum_p":225.0,"sum_brier":90.0},
            {"date":"2026-10-21","market":"PTS","probability_bin":70,
             "n":100,"wins":55,"sum_p":75.0,"sum_brier":25.0}
        ]
        result=walk_forward(rows)
        self.assertEqual(result["n"],400)
        self.assertEqual(result["daily"][0]["adjusted_predictions"],0)
        self.assertEqual(result["daily"][1]["adjusted_predictions"],100)
        self.assertLess(result["daily"][1]["brier_candidate"],
                        result["daily"][1]["brier_original"])

    def test_pooled_market_fallback_without_future_leakage(self):
        from calibration import calibrated_probability
        rows = []
        for day in ("2026-10-20", "2026-10-21"):
            for bucket in (40, 50, 60, 70, 80):
                rows.append({"date":day,"market":"PTS","probability_bin":bucket,
                             "n":12,"wins":3,"sum_p":12*(bucket+5)/100,
                             "sum_brier":3.0})
        result = walk_forward(rows)
        self.assertEqual(result["daily"][0]["adjusted_predictions"], 0)
        self.assertGreater(result["daily"][1]["adjusted_predictions"], 0)
        self.assertEqual(calibrated_probability("AST", .65,
            [{"market":"PTS","probability_bin":60,"n":100,
              "observed":.4,"predicted":.65}]), .65)

    def test_sparse_history_no_adjustment(self):
        rows=[{"date":"2026-10-21","market":"AST","probability_bin":60,
               "n":12,"wins":6,"sum_p":7.2,"sum_brier":3.0}]
        result=walk_forward(rows)
        self.assertFalse(result["improved"])
        self.assertEqual(result["brier_original"],result["brier_candidate"])

if __name__=="__main__":
    unittest.main()
