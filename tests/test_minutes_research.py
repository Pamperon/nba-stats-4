import copy
from datetime import datetime, timedelta, timezone
import unittest
import minutes_research as research


def logs():
    return [{'GAME_ID':str(i), 'GAME_DATE':(datetime(2026,10,30,tzinfo=timezone.utc)-timedelta(days=i)).date().isoformat(),
             'SEASON_TYPE':2, 'MIN':30, 'PTS':20, 'ANNO_STAGIONE':'2026-27'} for i in range(20)]


def row(**extra):
    return {'Giocatore':'A','ESPN ID':'123','Squadra':'Home','Partita':'Home - Away',
            'Mercato':'PTS','Scelta':'Over','Linea':19.5,'Quota':1.80,'Prob. stimata %':80,**extra}


class MinutesResearchTests(unittest.TestCase):
    cutoff='2026-11-01T10:00:00Z'

    def test_same_minutes_matches_smoothed_recent_hit_rate_and_does_not_mutate(self):
        rows=[row()];history={'A':logs()};before=copy.deepcopy((rows,history))
        saved=research.capture(rows,history,self.cutoff)
        self.assertEqual((rows,history),before)
        self.assertAlmostEqual(saved['panel'][0]['candidate_probability'],20.5/21)
        self.assertEqual(saved['panel'][0]['baseline_probability'],.8)
        self.assertIs(saved['promotion_allowed'],False)
        self.assertIsNone(saved['panel'][0]['features']['starter'])

    def test_only_pregame_regular_season_history_is_used(self):
        history=logs()+[dict(logs()[0],GAME_ID='future',GAME_DATE='2026-11-02',PTS=999)]
        history += [dict(logs()[0],GAME_ID='postseason',SEASON_TYPE=3,PTS=999)]
        result=research.profile(history,self.cutoff)
        self.assertEqual(result['history_n'],20)
        self.assertEqual(result['excluded_history'],{'not_strictly_pregame':1,'not_regular_season':1})

    def test_date_only_same_day_and_unknown_timezone_are_not_assumed_pregame(self):
        history=[dict(logs()[0],GAME_ID='same',GAME_DATE='2026-11-01'),
                 dict(logs()[0],GAME_ID='naive',GAME_DATE='2026-10-30T12:00:00')]
        samples,excluded=research.history(history,self.cutoff)
        self.assertEqual(samples,[])
        self.assertEqual(sum(excluded.values()),2)
        with self.assertRaises(ValueError):research.capture([],{},'2026-11-01T10:00:00')

    def test_duplicate_identity_fails_closed(self):
        saved=research.capture([row()],{'A':logs()+[logs()[0]]},self.cutoff)
        self.assertEqual(saved['panel'],[])
        self.assertEqual(saved['excluded'],{'ambiguous_history':1})

    def test_panel_is_selected_by_odds_before_outcomes_and_does_not_duplicate_players(self):
        rows=[row(Linea=9.5,Quota=1.5,actual=100),row(Linea=19.5,actual=0)]
        result=research.capture(rows,{'A':logs()},self.cutoff)
        self.assertEqual(len(result['panel']),1)
        self.assertEqual(result['panel'][0]['Linea'],19.5)
        self.assertNotIn('actual',result['panel'][0])

    def test_missing_history_and_invalid_minutes_do_not_impute_zero(self):
        self.assertEqual(research.capture([row()],{},self.cutoff)['panel'],[])
        for value in (0,-1,float('nan'),True,'DNP','2:61'):
            self.assertIsNone(research.minutes(value))
        self.assertEqual(research.minutes('12:30'),12.5)

    def test_injury_information_after_capture_is_not_used(self):
        source=row(**{'Disponibilità ESPN':'out','Disponibilità verificata alle':'2026-11-02T12:00:00Z'})
        result=research.capture([source],{'A':logs()},self.cutoff)
        self.assertEqual(result['panel'][0]['availability_at_capture'],'unknown')

    def test_minutes_role_change_affects_candidate_only(self):
        history=logs()
        for sample in history[:5]:sample['MIN']=15;sample['PTS']=10
        result=research.capture([row()],{'A':history},self.cutoff)['panel'][0]
        self.assertEqual(result['features']['projected_minutes'],15)
        self.assertAlmostEqual(result['candidate_probability'],.5/21)
        self.assertEqual(result['baseline_probability'],.8)
