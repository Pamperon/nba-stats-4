"""Execute production SQL against isolated PostgreSQL/PGlite; never contacts a provider."""
import datetime as dt
import json
import importlib
import os
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import storage
import scan_tracking as tracking
import calibration


class Database:
    def __init__(self):
        self.process = subprocess.Popen(['node', str(ROOT/'tests/tracking_db_bridge.cjs')],
                                        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def query(self, sql, params=()):
        number = 0
        def placeholder(_):
            nonlocal number
            number += 1
            return '$' + str(number)
        sql = re.sub(r'%s', placeholder, sql)
        def encode(value):
            if hasattr(value, 'obj'):
                return json.dumps(value.obj)
            if hasattr(value, 'isoformat'):
                return value.isoformat()
            return value
        self.process.stdin.write(json.dumps({'sql': sql, 'params': [encode(v) for v in params]}) + '\n')
        self.process.stdin.flush()
        raw = self.process.stdout.readline()
        if not raw:
            raise RuntimeError('Test database stopped unexpectedly')
        response = json.loads(raw)
        if 'error' in response:
            raise RuntimeError(response['error'])
        rows = []
        for raw_row in response.get('rows', []):
            row = []
            for value, field in zip(raw_row, response['fields']):
                kind = int(field['dataTypeID'])
                if value is not None and kind == 1082:
                    value = dt.date.fromisoformat(value)
                elif value is not None and kind == 1184:
                    value = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
                row.append(value)
            rows.append(tuple(row))
        return rows

    def connection(self):
        database = self
        class Connection:
            def __enter__(self):
                database.query('BEGIN')
                return self
            def __exit__(self, kind, value, traceback):
                database.query('ROLLBACK' if kind else 'COMMIT')
            def execute(self, sql, params=()):
                self.rows = database.query(sql, params)
                return self
            def fetchone(self):
                return self.rows[0] if self.rows else None
            def fetchall(self):
                return self.rows
        return Connection()

    def close(self):
        self.process.stdin.write('{"close":true}\n')
        self.process.stdin.flush()
        self.process.stdin.close()
        self.process.wait(timeout=20)


def assert_paused(function, *args):
    try:
        function(*args)
    except tracking.ScanPaused:
        return
    raise AssertionError('Expected deploy guard to reject new work')


def main():
    db = Database()
    try:
        with patch.object(storage, 'configured', return_value=True), patch.object(storage, 'connection', side_effect=db.connection):
            storage.initialize()
            tracking.initialize()
            calibration.initialize()
            calibration.initialize()
            from psycopg.types.json import Jsonb
            for _ in range(2):
                db.query("INSERT INTO nba_recommendation_results(snapshot_job_id,scan_date,report) VALUES (%s,%s,%s) ON CONFLICT(snapshot_job_id) DO NOTHING",
                         ('ticket-test', '2026-10-26', Jsonb({'policy':'risk-screen-v1','groups':{}})))
            assert db.query('SELECT count(*) FROM nba_recommendation_results')[0][0] == 1
            import recommendations
            import settle_espn
            ticket_row = {'Giocatore':'SQL Player', 'ESPN ID':'123', 'Partita':'A - B', 'Squadra':'A',
                          'Mercato':'PTS', 'Scelta':'Over', 'Linea':9.5, 'Quota':1.8,
                          'Prob. stimata %':80, 'Value stimato %':44, 'Partite':30,
                          'Stagione %':80, 'Minuti medi':30, 'Minuti ultime 5':29,
                          'Stato analisi':'Valutabile (stima empirica)'}
            storage.save('sql-ticket', {'date':'2026-10-23', 'state':'done', 'results':[ticket_row],
                                       'recommendations':recommendations.select([ticket_row])})
            with patch.object(settle_espn, 'settle_archive', return_value=([{**ticket_row, 'actual':10, 'played':True}],1)):
                assert recommendations.settle_snapshots('2026-10-23') == 1
                assert recommendations.settle_snapshots('2026-10-23') == 0
            assert db.query("SELECT report->'groups'->'Singola'->>'status' FROM nba_recommendation_results WHERE snapshot_job_id='sql-ticket'")[0][0] == 'won'
            storage.initialize()
            tracking.initialize()  # Additive migrations are repeatable.
            storage.save('legacy', {'date':'2026-10-26','state':'done','results':[], 'odds_api_http_requests_scan':6})
            status = tracking.day_status('2026-10-26')
            assert status['state'] == 'done' and status['last_saved']['api_requests'] == 6
            assert status['latest_attempt'] is None

            first = tracking.begin_attempt('failed', '2026-10-26', 'old', 'github')
            assert not first['reused']
            pending = tracking.start_request('failed', 'fixtures')
            responded = tracking.start_request('failed', 'odds')
            tracking.finish_request(responded, 200)
            network = tracking.start_request('failed', 'odds')
            tracking.finish_request(network)
            assert pending != responded != network
            assert tracking.request_usage('failed') == {'logged':3,'responded':1,'uncertain':2}
            tracking.finish_attempt('failed', 'error', 10, 'Test failure')
            status = tracking.day_status('2026-10-26')
            assert status['state'] == 'error'
            assert status['last_saved']['job_id'] == 'legacy'  # Never invent a fresh save.
            assert status['latest_attempt']['api_requests']['logged'] == 3

            tracking.begin_attempt('saved', '2026-10-26', 'old', 'render')
            tracking.heartbeat('saved', 50, 'Halfway')
            assert tracking.begin_attempt('duplicate', '2026-10-26', 'other', 'github')['job_id'] == 'saved'
            assert tracking.begin_attempt('other-date', '2026-10-27', 'other', 'github')['reused']
            storage.save('saved', {'date':'2026-10-26','state':'partial','results':[]})
            # The snapshot commits before the final status write: it still wins.
            assert tracking.day_status('2026-10-26')['state'] == 'partial'
            next_job = tracking.begin_attempt('next-after-save', '2026-10-27', 'old', 'render')
            assert not next_job['reused']  # Committed snapshot releases the prior job even before final metadata.
            tracking.finish_attempt('next-after-save', 'error', 0, 'Synthetic test end')
            tracking.finish_attempt('saved', 'partial', 100, 'Partial')

            tracking.begin_attempt('interrupted', '2026-10-27', 'old', 'manual')
            tracking.start_request('interrupted', 'markets')
            db.query("UPDATE nba_scan_attempts SET heartbeat_at=NOW()-INTERVAL '3 minutes' WHERE job_id='interrupted'")
            status = tracking.day_status('2026-10-27')
            assert status['state'] == 'interrupted'
            assert status['latest_attempt']['api_requests']['uncertain'] == 1

            slot = '2026-10-25T21:00'
            assert storage.claim_slot(slot, 'old')
            tracking.begin_deploy_guard('new')
            assert tracking.deployment_blockers('new') == 1
            assert_paused(storage.claim_slot, '2026-10-26T07:00', 'old')
            assert_paused(tracking.begin_attempt, 'blocked', '2026-10-26', 'old', 'manual')
            # The same claimed batch may continue its second date during deploy.
            tracking.begin_attempt('batch-date-two', '2026-10-26', 'old', 'render', slot)
            assert tracking.deployment_blockers('new') == 2
            tracking.release_deploy_guard('old')  # Cannot release another runtime's guard.
            assert_paused(storage.claim_slot, '2026-10-26T07:00', 'old')
            tracking.finish_attempt('batch-date-two', 'done', 100, 'Done')
            storage.touch_slot(slot)
            storage.finish_slot(slot, True)
            assert tracking.deployment_blockers('new') == 0
            tracking.release_deploy_guard('new')
            assert storage.claim_slot('2026-10-26T07:00', 'old')
            assert not storage.claim_slot('2026-10-26T07:00', 'old')
            db.query("UPDATE nba_scan_slots SET heartbeat_at=NOW()-INTERVAL '3 minutes' WHERE status='running'")
            assert tracking.deployment_blockers('new') == 0  # Dead batches don't block cold starts.
            with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN':'offline-test-token','ODDSPAPI_API_KEY':'offline-test-key'}):
                import engine
                with patch.object(engine, 'API_KEY', 'offline-test-key'):
                    app = importlib.import_module('main')
            with patch.object(app.threading, 'Thread'):
                app.init_storage()
            with patch.object(engine, 'get_json', side_effect=AssertionError('No paid calls in DB tests')):
                from fastapi.testclient import TestClient
                client = TestClient(app.app)
                try:
                    response = client.get('/api/saved/status?date=2026-10-27')
                    assert response.status_code == 200, response.text
                    assert response.json()['state'] == 'interrupted'
                    assert response.json()['latest_attempt']['api_requests']['logged'] == 1
                    assert client.get('/api/health').json()['scan_tracking_ready'] is True
                finally:
                    client.close()
                    tracking.release_deploy_guard(app.RUNTIME_ID)
            print('PostgreSQL integration OK: migrations, durable requests, failures, restarts, duplicate guards, two-date deployment drain and HTTP startup/status')
    finally:
        db.close()


if __name__ == '__main__':
    main()
