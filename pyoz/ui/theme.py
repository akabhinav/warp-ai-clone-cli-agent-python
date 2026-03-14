"""PyOz theme — consistent colors and styles across the UI."""

from rich.theme import Theme
from rich.style import Style

# Brand colors
PYOZ_THEME = Theme({
    # Brand
    "pyoz.brand": "bold magenta",
    "pyoz.accent": "cyan",
    "pyoz.subtle": "dim",

    # Status
    "pyoz.success": "bold green",
    "pyoz.error": "bold red",
    "pyoz.warning": "bold yellow",
    "pyoz.info": "blue",

    # UI elements
    "pyoz.tool": "bold yellow",
    "pyoz.tool.arrow": "cyan",
    "pyoz.tool.output": "dim",
    "pyoz.tool.detail": "dim cyan",

    # Diff
    "pyoz.diff.add": "green",
    "pyoz.diff.remove": "red",
    "pyoz.diff.header": "bold cyan",

    # Input
    "pyoz.prompt": "bold green",
    "pyoz.slash": "bold cyan",

    # Stats
    "pyoz.stat.label": "dim",
    "pyoz.stat.value": "bold",
    "pyoz.stat.cost": "bold yellow",

    # Workspace
    "pyoz.ws.active": "bold green",
    "pyoz.ws.name": "bold cyan",
    "pyoz.ws.path": "dim",

    # Session
    "pyoz.session": "bold blue",
})

# Icons (using Unicode symbols)
ICONS = {
    "wizard": "🧙",
    "check": "✓",
    "cross": "✗",
    "circle": "○",
    "arrow": "→",
    "dot": "●",
    "bar": "│",
    "tools": "🔧",
    "file": "📄",
    "folder": "📁",
    "git": "⎇",
    "search": "🔍",
    "cmd": "⚡",
    "save": "💾",
    "clock": "⏱",
    "brain": "🧠",
    "stream": "⚡",
    "workspace": "📂",
}
