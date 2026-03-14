"""Tool registry — defines all tools and their schemas for LLM function calling."""

from typing import Any

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
        "description": "Run a shell command and return stdout, stderr, and exit code. Timeout: 120 seconds. Some dangerous commands are blocked.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
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
