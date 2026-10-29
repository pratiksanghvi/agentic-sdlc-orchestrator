"""R1 intake guardrail: size limits, secrets and obvious personal data in the requirement."""

from __future__ import annotations

import re

from orchestrator.guardrails.secrets import scan_text

_PII = {
    "US social security number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "payment card number": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
}


def _luhn_ok(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        checksum += d
    return len(digits) >= 13 and checksum % 10 == 0


def check_requirement(text: str, max_bytes: int) -> list[str]:
    """Return human-readable reasons to reject the input (empty list = accepted)."""
    problems: list[str] = []
    if not text.strip():
        return ["the requirement is empty"]
    size = len(text.encode("utf-8"))
    if size > max_bytes:
        problems.append(f"the requirement is {size} bytes; the limit is {max_bytes}")
    for finding in scan_text(text, "requirement.txt"):
        problems.append(f"line {finding.line} looks like a secret ({finding.type}); remove it")
    for label, pattern in _PII.items():
        for match in pattern.finditer(text):
            if label == "payment card number" and not _luhn_ok(match.group()):
                continue
            problems.append(f"the requirement appears to contain a {label}; remove it")
            break
    return problems
