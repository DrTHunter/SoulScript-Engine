"""Data types for the Burst Runner subsystem.

All structured objects exchanged between burst, tick, and the LLM
are defined here.  Kept deliberately free of business logic.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

@dataclass(frozen=True)
class BurstConfig:
    """Immutable configuration for a single burst execution."""

    profile: str
    burst_ticks: int = 15
    max_steps_per_tick: int = 3
    max_tool_calls_per_tick: int = 2          # max tool calls allowed per tick
    allowed_tools: tuple = (                   # frozen so it's hashable
        "memory.recall",
        "memory.search",
        "memory.add",
        "memory.bulk_add",
        "memory.update",
        "memory.delete",
        "memory.bulk_delete",
        "directives.search",
        "directives.list",
        "directives.get",
        "directives.manifest",
        "directives.changes",
    )
    stimulus: str = ""                         # injected into first user msg

    def tool_name(self) -> str:
        """The top-level tool name used for dispatch (always 'memory' in v1)."""
        return "memory"

    def allowed_tool_names(self) -> tuple:
        """All top-level tool names that appear in allowed_tools."""
        return tuple(sorted({t.split(".")[0] for t in self.allowed_tools}))


# ------------------------------------------------------------------
# Step-level model output (the structured JSON the LLM must produce)
# ------------------------------------------------------------------

class StepAction(str, Enum):
    THINK = "think"
    TOOL  = "tool"
    STOP  = "stop"


@dataclass
class ProposedMemory:
    """A memory the model wants to persist at end-of-tick."""

    text: str
    scope: str
    category: str
    tags: List[str] = field(default_factory=list)
    source: str = "tool"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "scope": self.scope,
            "category": self.category,
            "tags": self.tags,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProposedMemory":
        return cls(
            text=d.get("text", ""),
            scope=d.get("scope", ""),
            category=d.get("category", ""),
            tags=d.get("tags", []),
            source=d.get("source", "tool"),
        )


@dataclass
class StepOutput:
    """Parsed model output for a single step within a tick."""

    step_summary: str = ""
    action: StepAction = StepAction.THINK
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    proposed_memories: List[ProposedMemory] = field(default_factory=list)
    stop_reason: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StepOutput":
        action_raw = d.get("action", "think").lower()
        try:
            action = StepAction(action_raw)
        except ValueError:
            action = StepAction.THINK

        proposed = [
            ProposedMemory.from_dict(pm)
            for pm in d.get("proposed_memories", [])
        ]

        return cls(
            step_summary=d.get("step_summary", ""),
            action=action,
            tool_name=d.get("tool_name"),
            tool_args=d.get("tool_args"),
            proposed_memories=proposed,
            stop_reason=d.get("stop_reason"),
        )


# ------------------------------------------------------------------
# Tick-level outcome (written to journal)
# ------------------------------------------------------------------

@dataclass
class TickOutcome:
    """Summary of a single tick execution, serialised to journal."""

    tick_index: int
    steps_taken: int = 0
    tools_used: List[str] = field(default_factory=list)
    tool_actions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stop_reason: Optional[str] = None
    outcome_summary: str = ""
    memories_proposed: int = 0
    memories_written: int = 0
    metering: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "tick_index": self.tick_index,
            "steps_taken": self.steps_taken,
            "tools_used": self.tools_used,
            "tool_actions": self.tool_actions,
            "errors": self.errors,
            "stop_reason": self.stop_reason,
            "outcome_summary": self.outcome_summary,
            "memories_proposed": self.memories_proposed,
            "memories_written": self.memories_written,
        }
        if self.metering is not None:
            d["metering"] = self.metering
        return d
