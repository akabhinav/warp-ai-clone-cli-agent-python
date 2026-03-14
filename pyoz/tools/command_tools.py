"""Command tools — run shell commands safely."""

import os
import subprocess
import re
from typing import Any

BLOCKED_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/\s*$"),
    re.compile(r"\bformat\s+[cC]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]\s+[cC]:", re.IGNORECASE),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\brm\s+-rf\s+/\s"),
    re.compile(r"\brm\s+-rf\s+\*\s*$"),
    re.compile(r":(){ :\|:& };:"),
    re.compile(r"\bdd\s+.*of=/dev/[sh]d"),
]

COMMAND_TIMEOUT = 120


def run_command(command: str, cwd: str | None = None) -> dict[str, Any]:
    """Run shell command via subprocess with safety checks."""
    for pat in BLOCKED_PATTERNS:
        if pat.search(command):
            raise PermissionError(f"Blocked dangerous command: {command}")

    work_dir = os.path.abspath(cwd) if cwd else os.getcwd()
    if not os.path.isdir(work_dir):
        raise FileNotFoundError(f"Working directory not found: {work_dir}")

    is_windows = os.name == "nt"
    try:
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
