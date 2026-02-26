# config/

Configuration files for the runtime and web dashboard.

## Files

| File | Purpose |
|------|--------|
| `config.example.yaml` | Example YAML config structure |
| `pricing.yaml` | Token pricing per provider/model (USD per 1M tokens). Supports exact match, prefix match (e.g. `gpt-5.2` matches `gpt-5.2-2025-12-11`), and `_default` per provider. |
| `state.example.json` | Example state file format |
| `settings.json` | Web dashboard and tool settings. Stores timezone, display preferences, and tool-specific config (e.g. `tool_config.web_search` for search mode presets, SearXNG URL, and knowledge gate toggle). Auto-created on first save. |
| `connections.json` | External service connection config (LLM providers, TTS, STT endpoints). |

These are reference/runtime files. Per-agent configuration lives in:
- `profiles/` -- per-agent YAML configs
- `data/` -- runtime state and journals (auto-generated)
