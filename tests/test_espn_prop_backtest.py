"""Unit tests for offline ESPN historical audit. Run: python -m unittest discover -s tests -p 'test_espn_prop_backtest.py'"""
import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "espn_prop_backtest.py"
spec = importlib.util.spec_from_file_location("espn_prop_backtest", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AuditTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(module.norm("Nikola Jokić"), "nikolajokic")
        self.assertEqual(module.norm("New York Knicks"), "newyorkknicks")

    def test_band_boundaries(self):
        for name, low, high in module.BANDS:
            self.assertLessEqual(low, high)
        self.assertEqual(len(set(x[0] for x in module.BANDS)), 3)

    def test_summary_separates_minutes(self):
        rows = [
            {"band":"Singola","market":"PTS","minutes_group":"drop_10_to_25",
             "win":0,"odds":1.8,"predicted":0.7},
            {"band":"Singola","market":"PTS","minutes_group":"stable_or_rising",
             "win":1,"odds":1.8,"predicted":0.7},
        ]
        result = module.summarize(rows)
        self.assertEqual(result["all"]["all"]["n"], 2)
        self.assertEqual(result["minutes"]["drop_10_to_25"]["hit_rate"], 0)
        self.assertEqual(result["minutes"]["stable_or_rising"]["hit_rate"], 1)

if __name__ == "__main__":
    unittest.main()
