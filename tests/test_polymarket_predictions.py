"""
Tests for Polymarket Predictions Module.
"""

import unittest
from unittest.mock import patch, MagicMock

from polymarket_predictions import (
    PredictionMarket,
    _categorize_market,
    _translate_question,
    _translate_outcome_name,
    fetch_polymarket_predictions,
    get_predictions_by_category,
)


class TestCategorizeMarket(unittest.TestCase):
    def test_fed_category(self):
        self.assertEqual(_categorize_market("Will the Fed raise rates?"), "fed")
        self.assertEqual(_categorize_market("Federal Reserve interest rate decision"), "fed")
        self.assertEqual(_categorize_market("Fed funds rate in May"), "fed")

    def test_inflation_category(self):
        self.assertEqual(_categorize_market("Will inflation be above 3%?"), "inflation")
        self.assertEqual(_categorize_market("CPI report May 2026"), "inflation")

    def test_gold_category(self):
        self.assertEqual(_categorize_market("Gold price above $3000?"), "gold")
        self.assertEqual(_categorize_market("XAUUSD end of month"), "gold")
        self.assertEqual(_categorize_market("Gold hit $3100?"), "gold")

    def test_employment_category(self):
        self.assertEqual(_categorize_market("Nonfarm payrolls above 200K?"), "employment")
        self.assertEqual(_categorize_market("Unemployment rate in May"), "employment")

    def test_economy_category(self):
        self.assertEqual(_categorize_market("GDP growth Q2 2026"), "economy")
        self.assertEqual(_categorize_market("Will there be a recession?"), "economy")


class TestTranslateQuestion(unittest.TestCase):
    def test_fed_raise(self):
        result = _translate_question("Will the Fed raise rates in May?", "fed")
        self.assertIn("ขึ้นดอกเบี้ย", result)

    def test_fed_cut(self):
        result = _translate_question("Will the Fed cut rates?", "fed")
        self.assertIn("ลดดอกเบี้ย", result)

    def test_fed_hold(self):
        result = _translate_question("Will the Fed hold rates?", "fed")
        self.assertIn("คงดอกเบี้ย", result)

    def test_gold_above(self):
        result = _translate_question("Will gold price be above $3000?", "gold")
        self.assertIn("เกิน", result)
        self.assertIn("3000", result)

    def test_gold_below(self):
        result = _translate_question("Will gold price be below $2800?", "gold")
        self.assertIn("ต่ำกว่า", result)
        self.assertIn("2800", result)

    def test_inflation(self):
        result = _translate_question("Will inflation be above 3%?", "inflation")
        self.assertIn("เงินเฟ้อ", result)

    def test_employment(self):
        result = _translate_question("Will unemployment drop?", "employment")
        self.assertIn("การจ้างงาน", result)


class TestTranslateOutcomeName(unittest.TestCase):
    def test_yes_no(self):
        self.assertEqual(_translate_outcome_name("Yes", "fed"), "ใช่")
        self.assertEqual(_translate_outcome_name("No", "fed"), "ไม่ใช่")

    def test_fed_outcomes(self):
        self.assertEqual(_translate_outcome_name("Raise", "fed"), "ขึ้นดอกเบี้ย")
        self.assertEqual(_translate_outcome_name("Cut", "fed"), "ลดดอกเบี้ย")
        self.assertEqual(_translate_outcome_name("Hold", "fed"), "คงดอกเบี้ย")

    def test_direction(self):
        self.assertEqual(_translate_outcome_name("Above", "gold"), "สูงกว่า")
        self.assertEqual(_translate_outcome_name("Below", "gold"), "ต่ำกว่า")

    def test_unknown(self):
        self.assertEqual(_translate_outcome_name("Unknown", "gold"), "Unknown")


class TestFetchPolymarketPredictions(unittest.TestCase):
    @patch('polymarket_predictions.requests.get')
    def test_fetch_gold_market(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'markets': [
                {
                    'question': 'Will gold price be above $3000?',
                    'description': 'Gold price prediction',
                    'outcomes': ['Yes', 'No'],
                    'outcome_prices': ['0.65', '0.35'],
                    'volume': 1000000,
                    'slug': 'gold-price-3000',
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = fetch_polymarket_predictions()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, 'gold')
        self.assertEqual(results[0].outcomes[0]['price'], 0.65)
        self.assertIn("เกิน", results[0].question_th)

    @patch('polymarket_predictions.requests.get')
    def test_fetch_fed_market(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'markets': [
                {
                    'question': 'Will the Fed raise rates in May?',
                    'description': 'Fed rate decision',
                    'outcomes': ['Yes', 'No'],
                    'outcome_prices': ['0.25', '0.75'],
                    'volume': 5000000,
                    'slug': 'fed-rate-may',
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = fetch_polymarket_predictions()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, 'fed')
        self.assertIn("ขึ้นดอกเบี้ย", results[0].question_th)

    @patch('polymarket_predictions.requests.get')
    def test_excludes_sports(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'markets': [
                {
                    'question': 'Will NHL team win Stanley Cup?',
                    'description': 'Hockey prediction',
                    'outcomes': ['Yes', 'No'],
                    'outcome_prices': ['0.5', '0.5'],
                    'volume': 100000,
                    'slug': 'nhl-stanley-cup',
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = fetch_polymarket_predictions()

        self.assertEqual(len(results), 0)

    @patch('polymarket_predictions.requests.get')
    def test_excludes_crypto(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'markets': [
                {
                    'question': 'Will Bitcoin reach $100K?',
                    'description': 'Crypto prediction',
                    'outcomes': ['Yes', 'No'],
                    'outcome_prices': ['0.4', '0.6'],
                    'volume': 2000000,
                    'slug': 'bitcoin-100k',
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = fetch_polymarket_predictions()

        self.assertEqual(len(results), 0)

    @patch('polymarket_predictions.requests.get')
    def test_request_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        results = fetch_polymarket_predictions()

        self.assertEqual(results, [])

    @patch('polymarket_predictions.requests.get')
    def test_id_based_dedup(self, mock_get):
        """Test that markets are deduplicated by ID, not just question."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'markets': [
                {
                    'id': 'market-123',
                    'question': 'Will gold be above $3000?',
                    'description': 'Gold price',
                    'outcomes': ['Yes', 'No'],
                    'outcome_prices': ['0.6', '0.4'],
                    'volume': 1000000,
                    'slug': 'gold-above-3000',
                },
                {
                    'id': 'market-123',  # Same ID - should be deduped
                    'question': 'Will gold be above $3000?',  # Same question
                    'description': 'Gold price',
                    'outcomes': ['Yes', 'No'],
                    'outcome_prices': ['0.6', '0.4'],
                    'volume': 1000000,
                    'slug': 'gold-above-3000-2',
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = fetch_polymarket_predictions()

        # Should only have 1 market (deduped by ID)
        self.assertEqual(len(results), 1)


class TestGetPredictionsByCategory(unittest.TestCase):
    def test_group_by_category(self):
        markets = [
            PredictionMarket(
                market_id="fed_raise_1",
                question="Fed raise?", question_th="เฟดขึ้นดอกเบี้ย?",
                outcomes=[{'name': 'Yes', 'price': 0.25}],
                volume=1000, url='', category='fed', explanation_th=''
            ),
            PredictionMarket(
                market_id="gold_above_3000",
                question="Gold above $3000?", question_th="ทองเกิน $3000?",
                outcomes=[{'name': 'Yes', 'price': 0.65}],
                volume=2000, url='', category='gold', explanation_th=''
            ),
            PredictionMarket(
                market_id="fed_cut_1",
                question="Fed cut?", question_th="เฟดลดดอกเบี้ย?",
                outcomes=[{'name': 'Yes', 'price': 0.10}],
                volume=500, url='', category='fed', explanation_th=''
            ),
        ]

        result = get_predictions_by_category(markets)

        self.assertEqual(len(result), 2)
        self.assertEqual(len(result['fed']), 2)
        self.assertEqual(len(result['gold']), 1)


if __name__ == '__main__':
    unittest.main()
