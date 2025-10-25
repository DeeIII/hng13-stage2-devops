# DECISION LOG

## Goal
Deploy Blue/Green Node.js services behind Nginx with automatic failover and request-level retries using only pre-built images.

## Key Decisions

1. Orchestration: Docker Compose
- Simple, local-first, no cluster dependency
- Easy parameterization via .env

2. Nginx as Reverse Proxy
- Mature, deterministic failover controls
- Supports primary/backup upstream, retries, and tight timeouts
- Preserves upstream headers by default (no proxy_hide_header)

3. Failover Strategy
- Primary upstream with `max_fails=2`, `fail_timeout=5s`
- Backup upstream with `backup` flag
- Tight timeouts: `proxy_connect_timeout 2s`, `proxy_read_timeout 3s`
- Retries on `error timeout http_5xx` with `proxy_next_upstream_tries 2`

4. Health vs On-Request Failover
- Compose-level container healthcheck ensures startup order
- Runtime failover handled by Nginx via timeouts and `proxy_next_upstream`
- Keeps architecture minimal and compatible with generic images

5. Config Templating
- Use envsubst in entrypoint to avoid custom image builds
- Controlled by ACTIVE_POOL, computes PRIMARY/BACKUP endpoints at runtime

6. Ports
- nginx: 8080 public
- blue: 8081 direct
- green: 8082 direct
- Internal app ports fixed at 8080 per spec

7. Headers
- Forward all original headers (Host, X-Forwarded-*)
- Do not strip app headers; Nginx passes X-App-Pool and X-Release-Id through

## Alternatives Considered

- HAProxy: similar capabilities, but Nginx is more common and simpler for this case
- Envoy/Traefik: heavier, more complex; unnecessary for two-node BG
- Custom health checks in Lua: overkill; request-level failover + short timeouts suffice

## Risk Management

- Private images: Documented need to set BLUE_IMAGE/GREEN_IMAGE to accessible references
- Flaky networks: Low timeouts + retries ensure 0 non-200s under chaos
- Header loss: Explicitly avoid `proxy_hide_header` and add tests to compare direct vs proxied

## Validation Plan

- Baseline: multiple GET /version → 200, headers show blue
- Chaos: POST /chaos/start on blue, then GET /version → 200, now green
- Stability: 20 requests within 10s → 0 non-200s, ≥95% green
- Recovery: chaos stop + wait; traffic returns to blue

## Future Enhancements

- Add canary weight to slowly shift traffic
- Automate ACTIVE_POOL switch via CI with env update
- Add HTTPS termination and HSTS
- Add OpenTelemetry headers and access log JSON