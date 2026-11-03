import unittest
from unittest.mock import MagicMock, patch
import odds_provider_probe as probe


class ProviderProbeTests(unittest.TestCase):
    def test_account_redacts_secrets(self):
        result = probe.account_summary({"api_key": "SECRET", "current_subscription_id": "private",
            "subscriptions": [{"subscription_id": "private", "request_count": 12,
                "request_limit": 5000, "sport_ids": [11], "bookmakers": {
                    "bet365.it": {"has_player_props": True}}}]})
        self.assertEqual(result["request_count"], 12)
        self.assertTrue(result["bet365_it_player_props"])
        self.assertNotIn("SECRET", str(result))
        self.assertNotIn("private", str(result))

    def test_response_shapes(self):
        fixture = {"fixtureId": "a"}
        for payload in ([fixture], fixture, {"data": [fixture]}, {"fixtures": {"a": fixture}}):
            self.assertEqual(probe.fixtures_list(payload), [fixture])
        with self.assertRaises(probe.ProbeError):
            probe.fixtures_list({"unexpected": True})

    def test_active_player_market_coverage(self):
        catalog = {"1": {"marketType": "players-points"}, "2": {"marketType": "totals"}}
        player = {"active": True, "playerName": "Example", "price": 1.8}
        market = {"marketActive": True, "outcomes": {"o": {"players": {"p": player}}}}
        fixture = {"fixtureId": "f", "bookmakerOdds": {"bet365.it": {
            "bookmakerIsActive": True, "markets": {"1": market, "2": market}}}}
        self.assertEqual(probe.coverage(fixture, catalog)["active_selections"], 1)
        self.assertEqual(probe.compare(fixture, fixture, catalog)["missing_from_bulk"], 0)
        fixture["bookmakerOdds"]["bet365.it"]["suspended"] = True
        self.assertEqual(probe.selections(fixture, catalog), {})

    @patch.object(probe.time, "sleep")
    @patch.object(probe.scan_tracking, "finish_request")
    @patch.object(probe.scan_tracking, "start_request", return_value="request")
    @patch.object(probe.requests, "get")
    def test_budget_is_five_without_retries(self, get, start, finish, sleep):
        get.return_value = MagicMock(ok=True, status_code=200)
        get.return_value.json.return_value = {}
        caller = probe.Caller("SECRET")
        for _ in range(5):
            caller.get("odds", fixtureId="f")
        with self.assertRaises(probe.ProbeError):
            caller.get("odds", fixtureId="f")
        self.assertEqual(get.call_count, 5)
        self.assertEqual(start.call_count, 5)
        caller.get("account")
        self.assertEqual(caller.count, 5)
        self.assertEqual(start.call_count, 5)

    @patch.object(probe.time, "sleep")
    @patch.object(probe.scan_tracking, "finish_request")
    @patch.object(probe.scan_tracking, "start_request", return_value="request")
    @patch.object(probe.requests, "get", side_effect=probe.requests.RequestException("SECRET URL"))
    def test_transport_error_is_redacted(self, get, start, finish, sleep):
        caller = probe.Caller("SECRET")
        with self.assertRaises(probe.ProbeError) as caught:
            caller.get("odds")
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(get.call_count, 1)
        finish.assert_called_once_with("request", None)

    @patch.object(probe, "Caller")
    @patch.object(probe.storage, "connection")
    def test_saved_reservation_prevents_repeat_calls(self, connection, caller):
        conn = connection.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = ({"state": "reserved"},)
        result = probe.run_once("SECRET")
        self.assertTrue(result["reused"])
        caller.assert_not_called()

    @patch.object(probe.time, "sleep")
    @patch.object(probe.scan_tracking, "finish_request")
    @patch.object(probe.scan_tracking, "start_request", return_value="request")
    @patch.object(probe.requests, "get")
    def test_supplementary_budget_is_three(self, get, start, finish, sleep):
        get.return_value = MagicMock(ok=True, status_code=200)
        get.return_value.json.return_value = {}
        caller = probe.Caller("SECRET", limit=3, job_id="supplement")
        for _ in range(3):
            caller.get("odds", fixtureId="f")
        with self.assertRaises(probe.ProbeError):
            caller.get("odds", fixtureId="f")
        self.assertEqual(get.call_count, 3)
        self.assertEqual(start.call_args.args[0], "supplement")

    @patch.object(probe, "Caller")
    @patch.object(probe.storage, "connection")
    def test_supplementary_reservation_prevents_repeat(self, connection, caller):
        conn = connection.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = ({"state": "reserved"},)
        self.assertTrue(probe.check_missing_once("SECRET")["reused"])
        caller.assert_not_called()
