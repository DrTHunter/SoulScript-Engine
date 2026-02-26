"""TickScheduler — indefinite / finite loop scheduler for AGI-like autonomous runs.

Manages a schedule of ticks with configurable:
  - Tick interval (hours + minutes between cycles)
  - Finite or infinite loop count
  - Pause / resume / stop controls
  - Per-tick step count
  - Budget-aware automatic pausing

State is persisted to data/shared/agi_loop_state.json so it survives restarts.

Usage:
    scheduler = TickScheduler.from_config(config, profile_name="orion")
    scheduler.start()  # begins scheduling
    scheduler.stop()   # clean stop
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class LoopStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    WAITING = "waiting"  # between ticks, counting down
    ERROR = "error"


@dataclass
class ScheduleConfig:
    """Schedule configuration for the AGI loop."""
    interval_hours: int = 0
    interval_minutes: int = 30
    max_loops: int = 0  # 0 = infinite
    ticks_per_loop: int = 15
    max_steps_per_tick: int = 3
    stimulus: str = ""
    profile: str = ""
    auto_pause_on_budget: bool = True
    auto_pause_on_error_streak: int = 5  # pause after N consecutive errors

    @property
    def interval_seconds(self) -> int:
        return (self.interval_hours * 3600) + (self.interval_minutes * 60)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interval_hours": self.interval_hours,
            "interval_minutes": self.interval_minutes,
            "max_loops": self.max_loops,
            "ticks_per_loop": self.ticks_per_loop,
            "max_steps_per_tick": self.max_steps_per_tick,
            "stimulus": self.stimulus,
            "profile": self.profile,
            "auto_pause_on_budget": self.auto_pause_on_budget,
            "auto_pause_on_error_streak": self.auto_pause_on_error_streak,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScheduleConfig":
        return cls(
            interval_hours=d.get("interval_hours", 0),
            interval_minutes=d.get("interval_minutes", 30),
            max_loops=d.get("max_loops", 0),
            ticks_per_loop=d.get("ticks_per_loop", 15),
            max_steps_per_tick=d.get("max_steps_per_tick", 3),
            stimulus=d.get("stimulus", ""),
            profile=d.get("profile", ""),
            auto_pause_on_budget=d.get("auto_pause_on_budget", True),
            auto_pause_on_error_streak=d.get("auto_pause_on_error_streak", 5),
        )


@dataclass
class LoopState:
    """Persistent state for the AGI loop."""
    status: str = LoopStatus.IDLE
    loops_completed: int = 0
    total_ticks_run: int = 0
    total_errors: int = 0
    consecutive_errors: int = 0
    total_cost: float = 0.0
    started_at: str = ""
    last_loop_at: str = ""
    next_loop_at: str = ""
    last_error: str = ""
    schedule: Dict[str, Any] = field(default_factory=dict)

    # Log of recent loop outcomes for display
    recent_loops: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "loops_completed": self.loops_completed,
            "total_ticks_run": self.total_ticks_run,
            "total_errors": self.total_errors,
            "consecutive_errors": self.consecutive_errors,
            "total_cost": round(self.total_cost, 6),
            "started_at": self.started_at,
            "last_loop_at": self.last_loop_at,
            "next_loop_at": self.next_loop_at,
            "last_error": self.last_error,
            "schedule": self.schedule,
            "recent_loops": self.recent_loops[-50:],  # keep last 50
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LoopState":
        return cls(
            status=d.get("status", LoopStatus.IDLE),
            loops_completed=d.get("loops_completed", 0),
            total_ticks_run=d.get("total_ticks_run", 0),
            total_errors=d.get("total_errors", 0),
            consecutive_errors=d.get("consecutive_errors", 0),
            total_cost=d.get("total_cost", 0.0),
            started_at=d.get("started_at", ""),
            last_loop_at=d.get("last_loop_at", ""),
            next_loop_at=d.get("next_loop_at", ""),
            last_error=d.get("last_error", ""),
            schedule=d.get("schedule", {}),
            recent_loops=d.get("recent_loops", []),
        )


def _agi_state_path() -> str:
    """Path to the AGI loop state file."""
    from src import data_paths
    data_paths.shared_dir()
    return os.path.join(data_paths.DATA_ROOT, "shared", "agi_loop_state.json")


class TickScheduler:
    """Scheduler for indefinite AGI-like autonomous agent loops.

    Controls timing, loop counting, pause/resume, and integrates
    with the burst runner for actual tick execution.

    Parameters
    ----------
    config : ScheduleConfig
        Scheduling parameters.
    run_burst_fn : callable, optional
        Function to call for each loop cycle. Signature:
        (profile_name, burst_ticks, max_steps_per_tick, stimulus) -> list[TickOutcome]
    budget_tracker : optional BudgetTracker
        For budget-aware auto-pausing.
    state_path : str, optional
        Override path for state persistence.
    """

    def __init__(
        self,
        config: ScheduleConfig,
        run_burst_fn: Optional[Callable] = None,
        budget_tracker: "Any" = None,
        state_path: str | None = None,
    ):
        self.config = config
        self._run_burst_fn = run_burst_fn
        self.budget_tracker = budget_tracker
        self._state_path = state_path or _agi_state_path()
        self.state = self._load_state()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused by default
        self._listeners: List[Callable] = []

    def _load_state(self) -> LoopState:
        """Load persisted state or create new."""
        if os.path.isfile(self._state_path):
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    return LoopState.from_dict(json.load(f))
            except (json.JSONDecodeError, KeyError):
                pass
        return LoopState(schedule=self.config.to_dict())

    def _save_state(self):
        """Persist state to disk."""
        self.state.schedule = self.config.to_dict()
        os.makedirs(os.path.dirname(self._state_path), exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def add_listener(self, fn: Callable):
        """Add a callback for state change events."""
        self._listeners.append(fn)

    def _notify(self, event: str, data: Dict[str, Any] | None = None):
        """Notify all listeners of a state change."""
        for fn in self._listeners:
            try:
                fn(event, data or {})
            except Exception:
                pass

    def start(self):
        """Start the scheduler in a background thread."""
        if self._thread and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self._pause_event.set()
        self.state.status = LoopStatus.RUNNING
        self.state.started_at = datetime.now(timezone.utc).isoformat()
        self._save_state()
        self._notify("started")

        self._thread = threading.Thread(target=self._loop, daemon=True, name="agi-loop")
        self._thread.start()

    def stop(self):
        """Stop the scheduler gracefully."""
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused
        self.state.status = LoopStatus.STOPPED
        self._save_state()
        self._notify("stopped")
        if self._thread:
            self._thread.join(timeout=10)

    def pause(self):
        """Pause the scheduler (finish current tick, then wait)."""
        self._pause_event.clear()
        self.state.status = LoopStatus.PAUSED
        self._save_state()
        self._notify("paused")

    def resume(self):
        """Resume from pause."""
        self._pause_event.set()
        self.state.status = LoopStatus.RUNNING
        self._save_state()
        self._notify("resumed")

    def update_config(self, new_config: Dict[str, Any]):
        """Update schedule configuration (can be done while running)."""
        for key, value in new_config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._save_state()
        self._notify("config_updated", new_config)

    def get_status(self) -> Dict[str, Any]:
        """Return full status for the UI."""
        now = datetime.now(timezone.utc)
        countdown = ""
        if self.state.next_loop_at:
            try:
                next_dt = datetime.fromisoformat(self.state.next_loop_at)
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)
                diff = (next_dt - now).total_seconds()
                if diff > 0:
                    hours = int(diff // 3600)
                    minutes = int((diff % 3600) // 60)
                    seconds = int(diff % 60)
                    countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except (ValueError, TypeError):
                pass

        return {
            "status": self.state.status,
            "loops_completed": self.state.loops_completed,
            "max_loops": self.config.max_loops,
            "is_infinite": self.config.max_loops == 0,
            "total_ticks_run": self.state.total_ticks_run,
            "total_errors": self.state.total_errors,
            "consecutive_errors": self.state.consecutive_errors,
            "total_cost": round(self.state.total_cost, 4),
            "started_at": self.state.started_at,
            "last_loop_at": self.state.last_loop_at,
            "next_loop_at": self.state.next_loop_at,
            "countdown": countdown,
            "last_error": self.state.last_error,
            "schedule": self.config.to_dict(),
            "recent_loops": self.state.recent_loops[-20:],
            "budget": self.budget_tracker.get_summary() if self.budget_tracker else None,
        }

    def _loop(self):
        """Main scheduler loop (runs in background thread)."""
        while not self._stop_event.is_set():
            # Check pause
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            # Check finite loop limit
            if self.config.max_loops > 0 and self.state.loops_completed >= self.config.max_loops:
                self.state.status = LoopStatus.STOPPED
                self._save_state()
                self._notify("completed", {"reason": "max_loops_reached"})
                break

            # Check budget
            if self.config.auto_pause_on_budget and self.budget_tracker:
                if self.budget_tracker.is_hard_limit_hit():
                    self.state.status = LoopStatus.PAUSED
                    self.state.last_error = "Budget hard limit reached — auto-paused"
                    self._save_state()
                    self._notify("auto_paused", {"reason": "budget_exhausted"})
                    self._pause_event.clear()
                    self._pause_event.wait()
                    if self._stop_event.is_set():
                        break
                    continue

            # Check consecutive error streak
            if (
                self.config.auto_pause_on_error_streak > 0
                and self.state.consecutive_errors >= self.config.auto_pause_on_error_streak
            ):
                self.state.status = LoopStatus.PAUSED
                self.state.last_error = (
                    f"Auto-paused after {self.state.consecutive_errors} consecutive errors"
                )
                self._save_state()
                self._notify("auto_paused", {"reason": "error_streak"})
                self._pause_event.clear()
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break
                self.state.consecutive_errors = 0
                continue

            # Run one loop cycle
            self.state.status = LoopStatus.RUNNING
            loop_start = datetime.now(timezone.utc)
            self.state.last_loop_at = loop_start.isoformat()
            self._save_state()
            self._notify("loop_start", {"loop": self.state.loops_completed})

            loop_result = self._execute_loop()

            self.state.loops_completed += 1
            self.state.total_ticks_run += loop_result.get("ticks", 0)

            loop_errors = loop_result.get("errors", 0)
            self.state.total_errors += loop_errors
            if loop_errors > 0:
                self.state.consecutive_errors += loop_errors
            else:
                self.state.consecutive_errors = 0

            loop_cost = loop_result.get("cost", 0.0)
            self.state.total_cost += loop_cost

            # Record to recent loops
            self.state.recent_loops.append({
                "loop": self.state.loops_completed,
                "at": loop_start.isoformat(),
                "ticks": loop_result.get("ticks", 0),
                "errors": loop_errors,
                "cost": round(loop_cost, 6),
                "summary": loop_result.get("summary", ""),
            })
            self.state.recent_loops = self.state.recent_loops[-50:]

            self._notify("loop_end", loop_result)

            # Calculate next loop time
            if self._stop_event.is_set():
                break

            interval = self.config.interval_seconds
            if interval > 0:
                next_time = datetime.now(timezone.utc) + timedelta(seconds=interval)
                self.state.next_loop_at = next_time.isoformat()
                self.state.status = LoopStatus.WAITING
                self._save_state()
                self._notify("waiting", {"next_at": self.state.next_loop_at})

                # Sleep in 1-second intervals so we can respond to stop/pause
                for _ in range(interval):
                    if self._stop_event.is_set():
                        break
                    if not self._pause_event.is_set():
                        self.state.status = LoopStatus.PAUSED
                        self._save_state()
                        self._pause_event.wait()
                        if self._stop_event.is_set():
                            break
                    time.sleep(1)

        self.state.status = LoopStatus.STOPPED
        self.state.next_loop_at = ""
        self._save_state()

    def _execute_loop(self) -> Dict[str, Any]:
        """Execute one loop cycle (burst of ticks).

        Returns a result dict with keys: ticks, errors, cost, summary.
        """
        if self._run_burst_fn is None:
            # If no burst function provided, try importing
            try:
                from src.runner.burst import run_burst
                self._run_burst_fn = run_burst
            except ImportError:
                return {
                    "ticks": 0,
                    "errors": 1,
                    "cost": 0.0,
                    "summary": "Failed to import run_burst",
                }

        try:
            outcomes = self._run_burst_fn(
                profile_name=self.config.profile,
                burst_ticks=self.config.ticks_per_loop,
                max_steps_per_tick=self.config.max_steps_per_tick,
                stimulus=self.config.stimulus,
            )

            total_errors = sum(len(o.errors) for o in outcomes)
            total_cost = 0.0
            for o in outcomes:
                if o.metering:
                    m_cost = o.metering.get("cost", {})
                    if isinstance(m_cost, dict):
                        total_cost += m_cost.get("total_cost", 0.0)
                    elif isinstance(m_cost, (int, float)):
                        total_cost += m_cost

            # Record cost to budget tracker
            if self.budget_tracker and total_cost > 0:
                tier_name = "burst_loop"
                self.budget_tracker.record_cost(total_cost, tier_name)

            summaries = [o.outcome_summary for o in outcomes if o.outcome_summary]
            summary = "; ".join(summaries[:3]) if summaries else "Loop completed"

            if total_errors > 0:
                self.state.last_error = f"{total_errors} errors in last loop"

            return {
                "ticks": len(outcomes),
                "errors": total_errors,
                "cost": total_cost,
                "summary": summary[:300],
            }

        except Exception as exc:
            self.state.last_error = str(exc)[:200]
            return {
                "ticks": 0,
                "errors": 1,
                "cost": 0.0,
                "summary": f"Loop failed: {exc}",
            }

    @classmethod
    def from_config(
        cls,
        config_dict: Dict[str, Any],
        budget_tracker: "Any" = None,
        run_burst_fn: Optional[Callable] = None,
    ) -> "TickScheduler":
        """Create from a config dict.

        Expected structure::

            agi_loop:
              interval_hours: 0
              interval_minutes: 30
              max_loops: 0          # 0 = infinite
              ticks_per_loop: 15
              max_steps_per_tick: 3
              stimulus: ""
              profile: orion
              auto_pause_on_budget: true
              auto_pause_on_error_streak: 5
        """
        config = ScheduleConfig.from_dict(config_dict)
        return cls(
            config=config,
            run_burst_fn=run_burst_fn,
            budget_tracker=budget_tracker,
        )
