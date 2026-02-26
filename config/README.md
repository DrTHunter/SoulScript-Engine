# config/

Configuration files for the runtime and web dashboard.

## Files

| File | Purpose |
|------|--------|
| `config.example.yaml` | Example YAML config structure (default profile, data dir, global policy overrides) |
| `state.example.json` | Example state file format |
| `settings.json` | Web dashboard settings — timezone, display preferences, agent avatars, per-agent configs (model, voice, display name, knowledge attachments), vault limits, and tool config. Auto-created on first save. |
| `connections.json` | External service connection config (LLM providers, TTS, STT endpoints). Managed via Dashboard → Connections. |

These are reference/runtime files. Per-agent configuration lives in:
- `profiles/` — per-agent YAML configs
- `data/` — runtime state, chats, memory vault, FAISS indexes (auto-generated)
