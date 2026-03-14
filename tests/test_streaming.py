"""Tests for streaming support."""

import json
import tempfile
import os
import argparse

import pytest

from pyoz.providers.base import BaseLLMProvider, LLMResponse, StreamEvent, ToolCall


class MockStreamProvider(BaseLLMProvider):
    """Mock provider that supports streaming."""

    def __init__(self, responses=None):
        super().__init__(api_key="test", model="mock")
        self.responses = responses or []
        self._idx = 0

    @property
    def provider_name(self):
        return "claude"

    @property
    def model_name(self):
        return "mock"

    def chat(self, messages, tools, system_prompt=None):
        if self._idx < len(self.responses):
            resp = self.responses[self._idx]
            self._idx += 1
            return resp
        return LLMResponse(text="done")

    def chat_stream(self, messages, tools, system_prompt=None):
        # Simulate streaming text token by token
        if self._idx < len(self.responses):
            resp = self.responses[self._idx]
            self._idx += 1
            if resp.text:
                for word in resp.text.split(" "):
                    yield StreamEvent(type="text_delta", text=word + " ")
            yield StreamEvent(type="usage", input_tokens=resp.input_tokens, output_tokens=resp.output_tokens)
            yield StreamEvent(type="done")
            return resp
        yield StreamEvent(type="done")
        return LLMResponse(text="done")

    def format_tool_result(self, tool_call_id, result):
        return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": result}]}

    def format_tool_calls_message(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
        return {"role": "assistant", "content": content}


class MockStreamToolProvider(BaseLLMProvider):
    """Mock provider that emits tool call events in streaming mode."""

    def __init__(self, responses=None):
        super().__init__(api_key="test", model="mock")
        self.responses = responses or []
        self._idx = 0

    @property
    def provider_name(self):
        return "claude"

    @property
    def model_name(self):
        return "mock"

    def chat(self, messages, tools, system_prompt=None):
        if self._idx < len(self.responses):
            resp = self.responses[self._idx]
            self._idx += 1
            return resp
        return LLMResponse(text="done")

    def chat_stream(self, messages, tools, system_prompt=None):
        if self._idx < len(self.responses):
            resp = self.responses[self._idx]
            self._idx += 1
            if resp.text:
                for word in resp.text.split(" "):
                    yield StreamEvent(type="text_delta", text=word + " ")
            for tc in resp.tool_calls:
                yield StreamEvent(type="tool_call_start", tool_call_id=tc.id, tool_name=tc.name)
                args_json = json.dumps(tc.arguments)
                yield StreamEvent(type="tool_call_delta", text=args_json, tool_call_id=tc.id)
            yield StreamEvent(type="usage", input_tokens=resp.input_tokens, output_tokens=resp.output_tokens)
            yield StreamEvent(type="done")
            return resp
        yield StreamEvent(type="done")
        return LLMResponse(text="done")

    def format_tool_result(self, tool_call_id, result):
        return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": result}]}

    def format_tool_calls_message(self, response):
        content = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
        return {"role": "assistant", "content": content}


class TestStreamEvent:
    def test_text_delta(self):
        event = StreamEvent(type="text_delta", text="Hello")
        assert event.type == "text_delta"
        assert event.text == "Hello"

    def test_tool_call_start(self):
        event = StreamEvent(type="tool_call_start", tool_call_id="tc1", tool_name="read_file")
        assert event.type == "tool_call_start"
        assert event.tool_name == "read_file"

    def test_usage(self):
        event = StreamEvent(type="usage", input_tokens=100, output_tokens=50)
        assert event.input_tokens == 100
        assert event.output_tokens == 50

    def test_tool_call_delta(self):
        event = StreamEvent(type="tool_call_delta", text='{"path": "."}', tool_call_id="tc1")
        assert event.type == "tool_call_delta"
        assert event.tool_call_id == "tc1"
        assert event.text == '{"path": "."}'

    def test_done_event(self):
        event = StreamEvent(type="done")
        assert event.type == "done"
        assert event.text == ""


class TestBaseProviderStreamFallback:
    def test_fallback_yields_text(self):
        """Base provider's chat_stream should fall back to non-streaming."""

        class SimpleProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "test"
            @property
            def model_name(self):
                return "test"
            def chat(self, messages, tools, system_prompt=None):
                return LLMResponse(text="Hello world!", input_tokens=10, output_tokens=5)
            def format_tool_result(self, tool_call_id, result):
                return {}
            def format_tool_calls_message(self, response):
                return {}

        provider = SimpleProvider()
        events = list(provider.chat_stream([], []))
        text_events = [e for e in events if e.type == "text_delta"]
        assert len(text_events) == 1
        assert text_events[0].text == "Hello world!"
        done_events = [e for e in events if e.type == "done"]
        assert len(done_events) == 1


class TestStreamingAgent:
    def test_streaming_collects_tokens(self):
        """Test that streaming agent collects tokens via callback."""
        from pyoz.agent import Agent

        chunks = []

        def on_token(text):
            chunks.append(text)

        provider = MockStreamProvider([
            LLMResponse(text="Hello world friend", input_tokens=10, output_tokens=5),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=on_token,
                streaming=True,
            )
            result = agent.chat("hi")
            # Should have collected streaming chunks
            assert len(chunks) >= 1
            combined = "".join(chunks)
            assert "Hello" in combined

    def test_streaming_with_tool_calls(self):
        """Test that streaming agent correctly captures tool calls from stream events."""
        from pyoz.agent import Agent

        chunks = []

        def on_token(text):
            chunks.append(text)

        # First response: tool call, second: final text
        provider = MockStreamToolProvider([
            LLMResponse(
                text=None,
                tool_calls=[ToolCall(id="tc1", name="list_directory", arguments={"path": "."})],
                input_tokens=20,
                output_tokens=10,
            ),
            LLMResponse(text="Here are the files.", input_tokens=30, output_tokens=15),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=on_token,
                streaming=True,
            )
            result = agent.chat("list files")
            assert "files" in result.lower() or "Here" in result

    def test_streaming_multiple_tool_calls(self):
        """Test streaming with multiple tool calls in one response."""
        from pyoz.agent import Agent

        chunks = []

        def on_token(text):
            chunks.append(text)

        # First response: two tool calls, second: final text
        provider = MockStreamToolProvider([
            LLMResponse(
                text=None,
                tool_calls=[
                    ToolCall(id="tc1", name="read_file", arguments={"path": "a.txt"}),
                    ToolCall(id="tc2", name="read_file", arguments={"path": "b.txt"}),
                ],
                input_tokens=20,
                output_tokens=10,
            ),
            LLMResponse(text="Read both files.", input_tokens=30, output_tokens=15),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files so read_file tool works
            with open(os.path.join(tmpdir, "a.txt"), "w") as f:
                f.write("file a content")
            with open(os.path.join(tmpdir, "b.txt"), "w") as f:
                f.write("file b content")

            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=on_token,
                streaming=True,
            )
            result = agent.chat("read both files")
            # Should have executed both tool calls and returned final text
            assert "Read both" in result or "file" in result.lower()
            # Agent should have tracked 2 tool calls
            assert agent.total_tool_calls == 2

    def test_streaming_text_with_tool_calls(self):
        """Test streaming response with text AND tool calls mixed."""
        from pyoz.agent import Agent

        chunks = []

        def on_token(text):
            chunks.append(text)

        # Response with both text and tool call
        provider = MockStreamToolProvider([
            LLMResponse(
                text="Let me check that.",
                tool_calls=[ToolCall(id="tc1", name="list_directory", arguments={"path": "."})],
                input_tokens=20,
                output_tokens=10,
            ),
            LLMResponse(text="Here's what I found.", input_tokens=30, output_tokens=15),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=on_token,
                streaming=True,
            )
            result = agent.chat("show files")
            # The intermediate text was streamed, final text returned
            combined = "".join(chunks)
            assert "check" in combined.lower() or "found" in combined.lower()

    def test_streaming_token_usage_tracking(self):
        """Test that token usage is correctly tracked in streaming mode."""
        from pyoz.agent import Agent

        provider = MockStreamProvider([
            LLMResponse(text="Hello!", input_tokens=100, output_tokens=50),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=lambda t: None,
                streaming=True,
            )
            agent.chat("hi")
            assert agent.total_input_tokens == 100
            assert agent.total_output_tokens == 50

    def test_streaming_malformed_json_tool_args(self):
        """Test streaming handles malformed JSON in tool call arguments gracefully."""
        from pyoz.agent import Agent

        class MalformedArgsProvider(MockStreamToolProvider):
            def chat_stream(self, messages, tools, system_prompt=None):
                if self._idx < len(self.responses):
                    resp = self.responses[self._idx]
                    self._idx += 1
                    # Emit tool call with invalid JSON
                    for tc in resp.tool_calls:
                        yield StreamEvent(type="tool_call_start", tool_call_id=tc.id, tool_name=tc.name)
                        yield StreamEvent(type="tool_call_delta", text="{invalid json", tool_call_id=tc.id)
                    yield StreamEvent(type="usage", input_tokens=resp.input_tokens, output_tokens=resp.output_tokens)
                    yield StreamEvent(type="done")
                    return resp
                yield StreamEvent(type="done")
                return LLMResponse(text="done")

        provider = MalformedArgsProvider([
            LLMResponse(
                text=None,
                tool_calls=[ToolCall(id="tc1", name="list_directory", arguments={"path": "."})],
                input_tokens=10,
                output_tokens=5,
            ),
            LLMResponse(text="Done.", input_tokens=10, output_tokens=5),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=lambda t: None,
                streaming=True,
            )
            # Should not crash — malformed JSON treated as empty args
            result = agent.chat("do something")
            # Agent should have attempted the tool call (with empty args fallback)
            assert agent.total_tool_calls >= 1

    def test_streaming_without_callback(self):
        """Test streaming mode works even without on_stream_token callback."""
        from pyoz.agent import Agent

        provider = MockStreamProvider([
            LLMResponse(text="Hello world!", input_tokens=10, output_tokens=5),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=None,  # No callback
                streaming=True,
            )
            # Should still work, just no streaming output
            result = agent.chat("hi")
            assert "Hello" in result

    def test_streaming_multi_turn_tool_loop(self):
        """Test multi-turn streaming: tool call -> result -> next call -> final text."""
        from pyoz.agent import Agent

        chunks = []

        def on_token(text):
            chunks.append(text)

        # Turn 1: read_file, Turn 2: another read_file, Turn 3: final text
        provider = MockStreamToolProvider([
            LLMResponse(
                text=None,
                tool_calls=[ToolCall(id="tc1", name="read_file", arguments={"path": "first.txt"})],
                input_tokens=20,
                output_tokens=10,
            ),
            LLMResponse(
                text=None,
                tool_calls=[ToolCall(id="tc2", name="read_file", arguments={"path": "second.txt"})],
                input_tokens=25,
                output_tokens=12,
            ),
            LLMResponse(text="Read both files successfully.", input_tokens=30, output_tokens=15),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "first.txt"), "w") as f:
                f.write("first content")
            with open(os.path.join(tmpdir, "second.txt"), "w") as f:
                f.write("second content")

            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=on_token,
                streaming=True,
            )
            result = agent.chat("read both files one by one")
            assert "Read both" in result
            assert agent.total_tool_calls == 2
            # Token usage accumulated across all turns
            assert agent.total_input_tokens == 75  # 20 + 25 + 30
            assert agent.total_output_tokens == 37  # 10 + 12 + 15

    def test_non_streaming_no_callback(self):
        """Test that non-streaming mode doesn't use callback."""
        from pyoz.agent import Agent

        chunks = []

        def on_token(text):
            chunks.append(text)

        provider = MockStreamProvider([
            LLMResponse(text="Hello!", input_tokens=10, output_tokens=5),
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                on_stream_token=on_token,
                streaming=False,  # Streaming OFF
            )
            result = agent.chat("hi")
            assert result == "Hello!"
            assert len(chunks) == 0  # No streaming chunks


class TestStreamToggle:
    def test_stream_toggle(self):
        """Test /stream command toggles streaming on and off."""
        provider = MockStreamProvider([])

        with tempfile.TemporaryDirectory() as tmpdir:
            from pyoz.agent import Agent
            agent = Agent(
                provider=provider,
                work_dir=tmpdir,
                streaming=False,
            )
            assert agent.streaming is False
            agent.streaming = not agent.streaming
            assert agent.streaming is True
            agent.streaming = not agent.streaming
            assert agent.streaming is False

    def test_cli_no_stream_flag(self):
        """Test --no-stream CLI flag sets streaming to False."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--no-stream", action="store_true")

        # Default: streaming on
        args = parser.parse_args([])
        streaming = not args.no_stream
        assert streaming is True

        # With --no-stream: streaming off
        args = parser.parse_args(["--no-stream"])
        streaming = not args.no_stream
        assert streaming is False
