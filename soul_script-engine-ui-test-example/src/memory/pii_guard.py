"""PII guard — blocks storage of sensitive personal data.

Rule set (from spec):
  SHOULD store:  stable personal info, long-term prefs, projects/goals, constraints.
  SHOULD NOT store: passwords, secrets, tokens, SSNs, full addresses, credit cards.
"""

import re
from typing import List, Tuple

# (compiled regex, human-readable label)
_PII_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "SSN (xxx-xx-xxxx)"),
    (re.compile(r"\b\d{9}\b"), "potential SSN (9 consecutive digits)"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "credit/debit card number"),
]

_BLOCKED_KEYWORDS: List[str] = [
    "password:", "passwd:", "api_key:", "apikey:", "api key:",
    "secret_key:", "secretkey:", "secret key:",
    "access_token:", "auth_token:", "bearer ",
    "ssn:", "social security number:",
]


def check_pii(text: str) -> List[str]:
    """Return a list of PII violation descriptions. Empty list means safe."""
    violations: List[str] = []
    lower = text.lower().strip()

    for keyword in _BLOCKED_KEYWORDS:
        if keyword in lower:
            violations.append(f"Blocked keyword detected: '{keyword.rstrip(':').strip()}'")

    for pattern, label in _PII_PATTERNS:
        if pattern.search(text):
            violations.append(f"Pattern match: {label}")

    return violations
