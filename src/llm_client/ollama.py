"""Ollama local chat client.

Talks to the Ollama REST API at /api/chat (default http://localhost:11434).
Supports tool calling for models that advertise it.
"""

import uuid
from typing import Any, Dict, List, Optional

import requests

from src.llm_client.base import LLMClient, LLMResponse


class OllamaClient(LLMClient):
    def __init__(self, profile: dict):
        self.model: str = profile["model"]
        self.base_url: str = profile.get("base_url", "http://localhost:11434").rstrip("/")
        self.temperature: float = profile.get("temperature", 0.7)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]

        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=body,
            timeout=300,  # local models can be slow
        )
        resp.raise_for_status()
        data = resp.json()

        msg = data.get("message", {})
        content = msg.get("content") or None

        tool_calls: List[Dict[str, Any]] = []
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            tool_calls.append({
                "call_id": uuid.uuid4().hex[:12],
                "tool": fn.get("name", ""),
                "arguments": fn.get("arguments", {}),
            })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", self.model),
            usage=None,
            raw=data,
        )

    # ------------------------------------------------------------------
    # Internal message format  ->  Ollama wire format
    # ------------------------------------------------------------------
    @staticmethod
    def _convert_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for m in messages:
            role = m["role"]

            if role == "tool":
                out.append({"role": "tool", "content": m.get("content", "")})

            elif role == "assistant" and m.get("tool_calls"):
                ollama_tcs = []
                for tc in m["tool_calls"]:
                    ollama_tcs.append({
                        "function": {
                            "name": tc["tool"],
                            "arguments": tc["arguments"],
                        }
                    })
                entry: Dict[str, Any] = {"role": "assistant"}
                if m.get("content"):
                    entry["content"] = m["content"]
                entry["tool_calls"] = ollama_tcs
                out.append(entry)

            else:
                out.append({"role": role, "content": m.get("content", "")})

        return out
