"""DeepSeek LLM provider — OpenAI-compatible API."""

import json
import time
from collections.abc import Generator
from typing import Any

import httpx

from pyoz.providers.base import BaseLLMProvider, LLMResponse, StreamEvent, ToolCall

DEFAULT_MODEL = "deepseek-chat"
API_URL = "https://api.deepseek.com/v1/chat/completions"
MAX_TOKENS = 8192
RETRY_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 3


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek API provider (OpenAI-compatible)."""

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(api_key, model or DEFAULT_MODEL)
        self._client = httpx.Client(timeout=120.0)

    @property
    def provider_name(self) -> str:
        return "deepseek"

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
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": api_messages,
        }
        if tools:
            body["tools"] = tools

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._client.post(API_URL, headers=headers, json=body)
                if resp.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                if resp.status_code != 200:
                    error_msg = resp.text[:500]
                    raise RuntimeError(f"DeepSeek API {resp.status_code}: {error_msg}")
                break
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError("DeepSeek API request timed out")

        data = resp.json()
        return self._parse_response(data)

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        choice = data["choices"][0]
        msg = choice["message"]
        tool_calls = []

        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=args,
                ))

        usage = data.get("usage", {})
        return LLMResponse(
            text=msg.get("content"),
            tool_calls=tool_calls,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            stop_reason=choice.get("finish_reason"),
        )

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        """Stream a chat response from DeepSeek using SSE."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": api_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            body["tools"] = tools

        text_parts: list[str] = []
        tool_calls_map: dict[int, dict[str, str]] = {}
        input_tokens = 0
        output_tokens = 0

        for attempt in range(MAX_RETRIES + 1):
            try:
                with self._client.stream("POST", API_URL, headers=headers, json=body) as resp:
                    if resp.status_code in RETRY_STATUS_CODES and attempt < MAX_RETRIES:
                        time.sleep(2 ** (attempt + 1))
                        continue
                    if resp.status_code != 200:
                        error_msg = resp.read().decode()[:500]
                        raise RuntimeError(f"DeepSeek API {resp.status_code}: {error_msg}")

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

                        if event.get("usage"):
                            input_tokens = event["usage"].get("prompt_tokens", 0)
                            output_tokens = event["usage"].get("completion_tokens", 0)
                            continue

                        choices = event.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        if delta.get("content"):
                            text_parts.append(delta["content"])
                            yield StreamEvent(type="text_delta", text=delta["content"])

                        if delta.get("tool_calls"):
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                if idx not in tool_calls_map:
                                    tool_calls_map[idx] = {
                                        "id": tc.get("id", ""),
                                        "name": tc.get("function", {}).get("name", ""),
                                        "args": "",
                                    }
                                    if tool_calls_map[idx]["name"]:
                                        yield StreamEvent(
                                            type="tool_call_start",
                                            tool_call_id=tool_calls_map[idx]["id"],
                                            tool_name=tool_calls_map[idx]["name"],
                                        )
                                if tc.get("id") and not tool_calls_map[idx]["id"]:
                                    tool_calls_map[idx]["id"] = tc["id"]
                                if tc.get("function", {}).get("name") and not tool_calls_map[idx]["name"]:
                                    tool_calls_map[idx]["name"] = tc["function"]["name"]
                                arg_chunk = tc.get("function", {}).get("arguments", "")
                                if arg_chunk:
                                    tool_calls_map[idx]["args"] += arg_chunk
                                    yield StreamEvent(
                                        type="tool_call_delta",
                                        text=arg_chunk,
                                        tool_call_id=tool_calls_map[idx]["id"],
                                    )

                break
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError("DeepSeek API stream timed out")

        final_tool_calls = []
        for idx in sorted(tool_calls_map.keys()):
            tc_data = tool_calls_map[idx]
            try:
                args = json.loads(tc_data["args"]) if tc_data["args"] else {}
            except json.JSONDecodeError:
                args = {}
            final_tool_calls.append(ToolCall(
                id=tc_data["id"],
                name=tc_data["name"],
                arguments=args,
            ))

        yield StreamEvent(
            type="usage",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        yield StreamEvent(type="done")

        final_text = "".join(text_parts) if text_parts else None
        return LLMResponse(
            text=final_text,
            tool_calls=final_tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason="stop",
        )

    def format_tool_result(self, tool_call_id: str, result: str) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }

    def format_tool_calls_message(self, response: LLMResponse) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": response.text or ""}
        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ]
        return msg
