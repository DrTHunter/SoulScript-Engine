"""CLI entrypoint for the Burst Runner.

Usage:
    python -m src.run_burst --profile orion --burst-ticks 15 --max-steps 3
    python -m src.run_burst --profile orion --stimulus "Review and consolidate your memories."
"""

import argparse
import sys

from src.runner.burst import run_burst


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an agent in burst mode for N autonomous ticks.",
    )
    parser.add_argument(
        "--profile",
        required=True,
        help="Profile name (e.g. orion, elysia).",
    )
    parser.add_argument(
        "--burst-ticks",
        type=int,
        default=15,
        help="Number of ticks to run (default: 15).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=3,
        help="Max model calls per tick (default: 3).",
    )
    parser.add_argument(
        "--stimulus",
        type=str,
        default="",
        help="Optional seed prompt injected into each tick.",
    )
    args = parser.parse_args()

    outcomes = run_burst(
        profile_name=args.profile,
        burst_ticks=args.burst_ticks,
        max_steps_per_tick=args.max_steps,
        stimulus=args.stimulus,
    )

    # Exit code: 0 if no errors across all ticks, 1 otherwise
    total_errors = sum(len(o.errors) for o in outcomes)
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
