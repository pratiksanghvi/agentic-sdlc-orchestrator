"""Stage 7 — Documentation (no approval): facts → README + API docs → deterministic checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from orchestrator.contract import openapi
from orchestrator.execution.git_ops import ProductRepo
from orchestrator.guardrails.secrets import scan_files
from orchestrator.observability.node import observed_node
from orchestrator.runtime.context import get_context
from orchestrator.stages.common import StageIO, llm_step, prompt, ref_of, to_json

STAGE = "docs"


class Docs(BaseModel):
    readme_md: str
    api_md: str


class DocsState(StageIO, total=False):
    attempts: int
    feedback: str
    problems: list[str]


def _facts(ctx, state) -> dict:
    spec = ctx.store.read_json(ref_of(state, "spec"), "spec.json")
    stack_id = ctx.store.read_json(ref_of(state, "stack_adr"), "stack.json")["chosen_stack"]
    stack = ctx.config.stacks.stacks[stack_id]
    design = ctx.store.read(ref_of(state, "design"))
    contract = ctx.config.policy.contract
    return {
        "title": spec["title"],
        "functional_requirements": [f["statement"] for f in spec["functional_requirements"]],
        "non_functional_requirements": [f"{n['catalog_id']}: {n['statement']}"
                                        for n in spec["non_functional_requirements"]],
        "not_supported": [n["request"] for n in spec["not_supported"]],
        "stack": stack_id,
        "commands": {"build_and_test": " ".join(stack.commands.build_and_unit_test),
                     "run": " ".join(stack.commands.run)},
        "configuration": {contract.port_env: "HTTP port (required)",
                          "DB_PATH": "SQLite database file path (default app.db)"},
        "readiness_line": "SERVICE_READY port=<port>",
        "openapi": design["openapi.yaml"],
    }


def check_docs(docs: Docs, facts: dict) -> list[str]:
    problems = []
    for name, command in facts["commands"].items():
        if command not in docs.readme_md:
            problems.append(f"README.md must contain the exact {name} command `{command}`")
    ops = openapi.operations(openapi.load(facts["openapi"]))
    for op in ops:
        if op.path not in docs.api_md:
            problems.append(f"docs/API.md does not document {op.key}")
    known = {op.path for op in ops} | {"/metrics"}
    for path in set(re.findall(r"`(?:GET|POST|PUT|PATCH|DELETE) (/[^`\s]*)`", docs.api_md)):
        if path.split("?")[0] not in known:
            problems.append(f"docs/API.md documents {path}, which is not in the OpenAPI")
    for name, text in (("README.md", docs.readme_md), ("docs/API.md", docs.api_md)):
        if re.search(r"\b(TODO|TBD|FIXME)\b", text):
            problems.append(f"{name} contains a TODO/TBD placeholder")
    return problems


@observed_node(STAGE, "DC_generate")
def dc_generate(state: DocsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    facts = _facts(ctx, state)
    result = llm_step(ctx, stage=STAGE, node="DC_generate", purpose="docs.generate",
                      role="coding", effort="low", system="You write accurate technical docs.",
                      user=prompt(STAGE, "docs", facts=to_json(facts),
                                  feedback=state.get("feedback") or "none"),
                      schema=Docs)
    docs = result.value
    problems = check_docs(docs, facts)
    ws = Path(state["workspace"])
    (ws / "docs").mkdir(exist_ok=True)
    (ws / "README.md").write_text(docs.readme_md)
    (ws / "docs" / "API.md").write_text(docs.api_md)
    problems += [f"{f.file}:{f.line} looks like a secret" for f in
                 scan_files([ws / "README.md", ws / "docs" / "API.md"], base=ws)]
    ctx.log.append("event", "docs_checked", stage=STAGE, problems=problems)
    return {"problems": problems, "attempts": state.get("attempts", 0) + 1,
            "feedback": "\n".join(f"- {p}" for p in problems)}


@observed_node(STAGE, "DC_commit")
def dc_commit(state: DocsState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ws = Path(state["workspace"])
    ProductRepo(ws).commit_all(f"docs: README and API reference\n\nRun: {ctx.run_id}")
    ref = ctx.store.put("docs", {"README.md": (ws / "README.md").read_text(),
                                 "API.md": (ws / "docs" / "API.md").read_text(),
                                 "warnings.json": to_json(state.get("problems") or [])},
                        produced_by="DC")
    return {"artifacts": {"docs": ref.model_dump()}}


def build() -> StateGraph:
    g = StateGraph(DocsState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("DC_generate", dc_generate)
    g.add_node("DC_commit", dc_commit)
    g.add_edge(START, "DC_generate")
    g.add_conditional_edges(
        "DC_generate",
        lambda s: "DC_generate" if s["problems"] and s["attempts"] <= 2 else "DC_commit",
        ["DC_generate", "DC_commit"])
    g.add_edge("DC_commit", END)
    return g
