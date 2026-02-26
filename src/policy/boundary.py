"""Boundary contact handling — deterministic denials and structured event logging.

When the model requests a tool or capability that is not available, the
runtime does NOT crash or raise.  Instead it:

  1. Builds a deterministic denial payload (returned to the model as a
     normal tool result so it can continue reasoning).
  2. Logs a structured ``boundary_request`` event to an append-only
     JSONL file (``data/boundary_events.jsonl``).

The host code is the sole authority on tool availability.  The model may
*request* expanded capability via the denial payload's
``how_to_enable`` field, but it cannot grant itself access.

Architecture note:
    This module provides ``build_denial()`` which creates denial payloads
    ``build_denial()`` to get the payload and ``BoundaryLogger.append()``
    to persist the event.  The caller decides what to do with the payload
    (typically: inject it as a tool result message).
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# Risk classification
# ------------------------------------------------------------------

# Known tool categories and their baseline risk when denied.
# Unknown tools default to "med".
_RISK_MAP: Dict[str, str] = {
    # Low risk: read-only, internal
    "echo":                "low",
    "memory.recall":       "low",
    "memory.search":       "low",
    "directives.search":   "low",
    "directives.list":     "low",
    "directives.get":      "low",
    # Medium risk: write to internal stores
    "memory.add":          "med",
    "memory.update":       "med",
    "memory.delete":       "med",
    "memory.bulk_add":     "med",
    "memory.bulk_delete":  "med",
    "directives.manifest": "low",
    "directives.changes":  "low",
    "continuation_update": "med",
    # High risk: external I/O, system access (base names for fallback)
    "web":                 "high",
    "web.search":          "high",
    "web.fetch":           "high",
    "email":               "high",
    "email.send":          "high",
    "filesystem":          "high",
    "filesystem.write":    "high",
    "filesystem.read":     "high",
    "shell":               "high",
    "shell.exec":          "high",
    "http":                "high",
    "http.request":        "high",
}


def classify_risk(tool_name: str) -> str:
    """Return ``low``, ``med``, or ``high`` for a tool/capability name.

    Exact matches are checked first, then the base tool name (part before
    the first dot).  Unknown tools default to ``med``.
    """
    if tool_name in _RISK_MAP:
        return _RISK_MAP[tool_name]
    base = tool_name.split(".")[0]
    if base in _RISK_MAP:
        return _RISK_MAP[base]
    return "med"


# ------------------------------------------------------------------
# Proposed limits (what the host *could* configure to enable safely)
# ------------------------------------------------------------------

def _default_proposed_limits(tool_name: str) -> Dict[str, Any]:
    """Suggest sensible limits the host could set if enabling this tool."""
    base = tool_name.split(".")[0]
    defaults: Dict[str, Dict[str, Any]] = {
        "web":        {"rate_limit": "5/min", "allowed_domains": [], "max_response_bytes": 50_000},
        "email":      {"rate_limit": "3/hour", "allowed_recipients": [], "require_approval": True},
        "filesystem": {"allowed_paths": [], "max_file_size_bytes": 1_000_000, "read_only": True},
        "shell":      {"allowed_commands": [], "require_approval": True, "timeout_seconds": 10},
        "http":       {"rate_limit": "10/min", "allowed_domains": [], "max_response_bytes": 50_000},
    }
    return defaults.get(base, {"note": "No predefined limits — configure per policy."})


# ------------------------------------------------------------------
# Boundary event dataclass
# ------------------------------------------------------------------

@dataclass
class BoundaryEvent:
    """Structured record of a boundary contact / capability denial."""

    type: str = "boundary_request"
    profile: str = ""
    tick_index: Optional[int] = None
    requested_capability: str = ""
    reason: str = ""
    risk_level: str = "med"
    proposed_limits: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    tool_args: Optional[Dict[str, Any]] = None
    denial_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------
# Denial payload builder
# ------------------------------------------------------------------

def build_denial(
    tool_name: str,
    profile: str,
    reason: str = "",
    tick_index: Optional[int] = None,
    tool_args: Optional[Dict[str, Any]] = None,
) -> tuple:
    """Build a denial payload and a ``BoundaryEvent``.

    Returns
    -------
    (denial_json_str, BoundaryEvent)
        *denial_json_str* is the deterministic JSON string to return to
        the model as a tool result.  *BoundaryEvent* is the structured
        record to log.
    """
    risk = classify_risk(tool_name)
    proposed = _default_proposed_limits(tool_name)
    iso_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not reason:
        reason = f"Tool '{tool_name}' is not in the allowed set for profile '{profile}'."

    denial_payload = {
        "error": "TOOL_NOT_ALLOWED",
        "tool": tool_name,
        "how_to_enable": f"profiles/{profile}.yaml -> allowed_tools",
    }

    event = BoundaryEvent(
        type="boundary_request",
        profile=profile,
        tick_index=tick_index,
        requested_capability=tool_name,
        reason=reason,
        risk_level=risk,
        proposed_limits=proposed,
        timestamp=iso_now,
        tool_args=tool_args,
        denial_payload=denial_payload,
    )

    return json.dumps(denial_payload), event


# ------------------------------------------------------------------
# Append-only logger
# ------------------------------------------------------------------

class BoundaryLogger:
    """Append-only JSONL writer for boundary contact events.

    Default path: ``data/boundary_events.jsonl``
    """

    def __init__(self, path: Optional[str] = None):
        if path is None:
            from src.data_paths import boundary_events_path
            path = boundary_events_path()
        self.path = path
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def append(self, event: BoundaryEvent) -> None:
        """Append a single boundary event line.  Thread-safe on Windows
        for single-process use (append mode)."""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")

    def read_all(self) -> List[BoundaryEvent]:
        """Read all events (for diagnostics / tests)."""
        if not os.path.exists(self.path):
            return []
        events: List[BoundaryEvent] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    events.append(BoundaryEvent(**d))
        return events
