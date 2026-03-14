"""Process manager tools — list, kill, find by port, monitor.

Cross-platform: uses Python's psutil-free approach via /proc (Linux),
subprocess calls (Windows PowerShell / macOS), and os module.
"""

import os
import subprocess
from typing import Any

from pyoz.platform import IS_WINDOWS, IS_MACOS, IS_LINUX


def _run(args: list[str], timeout: int = 30) -> dict[str, Any]:
    """Run a command and return result."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timed out", "exit_code": -1}


def process_manager(action: str, pid: int = 0, name: str = "", port: int = 0) -> str:
    """Manage system processes.

    Args:
        action: One of: list, find, kill, ports, port-find, tree
        pid: Process ID (for kill)
        name: Process name filter (for find)
        port: Port number (for port-find)
    """
    action = action.lower().strip()

    if action == "list":
        return _list_processes(name)

    elif action == "find":
        if not name:
            return "Error: 'name' required for find"
        return _find_processes(name)

    elif action == "kill":
        if not pid:
            return "Error: 'pid' required for kill"
        return _kill_process(pid)

    elif action == "ports":
        return _list_listening_ports()

    elif action == "port-find":
        if not port:
            return "Error: 'port' required for port-find"
        return _find_process_by_port(port)

    elif action == "tree":
        return _process_tree(pid)

    else:
        return "Error: Unknown action. Use: list, find, kill, ports, port-find, tree"


def _list_processes(name_filter: str = "") -> str:
    """List running processes."""
    if IS_WINDOWS:
        cmd = ["powershell", "-NoProfile", "-Command",
               "Get-Process | Select-Object Id, ProcessName, CPU, "
               "@{N='Mem(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
               "Format-Table -AutoSize"]
        if name_filter:
            cmd = ["powershell", "-NoProfile", "-Command",
                   f"Get-Process -Name '*{name_filter}*' -ErrorAction SilentlyContinue | "
                   "Select-Object Id, ProcessName, CPU, "
                   "@{N='Mem(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
                   "Format-Table -AutoSize"]
    elif IS_MACOS:
        if name_filter:
            cmd = ["ps", "aux"]
        else:
            cmd = ["ps", "aux", "--sort=-%mem"]
    else:  # Linux
        if name_filter:
            cmd = ["ps", "aux", "--sort=-%mem"]
        else:
            cmd = ["ps", "aux", "--sort=-%mem"]

    r = _run(cmd)
    output = r["stdout"]

    # Filter on Unix
    if not IS_WINDOWS and name_filter and output:
        lines = output.splitlines()
        header = lines[0] if lines else ""
        filtered = [l for l in lines[1:] if name_filter.lower() in l.lower()]
        if filtered:
            output = header + "\n" + "\n".join(filtered[:50])
        else:
            output = f"No processes matching '{name_filter}'"

    # Truncate to top 50
    lines = output.splitlines()
    if len(lines) > 51:
        output = "\n".join(lines[:51]) + f"\n... ({len(lines) - 51} more)"

    return output if output else "No processes found."


def _find_processes(name: str) -> str:
    """Find processes by name."""
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Get-Process -Name '*{name}*' -ErrorAction SilentlyContinue | "
                   "Select-Object Id, ProcessName, CPU, "
                   "@{N='Mem(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}}, Path | "
                   "Format-Table -AutoSize"])
    else:
        r = _run(["pgrep", "-la", name])

    if not r["stdout"]:
        return f"No processes found matching '{name}'"
    return r["stdout"]


def _kill_process(pid: int) -> str:
    """Kill a process by PID."""
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Stop-Process -Id {pid} -Force -ErrorAction Stop"])
    else:
        r = _run(["kill", "-9", str(pid)])

    if r["exit_code"] == 0:
        return f"Process {pid} killed."
    return f"Failed to kill process {pid}: {r['stderr']}"


def _list_listening_ports() -> str:
    """List all listening ports and their processes."""
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
                   "Select-Object LocalPort, OwningProcess, "
                   "@{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName}} | "
                   "Sort-Object LocalPort | Format-Table -AutoSize"])
    elif IS_MACOS:
        r = _run(["lsof", "-i", "-P", "-n"])
        if r["stdout"]:
            lines = r["stdout"].splitlines()
            header = lines[0] if lines else ""
            listening = [l for l in lines[1:] if "LISTEN" in l]
            if listening:
                r["stdout"] = header + "\n" + "\n".join(listening)
            else:
                r["stdout"] = "No listening ports found."
    else:  # Linux
        r = _run(["ss", "-tlnp"])

    return r["stdout"] if r["stdout"] else "No listening ports found."


def _find_process_by_port(port: int) -> str:
    """Find which process is using a specific port."""
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"$conn = Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue; "
                   f"if ($conn) {{ $conn | ForEach-Object {{ "
                   f"$p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; "
                   f"\"Port {port} → PID $($_.OwningProcess) ($($p.ProcessName)) State: $($_.State)\" }} }} "
                   f"else {{ \"No process found on port {port}\" }}"])
    elif IS_MACOS:
        r = _run(["lsof", "-i", f":{port}", "-P", "-n"])
    else:  # Linux
        r = _run(["ss", "-tlnp", f"sport = :{port}"])

    output = r["stdout"]
    if not output or "No process" in output:
        return f"No process found on port {port}"
    return output


def _process_tree(pid: int = 0) -> str:
    """Show process tree."""
    if IS_WINDOWS:
        if pid:
            r = _run(["powershell", "-NoProfile", "-Command",
                       f"Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {pid} -or $_.ProcessId -eq {pid} }} | "
                       "Select-Object ProcessId, ParentProcessId, Name | Format-Table -AutoSize"])
        else:
            r = _run(["powershell", "-NoProfile", "-Command",
                       "Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 Id, ProcessName, CPU, "
                       "@{N='Mem(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}} | Format-Table -AutoSize"])
    else:
        if pid:
            r = _run(["ps", "--forest", "-p", str(pid)])
        else:
            r = _run(["ps", "auxf", "--sort=-%cpu"])
            if r["stdout"]:
                lines = r["stdout"].splitlines()
                r["stdout"] = "\n".join(lines[:30])

    return r["stdout"] if r["stdout"] else "No process tree available."
