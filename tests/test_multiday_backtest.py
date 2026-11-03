import unittest
from scripts.multiday_backtest import aggregate, analyze_dates

class FakeResponse:
    def __init__(self, status):
        self.status_code = status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("Unexpected request")
    def json(self):
        return {}

class FakeSession:
    def __init__(self):
        self.called = []
    def get(self, url, params, timeout):
        self.called.append(params["date"])
        return FakeResponse(404)

class MultiDayBacktestTests(unittest.TestCase):
    def test_aggregate_excludes_unsettled_and_incomplete(self):
        days = [{"proposals": {
            "singola": {"complete": True, "settled": True,
                        "missing_results": 0, "unit_profit": 0.8},
            "doppia": {"complete": True, "settled": False,
                       "missing_results": 1, "unit_profit": None}}},
            {"proposals": {
            "singola": {"complete": True, "settled": True,
                        "missing_results": 0, "unit_profit": -1},
            "doppia": {"complete": False, "settled": False,
                       "missing_results": 0, "unit_profit": None}}}]
        summary = aggregate(days)
        self.assertEqual(summary["singola"]["settled"], 2)
        self.assertAlmostEqual(summary["singola"]["roi"], -0.1)
        self.assertEqual(summary["doppia"]["settled"], 0)
        self.assertIsNone(summary["doppia"]["roi"])
        self.assertEqual(summary["doppia"]["missing_results"], 1)

    def test_brier_score_uses_only_verified_legs(self):
        days = [{"proposals": {"singola": {
            "complete": True, "settled": True, "missing_results": 0,
            "unit_profit": -1, "legs": [
                {"estimated_probability": 80, "win": False},
                {"estimated_probability": 90, "win": None}]}}}]
        summary = aggregate(days)["singola"]
        self.assertEqual(summary["verified_legs"], 1)
        self.assertAlmostEqual(summary["brier_score"], 0.64)
        self.assertAlmostEqual(summary["mean_absolute_error"], 0.8)
        self.assertEqual(summary["actual_hit_rate"], 0)
        self.assertAlmostEqual(summary["mean_predicted_probability"], 0.8)
        self.assertAlmostEqual(summary["calibration_gap"], 0.8)
        self.assertFalse(summary["sample_sufficient"])

    def test_today_is_checked_if_archive_available(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        session = FakeSession()
        report = analyze_dates([today], session)
        self.assertEqual(session.called, [today])
        self.assertEqual(report["days_skipped"][0]["reason"], "archive_unavailable")

    def test_unavailable_dates_are_skipped_without_guessing(self):
        session = FakeSession()
        report = analyze_dates(["2026-10-20", "2026-10-21"], session)
        self.assertEqual(report["days_evaluated"], 0)
        self.assertEqual(len(report["days_skipped"]), 2)
        self.assertEqual(report["odds_api_calls"], 0)
        self.assertEqual(session.called, ["2026-10-20", "2026-10-21"])

if __name__ == "__main__":
    unittest.main()
