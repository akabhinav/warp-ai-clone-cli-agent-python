#!/usr/bin/env bash
# ============================================================================
# PyOz Sandbox — Service Health Check
# Run this script to check the status of all sandbox services.
#
# Usage:
#   docker exec pyoz-agent /opt/pyoz/sandbox/healthcheck.sh
#   # or from host:
#   ./sandbox/healthcheck.sh
# ============================================================================

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

check_tcp() {
    local name="$1"
    local host="$2"
    local port="$3"

    if bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} ${name} — ${host}:${port} ${GREEN}UP${NC}"
        return 0
    else
        echo -e "  ${RED}✗${NC} ${name} — ${host}:${port} ${RED}DOWN${NC}"
        return 1
    fi
}

check_command() {
    local name="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} ${name} — available"
        return 0
    else
        echo -e "  ${RED}✗${NC} ${name} — not found"
        return 1
    fi
}

echo -e "${BOLD}═══ PyOz Sandbox Health Check ═══${NC}"
echo ""

total=0
healthy=0

echo -e "${BOLD}Services:${NC}"
services=(
    "PostgreSQL:${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}"
    "MySQL:${MYSQL_HOST:-mysql}:${MYSQL_PORT:-3306}"
    "MongoDB:${MONGO_HOST:-mongodb}:${MONGO_PORT:-27017}"
    "Redis:${REDIS_HOST:-redis}:${REDIS_PORT:-6379}"
    "Kafka:kafka:9092"
    "RabbitMQ:${RABBITMQ_HOST:-rabbitmq}:${RABBITMQ_PORT:-5672}"
    "Elasticsearch:${ELASTICSEARCH_HOST:-elasticsearch}:${ELASTICSEARCH_PORT:-9200}"
    "MinIO:minio:9000"
)

for svc in "${services[@]}"; do
    IFS=':' read -r name host port <<< "$svc"
    total=$((total + 1))
    if check_tcp "$name" "$host" "$port"; then
        healthy=$((healthy + 1))
    fi
done

echo ""
echo -e "${BOLD}Runtimes:${NC}"
runtimes=(
    "Python:python3:--version"
    "Node.js:node:--version"
    "Java:java:-version"
    "Go:go:version"
    "Rust:rustc:--version"
    ".NET:dotnet:--version"
    "Ruby:ruby:--version"
    "PHP:php:--version"
)

for rt in "${runtimes[@]}"; do
    IFS=':' read -r name cmd flag <<< "$rt"
    check_command "$name" "$cmd" "$flag" || true
done

echo ""
echo -e "${BOLD}CLI Tools:${NC}"
tools=(
    "Git:git:--version"
    "Docker CLI:docker:--version"
    "kubectl:kubectl:version"
    "Helm:helm:version"
    "Terraform:terraform:--version"
    "Maven:mvn:--version"
    "Gradle:gradle:--version"
    "psql:psql:--version"
    "mysql (client):mysql:--version"
    "mongosh:mongosh:--version"
    "redis-cli:redis-cli:--version"
)

for tool in "${tools[@]}"; do
    IFS=':' read -r name cmd flag <<< "$tool"
    check_command "$name" "$cmd" "$flag" || true
done

echo ""
echo -e "${BOLD}Summary:${NC} ${healthy}/${total} services healthy"

if [ $healthy -eq $total ]; then
    echo -e "${GREEN}All services are running!${NC}"
elif [ $healthy -gt 0 ]; then
    echo -e "${YELLOW}Some services are down. Use 'docker compose up -d <service>' to start them.${NC}"
else
    echo -e "${RED}No services are running. Run 'docker compose up -d' from the sandbox directory.${NC}"
fi
