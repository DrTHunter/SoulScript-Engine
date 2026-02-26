"""runtime_info — read-only snapshot of the current runtime state.

Returns a structured JSON object with agent identity, model/provider info,
runtime policy, allowed tools, memory and directive configuration.
Available even during stasis mode.  No side effects.

Supports on-demand refresh: every call builds a live snapshot and
computes a diff against the previous snapshot so the agent can see
exactly what changed since the last check.
"""

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.runtime_policy import RuntimePolicy
from src.governance.active_directives import ActiveDirectives
from src.memory.faiss_memory import FAISSMemory
from src.data_paths import vault_path as _get_vault_path, faiss_dir as _get_faiss_dir


def _diff_snapshots(
    prev: Dict[str, Any],
    curr: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Return a list of ``{field, old, new}`` dicts for top-level changes.

    Nested dicts (policy, memory, directives) are compared as JSON
    strings so any internal change is surfaced.
    """
    changes: List[Dict[str, str]] = []
    all_keys = sorted(set(list(prev.keys()) + list(curr.keys())))
    for key in all_keys:
        old_val = prev.get(key)
        new_val = curr.get(key)
        if old_val != new_val:
            changes.append({
                "field": key,
                "old": json.dumps(old_val, default=str) if old_val is not None else "(absent)",
                "new": json.dumps(new_val, default=str) if new_val is not None else "(absent)",
            })
    return changes


class RuntimeInfoTool:
    """Returns an on-demand JSON snapshot of runtime configuration."""

    _profile: dict = {}
    _policy: Optional[RuntimePolicy] = None
    _execution_mode: str = "interactive"
    _burst_config: Optional[dict] = None
    _last_snapshot: Optional[Dict[str, Any]] = None

    # Required fields — every snapshot MUST contain these keys
    REQUIRED_FIELDS = (
        "agent", "provider", "model", "base_url_host", "temperature",
        "execution_mode", "policy", "allowed_tools", "memory",
        "directives", "active_directives", "window_size",
    )

    @classmethod
    def set_context(
        cls,
        profile: dict,
        policy: RuntimePolicy,
        execution_mode: str = "interactive",
        burst_config: Optional[dict] = None,
    ) -> None:
        """Inject runtime context.  Called at startup and may be called
        again mid-session to reflect live changes (e.g. policy updates,
        mode transitions)."""
        cls._profile = dict(profile)  # shallow copy
        cls._policy = policy
        cls._execution_mode = execution_mode
        cls._burst_config = burst_config

    @classmethod
    def reset(cls) -> None:
        """Clear all state (for tests)."""
        cls._profile = {}
        cls._policy = None
        cls._execution_mode = "interactive"
        cls._burst_config = None
        cls._last_snapshot = None
        ActiveDirectives.reset()

    @staticmethod
    def definition() -> dict:
        return {
            "name": "runtime_info",
            "description": (
                "Returns a read-only JSON snapshot of the current runtime "
                "configuration: agent identity, model, provider, policy, "
                "allowed tools, memory and directive settings.  Includes a "
                "'diff' array showing any fields that changed since the last "
                "snapshot.  Available even during stasis mode."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }

    @staticmethod
    def execute(arguments: dict) -> str:
        profile = RuntimeInfoTool._profile
        policy = RuntimeInfoTool._policy

        # Redact base_url to host-only
        raw_url = profile.get("base_url", "")
        try:
            host = urlparse(raw_url).hostname or raw_url
        except Exception:
            host = raw_url

        # Build policy snapshot
        policy_snap = {}
        if policy:
            policy_snap = {
                "max_iterations": policy.max_iterations,
                "max_wall_time_seconds": policy.max_wall_time_seconds,
                "stasis_mode": policy.stasis_mode,
                "tool_failure_mode": policy.tool_failure_mode,
                "self_refine_steps": policy.self_refine_steps,
            }

        snapshot: Dict[str, Any] = {
            "agent": profile.get("name", "unknown"),
            "provider": profile.get("provider", "unknown"),
            "model": profile.get("model", "unknown"),
            "base_url_host": host,
            "temperature": profile.get("temperature", 0.7),
            "execution_mode": RuntimeInfoTool._execution_mode,
            "policy": policy_snap,
            "allowed_tools": profile.get("allowed_tools", []),
            "memory": profile.get("memory", {}),
            "directives": profile.get("directives", {}),
            "active_directives": ActiveDirectives.summary(),
            "window_size": profile.get("window_size", 50),
        }

        # Memory health (FAISS + vault)
        try:
            mem = FAISSMemory(
                vault_path=_get_vault_path(),
                faiss_dir=_get_faiss_dir(),
            )
            stats = mem.stats()
            snapshot["memory"] = {
                "active_memories": stats["active_memories"],
                "faiss_vectors": stats["faiss_vectors"],
                "vault_total_lines": stats["vault_total_lines"],
                "by_scope": stats.get("by_scope", {}),
            }
        except Exception:
            snapshot["memory"] = {"error": "unavailable"}

        # Burst-mode context (if set)
        if RuntimeInfoTool._burst_config:
            snapshot["burst"] = RuntimeInfoTool._burst_config

        # Diff against previous snapshot
        prev = RuntimeInfoTool._last_snapshot
        if prev is not None:
            diff = _diff_snapshots(prev, snapshot)
        else:
            diff = []

        # Store current as last
        RuntimeInfoTool._last_snapshot = dict(snapshot)

        # Build response with snapshot + diff
        response: Dict[str, Any] = dict(snapshot)
        response["diff"] = diff
        response["diff_count"] = len(diff)

        return json.dumps(response, indent=2)
