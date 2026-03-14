"""Package manager tools — install, search, list packages cross-platform.

Windows: winget, choco, scoop
macOS: brew
Linux: apt, dnf, pacman
All platforms: pip, npm, cargo, go install
"""

import os
import shutil
import subprocess
from typing import Any

from pyoz.platform import IS_WINDOWS, IS_MACOS, IS_LINUX

COMMAND_TIMEOUT = 120


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
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1}


def _detect_package_managers() -> list[dict[str, str]]:
    """Detect available package managers on this system."""
    managers = []

    # System package managers
    checks = [
        ("winget", "winget", "Windows Package Manager"),
        ("choco", "choco", "Chocolatey"),
        ("scoop", "scoop", "Scoop"),
        ("brew", "brew", "Homebrew"),
        ("apt", "apt", "APT (Debian/Ubuntu)"),
        ("dnf", "dnf", "DNF (Fedora/RHEL)"),
        ("pacman", "pacman", "Pacman (Arch)"),
        ("apk", "apk", "APK (Alpine)"),
    ]

    for cmd, exe, name in checks:
        if shutil.which(exe):
            managers.append({"id": cmd, "name": name, "path": shutil.which(exe)})

    # Dev package managers (always check these)
    dev_checks = [
        ("pip", "pip3" if not IS_WINDOWS else "pip", "Python pip"),
        ("npm", "npm", "Node.js npm"),
        ("cargo", "cargo", "Rust Cargo"),
        ("go", "go", "Go modules"),
        ("dotnet", "dotnet", ".NET NuGet"),
        ("composer", "composer", "PHP Composer"),
        ("gem", "gem", "Ruby Gems"),
    ]

    for cmd, exe, name in dev_checks:
        path = shutil.which(exe)
        if path:
            managers.append({"id": cmd, "name": name, "path": path})

    return managers


def package_manager(action: str, package: str = "", manager: str = "") -> str:
    """Manage packages: install, uninstall, search, list, update.

    Args:
        action: One of: install, uninstall, search, list, update, info, managers
        package: Package name (required for install/uninstall/search/info)
        manager: Package manager to use (auto-detected if empty)
    """
    action = action.lower().strip()

    if action == "managers":
        available = _detect_package_managers()
        if not available:
            return "No package managers found on this system."
        lines = ["Available package managers:"]
        for m in available:
            lines.append(f"  {m['id']:<12} {m['name']:<25} ({m['path']})")
        return "\n".join(lines)

    # Auto-detect manager if not specified
    if not manager:
        manager = _auto_select_manager(action)
        if not manager:
            return ("No suitable package manager found. "
                    "Use action='managers' to see what's available, "
                    "or specify manager= explicitly.")

    manager = manager.lower().strip()

    # Validate
    if action in ("install", "uninstall", "search", "info") and not package:
        return f"Error: 'package' is required for action '{action}'"

    # Route to the right handler
    handlers = {
        "winget": _winget,
        "choco": _choco,
        "scoop": _scoop,
        "brew": _brew,
        "apt": _apt,
        "dnf": _dnf,
        "pacman": _pacman,
        "pip": _pip,
        "npm": _npm,
        "cargo": _cargo,
        "go": _go,
        "dotnet": _dotnet_nuget,
    }

    handler = handlers.get(manager)
    if not handler:
        return f"Error: Unknown package manager '{manager}'. Use action='managers' to list available."

    if not shutil.which(manager if manager != "dotnet" else "dotnet"):
        # pip might be pip3
        if manager == "pip" and shutil.which("pip3"):
            pass
        else:
            return f"Error: '{manager}' is not installed on this system."

    return handler(action, package)


def _auto_select_manager(action: str) -> str:
    """Auto-select the best package manager for the current platform."""
    if IS_WINDOWS:
        for m in ["winget", "choco", "scoop"]:
            if shutil.which(m):
                return m
    elif IS_MACOS:
        if shutil.which("brew"):
            return "brew"
    else:  # Linux
        for m in ["apt", "dnf", "pacman", "apk"]:
            if shutil.which(m):
                return m
    # Fallback to dev managers
    if shutil.which("pip3") or shutil.which("pip"):
        return "pip"
    return ""


# --- Windows Package Managers ---

def _winget(action: str, package: str) -> str:
    if action == "install":
        r = _run(["winget", "install", "--accept-package-agreements", "--accept-source-agreements", "-e", package])
    elif action == "uninstall":
        r = _run(["winget", "uninstall", "-e", package])
    elif action == "search":
        r = _run(["winget", "search", package])
    elif action == "list":
        r = _run(["winget", "list"])
    elif action == "update":
        r = _run(["winget", "upgrade", "--all"] if not package else ["winget", "upgrade", "-e", package])
    elif action == "info":
        r = _run(["winget", "show", "-e", package])
    else:
        return f"Error: winget does not support action '{action}'"
    return _format_result(r)


def _choco(action: str, package: str) -> str:
    if action == "install":
        r = _run(["choco", "install", package, "-y"])
    elif action == "uninstall":
        r = _run(["choco", "uninstall", package, "-y"])
    elif action == "search":
        r = _run(["choco", "search", package])
    elif action == "list":
        r = _run(["choco", "list", "--local-only"])
    elif action == "update":
        r = _run(["choco", "upgrade", "all" if not package else package, "-y"])
    elif action == "info":
        r = _run(["choco", "info", package])
    else:
        return f"Error: choco does not support action '{action}'"
    return _format_result(r)


def _scoop(action: str, package: str) -> str:
    if action == "install":
        r = _run(["scoop", "install", package])
    elif action == "uninstall":
        r = _run(["scoop", "uninstall", package])
    elif action == "search":
        r = _run(["scoop", "search", package])
    elif action == "list":
        r = _run(["scoop", "list"])
    elif action == "update":
        r = _run(["scoop", "update"] if not package else ["scoop", "update", package])
    elif action == "info":
        r = _run(["scoop", "info", package])
    else:
        return f"Error: scoop does not support action '{action}'"
    return _format_result(r)


# --- macOS/Linux Package Managers ---

def _brew(action: str, package: str) -> str:
    if action == "install":
        r = _run(["brew", "install", package])
    elif action == "uninstall":
        r = _run(["brew", "uninstall", package])
    elif action == "search":
        r = _run(["brew", "search", package])
    elif action == "list":
        r = _run(["brew", "list"])
    elif action == "update":
        r = _run(["brew", "upgrade"] if not package else ["brew", "upgrade", package])
    elif action == "info":
        r = _run(["brew", "info", package])
    else:
        return f"Error: brew does not support action '{action}'"
    return _format_result(r)


def _apt(action: str, package: str) -> str:
    if action == "install":
        r = _run(["apt", "install", "-y", package], timeout=300)
    elif action == "uninstall":
        r = _run(["apt", "remove", "-y", package])
    elif action == "search":
        r = _run(["apt", "search", package])
    elif action == "list":
        r = _run(["apt", "list", "--installed"], timeout=60)
    elif action == "update":
        r = _run(["apt", "update"], timeout=300)
    elif action == "info":
        r = _run(["apt", "show", package])
    else:
        return f"Error: apt does not support action '{action}'"
    return _format_result(r)


def _dnf(action: str, package: str) -> str:
    if action == "install":
        r = _run(["dnf", "install", "-y", package], timeout=300)
    elif action == "uninstall":
        r = _run(["dnf", "remove", "-y", package])
    elif action == "search":
        r = _run(["dnf", "search", package])
    elif action == "list":
        r = _run(["dnf", "list", "installed"])
    elif action == "update":
        r = _run(["dnf", "upgrade", "-y"], timeout=300)
    elif action == "info":
        r = _run(["dnf", "info", package])
    else:
        return f"Error: dnf does not support action '{action}'"
    return _format_result(r)


def _pacman(action: str, package: str) -> str:
    if action == "install":
        r = _run(["pacman", "-S", "--noconfirm", package])
    elif action == "uninstall":
        r = _run(["pacman", "-R", "--noconfirm", package])
    elif action == "search":
        r = _run(["pacman", "-Ss", package])
    elif action == "list":
        r = _run(["pacman", "-Q"])
    elif action == "update":
        r = _run(["pacman", "-Syu", "--noconfirm"], timeout=300)
    elif action == "info":
        r = _run(["pacman", "-Si", package])
    else:
        return f"Error: pacman does not support action '{action}'"
    return _format_result(r)


# --- Dev Package Managers ---

def _pip(action: str, package: str) -> str:
    pip_cmd = "pip" if shutil.which("pip") else "pip3"
    if action == "install":
        r = _run([pip_cmd, "install", package])
    elif action == "uninstall":
        r = _run([pip_cmd, "uninstall", "-y", package])
    elif action == "search":
        # pip search is deprecated, use pip index versions
        r = _run([pip_cmd, "index", "versions", package])
    elif action == "list":
        r = _run([pip_cmd, "list"])
    elif action == "update":
        r = _run([pip_cmd, "install", "--upgrade", package] if package else [pip_cmd, "list", "--outdated"])
    elif action == "info":
        r = _run([pip_cmd, "show", package])
    else:
        return f"Error: pip does not support action '{action}'"
    return _format_result(r)


def _npm(action: str, package: str) -> str:
    if action == "install":
        r = _run(["npm", "install", package])
    elif action == "uninstall":
        r = _run(["npm", "uninstall", package])
    elif action == "search":
        r = _run(["npm", "search", package])
    elif action == "list":
        r = _run(["npm", "list", "--depth=0"])
    elif action == "update":
        r = _run(["npm", "update"] if not package else ["npm", "update", package])
    elif action == "info":
        r = _run(["npm", "info", package])
    else:
        return f"Error: npm does not support action '{action}'"
    return _format_result(r)


def _cargo(action: str, package: str) -> str:
    if action == "install":
        r = _run(["cargo", "install", package])
    elif action == "uninstall":
        r = _run(["cargo", "uninstall", package])
    elif action == "search":
        r = _run(["cargo", "search", package])
    elif action == "list":
        r = _run(["cargo", "install", "--list"])
    elif action == "update":
        r = _run(["cargo", "update"])
    elif action == "info":
        r = _run(["cargo", "search", package])
    else:
        return f"Error: cargo does not support action '{action}'"
    return _format_result(r)


def _go(action: str, package: str) -> str:
    if action == "install":
        r = _run(["go", "install", package])
    elif action == "list":
        r = _run(["go", "list", "-m", "all"])
    elif action == "update":
        r = _run(["go", "get", "-u", package] if package else ["go", "get", "-u", "./..."])
    elif action == "info":
        r = _run(["go", "list", "-m", "-json", package])
    else:
        return f"Error: go does not support action '{action}'"
    return _format_result(r)


def _dotnet_nuget(action: str, package: str) -> str:
    if action == "install":
        r = _run(["dotnet", "add", "package", package])
    elif action == "uninstall":
        r = _run(["dotnet", "remove", "package", package])
    elif action == "search":
        r = _run(["dotnet", "package", "search", package])
    elif action == "list":
        r = _run(["dotnet", "list", "package"])
    elif action == "update":
        r = _run(["dotnet", "add", "package", package] if package else ["dotnet", "restore"])
    elif action == "info":
        r = _run(["dotnet", "package", "search", package, "--exact-match"])
    else:
        return f"Error: dotnet does not support action '{action}'"
    return _format_result(r)


def _format_result(r: dict[str, Any]) -> str:
    """Format command result into a readable string."""
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    if r["exit_code"] != 0:
        parts.append(f"Exit code: {r['exit_code']}")
    return "\n".join(parts) if parts else "Done (no output)."
