# scripts/

Utility scripts for data seeding and maintenance. Run from the project root.

## Files

| File | Purpose |
|------|---------|
| `seed_memories.py` | Seeds the memory vault with test/example memories |

## seed_memories.py

Populates `data/memory/vault.jsonl` with sample memories for testing and bootstrapping.

### What's Seeded

Example data includes:
- Computer hardware specs (workstation, laptop, NAS, networking)
- Project state and priorities
- Bio facts and user preferences
- Example canon and register tier memories

### Usage

```bash
python scripts/seed_memories.py
```

Uses `VaultStore` from `src/memory/vault.py` to write properly formatted entries with full validation (PII guard, duplicate detection, write-gate).
