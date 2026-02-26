"""Tool registry: definitions, allowlist enforcement, and dispatch.

To add a new tool:
  1. Create a module in src/tools/ with a class exposing definition() -> dict
     and execute(arguments: dict) -> str.
  2. Import and register it in _ALL_TOOLS below.

Boundary handling:
  When ``dispatch()`` encounters an unknown or disallowed tool it returns
  a deterministic denial payload (JSON string) instead of raising.  This
  lets the model continue reasoning with the denial.  A structured event
  is logged to ``data/boundary_events.jsonl`` via ``BoundaryLogger``.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from src.tools.echo import EchoTool
from src.tools.task_inbox import TaskInboxTool
from src.tools.continuation_update import ContinuationUpdateTool
from src.tools.memory_tool import MemoryTool
from src.tools.directives_tool import DirectivesTool
from src.tools.runtime_info_tool import RuntimeInfoTool
from src.tools.creator_inbox import CreatorInboxTool
from src.tools.web_search import WebSearchTool
from src.tools.email_tool import EmailTool
from src.tools.computer_use import ComputerUseTool
from src.policy.boundary import BoundaryLogger, BoundaryEvent, build_denial

# Master catalogue — every tool the runtime knows about.
_ALL_TOOLS: Dict[str, Any] = {
    "echo": EchoTool(),
    "task_inbox": TaskInboxTool(),
    "continuation_update": ContinuationUpdateTool(),
    "memory": MemoryTool(),
    "directives": DirectivesTool(),
    "runtime_info": RuntimeInfoTool(),
    "creator_inbox": CreatorInboxTool(),
    "web_search": WebSearchTool(),
    "email": EmailTool(),
    "computer_use": ComputerUseTool(),
}


class ToolRegistry:
    """Provides definitions and dispatch restricted to an allowlist.

    On denial, ``dispatch()`` returns the denial payload string and a
    ``BoundaryEvent``.  On success it returns the tool result and None.
    """

    def __init__(
        self,
        allowed: List[str],
        profile: str = "",
        boundary_logger: Optional[BoundaryLogger] = None,
    ):
        self._allowed: Set[str] = set(allowed)
        self._profile: str = profile
        self._boundary_logger: BoundaryLogger = boundary_logger or BoundaryLogger()

    def get_definitions(self) -> List[Dict[str, Any]]:
        """Return JSON-Schema tool definitions for allowlisted tools only."""
        return [
            _ALL_TOOLS[name].definition()
            for name in _ALL_TOOLS
            if name in self._allowed
        ]

    def dispatch(
        self,
        name: str,
        arguments: Dict[str, Any],
        tick_index: Optional[int] = None,
    ) -> Tuple[str, Optional[BoundaryEvent]]:
        """Execute a tool by name.

        Returns
        -------
        (result_str, boundary_event_or_None)
            On success: (tool result, None).
            On denial:  (denial JSON payload, BoundaryEvent).

        Never raises for allowlist / registration issues.  Execution
        errors from the tool itself still raise normally.
        """
        # --- Unknown tool (not registered at all) ---
        if name not in _ALL_TOOLS:
            reason = f"Tool '{name}' is not registered in the runtime."
            denial_json, event = build_denial(
                tool_name=name,
                profile=self._profile,
                reason=reason,
                tick_index=tick_index,
                tool_args=arguments,
            )
            self._boundary_logger.append(event)
            return denial_json, event

        # --- Known but not allowed for this profile ---
        if name not in self._allowed:
            reason = (
                f"Tool '{name}' exists but is not in the allowlist "
                f"for profile '{self._profile}'."
            )
            denial_json, event = build_denial(
                tool_name=name,
                profile=self._profile,
                reason=reason,
                tick_index=tick_index,
                tool_args=arguments,
            )
            self._boundary_logger.append(event)
            return denial_json, event

        # --- Allowed: execute ---
        tool = _ALL_TOOLS[name]
        # Pass agent name for tools that support account selection (e.g. email)
        if name == "email":
            result = tool.execute(arguments, agent_name=self._profile)
        else:
            result = tool.execute(arguments)
        return result, None

    def is_registered(self, name: str) -> bool:
        """Check if a tool name exists in the master catalogue."""
        return name in _ALL_TOOLS

    def is_allowed(self, name: str) -> bool:
        """Check if a tool is both registered and in the allowlist."""
        return name in _ALL_TOOLS and name in self._allowed

    def get_description(self, name: str) -> str:
        """Return the human-readable description for a tool, or a fallback."""
        if name in _ALL_TOOLS:
            return _ALL_TOOLS[name].definition().get("description", "No description.")
        return "Unknown tool."
