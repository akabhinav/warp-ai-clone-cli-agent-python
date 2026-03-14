"""Tests for git tools."""

import os
import tempfile
import subprocess
import pytest

from pyoz.tools.file_tools import write_file
from pyoz.tools.git_tools import (
    git_init, git_commit, auto_commit, git_diff, git_undo, git_log, is_git_repo,
)


@pytest.fixture
def git_repo():
    """Create a temporary git repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init", tmpdir], capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmpdir, capture_output=True)
        # Initial commit
        write_file(os.path.join(tmpdir, ".gitignore"), "__pycache__/\n")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmpdir, capture_output=True)
        yield tmpdir


class TestGitInit:
    def test_init_creates_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = git_init(tmpdir)
            assert result == "initialized git repo"
            assert is_git_repo(tmpdir)

    def test_init_creates_gitignore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_init(tmpdir)
            assert os.path.isfile(os.path.join(tmpdir, ".gitignore"))


class TestGitCommit:
    def test_commit(self, git_repo):
        write_file(os.path.join(git_repo, "test.py"), "x = 1\n")
        result = git_commit("add test.py", git_repo)
        assert "committed" in result
        assert "add test.py" in result

    def test_nothing_to_commit(self, git_repo):
        result = git_commit("empty", git_repo)
        assert "nothing to commit" in result


class TestAutoCommit:
    def test_auto_commit_after_write(self, git_repo):
        path = os.path.join(git_repo, "new.py")
        write_file(path, "y = 2\n")
        result = auto_commit(path, "create", git_repo)
        assert "auto-committed" in result or "auto-commit skipped" in result


class TestGitDiff:
    def test_no_changes(self, git_repo):
        result = git_diff(git_repo)
        assert result == "no changes"

    def test_with_changes(self, git_repo):
        write_file(os.path.join(git_repo, ".gitignore"), "__pycache__/\n*.pyc\n")
        result = git_diff(git_repo)
        assert "*.pyc" in result or "Unstaged" in result


class TestGitUndo:
    def test_undo_reverts(self, git_repo):
        path = os.path.join(git_repo, "undo_test.py")
        write_file(path, "z = 3\n")
        git_commit("add undo_test", git_repo)
        result = git_undo(git_repo)
        assert "reverted" in result
        assert not os.path.isfile(path)


class TestGitLog:
    def test_log_returns_commits(self, git_repo):
        commits = git_log(5, git_repo)
        assert len(commits) >= 1
        assert "hash" in commits[0]
        assert "message" in commits[0]

    def test_log_with_new_commit(self, git_repo):
        write_file(os.path.join(git_repo, "log_test.py"), "a = 1\n")
        git_commit("test log", git_repo)
        commits = git_log(5, git_repo)
        messages = [c["message"] for c in commits]
        assert "test log" in messages


class TestIsGitRepo:
    def test_is_repo(self, git_repo):
        assert is_git_repo(git_repo) is True

    def test_not_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_git_repo(tmpdir) is False
