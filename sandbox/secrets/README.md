# Secrets Directory

This directory holds sensitive credentials as files. Docker mounts them
into containers at `/run/secrets/<name>` — they never appear in env vars,
`docker inspect`, or container logs.

## Setup

Run the setup script (recommended):
```bash
cd sandbox
./setup-secrets.sh
```

Or create manually:
```bash
# API Keys — put your actual key (no quotes, no newline)
echo -n "sk-ant-your-key-here" > secrets/anthropic_api_key.txt
echo -n "sk-your-openai-key"   > secrets/openai_api_key.txt

# Database credentials (JSON format)
cat > secrets/db_credentials.json << 'EOF'
{
  "postgres_user": "pyoz",
  "postgres_password": "CHANGE_ME_strong_password_here",
  "mysql_user": "pyoz",
  "mysql_password": "CHANGE_ME_strong_password_here",
  "mysql_root_password": "CHANGE_ME_root_password_here",
  "mongo_user": "pyoz",
  "mongo_password": "CHANGE_ME_strong_password_here",
  "redis_password": "",
  "rabbitmq_user": "pyoz",
  "rabbitmq_password": "CHANGE_ME_strong_password_here",
  "minio_access_key": "pyoz",
  "minio_secret_key": "CHANGE_ME_minio_secret_here"
}
EOF
```

## Security

- Files in this directory are git-ignored (see `.gitignore`)
- Set file permissions: `chmod 600 secrets/*`
- Never commit these files
- The agent reads credentials from `/run/secrets/` inside the container
- Passwords are masked (shown as `****`) in `environment_discovery()` output
