"""Versioned, immutable artifact store (design foundation F1).

Every write creates `<type>/v<n>/` holding the complete file set plus `manifest.json`.
Version folders are never modified; integrity is checked by re-hashing files against the
manifest. Lifecycle status (DRAFT / APPROVED / REJECTED / SUPERSEDED) lives in the event log.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from orchestrator.hashing import sha256_file_content, sha256_json
from orchestrator.observability.eventlog import utc_now

_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_DIR = re.compile(r"^v(\d+)$")


class ArtifactRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    version: int
    hash: str

    def __str__(self) -> str:
        return f"{self.type} v{self.version} ({self.hash[7:19]})"


class IntegrityError(Exception):
    """An artifact version on disk no longer matches its manifest."""


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _type_dir(self, artifact_type: str) -> Path:
        if not _TYPE_RE.match(artifact_type):
            raise ValueError(f"invalid artifact type: {artifact_type!r}")
        return self.root / artifact_type

    def versions(self, artifact_type: str) -> list[int]:
        type_dir = self._type_dir(artifact_type)
        if not type_dir.is_dir():
            return []
        found = (_VERSION_DIR.match(p.name) for p in type_dir.iterdir())
        return sorted(int(m.group(1)) for m in found if m)

    def put(
        self,
        artifact_type: str,
        files: dict[str, str | bytes],
        produced_by: str,
        inputs: list[ArtifactRef] | tuple[ArtifactRef, ...] = (),
        attempt: int = 1,
    ) -> ArtifactRef:
        if not files:
            raise ValueError("an artifact needs at least one file")
        encoded = {name: _encode(content) for name, content in files.items()}
        for name in encoded:
            _check_relative(name)
        file_hashes = {name: sha256_file_content(name, data) for name, data in encoded.items()}
        version_hash = sha256_json(file_hashes)

        existing = self.versions(artifact_type)
        version = (existing[-1] if existing else 0) + 1
        vdir = self._type_dir(artifact_type) / f"v{version}"
        vdir.mkdir(parents=True)
        manifest = {
            "type": artifact_type,
            "version": version,
            "produced_by": produced_by,
            "attempt": attempt,
            "created_at": utc_now(),
            "inputs": [ref.model_dump() for ref in inputs],
            "files": file_hashes,
            "hash": version_hash,
        }
        for name, data in encoded.items():
            target = vdir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            _make_read_only(target)
        manifest_path = vdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        _make_read_only(manifest_path)
        return ArtifactRef(type=artifact_type, version=version, hash=version_hash)

    def manifest(self, ref: ArtifactRef) -> dict:
        path = self.path(ref) / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def path(self, ref: ArtifactRef) -> Path:
        return self._type_dir(ref.type) / f"v{ref.version}"

    def read(self, ref: ArtifactRef, verify: bool = True) -> dict[str, str]:
        if verify:
            self.verify(ref)
        vdir = self.path(ref)
        names = self.manifest(ref)["files"]
        return {name: (vdir / name).read_text(encoding="utf-8") for name in names}

    def read_json(self, ref: ArtifactRef, name: str) -> dict:
        return json.loads(self.read(ref)[name])

    def latest(self, artifact_type: str) -> ArtifactRef | None:
        versions = self.versions(artifact_type)
        if not versions:
            return None
        manifest = json.loads(
            (self._type_dir(artifact_type) / f"v{versions[-1]}" / "manifest.json").read_text()
        )
        return ArtifactRef(type=artifact_type, version=versions[-1], hash=manifest["hash"])

    def verify(self, ref: ArtifactRef) -> None:
        """Raise IntegrityError unless files on disk match the manifest and the ref hash."""
        vdir = self.path(ref)
        if not (vdir / "manifest.json").is_file():
            raise IntegrityError(f"{ref}: version folder missing")
        manifest = self.manifest(ref)
        if manifest["hash"] != ref.hash:
            raise IntegrityError(f"{ref}: manifest hash {manifest['hash']} != reference")
        on_disk = {
            str(p.relative_to(vdir)) for p in vdir.rglob("*") if p.is_file()
        } - {"manifest.json"}
        if on_disk != set(manifest["files"]):
            raise IntegrityError(f"{ref}: file set changed on disk")
        for name, expected in manifest["files"].items():
            actual = sha256_file_content(name, (vdir / name).read_bytes())
            if actual != expected:
                raise IntegrityError(f"{ref}: {name} changed after it was written")
        if sha256_json(manifest["files"]) != ref.hash:
            raise IntegrityError(f"{ref}: version hash mismatch")


def _encode(content: str | bytes) -> bytes:
    return content.encode("utf-8") if isinstance(content, str) else content


def _check_relative(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or name == "manifest.json":
        raise ValueError(f"invalid artifact file name: {name!r}")


def _make_read_only(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
