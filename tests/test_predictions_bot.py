"""Tests for predictions_bot update processing and button handling."""

import unittest
from unittest.mock import patch, MagicMock
import predictions_bot


def reset_last_update_id():
    """Reset the global _last_update_id to None before each test."""
    predictions_bot._last_update_id = None


class TestNormalizeButtonText(unittest.TestCase):
    """Test _normalize_button_text helper."""

    def test_strips_variation_selector(self):
        from predictions_bot import _normalize_button_text
        text = '\U0001f3af\ufe0f Predictions'
        result = _normalize_button_text(text)
        self.assertEqual(result, '\U0001f3af Predictions')

    def test_strips_whitespace(self):
        from predictions_bot import _normalize_button_text
        result = _normalize_button_text('  Predictions  ')
        self.assertEqual(result, 'Predictions')

    def test_normal(self):
        from predictions_bot import _normalize_button_text
        result = _normalize_button_text('Predictions')
        self.assertEqual(result, 'Predictions')


class TestMatchesHelper(unittest.TestCase):
    """Test _matches helper."""

    def test_exact_match(self):
        from predictions_bot import _matches
        self.assertTrue(_matches('predictions', ['predictions', '/predictions']))

    def test_contains_match(self):
        from predictions_bot import _matches
        self.assertTrue(_matches('\U0001f3af predictions', ['predictions']))

    def test_no_match(self):
        from predictions_bot import _matches
        self.assertFalse(_matches('random text', ['predictions', 'alerts']))


class TestProcessUpdateButtons(unittest.TestCase):
    """Test process_update with ReplyKeyboardMarkup button presses."""

    def setUp(self):
        reset_last_update_id()

    def _make_update(self, text, chat_id=123, user_id=456, update_id=100):
        return {
            'update_id': update_id,
            'message': {
                'chat': {'id': chat_id},
                'from': {'id': user_id},
                'text': text,
            },
        }

    def test_predictions_button_routes_correctly(self):
        """🎯 Predictions button should trigger predictions handler."""
        update = self._make_update('\U0001f3af\ufe0f Predictions')

        with patch('predictions_bot.handle_predictions_command') as mock_handler:
            predictions_bot.process_update(update)
            mock_handler.assert_called_once_with(123)

    def test_predictions_button_plain_text(self):
        """Plain text 'Predictions' should route to predictions handler."""
        update = self._make_update('Predictions')

        with patch('predictions_bot.handle_predictions_command') as mock_handler:
            predictions_bot.process_update(update)
            mock_handler.assert_called_once_with(123)

    def test_predictions_slash_command(self):
        """/predictions command should route to predictions handler."""
        update = self._make_update('/predictions')

        with patch('predictions_bot.handle_predictions_command') as mock_handler:
            predictions_bot.process_update(update)
            mock_handler.assert_called_once_with(123)

    def test_alerts_button_routes_correctly(self):
        """🔔 Alerts button should trigger alerts handler."""
        update = self._make_update('\U0001f514\ufe0f Alerts')

        with patch('predictions_bot.handle_alerts_command') as mock_handler:
            predictions_bot.process_update(update)
            mock_handler.assert_called_once_with(123)

    def test_alerts_plain_text(self):
        """Plain text 'Alerts' should route to alerts handler."""
        update = self._make_update('Alerts')

        with patch('predictions_bot.handle_alerts_command') as mock_handler:
            predictions_bot.process_update(update)
            mock_handler.assert_called_once_with(123)

    def test_help_button_routes_correctly(self):
        """❓ Help button should trigger help handler."""
        update = self._make_update('\u2753\ufe0f Help')

        with patch('predictions_bot.handle_help_command') as mock_handler:
            predictions_bot.process_update(update)
            mock_handler.assert_called_once_with(123)

    def test_unknown_text_returns_false(self):
        """Unknown text should not trigger any handler."""
        update = self._make_update('random message')

        with patch('predictions_bot.handle_predictions_command') as mock_pred, \
             patch('predictions_bot.handle_help_command') as mock_help, \
             patch('predictions_bot.handle_alerts_command') as mock_alerts:
            result = predictions_bot.process_update(update)
            self.assertFalse(result)
            mock_pred.assert_not_called()
            mock_help.assert_not_called()
            mock_alerts.assert_not_called()

    def test_duplicate_update_skipped(self):
        """Same update_id should be skipped."""
        update = self._make_update('Predictions', chat_id=123, user_id=456, update_id=500)

        with patch('predictions_bot.handle_predictions_command') as mock_handler:
            # First call processes
            predictions_bot.process_update(update)
            self.assertEqual(mock_handler.call_count, 1)

            # Same update_id should be skipped
            result = predictions_bot.process_update(update)
            self.assertFalse(result)
            self.assertEqual(mock_handler.call_count, 1)


class TestProcessUpdateLogging(unittest.TestCase):
    """Test that process_update logs received messages."""

    def setUp(self):
        reset_last_update_id()

    def _make_update(self, text, chat_id=123, user_id=456, update_id=600):
        return {
            'update_id': update_id,
            'message': {
                'chat': {'id': chat_id},
                'from': {'id': user_id},
                'text': text,
            },
        }

    def test_message_logged(self):
        """Received message should be logged with user_id and chat_id."""
        update = self._make_update('Predictions')

        with patch('predictions_bot.logger') as mock_logger, \
             patch('predictions_bot.handle_predictions_command'):
            predictions_bot.process_update(update)
            # Check that logger.info was called with the message details
            call_args = str(mock_logger.info.call_args)
            self.assertIn('user=456', call_args)
            self.assertIn('chat=123', call_args)


if __name__ == '__main__':
    unittest.main()
