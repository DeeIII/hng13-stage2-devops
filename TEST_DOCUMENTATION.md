# AlertWatcher Unit Tests Documentation

## Overview

This document describes the comprehensive unit test suite for the `AlertWatcher` class, which monitors Nginx logs for blue/green deployment failovers and tracks error rates.

**Total Tests:** 37 ✅ All Passing

## Test Execution

### Run All Tests
```bash
python -m unittest test_watcher -v
```

### Run Specific Test Class
```bash
python -m unittest test_watcher.TestAlertWatcherInitialization -v
```

### Run Single Test
```bash
python -m unittest test_watcher.TestAlertWatcherInitialization.test_initialization_with_defaults -v
```

---

## Test Coverage

### 1. TestAlertWatcherInitialization (4 tests)
Tests that verify AlertWatcher properly initializes with environment variables and default values.

#### test_initialization_with_defaults
- **Purpose:** Verify AlertWatcher initializes with correct default values when no environment variables are set
- **Assertions:**
  - `error_threshold` defaults to `2.0`
  - `window_size` defaults to `200`
  - `cooldown_sec` defaults to `300`
  - `maintenance_mode` defaults to `False`
  - `current_pool` and `last_pool` are `None`
  - `last_failover_alert` and `last_error_rate_alert` are `None`
  - `request_window` is empty with correct maxlen

#### test_initialization_with_env_variables
- **Purpose:** Verify AlertWatcher correctly reads and applies environment variables
- **Environment Variables:**
  - `ERROR_RATE_THRESHOLD=5.5`
  - `WINDOW_SIZE=500`
  - `ALERT_COOLDOWN_SEC=600`
  - `MAINTENANCE_MODE=true`
  - `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/TEST/HOOK/URL`
- **Assertions:** All values are set correctly from environment

#### test_slack_webhook_warning_when_not_configured
- **Purpose:** Verify warning is printed when Slack webhook is not configured
- **Assertions:**
  - `slack_webhook` is `None` when not configured
  - Warning message containing "SLACK_WEBHOOK_URL" is printed

#### test_maintenance_mode_enabled
- **Purpose:** Verify maintenance mode flag is correctly parsed from environment (case-insensitive)
- **Test Cases:**
  - `MAINTENANCE_MODE=TRUE` → `True`
  - `MAINTENANCE_MODE=false` → `False`

---

### 2. TestParseLogLine (6 tests)
Tests the `parse_log_line()` method that extracts key-value pairs from log lines.

#### test_parse_simple_key_value_pairs
- **Purpose:** Parse unquoted key-value pairs
- **Input:** `'status=200 pool=blue response_time=0.045'`
- **Expected Output:** `{'status': '200', 'pool': 'blue', 'response_time': '0.045'}`

#### test_parse_quoted_values
- **Purpose:** Parse quoted values correctly
- **Input:** `'status=200 message="Request successful" pool="blue"'`
- **Expected Output:** `{'status': '200', 'message': 'Request successful', 'pool': 'blue'}`

#### test_parse_mixed_quoted_and_unquoted
- **Purpose:** Parse mix of quoted and unquoted values
- **Input:** `'ip=192.168.1.1 method=GET path="/api/test" status=200 pool=green'`
- **Expected Output:** All key-value pairs extracted correctly

#### test_parse_quoted_values_with_spaces
- **Purpose:** Parse quoted values containing spaces
- **Input:** `'request_id=123 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"'`
- **Expected Output:** User agent string preserved with spaces

#### test_parse_empty_string
- **Purpose:** Handle empty log lines gracefully
- **Input:** `''`
- **Expected Output:** `{}`

#### test_parse_line_with_missing_fields
- **Purpose:** Parse log lines with missing optional fields
- **Input:** `'status=404 pool=blue'`
- **Assertions:**
  - `status` and `pool` are present
  - `response_time` is not in result

---

### 3. TestCalculateErrorRate (7 tests)
Tests the `calculate_error_rate()` method that computes error percentages from request windows.

#### test_error_rate_empty_window
- **Purpose:** Return 0% when request window is empty
- **Window:** `[]`
- **Expected Rate:** `0.0%`

#### test_error_rate_no_errors
- **Purpose:** Return 0% when all requests are successful (status < 500)
- **Window:** `[200, 200, 201, 204, 200]`
- **Expected Rate:** `0.0%`

#### test_error_rate_all_errors
- **Purpose:** Return 100% when all requests are errors (status >= 500)
- **Window:** `[500, 502, 503, 500, 500]`
- **Expected Rate:** `100.0%`

#### test_error_rate_mixed_requests
- **Purpose:** Calculate correct percentage with mixed statuses
- **Window:** `[200, 200, 200, 500, 200, 200, 502, 200, 200, 200]`
- **Calculation:** 2 errors out of 10 = 20%
- **Expected Rate:** `20.0%`

#### test_error_rate_single_error
- **Purpose:** Calculate correct percentage with single error
- **Window:** `[200, 200, 200, 500]`
- **Expected Rate:** `25.0%`

#### test_error_rate_boundary_status_499
- **Purpose:** Verify status 499 is NOT counted as error (boundary < 500)
- **Window:** `[200, 499, 200]`
- **Expected Rate:** `0.0%`

#### test_error_rate_boundary_status_500
- **Purpose:** Verify status 500 IS counted as error (boundary >= 500)
- **Window:** `[200, 500, 200]`
- **Expected Rate:** `≈33.33%`

---

### 4. TestShouldSendAlert (9 tests)
Tests the `should_send_alert()` method for cooldown enforcement and maintenance mode.

#### test_should_not_send_alert_in_maintenance_mode
- **Purpose:** Alerts should never be sent when maintenance mode is enabled
- **Assertions:**
  - `should_send_alert('failover')` returns `False`
  - `should_send_alert('error_rate')` returns `False`

#### test_failover_alert_first_time
- **Purpose:** First failover alert should always be sent (no cooldown yet)
- **State:** `last_failover_alert = None`
- **Expected:** `True`

#### test_failover_alert_respects_cooldown
- **Purpose:** Failover alert blocked within cooldown period
- **State:** Last alert was 50 seconds ago
- **Cooldown:** 300 seconds
- **Expected:** `False`

#### test_failover_alert_after_cooldown_expires
- **Purpose:** Failover alert sent after cooldown expires
- **State:** Last alert was 301 seconds ago
- **Cooldown:** 300 seconds
- **Expected:** `True`

#### test_error_rate_alert_first_time
- **Purpose:** First error rate alert should always be sent (no cooldown yet)
- **State:** `last_error_rate_alert = None`
- **Expected:** `True`

#### test_error_rate_alert_respects_cooldown
- **Purpose:** Error rate alert blocked within cooldown period
- **State:** Last alert was 100 seconds ago
- **Cooldown:** 300 seconds
- **Expected:** `False`

#### test_error_rate_alert_after_cooldown_expires
- **Purpose:** Error rate alert sent after cooldown expires
- **State:** Last alert was 305 seconds ago
- **Cooldown:** 300 seconds
- **Expected:** `True`

#### test_cooldown_exactly_at_boundary
- **Purpose:** Alert sent when exactly at cooldown boundary
- **State:** Last alert was exactly 300 seconds ago
- **Cooldown:** 300 seconds
- **Expected:** `True` (>= comparison)

#### test_different_alert_types_independent_cooldown
- **Purpose:** Failover and error_rate alerts have independent cooldowns
- **State:**
  - Last failover: 50 seconds ago
  - Last error_rate: Never (None)
  - Cooldown: 300 seconds
- **Expected:**
  - `should_send_alert('failover')` → `False`
  - `should_send_alert('error_rate')` → `True`

---

### 5. TestProcessLogLine (10 tests)
Tests the `process_log_line()` method for pool change detection and failover alerts.

#### test_process_empty_line
- **Purpose:** Empty lines are handled gracefully
- **Inputs:** `''` and `'   '`
- **Expected:** No exceptions, window remains empty

#### test_process_line_adds_to_request_window
- **Purpose:** Valid status codes are added to request window
- **Input:** `'status=200 pool=blue'`
- **Expected:**
  - `request_window` length = 1
  - `request_window[0]` = 200

#### test_process_line_ignores_zero_status
- **Purpose:** Status 0 (invalid) is not added to window
- **Input:** `'status=0 pool=blue'`
- **Expected:** Window remains empty

#### test_process_detects_pool_change
- **Purpose:** Pool change triggers failover detection and alert
- **Sequence:**
  1. Process: `'status=200 pool=blue'` → sets current_pool to blue
  2. Process: `'status=200 pool=green'` → triggers failover alert
- **Mocked:** `handle_failover('blue', 'green')` called once

#### test_process_no_failover_without_previous_pool
- **Purpose:** Failover not triggered on first pool assignment
- **Input:** `'status=200 pool=blue'`
- **Expected:** `handle_failover()` not called

#### test_process_no_failover_if_pool_unchanged
- **Purpose:** Failover not triggered when pool remains same
- **Sequence:**
  1. First request: pool=blue (sets current_pool)
  2. Second request: pool=blue (unchanged)
- **Expected:** `handle_failover()` not called

#### test_process_detects_high_error_rate
- **Purpose:** High error rate triggers alert
- **Setup:**
  - Error threshold: 15%
  - Window size: 100
  - Requests: 50 total with ~34% errors (1 in every 3)
- **Expected:** `handle_error_rate_alert()` called with rate > 15%

#### test_process_error_rate_not_alerted_below_threshold
- **Purpose:** Error rate below threshold does not trigger alert
- **Setup:**
  - Error threshold: 15%
  - Requests: 10 total with 1 error (10%)
- **Expected:** `handle_error_rate_alert()` not called

#### test_process_not_enough_requests_for_error_rate
- **Purpose:** Error rate alert not sent until min(50, window_size) requests collected
- **Setup:**
  - Window size: 200
  - Requests: Only 5 (< 50 minimum)
- **Expected:** `handle_error_rate_alert()` not called

---

### 6. TestIntegration (2 tests)
Integration tests combining multiple features.

#### test_simultaneous_failover_and_error_rate
- **Purpose:** Both failover and error rate alerts can be triggered simultaneously
- **Scenario:**
  - 50 requests with ~34% error rate on blue pool
  - Switch to green pool
  - 10 more requests
- **Expected:**
  - `handle_failover()` called (blue → green)
  - `handle_error_rate_alert()` called (error rate > 15%)

#### test_request_window_maxlen_enforcement
- **Purpose:** Request window enforces maxlen and drops old entries
- **Setup:**
  - Window size: 5 (maxlen=5)
  - Add: 8 requests with statuses 200-207
- **Expected:**
  - Window length: 5
  - Window contents: [203, 204, 205, 206, 207] (last 5)

---

## Test Metrics

| Category | Count | Status |
|----------|-------|--------|
| Initialization Tests | 4 | ✅ Pass |
| Parse Log Line Tests | 6 | ✅ Pass |
| Error Rate Calculation Tests | 7 | ✅ Pass |
| Cooldown & Maintenance Tests | 9 | ✅ Pass |
| Log Processing Tests | 10 | ✅ Pass |
| Integration Tests | 2 | ✅ Pass |
| **TOTAL** | **37** | **✅ All Pass** |

---

## Key Test Patterns

### Environment Variable Isolation
Each test properly sets up and tears down environment variables to avoid cross-test contamination.

### Mocking Strategy
- `@patch('builtins.print')` - Suppress output during testing
- `@patch.object(AlertWatcher, 'method_name')` - Mock specific methods to verify calls

### Time Handling
Tests use `datetime.now() - timedelta(seconds=...)` to simulate time passing for cooldown tests.

### Request Window Testing
Tests use `collections.deque` with specific maxlen values to test window behavior.

---

## Coverage Summary

✅ **Initialization:** All default and custom configurations
✅ **Log Parsing:** Simple pairs, quoted values, mixed formats, edge cases
✅ **Error Rate:** Empty window, 0%, 100%, mixed rates, boundaries
✅ **Cooldown Logic:** First alert, within cooldown, after cooldown, boundary
✅ **Maintenance Mode:** Alert blocking in maintenance mode
✅ **Pool Detection:** Pool changes, failover triggering
✅ **Error Detection:** Error rate above/below threshold, minimum requests
✅ **Integration:** Simultaneous events, window management

---

## Running Tests in CI/CD

```bash
#!/bin/bash
cd /path/to/project
python -m unittest test_watcher -v
EXIT_CODE=$?
exit $EXIT_CODE
```

---

## Future Test Enhancements

Potential areas for additional tests:
- Slack alert sending (mock requests.post)
- Log file tailing behavior
- Concurrent log processing
- Large request windows (performance)
- Malformed log line handling
- Resource cleanup (file handles)
