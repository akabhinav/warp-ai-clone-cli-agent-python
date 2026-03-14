"""Workspace Manager — switch between projects, save/restore state, recent list.

Stores workspace metadata in ~/.pyoz/workspaces.json:
- Recent workspaces with paths, names, last access times
- Active workspace tracking
- Per-workspace settings (provider, model overrides)
"""

import json
import os
import time
from typing import Any

PYOZ_HOME = os.path.join(os.path.expanduser("~"), ".pyoz")
WORKSPACES_FILE = os.path.join(PYOZ_HOME, "workspaces.json")
MAX_RECENT = 20


def _ensure_pyoz_home() -> None:
    """Create ~/.pyoz directory if it doesn't exist."""
    os.makedirs(PYOZ_HOME, exist_ok=True)


def _load_workspaces() -> dict[str, Any]:
    """Load workspaces data from disk."""
    if not os.path.isfile(WORKSPACES_FILE):
        return {"active": None, "recent": [], "settings": {}}
    try:
        with open(WORKSPACES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"active": None, "recent": [], "settings": {}}


def _save_workspaces(data: dict[str, Any]) -> None:
    """Save workspaces data to disk."""
    _ensure_pyoz_home()
    with open(WORKSPACES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class WorkspaceManager:
    """Manage multiple project workspaces."""

    def __init__(self):
        self.data = _load_workspaces()

    def register(self, path: str, name: str | None = None) -> dict[str, str]:
        """Register a workspace and set it as active."""
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise FileNotFoundError(f"Directory not found: {abs_path}")

        ws_name = name or os.path.basename(abs_path)

        # Remove if already in recent
        self.data["recent"] = [
            w for w in self.data["recent"] if w["path"] != abs_path
        ]

        # Add to front of recent
        entry = {
            "path": abs_path,
            "name": ws_name,
            "last_access": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.data["recent"].insert(0, entry)

        # Trim to max
        self.data["recent"] = self.data["recent"][:MAX_RECENT]

        # Set active
        self.data["active"] = abs_path

        _save_workspaces(self.data)
        return {"path": abs_path, "name": ws_name}

    def switch(self, identifier: str) -> dict[str, str]:
        """Switch to a workspace by name, path, or index (1-based)."""
        # Try as index
        try:
            idx = int(identifier) - 1
            if 0 <= idx < len(self.data["recent"]):
                ws = self.data["recent"][idx]
                return self.register(ws["path"], ws["name"])
        except ValueError:
            pass

        # Try as path
        abs_path = os.path.abspath(identifier)
        if os.path.isdir(abs_path):
            return self.register(abs_path)

        # Try as name
        for ws in self.data["recent"]:
            if ws["name"].lower() == identifier.lower():
                return self.register(ws["path"], ws["name"])

        raise ValueError(f"Workspace not found: {identifier}")

    def list_recent(self) -> list[dict[str, str]]:
        """List recent workspaces."""
        return self.data["recent"]

    def get_active(self) -> str | None:
        """Get the active workspace path."""
        return self.data.get("active")

    def remove(self, identifier: str) -> bool:
        """Remove a workspace from recent list."""
        try:
            idx = int(identifier) - 1
            if 0 <= idx < len(self.data["recent"]):
                removed = self.data["recent"].pop(idx)
                if self.data["active"] == removed["path"]:
                    self.data["active"] = None
                _save_workspaces(self.data)
                return True
        except ValueError:
            pass

        for i, ws in enumerate(self.data["recent"]):
            if ws["name"].lower() == identifier.lower() or ws["path"] == os.path.abspath(identifier):
                self.data["recent"].pop(i)
                if self.data["active"] == ws["path"]:
                    self.data["active"] = None
                _save_workspaces(self.data)
                return True

        return False

    def set_workspace_setting(self, path: str, key: str, value: str) -> None:
        """Set a per-workspace setting."""
        abs_path = os.path.abspath(path)
        if abs_path not in self.data.get("settings", {}):
            self.data.setdefault("settings", {})[abs_path] = {}
        self.data["settings"][abs_path][key] = value
        _save_workspaces(self.data)

    def get_workspace_settings(self, path: str) -> dict[str, str]:
        """Get per-workspace settings."""
        abs_path = os.path.abspath(path)
        return self.data.get("settings", {}).get(abs_path, {})

    def touch(self, path: str) -> None:
        """Update last_access time for a workspace."""
        abs_path = os.path.abspath(path)
        for ws in self.data["recent"]:
            if ws["path"] == abs_path:
                ws["last_access"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _save_workspaces(self.data)
                return
