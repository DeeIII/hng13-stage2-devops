#!/usr/bin/env python3
"""
Unit tests for AlertWatcher class.
Tests initialization, log parsing, error rate calculation, cooldown enforcement, and failover detection.
"""

import unittest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from collections import deque

# Import the AlertWatcher class
from watcher import AlertWatcher


class TestAlertWatcherInitialization(unittest.TestCase):
    """Test AlertWatcher initialization with environment variables and defaults."""

    def setUp(self):
        """Clean up environment before each test."""
        for key in ['SLACK_WEBHOOK_URL', 'ERROR_RATE_THRESHOLD', 'WINDOW_SIZE', 
                    'ALERT_COOLDOWN_SEC', 'MAINTENANCE_MODE']:
            if key in os.environ:
                del os.environ[key]

    def tearDown(self):
        """Clean up environment after each test."""
        for key in ['SLACK_WEBHOOK_URL', 'ERROR_RATE_THRESHOLD', 'WINDOW_SIZE', 
                    'ALERT_COOLDOWN_SEC', 'MAINTENANCE_MODE']:
            if key in os.environ:
                del os.environ[key]

    @patch('builtins.print')
    def test_initialization_with_defaults(self, mock_print):
        """Test AlertWatcher initializes correctly with default values."""
        watcher = AlertWatcher()
        
        self.assertEqual(watcher.error_threshold, 2.0)
        self.assertEqual(watcher.window_size, 200)
        self.assertEqual(watcher.cooldown_sec, 300)
        self.assertFalse(watcher.maintenance_mode)
        self.assertIsNone(watcher.current_pool)
        self.assertIsNone(watcher.last_pool)
        self.assertIsNone(watcher.last_failover_alert)
        self.assertIsNone(watcher.last_error_rate_alert)
        self.assertEqual(len(watcher.request_window), 0)
        self.assertEqual(watcher.request_window.maxlen, 200)

    @patch('builtins.print')
    def test_initialization_with_env_variables(self, mock_print):
        """Test AlertWatcher initializes correctly with environment variables."""
        os.environ['ERROR_RATE_THRESHOLD'] = '5.5'
        os.environ['WINDOW_SIZE'] = '500'
        os.environ['ALERT_COOLDOWN_SEC'] = '600'
        os.environ['MAINTENANCE_MODE'] = 'true'
        os.environ['SLACK_WEBHOOK_URL'] = 'https://hooks.slack.com/services/TEST/HOOK/URL'
        
        watcher = AlertWatcher()
        
        self.assertEqual(watcher.error_threshold, 5.5)
        self.assertEqual(watcher.window_size, 500)
        self.assertEqual(watcher.cooldown_sec, 600)
        self.assertTrue(watcher.maintenance_mode)
        self.assertEqual(watcher.slack_webhook, 'https://hooks.slack.com/services/TEST/HOOK/URL')
        self.assertEqual(watcher.request_window.maxlen, 500)

    @patch('builtins.print')
    def test_slack_webhook_warning_when_not_configured(self, mock_print):
        """Test warning is printed when Slack webhook is not configured."""
        # Ensure webhook is not set or is the default placeholder
        if 'SLACK_WEBHOOK_URL' in os.environ:
            del os.environ['SLACK_WEBHOOK_URL']
        
        watcher = AlertWatcher()
        
        # Should have None slack_webhook
        self.assertIsNone(watcher.slack_webhook)
        
        # Check that warning was printed
        calls = mock_print.call_args_list
        warning_found = any('WARNING' in str(call_args) and 'SLACK_WEBHOOK_URL' in str(call_args) 
                           for call_args in calls)
        self.assertTrue(warning_found)

    @patch('builtins.print')
    def test_maintenance_mode_enabled(self, mock_print):
        """Test maintenance mode is correctly parsed from environment."""
        os.environ['MAINTENANCE_MODE'] = 'TRUE'
        watcher = AlertWatcher()
        self.assertTrue(watcher.maintenance_mode)
        
        del os.environ['MAINTENANCE_MODE']
        os.environ['MAINTENANCE_MODE'] = 'false'
        watcher = AlertWatcher()
        self.assertFalse(watcher.maintenance_mode)


class TestParseLogLine(unittest.TestCase):
    """Test parse_log_line method for extracting key-value pairs."""

    def setUp(self):
        """Initialize AlertWatcher for each test."""
        with patch('builtins.print'):
            self.watcher = AlertWatcher()

    def test_parse_simple_key_value_pairs(self):
        """Test parsing simple unquoted key-value pairs."""
        log_line = 'status=200 pool=blue response_time=0.045'
        result = self.watcher.parse_log_line(log_line)
        
        self.assertEqual(result['status'], '200')
        self.assertEqual(result['pool'], 'blue')
        self.assertEqual(result['response_time'], '0.045')

    def test_parse_quoted_values(self):
        """Test parsing quoted values."""
        log_line = 'status=200 message="Request successful" pool="blue"'
        result = self.watcher.parse_log_line(log_line)
        
        self.assertEqual(result['status'], '200')
        self.assertEqual(result['message'], 'Request successful')
        self.assertEqual(result['pool'], 'blue')

    def test_parse_mixed_quoted_and_unquoted(self):
        """Test parsing mix of quoted and unquoted values."""
        log_line = 'ip=192.168.1.1 method=GET path="/api/test" status=200 pool=green'
        result = self.watcher.parse_log_line(log_line)
        
        self.assertEqual(result['ip'], '192.168.1.1')
        self.assertEqual(result['method'], 'GET')
        self.assertEqual(result['path'], '/api/test')
        self.assertEqual(result['status'], '200')
        self.assertEqual(result['pool'], 'green')

    def test_parse_quoted_values_with_spaces(self):
        """Test parsing quoted values that contain spaces."""
        log_line = 'request_id=123 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"'
        result = self.watcher.parse_log_line(log_line)
        
        self.assertEqual(result['request_id'], '123')
        self.assertEqual(result['user_agent'], 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')

    def test_parse_empty_string(self):
        """Test parsing empty log line."""
        result = self.watcher.parse_log_line('')
        self.assertEqual(result, {})

    def test_parse_line_with_missing_fields(self):
        """Test parsing log line with some missing fields."""
        log_line = 'status=404 pool=blue'
        result = self.watcher.parse_log_line(log_line)
        
        self.assertEqual(result['status'], '404')
        self.assertEqual(result['pool'], 'blue')
        self.assertNotIn('response_time', result)


class TestCalculateErrorRate(unittest.TestCase):
    """Test calculate_error_rate method."""

    def setUp(self):
        """Initialize AlertWatcher for each test."""
        with patch('builtins.print'):
            self.watcher = AlertWatcher()

    def test_error_rate_empty_window(self):
        """Test error rate calculation with empty window."""
        error_rate = self.watcher.calculate_error_rate()
        self.assertEqual(error_rate, 0.0)

    def test_error_rate_no_errors(self):
        """Test error rate when all requests are successful (status < 500)."""
        self.watcher.request_window = deque([200, 200, 201, 204, 200])
        error_rate = self.watcher.calculate_error_rate()
        self.assertEqual(error_rate, 0.0)

    def test_error_rate_all_errors(self):
        """Test error rate when all requests are errors (status >= 500)."""
        self.watcher.request_window = deque([500, 502, 503, 500, 500])
        error_rate = self.watcher.calculate_error_rate()
        self.assertEqual(error_rate, 100.0)

    def test_error_rate_mixed_requests(self):
        """Test error rate with mix of successful and error requests."""
        # 2 errors out of 10 = 20%
        self.watcher.request_window = deque([200, 200, 200, 500, 200, 200, 502, 200, 200, 200])
        error_rate = self.watcher.calculate_error_rate()
        self.assertEqual(error_rate, 20.0)

    def test_error_rate_single_error(self):
        """Test error rate with single error in window."""
        self.watcher.request_window = deque([200, 200, 200, 500])
        error_rate = self.watcher.calculate_error_rate()
        self.assertAlmostEqual(error_rate, 25.0)

    def test_error_rate_boundary_status_499(self):
        """Test that status 499 is not counted as error (boundary < 500)."""
        self.watcher.request_window = deque([200, 499, 200])
        error_rate = self.watcher.calculate_error_rate()
        self.assertEqual(error_rate, 0.0)

    def test_error_rate_boundary_status_500(self):
        """Test that status 500 is counted as error (boundary >= 500)."""
        self.watcher.request_window = deque([200, 500, 200])
        error_rate = self.watcher.calculate_error_rate()
        self.assertAlmostEqual(error_rate, 33.33, places=2)


class TestShouldSendAlert(unittest.TestCase):
    """Test should_send_alert method for cooldown enforcement and maintenance mode."""

    def setUp(self):
        """Initialize AlertWatcher for each test."""
        with patch('builtins.print'):
            self.watcher = AlertWatcher()

    def test_should_not_send_alert_in_maintenance_mode(self):
        """Test that alerts are not sent in maintenance mode."""
        with patch('builtins.print'):
            self.watcher = AlertWatcher()
        self.watcher.maintenance_mode = True
        
        result = self.watcher.should_send_alert('failover')
        self.assertFalse(result)
        
        result = self.watcher.should_send_alert('error_rate')
        self.assertFalse(result)

    def test_failover_alert_first_time(self):
        """Test that failover alert is sent on first occurrence."""
        self.watcher.last_failover_alert = None
        result = self.watcher.should_send_alert('failover')
        self.assertTrue(result)

    def test_failover_alert_respects_cooldown(self):
        """Test that failover alert respects cooldown period."""
        # Set last alert to recent time (within cooldown)
        self.watcher.last_failover_alert = datetime.now() - timedelta(seconds=50)
        self.watcher.cooldown_sec = 300
        
        result = self.watcher.should_send_alert('failover')
        self.assertFalse(result)

    def test_failover_alert_after_cooldown_expires(self):
        """Test that failover alert is sent after cooldown expires."""
        # Set last alert to past (beyond cooldown)
        self.watcher.last_failover_alert = datetime.now() - timedelta(seconds=301)
        self.watcher.cooldown_sec = 300
        
        result = self.watcher.should_send_alert('failover')
        self.assertTrue(result)

    def test_error_rate_alert_first_time(self):
        """Test that error rate alert is sent on first occurrence."""
        self.watcher.last_error_rate_alert = None
        result = self.watcher.should_send_alert('error_rate')
        self.assertTrue(result)

    def test_error_rate_alert_respects_cooldown(self):
        """Test that error rate alert respects cooldown period."""
        # Set last alert to recent time (within cooldown)
        self.watcher.last_error_rate_alert = datetime.now() - timedelta(seconds=100)
        self.watcher.cooldown_sec = 300
        
        result = self.watcher.should_send_alert('error_rate')
        self.assertFalse(result)

    def test_error_rate_alert_after_cooldown_expires(self):
        """Test that error rate alert is sent after cooldown expires."""
        # Set last alert to past (beyond cooldown)
        self.watcher.last_error_rate_alert = datetime.now() - timedelta(seconds=305)
        self.watcher.cooldown_sec = 300
        
        result = self.watcher.should_send_alert('error_rate')
        self.assertTrue(result)

    def test_cooldown_exactly_at_boundary(self):
        """Test cooldown behavior exactly at boundary."""
        # Set last alert to exactly cooldown seconds ago
        self.watcher.last_failover_alert = datetime.now() - timedelta(seconds=300)
        self.watcher.cooldown_sec = 300
        
        result = self.watcher.should_send_alert('failover')
        self.assertTrue(result)

    def test_different_alert_types_independent_cooldown(self):
        """Test that failover and error_rate alerts have independent cooldowns."""
        # Set failover alert recently
        self.watcher.last_failover_alert = datetime.now() - timedelta(seconds=50)
        # Don't set error_rate alert
        self.watcher.last_error_rate_alert = None
        self.watcher.cooldown_sec = 300
        
        failover_result = self.watcher.should_send_alert('failover')
        error_rate_result = self.watcher.should_send_alert('error_rate')
        
        self.assertFalse(failover_result)  # Still in cooldown
        self.assertTrue(error_rate_result)  # First time, should send


class TestProcessLogLine(unittest.TestCase):
    """Test process_log_line method for pool change detection and failover alerts."""

    def setUp(self):
        """Initialize AlertWatcher for each test."""
        with patch('builtins.print'):
            self.watcher = AlertWatcher()

    def test_process_empty_line(self):
        """Test processing empty log line is handled gracefully."""
        # Should not raise an exception
        self.watcher.process_log_line('')
        self.watcher.process_log_line('   ')
        self.assertEqual(len(self.watcher.request_window), 0)

    def test_process_line_adds_to_request_window(self):
        """Test that valid status codes are added to request window."""
        log_line = 'status=200 pool=blue'
        self.watcher.process_log_line(log_line)
        
        self.assertEqual(len(self.watcher.request_window), 1)
        self.assertEqual(self.watcher.request_window[0], 200)

    def test_process_line_ignores_zero_status(self):
        """Test that status 0 is not added to request window."""
        log_line = 'status=0 pool=blue'
        self.watcher.process_log_line(log_line)
        
        self.assertEqual(len(self.watcher.request_window), 0)

    @patch.object(AlertWatcher, 'handle_failover')
    def test_process_detects_pool_change(self, mock_failover):
        """Test that pool change is detected and triggers failover alert."""
        # First line: establish pool
        log_line1 = 'status=200 pool=blue'
        self.watcher.process_log_line(log_line1)
        
        self.assertEqual(self.watcher.current_pool, 'blue')
        self.assertIsNone(self.watcher.last_pool)
        mock_failover.assert_not_called()
        
        # Second line: change pool
        log_line2 = 'status=200 pool=green'
        with patch('builtins.print'):
            self.watcher.process_log_line(log_line2)
        
        self.assertEqual(self.watcher.current_pool, 'green')
        self.assertEqual(self.watcher.last_pool, 'blue')
        mock_failover.assert_called_once_with('blue', 'green')

    @patch.object(AlertWatcher, 'handle_failover')
    def test_process_no_failover_without_previous_pool(self, mock_failover):
        """Test that failover is not triggered without a previous pool."""
        log_line = 'status=200 pool=blue'
        self.watcher.process_log_line(log_line)
        
        # Current pool is set but last_pool is None, so no failover
        mock_failover.assert_not_called()

    @patch.object(AlertWatcher, 'handle_failover')
    def test_process_no_failover_if_pool_unchanged(self, mock_failover):
        """Test that failover is not triggered if pool doesn't change."""
        # Set initial pool
        log_line1 = 'status=200 pool=blue'
        self.watcher.process_log_line(log_line1)
        mock_failover.reset_mock()
        
        # Same pool in next line
        log_line2 = 'status=201 pool=blue'
        self.watcher.process_log_line(log_line2)
        
        mock_failover.assert_not_called()

    @patch.object(AlertWatcher, 'handle_error_rate_alert')
    def test_process_detects_high_error_rate(self, mock_error_alert):
        """Test that high error rate is detected and triggers alert."""
        self.watcher.error_threshold = 15.0
        self.watcher.window_size = 100  # Set window size to avoid min(50, window_size) check
        
        # Add 15 errors out of 50 requests = 30% (exceeds 15% threshold)
        log_lines = []
        for i in range(50):
            if i % 3 == 0:  # Create ~17 errors out of 50 (~34%)
                log_lines.append('status=500 pool=blue')
            else:
                log_lines.append('status=200 pool=blue')
        
        with patch('builtins.print'):
            for line in log_lines:
                self.watcher.process_log_line(line)
        
        mock_error_alert.assert_called()
        call_args = mock_error_alert.call_args[0][0]
        self.assertGreater(call_args, 15.0)  # Should be > 15%

    @patch.object(AlertWatcher, 'handle_error_rate_alert')
    def test_process_error_rate_not_alerted_below_threshold(self, mock_error_alert):
        """Test that error rate below threshold does not trigger alert."""
        self.watcher.error_threshold = 15.0
        
        # Add 1 error out of 10 requests = 10% (below 15% threshold)
        log_lines = [
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
            'status=500 pool=blue',
        ]
        
        with patch('builtins.print'):
            for line in log_lines:
                self.watcher.process_log_line(line)
        
        mock_error_alert.assert_not_called()

    @patch.object(AlertWatcher, 'handle_error_rate_alert')
    def test_process_not_enough_requests_for_error_rate(self, mock_error_alert):
        """Test that error rate alert is not sent until enough requests are collected."""
        self.watcher.error_threshold = 15.0
        self.watcher.window_size = 200
        
        # Add only 5 requests with errors (less than min 50)
        log_lines = [
            'status=500 pool=blue',
            'status=500 pool=blue',
            'status=500 pool=blue',
            'status=200 pool=blue',
            'status=200 pool=blue',
        ]
        
        with patch('builtins.print'):
            for line in log_lines:
                self.watcher.process_log_line(line)
        
        # Should not trigger because we don't have min(50, window_size) requests yet
        mock_error_alert.assert_not_called()


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple features."""

    def setUp(self):
        """Initialize AlertWatcher for each test."""
        with patch('builtins.print'):
            self.watcher = AlertWatcher()

    @patch.object(AlertWatcher, 'handle_failover')
    @patch.object(AlertWatcher, 'handle_error_rate_alert')
    def test_simultaneous_failover_and_error_rate(self, mock_error_alert, mock_failover):
        """Test handling of simultaneous failover and high error rate."""
        self.watcher.error_threshold = 15.0
        self.watcher.window_size = 100
        
        # Simulate failover with high error rate
        # First 50 requests with blue pool and high error rate
        log_lines = []
        for i in range(50):
            if i % 3 == 0:
                log_lines.append('status=500 pool=blue')
            else:
                log_lines.append('status=200 pool=blue')
        
        # Then switch to green pool (10 more requests)
        for i in range(10):
            if i % 3 == 0:
                log_lines.append('status=500 pool=green')
            else:
                log_lines.append('status=200 pool=green')
        
        with patch('builtins.print'):
            for line in log_lines:
                self.watcher.process_log_line(line)
        
        # Both failover and error rate should be triggered
        mock_failover.assert_called()
        mock_error_alert.assert_called()

    def test_request_window_maxlen_enforcement(self):
        """Test that request window respects maxlen and drops old entries."""
        self.watcher.window_size = 5
        self.watcher.request_window = deque(maxlen=5)
        
        # Add more than maxlen requests
        for i in range(8):
            log_line = f'status={200 + i} pool=blue'
            self.watcher.process_log_line(log_line)
        
        # Window should only contain last 5 requests
        self.assertEqual(len(self.watcher.request_window), 5)
        # Check that it contains the last 5 statuses
        self.assertEqual(list(self.watcher.request_window), [203, 204, 205, 206, 207])


if __name__ == '__main__':
    unittest.main()
