"""Metering and deployment coordination regressions; all provider I/O is mocked."""
import asyncio
import contextlib
import datetime as dt
import importlib
import io
import os
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests
import engine
import scan_tracking as tracking
from scripts import scheduled_scan
from fastapi.testclient import TestClient

with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN': 'offline-token', 'ODDSPAPI_API_KEY': 'offline-key'}):
    main = importlib.import_module('main')


class SchedulerTimingTests(unittest.TestCase):
    def test_check_just_before_slot_waits_for_slot_instead_of_ten_minutes(self):
        now = dt.datetime(2026, 10, 25, 20, 59, 41, tzinfo=scheduled_scan.ROME)
        self.assertEqual(scheduled_scan.seconds_until_check(now), 19)
        self.assertEqual(scheduled_scan.seconds_until_check(now, maximum=35), 19)

    def test_each_italian_slot_is_a_wakeup_target_in_summer_and_winter(self):
        for month in (7, 10):
            for hour, minute in scheduled_scan.SLOTS:
                target = dt.datetime(2026, month, 25, hour, minute, tzinfo=scheduled_scan.ROME)
                now = target - dt.timedelta(seconds=10)
                self.assertEqual(scheduled_scan.seconds_until_check(now), 10)
                self.assertEqual(scheduled_scan.seconds_until_check(now.astimezone(dt.timezone.utc)), 10)

    def test_after_slot_and_overnight_keep_ten_minute_recovery_interval(self):
        for hour in (0, 7, 12, 17, 21, 23):
            now = dt.datetime(2026, 10, 25, hour, 0, tzinfo=scheduled_scan.ROME)
            self.assertEqual(scheduled_scan.seconds_until_check(now), 600)

    def test_render_loop_uses_slot_aware_wait_and_stops_without_extra_run(self):
        with patch.object(main, 'shutdown_event') as stop, patch.object(scheduled_scan, 'run') as run, patch.object(scheduled_scan, 'seconds_until_check', side_effect=[19, 600]) as delay:
            stop.wait.side_effect = [False, True]
            stop.is_set.side_effect = [False, True]
            main._render_scheduler_loop()
        run.assert_called_once_with(source='render')
        self.assertEqual(stop.wait.call_args_list, [unittest.mock.call(19), unittest.mock.call(600)])
        self.assertEqual(delay.call_count, 2)


class SavedDateSelectionTests(unittest.TestCase):
    def test_prefers_first_upcoming_day_and_keeps_completed_archive_accessible(self):
        def schedule(day):
            return {'games': [{'upcoming': day != '2026-10-26'}]}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'available_dates', return_value=[{'date':'2026-10-26'}]), patch.object(main, 'schedule', side_effect=schedule), patch.object(main, 'datetime') as clock:
            clock.now.return_value = dt.datetime(2026,10,26,8,tzinfo=scheduled_scan.ROME)
            result = main.saved_dates()
        self.assertEqual(result['default_date'], '2026-10-27')
        self.assertIn({'date':'2026-10-26'}, result['dates'])
        self.assertEqual(result['odds_api_calls'], 0)

    def test_calendar_outage_keeps_saved_dates_without_inventing_upcoming_day(self):
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'available_dates', return_value=[{'date':'2026-10-26'}]), patch.object(main, 'schedule', side_effect=main.HTTPException(502, 'offline')), patch.object(main, 'datetime') as clock:
            clock.now.return_value = dt.datetime(2026,10,26,8,tzinfo=scheduled_scan.ROME)
            result = main.saved_dates()
        self.assertIsNone(result['default_date'])
        self.assertEqual(result['dates'], [{'date':'2026-10-26'}])

    def test_saved_time_exposes_original_diagnostics_without_paid_requests(self):
        snapshot = {'saved_at':'2026-10-26T06:34:40+00:00',
                    'fixture_reports':[{'stato':'vuota','diagnostica':{'mercati_senza_catalogo':0, 'mercati_player_props':0}}]}
        with patch.object(main.storage, 'configured', return_value=True), patch.object(main.storage, 'latest', return_value=snapshot), patch.object(engine, 'get_json') as paid:
            result = main.saved_time('2026-10-27')
        self.assertEqual(result['fixture_reports'][0]['diagnostica']['mercati_senza_catalogo'],0)
        paid.assert_not_called()


class MeteredRequestTests(unittest.TestCase):
    def setUp(self):
        engine.reset_odds_api_request_count()
        engine.set_odds_request_job('offline-job')
        self.addCleanup(engine.set_odds_request_job, None)
        self.context = contextlib.ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(patch.object(engine, 'API_KEY', 'never-a-real-key'))
        self.context.enter_context(patch.object(engine, '_ODDS_API_NEXT_AT', 0))
        self.context.enter_context(patch.object(engine.time, 'sleep'))
        self.start = self.context.enter_context(patch.object(tracking, 'start_request', return_value='request-id'))
        self.finish = self.context.enter_context(patch.object(tracking, 'finish_request'))
        self.http = self.context.enter_context(patch.object(engine.requests, 'get'))
        self.http.return_value = Mock(status_code=200, ok=True, headers={}, json=Mock(return_value={'ok':True}))

    def test_record_commits_before_http_and_contains_no_credentials(self):
        order = []
        self.start.side_effect = lambda *args: (order.append('record') or 'request-id')
        self.http.side_effect = lambda *args, **kwargs: (order.append('http') or Mock(status_code=200,ok=True,json=lambda:{'ok':True}))
        self.finish.side_effect = lambda *args: order.append('response')
        self.assertEqual(engine.get_json('odds', fixtureId='test'), {'ok':True})
        self.assertEqual(order, ['record','http','response'])
        self.start.assert_called_once_with('offline-job','odds')
        self.assertEqual(engine.odds_api_request_count(), 1)

    def test_database_outage_prevents_paid_request(self):
        self.start.side_effect = RuntimeError('isolated simulated database outage')
        with self.assertRaisesRegex(RuntimeError, 'NON inviata'):
            engine.get_json('odds')
        self.http.assert_not_called()
        self.finish.assert_not_called()
        self.assertEqual(engine.odds_api_request_count(), 0)

    def test_network_error_leaves_durable_uncertain_attempt(self):
        self.http.side_effect = requests.Timeout()
        with self.assertRaisesRegex(RuntimeError, 'connessione'):
            engine.get_json('fixtures')
        self.finish.assert_called_once_with('request-id', None)
        self.assertEqual(engine.odds_api_request_count(), 1)

    def test_bounded_429_retry_records_both_requests(self):
        self.start.side_effect = ['first','second']
        self.http.side_effect = [Mock(status_code=429, ok=False, headers={'Retry-After':'2'}), Mock(status_code=200,ok=True,json=lambda:[]) ]
        self.assertEqual(engine.get_json('markets'), [])
        self.assertEqual(self.start.call_count, 2)
        self.assertEqual(self.http.call_count, 2)
        self.assertEqual([c.args for c in self.finish.call_args_list], [('first',429),('second',200)])
        self.assertEqual(engine.odds_api_request_count(), 2)

    def test_response_persistence_failure_never_repeats_http(self):
        self.finish.side_effect = RuntimeError('simulated database outage after response')
        with self.assertLogs(engine.logger, 'ERROR'):
            self.assertEqual(engine.get_json('odds'), {'ok':True})
        self.http.assert_called_once()

    def test_invalid_json_still_records_received_http_response(self):
        self.http.return_value.json.side_effect = ValueError('invalid JSON')
        with self.assertRaisesRegex(RuntimeError, 'JSON'):
            engine.get_json('odds')
        self.finish.assert_called_once_with('request-id',200)
        self.http.assert_called_once()


class DeployCoordinationTests(unittest.TestCase):
    def test_new_deploy_waits_for_existing_work(self):
        with patch.object(tracking, 'begin_deploy_guard') as begin, patch.object(tracking, 'deployment_blockers', side_effect=[2,1,0]), patch.object(tracking, 'release_deploy_guard') as release, patch.object(tracking.time, 'sleep') as sleep:
            tracking.wait_for_deployment('new', timeout=10)
        begin.assert_called_once_with('new')
        self.assertEqual(sleep.call_count,2)
        release.assert_not_called()  # Held until public routing is confirmed.

    def test_timeout_aborts_new_deploy_and_releases_guard(self):
        with patch.object(tracking, 'begin_deploy_guard'), patch.object(tracking, 'deployment_blockers', return_value=1), patch.object(tracking, 'release_deploy_guard') as release, patch.object(tracking.time, 'monotonic', side_effect=[0,11]):
            with self.assertRaises(tracking.ScanPaused):
                tracking.wait_for_deployment('new', timeout=10)
        release.assert_called_once_with('new')

    def test_slot_heartbeat_is_free_and_stops(self):
        stop = Mock()
        stop.wait.side_effect = [False,True]
        with patch.object(scheduled_scan,'call') as call:
            scheduled_scan.slot_heartbeat('2026-10-25T21:00',stop)
        self.assertEqual(call.call_count,1)
        self.assertIn('/api/storage/slot/heartbeat?',call.call_args.args[0])
        self.assertEqual(call.call_args.kwargs['method'],'POST')

    def test_release_waits_until_public_endpoint_serves_new_instance(self):
        old = Mock(ok=True,json=lambda:{'runtime_instance':'old'})
        new = Mock(ok=True,json=lambda:{'runtime_instance':main.RUNTIME_ID})
        with patch.object(main,'shutdown_event') as stop, patch.object(main.requests,'get',side_effect=[old,new]), patch.object(tracking,'release_deploy_guard') as release:
            stop.wait.return_value=False
            main._release_guard_when_public()
        release.assert_called_once_with(main.RUNTIME_ID)

    def test_scan_heartbeat_persists_progress(self):
        stop = threading.Event()
        main.jobs['heartbeat-test']={'progress':45,'stage':'Test progress','state':'running'}
        try:
            with patch.object(tracking,'heartbeat',side_effect=lambda *args:stop.set()) as heartbeat:
                main._scan_heartbeat('heartbeat-test',stop)
            heartbeat.assert_called_once_with('heartbeat-test',45,'Test progress')
        finally:
            main.jobs.pop('heartbeat-test',None)


class ScanEndpointTests(unittest.TestCase):
    def setUp(self):
        main.jobs.clear()
        main.shutdown_event.clear()
        self.addCleanup(main.shutdown_event.clear)
        self.client=TestClient(main.app)
        self.addCleanup(self.client.close)
        self.auth={'Authorization':'Bearer '+main.TOKEN}

    def test_failed_attempt_registration_never_starts_thread(self):
        with patch.object(tracking,'begin_attempt',side_effect=RuntimeError('DB unavailable')), patch.object(main.threading,'Thread') as thread, self.assertLogs(main.logger,'ERROR'):
            response=self.client.post('/api/scan?date=2026-10-26',headers=self.auth)
        self.assertEqual(response.status_code,503)
        thread.assert_not_called()
        self.assertFalse(main.jobs)

    def test_deploy_pause_never_starts_thread(self):
        with patch.object(tracking,'begin_attempt',side_effect=tracking.ScanPaused('paused')),patch.object(main.threading,'Thread') as thread:
            response=self.client.post('/api/scan?date=2026-10-26',headers=self.auth)
        self.assertEqual(response.status_code,503)
        thread.assert_not_called()

    def test_attempt_is_registered_before_thread_start(self):
        order=[]
        with patch.object(tracking,'begin_attempt',side_effect=lambda job,*args: (order.append('persist') or {'job_id':job,'date':'2026-10-26','reused':False})),patch.object(main.threading,'Thread') as thread:
            thread.return_value.start.side_effect=lambda:order.append('start')
            response=self.client.post('/api/scan?date=2026-10-26',headers=self.auth)
        self.assertEqual(response.status_code,200)
        self.assertEqual(order,['persist','start'])

    def test_persistent_active_job_is_reused_after_restart(self):
        with patch.object(tracking,'begin_attempt',return_value={'job_id':'existing','date':'2026-10-26','reused':True}),patch.object(main.threading,'Thread') as thread:
            response=self.client.post('/api/scan?date=2026-10-26',headers=self.auth)
        self.assertEqual(response.json(),{'job_id':'existing','reused':True})
        thread.assert_not_called()

    def test_shutdown_rejects_new_paid_work(self):
        main.shutdown_event.set()
        with patch.object(tracking,'begin_attempt') as begin:
            response=self.client.post('/api/scan?date=2026-10-26',headers=self.auth)
        self.assertEqual(response.status_code,503)
        begin.assert_not_called()

    def test_status_is_read_only_and_preserves_old_saved_time(self):
        payload={'date':'2026-10-26','state':'error','latest_attempt':{'state':'error'},'last_saved':{'saved_at':'2026-10-25T16:13:54Z'},'odds_api_calls':0}
        with patch.object(tracking,'day_status',return_value=payload),patch.object(engine,'get_json') as paid:
            response=self.client.get('/api/saved/status?date=2026-10-26')
        self.assertEqual(response.json(),payload)
        paid.assert_not_called()

    def test_graceful_shutdown_joins_existing_threads(self):
        thread=Mock()
        thread.is_alive.return_value=True
        with patch.dict(main.scan_threads,{'test':thread},clear=True):
            asyncio.run(main.drain_scans())
        thread.join.assert_called_once()
        self.assertTrue(main.shutdown_event.is_set())

class WorkerStartupFailureTests(unittest.TestCase):
    def test_heartbeat_thread_failure_is_terminal_before_any_paid_work(self):
        main.jobs['startup-failure']={'date':'2026-10-26','state':'queued'}
        try:
            with patch.object(main.threading,'Thread') as thread, patch.object(tracking,'finish_attempt') as finish, patch.object(engine,'get_fixtures') as paid, self.assertLogs(main.logger,'ERROR'), contextlib.redirect_stdout(io.StringIO()):
                thread.return_value.start.side_effect=RuntimeError('synthetic thread startup failure')
                main.do_scan('startup-failure','2026-10-26')
            self.assertEqual(main.jobs['startup-failure']['state'],'error')
            self.assertEqual(main.jobs['startup-failure']['odds_api_http_requests_scan'],0)
            self.assertEqual(finish.call_args.args[1],'error')
            paid.assert_not_called()
        finally:
            main.jobs.pop('startup-failure',None)


if __name__=='__main__':
    unittest.main()
