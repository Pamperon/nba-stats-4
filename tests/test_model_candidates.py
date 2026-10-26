import copy
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pandas as pd
import engine
import model_candidates as models
import shadow_study
import recommendations
from scripts.weight_selection_review import compare


def history(previous=60, current=2):
    start = datetime(2026, 10, 25, tzinfo=timezone.utc)
    rows = []
    for i in range(current+previous):
        rows.append({'GAME_ID':str(i), 'GAME_DATE':(start-timedelta(days=i)).isoformat(),
                     'SEASON_TYPE':2, 'ANNO_STAGIONE':'2026-27' if i<current else '2025-26',
                     'PTS':10 if i%3 else 0, 'REB':4, 'AST':2, 'MIN':30})
    return rows


def row(name='Player', price=1.8, game='A - B'):
    return {'Giocatore':name, 'ESPN ID':name, 'Squadra':'A', 'Partita':game,
            'Mercato':'PTS', 'Linea':4.5, 'Scelta':'Over', 'Quota':price,
            'Prob. stimata %':80, 'Value stimato %':round((.8*price-1)*100,1),
            'Stato analisi':'Valutabile (stima empirica)', 'Partite':62,
            'Stagione %':80, 'Minuti medi':30, 'Minuti ultime 5':29,
            'Disponibilità ESPN':'not-listed'}


class CandidateTests(unittest.TestCase):
    def test_baseline_reproduces_live_formula_for_both_directions(self):
        rows=history()
        context=models.prepare(rows, '2026-27', '2026-10-26T12:00:00+00:00')
        for choice in ('Over','Under'):
            for line in (4.5,9.5,14.5):
                expected=engine.finder_estimate_probability(pd.DataFrame(rows),'PTS',line,choice)['estimate']
                actual=models.estimate(context,'PTS',line,choice)[models.BASELINE]
                self.assertAlmostEqual(actual,expected,places=12)

    def test_future_game_and_playoffs_never_change_the_estimate(self):
        rows=history(); original=copy.deepcopy(rows)
        base=models.prepare(rows,'2026-27','2026-10-26T00:00:00+00:00')
        extra=[{**rows[0],'GAME_ID':'future','GAME_DATE':'2026-10-26T00:00:00Z','PTS':99},
               {**rows[0],'GAME_ID':'playoff','SEASON_TYPE':3,'PTS':99}]
        changed=models.prepare(rows+extra,'2026-27','2026-10-26T00:00:00+00:00')
        self.assertEqual(models.estimate(base,'PTS',4.5),models.estimate(changed,'PTS',4.5))
        self.assertEqual(rows,original)
        with self.assertRaises(ValueError):
            models.prepare(rows+[rows[0]],'2026-27','2026-10-26T00:00:00Z')

    def test_current_season_prior_has_fixed_strength_twenty(self):
        rows=history(previous=40,current=2)
        for r in rows:r['PTS']=0 if r['ANNO_STAGIONE']=='2026-27' else 10
        context=models.prepare(rows,'2026-27','2026-10-26T00:00:00Z')
        result=models.estimate(context,'PTS',4.5)
        self.assertAlmostEqual(result[models.SEASON],20*((40+.5)/41)/22)
        self.assertGreater(result[models.BASELINE],result[models.SEASON])

    def test_no_season_labels_means_no_invented_current_season_estimate(self):
        rows=history()
        for r in rows:r.pop('ANNO_STAGIONE')
        context=models.prepare(rows,'2026-27','2026-10-26T00:00:00Z')
        self.assertIsNone(models.estimate(context,'PTS',4.5)[models.SEASON])

    def test_selector_baseline_matches_live_and_does_not_use_results(self):
        rows=[row('A',1.8),row('B',1.9),row('C',1.5),row('D',1.6),row('E',1.2)]
        prepared=[{**r,'_models':{m:r['Prob. stimata %']/100 for m in models.MODELS}} for r in rows]
        self.assertEqual(shadow_study.policy_select(prepared,models.BASELINE,'probability')['groups'],
                         recommendations.select(rows)['groups'])
        altered=[{**r,'actual':999} for r in prepared]
        def names(result):
            return {k:[r['Giocatore'] for r in v['legs']] for k,v in result['groups'].items()}
        self.assertEqual(names(shadow_study.policy_select(prepared,models.BASELINE,'probability')),
                         names(shadow_study.policy_select(altered,models.BASELINE,'probability')))

    def test_distinct_game_policy_does_not_fill_with_correlated_legs(self):
        rows=[row('A',1.5),row('B',1.6)]
        prepared=[{**r,'_models':{m:.8 for m in models.MODELS}} for r in rows]
        picks=shadow_study.policy_select(prepared,models.BASELINE,'distinct_games')
        self.assertFalse(picks['groups']['Doppia']['complete'])
        self.assertEqual(len(picks['groups']['Doppia']['legs']),1)

    def test_same_game_outcomes_do_not_invent_a_bookmaker_price_or_roi(self):
        rows=[row('A',1.5),row('B',1.6)]
        ticket=recommendations.select(rows)
        result=recommendations.evaluate(ticket,[{**r,'actual':10,'played':True} for r in rows])
        self.assertEqual(result['groups']['Doppia']['status'],'won')
        self.assertIsNone(result['groups']['Doppia']['combined_odds'])
        self.assertIsNone(result['groups']['Doppia']['unit_profit'])

    def test_shadow_capture_preserves_public_values_and_scores_exact_saved_lines(self):
        original=row()
        captured_input={**original,'_shadow_probabilities':{m:.8 for m in models.MODELS}}
        saved=shadow_study.capture([captured_input])
        self.assertEqual(captured_input,original)
        self.assertFalse(saved['promotion_allowed'])
        with patch.object(recommendations,'select',side_effect=AssertionError('Do not recompute after result')):
            result=shadow_study.evaluate(saved,[{**original,'actual':0,'played':True}])
        self.assertEqual(result['models'][models.BASELINE]['n'],1)
        self.assertEqual(result['tickets']['baseline']['groups']['Singola']['status'],'lost')
        unresolved=shadow_study.evaluate(saved,[])
        self.assertEqual(unresolved['models'][models.BASELINE]['n'],0)
        self.assertEqual(unresolved['tickets']['baseline']['groups']['Singola']['status'],'unresolved')

    def test_replay_refuses_unreproducible_baseline(self):
        original=row()
        archive={'date':'2026-10-26','job_id':'j','saved_at':'2026-10-25T16:00:00Z',
                 'season':'2026-27','results':[original],'player_logs':{'Player':history()}}
        report,_=compare(archive,[])
        self.assertEqual(report['baseline_mismatch_lines'],1)
        self.assertEqual(report['eligible_lines'],0)


if __name__ == '__main__':
    unittest.main()
