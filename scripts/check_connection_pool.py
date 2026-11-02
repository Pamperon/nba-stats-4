"""Real PostgreSQL pool integration. Refuses any non-loopback test database."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import os
from pathlib import Path
import sys
from unittest.mock import patch
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import ConnectionPool, PoolTimeout

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage


def main():
    url = os.environ['POOL_TEST_DATABASE_URL']
    options = conninfo_to_dict(url)
    if options.get('host') not in ('localhost', '127.0.0.1', '::1'):
        raise RuntimeError('Pool integration requires a loopback PostgreSQL server')
    schema = 'pool_test_' + uuid.uuid4().hex

    def local_pool(*args, **kwargs):
        # The isolated CI PostgreSQL container has no certificate. Production
        # storage.open_pool always requires TLS; this override exists only here.
        kwargs['kwargs']['sslmode'] = 'disable'
        return ConnectionPool(*args, **kwargs)
    local_pool.check_connection = ConnectionPool.check_connection

    with patch.dict(os.environ, {'DATABASE_URL': url, 'NBA_DATABASE_POOL_ENABLED': '1'}), \
            patch.object(storage, 'ConnectionPool', local_pool):
        try:
            storage.open_pool()
            with storage.connection() as conn:
                conn.execute(f'CREATE SCHEMA {schema}')
                conn.execute(f'CREATE TABLE {schema}.events (id integer PRIMARY KEY)')
                conn.execute(f'INSERT INTO {schema}.events VALUES (1)')
            try:
                with storage.connection() as conn:
                    conn.execute(f'INSERT INTO {schema}.events VALUES (2)')
                    raise ValueError('rollback probe')
            except ValueError:
                pass
            with storage.connection() as conn:
                assert conn.execute(f'SELECT count(*) FROM {schema}.events').fetchone()[0] == 1
                conn.execute("SET LOCAL statement_timeout = '17s'")
            with storage.connection() as conn:
                assert conn.execute('SHOW statement_timeout').fetchone()[0] != '17s'
                assert conn.prepare_threshold is None

            def insert(number):
                with storage.connection() as conn:
                    pid = conn.info.backend_pid
                    conn.execute('SELECT pg_sleep(0.02)')
                    conn.execute(f'INSERT INTO {schema}.events VALUES (%s)', (number,))
                    return pid
            with ThreadPoolExecutor(max_workers=8) as executor:
                pids = set(executor.map(insert, range(10, 34)))
            assert len(pids) <= 4, pids
            with storage.connection() as conn:
                assert conn.execute(f'SELECT count(*) FROM {schema}.events').fetchone()[0] == 25

            with ExitStack() as stack:
                held = [stack.enter_context(storage.connection()) for _ in range(4)]
                try:
                    with storage._pool.connection(timeout=0.05):
                        raise AssertionError('Exceeded four-connection bound')
                except PoolTimeout:
                    pass
                # Kill an idle pooled connection externally, then put it back.
                dead_pid = held[0].info.backend_pid
            with psycopg.connect(url, autocommit=True) as admin:
                admin.execute('SELECT pg_terminate_backend(%s)', (dead_pid,))
            # Check callback must discard/recover the stale connection before
            # passing it to a caller. Acquire all four to exercise that slot.
            with ExitStack() as stack:
                recovered = [stack.enter_context(storage.connection()) for _ in range(4)]
                for conn in recovered:
                    assert conn.execute('SELECT 1').fetchone()[0] == 1
                    assert conn.info.backend_pid != dead_pid
            print('Pool integration passed: commit, rollback, concurrency <=4, timeout, stale recovery, local settings reset')
        finally:
            try:
                with psycopg.connect(url) as cleanup:
                    cleanup.execute(f'DROP SCHEMA IF EXISTS {schema} CASCADE')
            finally:
                storage.close_pool()
            assert storage._pool.closed


if __name__ == '__main__':
    main()
