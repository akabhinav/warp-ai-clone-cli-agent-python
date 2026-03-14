"""PyOz CLI — interactive terminal interface."""

import os
import sys
import signal
import argparse
from typing import Any

from pyoz.agent import Agent
from pyoz.providers.base import BaseLLMProvider


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"


def _color(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.RESET}"


def _create_provider(args: argparse.Namespace) -> BaseLLMProvider:
    """Create an LLM provider from CLI arguments."""
    provider = args.provider.lower()

    if provider == "claude":
        api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print(_color("Error: --api-key or ANTHROPIC_API_KEY required for Claude", Colors.RED))
            sys.exit(1)
        from pyoz.providers.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=api_key, model=args.model)

    elif provider == "openai":
        api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print(_color("Error: --api-key or OPENAI_API_KEY required for OpenAI", Colors.RED))
            sys.exit(1)
        from pyoz.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=args.model)

    elif provider == "ollama":
        from pyoz.providers.ollama_provider import OllamaProvider
        return OllamaProvider(model=args.model, base_url=args.ollama_url)

    else:
        print(_color(f"Error: Unknown provider '{provider}'. Use: claude, openai, ollama", Colors.RED))
        sys.exit(1)


def _on_tool_call(name: str, args: dict[str, Any], result: str) -> None:
    """Display tool calls as they happen."""
    # Format the tool call display
    detail = ""
    if name == "write_file":
        path = args.get("path", "?")
        size = len(args.get("content", "").encode("utf-8"))
        detail = f" {path} ({size} bytes)"
    elif name == "read_file":
        detail = f" {args.get('path', '?')}"
    elif name == "edit_file":
        detail = f" {args.get('path', '?')}"
    elif name == "run_command":
        cmd = args.get("command", "?")
        detail = f" {cmd}"
    elif name == "search_files":
        detail = f" pattern={args.get('pattern', '?')}"
    elif name == "git_commit":
        detail = f" \"{args.get('message', '?')}\""
    elif name == "static_config":
        detail = f" {args.get('language', '?')}/{args.get('project_name', '?')}"
    elif name == "list_directory":
        detail = f" {args.get('path', '.')}"

    print(f"  {_color('→', Colors.CYAN)} {_color(name, Colors.YELLOW)}{detail}")

    # Show command output inline for run_command
    if name == "run_command" and result:
        for line in result.splitlines()[:30]:  # Limit output lines
            print(f"  {_color('│', Colors.DIM)} {line}")
        if len(result.splitlines()) > 30:
            print(f"  {_color('│', Colors.DIM)} ... ({len(result.splitlines()) - 30} more lines)")


def _on_diff(path: str, old_text: str, new_text: str) -> None:
    """Display diff after edit_file."""
    rel_path = os.path.relpath(path)
    print(f"\n  {_color(rel_path + ':', Colors.BOLD)}")
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    for line in old_lines:
        print(f"  {_color('- ' + line, Colors.RED)}")
    for line in new_lines:
        print(f"  {_color('+ ' + line, Colors.GREEN)}")
    print()


def _handle_slash_command(command: str, agent: Agent) -> bool:
    """Handle slash commands. Returns True if handled."""
    cmd = command.strip().lower()

    if cmd == "/quit" or cmd == "/exit":
        print(_color("\nGoodbye!", Colors.CYAN))
        sys.exit(0)

    elif cmd == "/undo":
        from pyoz.tools.git_tools import git_undo
        try:
            result = git_undo(agent.work_dir)
            print(_color(f"  ✓ {result}", Colors.GREEN))
        except Exception as e:
            print(_color(f"  ✗ {e}", Colors.RED))
        return True

    elif cmd == "/diff":
        from pyoz.tools.git_tools import git_diff
        result = git_diff(agent.work_dir)
        print(result)
        return True

    elif cmd == "/log":
        from pyoz.tools.git_tools import git_log
        commits = git_log(10, agent.work_dir)
        if not commits:
            print(_color("  No commits yet.", Colors.DIM))
        else:
            for c in commits:
                print(f"  {_color(c['hash'], Colors.YELLOW)} {c['message']}")
        return True

    elif cmd == "/index":
        result = agent.reindex()
        print(_color(f"  ✓ Indexed: {result['files']} files, {result['symbols']} symbols", Colors.GREEN))
        return True

    elif cmd == "/files":
        from pyoz.tools.file_tools import list_directory
        entries = list_directory(agent.work_dir)
        for e in entries:
            if e["type"] == "directory":
                print(f"  {_color(e['name'] + '/', Colors.BLUE)}")
            else:
                print(f"  {e['name']} ({e.get('size', 0)} bytes)")
        return True

    elif cmd == "/stats":
        stats = agent.get_stats()
        print(f"  Turns: {stats['turns']}")
        print(f"  Tool calls: {stats['total_tool_calls']}")
        print(f"  Tokens: {stats['input_tokens']:,} in + {stats['output_tokens']:,} out")
        print(f"  Estimated cost: ${stats['estimated_cost']:.4f}")
        return True

    elif cmd == "/clear":
        agent.clear_history()
        print(_color("  ✓ Conversation cleared.", Colors.GREEN))
        return True

    elif cmd == "/rules":
        rules = agent.reload_rules()
        if rules and rules != "No rules file found.":
            print(_color("  Rules loaded:", Colors.GREEN))
            print(rules)
        else:
            print(_color("  No PYOZ.md or .pyoz/rules.md found.", Colors.DIM))
        return True

    elif cmd == "/help":
        print(f"""
  {_color('PyOz Commands:', Colors.BOLD)}
  /undo       Undo last git commit
  /diff       Show uncommitted changes
  /log        Show recent git history
  /index      Re-scan and re-index codebase
  /files      List files in working directory
  /stats      Show token usage and cost
  /clear      Clear conversation history
  /rules      Show loaded rules from PYOZ.md
  /help       Show this help
  /quit       Exit PyOz
""")
        return True

    return False


def _print_banner(info: dict[str, Any]) -> None:
    """Print startup banner."""
    print(f"""
{_color('🧙 PyOz — Coding Agent', Colors.BOLD + Colors.MAGENTA)}
  Provider: {_color(info['provider'], Colors.CYAN)} / {_color(info['model'], Colors.CYAN)}
  {_color('✓', Colors.GREEN)} tree-sitter AST indexer
  {_color('✓', Colors.GREEN)} Codebase: {info['files_indexed']} files indexed, {info['symbols']} symbols
  {_color('✓', Colors.GREEN)} Git: {info['git']}
  {_color('✓' if info['rules'] else '○', Colors.GREEN if info['rules'] else Colors.DIM)} Rules: {'loaded from PYOZ.md' if info['rules'] else 'none (create PYOZ.md to add rules)'}

  Type /help for commands. Ctrl+C to interrupt.
""")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="PyOz — Pure Agent Mode Coding Assistant")
    parser.add_argument("--provider", default="claude", choices=["claude", "openai", "ollama"],
                        help="LLM provider (default: claude)")
    parser.add_argument("--api-key", help="API key (or set ANTHROPIC_API_KEY / OPENAI_API_KEY)")
    parser.add_argument("--model", help="Model name override")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL")
    parser.add_argument("--work-dir", help="Working directory (default: current)")
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
    )

    # Initialize
    info = agent.initialize()
    _print_banner(info)

    # Handle Ctrl+C gracefully
    interrupted = False

    def signal_handler(sig, frame):
        nonlocal interrupted
        if interrupted:
            print(_color("\nForce quit.", Colors.RED))
            sys.exit(1)
        interrupted = True
        print(_color("\n  Interrupted. Press Ctrl+C again to quit.", Colors.YELLOW))

    signal.signal(signal.SIGINT, signal_handler)

    # Main REPL loop
    while True:
        interrupted = False
        try:
            user_input = input(_color("\n> ", Colors.GREEN + Colors.BOLD)).strip()
        except EOFError:
            print(_color("\nGoodbye!", Colors.CYAN))
            break
        except KeyboardInterrupt:
            print()
            continue

        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            if _handle_slash_command(user_input, agent):
                continue

        # Send to agent
        try:
            response = agent.chat(user_input)
            if response:
                print(f"\n{response}")

            # Show token stats
            stats = agent.get_stats()
            cost_str = f"${stats['estimated_cost']:.4f}" if stats['estimated_cost'] > 0 else "free"
            print(_color(
                f"\n  → ✓ done ({stats['total_tool_calls']} tool calls, "
                f"{stats['input_tokens']:,} + {stats['output_tokens']:,} tokens, "
                f"{cost_str})",
                Colors.DIM
            ))
        except KeyboardInterrupt:
            print(_color("\n  Interrupted.", Colors.YELLOW))
        except Exception as e:
            print(_color(f"\n  Error: {e}", Colors.RED))


def _run_self_test():
    """Run a basic self-test."""
    print(_color("Running PyOz self-test...", Colors.BOLD))
    errors = 0

    # Test file tools
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.tools.file_tools import write_file, read_file, edit_file, list_directory, search_files

        # write + read
        path = os.path.join(tmpdir, "test.txt")
        write_file(path, "hello world")
        content = read_file(path)
        assert content == "hello world", f"read_file failed: {content}"
        print(_color("  ✓ write_file + read_file", Colors.GREEN))

        # edit
        edit_file(path, "hello", "goodbye")
        content = read_file(path)
        assert content == "goodbye world", f"edit_file failed: {content}"
        print(_color("  ✓ edit_file", Colors.GREEN))

        # list_directory
        entries = list_directory(tmpdir)
        assert any(e["name"] == "test.txt" for e in entries)
        print(_color("  ✓ list_directory", Colors.GREEN))

        # search_files
        results = search_files("goodbye", tmpdir)
        assert len(results) > 0
        print(_color("  ✓ search_files", Colors.GREEN))

    # Test command tools
    from pyoz.tools.command_tools import run_command
    result = run_command("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]
    print(_color("  ✓ run_command", Colors.GREEN))

    # Test blocked commands
    try:
        run_command("rm -rf /")
        errors += 1
        print(_color("  ✗ blocked command not caught", Colors.RED))
    except PermissionError:
        print(_color("  ✓ dangerous commands blocked", Colors.GREEN))

    # Test git tools
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.tools.git_tools import git_init, git_commit, git_log, git_diff, is_git_repo
        git_init(tmpdir)
        assert is_git_repo(tmpdir)
        print(_color("  ✓ git_init", Colors.GREEN))

        # write a file and commit
        test_file = os.path.join(tmpdir, "code.py")
        write_file(test_file, "x = 1\n")
        result = git_commit("test commit", tmpdir)
        assert "committed" in result
        print(_color("  ✓ git_commit", Colors.GREEN))

        commits = git_log(5, tmpdir)
        assert len(commits) >= 2  # initial + test
        print(_color("  ✓ git_log", Colors.GREEN))

    # Test AST indexer
    with tempfile.TemporaryDirectory() as tmpdir:
        from pyoz.indexer.ast_indexer import ASTIndexer
        # Write a Python file
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
        assert indexer.symbol_count() >= 3  # class, 2 methods, function
        print(_color("  ✓ AST indexer (Python)", Colors.GREEN))

    # Test static configs
    from pyoz.tools.context_tools import static_config
    config = static_config("java", "myapp")
    assert "pom.xml" in config
    assert "myapp" in config
    print(_color("  ✓ static_config", Colors.GREEN))

    # Test tool registry
    from pyoz.tools.registry import get_tool_definitions_claude, get_tool_definitions_openai
    claude_tools = get_tool_definitions_claude()
    openai_tools = get_tool_definitions_openai()
    assert len(claude_tools) == 13
    assert len(openai_tools) == 13
    print(_color("  ✓ tool registry (13 tools)", Colors.GREEN))

    if errors == 0:
        print(_color("\n  All tests passed! ✓", Colors.GREEN + Colors.BOLD))
    else:
        print(_color(f"\n  {errors} test(s) failed ✗", Colors.RED + Colors.BOLD))
        sys.exit(1)


if __name__ == "__main__":
    main()
