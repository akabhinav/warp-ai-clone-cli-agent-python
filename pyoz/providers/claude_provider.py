"""Claude (Anthropic) LLM provider using native tool calling."""

import json
import time
from collections.abc import Generator
from typing import Any

import httpx

from pyoz.providers.base import BaseLLMProvider, LLMResponse, StreamEvent, ToolCall

DEFAULT_MODEL = "claude-sonnet-4-20250514"
API_URL = "https://api.anthropic.com/v1/messages"
MAX_TOKENS = 8192
RETRY_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 3


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API provider with native tool_use."""

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(api_key, model or DEFAULT_MODEL)
        self._client = httpx.Client(timeout=120.0)

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self.model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": messages,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = tools

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._client.post(API_URL, headers=headers, json=body)
                if resp.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    error_msg = resp.text[:500]
                    raise RuntimeError(f"Claude API {resp.status_code}: {error_msg}")
                break
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError("Claude API request timed out")

        data = resp.json()
        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        text_parts = []
        tool_calls = []

        for block in data.get("content", []):
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block.get("input", {}),
                ))

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            input_tokens=data.get("usage", {}).get("input_tokens", 0),
            output_tokens=data.get("usage", {}).get("output_tokens", 0),
            stop_reason=data.get("stop_reason"),
        )

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        """Stream a chat response from Claude using SSE."""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": messages,
            "stream": True,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = tools

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        input_tokens = 0
        output_tokens = 0
        current_tool_id = ""
        current_tool_name = ""
        current_tool_json = ""

        for attempt in range(MAX_RETRIES + 1):
            try:
                with self._client.stream("POST", API_URL, headers=headers, json=body) as resp:
                    if resp.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
                        time.sleep(2 ** (attempt + 1))
                        continue
                    if resp.status_code != 200:
                        error_msg = resp.read().decode()[:500]
                        raise RuntimeError(f"Claude API {resp.status_code}: {error_msg}")

                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type", "")

                        if event_type == "content_block_start":
                            block = event.get("content_block", {})
                            if block.get("type") == "tool_use":
                                current_tool_id = block.get("id", "")
                                current_tool_name = block.get("name", "")
                                current_tool_json = ""
                                yield StreamEvent(
                                    type="tool_call_start",
                                    tool_call_id=current_tool_id,
                                    tool_name=current_tool_name,
                                )

                        elif event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                text_parts.append(text)
                                yield StreamEvent(type="text_delta", text=text)
                            elif delta.get("type") == "input_json_delta":
                                current_tool_json += delta.get("partial_json", "")
                                yield StreamEvent(
                                    type="tool_call_delta",
                                    text=delta.get("partial_json", ""),
                                    tool_call_id=current_tool_id,
                                )

                        elif event_type == "content_block_stop":
                            if current_tool_name:
                                try:
                                    args = json.loads(current_tool_json) if current_tool_json else {}
                                except json.JSONDecodeError:
                                    args = {}
                                tool_calls.append(ToolCall(
                                    id=current_tool_id,
                                    name=current_tool_name,
                                    arguments=args,
                                ))
                                current_tool_name = ""
                                current_tool_id = ""
                                current_tool_json = ""

                        elif event_type == "message_delta":
                            usage = event.get("usage", {})
                            output_tokens = usage.get("output_tokens", output_tokens)

                        elif event_type == "message_start":
                            usage = event.get("message", {}).get("usage", {})
                            input_tokens = usage.get("input_tokens", input_tokens)

                break
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError("Claude API stream timed out")

        yield StreamEvent(
            type="usage",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        yield StreamEvent(type="done")

        final_text = "".join(text_parts) if text_parts else None
        return LLMResponse(
            text=final_text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason="end_turn",
        )

    def format_tool_result(self, tool_call_id: str, result: str) -> dict[str, Any]:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": result,
                }
            ],
        }

    def format_tool_calls_message(self, response: LLMResponse) -> dict[str, Any]:
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
