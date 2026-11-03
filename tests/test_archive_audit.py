"""Offline archive quality audit tests."""
import unittest
from scripts.archive_audit import audit

class ArchiveAuditTests(unittest.TestCase):
    def test_missing_probabilities_excluded(self):
        data={"date":"2026-10-24","results":[
            {"Partita":"A - B","Mercato":"PTS","Scelta":"Over",
             "Prob. stimata %":75.0},
            {"Partita":"A - B","Mercato":"AST","Scelta":"Under",
             "Prob. stimata %":None,"Stato analisi":"Non valutabile"}]}
        result=audit(data)
        self.assertEqual(result["eligible"],1)
        self.assertEqual(result["excluded"],1)
        self.assertEqual(result["excluded_reasons"],{"Non valutabile":1})
        self.assertEqual(result["database_writes"],0)

if __name__=="__main__":
    unittest.main()
