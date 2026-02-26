"""creator_inbox tool — agent-to-operator direct messages.

Backed by a single JSONL file: data/shared/creator_inbox.jsonl
Each line: {"id", "from", "type", "priority", "subject", "body",
            "needs_approval", "status", "created_at"}

A derived markdown view is appended to data/creator_inbox.md on each send
for easy operator reading.  The JSONL is the canonical truth store.
"""

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.data_paths import creator_inbox_path, shared_dir, DATA_ROOT

_JSONL_PATH = creator_inbox_path()
_MD_PATH = os.path.join(DATA_ROOT, "creator_inbox.md")

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")

_VALID_TYPES = {"message", "tool_request", "warning", "idea"}
_VALID_PRIORITIES = {"low", "normal", "high", "urgent"}

_MAX_SUBJECT = 120
_MAX_BODY = 2000


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


def _append_one(entry: Dict[str, Any]) -> None:
    """Append a single JSONL line."""
    _ensure_dir()
    with open(_JSONL_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _append_md(entry: Dict[str, Any]) -> None:
    """Append a human-readable markdown entry to the derived view."""
    os.makedirs(os.path.dirname(_MD_PATH) or ".", exist_ok=True)

    # Ensure header exists
    if not os.path.exists(_MD_PATH) or os.path.getsize(_MD_PATH) == 0:
        with open(_MD_PATH, "w", encoding="utf-8") as f:
            f.write("# Creator Inbox\n")

    priority_tag = ""
    if entry.get("priority") in ("high", "urgent"):
        priority_tag = f" [{entry['priority'].upper()}]"

    approval_tag = ""
    if entry.get("needs_approval"):
        approval_tag = " [NEEDS APPROVAL]"

    lines = [
        "",
        "---",
        "",
        f"## {entry['created_at'][:16].replace('T', ' ')} UTC | {entry['from']} | {entry['type']}{priority_tag}{approval_tag}",
        "",
        f"**Subject:** {entry['subject']}",
        "",
        entry["body"],
        "",
        f"*id: {entry['id']}*",
        "",
    ]

    with open(_MD_PATH, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


class CreatorInboxTool:
    """Lets agents send direct messages to the operator (Creator)."""

    @staticmethod
    def definition() -> dict:
        return {
            "name": "creator_inbox",
            "description": (
                "Send a message directly to the operator (Creator). "
                "Use for direct messages, permission requests, warnings, or ideas. "
                "Action 'send' is the only supported action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["send"],
                        "description": "Must be 'send'.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["message", "tool_request", "warning", "idea"],
                        "description": (
                            "Message type: 'message' for general comms, "
                            "'tool_request' for permission/tool expansion requests, "
                            "'warning' for boundary or safety concerns, "
                            "'idea' for proposals or suggestions."
                        ),
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": (
                            "Priority level. Default 'normal'. "
                            "Use 'urgent' only for safety or boundary issues."
                        ),
                    },
                    "subject": {
                        "type": "string",
                        "description": "Short one-line summary (max 120 chars).",
                    },
                    "body": {
                        "type": "string",
                        "description": "Full message text (max 2000 chars).",
                    },
                    "needs_approval": {
                        "type": "boolean",
                        "description": (
                            "Set true if this requires operator approval "
                            "before proceeding. Default false."
                        ),
                    },
                },
                "required": ["action", "type", "subject", "body"],
            },
        }

    @staticmethod
    def execute(arguments: dict) -> str:
        action = arguments.get("action", "")

        if action != "send":
            return f"Error: unknown action '{action}'. Only 'send' is supported."

        return _action_send(arguments)


# ---- action implementation ------------------------------------------------

def _action_send(arguments: dict) -> str:
    msg_type = arguments.get("type", "")
    if msg_type not in _VALID_TYPES:
        return (
            f"Error: invalid type '{msg_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_TYPES))}."
        )

    priority = arguments.get("priority", "normal")
    if priority not in _VALID_PRIORITIES:
        return (
            f"Error: invalid priority '{priority}'. "
            f"Must be one of: {', '.join(sorted(_VALID_PRIORITIES))}."
        )

    subject = (arguments.get("subject") or "").strip()
    if not subject:
        return "Error: 'subject' is required and cannot be empty."
    if len(subject) > _MAX_SUBJECT:
        return f"Error: 'subject' exceeds {_MAX_SUBJECT} characters ({len(subject)})."

    body = (arguments.get("body") or "").strip()
    if not body:
        return "Error: 'body' is required and cannot be empty."
    if len(body) > _MAX_BODY:
        return f"Error: 'body' exceeds {_MAX_BODY} characters ({len(body)})."

    needs_approval = bool(arguments.get("needs_approval", False))

    # The "from" field is set by the caller (profile name injected at dispatch)
    sender = arguments.get("_from", "unknown")

    entry = {
        "id": uuid.uuid4().hex[:12],
        "from": sender,
        "type": msg_type,
        "priority": priority,
        "subject": subject,
        "body": body,
        "needs_approval": needs_approval,
        "status": "unread",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    _append_one(entry)
    _append_md(entry)

    return f"Message sent (id={entry['id']}): {subject}"
