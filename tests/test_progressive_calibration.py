import unittest
from unittest.mock import patch
import calibration
import progressive_calibration

def row(p=80, price=1.5):
    return {"Mercato":"PTS","Scelta":"Over","Linea":19.5,
            "Quota":price,"Prob. stimata %":p,"Value stimato %":20}

class ProgressiveCalibrationTests(unittest.TestCase):
    def test_no_historical_evidence_is_noop(self):
        rows=[row()]
        output,status=progressive_calibration.apply(rows,[])
        self.assertEqual(output,rows)
        self.assertFalse(status["active"])

    def test_incomplete_validation_never_activates(self):
        history=[{"date":"2026-10-20","market":"PTS","probability_bin":80,
                  "n":400,"wins":100,"sum_p":320.0,"sum_brier":250.0}]
        output,status=progressive_calibration.apply([row()],history)
        self.assertFalse(status["active"])
        self.assertEqual(output[0]["Prob. stimata %"],80)

    def test_adjustment_preserves_raw_and_updates_value(self):
        aggregates=[{"market":"PTS","probability_bin":80,
                     "n":400,"observed":0.6,"predicted":0.8}]
        original=row()
        with patch.object(calibration,"approved_adjustments",return_value=aggregates):
            output,status=progressive_calibration.apply([original],[])
        self.assertTrue(status["active"])
        self.assertEqual(status["adjusted"],1)
        self.assertEqual(output[0]["Prob. grezza %"],80)
        self.assertEqual(output[0]["Prob. stimata %"],77.0)
        self.assertEqual(output[0]["Value stimato %"],15.5)
        self.assertNotIn("Prob. grezza %",original)
        aggregate=calibration.aggregate([{**output[0],"actual":20,"played":True}])
        self.assertAlmostEqual(aggregate[("PTS",80)]["sum_p"],0.8)

    def test_non_evaluable_rows_remain_unchanged(self):
        with patch.object(calibration,"approved_adjustments",return_value=[{"market":"PTS","probability_bin":80,"n":400,"observed":0.6,"predicted":0.8}]):
            result,_=progressive_calibration.apply([{"Mercato":"PTS","Prob. stimata %":None}],[])
        self.assertEqual(result[0]["Prob. stimata %"],None)

if __name__=="__main__":
    unittest.main()
