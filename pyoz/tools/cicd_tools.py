"""CI/CD tools — trigger, monitor, and manage CI/CD pipelines.

Supports GitHub Actions, GitLab CI, and generic webhook-based CI systems.
Enables autonomous build → test → deploy pipelines where the agent can
trigger workflows, watch for results, and act on failures.

Requires: gh (GitHub CLI) or glab (GitLab CLI) installed and authenticated.
"""

import json
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


def _detect_ci_platform(cwd: str) -> str:
    """Detect CI platform from repo files and available tools."""
    if os.path.isdir(os.path.join(cwd, ".github", "workflows")):
        return "github"
    if os.path.isfile(os.path.join(cwd, ".gitlab-ci.yml")):
        return "gitlab"
    if shutil.which("gh"):
        return "github"
    if shutil.which("glab"):
        return "gitlab"
    return "unknown"


def cicd_tool(
    action: str,
    target: str = "",
    workflow: str = "",
    branch: str = "",
    args: str = "",
    cwd: str | None = None,
) -> str:
    """CI/CD pipeline management: trigger, monitor, and manage workflows.

    Args:
        action: One of:
          GitHub Actions:
            workflow-list: List all workflows
            workflow-run: Trigger a workflow (target=workflow file/name)
            run-list: List recent workflow runs
            run-view: View a specific run (target=run ID)
            run-watch: Watch a run until completion (target=run ID)
            run-logs: Download and view run logs (target=run ID)
            run-rerun: Re-run a failed run (target=run ID)
            run-cancel: Cancel an in-progress run (target=run ID)
            check-status: Check CI status of current branch or PR
          GitLab CI:
            pipeline-list: List recent pipelines
            pipeline-view: View pipeline details (target=pipeline ID)
            pipeline-create: Trigger a new pipeline
            pipeline-cancel: Cancel a running pipeline (target=pipeline ID)
            pipeline-retry: Retry failed jobs (target=pipeline ID)
            job-list: List jobs for a pipeline (target=pipeline ID)
            job-log: View job log (target=job ID)
          General:
            status: Quick CI status check for current branch
            wait: Wait for CI to pass on current branch (blocks up to 10 min)
        target: Run ID, pipeline ID, job ID, or workflow name
        workflow: Workflow file name (e.g. "ci.yml", "deploy.yml")
        branch: Branch to trigger workflow on (default: current)
        args: Additional flags or workflow inputs as JSON (e.g. '{"env": "prod"}')
        cwd: Working directory
    """
    work_dir = cwd or os.getcwd()
    action = action.lower().strip()
    extra = args.split() if args and not args.strip().startswith("{") else []
    platform = _detect_ci_platform(work_dir)

    # ── GitHub Actions ────────────────────────────────────────

    if action == "workflow-list":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        return _fmt(_run(["gh", "workflow", "list"] + extra, work_dir))

    elif action == "workflow-run":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        wf = target or workflow
        if not wf:
            return "Error: 'target' or 'workflow' (workflow file name, e.g. 'ci.yml') required"
        cmd = ["gh", "workflow", "run", wf]
        if branch:
            cmd.extend(["--ref", branch])
        # Parse JSON inputs
        if args and args.strip().startswith("{"):
            try:
                inputs = json.loads(args)
                for key, value in inputs.items():
                    cmd.extend(["-f", f"{key}={value}"])
            except json.JSONDecodeError:
                return "Error: 'args' must be valid JSON for workflow inputs"
        else:
            cmd += extra
        return _fmt(_run(cmd, work_dir))

    elif action == "run-list":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        cmd = ["gh", "run", "list", "--limit", "15"]
        if workflow:
            cmd.extend(["--workflow", workflow])
        if branch:
            cmd.extend(["--branch", branch])
        cmd += extra
        return _fmt(_run(cmd, work_dir))

    elif action == "run-view":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        if not target:
            return "Error: 'target' (run ID) required"
        return _fmt(_run(["gh", "run", "view", target] + extra, work_dir))

    elif action == "run-watch":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        if not target:
            return "Error: 'target' (run ID) required"
        return _fmt(_run(["gh", "run", "watch", target, "--exit-status"] + extra, work_dir, timeout=600))

    elif action == "run-logs":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        if not target:
            return "Error: 'target' (run ID) required"
        r = _run(["gh", "run", "view", target, "--log-failed"] + extra, work_dir)
        if r["exit_code"] != 0 or not r["stdout"]:
            # If no failed logs, get all logs
            r = _run(["gh", "run", "view", target, "--log"] + extra, work_dir)
        output = _fmt(r)
        # Truncate if too long
        lines = output.split("\n")
        if len(lines) > 200:
            return "\n".join(lines[:100] + ["", f"... ({len(lines) - 200} lines omitted) ...", ""] + lines[-100:])
        return output

    elif action == "run-rerun":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        if not target:
            return "Error: 'target' (run ID) required"
        # Try rerun-failed first, fallback to full rerun
        r = _run(["gh", "run", "rerun", target, "--failed"] + extra, work_dir)
        if r["exit_code"] != 0:
            r = _run(["gh", "run", "rerun", target] + extra, work_dir)
        return _fmt(r)

    elif action == "run-cancel":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        if not target:
            return "Error: 'target' (run ID) required"
        return _fmt(_run(["gh", "run", "cancel", target], work_dir))

    elif action == "check-status":
        if not shutil.which("gh"):
            return "Error: GitHub CLI (gh) not found."
        # Check status of current branch's latest commit
        cmd = ["gh", "pr", "checks"]
        if target:
            cmd.append(target)
        cmd += extra
        return _fmt(_run(cmd, work_dir))

    # ── GitLab CI ─────────────────────────────────────────────

    elif action == "pipeline-list":
        if not shutil.which("glab"):
            return "Error: GitLab CLI (glab) not found."
        cmd = ["glab", "ci", "list"] + extra
        return _fmt(_run(cmd, work_dir))

    elif action == "pipeline-view":
        if not shutil.which("glab"):
            return "Error: GitLab CLI (glab) not found."
        if not target:
            return "Error: 'target' (pipeline ID) required"
        return _fmt(_run(["glab", "ci", "view", target] + extra, work_dir))

    elif action == "pipeline-create":
        if not shutil.which("glab"):
            return "Error: GitLab CLI (glab) not found."
        cmd = ["glab", "ci", "run"]
        if branch:
            cmd.extend(["-b", branch])
        # Parse JSON variables
        if args and args.strip().startswith("{"):
            try:
                variables = json.loads(args)
                for key, value in variables.items():
                    cmd.extend(["--variables", f"{key}:{value}"])
            except json.JSONDecodeError:
                return "Error: 'args' must be valid JSON for pipeline variables"
        else:
            cmd += extra
        return _fmt(_run(cmd, work_dir))

    elif action == "pipeline-cancel":
        if not shutil.which("glab"):
            return "Error: GitLab CLI (glab) not found."
        if not target:
            return "Error: 'target' (pipeline ID) required"
        return _fmt(_run(["glab", "ci", "cancel", target], work_dir))

    elif action == "pipeline-retry":
        if not shutil.which("glab"):
            return "Error: GitLab CLI (glab) not found."
        if not target:
            return "Error: 'target' (pipeline ID) required"
        return _fmt(_run(["glab", "ci", "retry", target], work_dir))

    elif action == "job-list":
        if not shutil.which("glab"):
            return "Error: GitLab CLI (glab) not found."
        cmd = ["glab", "ci", "list"]
        if target:
            cmd.extend(["--pipeline-id", target])
        return _fmt(_run(cmd, work_dir))

    elif action == "job-log":
        if not shutil.which("glab"):
            return "Error: GitLab CLI (glab) not found."
        if not target:
            return "Error: 'target' (job ID) required"
        return _fmt(_run(["glab", "ci", "trace", target], work_dir))

    # ── General / Cross-Platform ──────────────────────────────

    elif action == "status":
        results = []

        if platform == "github" and shutil.which("gh"):
            r = _run(["gh", "pr", "checks"], work_dir)
            if r["exit_code"] == 0 and r["stdout"]:
                results.append("GitHub Actions checks:\n" + r["stdout"])
            else:
                # Try run list for current branch
                r2 = _run(["gh", "run", "list", "--limit", "5"], work_dir)
                if r2["exit_code"] == 0:
                    results.append("Recent runs:\n" + r2["stdout"])

        elif platform == "gitlab" and shutil.which("glab"):
            r = _run(["glab", "ci", "list", "--per-page", "5"], work_dir)
            if r["exit_code"] == 0:
                results.append("GitLab pipelines:\n" + r["stdout"])

        if not results:
            return "No CI/CD status available. Ensure gh or glab CLI is installed and authenticated."
        return "\n\n".join(results)

    elif action == "wait":
        # Wait for CI to pass on current branch
        if platform == "github" and shutil.which("gh"):
            # Get latest run
            r = _run(["gh", "run", "list", "--limit", "1", "--json", "databaseId,status"], work_dir)
            if r["exit_code"] == 0 and r["stdout"]:
                try:
                    runs = json.loads(r["stdout"])
                    if runs:
                        run_id = str(runs[0]["databaseId"])
                        return _fmt(_run(
                            ["gh", "run", "watch", run_id, "--exit-status"],
                            work_dir, timeout=600
                        ))
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass
            return "No active runs found to wait for."

        elif platform == "gitlab" and shutil.which("glab"):
            return _fmt(_run(["glab", "ci", "view", "--wait"], work_dir, timeout=600))

        return "Error: gh or glab CLI required."

    else:
        return (
            "Error: Unknown action. Available actions:\n"
            "  GitHub Actions:\n"
            "    workflow-list, workflow-run, run-list, run-view, run-watch,\n"
            "    run-logs, run-rerun, run-cancel, check-status\n"
            "  GitLab CI:\n"
            "    pipeline-list, pipeline-view, pipeline-create,\n"
            "    pipeline-cancel, pipeline-retry, job-list, job-log\n"
            "  General:\n"
            "    status, wait"
        )
