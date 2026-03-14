"""Dotnet CLI tools — build, test, run, create .NET/C# projects.

Wraps the `dotnet` CLI for project creation, building, testing, running,
and package management. Works on Windows, macOS, and Linux.
"""

import os
import shutil
import subprocess
from typing import Any

COMMAND_TIMEOUT = 180  # Builds can take a while


def _run(args: list[str], cwd: str | None = None, timeout: int = COMMAND_TIMEOUT) -> dict[str, Any]:
    """Run a command and return result dict."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
        }
    except FileNotFoundError:
        return {"stdout": "", "stderr": "dotnet CLI not found. Install from https://dot.net", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1}


def _format(r: dict[str, Any]) -> str:
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    if r["exit_code"] != 0:
        parts.append(f"Exit code: {r['exit_code']}")
    return "\n".join(parts) if parts else "Done."


def dotnet_cli(action: str, project_path: str = "", args: str = "", cwd: str | None = None) -> str:
    """Run dotnet CLI actions.

    Args:
        action: One of: new, build, test, run, publish, clean, restore,
                add-package, remove-package, list-packages, info, sdk-list
        project_path: Path to project/solution (optional, uses cwd)
        args: Additional arguments (e.g. template name for 'new', package name for 'add-package')
        cwd: Working directory
    """
    if not shutil.which("dotnet"):
        return "Error: dotnet CLI not found. Install .NET SDK from https://dot.net"

    action = action.lower().strip()
    work_dir = cwd or os.getcwd()

    if action == "new":
        # dotnet new <template> -n <name> -o <path>
        if not args:
            return "Error: Specify template name in 'args' (e.g. 'console', 'webapi', 'classlib', 'blazor')"
        parts = args.split()
        template = parts[0]
        cmd = ["dotnet", "new", template]
        if project_path:
            cmd.extend(["-n", os.path.basename(project_path), "-o", project_path])
        cmd.extend(parts[1:])  # Extra flags
        return _format(_run(cmd, work_dir))

    elif action == "build":
        cmd = ["dotnet", "build"]
        if project_path:
            cmd.append(project_path)
        if args:
            cmd.extend(args.split())
        return _format(_run(cmd, work_dir))

    elif action == "test":
        cmd = ["dotnet", "test"]
        if project_path:
            cmd.append(project_path)
        if args:
            cmd.extend(args.split())
        return _format(_run(cmd, work_dir, timeout=300))

    elif action == "run":
        cmd = ["dotnet", "run"]
        if project_path:
            cmd.extend(["--project", project_path])
        if args:
            cmd.extend(["--", *args.split()])
        return _format(_run(cmd, work_dir))

    elif action == "publish":
        cmd = ["dotnet", "publish"]
        if project_path:
            cmd.append(project_path)
        if args:
            cmd.extend(args.split())
        else:
            cmd.extend(["-c", "Release"])
        return _format(_run(cmd, work_dir))

    elif action == "clean":
        cmd = ["dotnet", "clean"]
        if project_path:
            cmd.append(project_path)
        return _format(_run(cmd, work_dir))

    elif action == "restore":
        cmd = ["dotnet", "restore"]
        if project_path:
            cmd.append(project_path)
        return _format(_run(cmd, work_dir))

    elif action == "add-package":
        if not args:
            return "Error: Specify package name in 'args' (e.g. 'Newtonsoft.Json')"
        cmd = ["dotnet", "add"]
        if project_path:
            cmd.append(project_path)
        cmd.extend(["package", *args.split()])
        return _format(_run(cmd, work_dir))

    elif action == "remove-package":
        if not args:
            return "Error: Specify package name in 'args'"
        cmd = ["dotnet", "remove"]
        if project_path:
            cmd.append(project_path)
        cmd.extend(["package", args.split()[0]])
        return _format(_run(cmd, work_dir))

    elif action == "list-packages":
        cmd = ["dotnet", "list"]
        if project_path:
            cmd.append(project_path)
        cmd.append("package")
        return _format(_run(cmd, work_dir))

    elif action == "info":
        # Show dotnet SDK info
        r1 = _run(["dotnet", "--info"], work_dir)
        return _format(r1)

    elif action == "sdk-list":
        r = _run(["dotnet", "--list-sdks"], work_dir)
        runtimes = _run(["dotnet", "--list-runtimes"], work_dir)
        parts = ["SDKs:", r["stdout"], "", "Runtimes:", runtimes["stdout"]]
        return "\n".join(parts)

    else:
        return (f"Error: Unknown action '{action}'. "
                "Use: new, build, test, run, publish, clean, restore, "
                "add-package, remove-package, list-packages, info, sdk-list")
