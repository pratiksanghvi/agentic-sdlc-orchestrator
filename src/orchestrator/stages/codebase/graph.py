"""Stage 0 (brownfield only) — codebase snapshot + impact analysis, approved by a human.

Runs only when the run targets an existing product repository. The approved analysis becomes an
input to Requirements and Design; the existing stack is detected and kept. Greenfield runs pass
straight through.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from orchestrator.execution.git_ops import ProductRepo
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

STAGE = "codebase"
MAX_FILES, MAX_BYTES = 100, 150_000
SNAPSHOT_SUFFIXES = (".java", ".py", ".go", ".sql", ".properties", ".yml", ".yaml", ".xml", ".md",
                     ".mod", ".toml", ".json")
STACK_MARKERS = {"pom.xml": "java21-springboot3-maven", "go.mod": "go122-chi",
                 "requirements.txt": "python312-fastapi", "pyproject.toml": "python312-fastapi"}


class Endpoint(BaseModel):
    endpoint: str
    purpose: str


class Item(BaseModel):
    name: str
    detail: str


class Flow(BaseModel):
    name: str
    steps: list[str]


class Impact(BaseModel):
    summary: str
    endpoints: list[Endpoint]
    modules: list[Item]
    tables: list[Item]
    data_flows: list[Flow]
    impacted: list[Item]
    compatibility_risks: list[str]


class CodebaseState(StageIO, total=False):
    feedback: str


def detect_stack(ws: Path) -> str | None:
    return next((sid for marker, sid in STACK_MARKERS.items() if (ws / marker).is_file()), None)


def snapshot(ws: Path) -> tuple[dict[str, str], list[str]]:
    files, skipped, used = {}, [], 0
    for p in sorted(ws.rglob("*")):
        rel = str(p.relative_to(ws))
        if not p.is_file() or ".git" in p.parts or "target" in p.parts or \
                p.suffix not in SNAPSHOT_SUFFIXES:
            continue
        text = p.read_text(errors="replace")
        if len(files) >= MAX_FILES or used + len(text) > MAX_BYTES:
            skipped.append(rel)
            continue
        files[rel] = text
        used += len(text)
    return files, skipped


def _brownfield(state) -> bool:
    return bool(state.get("workspace")) and state.get("mode") == "brownfield"


@observed_node(STAGE, "B0_snapshot")
def b0_snapshot(state: CodebaseState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ws = Path(state["workspace"])
    if not (ws / ".git").is_dir():
        return {"status": "failed", "status_reason": f"{ws} is not a git repository"}
    stack = detect_stack(ws)
    if stack is None or stack not in ctx.config.stacks.stacks:
        return {"status": "failed", "status_reason": f"no supported stack detected in {ws}"}
    files, skipped = snapshot(ws)
    if skipped:
        return {"status": "failed", "status_reason": (
            f"workspace exceeds the snapshot budget ({MAX_FILES} files / {MAX_BYTES} bytes); "
            f"{len(skipped)} files would be dropped — point the run at a focused repository")}
    repo = ProductRepo(ws)
    meta = {"stack": stack, "head": repo.head(), "branch": repo.git("rev-parse", "--abbrev-ref",
                                                                    "HEAD"),
            "files": sorted(files)}
    ref = ctx.store.put("codebase_snapshot", {**{f"files/{k}": v for k, v in files.items()},
                                              "snapshot.json": to_json(meta)},
                        produced_by="B0")
    ctx.log.append("event", "codebase_snapshot", stage=STAGE, stack=stack, files=len(files),
                   head=meta["head"], artifact=ref.model_dump())
    return {"artifacts": {"codebase_snapshot": ref.model_dump()}, "feedback": ""}


@observed_node(STAGE, "B1_impact")
def b1_impact(state: CodebaseState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    snap_ref = ref_of(state, "codebase_snapshot")
    files = ctx.store.read(snap_ref)
    meta = ctx.store.read_json(snap_ref, "snapshot.json")
    body = "\n\n".join(f"--- {k[6:]} ---\n{v}" for k, v in files.items() if k.startswith("files/"))
    request = state["requirement_text"]
    if state.get("feedback"):
        request += f"\n\n(Reviewer feedback on the previous analysis: {state['feedback']})"
    result = llm_step(ctx, stage=STAGE, node="B1_impact", purpose="codebase.impact",
                      system="You analyse existing codebases precisely.",
                      user=prompt(STAGE, "impact", request=request, stack=meta["stack"],
                                  snapshot=body),
                      schema=Impact, max_tokens=32000)
    impact = result.value.model_dump()
    md = ["# Existing system and change impact", "", impact["summary"], "", "## Endpoints", ""]
    md += [f"- `{e['endpoint']}` — {e['purpose']}" for e in impact["endpoints"]]
    md += ["", "## Impacted", ""] + [f"- **{i['name']}** — {i['detail']}"
                                     for i in impact["impacted"]]
    md += ["", "## Compatibility risks", ""] + [f"- {r}" for r in impact["compatibility_risks"]]
    ref = ctx.store.put("codebase_analysis", {"analysis.json": to_json({**impact, **meta}),
                                              "analysis.md": "\n".join(md) + "\n"},
                        produced_by="B1", inputs=[snap_ref])
    ctx.log.append("decision", "impact_analysis", made_by="agent:codebase-analyst",
                   basis=[result.call_id], artifact=ref.model_dump())
    return {"artifacts": {"codebase_analysis": ref.model_dump()}}


@observed_node(STAGE, "B2_gate")
def b2_gate(state: CodebaseState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ref = ref_of(state, "codebase_analysis")
    a = ctx.store.read_json(ref, "analysis.json")
    lines = [a["summary"], "", f"Stack (kept): {a['stack']}   HEAD: {a['head'][:8]}",
             "Endpoints: " + ", ".join(e["endpoint"] for e in a["endpoints"]), "",
             "Impacted:"] + [f"  - {i['name']}: {i['detail']}" for i in a["impacted"]]
    lines += ["", "Compatibility risks:"] + [f"  - {r}" for r in a["compatibility_risks"]]
    lines += ["", f"Full analysis: {ctx.store.path(ref) / 'analysis.md'}"]
    decision = ask_choice("impact_approval", f"Stage 0 Codebase · approve impact analysis ({ref})",
                          "\n".join(lines),
                          [option("a", "Approve"),
                           option("r", "Reject with feedback", needs_reason=True), END_RUN],
                          artifact=ref)
    approver = ctx.config.app.approver_name
    if decision["key"] == "a":
        ctx.approvals.approve(ref, gate="impact_approval", approver=approver)
        return {"feedback": ""}
    if decision["key"] == "r":
        ctx.approvals.reject(ref, gate="impact_approval", approver=approver,
                             reason=decision["reason"])
        return {"feedback": decision["reason"]}
    return {"status": "ended", "status_reason": decision["reason"]}


def build() -> StateGraph:
    g = StateGraph(CodebaseState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("B0_snapshot", b0_snapshot)
    g.add_node("B1_impact", b1_impact)
    g.add_node("B2_gate", b2_gate)
    g.add_conditional_edges(START, lambda s: "B0_snapshot" if _brownfield(s) else END,
                            ["B0_snapshot", END])
    g.add_conditional_edges("B0_snapshot", lambda s: END if s.get("status") == "failed"
                            else "B1_impact", ["B1_impact", END])
    g.add_edge("B1_impact", "B2_gate")
    g.add_conditional_edges("B2_gate", lambda s: "B1_impact" if s.get("feedback") else END,
                            ["B1_impact", END])
    return g
