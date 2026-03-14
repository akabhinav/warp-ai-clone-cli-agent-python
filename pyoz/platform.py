"""Platform detection and cross-platform utilities.

Detects Windows/macOS/Linux and provides PowerShell-first command execution on Windows.
"""

import os
import shutil
import sys
from typing import Any


# --- Platform Detection ---

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

PLATFORM_NAME = "windows" if IS_WINDOWS else ("macos" if IS_MACOS else "linux")


def _find_powershell() -> str | None:
    """Find PowerShell executable (pwsh preferred over powershell.exe)."""
    # PowerShell 7+ (cross-platform)
    pwsh = shutil.which("pwsh")
    if pwsh:
        return pwsh
    # Windows PowerShell 5.x
    if IS_WINDOWS:
        ps = shutil.which("powershell")
        if ps:
            return ps
    return None


POWERSHELL_PATH = _find_powershell()
HAS_POWERSHELL = POWERSHELL_PATH is not None


# --- Shell Selection ---

def get_shell_info() -> dict[str, Any]:
    """Return current shell information."""
    if IS_WINDOWS and HAS_POWERSHELL:
        return {
            "shell": "powershell",
            "name": "PowerShell",
            "path": POWERSHELL_PATH,
            "platform": "windows",
        }
    elif IS_WINDOWS:
        return {
            "shell": "cmd",
            "name": "Command Prompt",
            "path": "cmd.exe",
            "platform": "windows",
        }
    else:
        shell = os.environ.get("SHELL", "/bin/sh")
        name = os.path.basename(shell)
        return {
            "shell": name,
            "name": name,
            "path": shell,
            "platform": PLATFORM_NAME,
        }


# --- PowerShell Command Mappings ---
# Maps common Unix commands to their PowerShell equivalents.
# The LLM uses these to generate correct commands on Windows.

POWERSHELL_COMMAND_MAP = {
    # Navigation & File System
    "pwd": "Get-Location",
    "cd": "Set-Location",
    "ls": "Get-ChildItem",
    "find": "Get-ChildItem -Recurse",
    "touch": "New-Item -ItemType File",
    "mkdir": "New-Item -ItemType Directory",
    "cp": "Copy-Item",
    "mv": "Move-Item",
    "rm": "Remove-Item",
    "rmdir": "Remove-Item -Recurse",
    "cat": "Get-Content",
    "head": "Get-Content -TotalCount",
    "tail": "Get-Content -Tail",
    "wc": "Measure-Object",

    # Text & Search
    "grep": "Select-String",
    "sed": "(Get-Content) -replace",
    "awk": "ForEach-Object",
    "sort": "Sort-Object",
    "uniq": "Get-Unique",
    "diff": "Compare-Object",

    # System & Process
    "ps": "Get-Process",
    "kill": "Stop-Process",
    "env": "Get-ChildItem Env:",
    "export": "$env:VAR = 'value'",
    "which": "Get-Command",
    "whoami": "$env:USERNAME",
    "hostname": "$env:COMPUTERNAME",
    "curl": "Invoke-WebRequest",
    "wget": "Invoke-WebRequest -OutFile",

    # Network
    "ping": "Test-Connection",
    "netstat": "Get-NetTCPConnection",
    "ifconfig": "Get-NetIPAddress",
    "nslookup": "Resolve-DnsName",

    # Archive & Compression
    "tar": "Expand-Archive / Compress-Archive",
    "zip": "Compress-Archive",
    "unzip": "Expand-Archive",

    # Permissions & Info
    "chmod": "Set-Acl / icacls",
    "chown": "Set-Acl",
    "stat": "Get-ItemProperty",
    "file": "Get-Item",
    "du": "Get-ChildItem -Recurse | Measure-Object -Property Length -Sum",
    "df": "Get-PSDrive",
}


def get_powershell_equivalent(unix_cmd: str) -> str | None:
    """Get PowerShell equivalent for a Unix command."""
    # Check direct mapping
    cmd_name = unix_cmd.strip().split()[0] if unix_cmd.strip() else ""
    return POWERSHELL_COMMAND_MAP.get(cmd_name)


def get_command_reference() -> str:
    """Return a formatted reference of Unix → PowerShell command mappings."""
    lines = ["Unix Command → PowerShell Equivalent", "=" * 45]
    for unix_cmd, ps_cmd in sorted(POWERSHELL_COMMAND_MAP.items()):
        lines.append(f"  {unix_cmd:<15} → {ps_cmd}")
    return "\n".join(lines)


# --- Path Utilities ---

def normalize_path(path: str) -> str:
    """Normalize a path for the current platform."""
    path = os.path.normpath(path)
    if IS_WINDOWS:
        # Convert forward slashes to backslashes on Windows
        path = path.replace("/", "\\")
    return path


def to_posix_path(path: str) -> str:
    """Convert a path to POSIX format (forward slashes)."""
    return path.replace("\\", "/")


def get_home_dir() -> str:
    """Get user home directory cross-platform."""
    return os.path.expanduser("~")


def get_temp_dir() -> str:
    """Get temp directory cross-platform."""
    import tempfile
    return tempfile.gettempdir()


# --- Shell-Specific Helpers ---

def build_shell_command(command: str) -> list[str]:
    """Build the subprocess args for running a shell command.

    On Windows with PowerShell: uses pwsh/powershell -NoProfile -Command
    On Windows without PowerShell: uses cmd /c
    On Unix: uses the default shell
    """
    if IS_WINDOWS and HAS_POWERSHELL:
        return [POWERSHELL_PATH, "-NoProfile", "-NonInteractive", "-Command", command]
    elif IS_WINDOWS:
        return ["cmd", "/c", command]
    else:
        # On Unix, let subprocess handle it with shell=True
        return command  # type: ignore


def get_env_var_syntax(var_name: str, value: str) -> str:
    """Return the syntax to set an environment variable."""
    if IS_WINDOWS and HAS_POWERSHELL:
        return f'$env:{var_name} = "{value}"'
    elif IS_WINDOWS:
        return f'set {var_name}={value}'
    else:
        return f'export {var_name}="{value}"'


def get_path_separator() -> str:
    """Return the PATH separator for the current platform."""
    return ";" if IS_WINDOWS else ":"


# --- Blocked Commands (Platform-Specific) ---

WINDOWS_BLOCKED_PATTERNS = [
    r"Remove-Item\s+.*-Recurse.*C:\\",
    r"Remove-Item\s+.*C:\\Windows",
    r"Remove-Item\s+.*C:\\Program\s*Files",
    r"Format-Volume",
    r"Clear-Disk",
    r"Stop-Computer\s+-Force",
    r"Restart-Computer\s+-Force",
    r"Remove-Item\s+-Path\s+\$env:SystemRoot",
    r"Remove-Item\s+/\s",
    r"Get-Process\s*\|\s*Stop-Process",  # kill all processes
    r"Stop-Service\s+.*-Force",
    r"Set-ExecutionPolicy\s+Unrestricted.*-Force",
    r"reg\s+delete\s+HKLM",
]

UNIX_BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/\s*$",
    r"\brm\s+-rf\s+/\s",
    r"\brm\s+-rf\s+\*\s*$",
    r"\bmkfs\b",
    r":(){ :\|:& };:",
    r"\bdd\s+.*of=/dev/[sh]d",
]

COMMON_BLOCKED_PATTERNS = [
    r"\bformat\s+[cC]:",
    r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]\s+[cC]:",
]


def get_blocked_patterns() -> list[str]:
    """Return blocked command patterns for the current platform."""
    patterns = list(COMMON_BLOCKED_PATTERNS)
    if IS_WINDOWS:
        patterns.extend(WINDOWS_BLOCKED_PATTERNS)
    else:
        patterns.extend(UNIX_BLOCKED_PATTERNS)
    return patterns
