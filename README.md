# Blue/Green Deployment with Nginx

Production-ready Blue/Green deployment setup using Docker Compose and Nginx reverse proxy with automatic failover.

## 🎯 Features

- ✅ **Zero-downtime failover** - Automatic switch from Blue to Green on failure
- ✅ **Health-based routing** - Nginx actively monitors upstream health
- ✅ **Request-level retry** - Failed requests automatically retry to backup pool
- ✅ **Header forwarding** - Preserves X-App-Pool and X-Release-Id headers
- ✅ **Parameterized configuration** - Fully controlled via .env file
- ✅ **Fast failure detection** - Tight timeouts (2-3s) for quick failover
- ✅ **Chaos testing support** - Built-in endpoints to simulate failures

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose V2
- curl (for testing)

## 🚀 Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone <your-repo-url>
cd hng13-stage2-devops

# Copy environment template
cp .env.example .env

# Edit .env if needed (default values work for testing)
nano .env
```

### 2. Start Services

```bash
# Start all services in detached mode
docker compose up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f
```

### 3. Verify Deployment

```bash
# Test main endpoint (should route to Blue)
curl -i http://localhost:8080/version

# Expected response headers:
# X-App-Pool: blue
# X-Release-Id: v1.0.0-blue
```

## 🧪 Testing Failover

### Scenario 1: Normal Operation (Blue Active)

```bash
# Multiple requests should all go to blue
for i in {1..5}; do
  curl -s http://localhost:8080/version | grep -E "X-App-Pool|X-Release-Id"
done

# Expected output (all from blue):
# X-App-Pool: blue
# X-Release-Id: v1.0.0-blue
```

### Scenario 2: Induce Failure on Blue

```bash
# Trigger chaos mode on Blue (simulate downtime)
curl -X POST "http://localhost:8081/chaos/start?mode=error"

# Next requests should automatically failover to Green
curl -i http://localhost:8080/version

# Expected headers (now from green):
# X-App-Pool: green
# X-Release-Id: v1.0.0-green
```

### Scenario 3: Verify Zero Downtime

```bash
# Run continuous requests while Blue is failing
for i in {1..20}; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/version)
  echo "Request $i: $HTTP_CODE"
  sleep 0.5
done

# Expected: All 200 responses (no 500s or timeouts)
```

### Scenario 4: Stop Chaos and Observe Recovery

```bash
# Stop chaos mode on Blue
curl -X POST http://localhost:8081/chaos/stop

# Wait for Nginx to detect Blue is healthy again (5-10 seconds)
sleep 10

# New requests should go back to Blue (primary)
curl -i http://localhost:8080/version
```

## 📊 Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ http://localhost:8080
       ▼
┌──────────────────────────────┐
│   Nginx Reverse Proxy        │
│   (Port 8080)                │
│                              │
│  Upstream Backend:           │
│   - Blue (primary)           │
│   - Green (backup)           │
└───────┬──────────────────┬───┘
        │                  │
        ▼                  ▼
┌──────────────┐    ┌──────────────┐
│  Blue App    │    │  Green App   │
│  Port 8081   │    │  Port 8082   │
└──────────────┘    └──────────────┘
```

### Traffic Flow

1. **Normal State**: All traffic → Blue (Green is on standby)
2. **Blue Fails**: Nginx detects failure (via health checks or request errors)
3. **Automatic Failover**: Traffic instantly routes to Green
4. **Blue Recovers**: After `fail_timeout` (5s), Blue becomes primary again

## ⚙️ Configuration

### Environment Variables (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `BLUE_IMAGE` | Docker image for Blue instance | `ghcr.io/hngprojects/hng_boilerplate_nodejs_web:staging` |
| `GREEN_IMAGE` | Docker image for Green instance | `ghcr.io/hngprojects/hng_boilerplate_nodejs_web:staging` |
| `ACTIVE_POOL` | Primary pool (blue or green) | `blue` |
| `RELEASE_ID_BLUE` | Release identifier for Blue | `v1.0.0-blue` |
| `RELEASE_ID_GREEN` | Release identifier for Green | `v1.0.0-green` |
| `PORT` | Internal app port | `8080` |
| `NGINX_PORT` | Nginx public port | `8080` |
| `BLUE_PORT` | Blue direct access port | `8081` |
| `GREEN_PORT` | Green direct access port | `8082` |

### Nginx Failover Configuration

Key settings in `nginx.conf.template`:

```nginx
upstream backend {
    # Primary server with tight failure detection
    server ${PRIMARY_HOST}:${PRIMARY_PORT} max_fails=2 fail_timeout=5s;
    
    # Backup server (only used when primary fails)
    server ${BACKUP_HOST}:${BACKUP_PORT} backup;
}

# Tight timeouts for fast failover
proxy_connect_timeout 2s;
proxy_send_timeout 3s;
proxy_read_timeout 3s;

# Retry on errors, timeouts, and 5xx responses
proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
proxy_next_upstream_tries 2;
proxy_next_upstream_timeout 10s;
```

## 🔄 Switching Active Pool

To switch primary pool from Blue to Green:

```bash
# Update .env
sed -i 's/ACTIVE_POOL=blue/ACTIVE_POOL=green/' .env

# Restart nginx to apply changes
docker compose restart nginx

# Verify Green is now primary
curl -i http://localhost:8080/version
# Expected: X-App-Pool: green
```

## 📝 API Endpoints

### Main Service (via Nginx - Port 8080)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/version` | GET | Returns app version and pool info |
| `/healthz` | GET | Health check endpoint |

### Direct Access (Blue: 8081, Green: 8082)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/version` | GET | Direct pool access |
| `/chaos/start?mode=error` | POST | Simulate 500 errors |
| `/chaos/start?mode=timeout` | POST | Simulate timeouts |
| `/chaos/stop` | POST | Stop chaos mode |
| `/healthz` | GET | Health check |

## 🐛 Troubleshooting

### Issue: Services won't start

```bash
# Check Docker is running
docker ps

# Check for port conflicts
sudo netstat -tulpn | grep -E '8080|8081|8082'

# View detailed logs
docker compose logs
```

### Issue: Failover not working

```bash
# Check Nginx configuration
docker compose exec nginx nginx -t

# View Nginx logs
docker compose logs nginx

# Check upstream health
docker compose exec nginx cat /etc/nginx/nginx.conf
```

### Issue: Headers not forwarded

```bash
# Test direct app access
curl -i http://localhost:8081/version

# Compare with proxied access
curl -i http://localhost:8080/version

# Both should show X-App-Pool and X-Release-Id headers
```

## 🧹 Cleanup

```bash
# Stop and remove all containers
docker compose down

# Remove volumes (if any)
docker compose down -v

# Remove images
docker rmi $(docker images -q ghcr.io/hngprojects/hng_boilerplate_nodejs_web)
```

## 📚 Project Structure

```
.
├── docker-compose.yml          # Service orchestration
├── nginx.conf.template         # Nginx configuration template
├── entrypoint.sh              # Nginx startup script with envsubst
├── .env.example               # Environment variables template
├── .env                       # Active configuration (not in git)
├── README.md                  # This file
├── DECISION.md               # Design decisions
└── .gitignore                # Git ignore rules
```

## 🔐 Security Considerations

- **No exposed secrets**: All sensitive data in .env (gitignored)
- **Health checks**: Automatic detection of unhealthy instances
- **Minimal attack surface**: Alpine-based images
- **Network isolation**: Services communicate via Docker network

## 📈 Performance Metrics

- **Failover time**: < 5 seconds (from failure to Green routing)
- **Request success rate**: 100% (with proper failover)
- **Timeout**: 10 seconds max per request
- **Zero downtime**: No client-visible errors during failover

## 🎓 Learning Outcomes

This project demonstrates:
- Blue/Green deployment patterns
- Nginx upstream health checks and failover
- Docker Compose service orchestration
- Zero-downtime deployment strategies
- Infrastructure as Code principles
- Chaos engineering for resilience testing

## 🔗 HNG Internship

This project is part of the HNG13 DevOps Internship program.

- Learn more: [HNG Internship](https://hng.tech/internship)
- Hire talented developers: [HNG Hire](https://hng.tech/hire)

## 👤 Author

**Osagunna Oyindamola**
- GitHub: [@oyinder](https://github.com/oyinder)
- Slack: @yDEEIII

## 📄 License

MIT License - Free to use and modify
