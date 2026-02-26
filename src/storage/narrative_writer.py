"""Append-only human-readable narrative journal.

Produces a scientist's-log style diary at ``data/{profile}_narrative.md``.
Groups entries by session (burst or interactive) with timestamps and
narrative-only text.  No raw data fields.
"""

import os
import re


class NarrativeWriter:
    """Append-only markdown narrative journal."""

    def __init__(self, path: str, agent_name: str):
        self.path = path
        self.agent_name = agent_name
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self._ensure_header()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def begin_burst_session(self, iso_time: str, stimulus: str = "") -> None:
        """Write the burst session header and optional stimulus quote."""
        date = iso_time[:10]
        hhmm = iso_time[11:16]
        lines = [
            "",
            "---",
            "",
            f"## Burst Session | {date} {hhmm} UTC",
            "",
        ]
        if stimulus:
            lines.append(f'> Stimulus: "{stimulus}"')
            lines.append("")
        self._append(lines)

    def add_tick(self, tick_index: int, iso_time: str, narrative: str) -> None:
        """Append one tick entry with human-readable narrative."""
        hhmm = iso_time[11:16]
        text = self._humanise(narrative, tick_index)
        lines = [
            f"### Tick {tick_index} | {hhmm} UTC",
            "",
            text,
            "",
        ]
        self._append(lines)

    def end_burst_session(self, ticks_completed: int, memories_written: int) -> None:
        """Append the session complete footer."""
        lines = [
            "### Session Complete",
            f"Completed {ticks_completed} ticks. {memories_written} memories written.",
            "",
        ]
        self._append(lines)

    def add_interactive_session(self, iso_time: str, narrative: str) -> None:
        """Append a complete interactive session block."""
        date = iso_time[:10]
        hhmm = iso_time[11:16]
        lines = [
            "",
            "---",
            "",
            f"## Interactive Session | {date} {hhmm} UTC",
            "",
            narrative,
            "",
        ]
        self._append(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_header(self) -> None:
        """Write the file heading if the file does not yet exist or is empty."""
        if os.path.exists(self.path) and os.path.getsize(self.path) > 0:
            return
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(f"# {self.agent_name} - Narrative Log\n")

    def _append(self, lines: list) -> None:
        """Append lines to the narrative file."""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _humanise(self, narrative: str, tick_index: int) -> str:
        """Replace auto-generated data summaries with human-readable text."""
        if not narrative:
            return "No narrative recorded for this tick."

        # Auto-generated: "Tick N completed: X steps, tool=..., memories=..."
        if re.match(rf"^Tick {tick_index} completed:", narrative):
            return "Tick ran to completion without an explicit narrative from the agent."

        # Exception: "Tick N failed with unhandled exception: ..."
        if re.match(rf"^Tick {tick_index} failed with", narrative):
            return "Tick encountered an error and could not complete."

        # Model-generated narrative — pass through as-is
        return narrative
