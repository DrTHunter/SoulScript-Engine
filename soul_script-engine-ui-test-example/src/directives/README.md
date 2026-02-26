# src/directives/

Parses, scores, and retrieves sections from user-authored directive markdown files.

## Components

| File | Purpose |
|------|---------|
| `parser.py` | `DirectiveSection` dataclass + `parse_directive_file()` — splits markdown on `## Headings` |
| `store.py` | `DirectiveStore` — loads sections, scores relevance, provides search/list/get |
| `injector.py` | `build_directives_block()` — formats relevant sections for system prompt injection |
| `manifest.py` | `generate_manifest()` / `save_manifest()` / `load_manifest()` / `validate_manifest()` / `diff_manifest()` / `audit_changes()` — builds, persists, validates, and diffs `directives/manifest.json` |

## How It Works

1. User writes markdown files in `directives/` with `## Heading` sections
2. At session start, `DirectiveStore` lazily parses the relevant files
3. Sections are scored against the last user message using the same algorithm as the Memory Vault (token overlap + substring bonus + SequenceMatcher)
4. Only top-scoring sections are injected into the system prompt
5. Agents can also search directives mid-conversation via the `directives` tool

## Scoring Algorithm

Same as `src/memory/vault.py`:

```
score = token_overlap_ratio + substring_bonus(0.3) + SequenceMatcher_ratio * 0.4
```

- Requires at least one matching token to score at all
- Heading text is included in scoring (high-signal)

## Key Config (in profile YAML)

```yaml
directives:
  enabled: true
  scopes: [shared, codex_animus]
  max_sections: 5
```

## Manifest

The manifest (`directives/manifest.json`) is an auto-generated index of every
directive section. It provides:

- Unique ID per section (`{scope}.{slug}`)
- SHA-256 content hash for drift detection
- Token estimate (chars / 4 heuristic)
- Trigger keywords for hybrid retrieval
- Risk level, version, status, and dependencies

Regenerate from the CLI:

```bash
python -m src.directives.manifest
```

Agents can read the manifest via the `directives` tool's `manifest` action.

## Change Control

`diff_manifest(old, new)` compares two manifests and returns structured deltas:
- **added** — directives in *new* not in *old*
- **removed** — directives in *old* not in *new*
- **changed** — common directives whose SHA-256 hash differs
- **unchanged_count** — count of identical entries

`audit_changes()` is the convenience wrapper: loads the persisted manifest,
generates a live one, and returns the diff.

Agents can call `directives.changes` to see the audit deltas at any time.

## Validation

`validate_manifest(manifest, directives_dir=None, check_hashes=True)` performs structural and content integrity checks:

- All required top-level keys present (`manifest_version`, `generated_utc`, `hash_algo`, `root_paths`, `default_retrieval_mode`, `directives`)
- All 12 required per-entry keys present
- Enum values in range (`status`: active/deprecated/experimental, `risk`: low/medium/high)
- No duplicate directive IDs
- Source files exist on disk
- SHA-256 hash matches live content (detects drift)

Returns `{"valid": bool, "errors": [str]}`.

## Directive Files

Located in `directives/` at the project root:
- `shared.md` — all agents
- `astraea.md` — Astraea only
- `callum.md` — Callum only
- `codex_animus.md` — Codex Animus only
- `manifest.json` — auto-generated index (see above)
