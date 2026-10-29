"""Stage 3 — Test Design: approved spec + design → approved acceptance test plan (T1–T4).

T1 (NFR cases from catalog recipes, code) and T2 (functional cases, LLM) run in parallel and join
at T3 (deterministic validation). The plan is written from the approved contract only; product
code does not exist yet, which keeps tests independent of the implementation.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.contract import openapi
from orchestrator.observability.node import observed_node
from orchestrator.runtime.context import get_context
from orchestrator.stages.common import (
    END_RUN,
    StageIO,
    ask_choice,
    llm_step,
    option,
    prompt,
    ref_of,
    to_json,
)
from orchestrator.stages.test_design import rules
from orchestrator.stages.test_design.schemas import FunctionalCases, TestCase

STAGE = "test_design"
NFR_ID_BASE = 900  # NFR case ids (TC-900+) never collide with functional ids


class TestDesignState(StageIO, total=False):
    feedback: str
    attempts: int
    problems: list[str]
    nfr_case_data: list[dict]
    functional_case_data: list[dict]
    next_step: str


def _inputs(ctx, state):
    spec = ctx.store.read_json(ref_of(state, "spec"), "spec.json")
    design_files = ctx.store.read(ref_of(state, "design"))
    plan = ctx.store.read_json(ref_of(state, "nfr_plan"), "nfr_plan.json")["plan"]
    return spec, design_files, plan


@observed_node(STAGE, "T0_entry")
def t0_entry(state: TestDesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ctx.approvals.require_approved(*(ref_of(state, t) for t in ("spec", "stack_adr", "design")))
    return {"feedback": "", "attempts": 0}


@observed_node(STAGE, "T1_nfr_cases")
def t1_nfr_cases(state: TestDesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    _, design_files, plan = _inputs(ctx, state)
    cases = rules.nfr_cases(plan, openapi.load(design_files["openapi.yaml"]), NFR_ID_BASE)
    return {"nfr_case_data": [c.model_dump() for c in cases]}


@observed_node(STAGE, "T2_functional_cases")
def t2_functional_cases(state: TestDesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    spec, design_files, _ = _inputs(ctx, state)
    mvp = {f["id"] for f in spec["functional_requirements"] if f["priority"] == "MVP"}
    criteria = [a for a in spec["acceptance_criteria"] if a["requirement_id"] in mvp]
    result = llm_step(
        ctx, stage=STAGE, node="T2_functional_cases", purpose="test_design.cases",
        system=prompt(STAGE, "system"),
        user=prompt(STAGE, "cases", criteria=to_json(criteria),
                    openapi=design_files["openapi.yaml"], first_id=1, second_id=2,
                    feedback=state.get("feedback") or "none"),
        schema=FunctionalCases,
        max_tokens=32000,
    )
    ctx.log.append("decision", "test_cases_designed", made_by="agent:qa-test-designer",
                   basis=[result.call_id], count=len(result.value.cases))
    return {"functional_case_data": [c.model_dump() for c in result.value.cases]}


@observed_node(STAGE, "T3_validate")
def t3_validate(state: TestDesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    spec, design_files, plan = _inputs(ctx, state)
    cases = [TestCase(**c) for c in state["functional_case_data"] + state["nfr_case_data"]]
    problems = rules.validate_plan(cases, spec, plan, openapi.load(design_files["openapi.yaml"]))
    ref = ctx.store.put(
        "test_plan",
        {"test_plan.json": to_json([c.model_dump() for c in cases]),
         "test_plan.md": rules.plan_markdown(cases)},
        produced_by="T3", inputs=[ref_of(state, t) for t in ("spec", "design", "nfr_plan")],
        attempt=state.get("attempts", 0) + 1,
    )
    ctx.approvals.set_status(ref, "DRAFT", by="agent:qa-test-designer")
    ctx.log.append("event", "test_plan_validated", stage=STAGE, problems=problems)
    return {"artifacts": {"test_plan": ref.model_dump()}, "problems": problems,
            "attempts": state.get("attempts", 0) + 1}


def route_after_validation(state: TestDesignState) -> str:
    ctx = get_context(state["run_id"])
    if state["problems"] and state["attempts"] <= ctx.config.policy.budgets.step_retries:
        return "T3_retry"
    return "T4_gate"


def t3_retry(state: TestDesignState) -> dict[str, Any]:
    return {"feedback": "\n".join(f"- {p}" for p in state["problems"])}


@observed_node(STAGE, "T4_gate")
def t4_gate(state: TestDesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ref = ref_of(state, "test_plan")
    cases = [TestCase(**c) for c in ctx.store.read_json(ref, "test_plan.json")]
    problems = state.get("problems") or []
    by_cover: dict[str, list[TestCase]] = {}
    for c in cases:
        by_cover.setdefault(c.covers, []).append(c)
    lines = [f"{len(cases)} cases covering {len(by_cover)} criteria/NFRs "
             f"({sum(c.kind == 'nfr' for c in cases)} non-functional, from catalog recipes)", ""]
    for cover, group in sorted(by_cover.items()):
        lines.append(f"  {cover}: " + "; ".join(f"{c.id} [{c.kind}] {c.title}" for c in group))
    if problems:
        lines += ["", "[red]Validation problems (approve is unavailable until fixed):[/]"]
        lines += [f"  - {p}" for p in problems]
    lines += ["", f"Full plan: {ctx.store.path(ref) / 'test_plan.md'}"]
    options = [] if problems else [option("a", "Approve")]
    options += [option("r", "Reject with feedback", needs_reason=True), END_RUN]
    decision = ask_choice("test_plan_approval", f"Stage 3 Test Design · approve {ref}",
                          "\n".join(lines), options, artifact=ref)
    approver = ctx.config.app.approver_name
    if decision["key"] == "a":
        ctx.approvals.approve(ref, gate="test_plan_approval", approver=approver)
        return {"next_step": "done"}
    if decision["key"] == "x":
        ctx.log.append("decision", "run_ended", gate="test_plan_approval",
                       made_by=f"human:{approver}", rationale=decision["reason"])
        return {"status": "ended", "status_reason": decision["reason"], "next_step": "done"}
    ctx.approvals.reject(ref, gate="test_plan_approval", approver=approver,
                         reason=decision["reason"])
    return {"feedback": f"- Human reviewer: {decision['reason']}", "attempts": 0,
            "next_step": "T_redo"}


def t_redo(state: TestDesignState) -> dict[str, Any]:
    """Fan out to both branches again so the T1+T2 join fires on every attempt."""
    return {}


def build() -> StateGraph:
    g = StateGraph(TestDesignState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("T0_entry", t0_entry)
    g.add_node("T1_nfr_cases", t1_nfr_cases)
    g.add_node("T2_functional_cases", t2_functional_cases)
    g.add_node("T3_validate", t3_validate)
    g.add_node("T3_retry", t3_retry)
    g.add_node("T4_gate", t4_gate)
    g.add_node("T_redo", t_redo)
    g.add_edge(START, "T0_entry")
    g.add_edge("T0_entry", "T_redo")
    g.add_edge("T_redo", "T1_nfr_cases")       # parallel fan-out ...
    g.add_edge("T_redo", "T2_functional_cases")
    g.add_edge(["T1_nfr_cases", "T2_functional_cases"], "T3_validate")  # ... joined here
    g.add_conditional_edges("T3_validate", route_after_validation, ["T3_retry", "T4_gate"])
    g.add_edge("T3_retry", "T_redo")
    g.add_conditional_edges("T4_gate", lambda s: END if s["next_step"] == "done" else
                            s["next_step"], ["T_redo", END])
    return g
