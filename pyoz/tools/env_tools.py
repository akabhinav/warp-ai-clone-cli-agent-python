"""Environment variable tools — get, set, load .env files, manage PATH.

Cross-platform: works on Windows (PowerShell/registry), macOS, and Linux.
"""

import os
import re
from typing import Any

from pyoz.platform import IS_WINDOWS


def env_manager(action: str, name: str = "", value: str = "", file_path: str = "") -> str:
    """Manage environment variables.

    Args:
        action: One of: get, set, unset, list, load-env, save-env, path-list, path-add
        name: Variable name (for get/set/unset)
        value: Variable value (for set)
        file_path: Path to .env file (for load-env/save-env)
    """
    action = action.lower().strip()

    if action == "get":
        if not name:
            return "Error: 'name' is required for get"
        val = os.environ.get(name)
        if val is None:
            return f"{name} is not set"
        return f"{name}={val}"

    elif action == "set":
        if not name:
            return "Error: 'name' is required for set"
        if not value and value != "":
            return "Error: 'value' is required for set"
        os.environ[name] = value
        return f"Set {name}={value} (current process)"

    elif action == "unset":
        if not name:
            return "Error: 'name' is required for unset"
        if name in os.environ:
            del os.environ[name]
            return f"Unset {name} (current process)"
        return f"{name} was not set"

    elif action == "list":
        # List environment variables, optionally filtered by name prefix
        prefix = name.upper() if name else ""
        lines = []
        for key in sorted(os.environ.keys()):
            if prefix and not key.upper().startswith(prefix):
                continue
            val = os.environ[key]
            # Truncate long values
            if len(val) > 100:
                val = val[:100] + "..."
            lines.append(f"{key}={val}")
        if not lines:
            return f"No environment variables found{' matching ' + prefix if prefix else ''}"
        return "\n".join(lines)

    elif action == "load-env":
        return _load_env_file(file_path or ".env")

    elif action == "save-env":
        return _save_env_file(file_path or ".env", name)

    elif action == "path-list":
        return _list_path()

    elif action == "path-add":
        if not value:
            return "Error: 'value' is required for path-add (the directory to add)"
        return _add_to_path(value)

    else:
        return ("Error: Unknown action. Use: get, set, unset, list, "
                "load-env, save-env, path-list, path-add")


def _load_env_file(path: str) -> str:
    """Load variables from a .env file into the current process."""
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        return f"Error: .env file not found: {abs_path}"

    loaded = []
    with open(abs_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE (with optional quotes)
            match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
            if not match:
                continue
            key = match.group(1)
            val = match.group(2).strip()
            # Remove surrounding quotes
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            os.environ[key] = val
            loaded.append(key)

    if not loaded:
        return f"No variables found in {abs_path}"
    return f"Loaded {len(loaded)} variables from {abs_path}: {', '.join(loaded)}"


def _save_env_file(path: str, filter_prefix: str = "") -> str:
    """Save current environment variables to a .env file."""
    abs_path = os.path.abspath(path)
    lines = []
    prefix = filter_prefix.upper() if filter_prefix else ""

    for key in sorted(os.environ.keys()):
        if prefix and not key.upper().startswith(prefix):
            continue
        val = os.environ[key]
        # Quote values with spaces
        if " " in val or "=" in val:
            val = f'"{val}"'
        lines.append(f"{key}={val}")

    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return f"Saved {len(lines)} variables to {abs_path}"


def _list_path() -> str:
    """List all directories in PATH."""
    separator = ";" if IS_WINDOWS else ":"
    path_val = os.environ.get("PATH", "")
    dirs = path_val.split(separator)

    lines = [f"PATH ({len(dirs)} entries):"]
    for i, d in enumerate(dirs, 1):
        exists = os.path.isdir(d)
        marker = "  " if exists else "  [missing] "
        lines.append(f"  {i:3}. {marker}{d}")

    return "\n".join(lines)


def _add_to_path(directory: str) -> str:
    """Add a directory to PATH (current process only)."""
    abs_dir = os.path.abspath(directory)
    if not os.path.isdir(abs_dir):
        return f"Error: Directory not found: {abs_dir}"

    separator = ";" if IS_WINDOWS else ":"
    current = os.environ.get("PATH", "")

    if abs_dir in current.split(separator):
        return f"Already in PATH: {abs_dir}"

    os.environ["PATH"] = abs_dir + separator + current
    return f"Added to PATH (current process): {abs_dir}"
