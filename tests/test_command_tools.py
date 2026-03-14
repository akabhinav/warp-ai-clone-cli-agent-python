"""Tests for command tools."""

import os
import tempfile
import pytest

from pyoz.tools.command_tools import run_command


class TestRunCommand:
    def test_basic_command(self):
        result = run_command("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_stderr(self):
        result = run_command("echo error >&2")
        assert "error" in result["stderr"]

    def test_exit_code(self):
        result = run_command("exit 42")
        assert result["exit_code"] == 42

    def test_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_command("pwd", cwd=tmpdir)
            assert result["exit_code"] == 0

    def test_blocked_rm_rf_root(self):
        with pytest.raises(PermissionError, match="Blocked"):
            run_command("rm -rf /")

    def test_blocked_rm_rf_root_space(self):
        with pytest.raises(PermissionError, match="Blocked"):
            run_command("rm -rf / --no-preserve-root")

    def test_blocked_mkfs(self):
        with pytest.raises(PermissionError, match="Blocked"):
            run_command("mkfs.ext4 /dev/sda")

    def test_missing_cwd(self):
        with pytest.raises(FileNotFoundError):
            run_command("echo hi", cwd="/nonexistent/path/abc123")

    def test_timeout_returns_error(self):
        result = run_command("sleep 200")
        # Should timeout and return error (120s timeout)
        # In test we just check it doesn't hang forever
        assert result["exit_code"] == -1 or result["stderr"]

    def test_multiline_output(self):
        result = run_command("echo 'line1\nline2\nline3'")
        assert result["exit_code"] == 0
        assert "line1" in result["stdout"]
