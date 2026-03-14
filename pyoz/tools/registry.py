"""Tool registry — defines all tools and their schemas for LLM function calling."""

from typing import Any

from pyoz.platform import IS_WINDOWS, HAS_POWERSHELL

# Tool definitions in a format that can be converted to Claude/OpenAI tool schemas
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read and return the content of a file. Returns the file content as a string.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating parent directories as needed. Overwrites if file exists.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Search and replace text in a file. The old_text must appear exactly once in the file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit"},
                "old_text": {"type": "string", "description": "Text to find (must appear exactly once)"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for a regex pattern across files in the codebase. Returns matching lines with file path and line number.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in (default: current directory)"},
                "file_ext": {"type": "string", "description": "Filter by file extension (e.g. '.java', '.py')"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory, skipping hidden and build directories.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: current directory)"},
            },
            "required": [],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a PowerShell command and return stdout, stderr, and exit code. "
            "Use PowerShell cmdlets: Get-ChildItem (ls), Select-String (grep), "
            "Get-Content (cat), New-Item (touch/mkdir), etc. Timeout: 120 seconds."
            if IS_WINDOWS and HAS_POWERSHELL
            else "Run a shell command and return stdout, stderr, and exit code. Timeout: 120 seconds. Some dangerous commands are blocked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": (
                    "PowerShell command to execute (use PowerShell cmdlets, not Unix commands)"
                    if IS_WINDOWS and HAS_POWERSHELL
                    else "Shell command to execute"
                )},
                "cwd": {"type": "string", "description": "Working directory (default: current directory)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_init",
        "description": "Initialize a git repository with .gitignore and initial commit.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "git_commit",
        "description": "Stage all changes and create a git commit with the given message.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "git_diff",
        "description": "Show uncommitted changes (both staged and unstaged) as a diff.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "git_undo",
        "description": "Undo the last git commit by reverting HEAD.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "git_log",
        "description": "Show the last N git commits.",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Number of commits to show (default: 10)"},
            },
            "required": [],
        },
    },
    {
        "name": "codebase_index",
        "description": "Get the AST-structured summary of all indexed files in the codebase. Shows classes, methods, fields, imports, and dependencies.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "static_config",
        "description": "Get a known-good build configuration file for a language/framework. Use this instead of generating build configs yourself. Supports: java, python, go, rust, javascript, typescript, kotlin, csharp.",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "description": "Programming language (java, python, go, rust, javascript, typescript, kotlin, csharp)"},
                "project_name": {"type": "string", "description": "Project name for the config file"},
            },
            "required": ["language", "project_name"],
        },
    },
    {
        "name": "platform_info",
        "description": (
            "Get current platform info, shell type, and PowerShell command reference. "
            "Use this to look up the correct PowerShell equivalent for Unix commands."
            if IS_WINDOWS
            else "Get current platform and shell information."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "package_manager",
        "description": (
            "Manage packages: install, uninstall, search, list, update. "
            "Supports winget, choco, scoop, brew, apt, dnf, pip, npm, cargo, go, dotnet. "
            "Auto-detects the best package manager for the current platform."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: install, uninstall, search, list, update, info, managers",
                },
                "package": {
                    "type": "string",
                    "description": "Package name (required for install/uninstall/search/info)",
                },
                "manager": {
                    "type": "string",
                    "description": "Package manager to use (auto-detected if empty). Options: winget, choco, scoop, brew, apt, dnf, pip, npm, cargo, go, dotnet",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "dotnet_cli",
        "description": (
            "Run .NET/C# CLI actions: create projects, build, test, run, manage NuGet packages. "
            "Requires .NET SDK installed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: new, build, test, run, publish, clean, restore, add-package, remove-package, list-packages, info, sdk-list",
                },
                "project_path": {
                    "type": "string",
                    "description": "Path to project/solution (optional, uses working directory)",
                },
                "args": {
                    "type": "string",
                    "description": "Additional arguments (e.g. template name for 'new', package name for 'add-package')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "env_manager",
        "description": (
            "Manage environment variables: get, set, unset, list, load .env files, manage PATH. "
            "Changes apply to the current process."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: get, set, unset, list, load-env, save-env, path-list, path-add",
                },
                "name": {
                    "type": "string",
                    "description": "Variable name (for get/set/unset) or prefix filter (for list)",
                },
                "value": {
                    "type": "string",
                    "description": "Variable value (for set) or directory (for path-add)",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to .env file (for load-env/save-env, default: .env)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "process_manager",
        "description": (
            "Manage system processes: list running processes, find by name, kill by PID, "
            "list listening ports, find which process uses a port."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: list, find, kill, ports, port-find, tree",
                },
                "pid": {
                    "type": "integer",
                    "description": "Process ID (for kill, tree)",
                },
                "name": {
                    "type": "string",
                    "description": "Process name filter (for find, list)",
                },
                "port": {
                    "type": "integer",
                    "description": "Port number (for port-find)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "system_info",
        "description": (
            "Get system information: OS, CPU, memory, disk, network, installed SDKs. "
            "Use category='sdks' to check all installed development tools."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category: overview, os, cpu, memory, disk, network, sdks, python, node, java, dotnet, rust, go",
                },
            },
            "required": [],
        },
    },
    # --- Tier 2 Tools ---
    {
        "name": "docker_tool",
        "description": (
            "Docker and Docker Compose management: build images, run/stop/restart containers, "
            "view logs, manage images/volumes/networks, compose up/down. "
            "Requires Docker installed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Action — Containers: run, exec, stop, start, restart, rm, ps, logs, inspect; "
                        "Images: build, pull, push, images, rmi, tag; "
                        "Compose: compose-up, compose-down, compose-build, compose-logs, compose-ps, compose-restart, compose-exec; "
                        "System: info, version, prune, networks, volumes, stats"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": "Container/image name, service name, or Dockerfile path",
                },
                "args": {
                    "type": "string",
                    "description": "Additional flags (e.g. '-d -p 8080:80', '--build', '-f docker-compose.prod.yml')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "service_manager",
        "description": (
            "Manage system services (Windows: PowerShell services, Linux: systemd, macOS: launchctl). "
            "Start, stop, restart, enable/disable services, view logs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: list, find, status, start, stop, restart, enable, disable, logs",
                },
                "name": {
                    "type": "string",
                    "description": "Service name (required for most actions)",
                },
                "args": {
                    "type": "string",
                    "description": "Extra arguments (e.g. number of log lines)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "http_request",
        "description": (
            "Make HTTP API requests (GET, POST, PUT, PATCH, DELETE). "
            "Supports JSON bodies, custom headers, bearer auth, query params. "
            "Returns status code, headers, and response body."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP method: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS",
                },
                "url": {
                    "type": "string",
                    "description": "Full URL to request (e.g. https://api.example.com/users)",
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers as key-value pairs",
                },
                "body": {
                    "type": "string",
                    "description": "Raw request body string",
                },
                "json_body": {
                    "type": "object",
                    "description": "JSON request body (auto-sets Content-Type)",
                },
                "query_params": {
                    "type": "object",
                    "description": "URL query parameters as key-value pairs",
                },
                "auth_token": {
                    "type": "string",
                    "description": "Bearer token for Authorization header",
                },
            },
            "required": ["method", "url"],
        },
    },
    {
        "name": "msbuild_tool",
        "description": (
            "MSBuild and Visual Studio Solution management. Build .sln/.csproj projects, "
            "manage solution structure, project references. Uses dotnet CLI or MSBuild."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Action — Build: build, rebuild, clean, restore, publish, test; "
                        "Solution: sln-new, sln-list, sln-add, sln-remove; "
                        "Project: proj-list, proj-add-ref, proj-remove-ref; "
                        "Info: info, find-solutions, find-projects"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": "Solution (.sln) or project (.csproj) path",
                },
                "args": {
                    "type": "string",
                    "description": "Extra arguments (config, platform, package/project names)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "schedule_task",
        "description": (
            "Manage scheduled tasks. Windows: Task Scheduler (daily, weekly, hourly, startup, logon). "
            "Unix: cron jobs (5-field cron expression). Create, delete, enable/disable, run."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: list, create, delete, enable, disable, status, run",
                },
                "name": {
                    "type": "string",
                    "description": "Task/job name",
                },
                "command": {
                    "type": "string",
                    "description": "Command to execute (for create)",
                },
                "schedule": {
                    "type": "string",
                    "description": "Schedule: cron '0 9 * * *' (Unix) or 'daily 09:00', 'weekly Monday 09:00', 'hourly', 'startup' (Windows)",
                },
                "description": {
                    "type": "string",
                    "description": "Task description (optional)",
                },
            },
            "required": ["action"],
        },
    },
    # --- Kubernetes & Helm ---
    {
        "name": "kubernetes_tool",
        "description": (
            "Kubernetes cluster and workload management: deploy apps, manage pods/deployments/"
            "services, view logs, scale replicas, rollout/rollback, apply manifests, Helm charts, "
            "Kustomize, ConfigMaps, Secrets, node management. Enterprise-grade k8s lifecycle. "
            "Requires kubectl (and optionally helm) installed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Action — Cluster: cluster-info, get-contexts, use-context, get-nodes, top-nodes; "
                        "Namespaces: get-namespaces, create-namespace, delete-namespace; "
                        "Workloads: get-pods, get-deployments, get-services, get-statefulsets, get-daemonsets, "
                        "get-jobs, get-cronjobs, get-ingresses, get-all; "
                        "Deploy: apply, delete, create-deployment, scale, set-image, "
                        "rollout-status, rollout-history, rollout-undo, rollout-restart; "
                        "Pod Ops: logs, exec, describe, port-forward, get-events; "
                        "Config: get-configmaps, get-secrets, create-configmap, create-secret; "
                        "Helm: helm-install, helm-upgrade, helm-uninstall, helm-list, "
                        "helm-repo-add, helm-repo-update, helm-search, helm-status; "
                        "Advanced: kustomize, top-pods, get-pvc, get-hpa, cordon, uncordon, drain, "
                        "taint, label, annotate"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": "Resource name, manifest file path, Helm release/chart name, or node name",
                },
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace (default: current context, 'all' for --all-namespaces)",
                },
                "args": {
                    "type": "string",
                    "description": "Additional flags (e.g. '--replicas=3', '-l app=web', '-f values.yaml', '--image=nginx:latest')",
                },
            },
            "required": ["action"],
        },
    },
    # --- Database ---
    {
        "name": "database_tool",
        "description": (
            "Connect to and query any database engine. Supports PostgreSQL, MySQL, MariaDB, "
            "SQLite, MongoDB, Redis, and MSSQL. Execute SQL queries, list tables, describe "
            "schemas, get server info. For MongoDB: JSON-based find/insert/update/delete/aggregate. "
            "For Redis: direct commands (GET, SET, KEYS, etc.). User provides credentials."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action: query, list-tables, describe, info",
                },
                "engine": {
                    "type": "string",
                    "description": "Database engine: sqlite, postgres, mysql, mariadb, mssql, mongodb, redis",
                },
                "query": {
                    "type": "string",
                    "description": "SQL query, MongoDB JSON query, Redis command, or table name for describe",
                },
                "host": {
                    "type": "string",
                    "description": "Database host (default: localhost)",
                },
                "port": {
                    "type": "integer",
                    "description": "Database port (default: engine-specific)",
                },
                "database": {
                    "type": "string",
                    "description": "Database name (or file path for SQLite)",
                },
                "username": {
                    "type": "string",
                    "description": "Database username",
                },
                "password": {
                    "type": "string",
                    "description": "Database password",
                },
                "connection_string": {
                    "type": "string",
                    "description": "Full connection string (overrides individual params)",
                },
            },
            "required": ["action", "engine"],
        },
    },
    # --- Git Workflow / PR ---
    {
        "name": "git_workflow_tool",
        "description": (
            "Automated git workflow: create branches, push, create/review/merge pull requests, "
            "clone repos, create releases. Works with GitHub (gh CLI) and GitLab (glab CLI). "
            "Includes auto-branch-push-pr (one-shot: branch → push → PR) and auto-fix-pr "
            "(checkout PR → ready for fixes). Enables fully autonomous code → deploy pipelines."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Action — Branch: create-branch, switch-branch, list-branches, delete-branch, "
                        "push, pull, fetch, rebase, merge-branch, stash, stash-pop; "
                        "PR: pr-create, pr-list, pr-view, pr-diff, pr-merge, pr-close, "
                        "pr-review, pr-approve, pr-comment, pr-checkout; "
                        "Repo: clone, fork, repo-view, release-create, release-list; "
                        "Automation: auto-branch-push-pr, auto-fix-pr"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": "PR number, branch name, repo URL, release tag, or run ID",
                },
                "branch": {
                    "type": "string",
                    "description": "Base branch for PR or branch creation (default: main)",
                },
                "title": {
                    "type": "string",
                    "description": "PR title, commit message, or release title",
                },
                "body": {
                    "type": "string",
                    "description": "PR description, review comment, or release notes",
                },
                "args": {
                    "type": "string",
                    "description": "Additional flags (e.g. '--draft', '--squash', '--reviewer=user')",
                },
            },
            "required": ["action"],
        },
    },
    # --- CI/CD ---
    {
        "name": "cicd_tool",
        "description": (
            "CI/CD pipeline management: trigger, monitor, and manage GitHub Actions workflows "
            "and GitLab CI pipelines. View run status, watch for completion, get logs, rerun "
            "failed jobs, cancel runs. Enables autonomous build-test-deploy with failure detection."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": (
                        "Action — GitHub Actions: workflow-list, workflow-run, run-list, run-view, "
                        "run-watch, run-logs, run-rerun, run-cancel, check-status; "
                        "GitLab CI: pipeline-list, pipeline-view, pipeline-create, pipeline-cancel, "
                        "pipeline-retry, job-list, job-log; "
                        "General: status, wait"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": "Run ID, pipeline ID, job ID, or workflow name",
                },
                "workflow": {
                    "type": "string",
                    "description": "Workflow file name (e.g. 'ci.yml', 'deploy.yml')",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch to trigger workflow on (default: current)",
                },
                "args": {
                    "type": "string",
                    "description": "Additional flags or workflow inputs as JSON (e.g. '{\"env\": \"prod\"}')",
                },
            },
            "required": ["action"],
        },
    },
]


def get_tool_definitions_claude() -> list[dict[str, Any]]:
    """Return tool definitions in Claude API format."""
    tools = []
    for t in TOOL_DEFINITIONS:
        tools.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        })
    return tools


def get_tool_definitions_openai() -> list[dict[str, Any]]:
    """Return tool definitions in OpenAI API format."""
    tools = []
    for t in TOOL_DEFINITIONS:
        tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        })
    return tools
