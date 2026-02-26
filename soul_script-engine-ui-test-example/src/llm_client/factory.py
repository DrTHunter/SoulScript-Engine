"""Create an LLM client from a profile dict.

Adding a new provider:
  1. Implement a subclass of LLMClient in its own module.
  2. Import it here and add a key to _PROVIDERS.
"""

from src.llm_client.base import LLMClient
from src.llm_client.openai_compat import OpenAICompatClient
from src.llm_client.ollama import OllamaClient
from src.llm_client.anthropic_client import AnthropicClient

_PROVIDERS = {
    "openai": OpenAICompatClient,
    "deepseek": OpenAICompatClient,  # DeepSeek uses OpenAI-compatible API
    "ollama": OllamaClient,
    "anthropic": AnthropicClient,
}

# Environment variable mapping for non-OpenAI providers using OpenAI-compat client
_API_KEY_ENV_VARS = {
    "deepseek": "DEEPSEEK_API_KEY",
}


def create_client(profile: dict) -> LLMClient:
    provider = profile["provider"]
    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available: {sorted(_PROVIDERS)}"
        )
    return cls(profile)
