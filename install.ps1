# ──────────────────────────────────────────────────────────────
# PyOz Installer — Windows PowerShell
# Usage:  irm <raw-url>/install.ps1 | iex
#   or:   .\install.ps1
# ──────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$Repo = "https://github.com/akabhinav/warp-ai-clone-cli-agent-python.git"
$InstallDir = if ($env:PYOZ_HOME) { $env:PYOZ_HOME } else { "$env:USERPROFILE\.pyoz" }
$MinPython = [version]"3.11"

function Write-Info  { param($msg) Write-Host "[pyoz] $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "[pyoz] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[pyoz] $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "[pyoz] $msg" -ForegroundColor Red; exit 1 }

# ── Check Python ──────────────────────────────────────────────
$python = $null
foreach ($cmd in @("python", "python3")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -and [version]$ver -ge $MinPython) {
            $python = $cmd
            break
        }
    } catch { }
}
if (-not $python) {
    Write-Err "Python $MinPython+ is required. Download from https://python.org"
}
Write-Info "Using $python ($(& $python --version 2>&1))"

# ── Check git ─────────────────────────────────────────────────
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err "git is required. Download from https://git-scm.com/download/win"
}

# ── Clone or update ───────────────────────────────────────────
if (Test-Path "$InstallDir\.git") {
    Write-Info "Updating existing installation..."
    Push-Location $InstallDir
    git pull --quiet origin main 2>$null
    Pop-Location
} else {
    Write-Info "Cloning PyOz into $InstallDir..."
    git clone --depth 1 $Repo $InstallDir
}

# ── Create venv ───────────────────────────────────────────────
if (-not (Test-Path "$InstallDir\venv")) {
    Write-Info "Creating virtual environment..."
    & $python -m venv "$InstallDir\venv"
}

# ── Install ───────────────────────────────────────────────────
Write-Info "Installing dependencies..."
& "$InstallDir\venv\Scripts\pip.exe" install --quiet --upgrade pip
& "$InstallDir\venv\Scripts\pip.exe" install --quiet -e $InstallDir

# ── Create launcher ───────────────────────────────────────────
$launcher = "$InstallDir\pyoz.cmd"
@"
@echo off
"$InstallDir\venv\Scripts\python.exe" -m pyoz %*
"@ | Set-Content $launcher -Encoding ASCII

# ── Add to PATH ───────────────────────────────────────────────
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$InstallDir*") {
    Write-Warn "Adding $InstallDir to your user PATH..."
    [Environment]::SetEnvironmentVariable("PATH", "$userPath;$InstallDir", "User")
    $env:PATH = "$env:PATH;$InstallDir"
    Write-Ok "Added to PATH. Restart your terminal for changes to take effect."
}

# ── Done ──────────────────────────────────────────────────────
Write-Host ""
Write-Ok "PyOz installed successfully!"
Write-Host ""
Write-Info "Quick start:"
Write-Host "  pyoz --provider claude --api-key YOUR_KEY"
Write-Host "  pyoz --provider openai --api-key YOUR_KEY"
Write-Host "  pyoz --provider ollama --model qwen2.5:7b"
Write-Host "  pyoz --test"
Write-Host ""
Write-Info "Set API key as env var to skip --api-key flag:"
Write-Host '  $env:ANTHROPIC_API_KEY = "sk-ant-..."'
Write-Host '  $env:OPENAI_API_KEY = "sk-..."'
Write-Host ""
