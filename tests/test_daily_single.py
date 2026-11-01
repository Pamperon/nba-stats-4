"""Offline checks for daily single selection and isolation from Top 5."""
import unittest
from unittest.mock import patch
import recommendations


def row(player, odds, probability):
    return {'Giocatore': player, 'ESPN ID': player, 'Quota': odds,
            'Prob. stimata %': probability, 'Partita': 'Home - Away',
            'Mercato': 'PTS', 'Linea': 10.5}


class DailySingleTests(unittest.TestCase):
    def test_no_forced_pick(self):
        with patch.object(recommendations, 'rejection_reasons', return_value=[]):
            self.assertIsNone(recommendations.select_single([row('A', 1.65, 85)]))
            self.assertIsNone(recommendations.select_single([row('B', 1.80, 58)]))

    def test_independent_probability_and_edge(self):
        with patch.object(recommendations, 'rejection_reasons', return_value=[]):
            self.assertIsNone(recommendations.select_single([row('A', 1.70, 62)]))
            chosen = recommendations.select_single([row('B', 1.80, 65)])
            self.assertEqual(chosen['Giocatore'], 'B')

    def test_select_by_expected_return(self):
        with patch.object(recommendations, 'rejection_reasons', return_value=[]):
            chosen = recommendations.select_single([
                row('A', 1.80, 65), row('B', 2.00, 63)])
            self.assertEqual(chosen['Giocatore'], 'B')

    def test_existing_risk_filter(self):
        with patch.object(recommendations, 'rejection_reasons', return_value=['minutes']):
            self.assertIsNone(recommendations.select_single([row('A', 1.90, 70)]))


if __name__ == '__main__':
    unittest.main()
