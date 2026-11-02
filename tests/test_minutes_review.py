import unittest
from scripts.review_minutes_research import review, paired_interval
from test_minutes_research import row, logs


class MinutesReviewTests(unittest.TestCase):
    def snapshot(self):
        return {'date':'2026-11-01','scan_finished_at':'2026-11-01T10:00:00Z',
                'results':[row()],'player_logs':{'A':logs()}}

    def test_missing_outcome_is_not_a_loss_and_reconstruction_is_explicit(self):
        result=review([self.snapshot()],[])
        self.assertEqual(result['overall']['n'],0)
        self.assertTrue(result['by_date'][0]['historically_reconstructed'])
        self.assertIs(result['promotion_allowed'],False)

    def test_duplicate_dates_and_conflicting_results_are_rejected(self):
        with self.assertRaises(ValueError):review([self.snapshot(),self.snapshot()],[])
        actual={**row(),'_audit_date':'2026-11-01','actual':20,'played':True}
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            review([self.snapshot()],[actual,{**actual,'actual':10}])

    def test_nonfinite_outcome_cannot_turn_into_loss(self):
        actual={**row(),'_audit_date':'2026-11-01','actual':float('nan'),'played':True}
        self.assertEqual(review([self.snapshot()],[actual])['overall']['n'],0)

    def test_clustered_interval_keeps_paired_rows_and_is_reproducible(self):
        rows=[{'game':str(i),'baseline_probability':.5,'candidate_probability':1.,'win':1}
              for i in range(4)]
        result=paired_interval(rows,'game',iterations=100)
        self.assertEqual(result['clusters'],4)
        self.assertEqual(result['interval'],[-.25,-.25])
        self.assertEqual(result,paired_interval(rows,'game',iterations=100))
