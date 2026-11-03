import importlib
import os
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from session_window import scan_schedules, next_publication_session

ROME = ZoneInfo('Europe/Rome')


def game(at, home='Home', away='Away', **extra):
    return {'start_at': at, 'upcoming': True, 'home': home, 'away': away, **extra}


class SessionDiscoveryTests(unittest.TestCase):
    def test_day_off_reaches_november_five_without_scanning_empty_days(self):
        read = Mock(side_effect=lambda day: {'games': [game('2026-11-05T01:00:00+01:00')] if day == '2026-11-05' else []})
        scans = scan_schedules(date(2026, 11, 3), read)
        self.assertEqual([day for day, _ in scans], ['2026-11-05'])
        self.assertEqual([call.args[0] for call in read.call_args_list], ['2026-11-03','2026-11-04','2026-11-05'])

    def test_future_evening_scans_both_halves_of_session_at_most(self):
        read = Mock(side_effect=lambda day: {'games': [game(day+'T20:00:00+01:00')] if day >= '2026-11-05' else []})
        self.assertEqual([day for day, _ in scan_schedules(date(2026, 11, 3), read)], ['2026-11-05','2026-11-06'])
        self.assertEqual(read.call_count, 4)

    def test_normal_today_and_tomorrow_window_is_preserved(self):
        read = Mock(return_value={'games': [game('2026-11-04T01:00:00+01:00')]})
        self.assertEqual([day for day, _ in scan_schedules(date(2026, 11, 3), read)], ['2026-11-03','2026-11-04'])
        self.assertEqual(read.call_count, 2)

    def test_long_gap_is_bounded_and_does_not_invent_paid_dates(self):
        read = Mock(return_value={'games': []})
        scans = scan_schedules(date(2026, 11, 3), read)
        self.assertEqual([day for day, _ in scans], ['2026-11-03','2026-11-04'])
        self.assertEqual(read.call_count, 7)

    def test_future_calendar_failure_does_not_skip_to_another_paid_date(self):
        read = Mock(side_effect=[{'games': []},{'games': []},TimeoutError('offline')])
        with self.assertRaisesRegex(RuntimeError, 'no slot claimed'):
            scan_schedules(date(2026, 11, 3), read)
        self.assertEqual(read.call_count, 3)

    def test_future_session_keeps_fourth_november_publication_date(self):
        now = datetime(2026, 11, 3, 10, tzinfo=ROME)
        def load(day):
            return {'games': [game('2026-11-05T01:00:00+01:00')] if day == '2026-11-04' else []}
        day, _ = next_publication_session(now.date(), now, load)
        self.assertEqual(day, '2026-11-04')

    def test_started_and_naive_fixtures_do_not_keep_an_old_session(self):
        now = datetime(2026, 11, 3, 10, tzinfo=ROME)
        def load(day):
            return {'games': [game('2026-11-03T09:00:00+01:00'),game('2026-11-03T20:00:00')] if day == '2026-11-03' else [game('2026-11-05T01:00:00+01:00')]}
        self.assertEqual(next_publication_session(now.date(), now, load)[0], '2026-11-04')


class FuturePublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {'NBA_STATS_ACCESS_TOKEN':'offline-test-token','ODDSPAPI_API_KEY':'offline-test-key'}):
            cls.main = importlib.import_module('main')
        cls.picks = importlib.import_module('nba_session_picks')

    def test_early_quotes_are_preliminary_and_not_published_on_wrong_day(self):
        main = self.main
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026,11,3,19,tzinfo=tz)
        def manifest(day):
            start = datetime.fromisoformat(day+'T18:00:00+01:00')
            return {'games':[game('2026-11-05T01:00:00+01:00')] if day=='2026-11-04' else [],
                    'start_at':start.isoformat(),'end_at':(start+timedelta(hours=18)).isoformat()}
        row={'Giocatore':'Early Player','Partita':'Home - Away','Mercato':'PTS','Linea':9.5,'Scelta':'Over','Quota':1.8,'Prob. stimata %':75}
        with patch.object(main, 'datetime', Clock), patch.object(main, 'nba_publication_session', side_effect=manifest), \
                patch.object(self.picks, 'read', return_value=None), patch.object(self.picks, 'publish') as publish, \
                patch.object(main.storage, 'recent_fixture_coverage', return_value=[row]), \
                patch('recommendations.select_single', return_value=row), patch('recommendations.select_daily', return_value={'lines':[]}):
            payload = main.session_picks(compact=True)
        publish.assert_not_called()
        self.assertEqual(payload['publication_date'],'2026-11-04')
        self.assertEqual(payload['publication_cutoff_at'],'2026-11-04T18:00:00+01:00')
        self.assertEqual(payload['preliminary_single'],row)
        self.assertIsNone(payload['official_single'])
        self.assertTrue(payload['official_top5_pending'])
        self.assertEqual(payload['quote_count'],1)

    def test_due_session_publishes_at_its_own_cutoff_and_keeps_frozen_lines(self):
        main=self.main
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return cls(2026,11,4,18,tzinfo=tz)
        games=[game('2026-11-05T01:00:00+01:00')]
        manifest={'games':games,'start_at':'2026-11-04T18:00:00+01:00','end_at':'2026-11-05T12:00:00+01:00'}
        official={'lines':[{'Giocatore':'Frozen Player'}],'single':None}
        with patch.object(main,'datetime',Clock), patch.object(main,'nba_publication_session',return_value=manifest), \
                patch.object(self.picks,'read',return_value=None), patch.object(self.picks,'publish',return_value=official) as publish, \
                patch.object(main.storage,'recent_fixture_coverage',return_value=[]):
            result=main.session_picks(compact=True)
        publish.assert_called_once_with('2026-11-04',games,now=Clock(2026,11,4,18,tzinfo=ROME))
        self.assertEqual(result['recommendations']['lines'],official['lines'])
        self.assertFalse(result['official_top5_pending'])

    def test_calendar_cache_reuses_valid_responses_but_not_failures(self):
        main=self.main;main._schedule_scoreboards.clear()
        self.addCleanup(main._schedule_scoreboards.clear)
        response=Mock();response.json.return_value={'events':[]}
        with patch.object(main.requests,'get',return_value=response) as get:
            main._schedule_scoreboard('20261105');main._schedule_scoreboard('20261105')
            self.assertEqual(get.call_count,1)
        response.json.return_value={}
        with patch.object(main.requests,'get',return_value=response) as get:
            for _ in range(2):
                with self.assertRaises(ValueError):main._schedule_scoreboard('20261106')
            self.assertEqual(get.call_count,2)

class EmptyFixtureCacheTests(unittest.TestCase):
    def test_empty_calendar_is_rechecked_without_changing_normal_cache_or_timestamp(self):
        import odds_feed
        odds_feed._MEMORY.clear()
        self.addCleanup(odds_feed._MEMORY.clear)
        loader=Mock(side_effect=[[],[{'fixtureId':'future'}]])
        with patch.object(odds_feed.storage,'configured',return_value=False):
            with patch.object(odds_feed.time,'time',return_value=1000):
                first=odds_feed.cached_payload('calendar',48*3600,loader,empty_max_age_seconds=3*3600)
            with patch.object(odds_feed.time,'time',return_value=1100):
                cached=odds_feed.cached_payload('calendar',48*3600,loader,empty_max_age_seconds=3*3600)
                self.assertEqual(cached['fetched_at'],first['fetched_at'])
                loader.assert_called_once()
            with patch.object(odds_feed.time,'time',return_value=12000):
                fresh=odds_feed.cached_payload('calendar',48*3600,loader,empty_max_age_seconds=3*3600)
                self.assertEqual(fresh['data'],[{'fixtureId':'future'}])
            with patch.object(odds_feed.time,'time',return_value=30000):
                odds_feed.cached_payload('calendar',48*3600,loader,empty_max_age_seconds=3*3600)
                self.assertEqual(loader.call_count,2)
