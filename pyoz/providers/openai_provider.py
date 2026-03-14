"""OpenAI LLM provider using native tool calling."""

import json
import time
from typing import Any

import httpx

from pyoz.providers.base import BaseLLMProvider, LLMResponse, ToolCall

DEFAULT_MODEL = "gpt-4o"
API_URL = "https://api.openai.com/v1/chat/completions"
MAX_TOKENS = 8192
RETRY_STATUS_CODES = {429, 500, 503}
MAX_RETRIES = 3


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider with native function calling."""

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(api_key, model or DEFAULT_MODEL)
        self._client = httpx.Client(timeout=120.0)

    @property
    def provider_name(self) -> str:
        return "openai"

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

        # Build messages with system prompt first
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
                    raise RuntimeError(f"OpenAI API {resp.status_code}: {error_msg}")
                break
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError("OpenAI API request timed out")

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
