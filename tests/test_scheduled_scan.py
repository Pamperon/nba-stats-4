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
            for hour in scheduler.SLOTS:
                target = dt.datetime.fromisoformat(f'{date}T{hour:02}:00').replace(tzinfo=scheduler.ROME)
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
            namespace = {'datetime': dt.datetime, 'HTTPException': HTTPException, 'storage': Mock(), 'logger': Mock()}
            exec(compile(ast.Module(body=[node], type_ignores=[]), 'main.py', 'exec'), namespace)
            function = namespace[name]
            for hour in range(24):
                args = [f'2026-10-25T{hour:02}:00'] + ([True] if name == 'slot_finish' else [])
                if hour in scheduler.SLOTS:
                    function(*args)
                else:
                    with self.assertRaises(HTTPException):
                        function(*args)
            for invalid in ('2026-10-25T07:01', '2026-10-25T7:00', '2026-02-30T07:00'):
                with self.assertRaises(HTTPException):
                    function(invalid, *([True] if name == 'slot_finish' else []))

    def test_duplicate_slot_never_starts_scan(self):
        with patch.object(scheduler, 'TOKEN', 'offline-token'), patch.dict(scheduler.os.environ, {'NBA_STATS_DRY_RUN': '0', 'NBA_STATS_MANUAL_SCAN': '0'}), patch.object(scheduler, 'due_slot', return_value=dt.datetime(2026, 10, 25, 12, tzinfo=scheduler.ROME)), patch.object(scheduler, 'call', return_value={'claimed': False}) as call, patch.object(scheduler, 'execute_scan') as execute:
            scheduler.run()
            execute.assert_not_called()
            self.assertEqual(call.call_count, 1)

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

if __name__ == '__main__':
    unittest.main()
