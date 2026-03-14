"""Tests for streaming support."""

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
        import tempfile
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

    def test_non_streaming_no_callback(self):
        """Test that non-streaming mode doesn't use callback."""
        import tempfile
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
