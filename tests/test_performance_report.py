import unittest
from performance_report import report

class PerformanceReportTests(unittest.TestCase):
    def test_market_and_date_metrics(self):
        rows = [
            dict(date="2026-10-23",market="PTS",probability_bin=70,n=10,wins=8,sum_p=7.0,sum_brier=1.8),
            dict(date="2026-10-24",market="AST",probability_bin=60,n=5,wins=2,sum_p=3.0,sum_brier=1.2)]
        out = report(rows)
        self.assertEqual(out["overall"][0]["n"],15)
        self.assertEqual(out["overall"][0]["wins"],10)
        self.assertEqual(len(out["by_date"]),2)
        self.assertEqual(len(out["by_market"]),2)
        self.assertFalse(out["combination_backtest_available"])
        self.assertEqual(out["odds_api_calls"],0)
    def test_empty(self):
        self.assertEqual(report([])["overall"],[])

if __name__ == "__main__":
    unittest.main()
