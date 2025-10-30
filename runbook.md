# Blue/Green Deployment Monitoring Runbook

This runbook provides operational guidance for responding to alerts from the Blue/Green deployment monitoring system.

## Alert Types

### 🔄 Failover Detected

**What it means:**
- Traffic has automatically switched from one pool to another (Blue→Green or Green→Blue)
- The previous primary pool likely became unhealthy or unresponsive
- The backup pool is now serving all traffic

**Severity:** ⚠️ WARNING - Immediate attention required

**Operator Actions:**

1. **Verify Current System Status** (within 2 minutes)
   ```bash
   docker-compose ps
   docker inspect app_blue --format='{{.State.Health.Status}}'
   docker inspect app_green --format='{{.State.Health.Status}}'
   ```

2. **Check Failed Pool Logs**
   ```bash
   # If Blue failed:
   docker-compose logs --tail=50 app_blue
   
   # If Green failed:
   docker-compose logs --tail=50 app_green
   ```

3. **Verify Traffic is Flowing**
   ```bash
   curl -I http://localhost:8080/
   # Should show X-App-Pool header with current active pool
   ```

4. **Restart Failed Pool (if safe)**
   ```bash
   docker-compose restart app_blue  # or app_green
   sleep 20  # Wait for health check
   docker-compose ps
   ```

5. **Monitor Recovery**
   ```bash
   docker-compose logs -f alert_watcher
   ```

---

### ⚠️ High Error Rate Detected

**What it means:**
- Upstream services are returning HTTP 5xx errors above the configured threshold
- Current error rate has exceeded the acceptable limit (default: 2%)
- May indicate application issues, resource exhaustion, or misconfigurations

**Severity:** 🚨 CRITICAL - Immediate action required

**Operator Actions:**

1. **Check Current Error Rate** (within 1 minute)
   ```bash
   docker-compose logs --tail=100 alert_watcher
   docker exec nginx tail -100 /var/log/nginx/error.log
   ```

2. **Identify Error Pattern**
   ```bash
   # Check for 5xx errors
   docker exec nginx grep "status=50" /var/log/nginx/access.log | tail -20
   ```

3. **Check Upstream Health**
   ```bash
   curl http://localhost:8081/healthz  # Blue
   curl http://localhost:8082/healthz  # Green
   ```

4. **Determine Root Cause**
   
   **502 Bad Gateway:** Upstream crashed or not responding
   ```bash
   docker-compose logs --tail=100 app_blue app_green
   ```

   **503 Service Unavailable:** Both pools failing health checks
   ```bash
   docker stats
   ```

   **504 Gateway Timeout:** Upstream slow or hanging
   ```bash
   docker exec nginx grep "request_time=[5-9]" /var/log/nginx/access.log
   ```

5. **Toggle to Healthy Pool**
   ```bash
   nano .env  # Change ACTIVE_POOL
   docker-compose restart nginx
   ```

6. **Restart Unhealthy Containers**
   ```bash
   docker-compose restart app_blue app_green
   sleep 30
   docker-compose ps
   ```

---

## Maintenance Mode

Use maintenance mode to suppress alerts during planned operations.

### Enable Maintenance Mode

```bash
nano .env
# Set: MAINTENANCE_MODE=true

docker-compose restart alert_watcher
```

**When to use:**
- Planned pool switches
- Scheduled maintenance windows
- Load testing / chaos engineering
- System upgrades

### Disable Maintenance Mode

```bash
nano .env
# Set: MAINTENANCE_MODE=false

docker-compose restart alert_watcher
```

⚠️ **Important:** Always remember to disable maintenance mode after operations complete!

---

## Common Scenarios

### Scenario 1: Planned Blue→Green Switch

```bash
# 1. Enable maintenance mode
nano .env  # MAINTENANCE_MODE=true
docker-compose restart alert_watcher

# 2. Switch active pool
nano .env  # ACTIVE_POOL=green
docker-compose restart nginx

# 3. Verify switch
curl -I http://localhost:8080/

# 4. Disable maintenance mode
nano .env  # MAINTENANCE_MODE=false
docker-compose restart alert_watcher
```

### Scenario 2: Emergency Rollback

```bash
# Quick rollback
nano .env  # Change ACTIVE_POOL to previous value
docker-compose restart nginx

# Verify rollback
curl -I http://localhost:8080/
```

### Scenario 3: Both Pools Failing

```bash
# Restart all services
docker-compose restart app_blue app_green nginx

# If still failing
docker-compose down
docker-compose up -d

# Check resources
free -h
df -h
docker system df
```

---

## Troubleshooting

### Alerts Not Appearing in Slack

```bash
# 1. Verify webhook URL
grep SLACK_WEBHOOK_URL .env

# 2. Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test"}' \
  YOUR_WEBHOOK_URL

# 3. Check watcher logs
docker-compose logs alert_watcher | grep -i slack

# 4. Restart watcher
docker-compose restart alert_watcher
```

### No Failover Detected During Testing

```bash
# 1. Generate traffic BEFORE stopping container
for i in {1..10}; do curl http://localhost:8080/; done

# 2. Stop pool
docker-compose stop app_blue

# 3. Generate traffic AFTER stopping
for i in {1..10}; do curl http://localhost:8080/; done

# 4. Check watcher logs
docker-compose logs alert_watcher | grep -i failover
```

---

## Monitoring Commands

### Real-time Monitoring

```bash
# Watch all logs
docker-compose logs -f

# Watch watcher only
docker-compose logs -f alert_watcher

# Watch nginx access logs
docker exec nginx tail -f /var/log/nginx/access.log

# Watch container health
watch docker-compose ps
```

### Health Check Commands

```bash
# Test all endpoints
curl http://localhost:8080/healthz  # nginx
curl http://localhost:8081/healthz  # blue
curl http://localhost:8082/healthz  # green

# Check which pool is active
curl -I http://localhost:8080/ | grep X-App-Pool
```

---

## Emergency Contacts

**On-Call Engineers:**
- Primary: [Your Name] - [Contact Info]
- Secondary: [Backup Name] - [Contact Info]

**Escalation Path:**
1. DevOps Team Lead
2. Infrastructure Manager
3. CTO

---

## Quick Reference

### Key Files
- `docker-compose.yml` - Service definitions
- `.env` - Configuration variables
- `nginx.conf.template` - Nginx config
- `watcher.py` - Alert logic

### Key Commands
```bash
# View status
docker-compose ps

# View logs
docker-compose logs -f alert_watcher

# Restart service
docker-compose restart [service_name]

# Switch pool
nano .env  # Edit ACTIVE_POOL
docker-compose restart nginx

# Enable maintenance mode
nano .env  # Set MAINTENANCE_MODE=true
docker-compose restart alert_watcher
```

---

**Last Updated:** 2025-10-30
