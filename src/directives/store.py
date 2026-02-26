"""Directive store — loads, scores, and searches directive sections.

Scoring uses the same algorithm as :mod:`src.memory.vault`:
token overlap + substring bonus + SequenceMatcher ratio.
"""

import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Union

from src.directives.parser import DirectiveSection, parse_directive_file


def score_section(query: str, section: DirectiveSection) -> float:
    """Score a directive section against a query.

    Algorithm (mirrors MemoryVault.search_memories):
      1. Token overlap ratio
      2. Substring bonus (+0.3)
      3. SequenceMatcher ratio * 0.4
    Returns 0.0 when there is no token overlap.
    """
    query_lower = query.lower()
    query_tokens = set(re.findall(r"\w+", query_lower))
    if not query_tokens:
        return 0.0

    # Combine heading + body for matching
    text_lower = (section.heading + " " + section.body).lower()
    text_tokens = set(re.findall(r"\w+", text_lower))

    overlap = len(query_tokens & text_tokens)
    if overlap == 0:
        return 0.0

    token_score = overlap / len(query_tokens)
    substr_bonus = 0.3 if query_lower in text_lower else 0.0
    seq_score = SequenceMatcher(None, query_lower, text_lower).ratio() * 0.4

    return token_score + substr_bonus + seq_score


class DirectiveStore:
    """Loads and searches user-authored directive markdown files."""

    def __init__(self, directives_dir: str, scopes: Union[str, List[str]]):
        self._dir = directives_dir
        if isinstance(scopes, str):
            self._scopes = [scopes.lower()]
        else:
            self._scopes = [s.lower() for s in scopes]
        self._sections: List[DirectiveSection] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        for scope in self._scopes:
            path = os.path.join(self._dir, f"{scope}.md")
            self._sections.extend(parse_directive_file(path, scope))
        self._loaded = True

    def search(self, query: str, limit: int = 5) -> List[DirectiveSection]:
        """Return sections ranked by relevance to *query*."""
        self._ensure_loaded()
        scored = []
        for section in self._sections:
            s = score_section(query, section)
            if s > 0:
                scored.append((s, section))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [sec for _, sec in scored[:limit]]

    def list_headings(self) -> List[Dict[str, str]]:
        """Return all section headings with their scope."""
        self._ensure_loaded()
        return [
            {"heading": s.heading, "scope": s.scope, "source": s.source_file}
            for s in self._sections
        ]

    def get_section(self, heading: str) -> Optional[DirectiveSection]:
        """Return a specific section by exact heading (case-insensitive)."""
        self._ensure_loaded()
        heading_lower = heading.lower().strip()
        for s in self._sections:
            if s.heading.lower().strip() == heading_lower:
                return s
        return None

    def get_all(self) -> List[DirectiveSection]:
        """Return all loaded sections."""
        self._ensure_loaded()
        return list(self._sections)
