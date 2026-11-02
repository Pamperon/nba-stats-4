import importlib
import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import admin_monitor

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test-token', 'ODDSPAPI_API_KEY': 'offline-test-key'}):
    main = importlib.import_module('main')


class AdminMonitorTests(unittest.TestCase):
    def test_private_data_requires_auth_and_success_is_not_cached(self):
        client = TestClient(main.app)
        self.addCleanup(client.close)
        with patch.object(admin_monitor, 'report', return_value={'read_only': True}) as report:
            for headers in ({}, {'Authorization': 'Bearer wrong'}):
                self.assertEqual(client.get('/api/admin/monitor', headers=headers).status_code, 401)
            report.assert_not_called()
            response = client.get('/api/admin/monitor', headers={'Authorization': 'Bearer offline-test-token'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['cache-control'], 'no-store')
        page = client.get('/admin/monitor')
        self.assertEqual(page.status_code, 200)
        self.assertIn("frame-ancestors 'none'", page.headers['content-security-policy'])
        self.assertEqual(page.headers['cache-control'], 'no-store')

    def test_database_failure_returns_generic_error(self):
        client = TestClient(main.app)
        self.addCleanup(client.close)
        with patch.object(admin_monitor, 'report', side_effect=RuntimeError('private connection detail')):
            response = client.get('/api/admin/monitor', headers={'Authorization': 'Bearer offline-test-token'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private connection', response.text)

    def test_bounded_queries_and_honest_missing_freshness(self):
        now = datetime(2026, 11, 2, tzinfo=timezone.utc)
        db = MagicMock()
        conn = db.return_value.__enter__.return_value
        conn.execute.return_value.fetchall.side_effect = [
            [(date(2026, 11, 1), 10, 9)], [('PTS', 70, 9, 6, 6.3, 2.0)],
            [(date(2026, 11, 2), 'partial', now, None, 'cache', 1, 200, ['No lines'], {}, {})],
            [(date(2026, 11, 2), 'done', 'Done', now, now)], [('success', 4)]]
        with patch.object(admin_monitor.storage, 'connection', db):
            data = admin_monitor.report()
        self.assertEqual(data['coverage'][0]['gap'], 1)
        self.assertIsNone(data['scans'][0]['odds_fetched_at'])
        self.assertEqual(data['scans'][0]['http_requests'], 1)
        self.assertEqual(data['odds_api_calls'], 0)
        statements = [call.args[0].strip().upper() for call in conn.execute.call_args_list]
        self.assertTrue(all(s.startswith(('SELECT ', 'SET LOCAL ')) for s in statements))
