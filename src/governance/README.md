# src/governance/

Governance hardening modules — anti-drift tracking and audit logging for the agent runtime.

## Modules

### `active_directives.py`

Session-scoped in-memory registry of which directives were actually loaded into the prompt pipeline.

- **`ActiveDirectives`** — singleton class (class-level state, no instantiation needed)
  - `record(heading, body, scope, *, manifest_entry=None)` — register one directive
  - `record_sections(sections, manifest=None)` — batch-register `DirectiveSection` objects; cross-references manifest for IDs/versions
  - `list()` → `[{id, name, scope, version, sha256, loaded_at_utc, token_estimate}]`
  - `ids()` → `[str]`
  - `summary()` → `{count, ids, scopes, total_tokens}`
  - `count()` → `int`
  - `reset()` — clear all entries (session start / tests)

Populated automatically by `src/directives/injector.py` when directives are loaded.

### `change_log.py`

Append-only governance change audit log written to `data/shared/change_log.jsonl`.

- **`build_governance_snapshot(profile, policy, active_directives_summary, memory_status)`** — builds a minimal, diff-friendly snapshot (base_url redacted to host-only)
- **`build_change_record(change_type, scope, requestor, rationale, before, after, *, approver, needs_approval)`** — builds a full change-log record with `change_id`, `timestamp_utc`, `diff_summary`
- **`ChangeLog(path=None)`** — append-only JSONL writer
  - `append(record)` — write one record
  - `read_all()` → `[dict]`
  - `read_recent(n=10)` → `[dict]` (last N)

Valid `change_type` values: `tool`, `directive`, `policy`, `memory`, `config`.

#### Safety rules

- No raw prompt text in records
- `base_url` redacted to hostname only
- No secrets / API keys / tokens
- No unrelated filesystem paths

## Data flow

```
Session start / tick start
    ↓
ActiveDirectives.reset()
    ↓
directives/injector.py → build_directives_block()
    ↓
ActiveDirectives.record_sections()  (auto-populates)
    ↓
ChangeLog.append()  (optional — for governance-critical changes)
```

## Tests

See `tests/test_governance.py` — 127 checks covering all modules and integration points.
