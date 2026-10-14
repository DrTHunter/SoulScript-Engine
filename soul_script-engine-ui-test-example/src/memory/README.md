# src/memory/

The Memory System — FAISS semantic search backed by vault.jsonl storage, plus a separate NotesFAISS index for knowledge notes.

## Components

| File | Purpose |
|------|---------|
| `types.py` | `Memory` dataclass, taxonomy tiers, valid tiers/categories/sources, length cap |
| `vault.py` | `VaultStore` class — append-only JSONL CRUD, versioning, topic upsert, snapshot |
| `faiss_memory.py` | `FAISSMemory` class — semantic search over vault memories using FAISS + sentence-transformers |
| `notes_faiss.py` | `NotesFAISS` class — read-only FAISS index over chunked soul scripts & knowledge notes |
| `load_and_index.py` | Builds the NotesFAISS index from user notes JSON files. Runnable as `python -m src.memory.load_and_index` |
| `chunker.py` | `SemanticChunker` — splits documents by `### H3` headers with configurable size limits |
| `pii_guard.py` | Regex-based PII detection (SSN, credit cards, passwords, API keys) |
| `faiss_schema.json` | JSON Schema for FAISS configuration |
| `FAISS_README.md` | Detailed documentation for the FAISS vector memory system |

Prompt injection (the always-injected snapshot + relevance-filtered search) is wired directly in `web/app.py` via `FAISSMemory.snapshot()` and `FAISSMemory.search()` — there is no separate injector module.

## Two FAISS Systems

### 1. FAISSMemory (Mutable — Vault Memories)
- Backed by `data/memory/vault.jsonl` as source of truth
- FAISS index is an ephemeral cache rebuilt as needed
- Supports add, update, update_by_topic, delete, search, snapshot
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
| `scope` | str | `shared` or agent-specific (e.g. `codex_animus`, `elysia`, `orion`) |
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
- **Read:** Resolves latest versions, filters out tombstones

## Write-Gate Pipeline

Every `create_memory()` / `update_memory()` call passes through these checks before storage:

1. **Empty-text rejection** — text must be non-blank after `strip()`
2. **Length gate** — text over `MAX_MEMORY_TEXT_LENGTH` (1200) chars is rejected (compress or split first)
3. **Tier validation** — `tier` must be one of `VALID_TIERS` (`canon`, `register`); `"log"` and any other value is rejected
4. **PII guard** — blocks SSNs, credit card numbers, passwords, API keys

Note what's *not* here yet, despite being defined in `types.py`/imagined in earlier drafts: there is no scope/category/source validation against `VALID_SCOPES`/`VALID_CATEGORIES`/`VALID_SOURCES`, no `JOURNAL_ONLY_SIGNALS` noise filter, no duplicate-detection gate, and no capacity gate. Callers should not rely on the vault to catch those.

## Topic-Based Upsert (Registers)

Register-tier memories use `topic_id` as a stable key to avoid paraphrase spam. `vault.update_by_topic(topic_id, scope, text, ...)` (or `FAISSMemory.update_by_topic(...)` to keep the FAISS index in sync) creates the record on first call and version-bumps it **in place** on every subsequent call with the same `topic_id` + `scope`:

```python
# First call creates a new register
vault.update_by_topic("current_projects", "shared",
                       "Projects: dashboard, memory upgrade")

# Second call with same topic_id + scope -> updates in place (version bump)
vault.update_by_topic("current_projects", "shared",
                       "Projects: dashboard, memory upgrade, email integration")
```

## Snapshot (Always-Injected Summary)

`vault.build_snapshot(scope)` (or `FAISSMemory.snapshot(scope)`, which just delegates to it) produces a compact Markdown block containing:
- All **canon** memories (invariants)
- **Register** memories that have a `topic_id` (actively maintained state)

This is *not* a similarity search — it's a flat scan of the vault, so identity/bio facts can't be missed just because a query doesn't match them well. `web/app.py` injects this block into the system prompt on every turn (always-on), separately from the relevance-filtered `FAISSMemory.search()` results used for episodic recall (canon facts are excluded from search results to avoid double-injecting them).

## Scoping

Scopes are dynamic per agent: `shared` + the agent's own name. Each agent sees `shared` + its own scope (e.g. `shared` + `codex_animus`).

## Safety

- **PII guard:** Blocks memories containing SSNs, credit card numbers, passwords, API keys
- **Length/tier gates:** Rejects over-length text and any tier outside `canon`/`register` (see Write-Gate Pipeline above)
- **Concurrent safety:** Append-only means no file locks needed — two agents can write simultaneously
- **Deletion safety:** Deletes are soft (tombstone, `deleted_at` set) — nothing is physically removed except by explicit `compact()`

There is no duplicate-detection gate and no automated consolidation/promotion tooling — paraphrase spam is only avoided where callers use `update_by_topic()` for register-tier state instead of creating a fresh record on every write.

## Search Scoring

`FAISSMemory.search()` is pure cosine similarity: query and memory text are both embedded with `all-mpnet-base-v2`, L2-normalized, and compared via `IndexFlatIP` (inner product on normalized vectors == cosine similarity). The returned `score` is that similarity, highest first.

## Vault Health

`VaultStore.stats()` returns: active count, deleted count, raw line count, and breakdowns by scope/category/tier. `FAISSMemory.stats()` adds FAISS-side numbers on top: `faiss_vectors` (total rows), `faiss_deleted`, `faiss_stale_rows` (rows superseded by a re-embed on update), and `faiss_effective` (vectors actually live and searchable).

## Key Config (in profile YAML)

```yaml
memory:
  enabled: true
  scopes: [shared, codex_animus]
  max_items: 20
  similarity_threshold: 0.85
```

Note: this block is currently documentation-only — `web/app.py` does not read it. Scope is hardcoded as `["shared", agent]` (`web/app.py`), and there's no enforced `max_items`/`similarity_threshold` cutoff in `vault.py` or `faiss_memory.py`.
