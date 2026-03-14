# ============================================================================
# PyOz Sandbox — Secrets Setup Script (Windows PowerShell)
# Creates secret files with secure random passwords.
# Run once before first `docker compose up`.
#
# Usage: .\setup-secrets.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

$SecretsDir = Join-Path $PSScriptRoot "secrets"
New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null

Write-Host "`nPyOz Sandbox — Secrets Setup" -ForegroundColor Cyan
Write-Host ""

# Generate a random password (32 chars, alphanumeric)
function New-RandomPassword {
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    -join (1..32 | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
}

# ── API Keys ─────────────────────────────────────────────────

$AnthropicFile = Join-Path $SecretsDir "anthropic_api_key.txt"
if (Test-Path $AnthropicFile) {
    Write-Host "Anthropic API key already exists, skipping." -ForegroundColor Yellow
} else {
    $apiKey = Read-Host "Enter your Anthropic API key (or press Enter to skip)"
    if ($apiKey) {
        [System.IO.File]::WriteAllText($AnthropicFile, $apiKey)
        Write-Host "Saved Anthropic API key." -ForegroundColor Green
    } else {
        New-Item -ItemType File -Force -Path $AnthropicFile | Out-Null
        Write-Host "Skipped Anthropic API key (add later to secrets\anthropic_api_key.txt)." -ForegroundColor Yellow
    }
}

$OpenAIFile = Join-Path $SecretsDir "openai_api_key.txt"
if (Test-Path $OpenAIFile) {
    Write-Host "OpenAI API key already exists, skipping." -ForegroundColor Yellow
} else {
    $apiKey = Read-Host "Enter your OpenAI API key (or press Enter to skip)"
    if ($apiKey) {
        [System.IO.File]::WriteAllText($OpenAIFile, $apiKey)
        Write-Host "Saved OpenAI API key." -ForegroundColor Green
    } else {
        New-Item -ItemType File -Force -Path $OpenAIFile | Out-Null
        Write-Host "Skipped OpenAI API key." -ForegroundColor Yellow
    }
}

# ── Database Credentials ─────────────────────────────────────

$CredsFile = Join-Path $SecretsDir "db_credentials.json"
if (Test-Path $CredsFile) {
    Write-Host "Database credentials already exist, skipping." -ForegroundColor Yellow
} else {
    $creds = @{
        postgres_user       = "pyoz"
        postgres_password   = New-RandomPassword
        mysql_user          = "pyoz"
        mysql_password      = New-RandomPassword
        mysql_root_password = New-RandomPassword
        mongo_user          = "pyoz"
        mongo_password      = New-RandomPassword
        redis_password      = ""
        rabbitmq_user       = "pyoz"
        rabbitmq_password   = New-RandomPassword
        minio_access_key    = "pyoz"
        minio_secret_key    = New-RandomPassword
    }

    $creds | ConvertTo-Json -Depth 2 | Set-Content -Path $CredsFile -Encoding UTF8 -NoNewline
    Write-Host "Generated random database passwords." -ForegroundColor Green
}

# ── Lock down file permissions (Windows ACL) ─────────────────
# Remove inherited permissions and restrict to current user only

$secretFiles = Get-ChildItem $SecretsDir -File | Where-Object { $_.Extension -in ".txt", ".json" }
foreach ($file in $secretFiles) {
    try {
        $acl = Get-Acl $file.FullName
        $acl.SetAccessRuleProtection($true, $false)  # Disable inheritance, remove inherited rules
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $currentUser, "FullControl", "Allow"
        )
        $acl.SetAccessRule($rule)
        Set-Acl -Path $file.FullName -AclObject $acl
    } catch {
        Write-Host "Warning: Could not set permissions on $($file.Name)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Secrets stored in: $SecretsDir" -ForegroundColor Cyan
Write-Host "File permissions restricted to current user only." -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  cd sandbox"
Write-Host "  docker compose up -d"
Write-Host "  docker exec -it pyoz-agent pyoz"
