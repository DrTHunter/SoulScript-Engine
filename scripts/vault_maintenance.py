#!/usr/bin/env python3
"""Vault Maintenance CLI — inspect, compact, and prune the memory vault.

Usage
-----
  python scripts/vault_maintenance.py              # show status dashboard
  python scripts/vault_maintenance.py compact       # remove old versions / tombstones
  python scripts/vault_maintenance.py list           # list all active memories
  python scripts/vault_maintenance.py list --scope orion  # filter by scope
  python scripts/vault_maintenance.py prune          # interactive review & delete
  python scripts/vault_maintenance.py prune --scope shared --dry-run
"""

import argparse
import json
import os
import sys
import textwrap

# Ensure project root is on the path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))
sys.path.insert(0, _PROJECT_ROOT)

from src.data_paths import vault_path, faiss_dir   # noqa: E402
from src.memory.faiss_memory import FAISSMemory     # noqa: E402


# ── Colours (ANSI, safe on Windows Terminal / PowerShell 7) ──────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def _bar(pct: float, width: int = 30) -> str:
    """ASCII progress bar."""
    filled = int(pct / 100 * width)
    colour = GREEN if pct < 60 else YELLOW if pct < 85 else RED
    return f"{colour}{'█' * filled}{'░' * (width - filled)}{RESET} {pct:.0f}%"


# ── Commands ─────────────────────────────────────────────────────────

def cmd_status(vault: FAISSMemory) -> None:
    """Print a dashboard of vault health."""
    stats = vault.stats()

    print(f"\n{BOLD}╔══════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║       Memory Vault — Status          ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════╝{RESET}\n")

    print(f"  Active memories : {BOLD}{stats['active_memories']}{RESET}")
    print(f"  FAISS vectors   : {stats['faiss_vectors']}")
    print(f"  Vault lines     : {stats['vault_total_lines']}")

    if stats.get("by_scope"):
        print(f"\n  {BOLD}By scope:{RESET}")
        for scope, count in sorted(stats["by_scope"].items()):
            print(f"    {scope:<12} {count}")
    print()


def cmd_compact(vault: FAISSMemory) -> None:
    """Compact the vault file (remove old versions / tombstones)."""
    result = vault.compact()
    print(f"\n  {BOLD}Compact complete{RESET}")
    print(f"  Lines before : {result.get('lines_before', '?')}")
    print(f"  Lines after  : {result.get('lines_after', '?')}")
    print(f"  Removed      : {GREEN}{result.get('lines_removed', '?')}{RESET}\n")


def cmd_list(vault: FAISSMemory, scope: str | None = None) -> None:
    """List all active memories, optionally filtered by scope."""
    memories = vault.list_all(scope=scope)
    if not memories:
        print(f"\n  No active memories{' for scope=' + scope if scope else ''}.\n")
        return

    print(f"\n  {BOLD}Active memories ({len(memories)}){RESET}",
          f"— scope={scope}" if scope else "")
    print(f"  {'─' * 70}")

    for m in memories:
        preview = textwrap.shorten(m.text, width=60, placeholder="…")
        cat_tag = f"{DIM}{m.category}{RESET}"
        scope_tag = f"{CYAN}{m.scope:<8}{RESET}"
        print(f"  {DIM}{m.id}{RESET}  {scope_tag}  {cat_tag:<20}  {preview}")

    print()


def cmd_prune(vault: FAISSMemory, scope: str | None = None,
              dry_run: bool = False) -> None:
    """Interactive review — walk through memories and optionally delete.

    In dry-run mode, prints what would happen without actually deleting.
    """
    memories = vault.list_all(scope=scope)
    if not memories:
        print(f"\n  No active memories to review.\n")
        return

    print(f"\n  {BOLD}Vault Prune — interactive review ({len(memories)} entries){RESET}")
    if dry_run:
        print(f"  {YELLOW}DRY RUN — nothing will be deleted{RESET}")
    print(f"  For each entry: [k]eep  [d]elete  [s]kip rest  [q]uit\n")

    to_delete: list[str] = []

    for i, m in enumerate(memories, 1):
        scope_tag = f"{CYAN}{m.scope}{RESET}"
        cat_tag = f"{DIM}{m.category}{RESET}"
        print(f"  {BOLD}[{i}/{len(memories)}]{RESET}  {scope_tag}  {cat_tag}  id={DIM}{m.id}{RESET}")
        # Wrap text nicely
        wrapped = textwrap.fill(m.text, width=72, initial_indent="    ",
                                subsequent_indent="    ")
        print(wrapped)
        if m.tags:
            print(f"    tags: {', '.join(m.tags)}")
        print(f"    created: {m.created_at[:10]}")

        while True:
            try:
                choice = input(f"  → [k]eep / [d]elete / [s]kip rest / [q]uit : ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"

            if choice in ("k", "keep", ""):
                print(f"    {GREEN}kept{RESET}\n")
                break
            elif choice in ("d", "delete"):
                to_delete.append(m.id)
                print(f"    {RED}marked for deletion{RESET}\n")
                break
            elif choice in ("s", "skip"):
                print(f"    skipping remaining…\n")
                break
            elif choice in ("q", "quit"):
                break
            else:
                print(f"    {DIM}(k/d/s/q){RESET}")

        if choice in ("s", "skip", "q", "quit"):
            break

    if not to_delete:
        print(f"  {GREEN}No deletions selected.{RESET}\n")
        return

    print(f"\n  {BOLD}Summary:{RESET} {len(to_delete)} memories marked for deletion:")
    for mid in to_delete:
        print(f"    {DIM}{mid}{RESET}")

    if dry_run:
        print(f"\n  {YELLOW}DRY RUN — no changes made.{RESET}\n")
        return

    try:
        confirm = input(f"\n  Confirm deletion? [y/N] : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = "n"

    if confirm in ("y", "yes"):
        deleted = 0
        for mid in to_delete:
            if vault.delete(mid):
                deleted += 1
        print(f"\n  {GREEN}Deleted {deleted} memories.{RESET}")
        # Auto-compact after prune
        result = vault.compact()
        print(f"  Compacted: {result['lines_removed']} stale lines removed.\n")
    else:
        print(f"\n  {YELLOW}Cancelled — nothing deleted.{RESET}\n")


# ── Main ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Memory Vault maintenance — inspect, compact, prune",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Commands:
              status   Show vault health dashboard (default)
              compact  Remove old versions & tombstones from JSONL
              list     List all active memories
              prune    Interactive walk-through to delete stale entries
        """),
    )
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "compact", "list", "prune"],
                        help="Action to perform (default: status)")
    parser.add_argument("--scope", default=None,
                        help="Filter by scope (orion, elysia, shared)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing (prune only)")

    args = parser.parse_args()

    path = vault_path()
    if not os.path.exists(path):
        print(f"\n  {RED}Vault file not found: {path}{RESET}\n")
        sys.exit(1)

    vault = FAISSMemory(vault_path=path, faiss_dir=faiss_dir())

    if args.command == "status":
        cmd_status(vault)
    elif args.command == "compact":
        cmd_compact(vault)
    elif args.command == "list":
        cmd_list(vault, scope=args.scope)
    elif args.command == "prune":
        cmd_prune(vault, scope=args.scope, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
