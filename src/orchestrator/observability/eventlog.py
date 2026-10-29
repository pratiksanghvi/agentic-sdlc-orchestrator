"""Append-only, hash-chained JSONL audit log.

Every record stores the hash of the previous record, so editing or deleting any past line
breaks the chain and `verify()` reports the first broken sequence number. One log per run
holds every record kind: events, LLM calls (full prompt and response inline), human
interactions and decisions.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from orchestrator.hashing import sha256_json

RecordKind = Literal["event", "llm_call", "human_interaction", "decision"]
GENESIS = "sha256:genesis"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._seq, self._last_hash = self._tail()

    def _tail(self) -> tuple[int, str]:
        if not self.path.exists():
            return 0, GENESIS
        last = None
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = json.loads(line)
        return (last["seq"], last["hash"]) if last else (0, GENESIS)

    def append(self, kind: RecordKind, name: str, **data: Any) -> dict[str, Any]:
        # normalise to plain JSON first so the hashed form equals the stored form
        data = json.loads(json.dumps(data, default=str))
        with self._lock:
            record = {
                "seq": self._seq + 1,
                "ts": utc_now(),
                "kind": kind,
                "name": name,
                "data": data,
                "prev_hash": self._last_hash,
            }
            record["hash"] = sha256_json(record)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._seq, self._last_hash = record["seq"], record["hash"]
            return record

    def records(self, kind: RecordKind | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        return [r for r in rows if kind is None or r["kind"] == kind]

    def verify(self) -> tuple[bool, int | None]:
        """Return (True, None) if the chain is intact, else (False, first bad seq)."""
        prev = GENESIS
        expected_seq = 1
        for record in self.records():
            body = {k: v for k, v in record.items() if k != "hash"}
            if (
                record.get("seq") != expected_seq
                or record.get("prev_hash") != prev
                or sha256_json(body) != record.get("hash")
            ):
                return False, record.get("seq", expected_seq)
            prev = record["hash"]
            expected_seq += 1
        return True, None
