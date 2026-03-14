#!/usr/bin/env bash
# ============================================================================
# PyOz Sandbox Entrypoint
# Waits for services, prints connection summary, starts shell or pyoz.
# ============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║       PyOz Enterprise Sandbox                ║"
echo "  ║       All services pre-configured            ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Wait for critical services ───────────────────────────────

wait_for_service() {
    local name="$1"
    local host="$2"
    local port="$3"
    local max_retries="${4:-30}"
    local retry=0

    while [ $retry -lt $max_retries ]; do
        if bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $name ($host:$port) — ready"
            return 0
        fi
        retry=$((retry + 1))
        sleep 1
    done
    echo -e "  ${YELLOW}⚠${NC} $name ($host:$port) — not available (may not be started)"
    return 1
}

echo -e "${BOLD}Checking services...${NC}"
echo ""

# Always check core services
wait_for_service "PostgreSQL" "${POSTGRES_HOST:-postgres}" "${POSTGRES_PORT:-5432}" 30 || true
wait_for_service "Redis"      "${REDIS_HOST:-redis}"       "${REDIS_PORT:-6379}"    15 || true

# Check optional services (only if env vars hint they should exist)
[ -n "$MYSQL_HOST" ]         && wait_for_service "MySQL"          "$MYSQL_HOST"         "${MYSQL_PORT:-3306}"  30 || true
[ -n "$MONGO_HOST" ]         && wait_for_service "MongoDB"        "$MONGO_HOST"         "${MONGO_PORT:-27017}" 30 || true
[ -n "$KAFKA_BOOTSTRAP_SERVERS" ] && wait_for_service "Kafka"     "kafka"               "9092"                 30 || true
[ -n "$RABBITMQ_HOST" ]      && wait_for_service "RabbitMQ"       "$RABBITMQ_HOST"      "${RABBITMQ_PORT:-5672}" 20 || true
[ -n "$ELASTICSEARCH_HOST" ] && wait_for_service "Elasticsearch"  "$ELASTICSEARCH_HOST" "${ELASTICSEARCH_PORT:-9200}" 30 || true
[ -n "$MINIO_ENDPOINT" ]     && wait_for_service "MinIO"          "minio"               "9000"                 15 || true

echo ""

# ── Print connection summary ─────────────────────────────────

echo -e "${BOLD}Connection credentials:${NC}"
echo -e "  ${CYAN}PostgreSQL${NC}  postgresql://${POSTGRES_USER:-pyoz}:****@${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-app_db}"
echo -e "  ${CYAN}MySQL${NC}       mysql://${MYSQL_USER:-pyoz}:****@${MYSQL_HOST:-mysql}:${MYSQL_PORT:-3306}/${MYSQL_DATABASE:-app_db}"
echo -e "  ${CYAN}MongoDB${NC}     mongodb://${MONGO_USER:-pyoz}:****@${MONGO_HOST:-mongodb}:${MONGO_PORT:-27017}/${MONGO_DB:-app_db}"
echo -e "  ${CYAN}Redis${NC}       redis://${REDIS_HOST:-redis}:${REDIS_PORT:-6379}"
echo -e "  ${CYAN}Kafka${NC}       ${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
echo ""

# ── Print available runtimes ─────────────────────────────────

echo -e "${BOLD}Installed runtimes:${NC}"
python3 --version  2>/dev/null && echo -e "  ${GREEN}✓${NC} Python:  $(python3 --version 2>&1 | head -1)" || true
node --version     2>/dev/null && echo -e "  ${GREEN}✓${NC} Node.js: $(node --version 2>&1)" || true
java -version      2>/dev/null && echo -e "  ${GREEN}✓${NC} Java:    $(java -version 2>&1 | head -1)" || true
go version         2>/dev/null && echo -e "  ${GREEN}✓${NC} Go:      $(go version 2>&1)" || true
rustc --version    2>/dev/null && echo -e "  ${GREEN}✓${NC} Rust:    $(rustc --version 2>&1)" || true
dotnet --version   2>/dev/null && echo -e "  ${GREEN}✓${NC} .NET:    $(dotnet --version 2>&1)" || true
ruby --version     2>/dev/null && echo -e "  ${GREEN}✓${NC} Ruby:    $(ruby --version 2>&1 | head -1)" || true
php --version      2>/dev/null && echo -e "  ${GREEN}✓${NC} PHP:     $(php --version 2>&1 | head -1)" || true
echo ""

# ── Check API key ────────────────────────────────────────────

if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠  No LLM API key set. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to .env${NC}"
    echo ""
fi

echo -e "${BOLD}Ready! Run ${GREEN}pyoz${NC}${BOLD} to start the agent.${NC}"
echo ""

# ── Start command ────────────────────────────────────────────
exec "$@"
