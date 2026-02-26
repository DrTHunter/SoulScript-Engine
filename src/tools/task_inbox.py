"""task_inbox tool — add tasks and fetch the next pending one.

Backed by a single JSONL file: data/task_inbox.jsonl
Each line: {"id", "profile", "status", "created_at", "done_at", "task"}
"""

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.data_paths import task_inbox_path, shared_dir

_JSONL_PATH = task_inbox_path()

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


def _ensure_dir() -> None:
    shared_dir()  # auto-creates


def _read_all() -> List[Dict[str, Any]]:
    """Read every line from the JSONL file."""
    if not os.path.exists(_JSONL_PATH):
        return []
    entries: List[Dict[str, Any]] = []
    with open(_JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _write_all(entries: List[Dict[str, Any]]) -> None:
    """Atomic rewrite of the entire JSONL file."""
    _ensure_dir()
    fd, tmp = tempfile.mkstemp(dir=shared_dir(), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.replace(tmp, _JSONL_PATH)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _append_one(entry: Dict[str, Any]) -> None:
    """Append a single line (fast path for add)."""
    _ensure_dir()
    with open(_JSONL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class TaskInboxTool:
    """Lets the agent add tasks and fetch the next pending one."""

    @staticmethod
    def definition() -> dict:
        return {
            "name": "task_inbox",
            "description": (
                "Manage a simple task queue. "
                "Use action 'add' to create a pending task, "
                "'next' to fetch and mark done the oldest pending task, "
                "or 'ack' to acknowledge a task by ID. "
                "Set dry_run=true to preview without side effects."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "next", "ack"],
                        "description": "'add' to create a task, 'next' to pop the oldest pending task, 'ack' to acknowledge a task by ID.",
                    },
                    "task": {
                        "type": "string",
                        "description": "Task description (required for 'add').",
                    },
                    "profile": {
                        "type": "string",
                        "description": "Profile name to scope the task. Defaults to first available agent.",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Task ID (required for 'ack').",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, preview the action without writing. Default false.",
                    },
                },
                "required": ["action"],
            },
        }

    @staticmethod
    def execute(arguments: dict) -> str:
        action = arguments.get("action", "")
        profile = arguments.get("profile", "")
        if not profile:
            # Discover first available agent from profiles/
            from pathlib import Path as _Path
            _profiles_dir = _Path(__file__).resolve().parent.parent.parent / "profiles"
            if _profiles_dir.exists():
                yamls = sorted(p.stem for p in _profiles_dir.glob("*.yaml"))
                profile = yamls[0] if yamls else "agent"
            else:
                profile = "agent"
        dry_run = arguments.get("dry_run", False)

        # Sanitise profile name
        if not _SAFE_NAME.match(profile):
            return f"Error: invalid profile name '{profile}'"

        if action == "add":
            return _action_add(arguments.get("task", ""), profile, dry_run=dry_run)
        if action == "next":
            return _action_next(
                profile if arguments.get("profile") else None,
                dry_run=dry_run,
            )
        if action == "ack":
            return _action_ack(arguments.get("task_id", ""), dry_run=dry_run)
        return f"Error: unknown action '{action}'. Use 'add', 'next', or 'ack'."


# ---- action implementations ------------------------------------------------

def _action_add(task: str, profile: str, *, dry_run: bool = False) -> str:
    if not task.strip():
        return "Error: 'task' is required for action 'add'."
    entry = {
        "id": uuid.uuid4().hex[:12],
        "profile": profile,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "done_at": None,
        "task": task.strip(),
    }
    if dry_run:
        return f"[DRY_RUN] Would add task (id={entry['id']}): {task.strip()}"
    _append_one(entry)
    return f"Task added (id={entry['id']}): {task.strip()}"


def _action_next(profile: str | None, *, dry_run: bool = False) -> str:
    entries = _read_all()
    target_idx = None
    for i, e in enumerate(entries):
        if e.get("status") != "pending":
            continue
        if profile is not None and e.get("profile") != profile:
            continue
        target_idx = i
        break

    if target_idx is None:
        return "NO_TASK — no pending tasks found."

    t = entries[target_idx]
    if dry_run:
        return f"[DRY_RUN] Would fetch and mark done: id={t['id']} | {t['task']}"

    entries[target_idx]["status"] = "done"
    entries[target_idx]["done_at"] = datetime.now(timezone.utc).isoformat()
    _write_all(entries)

    return f"TASK_FOUND id={t['id']} | {t['task']}"


def _action_ack(task_id: str, *, dry_run: bool = False) -> str:
    """Acknowledge a task by ID — marks it 'acknowledged'."""
    if not task_id.strip():
        return "Error: 'task_id' is required for action 'ack'."
    entries = _read_all()
    target_idx = None
    for i, e in enumerate(entries):
        if e.get("id") == task_id.strip():
            target_idx = i
            break

    if target_idx is None:
        return f"Error: task '{task_id}' not found."

    entry = entries[target_idx]
    if entry.get("status") == "acknowledged":
        return f"Task '{task_id}' is already acknowledged."

    if dry_run:
        return f"[DRY_RUN] Would acknowledge task id={task_id} | {entry['task']}"

    entries[target_idx]["status"] = "acknowledged"
    entries[target_idx]["acked_at"] = datetime.now(timezone.utc).isoformat()
    _write_all(entries)
    return f"Task acknowledged (id={task_id}): {entry['task']}"
