"""Open WebUI - Daily Backup Manager.

Backs up Open WebUI data on a daily schedule.
- Every 5th backup becomes a "master" backup.
- When a master is created, all non-master backups are deleted.
- Keep only the newest 10 master backups.

Backup destination (configurable):
    C:\\Users\\user\\OneDrive\\Master Backup\\OpenWebUI-Backups

Folder naming
    webui-data-20260217-181530            # regular (auto-pruned)
    webui-data-20260217-181530-master     # master (kept up to 10)

State is tracked in a small ``backup_manifest.json`` inside the backup root.
"""

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

# -- Paths --------------------------------------------------------------
SOURCE_ROOT = Path(
    r"C:\Users\user\AppData\Local\Programs\Python\Python311\Lib\site-packages\open_webui\data"
)
_SCRIPT_DIR = Path(__file__).resolve().parent
BACKUP_ROOT = _SCRIPT_DIR.parent / "backups" / "openwebui"

MANIFEST_FILE = BACKUP_ROOT / "backup_manifest.json"
MASTER_INTERVAL = 5        # every N backups -> master backup
KEEP_MASTER = 10           # keep newest N master backups
KEEP_REGULAR = 4           # keep newest N regular backups (until a master)


# -- Helpers ------------------------------------------------------------

def _load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"backup_count": 0, "backups": []}


def _save_manifest(manifest: dict) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _copy_tree(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    for item in src.rglob("*"):
        if "__pycache__" in item.parts or item.suffix == ".pyc":
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _prune_regular(manifest: dict, *, remove_all: bool = False) -> None:
    regulars = [b for b in manifest["backups"] if b.get("type") == "regular"]
    regulars.sort(key=lambda b: b["sequence"])
    if remove_all:
        to_delete = list(regulars)
    else:
        to_delete = regulars[:-KEEP_REGULAR] if len(regulars) > KEEP_REGULAR else []
    for entry in to_delete:
        folder = BACKUP_ROOT / entry["folder"]
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            print(f"  [x] Pruned regular backup: {entry['folder']}")
        manifest["backups"].remove(entry)


def _prune_master(manifest: dict) -> None:
    masters = [b for b in manifest["backups"] if b.get("type") == "master"]
    masters.sort(key=lambda b: b["sequence"])
    to_delete = masters[:-KEEP_MASTER] if len(masters) > KEEP_MASTER else []
    for entry in to_delete:
        folder = BACKUP_ROOT / entry["folder"]
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            print(f"  [x] Pruned master backup: {entry['folder']}")
        manifest["backups"].remove(entry)


# -- Main ---------------------------------------------------------------

def run_backup(*, silent: bool = False) -> dict:
    manifest = _load_manifest()
    sequence = manifest["backup_count"] + 1
    manifest["backup_count"] = sequence

    is_master = (sequence % MASTER_INTERVAL == 0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder_name = f"webui-data-{stamp}" + ("-master" if is_master else "")
    dest = BACKUP_ROOT / folder_name

    if not silent:
        kind = "MASTER" if is_master else "regular"
        print(f"\n  [Backup] Open WebUI Backup - {stamp} ({kind})")

    t0 = time.time()
    dest.mkdir(parents=True, exist_ok=True)

    if SOURCE_ROOT.exists():
        _copy_tree(SOURCE_ROOT, dest)
    else:
        raise FileNotFoundError(f"Open WebUI data not found: {SOURCE_ROOT}")

    elapsed = time.time() - t0

    entry = {
        "sequence": sequence,
        "folder": folder_name,
        "type": "master" if is_master else "regular",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 2),
    }
    manifest["backups"].append(entry)

    _prune_regular(manifest, remove_all=is_master)
    _prune_master(manifest)
    _save_manifest(manifest)

    if not silent:
        print(f"  [OK] Backed up to {folder_name}  ({elapsed:.1f}s)")
        total_master = sum(1 for b in manifest["backups"] if b.get("type") == "master")
        total_reg = sum(1 for b in manifest["backups"] if b.get("type") == "regular")
        next_master = MASTER_INTERVAL - (sequence % MASTER_INTERVAL)
        print(f"  [i] {total_reg} regular + {total_master} master backups on disk")
        print(f"  [>] Next master backup in {next_master} backup(s)\n")

    return entry


if __name__ == "__main__":
    run_backup()
