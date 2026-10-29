"""RunContext: everything one run needs, wired together, plus a registry for graph nodes."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from orchestrator import __version__
from orchestrator.artifacts.approvals import Approvals
from orchestrator.artifacts.store import ArtifactStore
from orchestrator.config.models import Config
from orchestrator.human.gate import GateIO, HumanGate
from orchestrator.llm.client import LLMBackend, TracedLLM
from orchestrator.llm.costs import CostTracker
from orchestrator.observability.eventlog import EventLog


@dataclass
class RunContext:
    run_id: str
    run_dir: Path
    root: Path
    config: Config
    log: EventLog
    store: ArtifactStore
    approvals: Approvals
    gate: HumanGate
    costs: CostTracker
    llm: TracedLLM


_registry: dict[str, RunContext] = {}
_registry_lock = threading.Lock()


def new_run_id() -> str:
    return f"run-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def create_run(
    root: Path,
    config: Config,
    io: GateIO,
    backend: LLMBackend,
    run_id: str | None = None,
) -> RunContext:
    run_id = run_id or new_run_id()
    run_dir = root / "runs" / run_id
    log = EventLog(run_dir / "logs" / "events.jsonl")
    store = ArtifactStore(run_dir / "artifacts")
    policy = config.policy
    gate = HumanGate(io, log, config.app.approver_name, policy.gates.min_reason_chars)
    costs = CostTracker(
        config.pricing,
        policy.budgets.cost_usd_confirm,
        confirm=lambda question: gate.confirm("cost_ceiling", question),
    )
    llm = TracedLLM(
        backend,
        log,
        costs,
        models={
            "reasoning": config.app.model_reasoning,
            "coding": config.app.model_coding,
            "fallback": config.app.model_fallback,
        },
        schema_retries=policy.llm.schema_retries,
        max_tokens=policy.llm.max_tokens,
    )
    ctx = RunContext(
        run_id=run_id,
        run_dir=run_dir,
        root=root,
        config=config,
        log=log,
        store=store,
        approvals=Approvals(log, store),
        gate=gate,
        costs=costs,
        llm=llm,
    )
    log.append(
        "event",
        "run_started",
        run_id=run_id,
        orchestrator_version=__version__,
        governance_hashes=config.governance_hashes,
        models={"reasoning": config.app.model_reasoning, "coding": config.app.model_coding,
                "fallback": config.app.model_fallback},
        approver=config.app.approver_name,
    )
    register(ctx)
    return ctx


def register(ctx: RunContext) -> None:
    with _registry_lock:
        _registry[ctx.run_id] = ctx


def get_context(run_id: str) -> RunContext:
    with _registry_lock:
        try:
            return _registry[run_id]
        except KeyError:
            raise KeyError(f"no active run context for {run_id}") from None
