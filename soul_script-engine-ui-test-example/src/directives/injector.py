"""Directives injector — builds a bounded context block for prompt injection.

Called once at session start to load relevant directive sections and
format them as a Markdown block appended to the system prompt.
Also registers loaded sections with the ActiveDirectives tracker.
"""

from typing import List, Optional

from src.directives.store import DirectiveStore
from src.governance.active_directives import ActiveDirectives


def build_directives_block(
    store: DirectiveStore,
    query: Optional[str] = None,
    max_sections: int = 5,
    manifest: Optional[dict] = None,
) -> str:
    """Return a Markdown block of relevant directive sections.

    If *query* is given, returns top-ranked sections by relevance.
    If no query, returns all sections up to *max_sections*.
    Returns an empty string when no sections match.

    Side effect: registers loaded sections with ActiveDirectives.
    """
    if query:
        sections = store.search(query, limit=max_sections)
    else:
        sections = store.get_all()[:max_sections]

    if not sections:
        return ""

    # Register with ActiveDirectives tracker
    ActiveDirectives.record_sections(sections, manifest=manifest)

    lines = [
        "## Active Directives",
        "",
        "The following directives have been loaded based on session context.",
        "These are authoritative instructions from the user. Follow them.",
        "",
    ]

    for section in sections:
        lines.append(f"### {section.heading}")
        lines.append(section.body)
        lines.append(f"*(scope: {section.scope})*")
        lines.append("")

    return "\n".join(lines)
