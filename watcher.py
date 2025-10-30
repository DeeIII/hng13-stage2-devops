#!/usr/bin/env python3
"""
Nginx Log Watcher for Blue/Green Deployment Monitoring
Monitors Nginx access logs, detects failovers, tracks error rates, and sends Slack alerts.
"""

import os
import re
import time
import requests
from collections import deque
from datetime import datetime


class AlertWatcher:
    def __init__(self):
        # Configuration from environment variables
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.error_threshold = float(os.getenv('ERROR_RATE_THRESHOLD', '2.0'))
        self.window_size = int(os.getenv('WINDOW_SIZE', '200'))
        self.cooldown_sec = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))
        self.maintenance_mode = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'
        
        # State tracking
        self.current_pool = None
        self.last_pool = None
        self.request_window = deque(maxlen=self.window_size)
        self.last_failover_alert = None
        self.last_error_rate_alert = None
        
        # Validation
        if not self.slack_webhook or self.slack_webhook == 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL':
            print("⚠️  WARNING: SLACK_WEBHOOK_URL not configured. Alerts will be logged only.")
            self.slack_webhook = None
        
        print(f"✓ Alert Watcher initialized")
        print(f"  - Error threshold: {self.error_threshold}%")
        print(f"  - Window size: {self.window_size} requests")
        print(f"  - Alert cooldown: {self.cooldown_sec} seconds")
        print(f"  - Maintenance mode: {self.maintenance_mode}")
        print(f"  - Slack alerts: {'enabled' if self.slack_webhook else 'disabled (logs only)'}")
        print()

    def parse_log_line(self, line):
        """Parse Nginx log line in key=value format."""
        data = {}
        
        # Extract quoted and unquoted values
        pattern = r'(\w+)=(?:"([^"]*)"|([^\s]*))'
        matches = re.findall(pattern, line)
        
        for key, quoted_val, unquoted_val in matches:
            data[key] = quoted_val if quoted_val else unquoted_val
        
        return data

    def calculate_error_rate(self):
        """Calculate current error rate over the sliding window."""
        if len(self.request_window) == 0:
            return 0.0
        
        error_count = sum(1 for status in self.request_window if status >= 500)
        return (error_count / len(self.request_window)) * 100

    def should_send_alert(self, alert_type):
        """Check if enough time has passed since last alert (cooldown)."""
        if self.maintenance_mode:
            return False
        
        now = datetime.now()
        
        if alert_type == 'failover':
            if self.last_failover_alert is None:
                return True
            return (now - self.last_failover_alert).total_seconds() >= self.cooldown_sec
        
        elif alert_type == 'error_rate':
            if self.last_error_rate_alert is None:
                return True
            return (now - self.last_error_rate_alert).total_seconds() >= self.cooldown_sec
        
        return False

    def send_slack_alert(self, alert_data):
        """Send alert to Slack webhook."""
        if not self.slack_webhook:
            print(f"📢 ALERT (Slack disabled): {alert_data['text']}")
            return
        
        try:
            payload = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": alert_data['title'],
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": alert_data['text']
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                            }
                        ]
                    }
                ]
            }
            
            if 'fields' in alert_data:
                payload['blocks'].insert(2, {
                    "type": "section",
                    "fields": alert_data['fields']
                })
            
            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✓ Slack alert sent: {alert_data['title']}")
            else:
                print(f"✗ Failed to send Slack alert: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"✗ Error sending Slack alert: {e}")

    def handle_failover(self, from_pool, to_pool):
        """Detect and alert on pool failover."""
        if not self.should_send_alert('failover'):
            print(f"⏱  Failover detected ({from_pool}→{to_pool}) but in cooldown period")
            return
        
        alert_data = {
            'title': '🔄 Failover Detected',
            'text': f"*Pool switch detected:* {from_pool.upper()} → {to_pool.upper()}",
            'fields': [
                {
                    "type": "mrkdwn",
                    "text": f"*Previous Pool:*\n{from_pool.upper()}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Current Pool:*\n{to_pool.upper()}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Action Required:*\nCheck health of {from_pool.upper()} pool"
                }
            ]
        }
        
        self.send_slack_alert(alert_data)
        self.last_failover_alert = datetime.now()

    def handle_error_rate_alert(self, error_rate):
        """Alert on high error rate."""
        if not self.should_send_alert('error_rate'):
            print(f"⏱  High error rate ({error_rate:.2f}%) detected but in cooldown period")
            return
        
        alert_data = {
            'title': '⚠️ High Error Rate Detected',
            'text': f"*Error rate exceeded threshold:* {error_rate:.2f}% (threshold: {self.error_threshold}%)",
            'fields': [
                {
                    "type": "mrkdwn",
                    "text": f"*Current Error Rate:*\n{error_rate:.2f}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Threshold:*\n{self.error_threshold}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Window Size:*\n{len(self.request_window)} requests"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Current Pool:*\n{self.current_pool.upper() if self.current_pool else 'Unknown'}"
                },
                {
                    "type": "mrkdwn",
                    "text": "*Action Required:*\nInspect upstream logs, consider pool toggle"
                }
            ]
        }
        
        self.send_slack_alert(alert_data)
        self.last_error_rate_alert = datetime.now()

    def process_log_line(self, line):
        """Process a single log line."""
        if not line or line.strip() == '':
            return
        
        data = self.parse_log_line(line)
        
        # Extract relevant fields
        status = int(data.get('status', '0'))
        pool = data.get('pool', '')
        
        # Track request in sliding window
        if status > 0:
            self.request_window.append(status)
        
        # Detect pool changes (failover)
        if pool and pool != self.current_pool:
            self.last_pool = self.current_pool
            self.current_pool = pool
            
            if self.last_pool and self.last_pool != self.current_pool:
                print(f"🔄 Failover detected: {self.last_pool} → {self.current_pool}")
                self.handle_failover(self.last_pool, self.current_pool)
        
        # Check error rate (only if we have enough data)
        if len(self.request_window) >= min(50, self.window_size):
            error_rate = self.calculate_error_rate()
            
            if error_rate > self.error_threshold:
                print(f"⚠️  High error rate: {error_rate:.2f}% (threshold: {self.error_threshold}%)")
                self.handle_error_rate_alert(error_rate)

    def tail_logs(self, log_path):
        """Tail Nginx access logs in real-time."""
        print(f"👀 Watching logs at: {log_path}")
        print(f"⏳ Waiting for log file to be created...\n")
        
        # Wait for log file to exist
        while not os.path.exists(log_path):
            time.sleep(1)
        
        print(f"✓ Log file found, starting watch...\n")
        
        # Read existing lines first to get to end, then tail
        with open(log_path, 'r') as f:
            # Read all existing lines (don't process them to avoid false alerts on startup)
            for _ in f:
                pass
            
            # Now tail new lines
            while True:
                line = f.readline()
                
                if line:
                    self.process_log_line(line)
                else:
                    time.sleep(0.1)

    def run(self):
        """Main entry point."""
        log_path = '/var/log/nginx/access.log'
        
        print("=" * 60)
        print("🚀 Alert Watcher Started")
        print("=" * 60)
        
        try:
            self.tail_logs(log_path)
        except KeyboardInterrupt:
            print("\n\n✓ Alert Watcher stopped by user")
        except Exception as e:
            print(f"\n\n✗ Alert Watcher error: {e}")
            raise


if __name__ == '__main__':
    watcher = AlertWatcher()
    watcher.run()
