"""PyOz Agent — the core agent loop.

One loop. LLM decides everything using tools.
No pipeline, no classification, no entity extraction.
"""

import json
import os
import sys
import traceback
from collections.abc import Generator
from typing import Any, Callable

from pyoz.providers.base import BaseLLMProvider, LLMResponse, StreamEvent, ToolCall
from pyoz.session import SessionManager
from pyoz.platform import IS_WINDOWS, HAS_POWERSHELL, PLATFORM_NAME, get_shell_info, get_command_reference
from pyoz.tools.file_tools import read_file, write_file, edit_file, search_files, list_directory
from pyoz.tools.command_tools import run_command
from pyoz.tools.git_tools import (
    git_init, git_commit, auto_commit, git_diff, git_undo, git_log, is_git_repo,
)
from pyoz.tools.context_tools import static_config, codebase_index, platform_info
from pyoz.tools.package_tools import package_manager
from pyoz.tools.dotnet_tools import dotnet_cli
from pyoz.tools.env_tools import env_manager
from pyoz.tools.process_tools import process_manager
from pyoz.tools.system_tools import system_info
from pyoz.tools.docker_tools import docker_tool
from pyoz.tools.service_tools import service_manager
from pyoz.tools.http_tools import http_request
from pyoz.tools.msbuild_tools import msbuild_tool
from pyoz.tools.schedule_tools import schedule_task
from pyoz.tools.kubernetes_tools import kubernetes_tool
from pyoz.tools.database_tools import database_tool
from pyoz.tools.git_workflow_tools import git_workflow_tool
from pyoz.tools.cicd_tools import cicd_tool
from pyoz.tools.registry import get_tool_definitions_claude, get_tool_definitions_openai
from pyoz.indexer.ast_indexer import ASTIndexer

MAX_TOOL_CALLS_PER_TURN = 50

# Keywords that suggest a task needs planning (creation, setup, new project)
_PLANNING_KEYWORDS = [
    "create", "build", "make", "setup", "set up", "scaffold", "generate",
    "new project", "new app", "new application", "bootstrap", "init",
    "implement", "develop", "design", "architect",
]

PLANNING_PROMPT = """You are a planning assistant. The user has given a task that involves creating
something new. Your ONLY job is to identify ambiguous technical choices and ask about them.

Analyze the user's request and identify choices that are NOT specified:
- Database type (SQLite, PostgreSQL, MySQL, MongoDB, etc.)
- Framework or library
- Build tool (Maven, Gradle, npm, etc.)
- Project structure (monolith, microservice, etc.)
- Architecture patterns
- Any other significant technical decision

Rules:
1. If ALL choices are clearly specified or there's only one reasonable option, respond with:
   PLAN_READY: <one-line summary of what you'll build>
2. If there ARE ambiguous choices, respond with:
   NEEDS_INPUT: <brief explanation>
   Then call the ask_user tool for EACH ambiguous choice (max 3 questions).
3. Do NOT ask about trivial things (variable names, file names, etc.)
4. Do NOT ask if the task is completely clear (e.g. "fix the bug in line 5")
5. Keep questions concise. Always suggest a recommended option first.
"""


def _load_rules(work_dir: str) -> str:
    """Load rules from PYOZ.md or .pyoz/rules.md."""
    candidates = [
        os.path.join(work_dir, "PYOZ.md"),
        os.path.join(work_dir, ".pyoz", "rules.md"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    return ""


def _build_system_prompt(rules: str, codebase_ctx: str) -> str:
    """Build the system prompt for the LLM."""
    shell_info = get_shell_info()

    prompt = """You are PyOz, an expert coding agent. You help developers
write code, debug issues, run commands, and build projects.

CAPABILITIES:
- Create new projects from scratch in any language
- Edit existing files with targeted changes
- Run build/test/lint commands and fix errors
- Search codebases to understand existing code
- Use git for version control

IMPORTANT BEHAVIORS:
1. When creating projects, use the static_config tool for build
   configs (pom.xml, package.json, etc.) — never generate
   XML or JSON build files yourself, they will be wrong.
2. After writing/editing files, the system auto-commits to git.
3. When a build or test fails, read the error, read the failing
   file, fix it, and retry — all in the same turn.
4. Always use os.makedirs for directory creation (cross-platform).
   Never use mkdir -p (fails on Windows).
5. When editing files, use edit_file for small targeted changes.
   Use write_file only when creating new files or rewriting entirely.
6. Before creating a project, use ask_user to clarify ambiguous
   technical choices (database, framework, build tool, etc.).
   If the user has already specified everything, skip asking.
   During execution, use ask_user if you encounter a decision
   that could go multiple ways.

TOOL SELECTION GUIDE:
- package_manager: Install/uninstall/search packages. Auto-detects the
  right manager (winget/choco/brew/apt/pip/npm/cargo). Use action="managers"
  to see what's available. Prefer this over run_command for package ops.
- dotnet_cli: .NET/C# project commands. Use for single-project operations
  (dotnet new/build/test/run/add-package). For solution-level operations
  (.sln management, multi-project refs), use msbuild_tool instead.
- env_manager: Read/write environment variables. Use action="load-env" to
  load .env files, action="path-list"/"path-add" for PATH management.
  Prefer this over run_command for any env var operations.
- process_manager: Find what's running and what's using ports. Use
  action="port-find" when a port is busy, action="find" to locate processes
  by name, action="kill" to stop a process. Prefer over run_command with ps/kill.
- system_info: Check system state before starting work. Use category="sdks"
  to verify tools are installed, category="memory"/"disk" to check resources,
  category="overview" for a full snapshot.
- docker_tool: Full Docker lifecycle. Use for building images, running
  containers, compose up/down, viewing logs, pruning. Always prefer this
  over run_command with docker/docker-compose commands.
- service_manager: System services (systemd/PowerShell/launchctl). Use to
  start/stop databases (mysql, postgres), web servers (nginx, apache),
  or any system daemon. Use action="find" to search by partial name.
- http_request: Make API calls. Always prefer this over run_command with
  curl/wget/Invoke-WebRequest. Supports JSON bodies, auth tokens, headers.
  Use for testing APIs, health checks, webhook triggers.
- msbuild_tool: Visual Studio solution management. Use for multi-project
  .sln operations: sln-add/sln-remove projects, proj-add-ref for project
  references, build/rebuild entire solutions. For single .csproj, use dotnet_cli.
- schedule_task: Create recurring jobs. On Unix uses cron (5-field expressions).
  On Windows uses Task Scheduler (daily/weekly/hourly/startup/logon schedules).
  Use action="list" to see existing tasks before creating new ones.
- kubernetes_tool: Full Kubernetes lifecycle. Use for deploying apps, managing
  pods/deployments/services, viewing logs, scaling, rollouts/rollbacks, applying
  manifests, Helm charts, Kustomize builds, ConfigMaps, Secrets, and node
  management. Always prefer this over run_command with kubectl/helm commands.
- database_tool: Connect to any database. Supports PostgreSQL, MySQL, SQLite,
  MongoDB, Redis, MSSQL. Use for running queries, listing tables, describing
  schemas, checking server info. User provides credentials (host, port, username,
  password, or connection_string). Always prefer this over run_command with
  psql/mysql/sqlite3/mongosh/redis-cli commands.
- git_workflow_tool: Full PR lifecycle. Create branches, push, create/review/merge
  PRs, clone repos, create releases. Use auto-branch-push-pr for one-shot
  branch→push→PR creation. Use auto-fix-pr to checkout and fix a PR. Always
  prefer this over run_command with gh/glab/git push commands.
- cicd_tool: CI/CD pipeline management. Trigger GitHub Actions or GitLab CI
  pipelines, view run status, watch for completion, get logs, rerun failed jobs.
  Use action="status" for quick CI check, action="wait" to block until CI passes.
  Always prefer this over run_command with gh run/glab ci commands.
- platform_info: Check current OS and shell. Use when you need to decide
  between platform-specific approaches.
- codebase_index: Get AST summary of the codebase. Use at start of work
  to understand project structure before making changes.
- ask_user: Ask the user a clarifying question when facing ambiguous
  technical decisions (which database, framework, architecture, etc.).
  Present 2-4 concrete options with the recommended one first. Do NOT use
  for trivial or obvious choices. Do NOT use when the user already specified
  their preference."""

    # Platform-specific instructions
    prompt += f"\n\nPLATFORM: {shell_info['platform']} (shell: {shell_info['name']})"

    if IS_WINDOWS and HAS_POWERSHELL:
        prompt += """

WINDOWS + POWERSHELL MODE:
You are running on Windows with PowerShell. ALWAYS use PowerShell commands
instead of Unix/bash commands when running commands via run_command.

Key PowerShell commands to use:
- Navigation: Get-Location (pwd), Set-Location (cd), Get-ChildItem (ls/dir)
- Files: Get-Content (cat), New-Item (touch/mkdir), Copy-Item (cp),
  Move-Item (mv), Remove-Item (rm), Test-Path (test -f)
- Search: Select-String (grep), Get-ChildItem -Recurse -Filter (find)
- Text: (Get-Content file) -replace 'old','new' (sed)
- Process: Get-Process (ps), Stop-Process (kill), Start-Process
- Network: Invoke-WebRequest (curl/wget), Test-Connection (ping)
- System: Get-Command (which), $env:VAR (env vars), Get-PSDrive (df)
- Archives: Compress-Archive (zip), Expand-Archive (unzip)
- Pipe: | Where-Object (filter), | ForEach-Object (map),
  | Measure-Object (count/sum), | Sort-Object, | Select-Object

PowerShell syntax rules:
- Use semicolons (;) to chain commands, NOT && or ||
- Variables use $: $var = "value"
- Env vars: $env:PATH, $env:HOME
- String interpolation: "Hello $name" or "Path: $($obj.Property)"
- Comparison: -eq, -ne, -gt, -lt, -ge, -le (NOT ==, !=, >, <)
- Logical: -and, -or, -not (NOT &&, ||, !)
- Wildcards: Get-ChildItem *.java -Recurse
- Pipeline: Get-Process | Where-Object { $_.CPU -gt 100 }
- Error handling: try { } catch { $_.Exception.Message }

NEVER use these Unix commands on Windows:
- ls, cat, grep, find, rm, cp, mv, mkdir -p, touch, head, tail
- chmod, chown, ln -s, tar, sed, awk, curl (use PowerShell equivalents)"""

    elif IS_WINDOWS:
        prompt += """

WINDOWS + CMD MODE:
You are running on Windows with Command Prompt (cmd.exe).
Use Windows-native commands: dir, type, copy, move, del, mkdir, rmdir.
Use backslashes for paths: C:\\Users\\name\\project"""

    else:
        prompt += f"""

UNIX MODE ({shell_info['platform'].upper()}):
You are running on {shell_info['platform']}. Use standard Unix/bash commands."""

    if rules:
        prompt += f"\n\nRULES:\n{rules}"

    if codebase_ctx and codebase_ctx != "No files indexed yet.":
        prompt += f"\n\nCODEBASE CONTEXT:\n{codebase_ctx}"

    return prompt


class Agent:
    """The PyOz agent — pure agent mode with tool calling."""

    def __init__(
        self,
        provider: BaseLLMProvider,
        work_dir: str | None = None,
        on_tool_call: Callable[[str, dict, str], None] | None = None,
        on_diff: Callable[[str, str, str], None] | None = None,
        on_stream_token: Callable[[str], None] | None = None,
        on_ask_user: Callable[[str, list[str]], str] | None = None,
        streaming: bool = False,
    ):
        self.provider = provider
        self.work_dir = os.path.abspath(work_dir) if work_dir else os.getcwd()
        self.on_tool_call = on_tool_call  # callback(tool_name, args, result)
        self.on_diff = on_diff  # callback(path, old_text, new_text)
        self.on_stream_token = on_stream_token  # callback(text_chunk)
        self.on_ask_user = on_ask_user  # callback(question, options) -> user's answer
        self.streaming = streaming

        # Conversation history
        self.messages: list[dict[str, Any]] = []

        # AST Indexer
        self.indexer = ASTIndexer(self.work_dir)

        # Rules
        self.rules = _load_rules(self.work_dir)

        # Session manager
        self.session_mgr = SessionManager(self.work_dir)

        # Session stats
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tool_calls = 0
        self.turn_count = 0

        # Cost per token (approximate)
        self._cost_rates = {
            "claude": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
            "openai": {"input": 2.5 / 1_000_000, "output": 10.0 / 1_000_000},
            "ollama": {"input": 0.0, "output": 0.0},
        }

    def initialize(self) -> dict[str, Any]:
        """Initialize the agent — scan codebase, check git."""
        self.indexer.scan()
        git_status = "clean" if is_git_repo(self.work_dir) else "no repo"
        return {
            "files_indexed": self.indexer.file_count(),
            "symbols": self.indexer.symbol_count(),
            "git": git_status,
            "rules": bool(self.rules),
            "provider": self.provider.provider_name,
            "model": self.provider.model_name,
        }

    def _needs_planning(self, message: str) -> bool:
        """Check if a user message likely needs a planning phase."""
        msg_lower = message.lower()
        return any(kw in msg_lower for kw in _PLANNING_KEYWORDS)

    def _run_planning_phase(self, user_message: str) -> str | None:
        """Run a planning phase to identify ambiguous choices.

        Returns the enriched user message with clarifications,
        or None if no planning was needed.
        """
        if not self.on_ask_user:
            return None  # No way to ask the user, skip planning

        # Use a lightweight LLM call with only the ask_user tool
        planning_messages = [
            {"role": "user", "content": user_message},
        ]

        # Only give the ask_user tool during planning
        if self.provider.provider_name == "claude":
            ask_tool = [{
                "name": "ask_user",
                "description": (
                    "Ask the user a clarifying question. Present 2-4 concrete options "
                    "with the recommended option first."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Concise question"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "2-4 options, recommended first",
                        },
                    },
                    "required": ["question", "options"],
                },
            }]
        else:
            ask_tool = [{
                "type": "function",
                "function": {
                    "name": "ask_user",
                    "description": (
                        "Ask the user a clarifying question. Present 2-4 concrete options "
                        "with the recommended option first."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "Concise question"},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "2-4 options, recommended first",
                            },
                        },
                        "required": ["question", "options"],
                    },
                },
            }]

        response = self.provider.chat(planning_messages, ask_tool, PLANNING_PROMPT)
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens

        # If PLAN_READY — no clarification needed
        if response.text and "PLAN_READY:" in response.text:
            return None

        # If tool calls — ask the user each question
        if not response.tool_calls:
            return None

        clarifications = []
        for tc in response.tool_calls:
            if tc.name == "ask_user":
                question = tc.arguments.get("question", "")
                options = tc.arguments.get("options", [])
                if question and options:
                    answer = self.on_ask_user(question, options)
                    clarifications.append(f"{question} → {answer}")

        if not clarifications:
            return None

        # Build enriched message with user's choices
        enriched = user_message + "\n\nUser clarifications:\n"
        for c in clarifications:
            enriched += f"- {c}\n"

        return enriched

    def chat(self, user_message: str) -> str:
        """Process a user message and return the final text response.

        This is the core agent loop:
        1. (Optional) Run planning phase for ambiguous creation tasks
        2. Add user message to history
        3. Send to LLM with tools
        4. If LLM returns tool calls → execute them, feed results back
        5. Loop until LLM returns text (no tool calls) or max iterations
        """
        self.turn_count += 1

        # Planning phase: detect ambiguous tasks and ask clarifying questions
        actual_message = user_message
        if self._needs_planning(user_message):
            enriched = self._run_planning_phase(user_message)
            if enriched:
                actual_message = enriched

        self.messages.append({"role": "user", "content": actual_message})

        # Manage context window — summarize old messages if too many
        self._manage_context()

        # Get tool definitions based on provider
        if self.provider.provider_name == "claude":
            tools = get_tool_definitions_claude()
        else:
            tools = get_tool_definitions_openai()

        system_prompt = _build_system_prompt(self.rules, self.indexer.get_summary())

        tool_calls_this_turn = 0
        final_text = ""

        while tool_calls_this_turn < MAX_TOOL_CALLS_PER_TURN:
            # Call LLM (streaming or non-streaming)
            if self.streaming and self.on_stream_token:
                response = self._chat_streaming(tools, system_prompt)
            else:
                response = self.provider.chat(self.messages, tools, system_prompt)

            # Track tokens
            self.total_input_tokens += response.input_tokens
            self.total_output_tokens += response.output_tokens

            # No tool calls → we're done
            if not response.tool_calls:
                final_text = response.text or ""
                if final_text:
                    self.messages.append({"role": "assistant", "content": final_text})
                break

            # Has tool calls → execute them
            # Add assistant's tool-calling message to history
            self.messages.append(self.provider.format_tool_calls_message(response))

            # If there's also text alongside tool calls, capture it
            if response.text:
                final_text = response.text

            # Execute each tool call
            tool_results = []
            for tc in response.tool_calls:
                tool_calls_this_turn += 1
                self.total_tool_calls += 1

                result = self._execute_tool(tc)
                tool_results.append((tc.id, result))

                if self.on_tool_call:
                    self.on_tool_call(tc.name, tc.arguments, result)

            # Feed results back to LLM
            if self.provider.provider_name == "claude":
                # Claude: all tool results go in one user message
                content = []
                for tc_id, result in tool_results:
                    content.append({
                        "type": "tool_result",
                        "tool_use_id": tc_id,
                        "content": result,
                    })
                self.messages.append({"role": "user", "content": content})
            else:
                # OpenAI/Ollama: each tool result is a separate message
                for tc_id, result in tool_results:
                    self.messages.append(
                        self.provider.format_tool_result(tc_id, result)
                    )

        if tool_calls_this_turn >= MAX_TOOL_CALLS_PER_TURN:
            final_text += "\n\n[Reached maximum tool calls per turn (50). Stopping.]"

        # Auto-save session after each turn
        self._auto_save_session()

        return final_text

    def _chat_streaming(
        self,
        tools: list[dict[str, Any]],
        system_prompt: str,
    ) -> LLMResponse:
        """Call LLM with streaming, emitting tokens via callback."""
        stream = self.provider.chat_stream(self.messages, tools, system_prompt)

        # Collect the full response from the generator
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        input_tokens = 0
        output_tokens = 0

        # Track tool call building during stream
        current_tool_args: dict[str, str] = {}  # tool_call_id -> accumulated args json

        try:
            for event in stream:
                if event.type == "text_delta" and event.text:
                    text_parts.append(event.text)
                    if self.on_stream_token:
                        self.on_stream_token(event.text)
                elif event.type == "tool_call_start":
                    current_tool_args[event.tool_call_id] = ""
                elif event.type == "tool_call_delta":
                    if event.tool_call_id in current_tool_args:
                        current_tool_args[event.tool_call_id] += event.text
                elif event.type == "usage":
                    input_tokens = event.input_tokens
                    output_tokens = event.output_tokens
                elif event.type == "done":
                    break
        except StopIteration as e:
            # Generator returned a value
            if isinstance(e.value, LLMResponse):
                return e.value

        # If generator returned response through return statement
        # we need to construct it from events
        final_text = "".join(text_parts) if text_parts else None

        # End the streaming line if we printed text
        if text_parts and self.on_stream_token:
            self.on_stream_token("\n")

        return LLMResponse(
            text=final_text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a single tool call and return the result as string."""
        name = tool_call.name
        args = tool_call.arguments

        try:
            if name == "read_file":
                return read_file(self._resolve_path(args["path"]))

            elif name == "write_file":
                path = self._resolve_path(args["path"])
                result = write_file(path, args["content"])
                # Auto-commit and re-index
                if is_git_repo(self.work_dir):
                    commit_result = auto_commit(path, "create", self.work_dir)
                self.indexer.reindex_file(path)
                return result

            elif name == "edit_file":
                path = self._resolve_path(args["path"])
                old_text = args["old_text"]
                new_text = args["new_text"]

                # Read before for diff
                if self.on_diff:
                    try:
                        before = read_file(path)
                    except FileNotFoundError:
                        before = ""

                result = edit_file(path, old_text, new_text)

                # Show diff
                if self.on_diff:
                    self.on_diff(path, old_text, new_text)

                # Auto-commit and re-index
                if is_git_repo(self.work_dir):
                    auto_commit(path, "edit", self.work_dir)
                self.indexer.reindex_file(path)
                return result

            elif name == "search_files":
                results = search_files(
                    args["pattern"],
                    self._resolve_path(args.get("path")) if args.get("path") else self.work_dir,
                    args.get("file_ext"),
                )
                if not results:
                    return "No matches found."
                lines = []
                for r in results[:100]:  # Limit results
                    lines.append(f"{r['file']}:{r['line']}: {r['text']}")
                return "\n".join(lines)

            elif name == "list_directory":
                path = self._resolve_path(args.get("path")) if args.get("path") else self.work_dir
                entries = list_directory(path)
                lines = []
                for e in entries:
                    if e["type"] == "directory":
                        lines.append(f"  {e['name']}/")
                    else:
                        size = e.get("size", 0)
                        lines.append(f"  {e['name']} ({size} bytes)")
                return "\n".join(lines) if lines else "Empty directory."

            elif name == "run_command":
                cwd = self._resolve_path(args.get("cwd")) if args.get("cwd") else self.work_dir
                result = run_command(args["command"], cwd)
                parts = []
                if result["stdout"]:
                    parts.append(result["stdout"])
                if result["stderr"]:
                    parts.append(f"STDERR: {result['stderr']}")
                parts.append(f"Exit code: {result['exit_code']}")
                return "\n".join(parts)

            elif name == "git_init":
                return git_init(self.work_dir)

            elif name == "git_commit":
                return git_commit(args["message"], self.work_dir)

            elif name == "git_diff":
                return git_diff(self.work_dir)

            elif name == "git_undo":
                return git_undo(self.work_dir)

            elif name == "git_log":
                n = args.get("n", 10)
                commits = git_log(n, self.work_dir)
                if not commits:
                    return "No commits yet."
                lines = []
                for c in commits:
                    lines.append(f"{c['hash']} {c['message']} ({c['time']})")
                return "\n".join(lines)

            elif name == "codebase_index":
                return self.indexer.get_summary()

            elif name == "static_config":
                return static_config(args["language"], args["project_name"])

            elif name == "platform_info":
                return platform_info()

            elif name == "package_manager":
                return package_manager(
                    action=args["action"],
                    package=args.get("package", ""),
                    manager=args.get("manager", ""),
                )

            elif name == "dotnet_cli":
                return dotnet_cli(
                    action=args["action"],
                    project_path=self._resolve_path(args.get("project_path")) if args.get("project_path") else "",
                    args=args.get("args", ""),
                    cwd=self.work_dir,
                )

            elif name == "env_manager":
                return env_manager(
                    action=args["action"],
                    name=args.get("name", ""),
                    value=args.get("value", ""),
                    file_path=self._resolve_path(args.get("file_path")) if args.get("file_path") else "",
                )

            elif name == "process_manager":
                return process_manager(
                    action=args["action"],
                    pid=args.get("pid", 0),
                    name=args.get("name", ""),
                    port=args.get("port", 0),
                )

            elif name == "system_info":
                return system_info(args.get("category", "overview"))

            elif name == "docker_tool":
                return docker_tool(
                    action=args["action"],
                    target=args.get("target", ""),
                    args=args.get("args", ""),
                    cwd=self.work_dir,
                )

            elif name == "service_manager":
                return service_manager(
                    action=args["action"],
                    name=args.get("name", ""),
                    args=args.get("args", ""),
                )

            elif name == "http_request":
                return http_request(
                    method=args["method"],
                    url=args["url"],
                    headers=args.get("headers"),
                    body=args.get("body", ""),
                    json_body=args.get("json_body"),
                    query_params=args.get("query_params"),
                    auth_token=args.get("auth_token", ""),
                )

            elif name == "msbuild_tool":
                return msbuild_tool(
                    action=args["action"],
                    target=args.get("target", ""),
                    args=args.get("args", ""),
                    cwd=self.work_dir,
                )

            elif name == "schedule_task":
                return schedule_task(
                    action=args["action"],
                    name=args.get("name", ""),
                    command=args.get("command", ""),
                    schedule=args.get("schedule", ""),
                    description=args.get("description", ""),
                )

            elif name == "kubernetes_tool":
                return kubernetes_tool(
                    action=args["action"],
                    target=args.get("target", ""),
                    namespace=args.get("namespace", ""),
                    args=args.get("args", ""),
                    cwd=self.work_dir,
                )

            elif name == "database_tool":
                return database_tool(
                    action=args["action"],
                    engine=args.get("engine", "sqlite"),
                    query=args.get("query", ""),
                    host=args.get("host", ""),
                    port=args.get("port", 0),
                    database=args.get("database", ""),
                    username=args.get("username", ""),
                    password=args.get("password", ""),
                    connection_string=args.get("connection_string", ""),
                )

            elif name == "git_workflow_tool":
                return git_workflow_tool(
                    action=args["action"],
                    target=args.get("target", ""),
                    branch=args.get("branch", ""),
                    title=args.get("title", ""),
                    body=args.get("body", ""),
                    args=args.get("args", ""),
                    cwd=self.work_dir,
                )

            elif name == "ask_user":
                question = args.get("question", "What would you like to do?")
                options = args.get("options", [])
                if self.on_ask_user:
                    answer = self.on_ask_user(question, options)
                    return f"User answered: {answer}"
                return "No user interaction available. Make a reasonable default choice and proceed."

            elif name == "cicd_tool":
                return cicd_tool(
                    action=args["action"],
                    target=args.get("target", ""),
                    workflow=args.get("workflow", ""),
                    branch=args.get("branch", ""),
                    args=args.get("args", ""),
                    cwd=self.work_dir,
                )

            else:
                return f"Error: Unknown tool '{name}'"

        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}"

    def _resolve_path(self, path: str | None) -> str:
        """Resolve a path relative to the working directory."""
        if not path:
            return self.work_dir
        if os.path.isabs(path):
            return path
        return os.path.join(self.work_dir, path)

    def _manage_context(self) -> None:
        """Manage conversation context window size.

        Keep recent 10 turns in full, summarize rest.
        Always keep the first message (if it exists).
        """
        # Count user messages (each user message = 1 turn)
        user_msg_count = sum(1 for m in self.messages if m["role"] == "user"
                            and isinstance(m.get("content"), str))
        if user_msg_count <= 10:
            return

        # Find messages to summarize (keep last 20 messages roughly = 10 turns)
        keep_count = 20
        if len(self.messages) <= keep_count:
            return

        old_messages = self.messages[:-keep_count]
        new_messages = self.messages[-keep_count:]

        # Create summary of old messages
        summary_parts = []
        for msg in old_messages:
            if msg["role"] == "user" and isinstance(msg.get("content"), str):
                summary_parts.append(f"User: {msg['content'][:100]}")
            elif msg["role"] == "assistant" and isinstance(msg.get("content"), str):
                summary_parts.append(f"Assistant: {msg['content'][:100]}")

        if summary_parts:
            summary = "[Previous conversation summary]\n" + "\n".join(summary_parts)
            self.messages = [{"role": "user", "content": summary}] + new_messages
        else:
            self.messages = new_messages

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        provider = self.provider.provider_name
        rates = self._cost_rates.get(provider, {"input": 0, "output": 0})
        cost = (self.total_input_tokens * rates["input"] +
                self.total_output_tokens * rates["output"])
        return {
            "turns": self.turn_count,
            "total_tool_calls": self.total_tool_calls,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "estimated_cost": round(cost, 4),
        }

    def clear_history(self) -> None:
        """Clear conversation history but keep codebase context."""
        self.messages.clear()
        self.turn_count = 0

    def reload_rules(self) -> str:
        """Reload rules from PYOZ.md."""
        self.rules = _load_rules(self.work_dir)
        return self.rules or "No rules file found."

    def reindex(self) -> dict[str, int]:
        """Re-scan and re-index the codebase."""
        self.indexer.scan()
        return {
            "files": self.indexer.file_count(),
            "symbols": self.indexer.symbol_count(),
        }

    # --- Session persistence ---

    def _auto_save_session(self) -> None:
        """Auto-save session after each turn."""
        try:
            self.session_mgr.save(
                messages=self.messages,
                stats=self.get_stats(),
                provider=self.provider.provider_name,
                model=self.provider.model_name,
            )
        except Exception:
            pass  # Don't fail on save errors

    def save_session(self) -> str:
        """Manually save the current session."""
        return self.session_mgr.save(
            messages=self.messages,
            stats=self.get_stats(),
            provider=self.provider.provider_name,
            model=self.provider.model_name,
        )

    def load_session(self) -> bool:
        """Load a previous session if available. Returns True if loaded."""
        data = self.session_mgr.load()
        if not data:
            return False
        self.messages = data.get("messages", [])
        stats = data.get("stats", {})
        self.total_input_tokens = stats.get("input_tokens", 0)
        self.total_output_tokens = stats.get("output_tokens", 0)
        self.total_tool_calls = stats.get("total_tool_calls", 0)
        self.turn_count = stats.get("turns", 0)
        return True

    def new_session(self) -> str | None:
        """Archive current session and start fresh."""
        archive = self.session_mgr.archive()
        self.clear_history()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tool_calls = 0
        self.session_mgr.delete()
        return archive

    def list_sessions(self) -> list[dict[str, str]]:
        """List archived sessions."""
        return self.session_mgr.list_history()

    def export_session(self) -> str | None:
        """Export current session as markdown."""
        return self.session_mgr.export_markdown()

    # --- Workspace switching ---

    def change_work_dir(self, new_dir: str) -> dict[str, Any]:
        """Switch working directory and re-initialize."""
        abs_path = os.path.abspath(new_dir)
        if not os.path.isdir(abs_path):
            raise FileNotFoundError(f"Directory not found: {abs_path}")

        # Save current session before switching
        self._auto_save_session()

        # Switch
        self.work_dir = abs_path
        self.indexer = ASTIndexer(self.work_dir)
        self.rules = _load_rules(self.work_dir)
        self.session_mgr = SessionManager(self.work_dir)

        # Clear conversation (different project context)
        self.messages.clear()
        self.turn_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tool_calls = 0

        # Try to load existing session for new workspace
        self.load_session()

        return self.initialize()
