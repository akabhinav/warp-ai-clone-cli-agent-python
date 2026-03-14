"""Scheduled task tools — manage cron jobs (Unix) and Task Scheduler (Windows).

Windows: PowerShell ScheduledTasks module (Get-ScheduledTask, Register-ScheduledTask)
Linux: crontab
macOS: launchd plist + crontab fallback
"""

import os
import subprocess
import tempfile
from typing import Any

from pyoz.platform import IS_WINDOWS, IS_MACOS, IS_LINUX


def _run(args: list[str], timeout: int = 30, input_text: str | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=input_text)
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"Command not found: {args[0]}", "exit_code": -1}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timed out", "exit_code": -1}


def _fmt(r: dict[str, Any]) -> str:
    parts = []
    if r["stdout"]:
        parts.append(r["stdout"])
    if r["stderr"] and r["exit_code"] != 0:
        parts.append(f"STDERR: {r['stderr']}")
    if r["exit_code"] != 0 and not parts:
        parts.append(f"Failed (exit code {r['exit_code']})")
    return "\n".join(parts) if parts else "Done."


def schedule_task(action: str, name: str = "", command: str = "",
                  schedule: str = "", description: str = "") -> str:
    """Manage scheduled tasks / cron jobs.

    Args:
        action: One of: list, create, delete, enable, disable, status, run
        name: Task name (required for create/delete/enable/disable/status/run)
        command: Command to execute (required for create)
        schedule: Schedule expression:
          - Cron format: "0 9 * * *" (Unix, 5 fields: min hour day month weekday)
          - Windows keywords: "daily 09:00", "hourly", "weekly Monday 09:00",
            "once 2026-03-15 14:00", "startup", "logon"
        description: Task description (optional)
    """
    action = action.lower().strip()

    if action == "list":
        return _list_tasks(name)
    elif action == "create":
        if not name:
            return "Error: 'name' required for create"
        if not command:
            return "Error: 'command' required for create"
        if not schedule:
            return "Error: 'schedule' required for create"
        return _create_task(name, command, schedule, description)
    elif action == "delete":
        if not name:
            return "Error: 'name' required for delete"
        return _delete_task(name)
    elif action == "enable":
        if not name:
            return "Error: 'name' required for enable"
        return _enable_task(name)
    elif action == "disable":
        if not name:
            return "Error: 'name' required for disable"
        return _disable_task(name)
    elif action == "status":
        if not name:
            return "Error: 'name' required for status"
        return _task_status(name)
    elif action == "run":
        if not name:
            return "Error: 'name' required for run"
        return _run_task(name)
    else:
        return "Error: Unknown action. Use: list, create, delete, enable, disable, status, run"


# --- List ---

def _list_tasks(filter_text: str = "") -> str:
    if IS_WINDOWS:
        cmd = ["powershell", "-NoProfile", "-Command"]
        if filter_text:
            cmd.append(
                f"Get-ScheduledTask | Where-Object {{ $_.TaskName -like '*{filter_text}*' }} | "
                "Select-Object TaskName, State, @{N='NextRun';E={($_ | Get-ScheduledTaskInfo).NextRunTime}} | "
                "Format-Table -AutoSize"
            )
        else:
            cmd.append(
                "Get-ScheduledTask | Select-Object TaskName, State, TaskPath | "
                "Format-Table -AutoSize"
            )
        r = _run(cmd)
    else:
        # Unix — show crontab
        r = _run(["crontab", "-l"])
        if r["exit_code"] != 0:
            return "No cron jobs found (crontab empty or not configured)."
        if filter_text and r["stdout"]:
            lines = r["stdout"].splitlines()
            matched = [l for l in lines if filter_text.lower() in l.lower()]
            return "\n".join(matched) if matched else f"No cron jobs matching '{filter_text}'"

    output = r["stdout"]
    lines = output.splitlines()
    if len(lines) > 50:
        output = "\n".join(lines[:50]) + f"\n... ({len(lines) - 50} more)"
    return output if output else "No scheduled tasks found."


# --- Create ---

def _create_task(name: str, command: str, schedule: str, description: str) -> str:
    if IS_WINDOWS:
        return _create_windows_task(name, command, schedule, description)
    else:
        return _create_cron_job(name, command, schedule)


def _create_windows_task(name: str, command: str, schedule: str, description: str) -> str:
    """Create a Windows Scheduled Task."""
    trigger = _parse_windows_schedule(schedule)
    if trigger.startswith("Error"):
        return trigger

    desc = description or f"PyOz task: {name}"

    ps_script = (
        f"$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -Command \"{command}\"'; "
        f"$trigger = {trigger}; "
        f"$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
        f"Register-ScheduledTask -TaskName '{name}' -Action $action -Trigger $trigger "
        f"-Settings $settings -Description '{desc}' -Force"
    )

    r = _run(["powershell", "-NoProfile", "-Command", ps_script])
    if r["exit_code"] == 0:
        return f"Created scheduled task '{name}' with schedule: {schedule}"
    return _fmt(r)


def _parse_windows_schedule(schedule: str) -> str:
    """Convert schedule string to PowerShell trigger."""
    s = schedule.lower().strip()

    if s == "startup":
        return "New-ScheduledTaskTrigger -AtStartup"
    elif s == "logon":
        return "New-ScheduledTaskTrigger -AtLogOn"
    elif s == "hourly":
        return "New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)"
    elif s.startswith("daily"):
        time_part = s.replace("daily", "").strip() or "09:00"
        return f"New-ScheduledTaskTrigger -Daily -At '{time_part}'"
    elif s.startswith("weekly"):
        parts = s.replace("weekly", "").strip().split()
        day = parts[0].capitalize() if parts else "Monday"
        time_part = parts[1] if len(parts) > 1 else "09:00"
        return f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {day} -At '{time_part}'"
    elif s.startswith("once"):
        datetime_part = s.replace("once", "").strip()
        if not datetime_part:
            return "Error: 'once' schedule needs a datetime, e.g. 'once 2026-03-15 14:00'"
        return f"New-ScheduledTaskTrigger -Once -At '{datetime_part}'"

    # Try cron-style for Windows too
    if len(s.split()) == 5:
        return f"Error: Cron format not supported for Windows. Use: daily HH:MM, weekly Day HH:MM, hourly, startup, logon, once DATETIME"

    return f"Error: Unknown schedule format '{schedule}'. Use: daily HH:MM, weekly Day HH:MM, hourly, startup, logon, once DATETIME"


def _create_cron_job(name: str, command: str, schedule: str) -> str:
    """Create a cron job on Unix."""
    parts = schedule.strip().split()
    if len(parts) != 5:
        return (f"Error: Invalid cron schedule '{schedule}'. "
                "Use 5 fields: minute hour day-of-month month day-of-week. "
                "Example: '0 9 * * *' (daily at 9am)")

    cron_line = f"{schedule} {command} # pyoz:{name}"

    # Read existing crontab
    r = _run(["crontab", "-l"])
    existing = r["stdout"] if r["exit_code"] == 0 else ""

    # Check if already exists
    if f"pyoz:{name}" in existing:
        return f"Error: Cron job '{name}' already exists. Delete it first."

    # Add new line
    new_crontab = existing.rstrip() + "\n" + cron_line + "\n"

    # Install new crontab
    r = _run(["crontab", "-"], input_text=new_crontab)
    if r["exit_code"] == 0:
        return f"Created cron job '{name}': {schedule} {command}"
    return _fmt(r)


# --- Delete ---

def _delete_task(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Unregister-ScheduledTask -TaskName '{name}' -Confirm:$false -ErrorAction Stop"])
        if r["exit_code"] == 0:
            return f"Deleted scheduled task '{name}'"
        return _fmt(r)
    else:
        # Remove cron job by name tag
        r = _run(["crontab", "-l"])
        if r["exit_code"] != 0:
            return f"No cron jobs found."
        lines = r["stdout"].splitlines()
        new_lines = [l for l in lines if f"pyoz:{name}" not in l]
        if len(new_lines) == len(lines):
            return f"Cron job '{name}' not found."
        new_crontab = "\n".join(new_lines) + "\n"
        r = _run(["crontab", "-"], input_text=new_crontab)
        if r["exit_code"] == 0:
            return f"Deleted cron job '{name}'"
        return _fmt(r)


# --- Enable / Disable ---

def _enable_task(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Enable-ScheduledTask -TaskName '{name}' -ErrorAction Stop"])
        if r["exit_code"] == 0:
            return f"Enabled task '{name}'"
        return _fmt(r)
    else:
        return "Enable/disable not supported for cron. Delete and recreate instead."


def _disable_task(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Disable-ScheduledTask -TaskName '{name}' -ErrorAction Stop"])
        if r["exit_code"] == 0:
            return f"Disabled task '{name}'"
        return _fmt(r)
    else:
        return "Enable/disable not supported for cron. Delete and recreate instead."


# --- Status / Run ---

def _task_status(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"$t = Get-ScheduledTask -TaskName '{name}' -ErrorAction Stop; "
                   f"$i = $t | Get-ScheduledTaskInfo; "
                   f"[PSCustomObject]@{{ "
                   f"Name=$t.TaskName; State=$t.State; "
                   f"LastRun=$i.LastRunTime; NextRun=$i.NextRunTime; "
                   f"LastResult=$i.LastTaskResult; "
                   f"Description=$t.Description }} | Format-List"])
        return _fmt(r)
    else:
        r = _run(["crontab", "-l"])
        if r["exit_code"] != 0:
            return f"Cron job '{name}' not found."
        for line in r["stdout"].splitlines():
            if f"pyoz:{name}" in line:
                return f"Cron job '{name}': {line}"
        return f"Cron job '{name}' not found."


def _run_task(name: str) -> str:
    if IS_WINDOWS:
        r = _run(["powershell", "-NoProfile", "-Command",
                   f"Start-ScheduledTask -TaskName '{name}' -ErrorAction Stop"])
        if r["exit_code"] == 0:
            return f"Started task '{name}' (running now)"
        return _fmt(r)
    else:
        return "Direct run not supported for cron. Execute the command directly."
