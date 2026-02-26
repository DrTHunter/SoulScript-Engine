"""Canonical data directory layout.

Every module that reads or writes to ``data/`` imports paths from here.
No other module should compute data paths independently.

Layout
------
data/
  journal.md                  # Human-readable diary (date, source, summary)
  tool_requests.md            # Human-readable tool request log (all agents)
  orion/                      # Orion-specific runtime data
    state.json
    journal.jsonl
    summary.md
    continuation.md
    narrative.md
  elysia/                     # Elysia-specific runtime data
    state.json
    journal.jsonl
    summary.md
    continuation.md
    narrative.md
  memory/                     # Memory Vault (shared across agents)
    vault.jsonl
  shared/                     # Cross-agent / system-level data
    boundary_events.jsonl
    change_log.jsonl
"""

import os

# Root data directory — relative to project root
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DATA_ROOT = os.path.join(_PROJECT_ROOT, "data")


# ------------------------------------------------------------------
# Directory getters (auto-create on access)
# ------------------------------------------------------------------

def _ensure(path: str) -> str:
    """Create directory if needed, return the path."""
    os.makedirs(path, exist_ok=True)
    return path


def profile_dir(profile: str) -> str:
    """``data/<profile>/`` — per-agent runtime data."""
    return _ensure(os.path.join(DATA_ROOT, profile))


def memory_dir() -> str:
    """``data/memory/`` — shared memory vault."""
    return _ensure(os.path.join(DATA_ROOT, "memory"))


def faiss_dir() -> str:
    """``data/memory/faiss/`` — FAISS vector index storage."""
    return _ensure(os.path.join(DATA_ROOT, "memory", "faiss"))


def shared_dir() -> str:
    """``data/shared/`` — cross-agent system data."""
    return _ensure(os.path.join(DATA_ROOT, "shared"))


# ------------------------------------------------------------------
# File path getters (per-profile)
# ------------------------------------------------------------------

def state_path(profile: str) -> str:
    """``data/<profile>/state.json``"""
    return os.path.join(profile_dir(profile), "state.json")


def journal_path(profile: str) -> str:
    """``data/<profile>/journal.jsonl``"""
    return os.path.join(profile_dir(profile), "journal.jsonl")


def summary_path(profile: str) -> str:
    """``data/<profile>/summary.md``"""
    return os.path.join(profile_dir(profile), "summary.md")


def continuation_path(profile: str) -> str:
    """``data/<profile>/continuation.md``"""
    return os.path.join(profile_dir(profile), "continuation.md")


def narrative_path(profile: str) -> str:
    """``data/<profile>/narrative.md`` — human-readable narrative log."""
    return os.path.join(profile_dir(profile), "narrative.md")


# ------------------------------------------------------------------
# File path getters (shared / global)
# ------------------------------------------------------------------

def vault_path() -> str:
    """``data/memory/vault.jsonl``"""
    memory_dir()  # ensure exists
    return os.path.join(DATA_ROOT, "memory", "vault.jsonl")


def boundary_events_path() -> str:
    """``data/shared/boundary_events.jsonl``"""
    shared_dir()  # ensure exists
    return os.path.join(DATA_ROOT, "shared", "boundary_events.jsonl")


def change_log_path() -> str:
    """``data/shared/change_log.jsonl`` — governance change audit log."""
    shared_dir()  # ensure exists
    return os.path.join(DATA_ROOT, "shared", "change_log.jsonl")


def human_journal_path() -> str:
    """``data/journal.md`` — the human-readable diary."""
    _ensure(DATA_ROOT)
    return os.path.join(DATA_ROOT, "journal.md")


def tool_requests_path() -> str:
    """``data/tool_requests.md`` — human-readable tool request log."""
    _ensure(DATA_ROOT)
    return os.path.join(DATA_ROOT, "tool_requests.md")
