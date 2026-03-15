"""Tests for the agent loop."""

import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from pyoz.agent import Agent, _build_system_prompt, _convert_messages, _load_rules
from pyoz.providers.base import BaseLLMProvider, LLMResponse, ToolCall


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for testing the agent loop."""

    def __init__(self, responses: list[LLMResponse] | None = None):
        super().__init__(api_key="test", model="mock-model")
        self.responses = responses or []
        self._call_index = 0
        self.call_log: list[dict] = []

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def chat(self, messages, tools, system_prompt=None):
        self.call_log.append({
            "messages": messages,
            "tools": tools,
            "system_prompt": system_prompt,
        })
        if self._call_index < len(self.responses):
            resp = self.responses[self._call_index]
            self._call_index += 1
            return resp
        return LLMResponse(text="(no more mock responses)")

    def format_tool_result(self, tool_call_id, result):
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": result}],
        }

    def format_tool_calls_message(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.arguments,
            })
        return {"role": "assistant", "content": content}


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestAgentTextResponse:
    def test_text_only_response(self, tmpdir):
        provider = MockProvider([
            LLMResponse(text="Hello! How can I help?", input_tokens=10, output_tokens=5),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        result = agent.chat("hi")
        assert result == "Hello! How can I help?"

    def test_conversation_history_passed(self, tmpdir):
        provider = MockProvider([
            LLMResponse(text="First response", input_tokens=10, output_tokens=5),
            LLMResponse(text="Second response", input_tokens=20, output_tokens=10),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        agent.chat("first message")
        agent.chat("second message")
        # Second call should have history
        assert len(provider.call_log) == 2
        second_call_msgs = provider.call_log[1]["messages"]
        assert any("first message" in str(m) for m in second_call_msgs)


class TestAgentToolCalls:
    def test_single_tool_call(self, tmpdir):
        provider = MockProvider([
            # First: LLM calls write_file
            LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="list_directory", arguments={"path": tmpdir})],
                input_tokens=10,
                output_tokens=5,
            ),
            # Second: LLM responds with text
            LLMResponse(text="I listed the directory.", input_tokens=15, output_tokens=8),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        result = agent.chat("list files")
        assert "listed" in result.lower()

    def test_multiple_tool_calls_in_sequence(self, tmpdir):
        from pyoz.tools.file_tools import write_file
        write_file(os.path.join(tmpdir, "test.txt"), "hello world")

        provider = MockProvider([
            # First: read_file
            LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="read_file", arguments={"path": "test.txt"})],
                input_tokens=10, output_tokens=5,
            ),
            # Second: another tool call
            LLMResponse(
                tool_calls=[ToolCall(id="tc2", name="list_directory", arguments={})],
                input_tokens=15, output_tokens=8,
            ),
            # Third: text response
            LLMResponse(text="Done reading and listing.", input_tokens=20, output_tokens=10),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        result = agent.chat("show me the files")
        assert "Done" in result

    def test_tool_error_returned_to_llm(self, tmpdir):
        provider = MockProvider([
            # Try to read missing file
            LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="read_file", arguments={"path": "missing.txt"})],
                input_tokens=10, output_tokens=5,
            ),
            # LLM sees error and responds
            LLMResponse(text="File not found.", input_tokens=15, output_tokens=5),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        result = agent.chat("read missing.txt")
        assert "not found" in result.lower()

    def test_max_iterations_stops(self, tmpdir):
        # Create infinite tool call loop
        responses = []
        for i in range(60):
            responses.append(LLMResponse(
                tool_calls=[ToolCall(id=f"tc{i}", name="list_directory", arguments={})],
                input_tokens=5, output_tokens=3,
            ))
        provider = MockProvider(responses)
        agent = Agent(provider, work_dir=tmpdir)
        result = agent.chat("loop forever")
        assert "maximum tool calls" in result.lower()

    def test_on_tool_call_callback(self, tmpdir):
        calls = []

        def on_tool_call(name, args, result):
            calls.append((name, args))

        provider = MockProvider([
            LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="list_directory", arguments={})],
                input_tokens=10, output_tokens=5,
            ),
            LLMResponse(text="Done.", input_tokens=10, output_tokens=5),
        ])
        agent = Agent(provider, work_dir=tmpdir, on_tool_call=on_tool_call)
        agent.chat("list")
        assert len(calls) == 1
        assert calls[0][0] == "list_directory"


class TestAgentStats:
    def test_token_tracking(self, tmpdir):
        provider = MockProvider([
            LLMResponse(text="Hello!", input_tokens=100, output_tokens=50),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        agent.chat("hi")
        stats = agent.get_stats()
        assert stats["input_tokens"] == 100
        assert stats["output_tokens"] == 50
        assert stats["turns"] == 1

    def test_tool_call_count(self, tmpdir):
        provider = MockProvider([
            LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="list_directory", arguments={})],
                input_tokens=10, output_tokens=5,
            ),
            LLMResponse(text="Done.", input_tokens=10, output_tokens=5),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        agent.chat("list")
        stats = agent.get_stats()
        assert stats["total_tool_calls"] == 1


class TestAgentInit:
    def test_initialize(self, tmpdir):
        from pyoz.tools.file_tools import write_file
        write_file(os.path.join(tmpdir, "app.py"), "def main(): pass\n")
        provider = MockProvider()
        agent = Agent(provider, work_dir=tmpdir)
        info = agent.initialize()
        assert info["files_indexed"] >= 1
        assert info["provider"] == "claude"
        assert info["model"] == "mock-model"


class TestSystemPrompt:
    def test_includes_capabilities(self):
        prompt = _build_system_prompt("", "")
        assert "PyOz" in prompt
        assert "CAPABILITIES" in prompt

    def test_includes_rules(self):
        prompt = _build_system_prompt("Use Java 17", "")
        assert "Use Java 17" in prompt
        assert "RULES" in prompt

    def test_includes_context(self):
        prompt = _build_system_prompt("", "FILE: test.py\n  class Foo")
        assert "CODEBASE CONTEXT" in prompt
        assert "test.py" in prompt


class TestLoadRules:
    def test_load_pyoz_md(self, tmpdir):
        from pyoz.tools.file_tools import write_file
        write_file(os.path.join(tmpdir, "PYOZ.md"), "# Rules\n- Use Python 3\n")
        rules = _load_rules(tmpdir)
        assert "Use Python 3" in rules

    def test_load_dotpyoz_rules(self, tmpdir):
        from pyoz.tools.file_tools import write_file
        os.makedirs(os.path.join(tmpdir, ".pyoz"))
        write_file(os.path.join(tmpdir, ".pyoz", "rules.md"), "# Rules\n- Use Go\n")
        rules = _load_rules(tmpdir)
        assert "Use Go" in rules

    def test_no_rules_file(self, tmpdir):
        rules = _load_rules(tmpdir)
        assert rules == ""


class TestAgentClear:
    def test_clear_history(self, tmpdir):
        provider = MockProvider([
            LLMResponse(text="Hi!", input_tokens=10, output_tokens=5),
        ])
        agent = Agent(provider, work_dir=tmpdir)
        agent.chat("hello")
        assert len(agent.messages) > 0
        agent.clear_history()
        assert len(agent.messages) == 0
        assert agent.turn_count == 0


class TestConvertMessages:
    """Tests for _convert_messages — cross-provider session format conversion."""

    # --- Same-family: no conversion needed ---

    def test_same_provider_no_conversion(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = _convert_messages(msgs, "claude", "claude")
        assert result is msgs  # same object, untouched

    def test_openai_to_deepseek_no_conversion(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "x"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "tc1", "content": "file contents"},
        ]
        result = _convert_messages(msgs, "openai", "deepseek")
        assert result is msgs  # same object, untouched

    def test_deepseek_to_openai_no_conversion(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = _convert_messages(msgs, "deepseek", "openai")
        assert result is msgs

    # --- Claude → OpenAI/DeepSeek ---

    def test_claude_to_openai_tool_use(self):
        """Claude tool_use blocks should become OpenAI tool_calls."""
        msgs = [
            {"role": "user", "content": "list files"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check."},
                    {
                        "type": "tool_use",
                        "id": "tc1",
                        "name": "list_directory",
                        "input": {"path": "/tmp"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tc1",
                        "content": "file1.py\nfile2.py",
                    },
                ],
            },
            {"role": "assistant", "content": "Found 2 files."},
        ]
        result = _convert_messages(msgs, "claude", "deepseek")

        # msg[0]: plain user message — unchanged
        assert result[0] == {"role": "user", "content": "list files"}

        # msg[1]: assistant with tool_calls
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Let me check."
        assert len(result[1]["tool_calls"]) == 1
        tc = result[1]["tool_calls"][0]
        assert tc["id"] == "tc1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "list_directory"
        assert json.loads(tc["function"]["arguments"]) == {"path": "/tmp"}

        # msg[2]: tool result → role=tool message
        assert result[2]["role"] == "tool"
        assert result[2]["tool_call_id"] == "tc1"
        assert result[2]["content"] == "file1.py\nfile2.py"

        # msg[3]: plain assistant text — unchanged
        assert result[3] == {"role": "assistant", "content": "Found 2 files."}

    def test_claude_to_openai_multiple_tool_results(self):
        """Multiple tool_result blocks in one Claude user message
        become separate tool messages."""
        msgs = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tc1",
                        "content": "result1",
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "tc2",
                        "content": "result2",
                    },
                ],
            },
        ]
        result = _convert_messages(msgs, "claude", "openai")
        assert len(result) == 2
        assert result[0] == {
            "role": "tool",
            "tool_call_id": "tc1",
            "content": "result1",
        }
        assert result[1] == {
            "role": "tool",
            "tool_call_id": "tc2",
            "content": "result2",
        }

    def test_claude_to_openai_text_only_messages_unchanged(self):
        """Plain text messages should pass through unchanged."""
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = _convert_messages(msgs, "claude", "deepseek")
        assert result == msgs

    # --- OpenAI/DeepSeek → Claude ---

    def test_openai_to_claude_tool_calls(self):
        """OpenAI tool_calls should become Claude content array
        with tool_use blocks."""
        msgs = [
            {"role": "user", "content": "list files"},
            {
                "role": "assistant",
                "content": "Let me check.",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {
                            "name": "list_directory",
                            "arguments": '{"path": "/tmp"}',
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "tc1",
                "content": "file1.py\nfile2.py",
            },
            {"role": "assistant", "content": "Found 2 files."},
        ]
        result = _convert_messages(msgs, "deepseek", "claude")

        # msg[0]: plain user — unchanged
        assert result[0] == {"role": "user", "content": "list files"}

        # msg[1]: assistant with content array
        assert result[1]["role"] == "assistant"
        content = result[1]["content"]
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "Let me check."}
        assert content[1]["type"] == "tool_use"
        assert content[1]["id"] == "tc1"
        assert content[1]["name"] == "list_directory"
        assert content[1]["input"] == {"path": "/tmp"}

        # msg[2]: tool → user with tool_result
        assert result[2]["role"] == "user"
        assert isinstance(result[2]["content"], list)
        assert result[2]["content"][0]["type"] == "tool_result"
        assert result[2]["content"][0]["tool_use_id"] == "tc1"

        # msg[3]: plain assistant — unchanged
        assert result[3] == {"role": "assistant", "content": "Found 2 files."}

    def test_openai_to_claude_consecutive_tool_results_merged(self):
        """Consecutive tool role messages should be merged into one
        Claude user message."""
        msgs = [
            {"role": "tool", "tool_call_id": "tc1", "content": "result1"},
            {"role": "tool", "tool_call_id": "tc2", "content": "result2"},
        ]
        result = _convert_messages(msgs, "openai", "claude")
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert len(result[0]["content"]) == 2
        assert result[0]["content"][0]["tool_use_id"] == "tc1"
        assert result[0]["content"][1]["tool_use_id"] == "tc2"

    def test_openai_to_claude_text_only_unchanged(self):
        """Plain text messages pass through for OpenAI→Claude too."""
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = _convert_messages(msgs, "openai", "claude")
        assert result == msgs

    # --- Edge cases ---

    def test_empty_messages(self):
        assert _convert_messages([], "claude", "deepseek") == []
        assert _convert_messages([], "deepseek", "claude") == []

    def test_claude_to_openai_assistant_no_text(self):
        """Assistant with only tool_use (no text block) should get
        empty content string."""
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tc1",
                        "name": "run_command",
                        "input": {"command": "ls"},
                    },
                ],
            },
        ]
        result = _convert_messages(msgs, "claude", "deepseek")
        assert result[0]["content"] == ""
        assert len(result[0]["tool_calls"]) == 1

    def test_openai_to_claude_assistant_no_text(self):
        """Assistant with empty content + tool_calls should only have
        tool_use blocks."""
        msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {
                            "name": "run_command",
                            "arguments": '{"command": "ls"}',
                        },
                    },
                ],
            },
        ]
        result = _convert_messages(msgs, "openai", "claude")
        content = result[0]["content"]
        assert isinstance(content, list)
        # no text block since content was empty
        assert len(content) == 1
        assert content[0]["type"] == "tool_use"

    def test_ollama_to_claude(self):
        """Ollama is OpenAI-style, so conversion to Claude should work."""
        msgs = [
            {
                "role": "assistant",
                "content": "checking",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "x.py"}',
                        },
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "tc1", "content": "code here"},
        ]
        result = _convert_messages(msgs, "ollama", "claude")
        assert result[0]["role"] == "assistant"
        assert isinstance(result[0]["content"], list)
        assert result[1]["role"] == "user"
        assert result[1]["content"][0]["type"] == "tool_result"

    def test_claude_to_ollama(self):
        """Claude to Ollama conversion should work like Claude to OpenAI."""
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tc1",
                        "name": "read_file",
                        "input": {"path": "x.py"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tc1",
                        "content": "code here",
                    },
                ],
            },
        ]
        result = _convert_messages(msgs, "claude", "ollama")
        assert result[0]["role"] == "assistant"
        assert "tool_calls" in result[0]
        assert result[1]["role"] == "tool"
        assert result[1]["tool_call_id"] == "tc1"
