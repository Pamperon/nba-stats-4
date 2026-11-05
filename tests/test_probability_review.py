import unittest
from probability_review import summarize

class ProbabilityReviewTests(unittest.TestCase):
    def test_only_settled_finite_published_probabilities(self):
        rows=[{'status':'won','Prob. stimata %':80}, {'status':'lost','Prob. stimata %':90},
              {'status':'unresolved','Prob. stimata %':99}, {'status':'not_played','Prob. stimata %':80},
              {'status':'won','Prob. stimata %':float('nan')}, {'status':'lost'}]
        result=summarize(rows)
        self.assertEqual(result['n'],2)
        self.assertEqual(result['estimated_pct'],85)
        self.assertEqual(result['observed_pct'],50)
        self.assertEqual([b['n'] for b in result['bins']],[1,1])
    def test_empty_and_boundaries(self):
        self.assertIsNone(summarize([])['observed_pct'])
        self.assertEqual(summarize([{'status':'won','estimated_probability':100}])['bins'][0]['n'],1)
