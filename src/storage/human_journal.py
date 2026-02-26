"""Human-readable journal — ``data/journal.md``.

A clean, chronological markdown diary that records one entry per
session or burst.  Designed to be opened in any text editor or
markdown viewer and read like a logbook.

Format::

    ## 2026-02-13 18:14  ·  burst  ·  orion

    Ran 5 ticks.  Orion wrote 10 memories about his first awakening,
    including identity anchors and continuity checks.  2 errors
    (duplicate detection).  No tool boundary contacts.

    ---

Each entry is separated by a horizontal rule.  Newest entries are
appended at the bottom.
"""

import os
import time
from typing import List, Optional

from src.data_paths import human_journal_path


def append_entry(
    source: str,
    profile: str,
    summary: str,
    details: Optional[List[str]] = None,
) -> None:
    """Append one diary entry to ``data/journal.md``.

    Parameters
    ----------
    source:
        What produced this entry.  Examples: ``session``, ``burst``,
        ``tool``, ``system``, ``migration``.
    profile:
        Agent name (e.g. ``orion``, ``elysia``, ``system``).
    summary:
        1-3 sentence plain-English summary of what happened.
    details:
        Optional bullet points for extra context (kept short).
    """
    path = human_journal_path()
    now = time.strftime("%Y-%m-%d %H:%M", time.localtime())

    lines = [
        f"## {now}  ·  {source}  ·  {profile}",
        "",
        summary.strip(),
    ]

    if details:
        lines.append("")
        for d in details:
            lines.append(f"- {d}")

    lines.append("")
    lines.append("---")
    lines.append("")

    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
