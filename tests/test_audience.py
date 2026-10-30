"""Collection privacy, authentication and failure isolation, without network I/O."""
import importlib
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import audience

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-test-token', 'ODDSPAPI_API_KEY': 'offline-test-key'}):
    main = importlib.import_module('main')


class AudienceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {'Origin': 'https://basketlab.it'}
        self.payload = {'source': 'whatsapp', 'events': ['apertura', 'quote']}

    def test_no_private_or_unbounded_payloads(self):
        for value in [None, {}, {**self.payload, 'ip': '1.2.3.4'},
                      {**self.payload, 'source': 'arbitrary-person-name'},
                      {**self.payload, 'events': ['searched-player-name']},
                      {**self.payload, 'events': ['quote'] * 11}]:
            with self.assertRaises(ValueError):
                audience.validate(value)

    def test_valid_batch_records_only_enumerated_values(self):
        with patch.object(audience, 'record') as record, patch.object(audience, 'allowed', return_value=True):
            result = self.client.post('/api/audience/event', json=self.payload, headers=self.headers)
        self.assertEqual(result.status_code, 204)
        record.assert_called_once_with('whatsapp', ['apertura', 'quote'])
        self.assertNotIn('set-cookie', result.headers)

    def test_foreign_origins_robots_and_optout_not_recorded(self):
        with patch.object(audience, 'record') as record:
            for headers in [{}, {'Origin': 'https://evil.example'},
                            {**self.headers, 'DNT': '1'}, {**self.headers, 'Sec-GPC': '1'},
                            {**self.headers, 'User-Agent': 'Googlebot'}]:
                self.client.post('/api/audience/event', json=self.payload, headers=headers)
        record.assert_not_called()

    def test_oversized_invalid_and_limited_batches_not_recorded(self):
        with patch.object(audience, 'record') as record, patch.object(audience, 'allowed', return_value=True):
            for body in ['{' , 'x' * 3000, '{"source":"whatsapp","events":["personal"]}']:
                self.client.post('/api/audience/event', content=body, headers=self.headers)
        record.assert_not_called()
        with patch.object(audience, 'record') as record, patch.object(audience, 'allowed', return_value=False):
            self.client.post('/api/audience/event', json=self.payload, headers=self.headers)
        record.assert_not_called()

    def test_collection_failure_does_not_break_site(self):
        with patch.object(audience, 'record', side_effect=RuntimeError('offline')), patch.object(audience, 'allowed', return_value=True):
            self.assertEqual(self.client.post('/api/audience/event', json=self.payload, headers=self.headers).status_code, 204)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_report_is_private_bounded_and_uncached(self):
        self.assertEqual(self.client.get('/api/audience/report').status_code, 401)
        headers = {'Authorization': 'Bearer ' + main.TOKEN}
        self.assertEqual(self.client.get('/api/audience/report?days=999', headers=headers).status_code, 422)
        with patch.object(audience, 'report', return_value={'rows': []}):
            result = self.client.get('/api/audience/report', headers=headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.headers['cache-control'], 'no-store')
        page = self.client.get('/admin/visite')
        self.assertIn('noindex', page.headers['x-robots-tag'])
        self.assertEqual(page.headers['cache-control'], 'no-store')

    def test_daily_identifier_validation_and_request_isolation(self):
        payload = {'day': '2026-10-30', 'id': 'a' * 32}
        for invalid in [None, {}, {**payload, 'source': 'google'},
                        {**payload, 'id': 'personal-email@example.com'},
                        {**payload, 'day': '2026-1-1'}]:
            with self.assertRaises(ValueError):
                audience.validate_unique(invalid)
        with patch.object(audience, 'record_unique') as record, patch.object(audience, 'allowed', return_value=True):
            response = self.client.post('/api/audience/unique', json=payload, headers=self.headers)
            record.assert_called_once_with(payload['day'], payload['id'])
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertNotIn('set-cookie', response.headers)
        with patch.object(audience, 'record_unique') as record:
            for headers in [{}, {**self.headers, 'DNT': '1'}, {**self.headers, 'Sec-GPC': '1'}, {**self.headers, 'User-Agent': 'Googlebot'}]:
                self.client.post('/api/audience/unique', json=payload, headers=headers)
            record.assert_not_called()

    def test_wrong_day_never_opens_database(self):
        with patch.object(audience.storage, 'connection') as connection:
            audience.record_unique('2000-01-01', 'b' * 32)
            connection.assert_not_called()
