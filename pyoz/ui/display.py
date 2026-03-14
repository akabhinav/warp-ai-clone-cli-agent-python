"""PyOz display — rich output components for tool calls, diffs, stats, etc."""

import os
import time
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule

from pyoz.ui.theme import PYOZ_THEME, ICONS
from pyoz.platform import IS_WINDOWS, HAS_POWERSHELL, PLATFORM_NAME, get_shell_info

# Global console with theme
console = Console(theme=PYOZ_THEME, highlight=False)


def print_banner(info: dict[str, Any], session_resumed: bool = False) -> None:
    """Print a beautiful startup banner."""
    # Build status lines
    lines = []
    lines.append(f"  Provider: [pyoz.accent]{info['provider']}[/] / [pyoz.accent]{info['model']}[/]")
    lines.append(f"  [pyoz.success]{ICONS['check']}[/] AST Indexer ready")
    lines.append(f"  [pyoz.success]{ICONS['check']}[/] Codebase: [pyoz.stat.value]{info['files_indexed']}[/] files, [pyoz.stat.value]{info['symbols']}[/] symbols")
    lines.append(f"  [pyoz.success]{ICONS['check']}[/] Git: {info['git']}")

    # Platform info
    shell_info = get_shell_info()
    platform_str = shell_info['platform'].capitalize()
    shell_str = shell_info['name']
    if IS_WINDOWS and HAS_POWERSHELL:
        lines.append(f"  [pyoz.success]{ICONS['check']}[/] Platform: {platform_str} + [bold magenta]PowerShell[/]")
    else:
        lines.append(f"  [pyoz.success]{ICONS['check']}[/] Platform: {platform_str} ({shell_str})")

    if info.get("rules"):
        lines.append(f"  [pyoz.success]{ICONS['check']}[/] Rules: loaded from PYOZ.md")
    else:
        lines.append(f"  [pyoz.subtle]{ICONS['circle']}[/] [pyoz.subtle]Rules: none (create PYOZ.md to add)[/]")

    if session_resumed:
        turns = info.get("session_turns", 0)
        lines.append(f"  [pyoz.session]{ICONS['save']}[/] Session resumed ([pyoz.stat.value]{turns}[/] turns)")

    content = "\n".join(lines)

    panel = Panel(
        content,
        title=f"{ICONS['wizard']} [pyoz.brand]PyOz — Coding Agent[/]",
        subtitle="[pyoz.subtle]Type /help for commands  •  Ctrl+C to interrupt[/]",
        border_style="magenta",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


def print_tool_call(name: str, args: dict[str, Any], result: str) -> None:
    """Display a tool call with formatted output."""
    # Format tool detail
    detail = _format_tool_detail(name, args)
    tool_line = Text()
    tool_line.append(f"  {ICONS['arrow']} ", style="pyoz.tool.arrow")
    tool_line.append(name, style="pyoz.tool")
    if detail:
        tool_line.append(f" {detail}", style="pyoz.tool.detail")

    console.print(tool_line)

    # Show command output inline
    if name == "run_command" and result:
        lines = result.splitlines()
        show_lines = lines[:30]
        for line in show_lines:
            console.print(f"  [pyoz.tool.output]{ICONS['bar']}[/] {line}")
        if len(lines) > 30:
            console.print(f"  [pyoz.tool.output]{ICONS['bar']}[/] [pyoz.subtle]... ({len(lines) - 30} more lines)[/]")


def print_diff(path: str, old_text: str, new_text: str) -> None:
    """Display a beautiful inline diff."""
    rel_path = os.path.relpath(path)
    console.print()
    console.print(f"  [pyoz.diff.header]{rel_path}:[/]")

    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    for line in old_lines:
        console.print(f"  [pyoz.diff.remove]- {line}[/]")
    for line in new_lines:
        console.print(f"  [pyoz.diff.add]+ {line}[/]")
    console.print()


def print_response(text: str) -> None:
    """Display LLM response with markdown rendering."""
    console.print()
    md = Markdown(text)
    console.print(md, width=min(console.width, 100))


def print_turn_stats(stats: dict[str, Any], tool_calls_this_turn: int = 0) -> None:
    """Display per-turn statistics."""
    cost = stats.get("estimated_cost", 0)
    cost_str = f"${cost:.4f}" if cost > 0 else "free"

    stat_text = Text()
    stat_text.append(f"\n  {ICONS['check']} done", style="pyoz.success")
    stat_text.append(f"  {ICONS['tools']}", style="pyoz.subtle")
    stat_text.append(f" {stats['total_tool_calls']} calls", style="pyoz.subtle")
    stat_text.append(f"  {ICONS['brain']}", style="pyoz.subtle")
    stat_text.append(f" {stats['input_tokens']:,}↑ {stats['output_tokens']:,}↓", style="pyoz.subtle")
    stat_text.append(f"  {ICONS['clock']}", style="pyoz.subtle")
    stat_text.append(f" {cost_str}", style="pyoz.stat.cost" if cost > 0 else "pyoz.subtle")

    console.print(stat_text)


def print_error(message: str) -> None:
    """Display an error message."""
    console.print(f"\n  [pyoz.error]{ICONS['cross']} {message}[/]")


def print_success(message: str) -> None:
    """Display a success message."""
    console.print(f"  [pyoz.success]{ICONS['check']} {message}[/]")


def print_info(message: str) -> None:
    """Display an info message."""
    console.print(f"  [pyoz.info]{message}[/]")


def print_warning(message: str) -> None:
    """Display a warning."""
    console.print(f"  [pyoz.warning]{message}[/]")


def print_workspaces(current: str, recent: list[dict[str, str]]) -> None:
    """Display workspace list."""
    console.print(f"  [pyoz.stat.label]Current:[/] [pyoz.ws.active]{current}[/]")

    if not recent:
        console.print("  [pyoz.subtle]No recent workspaces.[/]")
        return

    table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False)
    table.add_column("#", style="pyoz.accent", width=3)
    table.add_column("Name", style="pyoz.ws.name")
    table.add_column("Path", style="pyoz.ws.path")
    table.add_column("Last Access", style="pyoz.subtle")

    for i, ws in enumerate(recent, 1):
        marker = " ←" if ws["path"] == current else ""
        name_str = ws["name"] + ("[pyoz.ws.active]" + marker + "[/]" if marker else "")
        table.add_row(str(i), name_str, ws["path"], ws.get("last_access", ""))

    console.print()
    console.print("  Recent workspaces:", style="pyoz.stat.label")
    console.print(table)


def print_sessions(sessions: list[dict[str, str]]) -> None:
    """Display session history."""
    if not sessions:
        console.print("  [pyoz.subtle]No archived sessions.[/]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("#", style="pyoz.accent", width=3)
    table.add_column("Date", style="pyoz.session")
    table.add_column("Turns", justify="right")
    table.add_column("Provider", style="pyoz.subtle")

    for i, s in enumerate(sessions, 1):
        table.add_row(str(i), s["saved_at"], str(s["turns"]), s["provider"])

    console.print("  Archived sessions:", style="pyoz.stat.label")
    console.print(table)


def print_stats(stats: dict[str, Any]) -> None:
    """Display detailed session statistics."""
    table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
    table.add_column("Label", style="pyoz.stat.label")
    table.add_column("Value", style="pyoz.stat.value")

    table.add_row("Turns", str(stats["turns"]))
    table.add_row("Tool calls", str(stats["total_tool_calls"]))
    table.add_row("Input tokens", f"{stats['input_tokens']:,}")
    table.add_row("Output tokens", f"{stats['output_tokens']:,}")

    cost = stats.get("estimated_cost", 0)
    cost_style = "pyoz.stat.cost" if cost > 0 else "pyoz.subtle"
    cost_str = f"${cost:.4f}" if cost > 0 else "free"
    table.add_row("Estimated cost", f"[{cost_style}]{cost_str}[/]")

    console.print(table)


def print_commits(commits: list[dict[str, str]]) -> None:
    """Display git log."""
    if not commits:
        console.print("  [pyoz.subtle]No commits yet.[/]")
        return
    for c in commits:
        console.print(f"  [pyoz.accent]{c['hash']}[/] {c['message']}")


def print_files(entries: list[dict[str, Any]]) -> None:
    """Display file listing."""
    for e in entries:
        if e["type"] == "directory":
            console.print(f"  [bold blue]{e['name']}/[/]")
        else:
            size = e.get("size", 0)
            console.print(f"  {e['name']} [pyoz.subtle]({size:,} bytes)[/]")


def print_diff_output(diff_text: str) -> None:
    """Display git diff output with syntax highlighting."""
    if diff_text == "no changes":
        console.print("  [pyoz.subtle]No changes.[/]")
        return
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            console.print(f"  [pyoz.diff.add]{line}[/]")
        elif line.startswith("-") and not line.startswith("---"):
            console.print(f"  [pyoz.diff.remove]{line}[/]")
        elif line.startswith("@@"):
            console.print(f"  [pyoz.diff.header]{line}[/]")
        else:
            console.print(f"  {line}")


def print_rules(rules: str) -> None:
    """Display PYOZ.md rules."""
    md = Markdown(rules)
    console.print(md)


def print_help() -> None:
    """Display comprehensive help menu."""
    help_sections = [
        ("Git", [
            ("/undo", "Undo last git commit"),
            ("/diff", "Show uncommitted changes"),
            ("/log", "Show recent git history"),
        ]),
        ("Codebase", [
            ("/index", "Re-scan and re-index codebase"),
            ("/files", "List files in working directory"),
            ("/rules", "Show loaded rules from PYOZ.md"),
        ]),
        ("Session", [
            ("/save", "Save current session"),
            ("/resume", "Resume last saved session"),
            ("/new", "Archive current, start fresh"),
            ("/sessions", "List archived sessions"),
            ("/export", "Export session as markdown"),
            ("/clear", "Clear conversation history"),
        ]),
        ("Workspace", [
            ("/workspace, /ws", "Show current & recent workspaces"),
            ("/ws <path|name|#>", "Switch to workspace"),
            ("/ws-add [path]", "Add directory as workspace"),
            ("/ws-remove <id>", "Remove workspace"),
        ]),
        ("Settings", [
            ("/stream", "Toggle streaming output"),
            ("/stats", "Show token usage and cost"),
            ("/platform", "Show platform & shell info" + (" + PowerShell reference" if IS_WINDOWS else "")),
        ]),
        ("General", [
            ("/help", "Show this help"),
            ("/quit", "Exit PyOz"),
        ]),
    ]

    for section_name, commands in help_sections:
        table = Table(show_header=False, box=None, padding=(0, 2), pad_edge=False)
        table.add_column("Command", style="pyoz.slash", min_width=22)
        table.add_column("Description")
        for cmd, desc in commands:
            table.add_row(cmd, desc)

        console.print(f"\n  [bold]{section_name}[/]")
        console.print(table)
    console.print()


def print_platform_info() -> None:
    """Display platform and shell information with PowerShell reference on Windows."""
    shell_info = get_shell_info()

    lines = [
        f"  [pyoz.stat.label]Platform:[/] [pyoz.stat.value]{shell_info['platform'].capitalize()}[/]",
        f"  [pyoz.stat.label]Shell:[/]    [pyoz.stat.value]{shell_info['name']}[/]",
        f"  [pyoz.stat.label]Path:[/]     [pyoz.subtle]{shell_info['path']}[/]",
    ]
    console.print("\n".join(lines))

    if IS_WINDOWS and HAS_POWERSHELL:
        console.print()
        console.print("  [bold]PowerShell Quick Reference:[/]")

        from pyoz.platform import POWERSHELL_COMMAND_MAP

        categories = {
            "Navigation & Files": ["pwd", "cd", "ls", "find", "cat", "head", "tail", "cp", "mv", "rm", "mkdir", "touch"],
            "Search & Text": ["grep", "sed", "sort", "diff", "wc"],
            "System": ["ps", "kill", "which", "env", "whoami"],
            "Network": ["curl", "wget", "ping"],
        }

        for cat_name, commands in categories.items():
            table = Table(show_header=False, box=None, padding=(0, 1), pad_edge=False)
            table.add_column("Unix", style="pyoz.subtle", min_width=12)
            table.add_column("Arrow", style="pyoz.tool.arrow", width=3)
            table.add_column("PowerShell", style="pyoz.accent")
            for cmd in commands:
                if cmd in POWERSHELL_COMMAND_MAP:
                    table.add_row(cmd, "→", POWERSHELL_COMMAND_MAP[cmd])
            console.print(f"\n  [bold]{cat_name}:[/]")
            console.print(table)
    console.print()


def _format_tool_detail(name: str, args: dict[str, Any]) -> str:
    """Format tool call detail string."""
    if name == "write_file":
        path = args.get("path", "?")
        size = len(args.get("content", "").encode("utf-8"))
        return f"{path} ({size:,} bytes)"
    elif name == "read_file":
        return args.get("path", "?")
    elif name == "edit_file":
        return args.get("path", "?")
    elif name == "run_command":
        return args.get("command", "?")
    elif name == "search_files":
        return f"pattern={args.get('pattern', '?')}"
    elif name == "git_commit":
        return f'"{args.get("message", "?")}"'
    elif name == "static_config":
        return f"{args.get('language', '?')}/{args.get('project_name', '?')}"
    elif name == "list_directory":
        return args.get("path", ".")
    elif name == "git_log":
        return f"n={args.get('n', 10)}"
    return ""
