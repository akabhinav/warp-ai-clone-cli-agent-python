# ============================================================================
# PyOz Sandbox — Service Health Check (Windows PowerShell)
#
# Usage: .\healthcheck.ps1
#   or:  docker exec pyoz-agent /opt/pyoz/sandbox/healthcheck.sh
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"

function Test-TcpPort {
    param([string]$Host_, [int]$Port, [int]$Timeout = 3000)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $result = $client.BeginConnect($Host_, $Port, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne($Timeout)
        $client.Close()
        return $success
    } catch {
        return $false
    }
}

Write-Host "`n=== PyOz Sandbox Health Check ===" -ForegroundColor Cyan
Write-Host ""

# ── Check services via localhost (exposed ports) ─────────────
Write-Host "Services (via localhost):" -ForegroundColor White

$services = @(
    @{ Name = "PostgreSQL";    Host = "127.0.0.1"; Port = 5432 },
    @{ Name = "MySQL";         Host = "127.0.0.1"; Port = 3306 },
    @{ Name = "MongoDB";       Host = "127.0.0.1"; Port = 27017 },
    @{ Name = "Redis";         Host = "127.0.0.1"; Port = 6379 },
    @{ Name = "Kafka";         Host = "127.0.0.1"; Port = 9092 },
    @{ Name = "RabbitMQ";      Host = "127.0.0.1"; Port = 5672 },
    @{ Name = "RabbitMQ UI";   Host = "127.0.0.1"; Port = 15672 },
    @{ Name = "Elasticsearch"; Host = "127.0.0.1"; Port = 9200 },
    @{ Name = "MinIO";         Host = "127.0.0.1"; Port = 9000 },
    @{ Name = "MinIO Console"; Host = "127.0.0.1"; Port = 9001 },
    @{ Name = "Nginx";         Host = "127.0.0.1"; Port = 80 }
)

$total = 0
$healthy = 0

foreach ($svc in $services) {
    $total++
    if (Test-TcpPort -Host_ $svc.Host -Port $svc.Port) {
        Write-Host "  [OK] $($svc.Name) — $($svc.Host):$($svc.Port)" -ForegroundColor Green
        $healthy++
    } else {
        Write-Host "  [--] $($svc.Name) — $($svc.Host):$($svc.Port) (not running)" -ForegroundColor DarkGray
    }
}

# ── Check Docker containers ──────────────────────────────────
Write-Host ""
Write-Host "Docker containers:" -ForegroundColor White

$containers = docker ps --filter "name=pyoz-" --format "{{.Names}}`t{{.Status}}" 2>$null
if ($containers) {
    foreach ($line in $containers -split "`n") {
        if ($line) {
            $parts = $line -split "`t"
            $name = $parts[0]
            $status = $parts[1]
            if ($status -match "Up") {
                Write-Host "  [OK] $name — $status" -ForegroundColor Green
            } else {
                Write-Host "  [!!] $name — $status" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "  No pyoz containers running." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Summary: $healthy/$total services reachable" -ForegroundColor Cyan

if ($healthy -eq $total) {
    Write-Host "All services are running!" -ForegroundColor Green
} elseif ($healthy -gt 0) {
    Write-Host "Some services are down. Use 'docker compose up -d <service>' to start." -ForegroundColor Yellow
} else {
    Write-Host "No services running. Run 'docker compose up -d' from the sandbox directory." -ForegroundColor Red
}
Write-Host ""
