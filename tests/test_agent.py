"""Tests for the agent loop."""

import os
import tempfile
import pytest
from unittest.mock import MagicMock

from pyoz.agent import Agent, _build_system_prompt, _load_rules
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
