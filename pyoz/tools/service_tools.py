"""Service management tools — start/stop/restart/list system services.

Windows: PowerShell Get-Service / Start-Service / Stop-Service / sc.exe
Linux: systemctl (systemd)
macOS: launchctl
"""

import os
import shutil
import subprocess
from typing import Any

from pyoz.platform import IS_WINDOWS, IS_MACOS, IS_LINUX


def _run(args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timed out", "exit_code": -1}


def _fmt(r: dict[str, Any]) -> str:
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    if r["exit_code"] != 0 and not parts:
        parts.append(f"Failed (exit code {r['exit_code']})")
    return "\n".join(parts) if parts else "Done."


def service_manager(action: str, name: str = "", args: str = "") -> str:
    """Manage system services.

    Args:
        action: One of: list, status, start, stop, restart, enable, disable, logs, find
        name: Service name (required for start/stop/restart/status/enable/disable/logs)
        args: Extra arguments (e.g. filter for list, lines count for logs)
    """
    action = action.lower().strip()

    if action == "list":
        return _list_services(name)
    elif action == "find":
        if not name:
            return "Error: 'name' (search term) required for find"
        return _find_service(name)
    elif action == "status":
        if not name:
            return "Error: 'name' required for status"
        return _service_status(name)
    elif action == "start":
        if not name:
            return "Error: 'name' required for start"
        return _start_service(name)
    elif action == "stop":
        if not name:
            return "Error: 'name' required for stop"
        return _stop_service(name)
    elif action == "restart":
        if not name:
            return "Error: 'name' required for restart"
        return _restart_service(name)
    elif action == "enable":
        if not name:
            return "Error: 'name' required for enable"
        return _enable_service(name)
    elif action == "disable":
        if not name:
            return "Error: 'name' required for disable"
        return _disable_service(name)
    elif action == "logs":
        if not name:
            return "Error: 'name' required for logs"
        lines = int(args) if args and args.isdigit() else 50
        return _service_logs(name, lines)
    else:
        return "Error: Unknown action. Use: list, find, status, start, stop, restart, enable, disable, logs"


# --- List / Find ---

def _list_services(filter_text: str = "") -> str:
    if IS_WINDOWS:
        cmd = ["powershell", "-NoProfile", "-Command"]
        if filter_text:
            cmd.append(
                f"Get-Service | Where-Object {{ $_.DisplayName -like '*{filter_text}*' -or $_.Name -like '*{filter_text}*' }} | "
                "Select-Object Status, Name, DisplayName | Format-Table -AutoSize"
            )
        else:
            cmd.append(
                "Get-Service | Select-Object Status, Name, DisplayName | Format-Table -AutoSize"
            )
    elif IS_MACOS:
        if filter_text:
            r = _run(["launchctl", "list"])
            if r["stdout"]:
                lines = r["stdout"].splitlines()
                header = lines[0] if lines else ""
                matched = [l for l in lines[1:] if filter_text.lower() in l.lower()]
                return header + "\n" + "\n".join(matched[:50]) if matched else f"No services matching '{filter_text}'"
            return "No services found."
        cmd = ["launchctl", "list"]
    else:  # Linux
        cmd = ["systemctl", "list-units", "--type=service", "--no-pager"]
        if filter_text:
            r = _run(cmd)
            if r["stdout"]:
                lines = r["stdout"].splitlines()
                header = lines[0] if lines else ""
                matched = [l for l in lines[1:] if filter_text.lower() in l.lower()]
                return header + "\n" + "\n".join(matched[:50]) if matched else f"No services matching '{filter_text}'"
            return "No services found."

    r = _run(cmd)
    output = r["stdout"]
    # Truncate long output
    lines = output.splitlines()
    if len(lines) > 60:
        output = "\n".join(lines[:60]) + f"\n... ({len(lines) - 60} more)"
    return output if output else "No services found."


def _find_service(search: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Get-Service -Name '*{search}*' -ErrorAction SilentlyContinue | "
                   "Select-Object Status, Name, DisplayName, StartType | Format-Table -AutoSize"])
    elif IS_MACOS:
        r = _run(["launchctl", "list"])
        if r["stdout"]:
            lines = r["stdout"].splitlines()
            matched = [l for l in lines if search.lower() in l.lower()]
            return "\n".join(matched[:30]) if matched else f"No services matching '{search}'"
        return f"No services matching '{search}'"
    else:
        r = _run(["systemctl", "list-units", "--type=service", "--no-pager", "--all"])
        if r["stdout"]:
            lines = r["stdout"].splitlines()
            header = lines[0] if lines else ""
            matched = [l for l in lines[1:] if search.lower() in l.lower()]
            return header + "\n" + "\n".join(matched[:30]) if matched else f"No services matching '{search}'"
        return f"No services matching '{search}'"

    return _fmt(r) if r["stdout"] else f"No services matching '{search}'"


# --- Status ---

def _service_status(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Get-Service -Name '{name}' -ErrorAction Stop | "
                   "Select-Object Status, Name, DisplayName, StartType, "
                   "@{N='DependsOn';E={($_.ServicesDependedOn | ForEach-Object {{ $_.Name }}) -join ', '}} | "
                   "Format-List"])
    elif IS_MACOS:
        r = _run(["launchctl", "print", f"system/{name}"])
        if r["exit_code"] != 0:
            r = _run(["launchctl", "print", f"gui/{os.getuid()}/{name}"])
    else:
        r = _run(["systemctl", "status", name, "--no-pager"])
    return _fmt(r)


# --- Start / Stop / Restart ---

def _start_service(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command", f"Start-Service -Name '{name}' -ErrorAction Stop"])
    elif IS_MACOS:
        r = _run(["launchctl", "start", name])
    else:
        r = _run(["systemctl", "start", name])
    if r["exit_code"] == 0:
        return f"Service '{name}' started."
    return _fmt(r)


def _stop_service(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command", f"Stop-Service -Name '{name}' -Force -ErrorAction Stop"])
    elif IS_MACOS:
        r = _run(["launchctl", "stop", name])
    else:
        r = _run(["systemctl", "stop", name])
    if r["exit_code"] == 0:
        return f"Service '{name}' stopped."
    return _fmt(r)


def _restart_service(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command", f"Restart-Service -Name '{name}' -Force -ErrorAction Stop"])
    elif IS_MACOS:
        _run(["launchctl", "stop", name])
        r = _run(["launchctl", "start", name])
    else:
        r = _run(["systemctl", "restart", name])
    if r["exit_code"] == 0:
        return f"Service '{name}' restarted."
    return _fmt(r)


# --- Enable / Disable ---

def _enable_service(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Set-Service -Name '{name}' -StartupType Automatic -ErrorAction Stop"])
    elif IS_MACOS:
        r = _run(["launchctl", "enable", f"system/{name}"])
    else:
        r = _run(["systemctl", "enable", name])
    if r["exit_code"] == 0:
        return f"Service '{name}' enabled (auto-start)."
    return _fmt(r)


def _disable_service(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Set-Service -Name '{name}' -StartupType Disabled -ErrorAction Stop"])
    elif IS_MACOS:
        r = _run(["launchctl", "disable", f"system/{name}"])
    else:
        r = _run(["systemctl", "disable", name])
    if r["exit_code"] == 0:
        return f"Service '{name}' disabled."
    return _fmt(r)


# --- Logs ---

def _service_logs(name: str, lines: int = 50) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Get-EventLog -LogName Application -Source '{name}' -Newest {lines} -ErrorAction SilentlyContinue | "
                   "Format-Table -AutoSize TimeGenerated, EntryType, Message -Wrap"])
        if not r["stdout"]:
            # Try Windows Event Log with Get-WinEvent
            r = _run(["powershell", "-NoProfile", "-Command",
                       f"Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='*{name}*'}} "
                       f"-MaxEvents {lines} -ErrorAction SilentlyContinue | "
                       "Format-Table -AutoSize TimeCreated, LevelDisplayName, Message -Wrap"])
    elif IS_MACOS:
        r = _run(["log", "show", "--predicate", f"subsystem == '{name}'", "--last", "1h", "--style", "compact"])
    else:
        r = _run(["journalctl", "-u", name, f"-n{lines}", "--no-pager"])
    return _fmt(r) if r["stdout"] else f"No logs found for service '{name}'"
