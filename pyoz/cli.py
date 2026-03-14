"""PyOz CLI — world-class interactive terminal interface.

Uses rich for beautiful output and prompt_toolkit for enhanced input.
"""

import os
import sys
import signal
import argparse
import time
from typing import Any

from pyoz.agent import Agent
from pyoz.providers.base import BaseLLMProvider
from pyoz.workspace import WorkspaceManager
from pyoz.session import SessionManager
from pyoz.ui.display import (
    console,
    print_banner,
    print_tool_call,
    print_diff,
    print_response,
    print_turn_stats,
    print_error,
    print_success,
    print_info,
    print_warning,
    print_workspaces,
    print_sessions,
    print_stats,
    print_commits,
    print_files,
    print_diff_output,
    print_rules,
    print_help,
    print_platform_info,
)
from pyoz.ui.input import InputManager


def _read_secret_file(path: str) -> str | None:
    """Read an API key from a Docker secret file."""
    try:
        with open(path) as f:
            value = f.read().strip()
            return value if value else None
    except (FileNotFoundError, PermissionError):
        return None


def _create_provider(args: argparse.Namespace) -> BaseLLMProvider:
    """Create an LLM provider from CLI arguments."""
    provider = args.provider.lower()

    if provider == "claude":
        api_key = (
            args.api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or _read_secret_file("/run/secrets/anthropic_api_key")
        )
        if not api_key:
            print_error("--api-key or ANTHROPIC_API_KEY environment variable required for Claude")
            sys.exit(1)
        from pyoz.providers.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=api_key, model=args.model)

    elif provider == "openai":
        api_key = (
            args.api_key
            or os.environ.get("OPENAI_API_KEY")
            or _read_secret_file("/run/secrets/openai_api_key")
        )
        if not api_key:
            print_error("--api-key or OPENAI_API_KEY environment variable required for OpenAI")
            sys.exit(1)
        from pyoz.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=args.model)

    elif provider == "ollama":
        from pyoz.providers.ollama_provider import OllamaProvider
        return OllamaProvider(model=args.model, base_url=args.ollama_url)

    else:
        print_error(f"Unknown provider '{provider}'. Use: claude, openai, ollama")
        sys.exit(1)


def _on_tool_call(name: str, args: dict[str, Any], result: str) -> None:
    """Display tool calls as they happen."""
    print_tool_call(name, args, result)


def _on_diff(path: str, old_text: str, new_text: str) -> None:
    """Display diff after edit_file."""
    print_diff(path, old_text, new_text)


def _on_stream_token(text: str) -> None:
    """Print streaming tokens as they arrive."""
    sys.stdout.write(text)
    sys.stdout.flush()


def _on_ask_user(question: str, options: list[str]) -> str:
    """Prompt the user with a question and options during planning/execution."""
    console.print()
    console.print(f"  [pyoz.accent]? {question}[/]")
    for i, opt in enumerate(options, 1):
        marker = "(recommended)" if i == 1 else ""
        console.print(f"    [pyoz.brand]{i}.[/] {opt} [pyoz.subtle]{marker}[/]")
    console.print(f"    [pyoz.brand]{len(options) + 1}.[/] Other (type your own)")
    console.print()

    while True:
        try:
            raw = input("  Choose [1]: ").strip()
            if not raw:
                # Default to first (recommended) option
                console.print(f"  [pyoz.success]→ {options[0]}[/]")
                return options[0]

            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(options):
                    console.print(f"  [pyoz.success]→ {options[idx - 1]}[/]")
                    return options[idx - 1]
                elif idx == len(options) + 1:
                    custom = input("  Your choice: ").strip()
                    if custom:
                        console.print(f"  [pyoz.success]→ {custom}[/]")
                        return custom
                    continue
            else:
                # User typed a free-form answer
                console.print(f"  [pyoz.success]→ {raw}[/]")
                return raw
        except (EOFError, KeyboardInterrupt):
            console.print(f"\n  [pyoz.subtle]Using default: {options[0]}[/]")
            return options[0]


def _handle_slash_command(command: str, agent: Agent, workspace_mgr: WorkspaceManager) -> bool:
    """Handle slash commands. Returns True if handled."""
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("/quit", "/exit"):
        try:
            agent.save_session()
        except Exception:
            pass
        console.print("\n[pyoz.accent]Goodbye![/]")
        sys.exit(0)

    elif cmd == "/undo":
        from pyoz.tools.git_tools import git_undo
        try:
            result = git_undo(agent.work_dir)
            print_success(result)
        except Exception as e:
            print_error(str(e))
        return True

    elif cmd == "/diff":
        from pyoz.tools.git_tools import git_diff
        result = git_diff(agent.work_dir)
        print_diff_output(result)
        return True

    elif cmd == "/log":
        from pyoz.tools.git_tools import git_log
        commits = git_log(10, agent.work_dir)
        print_commits(commits)
        return True

    elif cmd == "/index":
        with console.status("[pyoz.accent]Indexing codebase...[/]", spinner="dots"):
            result = agent.reindex()
        print_success(f"Indexed: {result['files']} files, {result['symbols']} symbols")
        return True

    elif cmd == "/files":
        from pyoz.tools.file_tools import list_directory
        entries = list_directory(agent.work_dir)
        print_files(entries)
        return True

    elif cmd == "/stats":
        stats = agent.get_stats()
        print_stats(stats)
        return True

    elif cmd == "/clear":
        agent.clear_history()
        print_success("Conversation cleared.")
        return True

    elif cmd == "/rules":
        rules = agent.reload_rules()
        if rules and rules != "No rules file found.":
            print_rules(rules)
        else:
            console.print("  [pyoz.subtle]No PYOZ.md or .pyoz/rules.md found.[/]")
        return True

    # --- Workspace commands ---
    elif cmd in ("/workspace", "/ws"):
        if not arg:
            recent = workspace_mgr.list_recent()
            print_workspaces(agent.work_dir, recent)
        else:
            try:
                ws = workspace_mgr.switch(arg)
                with console.status("[pyoz.accent]Switching workspace...[/]", spinner="dots"):
                    info = agent.change_work_dir(ws["path"])
                workspace_mgr.touch(ws["path"])
                print_success(f"Switched to: {ws['name']} ({ws['path']})")
                console.print(f"    {info['files_indexed']} files indexed, {info['symbols']} symbols")
                if agent.turn_count > 0:
                    console.print(f"    [pyoz.session]Resumed session ({agent.turn_count} turns)[/]")
            except (ValueError, FileNotFoundError) as e:
                print_error(str(e))
        return True

    elif cmd == "/ws-add":
        path = arg or agent.work_dir
        try:
            name = os.path.basename(os.path.abspath(path))
            ws = workspace_mgr.register(path, name)
            print_success(f"Added workspace: {ws['name']} ({ws['path']})")
        except Exception as e:
            print_error(str(e))
        return True

    elif cmd == "/ws-remove":
        if not arg:
            console.print("  [pyoz.subtle]Usage: /ws-remove <name|number>[/]")
        elif workspace_mgr.remove(arg):
            print_success(f"Removed workspace: {arg}")
        else:
            print_error(f"Workspace not found: {arg}")
        return True

    # --- Session commands ---
    elif cmd == "/save":
        path = agent.save_session()
        print_success(f"Session saved: {path}")
        return True

    elif cmd == "/resume":
        if agent.load_session():
            print_success(f"Session resumed ({agent.turn_count} turns, {agent.total_tool_calls} tool calls)")
        else:
            console.print("  [pyoz.subtle]No saved session found.[/]")
        return True

    elif cmd == "/new":
        archive = agent.new_session()
        if archive:
            print_success("Previous session archived. Starting fresh.")
        else:
            print_success("Starting new session.")
        return True

    elif cmd == "/sessions":
        sessions = agent.list_sessions()
        print_sessions(sessions)
        return True

    elif cmd == "/export":
        md = agent.export_session()
        if md:
            export_path = os.path.join(agent.work_dir, "pyoz_session.md")
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(md)
            print_success(f"Session exported to: {export_path}")
        else:
            console.print("  [pyoz.subtle]No session to export.[/]")
        return True

    # --- Streaming toggle ---
    elif cmd == "/stream":
        agent.streaming = not agent.streaming
        state = "on" if agent.streaming else "off"
        print_success(f"Streaming: {state}")
        return True

    elif cmd == "/platform":
        print_platform_info()
        return True

    elif cmd == "/help":
        print_help()
        return True

    return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PyOz — Pure Agent Mode Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pyoz.py --provider claude --api-key sk-ant-...
  python pyoz.py --provider openai --api-key sk-...
  python pyoz.py --provider ollama --model qwen2.5:7b
  python pyoz.py --test
        """,
    )
    parser.add_argument("--provider", default="claude", choices=["claude", "openai", "ollama"],
                        help="LLM provider (default: claude)")
    parser.add_argument("--api-key", help="API key (or set ANTHROPIC_API_KEY / OPENAI_API_KEY env var)")
    parser.add_argument("--model", help="Model name override")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL")
    parser.add_argument("--work-dir", help="Working directory (default: current)")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output (streaming is on by default)")
    parser.add_argument("--no-resume", action="store_true", help="Don't resume previous session")
    parser.add_argument("--test", action="store_true", help="Run self-test")

    args = parser.parse_args()

    if args.test:
        _run_self_test()
        return

    # Create provider
    provider = _create_provider(args)

    # Create agent
    work_dir = args.work_dir or os.getcwd()
    agent = Agent(
        provider=provider,
        work_dir=work_dir,
        on_tool_call=_on_tool_call,
        on_diff=_on_diff,
        on_stream_token=_on_stream_token,
        on_ask_user=_on_ask_user,
        streaming=not args.no_stream,
    )

    # Initialize
    with console.status("[pyoz.accent]Initializing...[/]", spinner="dots"):
        info = agent.initialize()

    # Register workspace
    workspace_mgr = WorkspaceManager()
    workspace_mgr.register(work_dir)

    # Try to resume session
    session_resumed = False
    if not args.no_resume and agent.session_mgr.has_session():
        session_resumed = agent.load_session()
        if session_resumed:
            info["session_turns"] = agent.turn_count

    print_banner(info, session_resumed)

    # Create input manager with history + autocomplete
    input_mgr = InputManager()

    # Handle Ctrl+C gracefully
    interrupted = False

    def signal_handler(sig, frame):
        nonlocal interrupted
        if interrupted:
            try:
                agent.save_session()
            except Exception:
                pass
            console.print("\n[pyoz.error]Force quit.[/]")
            sys.exit(1)
        interrupted = True
        console.print("\n  [pyoz.warning]Interrupted. Press Ctrl+C again to quit.[/]")

    signal.signal(signal.SIGINT, signal_handler)

    # Main REPL loop
    while True:
        interrupted = False
        try:
            user_input = input_mgr.get_input("> ")
        except EOFError:
            try:
                agent.save_session()
            except Exception:
                pass
            console.print("\n[pyoz.accent]Goodbye![/]")
            break
        except KeyboardInterrupt:
            console.print()
            continue

        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            if _handle_slash_command(user_input, agent, workspace_mgr):
                continue

        # Send to agent
        try:
            start_time = time.time()

            if agent.streaming:
                console.print()  # Newline before streaming output

            response = agent.chat(user_input)

            elapsed = time.time() - start_time

            if response and not agent.streaming:
                print_response(response)

            # Show turn stats
            stats = agent.get_stats()
            print_turn_stats(stats)

        except KeyboardInterrupt:
            console.print("\n  [pyoz.warning]Interrupted.[/]")
        except Exception as e:
            print_error(str(e))


def _run_self_test():
    """Run a comprehensive self-test."""
    from rich.panel import Panel

    console.print(Panel(
        "[pyoz.brand]PyOz Self-Test[/]",
        border_style="magenta",
        padding=(0, 2),
    ))
    errors = 0
    tests_run = 0

    def _pass(name: str):
        nonlocal tests_run
        tests_run += 1
        console.print(f"  [pyoz.success]✓[/] {name}")

    def _fail(name: str, msg: str):
        nonlocal errors, tests_run
        errors += 1
        tests_run += 1
        console.print(f"  [pyoz.error]✗[/] {name}: {msg}")

    import tempfile

    # Test file tools
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.tools.file_tools import write_file, read_file, edit_file, list_directory, search_files

        path = os.path.join(tmpdir, "test.txt")
        write_file(path, "hello world")
        content = read_file(path)
        assert content == "hello world"
        _pass("write_file + read_file")

        edit_file(path, "hello", "goodbye")
        content = read_file(path)
        assert content == "goodbye world"
        _pass("edit_file")

        entries = list_directory(tmpdir)
        assert any(e["name"] == "test.txt" for e in entries)
        _pass("list_directory")

        results = search_files("goodbye", tmpdir)
        assert len(results) > 0
        _pass("search_files")

    # Test command tools
    from pyoz.tools.command_tools import run_command
    result = run_command("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]
    _pass("run_command")

    try:
        run_command("rm -rf /")
        _fail("dangerous command blocking", "not caught")
    except PermissionError:
        _pass("dangerous command blocking")

    # Test git tools
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.tools.git_tools import git_init, git_commit, git_log, is_git_repo
        git_init(tmpdir)
        assert is_git_repo(tmpdir)
        _pass("git_init")

        test_file = os.path.join(tmpdir, "code.py")
        write_file(test_file, "x = 1\n")
        result = git_commit("test commit", tmpdir)
        assert "committed" in result
        _pass("git_commit")

        commits = git_log(5, tmpdir)
        assert len(commits) >= 2
        _pass("git_log")

    # Test AST indexer
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.indexer.ast_indexer import ASTIndexer
        py_file = os.path.join(tmpdir, "example.py")
        write_file(py_file, """
import os
from typing import List

class MyClass:
    def __init__(self, name: str):
        self.name = name
    def greet(self) -> str:
        return f"Hello, {self.name}"

def standalone_func(x: int) -> int:
    return x * 2
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        assert indexer.file_count() == 1
        assert indexer.symbol_count() >= 3
        _pass("AST indexer (Python)")

    # Test static configs
    from pyoz.tools.context_tools import static_config
    config = static_config("java", "myapp")
    assert "pom.xml" in config
    _pass("static_config")

    # Test tool registry
    from pyoz.tools.registry import get_tool_definitions_claude, get_tool_definitions_openai
    claude_tools = len(get_tool_definitions_claude())
    openai_tools = len(get_tool_definitions_openai())
    assert claude_tools == openai_tools
    assert claude_tools >= 25  # At least 25 tools (including ask_user)
    _pass(f"tool registry ({claude_tools} tools)")

    # Test workspace manager
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.workspace import WorkspaceManager
        mgr = WorkspaceManager()
        ws = mgr.register(tmpdir, "test-ws")
        assert ws["name"] == "test-ws"
        recent = mgr.list_recent()
        assert len(recent) >= 1
        _pass("workspace manager")

    # Test session persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.session import SessionManager
        smgr = SessionManager(tmpdir)
        smgr.save([{"role": "user", "content": "test"}], {"turns": 1})
        data = smgr.load()
        assert data is not None
        assert data["messages"][0]["content"] == "test"
        _pass("session persistence")

    # Test UI components
    try:
        from pyoz.ui.display import console as test_console
        from pyoz.ui.theme import PYOZ_THEME, ICONS
        assert len(ICONS) > 0
        _pass("UI components")
    except Exception as e:
        _fail("UI components", str(e))

    # Test input manager
    try:
        from pyoz.ui.input import InputManager, SlashCommandCompleter
        completer = SlashCommandCompleter()
        assert completer is not None
        _pass("input manager")
    except Exception as e:
        _fail("input manager", str(e))

    # Summary
    console.print()
    if errors == 0:
        console.print(Panel(
            f"[pyoz.success]All {tests_run} tests passed![/]",
            border_style="green",
            padding=(0, 2),
        ))
    else:
        console.print(Panel(
            f"[pyoz.error]{errors}/{tests_run} tests failed[/]",
            border_style="red",
            padding=(0, 2),
        ))
        sys.exit(1)


if __name__ == "__main__":
    main()
