"""Orion Forge - Daily Backup Manager.

Creates ONE new timestamped backup folder per run.  Never touches existing
backup folders — only the NEW folder is written, then old folders are pruned.

Policy
------
- Every 5th backup is promoted to **master**.
- When a master is created all non-master backups are deleted.
- Keep only the newest 10 master backups.
- Incremental copies: only files whose mtime or size changed since the
  most recent prior backup are copied; unchanged files are hard-linked
  (or copied if hard-links aren't available, e.g. across OneDrive drives).

Folder naming
    backup-20260217-181530            # regular (auto-pruned)
    backup-20260217-181530-master     # master (kept up to 10)

State is tracked in ``backup_manifest.json`` inside the backup root.
"""

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = PROJECT_ROOT / "backups"

# Directories / files to include in every backup (relative to PROJECT_ROOT)
INCLUDE = [
    "data",
    "config",
    "directives",
    "profiles",
    "prompts",
    "notes",
    "src",
    "web",
    "scripts",
    "tests",
    "tools",
    "sandbox",
    "requirements.txt",
    "README.md",
    "Commands Bible.txt",
]

MANIFEST_FILE = BACKUP_ROOT / "backup_manifest.json"
MASTER_INTERVAL = 5        # every N backups -> master backup
KEEP_MASTER = 10           # keep newest N master backups
KEEP_REGULAR = 4           # keep newest N regular backups (before a master)


# ── Helpers ────────────────────────────────────────────────────────────

def _load_manifest() -> dict:
    """Load or initialise the manifest."""
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"backup_count": 0, "backups": []}


def _save_manifest(manifest: dict) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _latest_backup_folder(manifest: dict) -> Path | None:
    """Return the Path of the most recent backup folder, or None."""
    if not manifest["backups"]:
        return None
    latest = max(manifest["backups"], key=lambda b: b["sequence"])
    p = BACKUP_ROOT / latest["folder"]
    return p if p.is_dir() else None


def _file_changed(src: Path, ref: Path) -> bool:
    """Return True if *src* differs from *ref* (size or mtime)."""
    if not ref.exists():
        return True
    try:
        ss = src.stat()
        rs = ref.stat()
        return ss.st_size != rs.st_size or abs(ss.st_mtime - rs.st_mtime) > 1.0
    except OSError:
        return True


def _copy_tree(src: Path, dst: Path, ref_base: Path | None = None,
               ref_src_name: str | None = None) -> dict:
    """Copy a directory tree to *dst*.

    If *ref_base* is given (the previous backup folder) unchanged files are
    hard-linked instead of copied.  Returns ``{"copied": N, "linked": N}``.
    """
    stats = {"copied": 0, "linked": 0}

    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        ref = ref_base / ref_src_name if ref_base and ref_src_name else None
        if ref and not _file_changed(src, ref):
            try:
                os.link(ref, dst)
                stats["linked"] += 1
                return stats
            except OSError:
                pass  # fall through to copy
        shutil.copy2(src, dst)
        stats["copied"] += 1
        return stats

    for item in src.rglob("*"):
        if "__pycache__" in item.parts or item.suffix == ".pyc":
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)

        ref_file = (ref_base / ref_src_name / rel) if ref_base and ref_src_name else None
        if ref_file and not _file_changed(item, ref_file):
            try:
                os.link(ref_file, target)
                stats["linked"] += 1
                continue
            except OSError:
                pass
        shutil.copy2(item, target)
        stats["copied"] += 1

    return stats


def _remove_folder(folder: Path, label: str = "") -> None:
    """Remove a backup folder robustly and verify it's gone."""
    if not folder.exists():
        return
    shutil.rmtree(folder, ignore_errors=True)
    # Retry once if OneDrive or antivirus kept it alive
    if folder.exists():
        time.sleep(0.5)
        shutil.rmtree(folder, ignore_errors=True)
    # Final sweep: delete the empty shell directory itself
    if folder.exists():
        try:
            folder.rmdir()       # works if shutil left an empty dir
        except OSError:
            pass
    if label and not folder.exists():
        print(f"  [x] Pruned {label}: {folder.name}")


def _cleanup_orphans(manifest: dict) -> None:
    """Delete any backup-* folders on disk that aren't in the manifest."""
    if not BACKUP_ROOT.is_dir():
        return
    known = {b["folder"] for b in manifest["backups"]}
    for child in sorted(BACKUP_ROOT.iterdir()):
        if child.is_dir() and child.name.startswith("backup-") and child.name not in known:
            _remove_folder(child, "orphan")


def _prune_regular(manifest: dict, *, remove_all: bool = False) -> None:
    """Delete regular backups (keep newest KEEP_REGULAR unless remove_all)."""
    regulars = [b for b in manifest["backups"] if b.get("type") == "regular"]
    regulars.sort(key=lambda b: b["sequence"])
    if remove_all:
        to_delete = list(regulars)
    else:
        to_delete = regulars[:-KEEP_REGULAR] if len(regulars) > KEEP_REGULAR else []
    for entry in to_delete:
        _remove_folder(BACKUP_ROOT / entry["folder"], "regular backup")
        manifest["backups"].remove(entry)


def _prune_master(manifest: dict) -> None:
    """Keep only the newest KEEP_MASTER master backups."""
    masters = [b for b in manifest["backups"] if b.get("type") == "master"]
    masters.sort(key=lambda b: b["sequence"])
    to_delete = masters[:-KEEP_MASTER] if len(masters) > KEEP_MASTER else []
    for entry in to_delete:
        _remove_folder(BACKUP_ROOT / entry["folder"], "master backup")
        manifest["backups"].remove(entry)


# ── Main entry ─────────────────────────────────────────────────────────

def run_backup(*, silent: bool = False) -> dict:
    """Create ONE new backup folder.  Never modifies existing backups."""
    manifest = _load_manifest()

    # ── Cleanup orphan directories left from past prune failures ───
    _cleanup_orphans(manifest)

    sequence = manifest["backup_count"] + 1
    manifest["backup_count"] = sequence

    is_master = (sequence % MASTER_INTERVAL == 0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder_name = f"backup-{stamp}" + ("-master" if is_master else "")
    dest = BACKUP_ROOT / folder_name

    if not silent:
        kind = "MASTER" if is_master else "regular"
        print(f"\n  [Backup] Orion Forge Backup - {stamp} ({kind})")

    # ── Reference folder for incremental copy ──────────────────────
    ref_folder = _latest_backup_folder(manifest)

    t0 = time.time()
    dest.mkdir(parents=True, exist_ok=True)

    total_copied = 0
    total_linked = 0
    for name in INCLUDE:
        src = PROJECT_ROOT / name
        if src.exists():
            s = _copy_tree(src, dest / name, ref_base=ref_folder, ref_src_name=name)
            total_copied += s["copied"]
            total_linked += s["linked"]

    elapsed = time.time() - t0

    entry = {
        "sequence": sequence,
        "folder": folder_name,
        "type": "master" if is_master else "regular",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 2),
        "files_copied": total_copied,
        "files_linked": total_linked,
    }
    manifest["backups"].append(entry)

    # ── Prune old backups ──────────────────────────────────────────
    _prune_regular(manifest, remove_all=is_master)
    _prune_master(manifest)

    _save_manifest(manifest)

    if not silent:
        print(f"  [OK] Backed up to {folder_name}  ({elapsed:.1f}s)")
        print(f"       {total_copied} files copied, {total_linked} hard-linked (unchanged)")
        total_master = sum(1 for b in manifest["backups"] if b.get("type") == "master")
        total_reg = sum(1 for b in manifest["backups"] if b.get("type") == "regular")
        next_master = MASTER_INTERVAL - (sequence % MASTER_INTERVAL)
        print(f"  [i] {total_reg} regular + {total_master} master backups on disk")
        print(f"  [>] Next master backup in {next_master} backup(s)\n")

    return entry


if __name__ == "__main__":
    run_backup()
