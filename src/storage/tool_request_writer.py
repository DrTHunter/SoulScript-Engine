"""Append-only human-readable tool request log.

Produces a chronological markdown log at ``data/tool_requests.md`` with
one entry per tool request.  Each entry records: agent, timestamp,
tool name, tool description, arguments, and the agent's reasoning.
"""

import os
import time


class ToolRequestWriter:
    """Append-only markdown log of tool requests."""

    _MAX_CONTEXT = 300

    def __init__(self, path: str):
        self.path = path
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self._ensure_header()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_request(
        self,
        agent: str,
        tool_name: str,
        description: str,
        arguments: dict,
        context: str = "",
    ) -> None:
        """Append one tool request entry to the log.

        Parameters
        ----------
        agent:
            Profile name of the requesting agent (e.g. "orion").
        tool_name:
            Tool or qualified action name (e.g. "memory", "memory.add").
        description:
            Human-readable tool description from the tool definition.
        arguments:
            The raw arguments dict sent with the tool call.
        context:
            The agent's reasoning / message text that accompanied the
            request.  Truncated to ``_MAX_CONTEXT`` characters.
        """
        now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

        lines = [
            "",
            "---",
            "",
            f"## {now} | {agent} | {tool_name}",
            "",
            f"**Description:** {description}",
            "",
        ]

        # Format arguments line — pull out "action" if present
        args_copy = dict(arguments) if arguments else {}
        action = args_copy.pop("action", None)
        args_str = self._format_args(args_copy)

        if action and args_str:
            lines.append(f"**Action:** {action} | **Args:** {args_str}")
        elif action:
            lines.append(f"**Action:** {action}")
        elif args_str:
            lines.append(f"**Args:** {args_str}")

        lines.append("")

        # Context / reasoning
        ctx = (context or "").strip()
        if not ctx:
            ctx = "No context provided."
        elif len(ctx) > self._MAX_CONTEXT:
            ctx = ctx[:self._MAX_CONTEXT] + "..."
        lines.append(f"**Context:** {ctx}")
        lines.append("")

        self._append(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_header(self) -> None:
        """Write the file heading if the file does not yet exist or is empty."""
        if os.path.exists(self.path) and os.path.getsize(self.path) > 0:
            return
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# Tool Request Log\n")

    def _append(self, lines: list) -> None:
        """Append lines to the log file."""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    @staticmethod
    def _format_args(args: dict) -> str:
        """Format an arguments dict as key=value pairs."""
        if not args:
            return ""
        parts = []
        for k, v in args.items():
            if isinstance(v, str) and len(v) > 80:
                v = v[:80] + "..."
            parts.append(f"{k}={v}")
        return ", ".join(parts)
