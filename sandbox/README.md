# PyOz Enterprise Sandbox

Pre-configured development environment with all enterprise software pre-installed.
Drop in the PyOz agent and build any enterprise system — databases, message queues,
and runtimes are all ready to use.

Works on **Linux**, **macOS**, and **Windows** (via Docker Desktop).

## Quick Start

### Linux / macOS

```bash
cd sandbox

# 1. Setup secrets (prompts for API keys, generates random DB passwords)
./setup-secrets.sh

# 2. Start services
docker compose up -d                     # Standard
docker compose up -d agent postgres redis # Lightweight
docker compose --profile full up -d       # Full enterprise

# 3. Enter the agent
docker exec -it pyoz-agent bash
pyoz

# 4. Ask it to build anything!
> Build an inventory management system with PostgreSQL, Redis caching, and Kafka events
```

### Windows

```powershell
cd sandbox

# Option A: Double-click start.bat (does everything)

# Option B: Manual
.\setup-secrets.ps1                            # Setup secrets
docker compose up -d                           # Start services
docker exec -it pyoz-agent bash                # Enter agent
pyoz                                           # Start PyOz
```

> **Windows Requirements**: [Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)
> with WSL 2 backend enabled (default). No other dependencies needed.

## Security

Credentials are protected at every layer:

| Layer | Protection |
|-------|-----------|
| **Storage** | API keys and passwords stored as files in `secrets/` (chmod 600 / Windows ACL) |
| **Docker** | Mounted via Docker secrets at `/run/secrets/` — never in env vars or `docker inspect` |
| **Agent output** | Passwords masked as `py****` in `environment_discovery()` output |
| **Network** | All ports bound to `127.0.0.1` — not exposed to LAN or internet |
| **Container** | No Docker socket mount, `no-new-privileges`, capabilities dropped |
| **Git** | `secrets/` directory is git-ignored — never committed |

### Setup Secrets

```bash
# Linux/macOS                    # Windows
./setup-secrets.sh               .\setup-secrets.ps1
```

This will:
1. Prompt for your API keys (Anthropic and/or OpenAI)
2. Generate random 32-character passwords for all databases
3. Lock file permissions (chmod 600 / Windows ACL)

## What's Included

### Agent Container (all pre-installed)

| Category | Software |
|----------|----------|
| **Languages** | Python 3.12, Node.js 22, Java 21, Go 1.22, Rust, .NET 8, Ruby, PHP 8.3 |
| **Build Tools** | Maven, Gradle, npm, yarn, pnpm, pip, cargo, composer, gem |
| **DB Clients** | psql, mysql, mongosh, redis-cli, sqlite3 |
| **Infra** | Docker CLI, kubectl, Helm, Terraform |
| **Kafka** | kafka-console-producer, kafka-console-consumer, kafka-topics |
| **Other** | git, curl, wget, jq, yq, vim, nano |

### Service Containers

| Service | Image | Default Port | Profile |
|---------|-------|-------------|---------|
| PostgreSQL 16 | `postgres:16-alpine` | 5432 | default |
| MySQL 8 | `mysql:8.0` | 3306 | default |
| MongoDB 7 | `mongo:7` | 27017 | default |
| Redis 7 | `redis:7-alpine` | 6379 | default |
| Kafka (KRaft) | `apache/kafka:3.7.1` | 9092 | default |
| RabbitMQ 3 | `rabbitmq:3-management-alpine` | 5672, 15672 (UI) | full |
| Elasticsearch 8 | `elasticsearch:8.15.0` | 9200 | full |
| MinIO | `minio/minio:latest` | 9000, 9001 (UI) | full |
| Nginx | `nginx:alpine` | 80, 443 | full |

## How the Agent Knows Credentials

Credentials flow through Docker secrets — never plain text env vars:

```
secrets/db_credentials.json (your machine, chmod 600)
  → Docker mounts at /run/secrets/db_credentials (inside container)
    → Agent reads JSON file internally
      → environment_discovery() returns MASKED output:

{
  "sandbox_services": {
    "postgres": {
      "host": "postgres",
      "port": 5432,
      "user": "pyoz",
      "password": "py****",        ← masked, never shows real password
      "database": "app_db",
      "connection_hint": "Read password from /run/secrets/db_credentials",
      "running": true
    }
  }
}
```

The agent reads credentials from the secrets file internally to connect,
but never exposes raw passwords in output.

## Platform-Specific Notes

### Windows

- **Docker Desktop WSL 2** is required (default on modern Docker Desktop)
- The agent container runs Linux — all runtimes work identically to Linux
- Use PowerShell scripts (`*.ps1`) instead of bash scripts (`*.sh`)
- File permissions use Windows ACLs instead of Unix chmod
- If you see "port already in use", change ports in `.env`:
  ```
  POSTGRES_EXTERNAL_PORT=5433
  MYSQL_EXTERNAL_PORT=3307
  ```

### macOS (Apple Silicon / M1-M4)

- Docker Desktop handles ARM64 translation automatically
- The Dockerfile supports both `amd64` and `arm64` architectures
- Some images (Elasticsearch) may run under Rosetta emulation — slightly slower

### Linux

- Native performance, no emulation overhead
- If using Podman instead of Docker: `alias docker=podman` works for most commands

## Common Operations

```bash
# Health check
# Linux/macOS:
docker exec pyoz-agent /opt/pyoz/sandbox/healthcheck.sh
# Windows:
powershell -File healthcheck.ps1

# View service logs
docker compose logs -f kafka
docker compose logs -f postgres

# Start a specific service
docker compose up -d mongodb

# Stop everything
docker compose --profile full down

# Reset all data (removes volumes)
docker compose --profile full down -v

# Rebuild agent image (after code changes)
docker compose build agent
```

## Resource Requirements

| Profile | RAM | Disk |
|---------|-----|------|
| Lightweight (agent + postgres + redis) | ~1 GB | ~5 GB |
| Standard (+ mysql + mongodb + kafka) | ~4 GB | ~8 GB |
| Full enterprise (+ es + rabbitmq + minio) | ~8 GB | ~10 GB |

**Windows note**: Docker Desktop reserves RAM via WSL 2. Adjust in
Docker Desktop Settings > Resources if needed.

## Customization

- **Ports**: Change external port mappings in `.env` (e.g., `POSTGRES_EXTERNAL_PORT=5433`)
- **Nginx**: Edit `sandbox/nginx.conf` to configure reverse proxy
- **Workspace**: Files in `/workspace` inside the container persist via Docker volume
- **New services**: Add them to `docker-compose.yml` and inject env vars into the agent
