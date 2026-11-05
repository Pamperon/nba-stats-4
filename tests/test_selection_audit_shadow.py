import copy,unittest
import recommendations,selection_audit_shadow as audit
from tests.test_full_selection_audit import row

class SelectionShadowTests(unittest.TestCase):
 def test_frozen_selection_and_live_rows_unchanged(self):
  rows=[row(str(i),85-i*.2,1.25) for i in range(15)]
  before=copy.deepcopy(rows);saved=audit.capture(rows)
  self.assertEqual(rows,before)
  self.assertFalse(saved['promotion_allowed'])
  self.assertEqual(saved['variants']['current'],recommendations.select_daily(rows)['lines'][:10])
 def test_minutes_variant_and_no_result_leakage(self):
  risky=row('A',90,1.3);risky['Minuti ultime 5']=25
  rows=[risky,row('B',85,1.3)]
  saved=audit.capture(rows)
  self.assertEqual([r['Giocatore'] for r in saved['variants']['minutes90']],['B'])
  for r in rows:r['_win']=0
  self.assertEqual([r['Giocatore'] for r in audit.capture(rows)['variants']['current']],['A','B'])
 def test_results_require_exact_fixture_and_explicit_play(self):
  saved=audit.capture([row('A',85,1.3)])
  self.assertEqual(audit.evaluate(saved,[{**row('A'), 'Partita':'C - D','actual':20,'played':True}])['variants']['current']['verified'],0)
  self.assertEqual(audit.evaluate(saved,[{**row('A'),'actual':20,'played':False}])['variants']['current']['verified'],0)
  self.assertEqual(audit.evaluate(saved,[{**row('A'),'actual':20,'played':True}])['variants']['current']['wins'],1)
