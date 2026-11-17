import unittest
from unittest.mock import MagicMock, patch
import odds_coverage_probe as probe


class CoverageProbeTests(unittest.TestCase):
    def test_cached_summary_distinguishes_missing_fixture_from_missing_bookmaker(self):
        calendar = {'data': [
            {'fixtureId': 'a', 'startTime': '2100-11-18T01:00:00Z'},
            {'fixtureId': 'b', 'startTime': '2100-11-18T02:00:00Z'},
            {'fixtureId': 'other', 'startTime': '2100-11-19T01:00:00Z'}]}
        feed = {'identity': 'corrected-feed', 'data': {'a': {
            'fixtureId': 'a', 'startTime': '2100-11-18T01:00:00Z', 'bookmakerOdds': {}}}}
        with patch.object(probe.storage, 'cache_read', side_effect=[calendar, {'data': {}}, feed]):
            report, targets, _, _ = probe.cached_report('2100-11-18')
        self.assertEqual(len(targets), 2)
        self.assertEqual(report['feed_fixture_count'], 1)
        self.assertTrue(report['target_coverage'][0]['present_in_bulk'])
        self.assertFalse(report['target_coverage'][0]['bookmaker_present'])
        self.assertFalse(report['target_coverage'][1]['present_in_bulk'])

    def test_reservation_precedes_single_request_and_rerun_cannot_repeat_it(self):
        connection = MagicMock()
        conn = connection.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.side_effect = [None, (0,), ('reserved',)]
        caller = MagicMock(count=1, history=[{'endpoint': 'account'}, {'endpoint': 'odds'}])
        caller.get.side_effect = [{}, {'fixtureId': 'exact', 'bookmakerOdds': {}}]
        cached = ({'target_coverage': []}, [{'fixtureId': 'exact', 'startTime': '2100-11-18T01:00:00Z'}], {}, {})
        with patch.object(probe.storage, 'connection', connection), \
             patch.object(probe, 'cached_report', return_value=cached), \
             patch.object(probe, 'Caller', return_value=caller) as make_caller:
            result = probe.run_once('2100-11-18', 'offline-key')
        self.assertEqual(result['state'], 'done')
        self.assertEqual(result['billable_http_attempts'], 1)
        make_caller.assert_called_once_with('offline-key', limit=1, job_id='nba-feed-coverage:2100-11-18:v1')
        self.assertEqual(caller.get.call_args_list[1].kwargs['fixtureId'], 'exact')
        self.assertEqual(caller.get.call_count, 2)  # Free account + one odds request.
        conn.execute.return_value.fetchone.side_effect = [({'state': 'done', 'comparison': {}},)]
        with patch.object(probe.storage, 'connection', connection), patch.object(probe, 'Caller') as make_caller:
            self.assertTrue(probe.run_once('2100-11-18', 'offline-key')['reused'])
        make_caller.assert_not_called()

    def test_active_scan_or_competing_reservation_prevents_any_provider_call(self):
        for rows in ([None, (1,)], [None, (0,), None]):
            connection = MagicMock()
            connection.return_value.__enter__.return_value.execute.return_value.fetchone.side_effect = rows
            with patch.object(probe.storage, 'connection', connection), patch.object(probe, 'Caller') as caller:
                if len(rows) == 2:
                    with self.assertRaises(probe.ProbeError):
                        probe.run_once('2100-11-18', 'offline-key')
                else:
                    self.assertEqual(probe.run_once('2100-11-18', 'offline-key')['state'], 'reserved')
            caller.assert_not_called()

    def test_account_projection_excludes_identity_and_credentials(self):
        report = probe.account_summary({'apiKey': 'secret', 'email': 'private@example.test',
            'subscriptions': [{'is_active': True, 'request_count': 20, 'request_limit': 300,
                'sport_ids': [11], 'bookmakers': {'bet365.it': {'has_player_props': True}}}]})
        self.assertTrue(report['bet365_it_player_props'])
        self.assertNotIn('apiKey', report)
        self.assertNotIn('email', report)
