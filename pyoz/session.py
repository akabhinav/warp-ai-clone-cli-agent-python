"""Session Persistence — save/resume conversations to disk.

Stores sessions in ~/.pyoz/sessions/<workspace_hash>/:
- session.json: conversation history, stats, metadata
- Auto-save after each turn
- Resume from last session on startup
"""

import hashlib
import json
import os
import time
from typing import Any

PYOZ_HOME = os.path.join(os.path.expanduser("~"), ".pyoz")
SESSIONS_DIR = os.path.join(PYOZ_HOME, "sessions")


def _workspace_hash(work_dir: str) -> str:
    """Generate a short hash for a workspace path."""
    return hashlib.sha256(os.path.abspath(work_dir).encode()).hexdigest()[:12]


def _session_dir(work_dir: str) -> str:
    """Get the session directory for a workspace."""
    return os.path.join(SESSIONS_DIR, _workspace_hash(work_dir))


class SessionManager:
    """Manage persistent sessions for a workspace."""

    def __init__(self, work_dir: str):
        self.work_dir = os.path.abspath(work_dir)
        self._dir = _session_dir(self.work_dir)
        self._session_file = os.path.join(self._dir, "session.json")
        self._history_dir = os.path.join(self._dir, "history")

    def save(
        self,
        messages: list[dict[str, Any]],
        stats: dict[str, Any],
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        """Save current session to disk."""
        os.makedirs(self._dir, exist_ok=True)

        session_data = {
            "work_dir": self.work_dir,
            "provider": provider,
            "model": model,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": messages,
            "stats": stats,
        }

        with open(self._session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, default=str)

        return self._session_file

    def load(self) -> dict[str, Any] | None:
        """Load the last saved session."""
        if not os.path.isfile(self._session_file):
            return None
        try:
            with open(self._session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def has_session(self) -> bool:
        """Check if a saved session exists."""
        return os.path.isfile(self._session_file)

    def delete(self) -> bool:
        """Delete the saved session."""
        if os.path.isfile(self._session_file):
            os.remove(self._session_file)
            return True
        return False

    def archive(self) -> str | None:
        """Archive current session to history before starting a new one."""
        if not self.has_session():
            return None

        os.makedirs(self._history_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        archive_file = os.path.join(self._history_dir, f"session_{timestamp}.json")

        # Copy current session to archive
        session = self.load()
        if session:
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump(session, f, indent=2, default=str)
            return archive_file
        return None

    def list_history(self) -> list[dict[str, str]]:
        """List archived sessions."""
        if not os.path.isdir(self._history_dir):
            return []

        sessions = []
        for fname in sorted(os.listdir(self._history_dir), reverse=True):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self._history_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                msg_count = len([m for m in data.get("messages", [])
                                if m.get("role") == "user" and isinstance(m.get("content"), str)])
                sessions.append({
                    "file": fname,
                    "saved_at": data.get("saved_at", "unknown"),
                    "turns": msg_count,
                    "provider": data.get("provider", "unknown"),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return sessions

    def load_from_history(self, identifier: str) -> dict[str, Any] | None:
        """Load a specific session from history by filename or index (1-based)."""
        history = self.list_history()
        if not history:
            return None

        # Try as index
        try:
            idx = int(identifier) - 1
            if 0 <= idx < len(history):
                fpath = os.path.join(self._history_dir, history[idx]["file"])
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except ValueError:
            pass

        # Try as filename
        fpath = os.path.join(self._history_dir, identifier)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)

        return None

    def export_markdown(self) -> str | None:
        """Export current session as markdown."""
        session = self.load()
        if not session:
            return None

        lines = [
            f"# PyOz Session — {session.get('saved_at', 'unknown')}",
            f"",
            f"**Workspace:** `{session.get('work_dir', 'unknown')}`  ",
            f"**Provider:** {session.get('provider', 'unknown')} / {session.get('model', 'unknown')}  ",
            f"",
            "---",
            "",
        ]

        for msg in session.get("messages", []):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user" and isinstance(content, str):
                lines.append(f"## User")
                lines.append(content)
                lines.append("")
            elif role == "assistant" and isinstance(content, str):
                lines.append(f"## PyOz")
                lines.append(content)
                lines.append("")
            elif role == "assistant" and isinstance(content, list):
                lines.append(f"## PyOz")
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            lines.append(block["text"])
                        elif block.get("type") == "tool_use":
                            lines.append(f"**Tool:** `{block['name']}({json.dumps(block.get('input', {}), default=str)[:100]})`")
                lines.append("")

        # Stats
        stats = session.get("stats", {})
        if stats:
            lines.append("---")
            lines.append("")
            lines.append(f"**Turns:** {stats.get('turns', 0)} | "
                        f"**Tool calls:** {stats.get('total_tool_calls', 0)} | "
                        f"**Tokens:** {stats.get('input_tokens', 0):,} in + {stats.get('output_tokens', 0):,} out | "
                        f"**Cost:** ${stats.get('estimated_cost', 0):.4f}")

        return "\n".join(lines)
