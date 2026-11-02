import copy
import unittest
from settlement_audit import diagnose
from test_settle_espn import event, summary


class SettlementAuditTests(unittest.TestCase):
    def setUp(self):
        self.row = {'Partita': 'Boston Celtics - New York Knicks',
                    'Squadra': 'Boston Celtics', 'Giocatore': 'Jayson Tatum',
                    'ESPN ID': '111', 'Mercato': 'PTS', 'Linea': 24.5,
                    'Scelta': 'Over', 'Prob. stimata %': 70}
        self.snapshot = {'scan_finished_at': '2026-10-24T12:00:00Z', 'results': [self.row]}
        self.evidence = {('events', '2026-10-24'): [event()], ('summary', '100'): summary()}

    def run_audit(self):
        return diagnose(self.snapshot, '2026-10-24', self.evidence)

    def test_matching_is_read_only_and_duplicate_lines_are_explicit(self):
        self.snapshot['results'] *= 2
        before = copy.deepcopy(self.snapshot)
        report, rows = self.run_audit()
        self.assertEqual(report['reasons'], {'matched': 2})
        self.assertEqual(report['duplicate_matched_lines'], 1)
        self.assertEqual([r['actual'] for r in rows], [27, 27])
        self.assertEqual(self.snapshot, before)

    def test_push_is_not_a_loss_or_binary_match(self):
        self.row['Linea'] = 27
        report, rows = self.run_audit()
        self.assertEqual(report['reasons'], {'push': 1})
        self.assertEqual(rows, [])

    def test_wrong_id_never_uses_matching_name(self):
        self.row['ESPN ID'] = '999'
        report, rows = self.run_audit()
        self.assertEqual(report['reasons'], {'athlete_not_in_boxscore': 1})
        self.assertFalse(rows)

    def test_team_mismatch_is_diagnostic_only(self):
        self.row['Squadra'] = 'New York Knicks'
        report, rows = self.run_audit()
        self.assertEqual(report['reasons'], {'team_mismatch_verified_id': 1})
        self.assertFalse(rows)

    def test_confirmed_dnp_requires_explicit_boxscore_flag(self):
        athlete = self.evidence[('summary', '100')]['boxscore']['players'][0]['statistics'][0]['athletes'][0]
        athlete['didNotPlay'] = True
        athlete['stats'] = []
        report, rows = self.run_audit()
        self.assertEqual(report['reasons'], {'confirmed_dnp': 1})
        self.assertFalse(rows)

    def test_dates_and_pregame_guards(self):
        for saved, reason in [('2026-10-24T19:00:00Z', 'post_tipoff_snapshot'),
                              ('2026-10-24T12:00:00', 'unverifiable_timestamp')]:
            self.snapshot['scan_finished_at'] = saved
            self.assertEqual(self.run_audit()[0]['reasons'], {reason: 1})
        self.evidence[('events', '2026-10-24')] = []
        self.assertEqual(self.run_audit()[0]['reasons'], {'missing_fixture': 1})

    def test_not_final_does_not_fetch_or_impute_outcome(self):
        self.evidence[('events', '2026-10-24')][0]['status']['type']['completed'] = False
        self.assertEqual(self.run_audit()[0]['reasons'], {'game_not_final': 1})
