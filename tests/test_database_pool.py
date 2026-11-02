import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import storage


class DatabasePoolTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test',
                                                  'NBA_DATABASE_POOL_ENABLED': '1'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.state = patch.object(storage, '_pool', None)
        self.state.start()
        self.addCleanup(self.state.stop)

    def test_import_and_cli_path_do_not_start_pool(self):
        with patch.object(storage.psycopg, 'connect') as connect:
            self.assertIs(storage.connection(), connect.return_value)
        connect.assert_called_once_with('postgresql://test', connect_timeout=10,
                                        sslmode='require')
        self.assertEqual(storage.pool_stats(), {'enabled': False})

    def test_concurrent_initialization_creates_one_bounded_pool(self):
        with patch.object(storage, 'ConnectionPool') as factory:
            candidate = factory.return_value
            candidate.closed = False
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda _: storage.open_pool(), range(16)))
            factory.assert_called_once()
            candidate.open.assert_called_once_with(wait=True, timeout=10)
            options = factory.call_args.kwargs
            self.assertEqual((options['min_size'], options['max_size']), (1, 4))
            self.assertEqual(options['max_waiting'], 16)
            self.assertIsNone(options['kwargs']['prepare_threshold'])
            self.assertEqual(options['kwargs']['sslmode'], 'require')
            self.assertIs(storage.connection(), candidate.connection.return_value)
            candidate.get_stats.return_value = {'pool_size': 1, 'requests_num': 3}
            self.assertEqual(storage.pool_stats(), {'enabled': True, 'closed': False,
                                                   'pool_size': 1, 'requests_num': 3})

    def test_failed_start_cleans_up_and_does_not_publish_broken_pool(self):
        with patch.object(storage, 'ConnectionPool') as factory:
            factory.return_value.open.side_effect = RuntimeError('unavailable')
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                storage.open_pool()
            factory.return_value.close.assert_called_once()
        self.assertIsNone(storage._pool)

    def test_disable_preserves_direct_connection_path(self):
        with patch.dict(os.environ, {'NBA_DATABASE_POOL_ENABLED': '0'}), \
                patch.object(storage, 'ConnectionPool') as factory:
            storage.open_pool()
        factory.assert_not_called()

    def test_shutdown_does_not_fall_back_to_unbounded_connections(self):
        candidate = MagicMock()
        with patch.object(storage, '_pool', candidate), \
                patch.object(storage.psycopg, 'connect') as connect:
            storage.close_pool()
            candidate.close.assert_called_once_with(timeout=5)
            storage.connection()
            candidate.connection.assert_called_once()
            connect.assert_not_called()
