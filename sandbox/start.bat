@echo off
REM ============================================================================
REM PyOz Sandbox — Quick Start (Windows)
REM ============================================================================

echo.
echo   PyOz Enterprise Sandbox — Windows Launcher
echo   ==========================================
echo.

REM Check Docker Desktop is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Check if secrets exist
if not exist "secrets\anthropic_api_key.txt" (
    echo [INFO] First run detected. Setting up secrets...
    echo.
    powershell -ExecutionPolicy Bypass -File "%~dp0setup-secrets.ps1"
    echo.
)

REM Start services
echo Starting sandbox services...
docker compose up -d

echo.
echo Sandbox is starting! Wait a moment for services to initialize.
echo.
echo To enter the agent:
echo   docker exec -it pyoz-agent bash
echo   pyoz
echo.
echo To check health:
echo   powershell -File healthcheck.ps1
echo.
pause
