"""Content hashing used for artifact versions, approvals and the audit chain."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> bytes:
    """Stable JSON bytes: sorted keys, no insignificant whitespace, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(data: Any) -> str:
    return sha256_bytes(canonical_json(data))


def sha256_file_content(name: str, content: bytes) -> str:
    """JSON files are hashed in canonical form so re-formatting does not change the hash."""
    if name.endswith(".json"):
        try:
            return sha256_json(json.loads(content))
        except ValueError:
            pass
    return sha256_bytes(content)
