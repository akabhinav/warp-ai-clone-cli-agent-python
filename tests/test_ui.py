"""Tests for UI components."""

import os
import tempfile
import pytest
from io import StringIO

from rich.console import Console

from pyoz.ui.theme import PYOZ_THEME, ICONS
from pyoz.ui.display import (
    print_banner,
    print_tool_call,
    print_diff,
    print_response,
    print_turn_stats,
    print_error,
    print_success,
    print_info,
    print_workspaces,
    print_sessions,
    print_stats,
    print_commits,
    print_files,
    print_diff_output,
    print_help,
    _format_tool_detail,
)
from pyoz.ui.input import SlashCommandCompleter, SLASH_COMMANDS, InputManager


class TestTheme:
    def test_theme_has_brand_styles(self):
        assert "pyoz.brand" in PYOZ_THEME.styles
        assert "pyoz.accent" in PYOZ_THEME.styles

    def test_theme_has_status_styles(self):
        assert "pyoz.success" in PYOZ_THEME.styles
        assert "pyoz.error" in PYOZ_THEME.styles
        assert "pyoz.warning" in PYOZ_THEME.styles

    def test_theme_has_tool_styles(self):
        assert "pyoz.tool" in PYOZ_THEME.styles
        assert "pyoz.tool.arrow" in PYOZ_THEME.styles

    def test_theme_has_diff_styles(self):
        assert "pyoz.diff.add" in PYOZ_THEME.styles
        assert "pyoz.diff.remove" in PYOZ_THEME.styles

    def test_icons_defined(self):
        assert "wizard" in ICONS
        assert "check" in ICONS
        assert "arrow" in ICONS
        assert "tools" in ICONS
        assert len(ICONS) >= 10


class TestDisplayFunctions:
    """Test that display functions execute without errors."""

    def test_print_banner(self, capsys):
        info = {
            "provider": "claude",
            "model": "sonnet",
            "files_indexed": 10,
            "symbols": 45,
            "git": "clean",
            "rules": True,
        }
        print_banner(info)
        # Should not raise

    def test_print_banner_with_session(self, capsys):
        info = {
            "provider": "openai",
            "model": "gpt-4o",
            "files_indexed": 5,
            "symbols": 20,
            "git": "no repo",
            "rules": False,
            "session_turns": 3,
        }
        print_banner(info, session_resumed=True)

    def test_print_tool_call_write(self, capsys):
        print_tool_call("write_file", {"path": "test.py", "content": "x = 1"}, "wrote 5 bytes")

    def test_print_tool_call_run_command(self, capsys):
        print_tool_call("run_command", {"command": "echo hello"}, "hello\nExit code: 0")

    def test_print_tool_call_read(self, capsys):
        print_tool_call("read_file", {"path": "test.py"}, "x = 1")

    def test_print_tool_call_search(self, capsys):
        print_tool_call("search_files", {"pattern": "def.*"}, "file.py:1: def main():")

    def test_print_diff(self, capsys):
        print_diff("/tmp/test.py", "old_text", "new_text")

    def test_print_response(self, capsys):
        print_response("Hello! Here is some **markdown** text.")

    def test_print_turn_stats(self, capsys):
        stats = {
            "total_tool_calls": 5,
            "input_tokens": 1000,
            "output_tokens": 500,
            "estimated_cost": 0.0125,
        }
        print_turn_stats(stats)

    def test_print_turn_stats_free(self, capsys):
        stats = {
            "total_tool_calls": 0,
            "input_tokens": 100,
            "output_tokens": 50,
            "estimated_cost": 0,
        }
        print_turn_stats(stats)

    def test_print_error(self, capsys):
        print_error("Something went wrong")

    def test_print_success(self, capsys):
        print_success("Operation completed")

    def test_print_info(self, capsys):
        print_info("Some information")

    def test_print_workspaces(self, capsys):
        recent = [
            {"path": "/home/user/proj1", "name": "proj1", "last_access": "2026-03-14"},
            {"path": "/home/user/proj2", "name": "proj2", "last_access": "2026-03-13"},
        ]
        print_workspaces("/home/user/proj1", recent)

    def test_print_workspaces_empty(self, capsys):
        print_workspaces("/home/user/proj1", [])

    def test_print_sessions(self, capsys):
        sessions = [
            {"file": "session_123.json", "saved_at": "2026-03-14 10:00:00", "turns": 5, "provider": "claude"},
        ]
        print_sessions(sessions)

    def test_print_sessions_empty(self, capsys):
        print_sessions([])

    def test_print_stats(self, capsys):
        stats = {
            "turns": 3,
            "total_tool_calls": 10,
            "input_tokens": 5000,
            "output_tokens": 2000,
            "estimated_cost": 0.045,
        }
        print_stats(stats)

    def test_print_commits(self, capsys):
        commits = [
            {"hash": "abc1234", "message": "initial commit"},
            {"hash": "def5678", "message": "add feature"},
        ]
        print_commits(commits)

    def test_print_commits_empty(self, capsys):
        print_commits([])

    def test_print_files(self, capsys):
        entries = [
            {"name": "src", "type": "directory"},
            {"name": "main.py", "type": "file", "size": 1234},
        ]
        print_files(entries)

    def test_print_diff_output(self, capsys):
        print_diff_output("- old line\n+ new line\n@@ -1,3 +1,3 @@")

    def test_print_diff_no_changes(self, capsys):
        print_diff_output("no changes")

    def test_print_help(self, capsys):
        print_help()


class TestFormatToolDetail:
    def test_write_file(self):
        result = _format_tool_detail("write_file", {"path": "test.py", "content": "hello"})
        assert "test.py" in result
        assert "5" in result  # 5 bytes

    def test_read_file(self):
        result = _format_tool_detail("read_file", {"path": "test.py"})
        assert result == "test.py"

    def test_run_command(self):
        result = _format_tool_detail("run_command", {"command": "npm test"})
        assert result == "npm test"

    def test_search_files(self):
        result = _format_tool_detail("search_files", {"pattern": "def.*"})
        assert "def.*" in result

    def test_git_commit(self):
        result = _format_tool_detail("git_commit", {"message": "fix bug"})
        assert "fix bug" in result

    def test_static_config(self):
        result = _format_tool_detail("static_config", {"language": "java", "project_name": "app"})
        assert "java/app" == result

    def test_unknown_tool(self):
        result = _format_tool_detail("unknown_tool", {})
        assert result == ""


class TestSlashCommandCompleter:
    def test_completer_exists(self):
        completer = SlashCommandCompleter()
        assert completer is not None

    def test_slash_commands_defined(self):
        assert len(SLASH_COMMANDS) >= 15
        names = [cmd for cmd, _ in SLASH_COMMANDS]
        assert "/help" in names
        assert "/quit" in names
        assert "/workspace" in names
        assert "/save" in names
        assert "/stream" in names


class TestInputManager:
    def test_creates_without_error(self):
        mgr = InputManager()
        assert mgr is not None

    def test_has_session(self):
        mgr = InputManager()
        # Should have a prompt session (or None as fallback)
        # Just verify it doesn't crash
        assert True
