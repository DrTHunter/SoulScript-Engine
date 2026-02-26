"""OpenAI-compatible Chat Completions client.

Works with any API that follows the OpenAI /v1/chat/completions schema
(OpenAI, Azure OpenAI, Together AI, Groq, etc.).
"""

import json
import os
from typing import Any, Dict, List, Optional

import requests

from src.llm_client.base import LLMClient, LLMResponse


class OpenAICompatClient(LLMClient):
    # Map provider names to their API key env vars and default base URLs
    _PROVIDER_DEFAULTS = {
        "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1"),
        "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1"),
    }

    def __init__(self, profile: dict):
        self.model: str = profile["model"]
        provider = profile.get("provider", "openai")
        env_var, default_url = self._PROVIDER_DEFAULTS.get(
            provider, ("OPENAI_API_KEY", "https://api.openai.com/v1")
        )
        self.base_url: str = profile.get("base_url", default_url).rstrip("/")
        self.api_key: str = profile.get("api_key", "") or os.environ.get(env_var, "")
        self.temperature: float = profile.get("temperature", 0.7)
        if not self.api_key:
            raise EnvironmentError(
                f"{env_var} environment variable is not set. "
                f"Export it before running with the {provider} provider."
            )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=body,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        content = choice.get("content")

        tool_calls = []
        for tc in choice.get("tool_calls", []) or []:
            tool_calls.append({
                "call_id": tc["id"],
                "tool": tc["function"]["name"],
                "arguments": json.loads(tc["function"]["arguments"]),
            })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", self.model),
            usage=data.get("usage"),
            raw=data,
        )

    # ------------------------------------------------------------------
    # Internal message format  ->  OpenAI wire format
    # ------------------------------------------------------------------
    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for m in messages:
            role = m["role"]

            if role == "tool":
                out.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", ""),
                    "content": m.get("content", ""),
                })

            elif role == "assistant" and m.get("tool_calls"):
                oai_tcs = []
                for tc in m["tool_calls"]:
                    oai_tcs.append({
                        "id": tc["call_id"],
                        "type": "function",
                        "function": {
                            "name": tc["tool"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    })
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": oai_tcs,
                })

            else:
                out.append({"role": role, "content": m.get("content", "")})

        return out
