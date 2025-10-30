# Running AlertWatcher Unit Tests

## Quick Start

Run all 37 tests with verbose output:
```bash
python -m unittest test_watcher -v
```

## Test Results Summary

✅ **37 tests - ALL PASSING**

### Test Breakdown by Category

| Test Class | Tests | Status |
|-----------|-------|--------|
| TestAlertWatcherInitialization | 4 | ✅ PASS |
| TestParseLogLine | 6 | ✅ PASS |
| TestCalculateErrorRate | 7 | ✅ PASS |
| TestShouldSendAlert | 9 | ✅ PASS |
| TestProcessLogLine | 10 | ✅ PASS |
| TestIntegration | 2 | ✅ PASS |

## Test Coverage

### 1. **Initialization** (4 tests)
- ✅ AlertWatcher initializes correctly with environment variables
- ✅ AlertWatcher initializes correctly with default values
- ✅ Warning is printed when Slack webhook not configured
- ✅ Maintenance mode is correctly parsed from environment

### 2. **Log Parsing** (6 tests)
- ✅ parse_log_line correctly extracts key-value pairs from Nginx log lines
- ✅ Handles simple unquoted key-value pairs
- ✅ Handles quoted values with spaces
- ✅ Handles mixed quoted and unquoted values
- ✅ Handles empty strings
- ✅ Handles lines with missing fields

### 3. **Error Rate Calculation** (7 tests)
- ✅ calculate_error_rate accurately computes the error percentage from a window of request statuses
- ✅ Returns 0% for empty window
- ✅ Returns 0% for all successful requests
- ✅ Returns 100% for all error requests
- ✅ Returns correct percentage for mixed requests
- ✅ Correctly identifies error boundary at status 500 (>= 500 = error)
- ✅ Correctly identifies non-error boundary at status 499 (< 500 = not error)

### 4. **Cooldown & Maintenance** (9 tests)
- ✅ should_send_alert enforces cooldown periods and maintenance mode for different alert types
- ✅ No alerts sent in maintenance mode
- ✅ First failover alert always sent
- ✅ First error rate alert always sent
- ✅ Failover alert respects cooldown period
- ✅ Error rate alert respects cooldown period
- ✅ Alerts sent after cooldown expires
- ✅ Alerts sent at cooldown boundary
- ✅ Different alert types have independent cooldowns

### 5. **Log Processing & Failover** (10 tests)
- ✅ process_log_line correctly detects pool changes and triggers failover alerts
- ✅ Handles empty log lines gracefully
- ✅ Adds valid status codes to request window
- ✅ Ignores invalid status (0)
- ✅ Detects pool change and triggers failover alert
- ✅ Does not trigger failover on first pool assignment
- ✅ Does not trigger failover if pool unchanged
- ✅ Detects high error rate and triggers alert
- ✅ Does not alert for error rate below threshold
- ✅ Does not alert without sufficient requests collected

### 6. **Integration** (2 tests)
- ✅ Handles simultaneous failover and error rate events
- ✅ Request window enforces maxlen and drops old entries

## Running Specific Tests

Run a single test class:
```bash
python -m unittest test_watcher.TestAlertWatcherInitialization -v
```

Run a single test:
```bash
python -m unittest test_watcher.TestAlertWatcherInitialization.test_initialization_with_defaults -v
```

Run tests with pattern matching:
```bash
python -m unittest test_watcher.TestCalculateErrorRate -v
```

## Test Details

See **TEST_DOCUMENTATION.md** for comprehensive documentation of all 37 tests, including:
- Detailed description of each test
- Input/output examples
- Expected behavior
- Edge cases covered
- Mocking strategies used

## Key Testing Techniques

✅ **Environment Variable Isolation** - Proper setup/teardown to prevent test pollution
✅ **Mock Objects** - Using `@patch` to isolate components and verify calls
✅ **Boundary Testing** - Testing edge cases like status 499 vs 500, cooldown boundaries
✅ **Time Simulation** - Using `timedelta` to test time-based logic
✅ **Data Structure Testing** - Testing deque behavior with maxlen enforcement
✅ **Error Rate Scenarios** - Testing 0%, 100%, and mixed error percentages
✅ **State Management** - Testing pool tracking and alert history

## CI/CD Integration

```bash
#!/bin/bash
set -e

echo "Running AlertWatcher unit tests..."
python -m unittest test_watcher -v

echo ""
echo "✅ All tests passed!"
```
