# Backend.im CLI Deployment Infrastructure Research
## DevOps Research Task - HNG Stage 2 Part B

**Author:** Osagunna Oyindamola (@yDEEIII)  
**Date:** October 2025  
**Objective:** Design infrastructure enabling developers to deploy backend code directly via Claude Code CLI

---

## Executive Summary

This document proposes a **lightweight, open-source architecture** that enables developers to push and deploy backend code to Backend.im directly through Claude Code CLI and other AI tools with minimal configuration.

### Key Requirements
- ✅ **One-command deployment** from local to production
- ✅ **AI tool integration** (Claude Code CLI, GitHub Copilot, etc.)
- ✅ **Minimal setup** (< 5 minutes for first-time users)
- ✅ **Cost-efficient** (open-source tools, pay-as-you-go infrastructure)
- ✅ **Secure** (authentication, secrets management, RBAC)

---

## 1. Proposed Architecture

### 1.1 High-Level Overview

```
┌──────────────────────────────────────────────────────────────┐
│              Developer's Local Machine                        │
│                                                               │
│  ┌────────────────┐          ┌──────────────────┐           │
│  │  Claude Code   │──────────│   backend-cli    │           │
│  │     CLI        │   uses   │  (thin wrapper)  │           │
│  └────────────────┘          └─────────┬────────┘           │
│                                         │                     │
└─────────────────────────────────────────┼─────────────────────┘
                                          │ HTTPS/SSH
                                          │ (authenticated)
                                          ▼
┌──────────────────────────────────────────────────────────────┐
│                     Backend.im Platform                       │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           API Gateway (Kong/nginx)                      │ │
│  │  - Authentication (JWT/API Keys)                        │ │
│  │  - Rate limiting                                        │ │
│  │  - Request routing                                      │ │
│  └──────────────────┬─────────────────────────────────────┘ │
│                     │                                         │
│  ┌──────────────────▼─────────────────────────────────────┐ │
│  │           Build & Deploy Service                        │ │
│  │  (Tekton Pipelines / Argo Workflows)                   │ │
│  │  - Git clone                                            │ │
│  │  - Build container                                      │ │
│  │  - Run tests                                            │ │
│  │  - Deploy to runtime                                    │ │
│  └──────────────────┬─────────────────────────────────────┘ │
│                     │                                         │
│  ┌──────────────────▼─────────────────────────────────────┐ │
│  │     Container Registry (Harbor/Docker Registry)         │ │
│  │  - Store built images                                   │ │
│  │  - Vulnerability scanning                               │ │
│  └──────────────────┬─────────────────────────────────────┘ │
│                     │                                         │
│  ┌──────────────────▼─────────────────────────────────────┐ │
│  │        Container Orchestration (K3s/K8s)                │ │
│  │  - Deploy containers                                    │ │
│  │  - Auto-scaling                                         │ │
│  │  - Health checks                                        │ │
│  │  - Load balancing                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Public URL    │
                    │  (Ingress)     │
                    └────────────────┘
```

### 1.2 Component Breakdown

| Component | Tool/Technology | Purpose | Why This Choice |
|-----------|----------------|---------|-----------------|
| **CLI Tool** | Python (Typer/Click) | Local command wrapper | Lightweight, easy to install via pip |
| **API Gateway** | Kong (open-source) | Authentication, routing | Battle-tested, plugin ecosystem |
| **CI/CD Engine** | Tekton Pipelines | Build & deploy automation | Cloud-native, Kubernetes-native |
| **Container Registry** | Harbor | Image storage | Open-source, built-in scanning |
| **Orchestrator** | K3s | Container runtime | Lightweight K8s, perfect for edge |
| **Ingress** | Traefik | Traffic routing | Auto SSL, dynamic config |
| **Secret Management** | Vault | API keys, tokens | Industry standard, auditable |
| **Storage** | MinIO | Object storage for artifacts | S3-compatible, self-hosted |

---

## 2. Detailed Architecture

### 2.1 Local Developer Setup

#### Installation (< 2 minutes)

```bash
# Install CLI
pip install backend-cli

# Initialize project
backend-cli init

# Authenticate
backend-cli login
# Opens browser → OAuth flow → stores token locally
```

#### Project Structure

```
my-app/
├── backend.yml          # Platform config
├── Dockerfile           # (optional) Auto-generated if missing
├── src/
│   ├── index.js
│   └── ...
└── tests/
```

#### backend.yml Example

```yaml
name: my-app
runtime: node:20           # or python:3.12, go:1.21, etc.
entrypoint: npm start
env:
  - DATABASE_URL=secret:db_url
  - API_KEY=secret:api_key
resources:
  memory: 512Mi
  cpu: 0.5
scaling:
  min: 1
  max: 5
```

### 2.2 CLI Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Developer runs: backend-cli deploy                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. CLI reads backend.yml                                     │
│ 2. Validates configuration                                   │
│ 3. Compresses source code (excluding .gitignore patterns)   │
│ 4. Generates deployment manifest                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Sends HTTPS POST to Backend.im API                       │
│    - Endpoint: https://api.backend.im/v1/deployments        │
│    - Headers: Authorization: Bearer <token>                 │
│    - Payload: {source: base64, config: backend.yml}        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. API Gateway (Kong) validates JWT                         │
│ 7. Routes to Build Service                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. Build Service (Tekton Pipeline):                         │
│    a. Extract source to workspace                           │
│    b. Generate Dockerfile if missing                        │
│    c. docker build -t user/app:v<timestamp>                 │
│    d. Push to Harbor registry                               │
│    e. Generate K8s manifests (Deployment, Service, Ingress) │
│    f. kubectl apply -f manifests/                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│ 9. K3s deploys container                                    │
│ 10. Traefik creates route: my-app.backend.im               │
│ 11. Sends webhook back to CLI with deployment URL          │
└──────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│ CLI output:                                                  │
│ ✓ Build completed in 45s                                    │
│ ✓ Deployed to https://my-app.backend.im                    │
│ ✓ Health check passed                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack Rationale

### 3.1 Frontend (CLI)

**Choice: Python with Typer**

```python
# Example CLI implementation
import typer
import requests
from pathlib import Path

app = typer.Typer()

@app.command()
def deploy(
    config: Path = typer.Option("backend.yml"),
    watch: bool = typer.Option(False, "--watch", "-w")
):
    """Deploy application to Backend.im"""
    
    # 1. Read config
    cfg = load_config(config)
    
    # 2. Compress source
    source_tar = compress_source(exclude_patterns=[".git", "node_modules"])
    
    # 3. Send to API
    response = requests.post(
        "https://api.backend.im/v1/deployments",
        headers={"Authorization": f"Bearer {get_token()}"},
        files={"source": source_tar},
        json={"config": cfg}
    )
    
    # 4. Stream logs if --watch
    if watch:
        stream_logs(response.json()["deployment_id"])
```

**Why Python?**
- Easy to install: `pip install backend-cli`
- Rich ecosystem: `requests`, `typer`, `rich` for beautiful CLI
- Cross-platform
- AI tools already understand Python syntax well

### 3.2 API Gateway

**Choice: Kong (open-source)**

**Why Kong?**
- JWT authentication built-in
- Rate limiting per user
- Extensive plugin ecosystem (logging, monitoring)
- OpenAPI spec support for AI tool integration
- Free for self-hosted deployments

**Configuration Example:**

```yaml
# kong.yml
services:
  - name: deployment-service
    url: http://build-service:8080
    routes:
      - name: deploy-route
        paths:
          - /v1/deployments
    plugins:
      - name: jwt
      - name: rate-limiting
        config:
          minute: 10
          policy: local
```

### 3.3 Build & Deploy Engine

**Choice: Tekton Pipelines**

**Why Tekton?**
- Open-source, CNCF project
- Kubernetes-native (runs as pods)
- Declarative pipelines (GitOps-friendly)
- Reusable tasks from Tekton Hub

**Pipeline Example:**

```yaml
# tekton-pipeline.yml
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: backend-deploy
spec:
  params:
    - name: app-name
    - name: source-url
  workspaces:
    - name: source-code
  tasks:
    # Task 1: Extract source
    - name: extract-source
      taskRef:
        name: untar-source
      workspaces:
        - name: output
          workspace: source-code
    
    # Task 2: Build container
    - name: build-image
      taskRef:
        name: buildah        # Open-source Docker alternative
      params:
        - name: IMAGE
          value: "harbor.backend.im/$(params.app-name):$(tasks.extract-source.results.version)"
      workspaces:
        - name: source
          workspace: source-code
    
    # Task 3: Deploy to K8s
    - name: deploy-app
      taskRef:
        name: kubectl-deploy
      params:
        - name: image
          value: $(tasks.build-image.results.IMAGE_URL)
```

### 3.4 Container Orchestration

**Choice: K3s (lightweight Kubernetes)**

**Why K3s?**
- Full K8s experience with 1/10th the resource usage
- Single binary installation
- Perfect for Backend.im's multi-tenant model
- Native support for:
  - Auto-scaling (HPA)
  - Rolling updates
  - Health checks
  - Network policies (tenant isolation)

**Deployment Manifest (auto-generated):**

```yaml
# Generated from backend.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: user-abc123
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: app
        image: harbor.backend.im/user-abc123/my-app:v20251025-142030
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: my-app-secrets
              key: db_url
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: my-app
spec:
  selector:
    app: my-app
  ports:
  - port: 80
    targetPort: 8080
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  rules:
  - host: my-app-user-abc123.backend.im
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-app
            port:
              number: 80
  tls:
  - hosts:
    - my-app-user-abc123.backend.im
    secretName: my-app-tls
```

---

## 4. Security Architecture

### 4.1 Authentication Flow

```
┌────────────────────────┐
│ backend-cli login      │
└───────────┬────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│ Opens browser:                          │
│ https://auth.backend.im/oauth/authorize │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│ User logs in (GitHub/Google OAuth)     │
│ Grants permissions to CLI               │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│ Redirect: http://localhost:5555/callback│
│ With: ?code=xyz123                      │
└───────────┬─────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────┐
│ CLI exchanges code for JWT token        │
│ Stores in: ~/.backend-cli/token         │
│ (Encrypted with OS keychain)            │
└─────────────────────────────────────────┘
```

### 4.2 Secrets Management

**Tool: HashiCorp Vault (open-source)**

```bash
# CLI automatically manages secrets
backend-cli secret set DATABASE_URL postgresql://...
backend-cli secret set API_KEY sk_live_...

# Secrets stored in Vault, injected at runtime
# Never in code, never in logs
```

**Vault Integration:**

```yaml
# K8s ServiceAccount with Vault authentication
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  annotations:
    vault.hashicorp.com/role: "my-app-role"
---
# Secrets injected as env vars
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/agent-inject-secret-db: "secret/data/my-app/db"
```

---

## 5. AI Tool Integration

### 5.1 Claude Code CLI Integration

**Approach: OpenAPI Spec + Natural Language Wrapper**

```yaml
# openapi.yml (Backend.im API)
openapi: 3.0.0
info:
  title: Backend.im Deployment API
  version: 1.0.0
paths:
  /v1/deployments:
    post:
      summary: Deploy application
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                source:
                  type: string
                  format: binary
                config:
                  type: object
      responses:
        '202':
          description: Deployment accepted
```

**Claude can now understand:**

```
User: "Deploy my Node.js app to Backend.im"

Claude interprets:
1. Look for backend.yml or create one
2. Run: backend-cli deploy
3. Monitor deployment status
4. Report URL when ready
```

### 5.2 GitHub Copilot Integration

**Copilot can suggest:**

```javascript
// In VS Code, user types: "deploy"
// Copilot suggests:

// Deploy to Backend.im
// Run: backend-cli deploy --watch

// Or directly in code:
const { exec } = require('child_process');
exec('backend-cli deploy', (error, stdout) => {
  if (error) throw error;
  console.log(`Deployed: ${stdout}`);
});
```

---

## 6. Cost Analysis

### 6.1 Infrastructure Costs (for 100 users, 500 deployments/month)

| Component | Tool | Monthly Cost |
|-----------|------|--------------|
| **Compute** | Hetzner Cloud (4 vCPU, 16GB) | $25 |
| **Storage** | MinIO (100GB) | $5 |
| **Bandwidth** | 5TB egress | $10 |
| **Domain** | backend.im | $1/month |
| **Total** | | **$41/month** |

**Scaling to 1000 users:**
- Add 2 more nodes: $50/month
- Total: **~$100/month**

### 6.2 Open-Source Savings

| If using managed services | Cost |
|---------------------------|------|
| Heroku/Render (1000 apps) | $7000/month |
| AWS ECS + ALB | $500/month |
| **Our approach** | **$100/month** |

**Savings: 98%**

---

## 7. Implementation Roadmap

### Phase 1: MVP (Week 1-2)
- [ ] CLI tool with basic `deploy` command
- [ ] Simple API endpoint (FastAPI)
- [ ] Docker build + run locally
- [ ] Static subdomain assignment

### Phase 2: Cloud Integration (Week 3-4)
- [ ] Deploy to K3s cluster
- [ ] Add Tekton pipelines
- [ ] Implement JWT authentication
- [ ] Add Harbor registry

### Phase 3: Production (Week 5-6)
- [ ] Add Vault for secrets
- [ ] Implement auto-scaling
- [ ] Add monitoring (Grafana/Prometheus)
- [ ] Create user documentation

### Phase 4: AI Enhancement (Week 7-8)
- [ ] Publish OpenAPI spec
- [ ] Create Claude MCP server
- [ ] Add natural language commands
- [ ] GitHub Copilot snippets

---

## 8. Custom Code Requirements

### 8.1 CLI Tool (Python)

```python
# backend_cli/main.py
import typer
from rich.console import Console
from pathlib import Path

app = typer.Typer()
console = Console()

@app.command()
def deploy():
    """Deploy application to Backend.im"""
    with console.status("[bold green]Deploying..."):
        # Read backend.yml
        config = load_config("backend.yml")
        
        # Compress source
        tar_path = create_tarball(exclude=[".git", "node_modules"])
        
        # Upload to API
        response = api_client.deploy(tar_path, config)
        
        # Stream logs
        for log in response.stream_logs():
            console.log(log)
        
        console.print(f"[green]✓[/green] Deployed to {response.url}")

if __name__ == "__main__":
    app()
```

**Lines of Code:** ~500

### 8.2 API Service (FastAPI)

```python
# backend_api/main.py
from fastapi import FastAPI, UploadFile, BackgroundTasks
from kubernetes import client, config

app = FastAPI()

@app.post("/v1/deployments")
async def create_deployment(
    source: UploadFile,
    background_tasks: BackgroundTasks
):
    # 1. Save source to workspace
    workspace = extract_tarball(source)
    
    # 2. Trigger build pipeline
    pipeline_id = tekton_client.create_pipeline_run(
        pipeline="backend-deploy",
        params={"workspace": workspace}
    )
    
    # 3. Return immediately, continue in background
    background_tasks.add_task(monitor_pipeline, pipeline_id)
    
    return {"deployment_id": pipeline_id, "status": "building"}
```

**Lines of Code:** ~800

### 8.3 Tekton Tasks (YAML)

Pre-built tasks from Tekton Hub:
- `git-clone` (official)
- `buildah` (official)
- `kubernetes-actions` (official)

**Custom YAML:** ~300 lines

---

## 9. Monitoring & Observability

### 9.1 Stack

- **Prometheus**: Metrics collection
- **Grafana**: Dashboards
- **Loki**: Log aggregation
- **Jaeger**: Distributed tracing

### 9.2 Key Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Deployment success rate | >95% | <90% |
| Average build time | <2 min | >5 min |
| API response time (p95) | <500ms | >2s |
| Container startup time | <10s | >30s |

---

## 10. Alternatives Considered

### 10.1 Managed PaaS

**Pros:**
- Zero infrastructure management
- Built-in monitoring

**Cons:**
- High cost ($7-25 per app/month)
- Vendor lock-in
- Limited customization

**Verdict:** Not suitable for cost-conscious platform

### 10.2 Serverless (AWS Lambda, Cloud Run)

**Pros:**
- Pay-per-request
- Auto-scaling

**Cons:**
- Cold start latency
- Vendor lock-in
- Not suitable for stateful backends
- Complex for long-running processes

**Verdict:** Good for specific use cases, not general backend hosting

### 10.3 VM-based (Ansible + systemd)

**Pros:**
- Simple
- No container overhead

**Cons:**
- Manual scaling
- No isolation between tenants
- Slow deployments
- Difficult to manage at scale

**Verdict:** Not scalable for multi-tenant platform

---

## 11. Conclusion

### Summary

This architecture provides:

✅ **Developer Experience:** One command (`backend-cli deploy`) from code to production  
✅ **Cost Efficiency:** $100/month for 1000 users (vs $7000 on Heroku)  
✅ **Open Source:** 100% OSS stack, no vendor lock-in  
✅ **AI-Friendly:** OpenAPI spec + natural language wrappers  
✅ **Secure:** JWT auth, Vault secrets, K8s network policies  
✅ **Scalable:** Horizontal scaling with K3s + auto-scaling

### Total Effort Estimate

- **Infrastructure Setup:** 2 weeks
- **CLI Development:** 1 week
- **API Service:** 1 week
- **Testing & Documentation:** 1 week

**Total: 5 weeks for MVP**

### Next Steps

1. Provision K3s cluster (Hetzner/DigitalOcean)
2. Deploy core services (Kong, Tekton, Harbor)
3. Build MVP CLI
4. Alpha test with 10 developers
5. Iterate based on feedback

---

## 12. References

- [Tekton Pipelines](https://tekton.dev/)
- [K3s Documentation](https://k3s.io/)
- [Kong Gateway](https://konghq.com/products/kong-gateway)
- [Harbor Registry](https://goharbor.io/)
- [Claude MCP Protocol](https://modelcontextprotocol.io/)
- [Typer CLI Framework](https://typer.tiangolo.com/)

---

**Author:** Osagunna Oyindamola  
**Contact:** @yDEEIII (Slack)  
**Repository:** https://github.com/DeeIII/hng13-stage2-devops