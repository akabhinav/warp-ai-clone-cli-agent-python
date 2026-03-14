"""MSBuild / Visual Studio Solution tools — build .sln, manage projects, NuGet.

Handles Visual Studio solutions (.sln), MSBuild projects (.csproj, .fsproj, .vbproj),
NuGet package restoration, and project reference management.
Cross-platform via dotnet CLI + MSBuild.
"""

import os
import re
import shutil
import subprocess
from typing import Any

from pyoz.platform import IS_WINDOWS


def _run(args: list[str], cwd: str | None = None, timeout: int = 300) -> dict[str, Any]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Build timed out", "exit_code": -1}


def _fmt(r: dict[str, Any]) -> str:
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    if r["exit_code"] != 0 and not parts:
        parts.append(f"Failed (exit code {r['exit_code']})")
    return "\n".join(parts) if parts else "Done."


def _find_build_tool() -> str | None:
    """Find the best available build tool: dotnet or msbuild."""
    if shutil.which("dotnet"):
        return "dotnet"
    if shutil.which("msbuild"):
        return "msbuild"
    if IS_WINDOWS:
        # Check common VS install paths
        vs_paths = [
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
            r"C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe",
            r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe",
        ]
        for p in vs_paths:
            if os.path.isfile(p):
                return p
    return None


def msbuild_tool(action: str, target: str = "", args: str = "", cwd: str | None = None) -> str:
    """MSBuild and Visual Studio Solution management.

    Args:
        action: One of:
          Build: build, rebuild, clean, restore, publish, test
          Solution: sln-list, sln-add, sln-remove, sln-new
          Project: proj-list, proj-add-ref, proj-remove-ref
          Info: info, find-solutions, find-projects
        target: Solution (.sln) or project (.csproj) path
        args: Extra arguments (e.g. configuration, platform, package name)
        cwd: Working directory
    """
    work_dir = cwd or os.getcwd()
    action = action.lower().strip()
    extra = args.split() if args else []

    build_tool = _find_build_tool()

    # --- Build actions ---
    if action == "build":
        return _build(target, "Build", extra, work_dir, build_tool)
    elif action == "rebuild":
        return _build(target, "Rebuild", extra, work_dir, build_tool)
    elif action == "clean":
        return _build(target, "Clean", extra, work_dir, build_tool)

    elif action == "restore":
        if not build_tool:
            return "Error: Neither dotnet nor MSBuild found."
        if build_tool == "dotnet" or build_tool.endswith("dotnet"):
            cmd = ["dotnet", "restore"]
            if target:
                cmd.append(target)
            return _fmt(_run(cmd, work_dir))
        else:
            cmd = [build_tool, target or ".", "/t:Restore"]
            return _fmt(_run(cmd, work_dir))

    elif action == "publish":
        if not shutil.which("dotnet"):
            return "Error: dotnet CLI required for publish"
        cmd = ["dotnet", "publish"]
        if target:
            cmd.append(target)
        cmd.extend(extra or ["-c", "Release"])
        return _fmt(_run(cmd, work_dir))

    elif action == "test":
        if not shutil.which("dotnet"):
            return "Error: dotnet CLI required for test"
        cmd = ["dotnet", "test"]
        if target:
            cmd.append(target)
        cmd.extend(extra)
        return _fmt(_run(cmd, work_dir, timeout=300))

    # --- Solution management ---
    elif action == "sln-new":
        if not shutil.which("dotnet"):
            return "Error: dotnet CLI required"
        name = target or os.path.basename(work_dir)
        cmd = ["dotnet", "new", "sln", "-n", name]
        return _fmt(_run(cmd, work_dir))

    elif action == "sln-list":
        sln = target or _find_sln(work_dir)
        if not sln:
            return "Error: No .sln file found. Specify target or create one with sln-new."
        cmd = ["dotnet", "sln", sln, "list"]
        return _fmt(_run(cmd, work_dir))

    elif action == "sln-add":
        if not args:
            return "Error: 'args' (project path) required for sln-add"
        sln = target or _find_sln(work_dir)
        if not sln:
            return "Error: No .sln file found."
        cmd = ["dotnet", "sln", sln, "add"] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "sln-remove":
        if not args:
            return "Error: 'args' (project path) required for sln-remove"
        sln = target or _find_sln(work_dir)
        if not sln:
            return "Error: No .sln file found."
        cmd = ["dotnet", "sln", sln, "remove"] + extra
        return _fmt(_run(cmd, work_dir))

    # --- Project references ---
    elif action == "proj-list":
        proj = target or _find_proj(work_dir)
        if not proj:
            return "Error: No .csproj/.fsproj found."
        cmd = ["dotnet", "list", proj, "reference"]
        return _fmt(_run(cmd, work_dir))

    elif action == "proj-add-ref":
        if not args:
            return "Error: 'args' (reference project path) required"
        proj = target or _find_proj(work_dir)
        if not proj:
            return "Error: No .csproj/.fsproj found."
        cmd = ["dotnet", "add", proj, "reference"] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "proj-remove-ref":
        if not args:
            return "Error: 'args' (reference project path) required"
        proj = target or _find_proj(work_dir)
        if not proj:
            return "Error: No .csproj/.fsproj found."
        cmd = ["dotnet", "remove", proj, "reference"] + extra
        return _fmt(_run(cmd, work_dir))

    # --- Info ---
    elif action == "info":
        return _build_info(work_dir)

    elif action == "find-solutions":
        return _find_files(work_dir, "*.sln")

    elif action == "find-projects":
        return _find_files(work_dir, "*.csproj") + "\n" + _find_files(work_dir, "*.fsproj")

    else:
        return (
            "Error: Unknown action. Available:\n"
            "  Build:    build, rebuild, clean, restore, publish, test\n"
            "  Solution: sln-new, sln-list, sln-add, sln-remove\n"
            "  Project:  proj-list, proj-add-ref, proj-remove-ref\n"
            "  Info:     info, find-solutions, find-projects"
        )


def _build(target: str, build_target: str, extra: list[str], cwd: str, build_tool: str | None) -> str:
    """Run a build command."""
    if not build_tool:
        return "Error: Neither dotnet CLI nor MSBuild found. Install .NET SDK from https://dot.net"

    if build_tool == "dotnet" or build_tool.endswith("dotnet"):
        action_map = {"Build": "build", "Rebuild": "build", "Clean": "clean"}
        dotnet_action = action_map.get(build_target, "build")
        cmd = ["dotnet", dotnet_action]
        if target:
            cmd.append(target)
        if build_target == "Rebuild":
            # dotnet doesn't have rebuild, so clean then build
            _run(["dotnet", "clean"] + ([target] if target else []), cwd)
        cmd.extend(extra)
        return _fmt(_run(cmd, cwd))
    else:
        cmd = [build_tool]
        if target:
            cmd.append(target)
        cmd.extend([f"/t:{build_target}", "/nologo"])
        # Default config
        if not any(a.startswith("/p:Configuration") for a in extra):
            cmd.append("/p:Configuration=Debug")
        cmd.extend(extra)
        return _fmt(_run(cmd, cwd))


def _find_sln(cwd: str) -> str:
    """Find first .sln file in directory."""
    for f in os.listdir(cwd):
        if f.endswith(".sln"):
            return os.path.join(cwd, f)
    return ""


def _find_proj(cwd: str) -> str:
    """Find first project file in directory."""
    for ext in (".csproj", ".fsproj", ".vbproj"):
        for f in os.listdir(cwd):
            if f.endswith(ext):
                return os.path.join(cwd, f)
    return ""


def _find_files(cwd: str, pattern: str) -> str:
    """Find files matching pattern recursively."""
    ext = pattern.replace("*", "")
    found = []
    skip = {".git", "node_modules", "bin", "obj", "packages", ".vs"}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith(ext):
                found.append(os.path.relpath(os.path.join(root, f), cwd))
    if not found:
        return f"No {pattern} files found."
    return "\n".join(found)


def _build_info(cwd: str) -> str:
    """Show build environment info."""
    lines = ["Build Environment", "=" * 40]

    build_tool = _find_build_tool()
    lines.append(f"  Build tool: {build_tool or 'None found'}")

    if shutil.which("dotnet"):
        r = _run(["dotnet", "--version"])
        lines.append(f"  .NET SDK:   {r['stdout']}")

    if IS_WINDOWS and shutil.which("msbuild"):
        r = _run(["msbuild", "-version", "-nologo"])
        lines.append(f"  MSBuild:    {r['stdout'].splitlines()[-1] if r['stdout'] else 'unknown'}")

    sln = _find_sln(cwd)
    if sln:
        lines.append(f"  Solution:   {os.path.basename(sln)}")
    proj = _find_proj(cwd)
    if proj:
        lines.append(f"  Project:    {os.path.basename(proj)}")

    return "\n".join(lines)
