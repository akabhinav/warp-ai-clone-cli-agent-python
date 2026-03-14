"""Tests for tool registry."""

from pyoz.tools.registry import (
    TOOL_DEFINITIONS,
    get_tool_definitions_claude,
    get_tool_definitions_openai,
)


class TestToolDefinitions:
    def test_has_13_tools(self):
        assert len(TOOL_DEFINITIONS) == 24

    def test_tool_names(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        expected = [
            "read_file", "write_file", "edit_file", "search_files",
            "list_directory", "run_command", "git_init", "git_commit",
            "git_diff", "git_undo", "git_log", "codebase_index", "static_config",
        ]
        for name in expected:
            assert name in names, f"Missing tool: {name}"

    def test_all_have_description(self):
        for t in TOOL_DEFINITIONS:
            assert t.get("description"), f"{t['name']} missing description"

    def test_all_have_parameters(self):
        for t in TOOL_DEFINITIONS:
            assert "parameters" in t, f"{t['name']} missing parameters"
            assert t["parameters"]["type"] == "object"


class TestClaudeFormat:
    def test_format(self):
        tools = get_tool_definitions_claude()
        assert len(tools) == 24
        for t in tools:
            assert "name" in t
            assert "description" in t
            assert "input_schema" in t

    def test_input_schema_is_parameters(self):
        tools = get_tool_definitions_claude()
        for t in tools:
            assert t["input_schema"]["type"] == "object"


class TestOpenAIFormat:
    def test_format(self):
        tools = get_tool_definitions_openai()
        assert len(tools) == 24
        for t in tools:
            assert t["type"] == "function"
            assert "function" in t
            assert "name" in t["function"]
            assert "parameters" in t["function"]
