"""LLM client interface and canonical response schema."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMResponse:
    """Provider-agnostic response from any chat completion call."""
    content: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    # Each tool_call dict: {"call_id": str, "tool": str, "arguments": dict}
    model: str = ""
    usage: Optional[Dict[str, int]] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class LLMClient(ABC):
    """Abstract base for all LLM provider clients."""

    model: str  # concrete classes must set this

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Send a chat completion request and return a normalised response."""
        ...
