"""File tools — read, write, edit, search, list.

Cross-platform: works on Windows, macOS, and Linux.
Uses Python's os module for all operations (no shell commands).
"""

import os
import re
from typing import Any

from pyoz.platform import IS_WINDOWS, normalize_path


SKIP_DIRS = {".git", "node_modules", "target", "build", "venv", "__pycache__", ".venv", "dist", ".tox", ".mypy_cache"}

# Windows-specific skip dirs
if IS_WINDOWS:
    SKIP_DIRS.update({"$RECYCLE.BIN", "System Volume Information", ".vs", "bin", "obj", "packages"})


def read_file(path: str) -> str:
    """Read and return file content."""
    path = os.path.abspath(normalize_path(path))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(path: str, content: str) -> str:
    """Write content to file, creating parent dirs as needed."""
    path = os.path.abspath(normalize_path(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    size = len(content.encode("utf-8"))
    return f"wrote {size} bytes to {path}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Search/replace in file. old_text must appear exactly once."""
    path = os.path.abspath(normalize_path(path))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    count = content.count(old_text)
    if count == 0:
        raise ValueError(f"old_text not found in {path}")
    if count > 1:
        raise ValueError(f"old_text found {count} times in {path} — must appear exactly once")
    new_content = content.replace(old_text, new_text, 1)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new_content)
    return f"edited {path}: replaced {len(old_text)} chars with {len(new_text)} chars"


def search_files(pattern: str, path: str | None = None, file_ext: str | None = None) -> list[dict[str, Any]]:
    """Regex search across codebase files."""
    search_path = os.path.abspath(normalize_path(path)) if path else os.getcwd()
    results = []
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    for root, dirs, files in os.walk(search_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if file_ext and not fname.endswith(file_ext):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append({
                                "file": os.path.relpath(fpath, search_path),
                                "line": lineno,
                                "text": line.rstrip()[:200],
                            })
            except (PermissionError, OSError):
                continue
    return results


def list_directory(path: str | None = None) -> list[dict[str, Any]]:
    """List files and folders, skipping hidden/build dirs."""
    dir_path = os.path.abspath(normalize_path(path)) if path else os.getcwd()
    if not os.path.isdir(dir_path):
        raise FileNotFoundError(f"Directory not found: {dir_path}")
    entries = []
    for name in sorted(os.listdir(dir_path)):
        if name.startswith(".") or name in SKIP_DIRS:
            continue
        full = os.path.join(dir_path, name)
        entry: dict[str, Any] = {"name": name}
        if os.path.isdir(full):
            entry["type"] = "directory"
        else:
            entry["type"] = "file"
            try:
                entry["size"] = os.path.getsize(full)
            except OSError:
                entry["size"] = 0
        entries.append(entry)
    return entries
