"""System info tools — OS, hardware, disk, installed SDKs, network.

Cross-platform: works on Windows (PowerShell/WMI), macOS, and Linux.
No external dependencies — uses subprocess and os module only.
"""

import os
import platform
import shutil
import subprocess
from typing import Any

from pyoz.platform import IS_WINDOWS, IS_MACOS, IS_LINUX, PLATFORM_NAME, HAS_POWERSHELL


def _run(args: list[str], timeout: int = 30) -> str:
    """Run a command and return stdout."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def system_info(category: str = "overview") -> str:
    """Get system information.

    Args:
        category: One of: overview, os, cpu, memory, disk, network,
                  sdks, python, node, java, dotnet, rust, go
    """
    category = category.lower().strip()

    if category == "overview":
        return _overview()
    elif category == "os":
        return _os_info()
    elif category == "cpu":
        return _cpu_info()
    elif category == "memory":
        return _memory_info()
    elif category == "disk":
        return _disk_info()
    elif category == "network":
        return _network_info()
    elif category == "sdks":
        return _all_sdks()
    elif category in ("python", "node", "java", "dotnet", "rust", "go"):
        return _sdk_info(category)
    else:
        return ("Error: Unknown category. Use: overview, os, cpu, memory, "
                "disk, network, sdks, python, node, java, dotnet, rust, go")


def _overview() -> str:
    """Quick system overview."""
    lines = [
        "System Overview",
        "=" * 40,
        f"  OS:        {platform.system()} {platform.release()}",
        f"  Platform:  {platform.platform()}",
        f"  Machine:   {platform.machine()}",
        f"  Processor: {platform.processor() or 'Unknown'}",
        f"  Python:    {platform.python_version()}",
        f"  Hostname:  {platform.node()}",
        f"  User:      {os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))}",
        f"  CWD:       {os.getcwd()}",
    ]

    if IS_WINDOWS and HAS_POWERSHELL:
        lines.append(f"  Shell:     PowerShell")
    elif IS_WINDOWS:
        lines.append(f"  Shell:     cmd.exe")
    else:
        lines.append(f"  Shell:     {os.environ.get('SHELL', 'unknown')}")

    # Quick SDK check
    sdks = []
    for name, cmd in [("Node", "node"), ("Java", "java"), ("Go", "go"),
                       ("Rust", "rustc"), ("dotnet", "dotnet"), ("Docker", "docker")]:
        if shutil.which(cmd):
            sdks.append(name)
    if sdks:
        lines.append(f"  SDKs:      {', '.join(sdks)}")

    return "\n".join(lines)


def _os_info() -> str:
    """Detailed OS information."""
    lines = [
        "Operating System",
        "=" * 40,
        f"  System:    {platform.system()}",
        f"  Release:   {platform.release()}",
        f"  Version:   {platform.version()}",
        f"  Platform:  {platform.platform()}",
        f"  Machine:   {platform.machine()}",
    ]

    if IS_WINDOWS:
        edition = _run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_OperatingSystem).Caption"])
        if edition:
            lines.append(f"  Edition:   {edition}")
        build = _run(["powershell", "-NoProfile", "-Command",
                      "(Get-CimInstance Win32_OperatingSystem).BuildNumber"])
        if build:
            lines.append(f"  Build:     {build}")
    elif IS_LINUX:
        # Try to read /etc/os-release
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=", 1)[1].strip().strip('"')
                        lines.append(f"  Distro:    {distro}")
                        break
        except FileNotFoundError:
            pass
    elif IS_MACOS:
        ver = _run(["sw_vers", "-productVersion"])
        if ver:
            lines.append(f"  macOS:     {ver}")

    return "\n".join(lines)


def _cpu_info() -> str:
    """CPU information."""
    lines = ["CPU Information", "=" * 40]
    cpu_count = os.cpu_count() or 0
    lines.append(f"  Cores:     {cpu_count}")
    lines.append(f"  Arch:      {platform.machine()}")

    if IS_WINDOWS:
        name = _run(["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Processor).Name"])
        if name:
            lines.append(f"  Model:     {name}")
        speed = _run(["powershell", "-NoProfile", "-Command",
                      "(Get-CimInstance Win32_Processor).MaxClockSpeed"])
        if speed:
            lines.append(f"  Speed:     {speed} MHz")
    elif IS_LINUX:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        model = line.split(":")[1].strip()
                        lines.append(f"  Model:     {model}")
                        break
        except FileNotFoundError:
            pass
    elif IS_MACOS:
        brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if brand:
            lines.append(f"  Model:     {brand}")

    return "\n".join(lines)


def _memory_info() -> str:
    """Memory information."""
    lines = ["Memory Information", "=" * 40]

    if IS_WINDOWS:
        total = _run(["powershell", "-NoProfile", "-Command",
                      "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,2)"])
        avail = _run(["powershell", "-NoProfile", "-Command",
                      "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,2)"])
        if total:
            lines.append(f"  Total:     {total} GB")
        if avail:
            lines.append(f"  Available: {avail} GB")
    elif IS_LINUX:
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]  # kB value
                        meminfo[key] = int(val)
                total_gb = meminfo.get("MemTotal", 0) / 1024 / 1024
                avail_gb = meminfo.get("MemAvailable", 0) / 1024 / 1024
                used_gb = total_gb - avail_gb
                lines.append(f"  Total:     {total_gb:.1f} GB")
                lines.append(f"  Available: {avail_gb:.1f} GB")
                lines.append(f"  Used:      {used_gb:.1f} GB ({used_gb/total_gb*100:.0f}%)" if total_gb else "")
        except (FileNotFoundError, ValueError):
            pass
    elif IS_MACOS:
        total = _run(["sysctl", "-n", "hw.memsize"])
        if total:
            total_gb = int(total) / 1024 / 1024 / 1024
            lines.append(f"  Total:     {total_gb:.1f} GB")

    return "\n".join(lines)


def _disk_info() -> str:
    """Disk usage information."""
    lines = ["Disk Usage", "=" * 40]

    if IS_WINDOWS:
        output = _run(["powershell", "-NoProfile", "-Command",
                       "Get-PSDrive -PSProvider FileSystem | "
                       "Select-Object Name, "
                       "@{N='Used(GB)';E={[math]::Round($_.Used/1GB,1)}}, "
                       "@{N='Free(GB)';E={[math]::Round($_.Free/1GB,1)}}, "
                       "@{N='Total(GB)';E={[math]::Round(($_.Used+$_.Free)/1GB,1)}} | "
                       "Format-Table -AutoSize"])
        if output:
            lines.append(output)
    else:
        output = _run(["df", "-h", "--type=ext4", "--type=xfs", "--type=btrfs",
                       "--type=apfs", "--type=hfs"])
        if not output:
            output = _run(["df", "-h"])
        if output:
            lines.append(output)

    # Current directory usage
    cwd = os.getcwd()
    try:
        usage = shutil.disk_usage(cwd)
        total_gb = usage.total / 1024 / 1024 / 1024
        free_gb = usage.free / 1024 / 1024 / 1024
        used_gb = usage.used / 1024 / 1024 / 1024
        lines.append(f"\n  Current directory ({cwd}):")
        lines.append(f"    Total: {total_gb:.1f} GB, Used: {used_gb:.1f} GB, Free: {free_gb:.1f} GB")
    except OSError:
        pass

    return "\n".join(lines)


def _network_info() -> str:
    """Network interface information."""
    lines = ["Network Information", "=" * 40]

    if IS_WINDOWS:
        output = _run(["powershell", "-NoProfile", "-Command",
                       "Get-NetIPAddress -AddressFamily IPv4 | "
                       "Where-Object { $_.IPAddress -ne '127.0.0.1' } | "
                       "Select-Object InterfaceAlias, IPAddress, PrefixLength | "
                       "Format-Table -AutoSize"])
        if output:
            lines.append(output)
        # Hostname and DNS
        hostname = _run(["powershell", "-NoProfile", "-Command", "$env:COMPUTERNAME"])
        if hostname:
            lines.append(f"  Hostname: {hostname}")
    else:
        # Try ip first, then ifconfig
        output = _run(["ip", "-4", "addr", "show"])
        if not output:
            output = _run(["ifconfig"])
        if output:
            # Trim to relevant lines
            relevant = []
            for line in output.splitlines():
                if "inet " in line or ":" in line.split()[0] if line.strip() else False:
                    relevant.append(line)
            lines.append("\n".join(relevant[:20]) if relevant else output[:500])

        hostname = platform.node()
        lines.append(f"\n  Hostname: {hostname}")

    return "\n".join(lines)


def _all_sdks() -> str:
    """Check all installed development SDKs and tools."""
    lines = ["Installed SDKs & Tools", "=" * 40]

    checks = [
        ("Python", ["python3", "--version"], ["python", "--version"]),
        ("pip", ["pip3", "--version"], ["pip", "--version"]),
        ("Node.js", ["node", "--version"], None),
        ("npm", ["npm", "--version"], None),
        ("Java", ["java", "-version"], None),
        ("Maven", ["mvn", "--version"], None),
        ("Gradle", ["gradle", "--version"], None),
        (".NET SDK", ["dotnet", "--version"], None),
        ("Go", ["go", "version"], None),
        ("Rust", ["rustc", "--version"], None),
        ("Cargo", ["cargo", "--version"], None),
        ("Docker", ["docker", "--version"], None),
        ("Docker Compose", ["docker", "compose", "version"], None),
        ("Git", ["git", "--version"], None),
        ("kubectl", ["kubectl", "version", "--client", "--short"], None),
        ("Terraform", ["terraform", "--version"], None),
        ("Ruby", ["ruby", "--version"], None),
        ("PHP", ["php", "--version"], None),
        ("GCC", ["gcc", "--version"], None),
        ("Make", ["make", "--version"], None),
    ]

    if IS_WINDOWS:
        checks.extend([
            ("MSBuild", ["msbuild", "-version"], None),
            ("NuGet", ["nuget", "help"], None),
            ("winget", ["winget", "--version"], None),
            ("choco", ["choco", "--version"], None),
            ("scoop", ["scoop", "--version"], None),
        ])

    found = 0
    for name, primary_cmd, fallback_cmd in checks:
        version = _get_version(primary_cmd)
        if not version and fallback_cmd:
            version = _get_version(fallback_cmd)
        if version:
            found += 1
            # Clean up version string
            version = version.splitlines()[0][:60]
            lines.append(f"  {name:<18} {version}")

    lines.insert(1, f"  ({found} tools detected)")
    return "\n".join(lines)


def _sdk_info(sdk: str) -> str:
    """Get detailed info for a specific SDK."""
    commands = {
        "python": [
            ("Version", ["python3", "--version"]),
            ("Location", ["which", "python3"] if not IS_WINDOWS else ["where", "python"]),
            ("pip", ["pip3", "--version"]),
        ],
        "node": [
            ("Version", ["node", "--version"]),
            ("npm", ["npm", "--version"]),
            ("Location", ["which", "node"] if not IS_WINDOWS else ["where", "node"]),
            ("npx", ["npx", "--version"]),
        ],
        "java": [
            ("Version", ["java", "-version"]),
            ("JAVA_HOME", None),  # env var
            ("Maven", ["mvn", "--version"]),
            ("Gradle", ["gradle", "--version"]),
        ],
        "dotnet": [
            ("Version", ["dotnet", "--version"]),
            ("SDKs", ["dotnet", "--list-sdks"]),
            ("Runtimes", ["dotnet", "--list-runtimes"]),
        ],
        "rust": [
            ("Version", ["rustc", "--version"]),
            ("Cargo", ["cargo", "--version"]),
            ("Toolchain", ["rustup", "show"]),
        ],
        "go": [
            ("Version", ["go", "version"]),
            ("GOPATH", None),
            ("Location", ["which", "go"] if not IS_WINDOWS else ["where", "go"]),
        ],
    }

    checks = commands.get(sdk, [])
    if not checks:
        return f"Error: Unknown SDK '{sdk}'"

    lines = [f"{sdk.capitalize()} SDK Info", "=" * 40]

    for label, cmd in checks:
        if cmd is None:
            # Environment variable
            val = os.environ.get(label.upper(), os.environ.get(label, "not set"))
            lines.append(f"  {label:<12} {val}")
        else:
            output = _get_version(cmd)
            if output:
                lines.append(f"  {label:<12} {output.splitlines()[0][:80]}")
            else:
                lines.append(f"  {label:<12} not installed")

    return "\n".join(lines)


def _get_version(cmd: list[str]) -> str:
    """Try to get version output from a command."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        # Java outputs to stderr
        output = r.stdout.strip() or r.stderr.strip()
        return output
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
