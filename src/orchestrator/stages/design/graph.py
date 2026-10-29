"""Stage 2 — Design: approved spec → approved stack (ADR-001) → approved design (D1–D6)."""

from __future__ import annotations

import json
from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.observability.node import observed_node
from orchestrator.runtime.context import get_context
from orchestrator.stages.common import (
    END_RUN,
    StageIO,
    ask_choice,
    existing_system,
    llm_step,
    option,
    prompt,
    ref_of,
    to_json,
)
from orchestrator.stages.design import rules
from orchestrator.stages.design.schemas import Design, StackDecision

STAGE = "design"


class DesignState(StageIO, total=False):
    stack_feedback: str
    design_feedback: str
    design_attempts: int
    problems: list[str]
    next_step: str


def _existing_stack(ctx, state) -> str | None:
    if "codebase_analysis" not in state.get("artifacts", {}):
        return None
    return ctx.store.read_json(ref_of(state, "codebase_analysis"), "analysis.json")["stack"]


def _spec(ctx, state) -> dict:
    return ctx.store.read_json(ref_of(state, "spec"), "spec.json")


def _stacks_text(ctx, spec) -> str:
    missing = rules.stacks_for_spec(ctx.config, spec)
    lines = []
    for sid, stack in ctx.config.stacks.stacks.items():
        note = f" — cannot be used: no implementation for {missing[sid]}" if missing[sid] else ""
        status = "VALIDATED end-to-end" if stack.validated else "not yet validated end-to-end"
        lines.append(f"- {sid}: language {stack.language}, datastore {stack.datastore}, "
                     f"{status}{note}")
    return "\n".join(lines)


@observed_node(STAGE, "D1_entry")
def d1_entry(state: DesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ctx.approvals.require_approved(ref_of(state, "spec"))
    return {"stack_feedback": "", "design_feedback": "", "design_attempts": 0}


@observed_node(STAGE, "D2_stack")
def d2_stack(state: DesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    spec = _spec(ctx, state)
    result = llm_step(
        ctx, stage=STAGE, node="D2_stack", purpose="design.stack",
        system=prompt(STAGE, "system"),
        user=prompt(STAGE, "stack", existing=existing_system(ctx, state), spec=to_json(spec),
                    stacks=_stacks_text(ctx, spec),
                    feedback=state.get("stack_feedback") or "none"),
        schema=StackDecision,
        validate=lambda d: rules.validate_stack(d, ctx.config, spec, _existing_stack(ctx, state)),
    )
    decision = result.value.model_dump()
    chosen = decision["recommended_stack_id"]
    ref = ctx.store.put(
        "stack_adr",
        {"stack.json": to_json({"decision": decision, "chosen_stack": chosen}),
         "adr-001-stack.md": rules.adr_markdown(decision, chosen)},
        produced_by="D2", inputs=[ref_of(state, "spec")],
    )
    ctx.log.append("decision", "stack_proposed", made_by="agent:solution-architect",
                   basis=[result.call_id], artifact=ref.model_dump(), stack=chosen)
    return {"artifacts": {"stack_adr": ref.model_dump()}}


@observed_node(STAGE, "stack_gate")
def stack_gate(state: DesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ref = ref_of(state, "stack_adr")
    data = ctx.store.read_json(ref, "stack.json")
    chosen = data["chosen_stack"]
    missing = rules.stacks_for_spec(ctx.config, _spec(ctx, state))
    alternatives = [sid for sid in ctx.config.stacks.stacks if sid != chosen and not missing[sid]
                    and _existing_stack(ctx, state) is None]  # brownfield keeps its stack
    def _label(sid: str) -> str:
        return "" if ctx.config.stacks.stacks[sid].validated else " (not validated end-to-end)"

    options = [option("a", f"Approve {chosen}{_label(chosen)}")]
    for i, sid in enumerate(alternatives, 1):
        options.append(option(str(i), f"Use {sid} instead{_label(sid)}", needs_reason=True))
    options += [option("r", "Reject with feedback", needs_reason=True), END_RUN]
    rec = data["decision"]
    summary = "\n".join([
        f"Recommended: [bold]{chosen}[/]",
        f"Rationale: {rec['rationale']}",
        "Options considered: " + "; ".join(
            f"{o['name']} ({o['stack_id'] or 'unsupported'})" for o in rec["options"]),
        f"ADR: {ctx.store.path(ref) / 'adr-001-stack.md'}",
    ])
    decision = ask_choice("stack_approval", f"Stage 2 Design · approve stack ({ref})", summary,
                          options, artifact=ref)
    approver = ctx.config.app.approver_name
    key = decision["key"]
    if key == "x":
        ctx.log.append("decision", "run_ended", gate="stack_approval",
                       made_by=f"human:{approver}", rationale=decision["reason"])
        return {"status": "ended", "status_reason": decision["reason"]}
    if key == "r":
        ctx.approvals.reject(ref, gate="stack_approval", approver=approver,
                             reason=decision["reason"])
        return {"stack_feedback": decision["reason"], "next_step": "D2_stack"}
    if key != "a":  # human picked another supported stack: record it as a new ADR version
        override = alternatives[int(key) - 1]
        ctx.approvals.set_status(ref, "SUPERSEDED", by=f"human:{approver}",
                                 reason=f"override to {override}")
        ref = ctx.store.put(
            "stack_adr",
            {"stack.json": to_json({"decision": rec, "chosen_stack": override,
                                    "override_reason": decision["reason"]}),
             "adr-001-stack.md": rules.adr_markdown(rec, override, decision["reason"])},
            produced_by="human", inputs=[ref_of(state, "spec")],
        )
    ctx.approvals.approve(ref, gate="stack_approval", approver=approver,
                          comment=decision["reason"])
    return {"artifacts": {"stack_adr": ref.model_dump()}, "next_step": "D3_nfr_lookup"}


@observed_node(STAGE, "D3_nfr_lookup")
def d3_nfr_lookup(state: DesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    stack_ref = ref_of(state, "stack_adr")
    ctx.approvals.require_approved(ref_of(state, "spec"), stack_ref)
    stack_id = ctx.store.read_json(stack_ref, "stack.json")["chosen_stack"]
    plan = rules.nfr_plan(ctx.config, _spec(ctx, state), stack_id)
    ref = ctx.store.put("nfr_plan", {"nfr_plan.json": to_json({"stack": stack_id, "plan": plan})},
                        produced_by="D3", inputs=[ref_of(state, "spec"), stack_ref])
    return {"artifacts": {"nfr_plan": ref.model_dump()}}


@observed_node(STAGE, "D4_architecture")
def d4_architecture(state: DesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    spec = _spec(ctx, state)
    stack_ref, plan_ref = ref_of(state, "stack_adr"), ref_of(state, "nfr_plan")
    stack_id = ctx.store.read_json(stack_ref, "stack.json")["chosen_stack"]
    plan = ctx.store.read_json(plan_ref, "nfr_plan.json")["plan"]
    stack = ctx.config.stacks.stacks[stack_id]
    allowed = set(stack.dependencies)
    result = llm_step(
        ctx, stage=STAGE, node="D4_architecture", purpose="design.architecture",
        system=prompt(STAGE, "system"),
        user=prompt(STAGE, "architecture", existing=existing_system(ctx, state), spec=to_json(spec),
                    stack=f"{stack_id} (language {stack.language}, datastore {stack.datastore})",
                    nfr_plan=to_json(plan), dependencies="\n".join(sorted(allowed)),
                    feedback=state.get("design_feedback") or "none"),
        schema=Design,
        max_tokens=32000,
    )
    design = result.value.model_dump()
    files = {
        "openapi.yaml": design["openapi_yaml"],
        "schema.sql": design["schema_sql"],
        "design.json": to_json({k: v for k, v in design.items()
                                if k not in ("openapi_yaml", "schema_sql")}),
        "design.md": rules.design_markdown(design, stack_id, plan),
        "traceability.json": to_json(design["traceability"]),
    }
    ref = ctx.store.put("design", files, produced_by="D4",
                        inputs=[ref_of(state, "spec"), stack_ref, plan_ref],
                        attempt=state.get("design_attempts", 0) + 1)
    ctx.approvals.set_status(ref, "DRAFT", by="agent:solution-architect")
    ctx.log.append("decision", "design_drafted", made_by="agent:solution-architect",
                   basis=[result.call_id], artifact=ref.model_dump())
    problems = rules.validate_design(result.value, spec, plan, allowed)
    ctx.log.append("event", "design_validated", stage=STAGE, problems=problems)
    return {"artifacts": {"design": ref.model_dump()}, "problems": problems,
            "design_attempts": state.get("design_attempts", 0) + 1}


def route_after_architecture(state: DesignState) -> str:
    ctx = get_context(state["run_id"])
    if state["problems"] and state["design_attempts"] <= ctx.config.policy.budgets.step_retries:
        return "D5_retry"
    return "D6_gate"


def d5_retry(state: DesignState) -> dict[str, Any]:
    return {"design_feedback": "\n".join(f"- {p}" for p in state["problems"])}


@observed_node(STAGE, "D6_gate")
def d6_gate(state: DesignState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ref = ref_of(state, "design")
    files = ctx.store.read(ref)
    design = json.loads(files["design.json"])
    problems = state.get("problems") or []
    ops, _ = rules.openapi_operations(files["openapi.yaml"])
    lines = [f"Modules: {', '.join(m['name'] for m in design['modules'])}",
             f"Endpoints ({len(ops)}):"] + [f"  {op}" for op in sorted(ops)]
    tables = rules.table_names(files["schema.sql"])
    lines += [f"Tables: {', '.join(tables)}", f"Dependencies: {', '.join(design['dependencies'])}"]
    if problems:
        lines += ["", "[red]Validation problems (approve is unavailable until fixed):[/]"]
        lines += [f"  - {p}" for p in problems]
    lines += ["", f"Full design: {ctx.store.path(ref)}"]
    options = [] if problems else [option("a", "Approve")]
    options += [option("r", "Reject with feedback", needs_reason=True),
                option("k", "Change the stack decision", needs_reason=True), END_RUN]
    decision = ask_choice("design_approval", f"Stage 2 Design · approve {ref}", "\n".join(lines),
                          options, artifact=ref)
    approver = ctx.config.app.approver_name
    key = decision["key"]
    if key == "a":
        ctx.approvals.approve(ref, gate="design_approval", approver=approver)
        return {"next_step": "done"}
    if key == "x":
        ctx.log.append("decision", "run_ended", gate="design_approval",
                       made_by=f"human:{approver}", rationale=decision["reason"])
        return {"status": "ended", "status_reason": decision["reason"], "next_step": "done"}
    ctx.approvals.reject(ref, gate="design_approval", approver=approver,
                         reason=decision["reason"])
    if key == "k":
        return {"stack_feedback": decision["reason"], "design_feedback": "",
                "design_attempts": 0, "next_step": "D2_stack"}
    return {"design_feedback": f"- Human reviewer: {decision['reason']}", "design_attempts": 0,
            "next_step": "D4_architecture"}


def _after_stack_gate(state: DesignState) -> str:
    return END if state.get("status") == "ended" else state["next_step"]


def _after_design_gate(state: DesignState) -> str:
    return END if state["next_step"] == "done" else state["next_step"]


def build() -> StateGraph:
    g = StateGraph(DesignState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("D1_entry", d1_entry)
    g.add_node("D2_stack", d2_stack)
    g.add_node("stack_gate", stack_gate)
    g.add_node("D3_nfr_lookup", d3_nfr_lookup)
    g.add_node("D4_architecture", d4_architecture)
    g.add_node("D5_retry", d5_retry)
    g.add_node("D6_gate", d6_gate)
    g.add_edge(START, "D1_entry")
    g.add_edge("D1_entry", "D2_stack")
    g.add_edge("D2_stack", "stack_gate")
    g.add_conditional_edges("stack_gate", _after_stack_gate, ["D2_stack", "D3_nfr_lookup", END])
    g.add_edge("D3_nfr_lookup", "D4_architecture")
    g.add_conditional_edges("D4_architecture", route_after_architecture, ["D5_retry", "D6_gate"])
    g.add_edge("D5_retry", "D4_architecture")
    g.add_conditional_edges("D6_gate", _after_design_gate, ["D2_stack", "D4_architecture", END])
    return g
