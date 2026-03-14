"""Git workflow tools — automated PR lifecycle, branch management, and code review.

Automates the full pull request workflow: create branches, push, create PRs,
review, approve, merge, and clean up. Works with GitHub (gh CLI) and GitLab
(glab CLI). Enables fully autonomous code → commit → PR → merge pipelines.

Requires: git + gh (GitHub CLI) or glab (GitLab CLI) installed and authenticated.
"""

import os
import shutil
import subprocess
from typing import Any

COMMAND_TIMEOUT = 120


def _run(args: list[str], cwd: str | None = None, timeout: int = COMMAND_TIMEOUT) -> dict[str, Any]:
    """Run a command and return result dict."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1}


def _fmt(r: dict[str, Any]) -> str:
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    elif r["stderr"] and r["exit_code"] == 0:
        parts.append(r["stderr"])
    if r["exit_code"] != 0 and not parts:
        parts.append(f"Exit code: {r['exit_code']}")
    return "\n".join(parts) if parts else "Done."


def _detect_platform() -> str:
    """Detect if we're in a GitHub or GitLab repo."""
    if shutil.which("gh"):
        return "github"
    if shutil.which("glab"):
        return "gitlab"
    return "unknown"


def _git(args: list[str], cwd: str) -> dict[str, Any]:
    """Run a git command."""
    return _run(["git"] + args, cwd)


def git_workflow_tool(
    action: str,
    target: str = "",
    branch: str = "",
    title: str = "",
    body: str = "",
    args: str = "",
    cwd: str | None = None,
) -> str:
    """Automated git workflow: branches, PRs, reviews, merges.

    Args:
        action: One of:
          Branch: create-branch, switch-branch, list-branches, delete-branch,
                  push, pull, fetch, rebase, merge-branch, stash, stash-pop
          PR: pr-create, pr-list, pr-view, pr-diff, pr-merge, pr-close,
              pr-review, pr-approve, pr-comment, pr-checkout
          Repo: clone, fork, repo-view, release-create, release-list
          Automation: auto-fix-pr, auto-branch-push-pr
        target: PR number, repo URL, branch name, or release tag
        branch: Branch name (for create-branch, pr-create base)
        title: PR title or release title
        body: PR body/description or release notes
        args: Additional flags (e.g. "--draft", "--squash", "--reviewer=user")
        cwd: Working directory
    """
    if not shutil.which("git"):
        return "Error: git not found. Install git first."

    action = action.lower().strip()
    work_dir = cwd or os.getcwd()
    extra = args.split() if args else []
    platform = _detect_platform()

    # ── Branch Management ─────────────────────────────────────

    if action == "create-branch":
        if not target:
            return "Error: 'target' (branch name) required"
        # Create and switch to new branch
        base = branch or "main"
        r = _git(["checkout", "-b", target, base], work_dir)
        if r["exit_code"] != 0:
            # Try without base
            r = _git(["checkout", "-b", target], work_dir)
        return _fmt(r)

    elif action == "switch-branch":
        if not target:
            return "Error: 'target' (branch name) required"
        return _fmt(_git(["checkout", target], work_dir))

    elif action == "list-branches":
        r = _git(["branch", "-a", "--sort=-committerdate"] + extra, work_dir)
        return _fmt(r)

    elif action == "delete-branch":
        if not target:
            return "Error: 'target' (branch name) required"
        # Delete local and optionally remote
        local = _git(["branch", "-D", target], work_dir)
        if "--remote" in extra or "-r" in extra:
            remote = _git(["push", "origin", "--delete", target], work_dir)
            return f"Local: {_fmt(local)}\nRemote: {_fmt(remote)}"
        return _fmt(local)

    elif action == "push":
        branch_name = target or ""
        if not branch_name:
            r = _git(["rev-parse", "--abbrev-ref", "HEAD"], work_dir)
            branch_name = r["stdout"].strip()
        cmd = ["push", "-u", "origin", branch_name] + extra
        return _fmt(_git(cmd, work_dir))

    elif action == "pull":
        branch_name = target or ""
        if branch_name:
            return _fmt(_git(["pull", "origin", branch_name] + extra, work_dir))
        return _fmt(_git(["pull"] + extra, work_dir))

    elif action == "fetch":
        return _fmt(_git(["fetch", "--all", "--prune"] + extra, work_dir))

    elif action == "rebase":
        base = target or "main"
        return _fmt(_git(["rebase", base] + extra, work_dir))

    elif action == "merge-branch":
        if not target:
            return "Error: 'target' (branch to merge) required"
        return _fmt(_git(["merge", target] + extra, work_dir))

    elif action == "stash":
        msg = ["-m", title] if title else []
        return _fmt(_git(["stash", "push"] + msg + extra, work_dir))

    elif action == "stash-pop":
        return _fmt(_git(["stash", "pop"] + extra, work_dir))

    # ── Pull Request Lifecycle ────────────────────────────────

    elif action == "pr-create":
        if platform == "github":
            if not shutil.which("gh"):
                return "Error: GitHub CLI (gh) not found. Install from https://cli.github.com/"
            cmd = ["gh", "pr", "create"]
            if title:
                cmd.extend(["--title", title])
            if body:
                cmd.extend(["--body", body])
            if branch:
                cmd.extend(["--base", branch])
            cmd += extra
            return _fmt(_run(cmd, work_dir))
        elif platform == "gitlab":
            cmd = ["glab", "mr", "create"]
            if title:
                cmd.extend(["--title", title])
            if body:
                cmd.extend(["--description", body])
            if branch:
                cmd.extend(["--target-branch", branch])
            cmd += extra
            return _fmt(_run(cmd, work_dir))
        else:
            return "Error: Neither gh (GitHub) nor glab (GitLab) CLI found. Install one to create PRs."

    elif action == "pr-list":
        if platform == "github":
            cmd = ["gh", "pr", "list"] + extra
            return _fmt(_run(cmd, work_dir))
        elif platform == "gitlab":
            cmd = ["glab", "mr", "list"] + extra
            return _fmt(_run(cmd, work_dir))
        return "Error: gh or glab CLI required."

    elif action == "pr-view":
        if not target:
            return "Error: 'target' (PR number) required"
        if platform == "github":
            return _fmt(_run(["gh", "pr", "view", target] + extra, work_dir))
        elif platform == "gitlab":
            return _fmt(_run(["glab", "mr", "view", target] + extra, work_dir))
        return "Error: gh or glab CLI required."

    elif action == "pr-diff":
        if not target:
            return "Error: 'target' (PR number) required"
        if platform == "github":
            return _fmt(_run(["gh", "pr", "diff", target] + extra, work_dir))
        elif platform == "gitlab":
            return _fmt(_run(["glab", "mr", "diff", target] + extra, work_dir))
        return "Error: gh or glab CLI required."

    elif action == "pr-merge":
        if not target:
            return "Error: 'target' (PR number) required"
        if platform == "github":
            cmd = ["gh", "pr", "merge", target]
            # Default to squash merge if not specified
            if "--merge" not in extra and "--rebase" not in extra and "--squash" not in extra:
                cmd.append("--squash")
            cmd.append("--delete-branch")
            cmd += extra
            return _fmt(_run(cmd, work_dir))
        elif platform == "gitlab":
            cmd = ["glab", "mr", "merge", target, "--squash", "--remove-source-branch"] + extra
            return _fmt(_run(cmd, work_dir))
        return "Error: gh or glab CLI required."

    elif action == "pr-close":
        if not target:
            return "Error: 'target' (PR number) required"
        if platform == "github":
            return _fmt(_run(["gh", "pr", "close", target] + extra, work_dir))
        elif platform == "gitlab":
            return _fmt(_run(["glab", "mr", "close", target] + extra, work_dir))
        return "Error: gh or glab CLI required."

    elif action == "pr-review":
        if not target:
            return "Error: 'target' (PR number) required"
        if platform == "github":
            cmd = ["gh", "pr", "review", target]
            if body:
                cmd.extend(["--body", body])
            cmd += extra
            return _fmt(_run(cmd, work_dir))
        return "Error: GitHub CLI (gh) required for reviews."

    elif action == "pr-approve":
        if not target:
            return "Error: 'target' (PR number) required"
        if platform == "github":
            cmd = ["gh", "pr", "review", target, "--approve"]
            if body:
                cmd.extend(["--body", body])
            return _fmt(_run(cmd, work_dir))
        elif platform == "gitlab":
            return _fmt(_run(["glab", "mr", "approve", target], work_dir))
        return "Error: gh or glab CLI required."

    elif action == "pr-comment":
        if not target or not body:
            return "Error: 'target' (PR number) and 'body' (comment text) required"
        if platform == "github":
            return _fmt(_run(["gh", "pr", "comment", target, "--body", body], work_dir))
        elif platform == "gitlab":
            return _fmt(_run(["glab", "mr", "note", target, "-m", body], work_dir))
        return "Error: gh or glab CLI required."

    elif action == "pr-checkout":
        if not target:
            return "Error: 'target' (PR number) required"
        if platform == "github":
            return _fmt(_run(["gh", "pr", "checkout", target] + extra, work_dir))
        elif platform == "gitlab":
            return _fmt(_run(["glab", "mr", "checkout", target] + extra, work_dir))
        return "Error: gh or glab CLI required."

    # ── Repo Operations ───────────────────────────────────────

    elif action == "clone":
        if not target:
            return "Error: 'target' (repo URL or owner/repo) required"
        cmd = ["git", "clone", target] + extra
        return _fmt(_run(cmd, work_dir, timeout=300))

    elif action == "fork":
        if platform == "github":
            cmd = ["gh", "repo", "fork"]
            if target:
                cmd.append(target)
            cmd.append("--clone")
            cmd += extra
            return _fmt(_run(cmd, work_dir, timeout=300))
        return "Error: GitHub CLI (gh) required for forking."

    elif action == "repo-view":
        if platform == "github":
            cmd = ["gh", "repo", "view"]
            if target:
                cmd.append(target)
            cmd += extra
            return _fmt(_run(cmd, work_dir))
        return "Error: GitHub CLI (gh) required."

    elif action == "release-create":
        if not target:
            return "Error: 'target' (tag name) required"
        if platform == "github":
            cmd = ["gh", "release", "create", target]
            if title:
                cmd.extend(["--title", title])
            if body:
                cmd.extend(["--notes", body])
            cmd += extra
            return _fmt(_run(cmd, work_dir))
        elif platform == "gitlab":
            cmd = ["glab", "release", "create", target]
            if title:
                cmd.extend(["--name", title])
            if body:
                cmd.extend(["--notes", body])
            cmd += extra
            return _fmt(_run(cmd, work_dir))
        return "Error: gh or glab CLI required."

    elif action == "release-list":
        if platform == "github":
            return _fmt(_run(["gh", "release", "list"] + extra, work_dir))
        elif platform == "gitlab":
            return _fmt(_run(["glab", "release", "list"] + extra, work_dir))
        return "Error: gh or glab CLI required."

    # ── Automation Composites ─────────────────────────────────

    elif action == "auto-branch-push-pr":
        # All-in-one: create branch, push, create PR
        if not target:
            return "Error: 'target' (branch name) required"
        if not title:
            return "Error: 'title' (PR title) required"

        results = []

        # 1. Create branch
        base = branch or "main"
        r = _git(["checkout", "-b", target], work_dir)
        results.append(f"1. Create branch '{target}': {'OK' if r['exit_code'] == 0 else _fmt(r)}")

        # 2. Stage and commit any changes
        _git(["add", "-A"], work_dir)
        r = _git(["commit", "-m", title, "--allow-empty"], work_dir)
        results.append(f"2. Commit: {'OK' if r['exit_code'] == 0 else _fmt(r)}")

        # 3. Push
        r = _git(["push", "-u", "origin", target], work_dir)
        if r["exit_code"] != 0:
            results.append(f"3. Push: FAILED — {_fmt(r)}")
            return "\n".join(results)
        results.append("3. Push: OK")

        # 4. Create PR
        if platform == "github":
            cmd = ["gh", "pr", "create", "--title", title, "--base", base]
            if body:
                cmd.extend(["--body", body])
            cmd += extra
            r = _run(cmd, work_dir)
            results.append(f"4. PR Created: {_fmt(r)}")
        elif platform == "gitlab":
            cmd = ["glab", "mr", "create", "--title", title, "--target-branch", base, "--yes"]
            if body:
                cmd.extend(["--description", body])
            cmd += extra
            r = _run(cmd, work_dir)
            results.append(f"4. MR Created: {_fmt(r)}")
        else:
            results.append("4. PR: Skipped (no gh/glab CLI)")

        return "\n".join(results)

    elif action == "auto-fix-pr":
        # Checkout a PR, let the agent work on it, push fixes
        if not target:
            return "Error: 'target' (PR number) required"

        results = []

        # 1. Checkout PR
        if platform == "github":
            r = _run(["gh", "pr", "checkout", target], work_dir)
        elif platform == "gitlab":
            r = _run(["glab", "mr", "checkout", target], work_dir)
        else:
            return "Error: gh or glab CLI required."

        if r["exit_code"] != 0:
            return f"Failed to checkout PR #{target}: {_fmt(r)}"
        results.append(f"1. Checked out PR #{target}: OK")

        # 2. Get current branch
        r = _git(["rev-parse", "--abbrev-ref", "HEAD"], work_dir)
        pr_branch = r["stdout"].strip()
        results.append(f"2. On branch: {pr_branch}")

        # 3. Return info for the agent to work with
        results.append(f"3. Ready for fixes. After making changes:")
        results.append(f"   - Use git_commit to commit changes")
        results.append(f"   - Use git_workflow_tool push to push to '{pr_branch}'")
        results.append(f"   - Use pr-comment to leave review notes")

        return "\n".join(results)

    else:
        return (
            "Error: Unknown action. Available actions:\n"
            "  Branch:     create-branch, switch-branch, list-branches, delete-branch,\n"
            "              push, pull, fetch, rebase, merge-branch, stash, stash-pop\n"
            "  PR:         pr-create, pr-list, pr-view, pr-diff, pr-merge, pr-close,\n"
            "              pr-review, pr-approve, pr-comment, pr-checkout\n"
            "  Repo:       clone, fork, repo-view, release-create, release-list\n"
            "  Automation: auto-branch-push-pr, auto-fix-pr"
        )
