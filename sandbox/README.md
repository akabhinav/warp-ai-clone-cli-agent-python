# PyOz Enterprise Sandbox

Pre-configured development environment with all enterprise software pre-installed.
Drop in the PyOz agent and build any enterprise system — databases, message queues,
and runtimes are all ready to use.

## Quick Start

```bash
# 1. Configure API keys
cd sandbox
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY or OPENAI_API_KEY

# 2. Start services (pick a profile)

# Lightweight — just agent + PostgreSQL + Redis
docker compose up -d agent postgres redis

# Standard — add MySQL, MongoDB, Kafka
docker compose up -d

# Full enterprise — add RabbitMQ, Elasticsearch, MinIO, Nginx
docker compose --profile full up -d

# 3. Enter the agent
docker exec -it pyoz-agent bash

# 4. Start PyOz
pyoz

# 5. Ask it to build anything!
> Build an inventory management system with PostgreSQL, Redis caching, and Kafka events
```

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

All service credentials are injected as environment variables into the agent container.
When the agent runs `environment_discovery("all")`, it sees:

```json
{
  "sandbox_services": {
    "postgres": {
      "host": "postgres",
      "port": 5432,
      "user": "pyoz",
      "password": "pyoz_secret",
      "database": "app_db",
      "running": true
    },
    "redis": {
      "host": "redis",
      "port": 6379,
      "running": true
    },
    "kafka": {
      "host": "kafka",
      "port": 9092,
      "bootstrap_servers": "kafka:9092",
      "running": true
    }
  }
}
```

The agent reads env vars and generates code with correct connection strings automatically.

## Default Credentials

| Service | Username | Password | Database |
|---------|----------|----------|----------|
| PostgreSQL | `pyoz` | `pyoz_secret` | `app_db` |
| MySQL | `pyoz` | `pyoz_secret` | `app_db` |
| MongoDB | `pyoz` | `pyoz_secret` | `app_db` |
| Redis | *(none)* | *(none)* | — |
| RabbitMQ | `pyoz` | `pyoz_secret` | — |
| MinIO | `pyoz` | `pyoz_secret_key` | — |

Change these in `.env` before starting services.

## Common Operations

```bash
# Health check
docker exec pyoz-agent /opt/pyoz/sandbox/healthcheck.sh

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

# Scale (if needed)
docker compose up -d --scale kafka=3
```

## Resource Requirements

| Profile | RAM | Disk |
|---------|-----|------|
| Lightweight (agent + postgres + redis) | ~1 GB | ~5 GB |
| Standard (+ mysql + mongodb + kafka) | ~4 GB | ~8 GB |
| Full enterprise (+ es + rabbitmq + minio) | ~8 GB | ~10 GB |

## Customization

- **Ports**: Change external port mappings in `.env` (e.g., `POSTGRES_EXTERNAL_PORT=5433`)
- **Nginx**: Edit `sandbox/nginx.conf` to configure reverse proxy
- **Workspace**: Files in `/workspace` inside the container persist via Docker volume
- **New services**: Add them to `docker-compose.yml` and inject env vars into the agent
