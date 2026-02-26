"""Anthropic Messages API client.

Talks directly to the Anthropic Messages API (https://api.anthropic.com/v1/messages).
Supports tool calling, Computer Use (beta), and extended thinking.

Set ANTHROPIC_API_KEY in your environment, or the client will fall back to the
profile dict (not recommended for production).
"""

import json
import os
import uuid
from typing import Any, Dict, List, Optional

import requests

from src.llm_client.base import LLMClient, LLMResponse


class AnthropicClient(LLMClient):
    """Native Anthropic provider for the agent runtime."""

    # Anthropic models → context windows (for reference only)
    KNOWN_MODELS = {
        "claude-sonnet-4-20250514": 200_000,
        "claude-opus-4-20250514": 200_000,
        "claude-3-5-sonnet-20241022": 200_000,
        "claude-3-5-haiku-20241022": 200_000,
        "claude-3-opus-20240229": 200_000,
    }

    def __init__(self, profile: dict):
        self.model: str = profile["model"]
        self.base_url: str = profile.get(
            "base_url", "https://api.anthropic.com"
        ).rstrip("/")
        self.api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
        self.temperature: float = profile.get("temperature", 0.7)
        self.max_tokens: int = profile.get("max_tokens", 4096)

        if not self.api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Export it before running with the anthropic provider."
            )

    # ------------------------------------------------------------------
    # Main chat entry-point
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        # Separate system message from conversation messages
        system_text, conv_messages = self._extract_system(messages)

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages(conv_messages),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        if system_text:
            body["system"] = system_text

        # Build tool definitions
        api_tools = self._build_tools(tools)
        if api_tools:
            body["tools"] = api_tools

        resp = requests.post(
            f"{self.base_url}/v1/messages",
            headers=headers,
            json=body,
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()

        return self._parse_response(data)

    # ------------------------------------------------------------------
    # Tool schema conversion
    # ------------------------------------------------------------------
    def _build_tools(
        self, tools: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Convert internal tool definitions to Anthropic format."""
        api_tools: List[Dict[str, Any]] = []

        # Standard function tools
        if tools:
            for t in tools:
                api_tools.append({
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                })

        return api_tools

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    def _parse_response(self, data: Dict[str, Any]) -> LLMResponse:
        """Parse Anthropic response into canonical LLMResponse."""
        content_blocks = data.get("content", [])

        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        for block in content_blocks:
            btype = block.get("type")

            if btype == "text":
                text_parts.append(block["text"])

            elif btype == "tool_use":
                tool_calls.append({
                    "call_id": block["id"],
                    "tool": block["name"],
                    "arguments": block.get("input", {}),
                })

        # Usage
        usage_raw = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_raw.get("input_tokens", 0),
            "completion_tokens": usage_raw.get("output_tokens", 0),
            "total_tokens": (
                usage_raw.get("input_tokens", 0)
                + usage_raw.get("output_tokens", 0)
            ),
        }

        return LLMResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            model=data.get("model", self.model),
            usage=usage,
            raw=data,
        )

    # ------------------------------------------------------------------
    # Message format conversion
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_system(
        messages: List[Dict[str, Any]],
    ) -> tuple:
        """Pull out the system message (if any) and return (system_text, rest)."""
        if messages and messages[0].get("role") == "system":
            return messages[0].get("content", ""), messages[1:]
        return "", messages

    @staticmethod
    def _convert_messages(
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Convert internal message format → Anthropic Messages API format.

        Key differences from OpenAI:
        - Tool results use role="user" with tool_result content blocks
        - Assistant tool calls use tool_use content blocks
        - No separate tool_call_id field at message level
        """
        out: List[Dict[str, Any]] = []

        for m in messages:
            role = m["role"]

            if role == "system":
                # System messages are handled separately; skip here
                continue

            elif role == "tool":
                # Anthropic: tool results are sent as user messages
                out.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.get("tool_call_id", ""),
                            "content": m.get("content", ""),
                        }
                    ],
                })

            elif role == "assistant" and m.get("tool_calls"):
                # Assistant messages with tool calls → content blocks
                blocks: List[Dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc["call_id"],
                        "name": tc["tool"],
                        "input": tc["arguments"],
                    })
                out.append({"role": "assistant", "content": blocks})

            elif role == "assistant":
                out.append({"role": "assistant", "content": m.get("content", "")})

            elif role == "user":
                out.append({"role": "user", "content": m.get("content", "")})

            else:
                # Fallback for any other role
                out.append({"role": "user", "content": m.get("content", "")})

        return out
