"""Directive file parser — splits markdown into searchable sections.

Sections are delimited by ``## Heading`` lines.  HTML comments are
stripped.  Content before the first heading is discarded.
"""

import os
import re
from dataclasses import dataclass
from typing import List

_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass
class DirectiveSection:
    heading: str
    body: str
    scope: str
    source_file: str


def parse_directive_file(path: str, scope: str) -> List[DirectiveSection]:
    """Parse a markdown file into sections split on ``## `` headings.

    Returns one :class:`DirectiveSection` per non-empty heading block.
    """
    if not os.path.isfile(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Strip HTML comment lines
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("<!--")]
    text = "\n".join(lines)

    matches = list(_HEADING_RE.finditer(text))
    source_file = os.path.basename(path)
    sections: List[DirectiveSection] = []

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if body:
            sections.append(DirectiveSection(
                heading=heading,
                body=body,
                scope=scope,
                source_file=source_file,
            ))

    return sections
