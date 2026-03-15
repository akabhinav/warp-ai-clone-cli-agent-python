"""Ollama LLM provider using native tool calling."""

import json
import os
import time
from typing import Any

import httpx

from collections.abc import Generator

from pyoz.providers.base import BaseLLMProvider, LLMResponse, StreamEvent, ToolCall

DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_URL = "http://localhost:11434"
MAX_RETRIES = 3


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider with native tool calling."""

    def __init__(self, model: str | None = None, base_url: str | None = None, **kwargs):
        super().__init__(api_key=None, model=model or DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("OLLAMA_URL") or DEFAULT_URL).rstrip("/")
        self._client = httpx.Client(timeout=300.0)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(self._convert_messages(messages))

        # Convert tools to Ollama format (same as OpenAI format)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
        }
        if tools:
            body["tools"] = tools

        url = f"{self.base_url}/api/chat"

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._client.post(url, json=body)
                if resp.status_code != 200:
                    if attempt < MAX_RETRIES:
                        time.sleep(2 ** (attempt + 1))
                        continue
                    raise RuntimeError(f"Ollama API {resp.status_code}: {resp.text[:500]}")
                break
            except httpx.ConnectError:
                raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}. Is it running?")
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError("Ollama request timed out")

        data = resp.json()
        return self._parse_response(data)

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert messages to Ollama-compatible format."""
        converted = []
        for msg in messages:
            if msg["role"] == "user" and isinstance(msg.get("content"), list):
                # Convert Claude-style tool results
                text_parts = []
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        text_parts.append(f"Tool result: {block.get('content', '')}")
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif isinstance(block, str):
                        text_parts.append(block)
                converted.append({"role": "user", "content": "\n".join(text_parts)})
            elif msg["role"] == "assistant" and isinstance(msg.get("content"), list):
                text_parts = []
                tool_calls = []
                for block in msg["content"]:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "function": {
                                    "name": block["name"],
                                    "arguments": block.get("input", {}),
                                }
                            })
                out: dict[str, Any] = {"role": "assistant", "content": "\n".join(text_parts) or ""}
                if tool_calls:
                    out["tool_calls"] = tool_calls
                converted.append(out)
            elif msg["role"] == "tool":
                converted.append({
                    "role": "tool",
                    "content": msg.get("content", ""),
                })
            else:
                converted.append(msg)
        return converted

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        msg = data.get("message", {})
        tool_calls = []

        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(
                    id=f"ollama_{id(tc)}",
                    name=func.get("name", ""),
                    arguments=args,
                ))

        # Ollama doesn't report token counts in the same way
        eval_count = data.get("eval_count", 0)
        prompt_eval = data.get("prompt_eval_count", 0)

        return LLMResponse(
            text=msg.get("content") or None,
            tool_calls=tool_calls,
            input_tokens=prompt_eval,
            output_tokens=eval_count,
            stop_reason=data.get("done_reason"),
        )

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> Generator[StreamEvent, None, LLMResponse]:
        """Stream a chat response from Ollama."""
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(self._convert_messages(messages))

        body: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "stream": True,
        }
        if tools:
            body["tools"] = tools

        url = f"{self.base_url}/api/chat"
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        input_tokens = 0
        output_tokens = 0

        for attempt in range(MAX_RETRIES + 1):
            try:
                with self._client.stream("POST", url, json=body) as resp:
                    if resp.status_code != 200:
                        if attempt < MAX_RETRIES:
                            time.sleep(2 ** (attempt + 1))
                            continue
                        error_msg = resp.read().decode()[:500]
                        raise RuntimeError(f"Ollama API {resp.status_code}: {error_msg}")

                    for line in resp.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        msg = data.get("message", {})

                        # Text content
                        if msg.get("content"):
                            text_parts.append(msg["content"])
                            yield StreamEvent(type="text_delta", text=msg["content"])

                        # Tool calls (arrive in final message)
                        if msg.get("tool_calls"):
                            for tc in msg["tool_calls"]:
                                func = tc.get("function", {})
                                args = func.get("arguments", {})
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except json.JSONDecodeError:
                                        args = {}
                                tool_call = ToolCall(
                                    id=f"ollama_{id(tc)}",
                                    name=func.get("name", ""),
                                    arguments=args,
                                )
                                tool_calls.append(tool_call)
                                yield StreamEvent(
                                    type="tool_call_start",
                                    tool_call_id=tool_call.id,
                                    tool_name=tool_call.name,
                                )

                        # Final message with token counts
                        if data.get("done"):
                            input_tokens = data.get("prompt_eval_count", 0)
                            output_tokens = data.get("eval_count", 0)

                break
            except httpx.ConnectError:
                raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}. Is it running?")
            except httpx.TimeoutException:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError("Ollama stream timed out")

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
            stop_reason="stop",
        )

    def format_tool_result(self, tool_call_id: str, result: str) -> dict[str, Any]:
        return {
            "role": "tool",
            "content": result,
        }

    def format_tool_calls_message(self, response: LLMResponse) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": response.text or ""}
        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                }
                for tc in response.tool_calls
            ]
        return msg
