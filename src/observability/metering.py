"""Token accounting and USD cost metering for LLM calls.

Central module for all metering logic.  Consumers import data classes
and helper functions; they never compute costs themselves.

Usage:
    from src.observability.metering import meter_response, zero_metering

    m = meter_response(response, provider="openai", messages=messages)
    session = zero_metering()
    session = session + m  # accumulate
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml

from src.llm_client.base import LLMResponse


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class TokenUsage:
    """Raw token counts for a single LLM call or an aggregation."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    is_estimated: bool = False

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            is_estimated=self.is_estimated or other.is_estimated,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "is_estimated": self.is_estimated,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TokenUsage":
        return cls(
            prompt_tokens=d.get("prompt_tokens", 0),
            completion_tokens=d.get("completion_tokens", 0),
            total_tokens=d.get("total_tokens", 0),
            is_estimated=d.get("is_estimated", False),
        )


@dataclass
class CostBreakdown:
    """USD cost breakdown for a single call or aggregation."""

    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"

    def __add__(self, other: "CostBreakdown") -> "CostBreakdown":
        return CostBreakdown(
            input_cost=self.input_cost + other.input_cost,
            output_cost=self.output_cost + other.output_cost,
            total_cost=self.total_cost + other.total_cost,
            currency=self.currency,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_cost": round(self.input_cost, 6),
            "output_cost": round(self.output_cost, 6),
            "total_cost": round(self.total_cost, 6),
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CostBreakdown":
        return cls(
            input_cost=d.get("input_cost", 0.0),
            output_cost=d.get("output_cost", 0.0),
            total_cost=d.get("total_cost", 0.0),
            currency=d.get("currency", "USD"),
        )


@dataclass
class Metering:
    """Combined usage + cost for a single LLM call or aggregation."""

    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostBreakdown = field(default_factory=CostBreakdown)
    model: str = ""
    provider: str = ""

    def __add__(self, other: "Metering") -> "Metering":
        return Metering(
            usage=self.usage + other.usage,
            cost=self.cost + other.cost,
            model=self.model or other.model,
            provider=self.provider or other.provider,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "usage": self.usage.to_dict(),
            "cost": self.cost.to_dict(),
            "model": self.model,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Metering":
        return cls(
            usage=TokenUsage.from_dict(d.get("usage", {})),
            cost=CostBreakdown.from_dict(d.get("cost", {})),
            model=d.get("model", ""),
            provider=d.get("provider", ""),
        )


# ------------------------------------------------------------------
# Pricing registry
# ------------------------------------------------------------------

_PRICING_CACHE: Optional[Dict] = None


def _default_pricing_path() -> str:
    """Return the default pricing YAML path relative to project root."""
    project_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    return os.path.join(project_root, "config", "pricing.yaml")


def load_pricing(path: Optional[str] = None) -> Dict:
    """Load the pricing registry YAML.  Returns empty dict if file missing."""
    path = path or _default_pricing_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_pricing() -> Dict:
    """Lazy-load and cache the pricing registry."""
    global _PRICING_CACHE
    if _PRICING_CACHE is None:
        _PRICING_CACHE = load_pricing()
    return _PRICING_CACHE


def reset_pricing_cache() -> None:
    """Clear the cached pricing (useful for tests)."""
    global _PRICING_CACHE
    _PRICING_CACHE = None


def get_price(
    provider: str, model: str, pricing: Optional[Dict] = None
) -> Tuple[float, float]:
    """Return (input_per_1m, output_per_1m) for a provider/model.

    Lookup order:
      1. pricing[provider][model]        (exact match)
      2. pricing[provider][prefix]       (model starts with a known key)
      3. pricing[provider]["_default"]   (provider fallback)
      4. (0.0, 0.0)                      (unknown provider/model)
    """
    pricing = pricing or _get_pricing()
    provider_prices = pricing.get(provider, {})

    # 1. Exact match
    model_prices = provider_prices.get(model)

    # 2. Prefix match — e.g. "gpt-5.2-2025-12-11" matches "gpt-5.2"
    if not model_prices:
        for key, val in provider_prices.items():
            if key.startswith("_"):
                continue
            if isinstance(val, dict) and model.startswith(key):
                model_prices = val
                break

    # 3. Provider default
    if not model_prices:
        model_prices = provider_prices.get("_default")

    if not model_prices:
        return (0.0, 0.0)
    return (
        float(model_prices.get("input_per_1m", 0.0)),
        float(model_prices.get("output_per_1m", 0.0)),
    )


def compute_cost(
    usage: TokenUsage,
    provider: str,
    model: str,
    pricing: Optional[Dict] = None,
) -> CostBreakdown:
    """Compute USD cost from token usage and pricing registry."""
    input_per_1m, output_per_1m = get_price(provider, model, pricing)
    input_cost = usage.prompt_tokens * input_per_1m / 1_000_000
    output_cost = usage.completion_tokens * output_per_1m / 1_000_000
    return CostBreakdown(
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=input_cost + output_cost,
    )


# ------------------------------------------------------------------
# Estimation helpers
# ------------------------------------------------------------------

def estimate_tokens_from_text(text: str) -> int:
    """Estimate token count from a string using chars/4 heuristic."""
    return max(len(text) // 4, 1) if text else 0


def estimate_tokens_from_messages(messages: List[Dict[str, Any]]) -> int:
    """Estimate prompt token count from a message list using chars/4."""
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "") or ""
        total_chars += len(content)
    return max(total_chars // 4, 1)


# ------------------------------------------------------------------
# Response metering (the main boundary function)
# ------------------------------------------------------------------

def meter_response(
    response: LLMResponse,
    provider: str,
    messages: Optional[List[Dict[str, Any]]] = None,
    pricing: Optional[Dict] = None,
) -> Metering:
    """Create a Metering object from a single LLM response.

    If ``response.usage`` is populated (e.g. OpenAI), uses exact counts.
    If ``response.usage`` is None (e.g. Ollama), estimates via chars/4.
    """
    if response.usage:
        usage = TokenUsage(
            prompt_tokens=response.usage.get("prompt_tokens", 0),
            completion_tokens=response.usage.get("completion_tokens", 0),
            total_tokens=response.usage.get("total_tokens", 0),
            is_estimated=False,
        )
    else:
        prompt_tokens = (
            estimate_tokens_from_messages(messages) if messages else 0
        )
        completion_tokens = estimate_tokens_from_text(response.content or "")
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            is_estimated=True,
        )

    model = response.model
    cost = compute_cost(usage, provider, model, pricing)
    return Metering(usage=usage, cost=cost, model=model, provider=provider)


def zero_metering() -> Metering:
    """Return a zero-valued Metering for use as an accumulator seed."""
    return Metering()
