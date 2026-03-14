"""Git tools — init, commit, diff, undo, log."""

import os
import subprocess
from typing import Any

DEFAULT_GITIGNORE = """# PyOz defaults
__pycache__/
*.pyc
*.pyo
.venv/
venv/
node_modules/
target/
build/
dist/
*.egg-info/
.idea/
.vscode/
*.swp
*.swo
.DS_Store
Thumbs.db
.env
"""


def _git(args: list[str], cwd: str | None = None) -> tuple[str, str, int]:
    """Run a git command and return (stdout, stderr, returncode)."""
    work_dir = cwd or os.getcwd()
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=work_dir,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def git_init(cwd: str | None = None) -> str:
    """Initialize git repo with .gitignore and initial commit."""
    work_dir = cwd or os.getcwd()
    _git(["init"], work_dir)
    _git(["config", "user.email", "pyoz@agent"], work_dir)
    _git(["config", "user.name", "PyOz"], work_dir)
    gitignore_path = os.path.join(work_dir, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w") as f:
            f.write(DEFAULT_GITIGNORE)
    _git(["config", "commit.gpgsign", "false"], work_dir)
    _git(["add", "."], work_dir)
    _git(["commit", "-m", "pyoz: initial commit"], work_dir)
    return "initialized git repo"


def git_commit(message: str, cwd: str | None = None) -> str:
    """Stage all changes and commit."""
    work_dir = cwd or os.getcwd()
    _git(["add", "-A"], work_dir)
    stdout, stderr, code = _git(["commit", "-m", message], work_dir)
    if code != 0:
        if "nothing to commit" in stdout or "nothing to commit" in stderr:
            return "nothing to commit"
        raise RuntimeError(f"git commit failed: {stderr}")
    # extract short hash
    hash_out, _, _ = _git(["rev-parse", "--short", "HEAD"], work_dir)
    return f"committed: {message} ({hash_out})"


def auto_commit(file_path: str, action: str, cwd: str | None = None) -> str:
    """Auto-commit after write/edit with descriptive message."""
    work_dir = cwd or os.getcwd()
    rel_path = os.path.relpath(file_path, work_dir)
    basename = os.path.basename(file_path)
    message = f"pyoz: {action} {basename}"
    _git(["add", file_path], work_dir)
    stdout, stderr, code = _git(["commit", "-m", message], work_dir)
    if code != 0:
        return f"auto-commit skipped: {stderr}"
    hash_out, _, _ = _git(["rev-parse", "--short", "HEAD"], work_dir)
    return f"auto-committed: {message} ({hash_out})"


def git_diff(cwd: str | None = None) -> str:
    """Show uncommitted changes."""
    work_dir = cwd or os.getcwd()
    stdout, _, _ = _git(["diff"], work_dir)
    staged, _, _ = _git(["diff", "--cached"], work_dir)
    result = ""
    if staged:
        result += "=== Staged ===\n" + staged + "\n"
    if stdout:
        result += "=== Unstaged ===\n" + stdout + "\n"
    return result or "no changes"


def git_undo(cwd: str | None = None) -> str:
    """Revert the last commit."""
    work_dir = cwd or os.getcwd()
    hash_out, _, _ = _git(["rev-parse", "--short", "HEAD"], work_dir)
    stdout, stderr, code = _git(["revert", "HEAD", "--no-edit"], work_dir)
    if code != 0:
        raise RuntimeError(f"git revert failed: {stderr}")
    return f"reverted commit {hash_out}"


def git_log(n: int = 10, cwd: str | None = None) -> list[dict[str, str]]:
    """Return last N commits."""
    work_dir = cwd or os.getcwd()
    fmt = "%H%n%s%n%ai%n---"
    stdout, _, code = _git(["log", f"-{n}", f"--format={fmt}"], work_dir)
    if code != 0 or not stdout.strip():
        return []
    commits = []
    entries = stdout.split("---")
    for entry in entries:
        lines = entry.strip().splitlines()
        if len(lines) >= 3:
            commits.append({
                "hash": lines[0][:8],
                "message": lines[1],
                "time": lines[2],
            })
    return commits


def is_git_repo(cwd: str | None = None) -> bool:
    """Check if the current directory is inside a git repo."""
    _, _, code = _git(["rev-parse", "--git-dir"], cwd)
    return code == 0
