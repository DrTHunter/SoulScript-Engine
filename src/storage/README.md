# src/storage/

Persistence layer for conversation state and event logging.

## Components

| File | Purpose |
|------|---------|
| `state_store.py` | `StateStore` -- rolling-window conversation state with atomic writes |
| `journal_store.py` | `JournalStore` -- append-only JSONL event log |
| `human_journal.py` | `append_entry` -- human-readable diary at `data/journal.md` |
| `tool_request_writer.py` | `ToolRequestWriter` -- append-only tool request log at `data/tool_requests.md` |
| `narrative_writer.py` | `NarrativeWriter` -- per-profile narrative log at `data/<profile>/narrative.md` |

## State Store

- **File:** `data/<profile>/state.json`
- **Format:** JSON array of message objects
- **Rolling window:** Keeps the system prompt + last N non-system messages (configurable via `window_size` in profile YAML, default 50)
- **Atomic writes:** Uses `tempfile` + `os.replace` to prevent corruption on crash
- **Loaded at session start**, saved at session end (and on graceful exit)

## Journal Store

- **File:** `data/<profile>/journal.jsonl`
- **Format:** One JSON object per line, each with `timestamp`, `event`, and `data` fields
- **Append-only:** Never rewritten, never truncated
- **Event types:**
  - `user_input` -- user message content
  - `agent_selected` -- which agent was routed to
  - `llm_request_meta` -- model, provider, message count, iteration
  - `llm_response` -- content, tool calls, model
  - `tool_call` -- tool name and arguments
  - `tool_result` -- tool output
  - `policy_stop` -- why the policy gate stopped execution
  - `error` -- any error during the loop

The journal is the full forensic record of everything that happened. The state file is just the trimmed conversation window for session continuity.
