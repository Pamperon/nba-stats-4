import unittest
from minutes_shadow import assess, audit

class MinutesShadowTests(unittest.TestCase):
    def test_flags_drop(self):
        row = {"Minuti medi":32,"Minuti ultime 5":19,"Partite":25}
        self.assertEqual(assess(row), "watch")
        self.assertEqual(audit([row])["excluded_picks"], 0)
    def test_no_flag_for_stable_or_small_sample(self):
        self.assertEqual(assess({"Minuti medi":30,"Minuti ultime 5":29,"Partite":20}),"normal")
        self.assertEqual(assess({"Minuti medi":30,"Minuti ultime 5":12,"Partite":5}),"unknown")
    def test_no_mutation(self):
        row={"Minuti medi":30,"Minuti ultime 5":15,"Partite":20,"Prob. stimata %":80}
        before=dict(row)
        audit([row])
        self.assertEqual(row,before)

if __name__ == "__main__":
    unittest.main()
