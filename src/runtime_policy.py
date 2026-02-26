"""Runtime policy enforcement.

Controls:
    max_iterations     – hard cap on inner tool-call loops per user turn (default 25).
    max_wall_time_seconds – optional wall-clock limit per user turn.
    stasis_mode        – freeze state: no state overwrite, tools disabled;
                         journal may still append (Cryonics Protocol Directive).
    tool_failure_mode  – "continue" keeps going after a tool error;
                         "stop" halts the inner loop immediately.
    self_refine_steps  – internal refinement iterations per user turn (max 15).
"""

import time
from dataclasses import dataclass
from typing import Optional

_MAX_REFINE_CAP = 15


@dataclass
class RuntimePolicy:
    max_iterations: int = 25
    max_wall_time_seconds: Optional[float] = None
    stasis_mode: bool = False
    tool_failure_mode: str = "continue"  # "continue" | "stop"
    self_refine_steps: int = 0

    def __post_init__(self):
        self.self_refine_steps = max(0, min(self.self_refine_steps, _MAX_REFINE_CAP))

    def check(self, iteration: int, wall_start: float) -> Optional[str]:
        """Return a human-readable reason string if a limit is hit, else None."""
        if iteration >= self.max_iterations:
            return f"Max iterations reached ({self.max_iterations})"
        if self.max_wall_time_seconds is not None:
            elapsed = time.time() - wall_start
            if elapsed >= self.max_wall_time_seconds:
                return (
                    f"Wall-time limit exceeded "
                    f"({elapsed:.1f}s >= {self.max_wall_time_seconds}s)"
                )
        return None
