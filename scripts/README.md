# scripts/

Utility scripts for backup and maintenance. Run from the project root.

## Files

| File | Purpose |
|------|---------|
| `backup.py` | Daily backup manager — automatic versioned backups with retention policy |
| `openwebui_backup.py` | Open WebUI daily backup manager — versioned data backups with retention policy |
| `vault_maintenance.py` | CLI for memory vault inspection, compaction, and pruning |

## backup.py

Backs up runtime data on a daily schedule.

- **Regular backups** are auto-pruned (kept until a master is created)
- **Every 5th backup** becomes a "master" backup
- **Master backups** are kept, but only the newest 10 remain
- Tracks backup count in `backup_manifest.json` inside the backup root

### What's Backed Up

Copies these directories to the backup destination:

```
data/, config/, directives/, profiles/, prompts/, notes/, src/, web/, scripts/
```

### Folder Naming

```
backup-20260217-181530            # regular (auto-pruned)
backup-20260217-181530-master     # master (kept up to 10)
```

### Configuration

The backup destination is configured at the top of the script. Adjust `BACKUP_ROOT` for your environment.

| Constant | Default | Description |
|----------|---------|-------------|
| `MASTER_INTERVAL` | 5 | Every N backups → master backup |
| `KEEP_MASTER` | 10 | How many master backups to retain |
| `KEEP_REGULAR` | 4 | How many regular backups to retain |

### Usage

```bash
python scripts/backup.py
```

Run on a daily schedule via Task Scheduler (recommended).

---

## openwebui_backup.py

Backs up Open WebUI data on a daily schedule.

- **Regular backups** are auto-pruned (kept until a master is created)
- **Every 5th backup** becomes a "master" backup
- **Master backups** are kept, but only the newest 10 remain

### Backup Destination

```
C:\Users\user\OneDrive\Master Backup\OpenWebUI-Backups
```

### Usage

```bash
python scripts/openwebui_backup.py
```

---

## vault_maintenance.py

CLI for inspecting and maintaining the memory vault (`data/memory/vault.jsonl`).

### Commands

| Command | Description |
|---------|-------------|
| `status` | Dashboard with utilization bar, bloat ratio, and recommendations |
| `compact` | Remove old versions and tombstones (reduces file size) |
| `list` | List all active memories, optionally filtered by scope |
| `prune` | Interactive review & delete with dry-run support |

### Usage

```bash
# Show status dashboard
python scripts/vault_maintenance.py

# Compact the vault (remove old versions / tombstones)
python scripts/vault_maintenance.py compact

# List all active memories
python scripts/vault_maintenance.py list

# List memories for a specific scope
python scripts/vault_maintenance.py list --scope orion

# Interactive prune (review and delete)
python scripts/vault_maintenance.py prune

# Dry-run prune (preview only, no changes)
python scripts/vault_maintenance.py prune --scope shared --dry-run
```
