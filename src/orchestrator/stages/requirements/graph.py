"""Stage 1 — Requirements: raw requirement → approved spec (R1–R6)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.guardrails.intake import check_requirement
from orchestrator.observability.node import observed_node
from orchestrator.runtime.context import get_context
from orchestrator.stages.common import (
    END_RUN,
    StageIO,
    ask_choice,
    ask_questions,
    existing_system,
    llm_step,
    option,
    prompt,
    ref_of,
    to_json,
)
from orchestrator.stages.requirements import rules
from orchestrator.stages.requirements.render import gate_summary, requirements_markdown
from orchestrator.stages.requirements.schemas import Analysis, SpecDraft

STAGE = "requirements"


class RequirementsState(StageIO, total=False):
    clarifications: list[dict]   # {id, question, answer}
    clarification_rounds: int
    feedback: str
    validation_attempts: int
    problems: list[str]


def _system(ctx) -> str:
    catalog = "\n".join(
        f"    {nfr_id} ({e.category}): {e.capability} Params: "
        f"{', '.join(e.params) or 'none'}"
        for nfr_id, e in ctx.config.nfr.entries.items()
    )
    return prompt(STAGE, "system", catalog=catalog)


def _clarifications_text(state) -> str:
    items = state.get("clarifications") or []
    return "\n".join(f"{c['id']}: {c['question']} → {c['answer']}" for c in items) or "none"


@observed_node(STAGE, "R1_intake")
def r1_intake(state: RequirementsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    text = state["requirement_text"]
    problems = check_requirement(text, ctx.config.policy.input.max_bytes)
    if problems:
        ctx.log.append("event", "input_rejected", stage=STAGE, problems=problems)
        return {"status": "failed", "status_reason": "requirement rejected: " + "; ".join(problems)}
    ref = ctx.store.put("requirement_input", {"requirement.txt": text}, produced_by="R1")
    return {
        "artifacts": {"requirement_input": ref.model_dump()},
        "status": "running",
        "clarifications": [],
        "clarification_rounds": 0,
        "feedback": "",
        "validation_attempts": 0,
    }


@observed_node(STAGE, "R2_analyze")
def r2_analyze(state: RequirementsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    result = llm_step(
        ctx, stage=STAGE, node="R2_analyze", purpose="requirements.analyze",
        system=_system(ctx),
        user=prompt(STAGE, "analyze", requirement=state["requirement_text"],
                    existing=existing_system(ctx, state),
                    clarifications=_clarifications_text(state)),
        schema=Analysis,
        validate=lambda a: rules.validate_analysis(a, ctx.config.nfr),
    )
    ref = ctx.store.put(
        "analysis", {"analysis.json": result.value.model_dump_json(indent=2)}, produced_by="R2",
        inputs=[ref_of(state, "requirement_input")],
    )
    ctx.log.append("decision", "requirements_analyzed", made_by="agent:requirements-analyst",
                   basis=[result.call_id], artifact=ref.model_dump(),
                   blocking=[a.id for a in result.value.ambiguities if a.severity == "BLOCKING"])
    return {"artifacts": {"analysis": ref.model_dump()}}


def _open_blocking(ctx, state) -> list[dict]:
    analysis = ctx.store.read_json(ref_of(state, "analysis"), "analysis.json")
    answered = {c["question"] for c in state.get("clarifications") or []}
    return [a for a in analysis["ambiguities"]
            if a["severity"] == "BLOCKING" and a["question"] not in answered]


def route_after_analysis(state: RequirementsState) -> str:
    ctx = get_context(state["run_id"])
    rounds = state.get("clarification_rounds", 0)
    if _open_blocking(ctx, state) and rounds < ctx.config.policy.budgets.clarification_rounds:
        return "R3_clarify"
    return "R4_normalize"


@observed_node(STAGE, "R3_clarify")
def r3_clarify(state: RequirementsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    blocking = _open_blocking(ctx, state)
    answers = ask_questions(
        "clarify",
        "Clarification needed — blocking questions",
        [{"id": a["id"], "question": a["question"], "why": a["why_it_matters"],
          "options": a["options"], "default": a["recommended_default"]} for a in blocking],
    )
    clarifications = list(state.get("clarifications") or [])
    for ambiguity, answer in zip(blocking, answers, strict=True):
        clarifications.append({"id": f"C-{len(clarifications) + 1}",
                               "question": ambiguity["question"], "answer": answer["answer"]})
    ref = ctx.store.put("clarifications", {"clarifications.json": to_json(clarifications)},
                        produced_by="R3", inputs=[ref_of(state, "analysis")])
    return {
        "clarifications": clarifications,
        "clarification_rounds": state.get("clarification_rounds", 0) + 1,
        "artifacts": {"clarifications": ref.model_dump()},
    }


@observed_node(STAGE, "R4_normalize")
def r4_normalize(state: RequirementsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    analysis_ref = ref_of(state, "analysis")
    analysis = ctx.store.read_json(analysis_ref, "analysis.json")
    result = llm_step(
        ctx, stage=STAGE, node="R4_normalize", purpose="requirements.normalize",
        system=_system(ctx),
        user=prompt(STAGE, "normalize", requirement=state["requirement_text"],
                    existing=existing_system(ctx, state),
                    clarifications=_clarifications_text(state), analysis=to_json(analysis),
                    feedback=state.get("feedback") or "none"),
        schema=SpecDraft,
    )
    spec = result.value.model_dump()
    spec["not_supported"] = [
        {"request": a["text"], "category": a["category"], "classification": a["classification"],
         "message": rules.not_supported_message(a["text"], a["category"], a["classification"])}
        for a in analysis["nfr_asks"] if a["classification"] in ("NOT_IN_CATALOG",
                                                                  "UNSUPPORTED_CATEGORY")
    ]
    spec["constraints"] = ([f"Technology required by the user: {analysis['stack_constraint']}"]
                           if analysis.get("stack_constraint") else [])
    spec["clarifications"] = state.get("clarifications") or []
    inputs = [analysis_ref, ref_of(state, "requirement_input")]
    if "clarifications" in state.get("artifacts", {}):
        inputs.append(ref_of(state, "clarifications"))
    ref = ctx.store.put(
        "spec", {"spec.json": to_json(spec), "requirements.md": requirements_markdown(spec)},
        produced_by="R4", inputs=inputs, attempt=state.get("validation_attempts", 0) + 1,
    )
    ctx.approvals.set_status(ref, "DRAFT", by="agent:requirements-analyst")
    ctx.log.append("decision", "spec_drafted", made_by="agent:requirements-analyst",
                   basis=[result.call_id], artifact=ref.model_dump())
    return {"artifacts": {"spec": ref.model_dump()}}


@observed_node(STAGE, "R5_validate")
def r5_validate(state: RequirementsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    spec = ctx.store.read_json(ref_of(state, "spec"), "spec.json")
    sources = [state["requirement_text"]] + [c["answer"] for c in spec["clarifications"]]
    problems = rules.validate_spec(spec, ctx.config.nfr, sources)
    ctx.log.append("event", "spec_validated", stage=STAGE, problems=problems)
    return {"problems": problems, "validation_attempts": state.get("validation_attempts", 0) + 1}


def route_after_validation(state: RequirementsState) -> str:
    ctx = get_context(state["run_id"])
    if state["problems"] and state["validation_attempts"] <= ctx.config.policy.budgets.step_retries:
        return "R5_retry"
    return "R6_gate"


def r5_retry(state: RequirementsState) -> dict[str, Any]:
    return {"feedback": "\n".join(f"- {p}" for p in state["problems"])}


@observed_node(STAGE, "R6_gate")
def r6_gate(state: RequirementsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ref = ref_of(state, "spec")
    spec = ctx.store.read_json(ref, "spec.json")
    problems = state.get("problems") or []
    options = []
    if not problems:  # approve is hidden while validation problems remain
        options.append(option("a", "Approve"))
    options += [option("r", "Reject with feedback", needs_reason=True), END_RUN]
    decision = ask_choice(
        "spec_approval", f"Stage 1 Requirements · approve {ref}",
        gate_summary(spec, problems, str(ctx.store.path(ref) / "requirements.md")),
        options, artifact=ref,
    )
    approver = ctx.config.app.approver_name
    if decision["key"] == "a":
        ctx.approvals.approve(ref, gate="spec_approval", approver=approver)
        return {"status": "running", "problems": []}
    if decision["key"] == "r":
        ctx.approvals.reject(ref, gate="spec_approval", approver=approver,
                             reason=decision["reason"])
        return {"feedback": f"- Human reviewer: {decision['reason']}", "validation_attempts": 0}
    ctx.log.append("decision", "run_ended", gate="spec_approval", made_by=f"human:{approver}",
                   rationale=decision["reason"])
    return {"status": "ended", "status_reason": decision["reason"]}


def route_after_gate(state: RequirementsState) -> str:
    if state.get("status") == "ended":
        return END
    ctx = get_context(state["run_id"])
    return END if ctx.approvals.is_approved(ref_of(state, "spec")) else "R4_normalize"


def route_after_intake(state: RequirementsState) -> str:
    return END if state.get("status") == "failed" else "R2_analyze"


def build() -> StateGraph:
    g = StateGraph(RequirementsState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("R1_intake", r1_intake)
    g.add_node("R2_analyze", r2_analyze)
    g.add_node("R3_clarify", r3_clarify)
    g.add_node("R4_normalize", r4_normalize)
    g.add_node("R5_validate", r5_validate)
    g.add_node("R5_retry", r5_retry)
    g.add_node("R6_gate", r6_gate)
    g.add_edge(START, "R1_intake")
    g.add_conditional_edges("R1_intake", route_after_intake, ["R2_analyze", END])
    g.add_conditional_edges("R2_analyze", route_after_analysis, ["R3_clarify", "R4_normalize"])
    g.add_edge("R3_clarify", "R2_analyze")
    g.add_edge("R4_normalize", "R5_validate")
    g.add_conditional_edges("R5_validate", route_after_validation, ["R5_retry", "R6_gate"])
    g.add_edge("R5_retry", "R4_normalize")
    g.add_conditional_edges("R6_gate", route_after_gate, ["R4_normalize", END])
    return g
