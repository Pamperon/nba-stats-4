import threading
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import match_prewarm

class MatchPrewarmTests(unittest.TestCase):
    def test_only_upcoming_dates_are_warmed_without_changing_data(self):
        now=datetime(2026,11,3,12,tzinfo=ZoneInfo('Europe/Rome'))
        schedule=Mock(side_effect=lambda day:{'games':[{'upcoming':True,'start_at':'2026-11-05T01:00:00+01:00'}]} if day=='2026-11-05' else {'games':[]})
        with patch.object(match_prewarm.match_history,'load_window',return_value=([],0)) as load:
            self.assertEqual(match_prewarm.warm_upcoming(schedule,threading.Event(),now),['2026-11-05'])
            self.assertEqual(load.call_count,1)
            self.assertEqual(load.call_args.args[0].isoformat(),'2026-11-05')
        self.assertEqual(schedule.call_count,3)
    def test_completed_live_past_and_unknown_games_are_not_warmed(self):
        now=datetime(2026,11,3,12,tzinfo=ZoneInfo('Europe/Rome'))
        games=[{'upcoming':False,'start_at':'2026-11-03T13:00:00+01:00'}, {'upcoming':True,'start_at':'2026-11-03T11:00:00+01:00'}, {'upcoming':True,'start_at':'invalid'}]
        with patch.object(match_prewarm.match_history,'load_window') as load:
            self.assertEqual(match_prewarm.warm_upcoming(lambda _: {'games':games},threading.Event(),now),[])
            load.assert_not_called()
    def test_shutdown_prevents_network_and_failures_do_not_stop_next_dates(self):
        stop=threading.Event();stop.set();schedule=Mock()
        self.assertEqual(match_prewarm.warm_upcoming(schedule,stop),[]);schedule.assert_not_called()
        now=datetime(2026,11,3,12,tzinfo=ZoneInfo('Europe/Rome'))
        schedule=Mock(side_effect=[RuntimeError('unavailable'),{'games':[]},{'games':[]}])
        self.assertEqual(match_prewarm.warm_upcoming(schedule,threading.Event(),now),[])
        self.assertEqual(schedule.call_count,3)
    def test_stopped_loop_does_not_delay_shutdown(self):
        stop=threading.Event();stop.set();schedule=Mock()
        match_prewarm.run(stop,schedule);schedule.assert_not_called()
    def test_status_reports_completed_dates_without_exposing_mutable_state(self):
        original=dict(match_prewarm._status)
        stop=Mock();stop.is_set.return_value=False;stop.wait.side_effect=[False,True]
        try:
            with patch.object(match_prewarm,'warm_upcoming',return_value=['2026-11-05']):
                match_prewarm.run(stop,Mock())
            result=match_prewarm.status()
            self.assertEqual(result['state'],'idle')
            self.assertEqual(result['warmed_dates'],['2026-11-05'])
            self.assertIsNotNone(result['last_completed_at'])
            self.assertEqual(result['odds_api_calls'],0)
            result['warmed_dates'].append('invalid')
            self.assertEqual(match_prewarm.status()['warmed_dates'],['2026-11-05'])
        finally:
            match_prewarm._status.clear();match_prewarm._status.update(original)
