"""Command tools — run shell commands safely.

Uses PowerShell on Windows, default shell on Unix.
"""

import os
import re
import subprocess
from typing import Any

from pyoz.platform import (
    IS_WINDOWS,
    HAS_POWERSHELL,
    POWERSHELL_PATH,
    get_blocked_patterns,
)

# Compile blocked patterns for current platform
BLOCKED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in get_blocked_patterns()]

COMMAND_TIMEOUT = 120


def run_command(command: str, cwd: str | None = None) -> dict[str, Any]:
    """Run a shell command via subprocess with safety checks.

    On Windows: uses PowerShell (pwsh) if available, else cmd.exe.
    On Unix: uses the default shell via shell=True.
    """
    for pat in BLOCKED_PATTERNS:
        if pat.search(command):
            raise PermissionError(f"Blocked dangerous command: {command}")

    work_dir = os.path.abspath(cwd) if cwd else os.getcwd()
    if not os.path.isdir(work_dir):
        raise FileNotFoundError(f"Working directory not found: {work_dir}")

    try:
        if IS_WINDOWS and HAS_POWERSHELL:
            # Use PowerShell on Windows
            result = subprocess.run(
                [POWERSHELL_PATH, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
                cwd=work_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        elif IS_WINDOWS:
            # Fallback to cmd.exe on Windows without PowerShell
            result = subprocess.run(
                ["cmd", "/c", command],
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
                cwd=work_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        else:
            # Unix: use shell=True
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
                cwd=work_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {COMMAND_TIMEOUT} seconds",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        }


def get_platform_command(unix_command: str) -> str:
    """Translate a Unix command to the platform-appropriate command.

    On Unix: returns the command as-is.
    On Windows with PowerShell: translates common commands.
    """
    if not IS_WINDOWS:
        return unix_command

    # Common translations for Windows PowerShell
    translations = {
        "ls": "Get-ChildItem",
        "pwd": "Get-Location",
        "cat": "Get-Content",
        "rm": "Remove-Item",
        "cp": "Copy-Item",
        "mv": "Move-Item",
        "mkdir": "New-Item -ItemType Directory -Name",
        "echo": "Write-Output",
        "which": "Get-Command",
        "whoami": "$env:USERNAME",
        "clear": "Clear-Host",
        "grep": "Select-String",
        "find": "Get-ChildItem -Recurse -Filter",
        "head": "Get-Content -TotalCount",
        "tail": "Get-Content -Tail",
        "touch": "New-Item -ItemType File -Name",
        "wc -l": "(Get-Content).Count",
    }

    # Check if command starts with a known Unix command
    parts = unix_command.strip().split(maxsplit=1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    if cmd in translations:
        ps_cmd = translations[cmd]
        return f"{ps_cmd} {args}".strip() if args else ps_cmd

    return unix_command
