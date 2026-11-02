"""Regression tests for the read-only calibration audit (no database access)."""
import unittest
from scripts.audit_calibration import summarize


class CalibrationAuditTests(unittest.TestCase):
    def test_weighted_aggregation_and_market_separation(self):
        rows = [
            ("PTS", 80, 10, 7, 8.5, 1.9),
            ("PTS", 90, 5, 5, 4.7, 0.1),
            ("AST", 80, 4, 2, 3.4, 0.8),
        ]
        results = {(r["market"], r["probability_bin"]): r for r in summarize(rows)}
        self.assertEqual(results[("PTS", "all")]["n"], 15)
        self.assertEqual(results[("PTS", "all")]["wins"], 12)
        self.assertEqual(results[("PTS", "all")]["estimated_pct"], 88.0)
        self.assertEqual(results[("PTS", "all")]["observed_pct"], 80.0)
        self.assertEqual(results[("AST", "all")]["n"], 4)
        self.assertTrue(results[("AST", "all")]["sample_warning"])

    def test_empty_input(self):
        self.assertEqual(summarize([]), [])


if __name__ == "__main__":
    unittest.main()
