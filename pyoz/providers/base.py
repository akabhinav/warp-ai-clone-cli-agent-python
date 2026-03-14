"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None


@dataclass
class StreamEvent:
    """A single event from a streaming response."""
    type: str  # "text_delta", "tool_call_start", "tool_call_delta", "done", "usage"
    text: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key
        self.model = model
        self.streaming = False

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send a chat request with tools and return the response."""
        ...

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        """Stream a chat response token-by-token.

        Yields StreamEvent objects as they arrive.
        Returns the final LLMResponse when complete.

        Default implementation falls back to non-streaming chat.
        """
        response = self.chat(messages, tools, system_prompt)
        if response.text:
            yield StreamEvent(type="text_delta", text=response.text)
        yield StreamEvent(
            type="usage",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        yield StreamEvent(type="done")
        return response

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, result: str) -> dict[str, Any]:
        """Format a tool result for the next API call."""
        ...

    @abstractmethod
    def format_tool_calls_message(self, response: LLMResponse) -> dict[str, Any]:
        """Format the assistant's tool-calling response for conversation history."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...
