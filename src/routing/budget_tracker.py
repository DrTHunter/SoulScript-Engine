"""BudgetTracker — monthly spending enforcement with soft/hard limits.

Reads metering data from the observability layer and enforces:
  - Monthly hard cap (default $20)
  - Soft limit (default 80% of hard cap) — triggers warnings and tier demotion
  - Per-session caps
  - Per-tick caps (for burst mode)

Persists budget state to data/shared/budget_state.json.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src import data_paths


@dataclass
class BudgetState:
    """Current budget tracking state."""
    monthly_hard_cap: float = 20.00
    monthly_soft_cap: float = 16.00  # 80% of hard cap
    per_session_cap: float = 2.00
    per_tick_cap: float = 0.10

    # Accumulators
    month_key: str = ""  # e.g. "2026-02"
    monthly_spent: float = 0.0
    session_spent: float = 0.0
    total_spent_all_time: float = 0.0

    # Per-tier breakdown
    tier_spending: Dict[str, float] = field(default_factory=dict)

    # Timestamps
    last_updated: str = ""
    month_reset_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "monthly_hard_cap": self.monthly_hard_cap,
            "monthly_soft_cap": self.monthly_soft_cap,
            "per_session_cap": self.per_session_cap,
            "per_tick_cap": self.per_tick_cap,
            "month_key": self.month_key,
            "monthly_spent": round(self.monthly_spent, 6),
            "session_spent": round(self.session_spent, 6),
            "total_spent_all_time": round(self.total_spent_all_time, 6),
            "tier_spending": {k: round(v, 6) for k, v in self.tier_spending.items()},
            "last_updated": self.last_updated,
            "month_reset_at": self.month_reset_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BudgetState":
        return cls(
            monthly_hard_cap=d.get("monthly_hard_cap", 20.00),
            monthly_soft_cap=d.get("monthly_soft_cap", 16.00),
            per_session_cap=d.get("per_session_cap", 2.00),
            per_tick_cap=d.get("per_tick_cap", 0.10),
            month_key=d.get("month_key", ""),
            monthly_spent=d.get("monthly_spent", 0.0),
            session_spent=d.get("session_spent", 0.0),
            total_spent_all_time=d.get("total_spent_all_time", 0.0),
            tier_spending=d.get("tier_spending", {}),
            last_updated=d.get("last_updated", ""),
            month_reset_at=d.get("month_reset_at", ""),
        )


def _budget_state_path() -> str:
    """Path to the budget state JSON file."""
    data_paths.shared_dir()
    return os.path.join(data_paths.DATA_ROOT, "shared", "budget_state.json")


class BudgetTracker:
    """Tracks and enforces API spending budgets.

    Parameters
    ----------
    monthly_hard_cap : float
        Maximum monthly spending in USD (hard stop).
    monthly_soft_cap : float
        Soft warning threshold — triggers tier demotion.
    per_session_cap : float
        Maximum spending per interactive session.
    per_tick_cap : float
        Maximum spending per burst tick.
    state_path : str, optional
        Override path for budget state file.
    """

    def __init__(
        self,
        monthly_hard_cap: float = 20.00,
        monthly_soft_cap: float | None = None,
        per_session_cap: float = 2.00,
        per_tick_cap: float = 0.10,
        state_path: str | None = None,
    ):
        self._state_path = state_path or _budget_state_path()
        self.state = self._load_or_create(
            monthly_hard_cap,
            monthly_soft_cap or (monthly_hard_cap * 0.8),
            per_session_cap,
            per_tick_cap,
        )
        self._check_month_rollover()

    def _load_or_create(
        self,
        hard_cap: float,
        soft_cap: float,
        session_cap: float,
        tick_cap: float,
    ) -> BudgetState:
        """Load existing state or create fresh."""
        if os.path.isfile(self._state_path):
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = BudgetState.from_dict(data)
                # Update caps from config (they may have changed)
                state.monthly_hard_cap = hard_cap
                state.monthly_soft_cap = soft_cap
                state.per_session_cap = session_cap
                state.per_tick_cap = tick_cap
                return state
            except (json.JSONDecodeError, KeyError):
                pass

        return BudgetState(
            monthly_hard_cap=hard_cap,
            monthly_soft_cap=soft_cap,
            per_session_cap=session_cap,
            per_tick_cap=tick_cap,
            month_key=datetime.now(timezone.utc).strftime("%Y-%m"),
        )

    def _check_month_rollover(self):
        """Reset monthly spending if we've entered a new month."""
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if self.state.month_key != current_month:
            self.state.month_key = current_month
            self.state.monthly_spent = 0.0
            self.state.tier_spending = {}
            self.state.month_reset_at = datetime.now(timezone.utc).isoformat()
            self._save()

    def record_cost(self, cost_usd: float, tier_name: str = "unknown"):
        """Record spending from an LLM call.

        Parameters
        ----------
        cost_usd : float
            Cost in USD for this call.
        tier_name : str
            Which tier the call was routed to.
        """
        self._check_month_rollover()
        self.state.monthly_spent += cost_usd
        self.state.session_spent += cost_usd
        self.state.total_spent_all_time += cost_usd
        self.state.tier_spending[tier_name] = (
            self.state.tier_spending.get(tier_name, 0.0) + cost_usd
        )
        self.state.last_updated = datetime.now(timezone.utc).isoformat()
        self._save()

    def remaining(self) -> float:
        """Return remaining budget for the current month."""
        return max(0.0, self.state.monthly_hard_cap - self.state.monthly_spent)

    def is_hard_limit_hit(self) -> bool:
        """True if monthly hard cap is exceeded."""
        return self.state.monthly_spent >= self.state.monthly_hard_cap

    def is_soft_limit_hit(self) -> bool:
        """True if monthly soft cap is exceeded (warnings + tier demotion)."""
        return self.state.monthly_spent >= self.state.monthly_soft_cap

    def is_session_limit_hit(self) -> bool:
        """True if current session spending exceeds per_session_cap."""
        return self.state.session_spent >= self.state.per_session_cap

    def check_tick_budget(self, proposed_cost_estimate: float = 0.0) -> Optional[str]:
        """Check if a tick's estimated cost would exceed limits.

        Returns
        -------
        str or None
            Reason string if the call should be blocked, else None.
        """
        if self.is_hard_limit_hit():
            return (
                f"Monthly budget exhausted (${self.state.monthly_spent:.4f} / "
                f"${self.state.monthly_hard_cap:.2f})"
            )
        if proposed_cost_estimate > self.state.per_tick_cap:
            return (
                f"Estimated tick cost ${proposed_cost_estimate:.4f} exceeds "
                f"per-tick cap ${self.state.per_tick_cap:.2f}"
            )
        return None

    def reset_session(self):
        """Reset session-level spending (called at session start)."""
        self.state.session_spent = 0.0
        self._save()

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary dict for display / API."""
        return {
            "monthly_spent": round(self.state.monthly_spent, 4),
            "monthly_hard_cap": self.state.monthly_hard_cap,
            "monthly_soft_cap": self.state.monthly_soft_cap,
            "remaining": round(self.remaining(), 4),
            "session_spent": round(self.state.session_spent, 4),
            "per_session_cap": self.state.per_session_cap,
            "per_tick_cap": self.state.per_tick_cap,
            "total_all_time": round(self.state.total_spent_all_time, 4),
            "tier_spending": {k: round(v, 4) for k, v in self.state.tier_spending.items()},
            "month_key": self.state.month_key,
            "hard_limit_hit": self.is_hard_limit_hit(),
            "soft_limit_hit": self.is_soft_limit_hit(),
            "last_updated": self.state.last_updated,
        }

    def _save(self):
        """Persist budget state to disk."""
        os.makedirs(os.path.dirname(self._state_path), exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    @classmethod
    def from_config(cls, budget_cfg: Dict[str, Any]) -> "BudgetTracker":
        """Create a BudgetTracker from a config dict.

        Expected structure::

            budget:
              monthly_hard_cap: 20.00
              monthly_soft_cap: 16.00
              per_session_cap: 2.00
              per_tick_cap: 0.10
        """
        return cls(
            monthly_hard_cap=budget_cfg.get("monthly_hard_cap", 20.00),
            monthly_soft_cap=budget_cfg.get("monthly_soft_cap"),
            per_session_cap=budget_cfg.get("per_session_cap", 2.00),
            per_tick_cap=budget_cfg.get("per_tick_cap", 0.10),
        )
