"""Secret detection with detect-secrets (pip-installed, offline, no account)."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings


@dataclass(frozen=True)
class SecretFinding:
    file: str
    line: int
    type: str


def scan_files(paths: list[Path], base: Path | None = None) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    with default_settings():
        collection = SecretsCollection()
        for path in paths:
            collection.scan_file(str(path))
    for filename, secrets in collection.json().items():
        rel = str(Path(filename).relative_to(base)) if base else filename
        findings.extend(SecretFinding(rel, s["line_number"], s["type"]) for s in secrets)
    return findings


def scan_text(text: str, name: str = "input.txt") -> list[SecretFinding]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        return [SecretFinding(name, f.line, f.type) for f in scan_files([path])]
