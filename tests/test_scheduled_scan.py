"""Offline scheduler safety checks: no server, database or external API calls."""
import ast
import datetime as dt
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from scripts import scheduled_scan as scheduler

ROOT = Path(__file__).resolve().parents[1]

class SchedulerTests(unittest.TestCase):
    def test_rome_slots_across_summer_winter_and_dst_changes(self):
        for date in ('2026-01-15', '2026-07-15', '2026-03-29', '2026-10-25'):
            for hour, minute in scheduler.SLOTS:
                target = dt.datetime.fromisoformat(f'{date}T{hour:02}:{minute:02}').replace(tzinfo=scheduler.ROME)
                self.assertEqual(scheduler.due_slot(target), target)
                self.assertIsNone(scheduler.due_slot(target - dt.timedelta(seconds=1)))
                self.assertEqual(scheduler.due_slot(target + dt.timedelta(minutes=90)), target)
            self.assertIsNone(scheduler.due_slot(dt.datetime.fromisoformat(date + 'T03:00').replace(tzinfo=scheduler.ROME)))

    def test_claim_and_finish_accept_same_slots_as_scheduler(self):
        class HTTPException(Exception):
            pass
        tree = ast.parse((ROOT / 'main.py').read_text())
        for name in ('slot_claim', 'slot_finish'):
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            node.decorator_list = []
            node.args.defaults = []
            namespace = {'datetime': dt.datetime, 'HTTPException': HTTPException, 'storage': Mock(), 'logger': Mock(), 'RUNTIME_ID': 'offline-runtime'}
            exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
            function = namespace[name]
            for hour in range(24):
                for minute in (0, 30):
                    args = [f'2026-10-25T{hour:02}:{minute:02}'] + ([True] if name == 'slot_finish' else [])
                    if (hour, minute) in scheduler.SLOTS:
                        function(*args)
                    else:
                        with self.assertRaises(HTTPException):
                            function(*args)
            for invalid in ('2026-10-25T07:01', '2026-10-25T7:00', '2026-02-30T07:00'):
                with self.assertRaises(HTTPException):
                    function(invalid, *([True] if name == 'slot_finish' else []))

    def test_duplicate_slot_never_starts_scan(self):
        with patch.object(scheduler, 'TOKEN', 'offline-token'), patch.dict(scheduler.os.environ, {'NBA_STATS_DRY_RUN': '0', 'NBA_STATS_MANUAL_SCAN': '0'}), patch.object(scheduler, 'due_slot', return_value=dt.datetime(2026, 10, 25, 11, tzinfo=scheduler.ROME)), patch.object(scheduler, 'call', side_effect=[{'scheduler_revision': 'rome-five-slots-v3'}, {'games': []}, {'games': []}, {'claimed': False}]) as call, patch.object(scheduler, 'execute_scan') as execute:
            scheduler.run()
            execute.assert_not_called()
            self.assertEqual(call.call_count, 4)

    def test_old_deployment_cannot_consume_slot(self):
        with patch.object(scheduler, 'TOKEN', 'offline-token'), patch.dict(scheduler.os.environ, {'NBA_STATS_DRY_RUN': '0', 'NBA_STATS_MANUAL_SCAN': '0'}), patch.object(scheduler, 'due_slot', return_value=dt.datetime(2026, 10, 25, 11, tzinfo=scheduler.ROME)), patch.object(scheduler, 'call', return_value={'status': 'ok'}) as call, patch.object(scheduler, 'execute_scan') as execute:
            with self.assertRaisesRegex(RuntimeError, 'not deployed'):
                scheduler.run()
            call.assert_called_once_with('/api/health')
            execute.assert_not_called()

    def test_calendar_failure_never_consumes_slot_or_starts_paid_scan(self):
        slot = dt.datetime(2026, 10, 25, 11, tzinfo=scheduler.ROME)
        for failed_day in ('2026-10-25', '2026-10-26'):
            calls = []
            def fake_call(path, **kwargs):
                calls.append(path)
                if path == '/api/health':
                    return {'scheduler_revision': 'rome-five-slots-v3'}
                if path == '/api/schedule?date=' + failed_day:
                    raise TimeoutError('simulated ESPN outage')
                if path.startswith('/api/schedule?'):
                    return {'games': []}
                self.fail('Unexpected mutation: ' + path)
            with patch.object(scheduler, 'TOKEN', 'offline-token'), patch.dict(scheduler.os.environ, {'NBA_STATS_DRY_RUN': '0', 'NBA_STATS_MANUAL_SCAN': '0'}), patch.object(scheduler, 'due_slot', return_value=slot), patch.object(scheduler, 'call', side_effect=fake_call), patch.object(scheduler, 'execute_scan') as execute:
                with self.assertRaisesRegex(RuntimeError, 'no slot claimed'):
                    scheduler.run()
                execute.assert_not_called()
            self.assertFalse(any('/slot/' in path for path in calls))

    def test_calendar_recovers_on_next_heartbeat_without_paid_probe(self):
        slot = dt.datetime(2026, 10, 25, 11, tzinfo=scheduler.ROME)
        failed = [False]
        calls = []
        def fake_call(path, **kwargs):
            calls.append(path)
            if path == '/api/health':
                return {'scheduler_revision': 'rome-five-slots-v3'}
            if path.startswith('/api/schedule?'):
                if not failed[0]:
                    failed[0] = True
                    raise TimeoutError('first calendar read unavailable')
                return {'games': []}
            if '/slot/claim?' in path:
                return {'claimed': True}
            if path.startswith('/api/scan?'):
                self.fail('No games: no paid scan should start')
            return {}
        with patch.object(scheduler, 'TOKEN', 'offline-token'), patch.dict(scheduler.os.environ, {'NBA_STATS_DRY_RUN': '0', 'NBA_STATS_MANUAL_SCAN': '0'}), patch.object(scheduler, 'due_slot', return_value=slot), patch.object(scheduler, 'call', side_effect=fake_call):
            with self.assertRaises(RuntimeError):
                scheduler.run()
            scheduler.run()
        self.assertEqual(sum('/slot/claim?' in path for path in calls), 1)
        self.assertEqual(sum('success=true' in path for path in calls), 1)
        self.assertFalse(any('success=false' in path for path in calls))
        # Successful preflight calendars are reused by execution, not re-fetched.
        self.assertEqual(sum(path.startswith('/api/schedule?') for path in calls), 3)

    def test_malformed_calendar_cannot_be_mistaken_for_no_games(self):
        for payload in ({}, {'games': None}, {'games': [None]}, {'games': [{}]}, {'games': [{'upcoming': 'false'}]}, []):
            with patch.object(scheduler, 'call', return_value=payload):
                with self.assertRaises(RuntimeError):
                    scheduler.load_schedules(dt.date(2026, 10, 25))

    def test_database_claim_never_replays_failed_or_stale_slot(self):
        tree = ast.parse((ROOT / 'storage.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'claim_slot')
        connection = Mock()
        context = connection.return_value.__enter__ = Mock()
        connection.return_value.__exit__ = Mock(return_value=False)
        conn = context.return_value
        namespace = {'configured': lambda: True, 'connection': connection}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'storage.py', 'exec'), namespace)
        for row, expected in ((('slot',), True), (None, False)):
            conn.execute.return_value.fetchone.return_value = row
            self.assertEqual(namespace['claim_slot']('2026-10-25T12:00'), expected)
        sql = conn.execute.call_args.args[0]
        self.assertIn('ON CONFLICT(slot_key) DO NOTHING', sql)
        self.assertNotIn('DO UPDATE', sql)


    def test_half_hour_slot_preserves_minutes_and_recovers_only_within_two_hours(self):
        target = dt.datetime(2026, 10, 28, 14, 30, tzinfo=scheduler.ROME)
        self.assertTrue(scheduler.valid_slot("2026-10-28T14:30"))
        self.assertFalse(scheduler.valid_slot("2026-10-28T14:00"))
        self.assertFalse(scheduler.valid_slot("2026-10-28T12:00"))
        self.assertEqual(scheduler.due_slot(target + dt.timedelta(hours=2)), target)
        self.assertIsNone(scheduler.due_slot(target + dt.timedelta(hours=2, seconds=1)))
        self.assertEqual(scheduler.due_slot(target.astimezone(dt.timezone.utc)), target)
        calls = []
        def fake_call(path, **kwargs):
            calls.append(path)
            if path == "/api/health":
                return {"scheduler_revision": "rome-five-slots-v3"}
            if path.startswith("/api/schedule"):
                return {"games": []}
            if "/slot/claim?" in path:
                return {"claimed": True}
            return {}
        with patch.object(scheduler, "TOKEN", "offline"), \
             patch.dict(scheduler.os.environ, {"NBA_STATS_DRY_RUN":"0","NBA_STATS_MANUAL_SCAN":"0"}), \
             patch.object(scheduler, "due_slot", return_value=target), \
             patch.object(scheduler, "call", side_effect=fake_call):
            scheduler.run()
        self.assertTrue(any("slot=2026-10-28T14%3A30" in p for p in calls))

if __name__ == '__main__':
    unittest.main()
