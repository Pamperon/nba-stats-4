"""HTTP and scan lifecycle regressions; external I/O is mocked throughout."""
import contextlib
import datetime as dt
import importlib
import io
import os
import socket
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test-token', 'ODDSPAPI_API_KEY': 'offline-test-key'}):
    main = importlib.import_module('main')


class AppRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network is disabled'))
        self.network.start()
        self.addCleanup(self.network.stop)
        main.jobs.clear()
        # No context manager: these HTTP tests do not run startup or the scheduler.
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def test_scan_requires_authentication(self):
        with patch.object(main.engine, 'get_fixtures') as odds:
            self.assertEqual(self.client.post('/api/scan?date=2026-10-25').status_code, 401)
            odds.assert_not_called()

    def test_saved_time_reports_actual_http_requests_including_zero(self):
        for count in (0, 4):
            snapshot = {'saved_at': '2026-10-25T11:48:23+00:00', 'odds_api_http_requests_scan': count, 'quote_lines_scan': 328}
            with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'latest', return_value=snapshot):
                response = self.client.get('/api/saved/time?date=2026-10-25')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['odds_api_requests_scan'], count)
            self.assertEqual(response.json()['quote_lines_scan'], 328)

    def test_legacy_snapshot_never_invents_http_request_count(self):
        snapshot = {'saved_at': '2026-10-25T11:48:23+00:00', 'odds_api_calls_scan': 328}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'latest', return_value=snapshot):
            response = self.client.get('/api/saved/time?date=2026-10-25')
        self.assertEqual(response.json()['odds_api_requests_scan'], 'non misurate')
        self.assertIsNone(response.json()['odds_api_http_requests_scan'])

    def test_job_survives_restart_even_when_newer_snapshot_exists(self):
        snapshot = {'job_id': 'older', 'date': '2026-10-25', 'state': 'done'}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'by_job_id', return_value=snapshot) as read:
            response = self.client.get('/api/scan/older', headers={'Authorization': 'Bearer ' + main.TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['job_id'], 'older')
        read.assert_called_once_with('older')

    def test_storage_lookup_uses_requested_job(self):
        connection = MagicMock()
        connection.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            'older', {'date': '2026-10-25'}, dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc))
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'connection', connection):
            result = main.storage.by_job_id('older')
        self.assertEqual(result['job_id'], 'older')
        execute = connection.return_value.__enter__.return_value.execute
        self.assertEqual(execute.call_args.args[1], ('older',))
        self.assertIn('WHERE job_id=%s', execute.call_args.args[0])

    def test_complete_scan_saves_count_and_partial_state(self):
        for status in ('ok', 'vuota'):
            main.jobs['offline'] = {'date': '2026-10-25', 'state': 'queued', 'scan_source': 'github'}
            report = [{'stato': status}]
            connection = MagicMock()
            connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
            with patch.object(main.engine, 'get_fixtures', return_value=[{}]), patch.object(main.engine, 'fixture_is_upcoming', return_value=True), patch.object(main.engine, 'get_markets', return_value={}), patch.object(main.engine, 'finder_scan', return_value=([], [], 328, 0, [], [], {}, report)), patch.object(main.engine, 'odds_api_request_count', return_value=4), patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'connection', connection), patch.object(main.storage, 'save') as save, contextlib.redirect_stdout(io.StringIO()) as log:
                main.do_scan('offline', '2026-10-25')
            saved = save.call_args.args[1]
            self.assertEqual(saved['state'], 'done' if status == 'ok' else 'partial')
            self.assertEqual(saved['odds_api_http_requests_scan'], 4)
            self.assertIn('odds_api_http_requests=4', log.getvalue())

    def test_failed_scan_records_requests_and_error_without_saving(self):
        main.jobs['offline'] = {'date': '2026-10-25', 'state': 'queued'}
        with patch.object(main.engine, 'get_fixtures', side_effect=RuntimeError('Simulated provider failure')), patch.object(main.engine, 'odds_api_request_count', return_value=2), patch.object(main.storage, 'save') as save, self.assertLogs(main.logger, 'ERROR'), contextlib.redirect_stdout(io.StringIO()) as log:
            main.do_scan('offline', '2026-10-25')
        self.assertEqual(main.jobs['offline']['state'], 'error')
        self.assertEqual(main.jobs['offline']['odds_api_http_requests_scan'], 2)
        self.assertIn('odds_api_http_requests=2', log.getvalue())
        save.assert_not_called()

    def test_started_games_are_removed_from_public_snapshot(self):
        snapshot = {'date': '2026-10-25', 'results': [
            {'Partita': 'Boston Celtics - New York Knicks', 'Giocatore': 'A'},
            {'Partita': 'Miami Heat - Orlando Magic', 'Giocatore': 'B'}]}
        with patch.object(main, 'schedule', return_value={'games': [
                {'home': 'Boston Celtics', 'away': 'New York Knicks', 'upcoming': False},
                {'home': 'Miami Heat', 'away': 'Orlando Magic', 'upcoming': True}]}):
            result = main.visible_snapshot(snapshot)
        self.assertEqual([r['Giocatore'] for r in result['results']], ['B'])
        self.assertEqual(len(snapshot['results']), 2)
