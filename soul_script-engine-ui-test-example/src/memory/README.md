# src/memory/

The Memory System — FAISS semantic search backed by vault.jsonl storage, plus a separate NotesFAISS index for knowledge notes.

## Components

| File | Purpose |
|------|---------|
| `types.py` | `Memory` dataclass, taxonomy tiers, valid scopes/categories/sources, write-gate constants |
| `vault.py` | `VaultStore` class — all CRUD + search + write-gating + consolidation + promotion + snapshot |
| `faiss_memory.py` | `FAISSMemory` class — semantic search over vault memories using FAISS + sentence-transformers |
| `notes_faiss.py` | `NotesFAISS` class — read-only FAISS index over chunked soul scripts & knowledge notes |
| `load_and_index.py` | Builds the NotesFAISS index from user notes JSON files. Runnable as `python -m src.memory.load_and_index` |
| `chunker.py` | `SemanticChunker` — splits documents by `### H3` headers with configurable size limits |
| `pii_guard.py` | Regex-based PII detection (SSN, credit cards, passwords, API keys) |
| `injector.py` | `build_memory_block()` (relevance-filtered) and `build_snapshot_block()` (always-injected) for prompt injection |
| `faiss_schema.json` | JSON Schema for FAISS configuration |
| `FAISS_README.md` | Detailed documentation for the FAISS vector memory system |

## Two FAISS Systems

### 1. FAISSMemory (Mutable — Vault Memories)
- Backed by `data/memory/vault.jsonl` as source of truth
- FAISS index is an ephemeral cache rebuilt as needed
- Supports add, update, delete, search
- Stores: canon memories, register memories, user-created facts

### 2. NotesFAISS (Immutable — Knowledge Notes)
- Read-only index over soul scripts and knowledge notes from `data/user_notes/`
- Chunks by `### header` sections
- Stored in `data/memory/faiss/` (`notes_index.faiss` + `notes_meta.json`)
- Rebuilt on web app startup or via `/api/faiss/reindex`
- Supports filtered search by `note_ids`

### Technical Details
- **Embedding model:** `all-mpnet-base-v2` (768-dimensional)
- **Index type:** `IndexFlatIP` (cosine similarity)
- **Dependencies:** `faiss-cpu>=1.7.4`, `sentence-transformers>=2.2.0`

## Memory Taxonomy (3 tiers)

| Tier | Purpose | Lifecycle | Example |
|------|---------|-----------|---------|
| **CANON** | Durable invariants — mission, bio, identity, hard constraints | Rarely changes; always high-priority in injection | `"CANON: Mission — stabilize runtime, explore boundaries, add tools in layers"` |
| **REGISTER** | Mutable state — one record per `topic_id`, version-bumped in place | Updated frequently via `update_by_topic()` | `topic_id="current_projects"` → auto-upserts each write |
| **LOG** | Ephemeral — tick markers, runtime snapshots, check-ins | Write-gate **rejects** these; they do not belong in the vault | `"tick marker"` → blocked |

## Storage

- **File:** `data/memory/vault.jsonl`
- **FAISS:** `data/memory/faiss/` (ephemeral indexes)
- **Format:** One JSON object per line, each a `Memory` record
- **Fully append-only:** Adds, updates, and deletes all append new lines. Nothing is ever rewritten or removed (except `compact()`).

## Record Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique 12-char hex identifier |
| `text` | str | Memory content (max 1200 chars) |
| `scope` | str | `shared` or agent-specific (e.g. `codex_animus`, `astraea`, `callum`) |
| `category` | str | Content category (bio, mission, project, goal, etc.) |
| `tier` | str | `canon` or `register` (defaults to `canon` for backward compat) |
| `topic_id` | str? | Stable key for register-tier upserts (e.g. `current_projects`) |
| `tags` | list | Optional tags for filtering |
| `created_at` | str | ISO timestamp |
| `updated_at` | str? | ISO timestamp of last update |
| `source` | str? | Origin: `chat`, `manual`, `tool`, `operator`, `promotion` |
| `deleted_at` | str? | ISO timestamp if soft-deleted (tombstone) |
| `version` | int | Starts at 1, incremented on each update/delete |

## Version Resolution

Each record has an `id` and `version` (starts at 1). On read, the vault scans all lines and resolves each `id` to its highest-version line.

- **Update:** Appends a new line with same `id`, `version + 1`, updated fields
- **Delete:** Appends a tombstone line with same `id`, `version + 1`, `deleted_at` set
- **Bulk Delete:** Resolves latest state once, appends tombstones for all valid IDs in a single pass
- **Bulk Add:** Adds multiple memories in one pass with per-item validation
- **Read:** Resolves latest versions, filters out tombstones

## Write-Gate Pipeline

Every `add_memory()` / `bulk_add()` call passes through the write-gate before storage:

1. **Reject LOG-tier noise** — scans text for journal-only signals (`tick marker`, `runtime snapshot`, `check-in`, `heartbeat`, `no changes`, `nothing to report`, `status unchanged`, `routine scan`, `ephemeral`)
2. **Reject `tier="log"`** — explicit log tier is always blocked
3. **Length gate** — text over 1200 chars is rejected (compress or split first)
4. **Scope / tier / source validation**
5. **PII guard** — blocks SSNs, credit card numbers, passwords, API keys
6. **Register upsert** — if `tier=register` and `topic_id` matches an existing active record in the same scope → version-bump update instead of new record
7. **Duplicate gate** — blocks near-duplicates (token overlap ≥ 60% or SequenceMatcher ≥ 70%)
8. **Capacity gate** — rejects when vault is full (default 100 active)

## Topic-Based Upsert (Registers)

Register-tier memories use `topic_id` as a stable key to avoid paraphrase spam:

```python
# First call creates a new register
vault.add_memory("Projects: dashboard, memory upgrade",
                 "shared", "project", tier="register", topic_id="current_projects")

# Second call with same topic_id + scope → updates in place (version bump)
vault.add_memory("Projects: dashboard, memory upgrade, email integration",
                 "shared", "project", tier="register", topic_id="current_projects")
```

Explicit upsert API: `vault.update_by_topic(topic_id, scope, text, ...)` — creates if missing, updates if exists.

## Consolidation & Promotion

| Method | Purpose |
|--------|---------|
| `find_consolidation_candidates(scope, floor)` | Find pairs of similar active memories (for merging review) |
| `propose_deletions(scope)` | Identify deletion candidates with reasons — **never auto-deletes** |
| `promote_to_canon(memory_id, canonical_text)` | Upgrade register → canon tier (`source="promotion"`) |

## Snapshot (Always-Injected Summary)

`vault.build_snapshot(scope)` produces a compact Markdown block containing:
- All **canon** memories (invariants)
- **Register** memories that have a `topic_id` (actively maintained state)

This is meant to be always-injected alongside notes — small and high-signal.

## Injection Modes

| Function | Mode | Use case |
|----------|------|----------|
| `build_snapshot_block(vault, scopes)` | Always-injected | Canon + active registers as compact summary |
| `build_memory_block(vault, scopes, query=...)` | Relevance-filtered | Search/recall with tier-aware grouping (canon first) |

## Scoping

Scopes are dynamic per agent: `shared` + the agent's own name. Each agent sees `shared` + its own scope (e.g. `shared` + `codex_animus`).

## Safety

- **PII guard:** Blocks memories containing SSNs, credit card numbers, passwords, API keys
- **Write-gate:** Rejects ephemeral/journal-only noise before it reaches the vault
- **Duplicate detection:** Blocks near-duplicates (token overlap or sequence similarity) within the same scope
- **Concurrent safety:** Append-only means no file locks needed — two agents can write simultaneously
- **Deletion safety:** `propose_deletions()` only suggests — never auto-deletes

## Search Scoring

Token overlap + substring bonus (+0.3) + SequenceMatcher ratio × 0.4. Requires at least one matching token.

## Vault Health

`vault_stats()` returns: active count, max, utilization %, deleted count, raw lines, bloat ratio, breakdown by scope/tier/category, register topic count.

## Key Config (in profile YAML)

```yaml
memory:
  enabled: true
  scopes: [shared, codex_animus]
  max_items: 20
  similarity_threshold: 0.85
```
