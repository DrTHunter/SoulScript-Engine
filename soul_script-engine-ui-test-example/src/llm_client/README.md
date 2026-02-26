# src/llm_client/

LLM provider abstraction layer. Supports multiple providers through a common interface.

## Components

| File | Purpose |
|------|---------|
| `base.py` | `LLMClient` ABC + `LLMResponse` dataclass — the common interface |
| `factory.py` | `create_client(profile)` — dispatches to the right provider class |
| `openai_compat.py` | OpenAI Chat Completions API client (also used by DeepSeek) |
| `ollama.py` | Ollama `/api/chat` client |
| `anthropic_client.py` | Native Anthropic API client (Claude models) |

## Interface

Every provider implements:

```python
class LLMClient(ABC):
    def chat(self, messages: list, tools: list = None) -> LLMResponse:
        ...
```

`LLMResponse` contains:
- `content` — text response (str or None)
- `tool_calls` — list of `{"call_id": str, "tool": str, "arguments": dict}`
- `model` — model name string
- `usage` — token counts (if available)
- `raw` — full API response dict

## Providers

### OpenAI (`openai_compat.py`)
- Posts to `{base_url}/chat/completions`
- Reads `OPENAI_API_KEY` from environment variable
- Converts internal tool-call format to/from OpenAI wire format

### Anthropic (`anthropic_client.py`)
- Uses the native Anthropic SDK (`anthropic` package)
- Reads `ANTHROPIC_API_KEY` from environment variable
- Known models: `claude-sonnet-4`, `claude-opus-4`, `claude-3.5-sonnet`, `claude-3.5-haiku`, `claude-3-opus`

### Ollama (`ollama.py`)
- Posts to `{base_url}/api/chat` with `stream: false`
- No API key needed (local server)
- Generates `call_id` via `uuid.uuid4().hex[:12]` for tool calls

### DeepSeek (via `openai_compat.py`)
- Uses the OpenAI-compatible client
- Reads `DEEPSEEK_API_KEY` from environment variable
- Posts to `{base_url}/chat/completions`

## Configuration

Set in each profile YAML:

```yaml
provider: openai          # "openai", "ollama", "anthropic", or "deepseek"
model: gpt-5.1            # model identifier
base_url: https://api.openai.com/v1  # API endpoint
temperature: 0.7
```

## API Keys

Set via environment variables:

```powershell
# OpenAI
setx OPENAI_API_KEY "sk-your-key-here"

# Anthropic
setx ANTHROPIC_API_KEY "sk-ant-your-key-here"

# DeepSeek
setx DEEPSEEK_API_KEY "your-key-here"
```
