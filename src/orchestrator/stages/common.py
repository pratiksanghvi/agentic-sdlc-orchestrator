"""Shared building blocks for stage subgraphs (design foundation F3).

Each stage is a LangGraph subgraph whose input/output schemas are the shared `StageIO` keys; its
own working keys stay inside the subgraph. Stages read inputs only as approved artifact
references and write only their own artifacts.
"""

from __future__ import annotations

import json
from importlib import resources
from string import Template
from typing import Annotated, Any, TypedDict

from langgraph.types import interrupt

from orchestrator.artifacts.store import ArtifactRef
from orchestrator.llm.client import LLMError, Role, Structured, T
from orchestrator.runtime.context import RunContext


def merge_dicts(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class StageIO(TypedDict, total=False):
    run_id: str
    requirement_text: str
    # artifact type -> current ArtifactRef (as dict); merged so parallel stages can both write
    artifacts: Annotated[dict[str, dict], merge_dicts]
    status: str  # running | ended | failed | completed
    status_reason: str


def ref_of(state: dict, artifact_type: str) -> ArtifactRef:
    return ArtifactRef(**state["artifacts"][artifact_type])


def prompt(stage: str, name: str, **values: Any) -> str:
    text = resources.files(f"orchestrator.stages.{stage}").joinpath(f"prompts/{name}.md")
    return Template(text.read_text(encoding="utf-8")).substitute(values)


def to_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def llm_step(
    ctx: RunContext,
    *,
    stage: str,
    node: str,
    purpose: str,
    system: str,
    user: str,
    schema: type[T],
    role: Role = "reasoning",
    effort: str = "high",
    validate=None,
    max_tokens: int | None = None,
) -> Structured[T]:
    """Step-level retries on top of the client's schema retries, then the fallback model."""
    budgets = ctx.config.policy.budgets
    roles: list[Role] = [role] * (budgets.step_retries + 1)
    if ctx.config.app.model_fallback != ctx.llm.models[role]:
        roles += ["fallback"] * budgets.stronger_model_attempts
    last: Exception | None = None
    for attempt_role in roles:
        try:
            return ctx.llm.structured(
                stage=stage, node=node, purpose=purpose, system=system, user=user,
                schema=schema, role=attempt_role, effort=effort, validate=validate,
                max_tokens=max_tokens,
            )
        except LLMError as exc:
            last = exc
            ctx.log.append("event", "step_retry", stage=stage, node=node, error=str(exc))
    raise LLMError(f"{stage}/{node}: exhausted step retries: {last}")


# ---------- human gate requests (rendered and logged by the driver via HumanGate) ----------


def option(key: str, label: str, needs_reason: bool = False, confirm: str | None = None) -> dict:
    return {"key": key, "label": label, "needs_reason": needs_reason, "confirm": confirm}


END_RUN = option("x", "End run", needs_reason=True, confirm="End this run? It cannot be resumed.")


def ask_choice(gate: str, title: str, summary: str, options: list[dict],
               artifact: ArtifactRef | None = None) -> dict:
    """Pause the graph for a human decision. Returns {"key": ..., "reason": ...}."""
    return interrupt({
        "kind": "choose",
        "gate": gate,
        "title": title,
        "summary": summary,
        "options": options,
        "artifact": artifact.model_dump() if artifact else None,
    })


def ask_questions(gate: str, title: str, questions: list[dict]) -> list[dict]:
    """Pause for answers. Each question: {id, question, options, default}. Returns answers."""
    return interrupt({"kind": "questions", "gate": gate, "title": title, "questions": questions})


def ask_confirm(gate: str, question: str) -> bool:
    return interrupt({"kind": "confirm", "gate": gate, "question": question})
