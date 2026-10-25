"""Official ESPN completion replaces the 24-hour historical exclusion."""
import datetime as dt
import unittest
from unittest.mock import patch

import pandas as pd
import requests
import engine


def event(event_id, completed=None, nested=True):
    payload = {'id': event_id}
    if completed is not None:
        status = {'type': {'completed': completed}}
        if nested:
            payload['competitions'] = [{'status': status}]
        else:
            payload['status'] = status
    return payload


class CompletedHistoryTests(unittest.TestCase):
    def frame(self):
        now = pd.Timestamp.now(tz='UTC')
        return pd.DataFrame([
            {'GAME_ID': 'recent-final', 'GAME_DATE': now - pd.Timedelta(hours=5), 'SEASON_TYPE': 2, 'PTS': 25, 'REB': 5, 'AST': 5},
            {'GAME_ID': 'live', 'GAME_DATE': now - pd.Timedelta(hours=1), 'SEASON_TYPE': 2, 'PTS': 10, 'REB': 3, 'AST': 2},
            {'GAME_ID': 'older-final', 'GAME_DATE': now - pd.Timedelta(days=3), 'SEASON_TYPE': 2, 'PTS': 20, 'REB': 4, 'AST': 4},
        ])

    def test_recent_final_back_to_back_game_is_retained_and_live_is_excluded(self):
        games = self.frame()
        payload = {'events': [event('recent-final', True), event('live', False), event('older-final', True)]}
        with patch.object(engine, 'espn_season_schedule_payloads', return_value=((2, payload), (3, {'events': []}))), patch.object(engine, 'espn_event_summary') as summary, patch.object(engine, 'get_json') as paid:
            result = engine.completed_game_log(games, '1', '2026-27')
        self.assertEqual(result.GAME_ID.tolist(), ['recent-final', 'older-final'])
        self.assertEqual(result.loc[0, 'PTS'], 25)
        summary.assert_not_called()
        paid.assert_not_called()
        self.assertEqual(len(games), 3)  # Never mutate cached source data.

    def test_old_game_without_verified_final_status_is_also_excluded(self):
        games = self.frame().iloc[[2]]
        with patch.object(engine, 'espn_season_schedule_payloads', return_value=((2, {'events': []}),)), patch.object(engine, 'espn_event_summary', return_value={'header': event('older-final')}):
            self.assertTrue(engine.completed_game_log(games, '1', '2026-27').empty)

    def test_traded_player_game_can_be_verified_by_event_id(self):
        games = self.frame().iloc[[0]]
        with patch.object(engine, 'espn_season_schedule_payloads', return_value=((2, {'events': []}),)), patch.object(engine, 'espn_event_summary', return_value={'header': event('recent-final', True)}) as summary:
            result = engine.completed_game_log(games, 'new-team', '2026-27')
        self.assertEqual(result.GAME_ID.tolist(), ['recent-final'])
        summary.assert_called_once_with('recent-final')

    def test_provider_outage_does_not_admit_unverified_stats(self):
        with patch.object(engine, 'espn_season_schedule_payloads', side_effect=requests.Timeout()), patch.object(engine, 'espn_event_summary', side_effect=requests.Timeout()):
            result = engine.completed_game_log(self.frame(), '1', '2026-27')
        self.assertTrue(result.empty)

    def test_conflicting_schedule_status_cannot_admit_live_stats(self):
        first = {'events': [event('recent-final', True)]}
        second = {'events': [event('recent-final', False)]}
        with patch.object(engine, 'espn_season_schedule_payloads', return_value=((2, first), (3, second))), patch.object(engine, 'espn_event_summary') as summary:
            result = engine.completed_game_log(self.frame().iloc[[0]], '1', '2026-27')
        self.assertTrue(result.empty)
        summary.assert_not_called()

    def test_only_explicit_boolean_completion_is_accepted(self):
        for value in (1, 'true', 'false'):
            self.assertIsNone(engine.espn_event_completed(event('game', value)))
        self.assertTrue(engine.espn_event_completed(event('game', True)))
        self.assertTrue(engine.espn_event_completed(event('game', True, nested=False)))
        self.assertFalse(engine.espn_event_completed(event('game', False)))
        conflicting = event('game', True)
        conflicting['status'] = {'type': {'completed': False}}
        self.assertFalse(engine.espn_event_completed(conflicting))
        self.assertIsNone(engine.espn_event_completed({'status': {'type': {'state': 'post'}}}))

    def test_malformed_provider_payloads_fail_closed(self):
        self.assertIsNone(engine.espn_event_completed({'competitions': 123}))
        with patch.object(engine, 'espn_season_schedule_payloads', return_value=((2, []),)), patch.object(engine, 'espn_event_summary', return_value=[]):
            result = engine.completed_game_log(self.frame(), '1', '2026-27')
        self.assertTrue(result.empty)

    def test_schedule_and_summary_payloads_are_shared_by_completion_and_classification(self):
        engine.espn_season_schedule_payloads.cache_clear()
        engine.espn_event_summary.cache_clear()
        self.addCleanup(engine.espn_season_schedule_payloads.cache_clear)
        self.addCleanup(engine.espn_event_summary.cache_clear)
        with patch.object(engine, 'espn_json', return_value={'events': []}) as free:
            engine.espn_season_schedule_payloads('team-cache-test', 2027)
            engine.espn_season_schedule_payloads('team-cache-test', 2027)
        self.assertEqual(free.call_count, 2)  # Regular and playoff schedules, not per athlete.
        with patch.object(engine, 'espn_json', return_value={'header': event('shared-game', True)}) as free:
            engine.espn_event_summary('shared-game')
            engine.espn_event_summary('shared-game')
        self.assertEqual(free.call_count, 1)

    def test_classifier_returns_only_completed_games(self):
        games = self.frame()
        with patch.object(engine, 'espn_json', return_value={}), patch.object(engine, 'espn_log_to_frame', return_value=games), patch.object(engine, 'espn_schedule_competition_ids', return_value={}), patch.object(engine, 'completed_game_log', return_value=games.iloc[[0, 2]]) as final_filter:
            result = engine.espn_classified_game_log.__wrapped__('test', '2026-27', '1')
        final_filter.assert_called_once()
        self.assertEqual(result.GAME_ID.tolist(), ['recent-final', 'older-final'])

    def test_finder_keeps_recent_final_but_excludes_future_records(self):
        now = pd.Timestamp.now(tz='UTC')
        dates = [now - pd.Timedelta(hours=5)] + [now - pd.Timedelta(days=n) for n in range(2, 17)]
        games = pd.DataFrame([{'GAME_ID': str(i), 'GAME_DATE': date, 'SEASON_TYPE': 2,
                               'PTS': 30 if i == 0 else 10, 'REB': 5, 'AST': 5, 'MIN': 30}
                              for i, date in enumerate(dates)])
        fixture = {'fixtureId': 'test', 'participant1Name': 'A', 'participant2Name': 'B',
                   'startTime': (now + pd.Timedelta(hours=6)).isoformat()}
        player = {'id': '1', 'full_name': 'Test Player', 'team_id': '1', 'team_name': 'A'}
        row = {'Giocatore': 'Test Player', 'Linea': 19.5, 'Over': 1.8, 'Tipo': 'Soglia +'}
        supplied = pd.concat([games, games.iloc[[0]].assign(GAME_ID='future', GAME_DATE=now + pd.Timedelta(hours=1))], ignore_index=True)
        def selected(_id, season, *_args):
            return supplied.copy() if season == '2026-27' else games.iloc[:0].copy()
        def parsed(_odds, _catalog, label):
            return ([row], {}) if label == 'Punti (PTS)' else ([], {})
        with patch.object(engine, 'finder_player_index', return_value={'testplayer': player}), patch.object(engine, '_cache_read', return_value=({}, 'disk', now.timestamp())), patch.object(engine, '_odds_diagnostics', return_value={}), patch.object(engine, 'odds_source_audit', return_value=[]), patch.object(engine, 'parse_odds', side_effect=parsed), patch.object(engine, 'selected_game_log', side_effect=selected), patch.object(engine, 'get_json') as paid:
            results, _, _, _, _, _, logs, _ = engine.finder_scan([fixture], {}, '2026-27', 15, 1.01, 20, -100)
        self.assertEqual(len(logs['Test Player']), 16)
        self.assertEqual(results[0]['Partite'], 16)
        self.assertEqual(results[0]['Ultime 5'], '1/5')
        expected = engine.finder_estimate_probability(games, 'PTS', 19.5, 'Over')['estimate']
        self.assertEqual(results[0]['Prob. stimata %'], round(expected * 100, 1))
        paid.assert_not_called()


if __name__ == '__main__':
    unittest.main()
