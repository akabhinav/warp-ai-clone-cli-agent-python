#!/usr/bin/env bash
# ============================================================================
# PyOz Sandbox — Secrets Setup Script
# Creates secret files with secure random passwords.
# Run once before first `docker compose up`.
# ============================================================================

set -e

SECRETS_DIR="$(cd "$(dirname "$0")" && pwd)/secrets"
mkdir -p "$SECRETS_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}PyOz Sandbox — Secrets Setup${NC}"
echo ""

# Generate a random password (32 chars, alphanumeric)
gen_password() {
    head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32
}

# ── API Keys ─────────────────────────────────────────────────

if [ -f "$SECRETS_DIR/anthropic_api_key.txt" ]; then
    echo -e "${YELLOW}Anthropic API key already exists, skipping.${NC}"
else
    read -rp "Enter your Anthropic API key (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        printf '%s' "$api_key" > "$SECRETS_DIR/anthropic_api_key.txt"
        echo -e "${GREEN}Saved Anthropic API key.${NC}"
    else
        touch "$SECRETS_DIR/anthropic_api_key.txt"
        echo -e "${YELLOW}Skipped Anthropic API key (add later to secrets/anthropic_api_key.txt).${NC}"
    fi
fi

if [ -f "$SECRETS_DIR/openai_api_key.txt" ]; then
    echo -e "${YELLOW}OpenAI API key already exists, skipping.${NC}"
else
    read -rp "Enter your OpenAI API key (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        printf '%s' "$api_key" > "$SECRETS_DIR/openai_api_key.txt"
        echo -e "${GREEN}Saved OpenAI API key.${NC}"
    else
        touch "$SECRETS_DIR/openai_api_key.txt"
        echo -e "${YELLOW}Skipped OpenAI API key.${NC}"
    fi
fi

# ── Database Credentials ─────────────────────────────────────

if [ -f "$SECRETS_DIR/db_credentials.json" ]; then
    echo -e "${YELLOW}Database credentials already exist, skipping.${NC}"
else
    PG_PASS=$(gen_password)
    MYSQL_PASS=$(gen_password)
    MYSQL_ROOT_PASS=$(gen_password)
    MONGO_PASS=$(gen_password)
    RABBIT_PASS=$(gen_password)
    MINIO_SECRET=$(gen_password)

    cat > "$SECRETS_DIR/db_credentials.json" << ENDOFJSON
{
  "postgres_user": "pyoz",
  "postgres_password": "$PG_PASS",
  "mysql_user": "pyoz",
  "mysql_password": "$MYSQL_PASS",
  "mysql_root_password": "$MYSQL_ROOT_PASS",
  "mongo_user": "pyoz",
  "mongo_password": "$MONGO_PASS",
  "redis_password": "",
  "rabbitmq_user": "pyoz",
  "rabbitmq_password": "$RABBIT_PASS",
  "minio_access_key": "pyoz",
  "minio_secret_key": "$MINIO_SECRET"
}
ENDOFJSON

    echo -e "${GREEN}Generated random database passwords.${NC}"
fi

# ── Lock down file permissions ───────────────────────────────

chmod 600 "$SECRETS_DIR"/*.txt "$SECRETS_DIR"/*.json 2>/dev/null || true

echo ""
echo -e "${BOLD}Secrets stored in:${NC} $SECRETS_DIR"
echo -e "${CYAN}File permissions set to 600 (owner read/write only).${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  cd sandbox"
echo "  docker compose up -d"
echo "  docker exec -it pyoz-agent pyoz"
