"""Docker tools — build, run, compose, manage containers/images/volumes/networks.

Full Docker and Docker Compose lifecycle management.
Cross-platform: works wherever Docker CLI is installed.
"""

import os
import shutil
import subprocess
from typing import Any

COMMAND_TIMEOUT = 300  # Builds can be slow


def _run(args: list[str], cwd: str | None = None, timeout: int = COMMAND_TIMEOUT) -> dict[str, Any]:
    """Run a command and return result dict."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1}


def _fmt(r: dict[str, Any]) -> str:
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    elif r["stderr"] and r["exit_code"] == 0:
        # Docker often writes progress to stderr
        parts.append(r["stderr"])
    if r["exit_code"] != 0 and not parts:
        parts.append(f"Exit code: {r['exit_code']}")
    return "\n".join(parts) if parts else "Done."


def docker_tool(action: str, target: str = "", args: str = "", cwd: str | None = None) -> str:
    """Docker and Docker Compose management.

    Args:
        action: One of:
          Containers: run, exec, stop, start, restart, rm, ps, logs, inspect
          Images: build, pull, push, images, rmi, tag
          Compose: compose-up, compose-down, compose-build, compose-logs,
                   compose-ps, compose-restart, compose-exec
          System: info, version, prune, networks, volumes, stats
        target: Container/image name, service name, or Dockerfile path
        args: Additional flags (e.g. "-d -p 8080:80", "--build", "-f docker-compose.prod.yml")
        cwd: Working directory
    """
    if not shutil.which("docker"):
        return "Error: Docker not found. Install from https://docs.docker.com/get-docker/"

    action = action.lower().strip()
    work_dir = cwd or os.getcwd()
    extra = args.split() if args else []

    # --- Container lifecycle ---
    if action == "run":
        if not target:
            return "Error: 'target' (image name) required for run"
        cmd = ["docker", "run"] + extra + [target]
        return _fmt(_run(cmd, work_dir))

    elif action == "exec":
        if not target:
            return "Error: 'target' (container name) required for exec"
        if not args:
            return "Error: 'args' (command to run) required for exec"
        cmd = ["docker", "exec", target] + extra
        return _fmt(_run(cmd, work_dir, timeout=120))

    elif action == "stop":
        if not target:
            return "Error: 'target' (container name/id) required"
        cmd = ["docker", "stop", target]
        return _fmt(_run(cmd, work_dir))

    elif action == "start":
        if not target:
            return "Error: 'target' (container name/id) required"
        cmd = ["docker", "start", target]
        return _fmt(_run(cmd, work_dir))

    elif action == "restart":
        if not target:
            return "Error: 'target' (container name/id) required"
        cmd = ["docker", "restart", target]
        return _fmt(_run(cmd, work_dir))

    elif action == "rm":
        if not target:
            return "Error: 'target' (container name/id) required"
        cmd = ["docker", "rm"] + extra + [target]
        return _fmt(_run(cmd, work_dir))

    elif action == "ps":
        cmd = ["docker", "ps"] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "logs":
        if not target:
            return "Error: 'target' (container name/id) required"
        cmd = ["docker", "logs", "--tail", "100"] + extra + [target]
        return _fmt(_run(cmd, work_dir))

    elif action == "inspect":
        if not target:
            return "Error: 'target' (container/image name) required"
        cmd = ["docker", "inspect", target]
        return _fmt(_run(cmd, work_dir))

    # --- Image management ---
    elif action == "build":
        cmd = ["docker", "build"] + extra
        if target:
            cmd.extend(["-t", target])
        cmd.append(".")
        return _fmt(_run(cmd, work_dir, timeout=600))

    elif action == "pull":
        if not target:
            return "Error: 'target' (image name) required"
        cmd = ["docker", "pull", target]
        return _fmt(_run(cmd, work_dir, timeout=600))

    elif action == "push":
        if not target:
            return "Error: 'target' (image name) required"
        cmd = ["docker", "push", target]
        return _fmt(_run(cmd, work_dir, timeout=600))

    elif action == "images":
        cmd = ["docker", "images"] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "rmi":
        if not target:
            return "Error: 'target' (image name/id) required"
        cmd = ["docker", "rmi"] + extra + [target]
        return _fmt(_run(cmd, work_dir))

    elif action == "tag":
        if not target or not args:
            return "Error: 'target' (source image) and 'args' (new tag) required"
        cmd = ["docker", "tag", target, args]
        return _fmt(_run(cmd, work_dir))

    # --- Docker Compose ---
    elif action == "compose-up":
        cmd = ["docker", "compose"] + _compose_file_args(extra) + ["up", "-d"] + _strip_file_args(extra)
        return _fmt(_run(cmd, work_dir, timeout=600))

    elif action == "compose-down":
        cmd = ["docker", "compose"] + _compose_file_args(extra) + ["down"] + _strip_file_args(extra)
        return _fmt(_run(cmd, work_dir))

    elif action == "compose-build":
        cmd = ["docker", "compose"] + _compose_file_args(extra) + ["build"] + _strip_file_args(extra)
        return _fmt(_run(cmd, work_dir, timeout=600))

    elif action == "compose-logs":
        tail = ["--tail", "100"]
        cmd = ["docker", "compose"] + _compose_file_args(extra) + ["logs"] + tail
        if target:
            cmd.append(target)
        return _fmt(_run(cmd, work_dir))

    elif action == "compose-ps":
        cmd = ["docker", "compose"] + _compose_file_args(extra) + ["ps"]
        return _fmt(_run(cmd, work_dir))

    elif action == "compose-restart":
        cmd = ["docker", "compose"] + _compose_file_args(extra) + ["restart"]
        if target:
            cmd.append(target)
        return _fmt(_run(cmd, work_dir))

    elif action == "compose-exec":
        if not target or not args:
            return "Error: 'target' (service) and 'args' (command) required"
        cmd = ["docker", "compose", "exec", target] + extra
        return _fmt(_run(cmd, work_dir, timeout=120))

    # --- System ---
    elif action == "info":
        return _fmt(_run(["docker", "info"], work_dir))

    elif action == "version":
        r1 = _fmt(_run(["docker", "version"], work_dir))
        # Also check compose
        r2 = _fmt(_run(["docker", "compose", "version"], work_dir))
        return f"{r1}\n\nCompose: {r2}"

    elif action == "prune":
        # Clean up unused resources
        lines = []
        r = _run(["docker", "system", "prune", "-f"], work_dir)
        lines.append("System prune: " + _fmt(r))
        return "\n".join(lines)

    elif action == "networks":
        return _fmt(_run(["docker", "network", "ls"], work_dir))

    elif action == "volumes":
        return _fmt(_run(["docker", "volume", "ls"], work_dir))

    elif action == "stats":
        # One-shot stats (not streaming)
        return _fmt(_run(["docker", "stats", "--no-stream", "--format",
                          "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.PIDs}}"], work_dir))

    else:
        return (
            "Error: Unknown action. Available actions:\n"
            "  Containers: run, exec, stop, start, restart, rm, ps, logs, inspect\n"
            "  Images:     build, pull, push, images, rmi, tag\n"
            "  Compose:    compose-up, compose-down, compose-build, compose-logs,\n"
            "              compose-ps, compose-restart, compose-exec\n"
            "  System:     info, version, prune, networks, volumes, stats"
        )


def _compose_file_args(extra: list[str]) -> list[str]:
    """Extract -f flags for compose file specification."""
    result = []
    i = 0
    while i < len(extra):
        if extra[i] == "-f" and i + 1 < len(extra):
            result.extend(["-f", extra[i + 1]])
            i += 2
        else:
            i += 1
    return result


def _strip_file_args(extra: list[str]) -> list[str]:
    """Remove -f flags from extra args (they go before subcommand)."""
    result = []
    i = 0
    while i < len(extra):
        if extra[i] == "-f" and i + 1 < len(extra):
            i += 2
        else:
            result.append(extra[i])
            i += 1
    return result
