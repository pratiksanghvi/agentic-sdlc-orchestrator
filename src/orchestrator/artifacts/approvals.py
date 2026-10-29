"""Approvals bound to exact artifact versions and hashes (design foundation F2).

An approval is a decision record naming the gate, the artifact version and its hash. A stage
may only consume an input whose files still match that hash and which carries an approval.
"""

from __future__ import annotations

from typing import Literal

from orchestrator.artifacts.store import ArtifactRef, ArtifactStore, IntegrityError
from orchestrator.observability.eventlog import EventLog

Status = Literal["DRAFT", "APPROVED", "REJECTED", "SUPERSEDED"]


class GovernanceError(Exception):
    """A stage tried to consume an artifact that is unapproved or changed after approval."""


class Approvals:
    def __init__(self, log: EventLog, store: ArtifactStore) -> None:
        self.log = log
        self.store = store

    def set_status(self, ref: ArtifactRef, status: Status, by: str, reason: str = "") -> None:
        self.log.append(
            "event",
            "artifact_status",
            artifact=ref.model_dump(),
            status=status,
            by=by,
            reason=reason,
        )

    def status(self, ref: ArtifactRef) -> Status | None:
        current = None
        for rec in self.log.records("event"):
            if rec["name"] == "artifact_status" and rec["data"]["artifact"] == ref.model_dump():
                current = rec["data"]["status"]
        return current

    def approve(self, ref: ArtifactRef, gate: str, approver: str, comment: str = "") -> None:
        self.store.verify(ref)  # never approve content that is not what was written
        self.log.append(
            "decision",
            "approval",
            gate=gate,
            artifact=ref.model_dump(),
            decision="APPROVE",
            made_by=f"human:{approver}",
            rationale=comment,
        )
        self.set_status(ref, "APPROVED", by=f"human:{approver}", reason=comment)

    def reject(self, ref: ArtifactRef, gate: str, approver: str, reason: str) -> None:
        self.log.append(
            "decision",
            "approval",
            gate=gate,
            artifact=ref.model_dump(),
            decision="REJECT",
            made_by=f"human:{approver}",
            rationale=reason,
        )
        self.set_status(ref, "REJECTED", by=f"human:{approver}", reason=reason)

    def is_approved(self, ref: ArtifactRef) -> bool:
        return self.status(ref) == "APPROVED"

    def require_approved(self, *refs: ArtifactRef) -> None:
        """Stage entry check: each input is approved and its files still match the hash."""
        for ref in refs:
            if not self.is_approved(ref):
                raise GovernanceError(f"{ref} has no approval for this exact version")
            try:
                self.store.verify(ref)
            except IntegrityError as exc:
                raise GovernanceError(f"{ref} changed after approval: {exc}") from exc
