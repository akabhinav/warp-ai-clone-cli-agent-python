@echo off
REM ──────────────────────────────────────────────────────────
REM PyOz Installer — Windows
REM Usage:  install.bat
REM ──────────────────────────────────────────────────────────
setlocal enabledelayedexpansion

set "REPO=https://github.com/akabhinav/warp-ai-clone-cli-agent-python.git"
set "INSTALL_DIR=%USERPROFILE%\.pyoz"

echo [pyoz] PyOz Installer for Windows
echo.

REM ── Check Python ────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [pyoz] ERROR: Python 3.11+ is required.
    echo [pyoz] Download from https://python.org
    echo [pyoz] Make sure to check "Add Python to PATH" during install.
    exit /b 1
)

REM Verify Python version
for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYVER=%%v
echo [pyoz] Using Python %PYVER%

REM ── Check git ───────────────────────────────────────────────
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [pyoz] ERROR: git is required.
    echo [pyoz] Download from https://git-scm.com/download/win
    exit /b 1
)

REM ── Clone or update ─────────────────────────────────────────
if exist "%INSTALL_DIR%\.git" (
    echo [pyoz] Updating existing installation...
    cd /d "%INSTALL_DIR%"
    git pull --quiet origin main 2>nul || git pull --quiet
) else (
    echo [pyoz] Cloning PyOz into %INSTALL_DIR%...
    git clone --depth 1 "%REPO%" "%INSTALL_DIR%"
    cd /d "%INSTALL_DIR%"
)

REM ── Create venv ─────────────────────────────────────────────
if not exist "%INSTALL_DIR%\venv" (
    echo [pyoz] Creating virtual environment...
    python -m venv "%INSTALL_DIR%\venv"
)

REM ── Install ─────────────────────────────────────────────────
echo [pyoz] Installing dependencies...
"%INSTALL_DIR%\venv\Scripts\pip.exe" install --quiet --upgrade pip
"%INSTALL_DIR%\venv\Scripts\pip.exe" install --quiet -e "%INSTALL_DIR%"

REM ── Create launcher ─────────────────────────────────────────
set "LAUNCHER=%INSTALL_DIR%\pyoz.cmd"
(
echo @echo off
echo "%INSTALL_DIR%\venv\Scripts\python.exe" -m pyoz %%*
) > "%LAUNCHER%"

REM ── Add to PATH via registry ────────────────────────────────
echo.
echo [pyoz] Installation complete!
echo.

REM Check if INSTALL_DIR is in PATH
echo %PATH% | findstr /i "%INSTALL_DIR%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [pyoz] To use 'pyoz' from anywhere, add to your PATH:
    echo.
    echo   setx PATH "%%PATH%%;%INSTALL_DIR%"
    echo.
    echo   Or run: %LAUNCHER%
)

echo.
echo [pyoz] Quick start:
echo   pyoz --provider claude --api-key YOUR_KEY
echo   pyoz --provider openai --api-key YOUR_KEY
echo   pyoz --provider ollama --model qwen2.5:7b
echo   pyoz --test
echo.
echo [pyoz] Set API key as env var to skip --api-key flag:
echo   setx ANTHROPIC_API_KEY sk-ant-...
echo   setx OPENAI_API_KEY sk-...
echo.

endlocal
