"""Stage 6 — Policy & Security report (awareness only; fixing findings is not in the MVP).

S1 secrets (detect-secrets) ‖ S4 change control (approvals still match their hashes, every
product commit traces to this run, paths and dependencies within policy, frozen suite intact)
→ joined report shown to the human; the run then continues automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.artifacts.approvals import GovernanceError
from orchestrator.execution.git_ops import ProductRepo
from orchestrator.guardrails import code as code_guard
from orchestrator.guardrails.secrets import scan_files
from orchestrator.observability.node import observed_node
from orchestrator.runtime.context import get_context
from orchestrator.stages.common import StageIO, ref_of, show_notice, to_json

STAGE = "security"


class SecurityState(StageIO, total=False):
    secret_findings: list[dict]
    change_findings: list[dict]


@observed_node(STAGE, "S1_secrets")
def s1_secrets(state: SecurityState) -> dict[str, Any]:
    ws = Path(state["workspace"])
    files = [p for p in ws.rglob("*") if p.is_file() and ".git" not in p.parts
             and "target" not in p.parts]
    findings = [{"check": "S1", "severity": "HIGH", "file": f.file, "line": f.line,
                 "message": f"possible secret ({f.type})"} for f in scan_files(files, base=ws)]
    return {"secret_findings": findings}


@observed_node(STAGE, "S4_change_control")
def s4_change_control(state: SecurityState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    findings: list[dict] = []

    def add(message: str, severity: str = "HIGH") -> None:
        findings.append({"check": "S4", "severity": severity, "message": message})

    for t in ("spec", "stack_adr", "design", "test_plan", "acceptance_suite"):
        try:
            ctx.approvals.require_approved(ref_of(state, t))
        except (GovernanceError, KeyError) as exc:
            add(f"{t}: {exc}")
    repo = ProductRepo(Path(state["workspace"]))
    commits = repo.git("log", "--format=%H%x1f%B%x1e", f"master..run/{ctx.run_id}").split("\x1e")
    for entry in filter(None, (c.strip() for c in commits)):
        sha, _, body = entry.partition("\x1f")
        if f"Run: {ctx.run_id}" not in body:
            add(f"commit {sha[:8]} does not reference run {ctx.run_id}")
    stack_id = ctx.store.read_json(ref_of(state, "stack_adr"), "stack.json")["chosen_stack"]
    stack = ctx.config.stacks.stacks[stack_id]
    changed = [p for p in repo.git("diff", "--name-only", f"master...run/{ctx.run_id}")
               .splitlines() if p and p != ".gitignore"]
    for problem in code_guard.check_paths(changed, stack, ctx.config.policy.paths.forbidden):
        add(problem)
    pom = Path(state["workspace"]) / "pom.xml"
    if pom.is_file():
        for problem in code_guard.check_maven_dependencies(pom.read_text(), stack):
            add(problem)
    return {"change_findings": findings}


@observed_node(STAGE, "S5_report")
def s5_report(state: SecurityState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    findings = state["secret_findings"] + state["change_findings"]
    report = {"findings": findings, "checks": {
        "S1_secrets": "detect-secrets", "S4_change_control": "orchestrator",
        "S2_sast": "not in MVP (Semgrep cut for the deadline)",
        "S3_dependency_cves": "not in MVP (needs a separately installed scanner)"}}
    lines = ["# Security & policy report", "", f"Findings: {len(findings)}", ""]
    lines += [f"- [{f['severity']}] {f['check']} {f.get('file', '')}"
              f"{':' + str(f['line']) if f.get('line') else ''} {f['message']}"
              for f in findings] or ["- none"]
    lines += ["", "Checks not run in the MVP: S2 SAST (Semgrep), S3 dependency CVEs."]
    ref = ctx.store.put("security_report", {"security_report.json": to_json(report),
                                            "security_report.md": "\n".join(lines) + "\n"},
                        produced_by="S5")
    ctx.log.append("event", "security_report", stage=STAGE, findings=len(findings),
                   artifact=ref.model_dump())
    body = "\n".join(lines[2:]) + "\n\nThis report is for awareness; the run continues."
    show_notice("security_report", f"Stage 6 Security · {len(findings)} finding(s)", body)
    return {"artifacts": {"security_report": ref.model_dump()}}


def build() -> StateGraph:
    g = StateGraph(SecurityState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("S1_secrets", s1_secrets)
    g.add_node("S4_change_control", s4_change_control)
    g.add_node("S5_report", s5_report)
    g.add_edge(START, "S1_secrets")
    g.add_edge(START, "S4_change_control")
    g.add_edge(["S1_secrets", "S4_change_control"], "S5_report")
    g.add_edge("S5_report", END)
    return g
