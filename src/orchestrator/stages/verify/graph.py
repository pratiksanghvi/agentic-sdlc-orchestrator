"""Stage 5 — Build & Verify: does the generated service actually work?

V2 build + unit tests → V3 start (SERVICE_READY) → V4 approved acceptance tests (main phase,
then isolated phase after a restart). Any failure skips the later checks, then the fix agent gets
up to `verify_auto_fixes` attempts (shared across build, unit, startup and acceptance). After
that the human gets the test status and may give unlimited hints (one fix + one verify each) or
end the run (with the opted-in rollback).
"""

from __future__ import annotations

import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.execution import runner
from orchestrator.execution.git_ops import ProductRepo
from orchestrator.execution.service import ServiceProcess
from orchestrator.guardrails import code as code_guard
from orchestrator.observability.node import observed_node
from orchestrator.runtime.context import get_context
from orchestrator.stages.common import (
    END_RUN,
    StageIO,
    ask_choice,
    ask_confirm,
    option,
    prompt,
    ref_of,
    rollback_node,
    to_json,
)
from orchestrator.stages.implementation.graph import FileWrites, _system, _tree

STAGE = "verify"
SOURCE_SUFFIXES = (".java", ".py", ".go", ".xml", ".properties", ".yml", ".yaml", ".sql", ".mod")


class VerifyState(StageIO, total=False):
    attempt: int            # verification attempts so far
    auto_fixes: int         # automatic fixes used (shared budget)
    hinted: bool            # the latest fix came from a human hint
    hint: str
    report: dict            # latest verification report
    history: list[dict]     # summary per attempt
    first_failure_at: float
    next_step: str


def _stack(ctx, state):
    stack_id = ctx.store.read_json(ref_of(state, "stack_adr"), "stack.json")["chosen_stack"]
    return ctx.config.stacks.stacks[stack_id]


@observed_node(STAGE, "V1_entry")
def v1_entry(state: VerifyState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ctx.approvals.require_approved(ref_of(state, "test_plan"), ref_of(state, "acceptance_suite"))
    return {"attempt": 0, "auto_fixes": 0, "hinted": False, "hint": "", "history": []}


def _junit(path: Path) -> dict[str, dict]:
    results: dict[str, dict] = {}
    if not path.exists():
        return results
    for case in ET.parse(path).getroot().iter("testcase"):
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        results[case.get("name", "")] = {
            "passed": failure is None,
            "message": (failure.get("message", "") + "\n" + (failure.text or ""))[:1500]
            if failure is not None else "",
        }
    return results


def _run_phase(ctx, state, suite_dir: Path, ws: Path, stack, phase: str, attempt_dir: Path,
               db_path: Path) -> tuple[dict, dict[str, dict]]:
    contract = ctx.config.policy.contract
    service = ServiceProcess(stack.commands.run, ws, attempt_dir / f"service-{phase}.log",
                             contract.port_env, contract.ready_line_regex,
                             contract.startup_error_regex, {"DB_PATH": str(db_path)})
    start = service.start(ctx.config.policy.timeouts.startup_s)
    startup = {"ok": start.ok, "reason": start.reason, "startup_ms": start.startup_ms,
               "error_lines": start.error_lines, "log_tail": start.log_tail[-4000:]}
    if not start.ok:
        return startup, {}
    try:
        junit = attempt_dir / f"junit-{phase}.xml"
        result = runner.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                             f"test_acceptance_{phase}.py", f"--junitxml={junit}"],
                            suite_dir, ctx.config.policy.timeouts.acceptance_s,
                            env={"BASE_URL": f"http://127.0.0.1:{start.port}",
                                 "PYTHONPATH": str(suite_dir)})
        ctx.log.append("event", "acceptance_phase", stage=STAGE, phase=phase, ok=result.ok,
                       duration_ms=result.duration_ms)
        startup["log_tail"] = service.tail()[-4000:]
        return startup, _junit(junit)
    finally:
        service.stop()


@observed_node(STAGE, "V2_V4_verify")
def verify(state: VerifyState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ws = Path(state["workspace"])
    stack = _stack(ctx, state)
    attempt = state.get("attempt", 0) + 1
    attempt_dir = ctx.run_dir / "verify" / f"attempt-{attempt}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"attempt": attempt, "head": ProductRepo(ws).head(),
                              "hinted": state.get("hinted", False)}

    build = runner.run(stack.commands.build_and_unit_test, ws, ctx.config.policy.timeouts.build_s)
    report["build"] = {"ok": build.ok, "duration_ms": build.duration_ms,
                       "output_tail": build.tail(120)}
    ctx.log.append("event", "build", stage=STAGE, ok=build.ok, command=build.command,
                   duration_ms=build.duration_ms)
    if build.ok:
        suite_ref = ref_of(state, "acceptance_suite")
        files = ctx.store.read(suite_ref)  # verify=True: the frozen hash is re-checked here
        suite_dir = Path(tempfile.mkdtemp(prefix="acceptance-", dir=attempt_dir))
        for name, content in files.items():
            (suite_dir / name).write_text(content)
        report["suite"] = suite_ref.model_dump()
        results: dict[str, dict] = {}
        phases = [p for p in ("main", "isolated") if f"test_acceptance_{p}.py" in files]
        for phase in phases:
            db = attempt_dir / f"{phase}.sqlite"
            startup, phase_results = _run_phase(ctx, state, suite_dir, ws, stack, phase,
                                                attempt_dir, db)
            report.setdefault("startup", startup)
            if not startup["ok"]:
                report["startup"] = startup
                break
            results.update(phase_results)
        report["acceptance"] = results
    cases = ctx.store.read_json(ref_of(state, "test_plan"), "test_plan.json")
    report["tests_total"] = len(cases)
    acc = report.get("acceptance") or {}
    report["tests_passed"] = sum(1 for r in acc.values() if r["passed"])
    report["passed"] = bool(build.ok and report.get("startup", {}).get("ok")
                            and acc and report["tests_passed"] == len(cases))
    report["failed_stage"] = ("build" if not build.ok else
                              "startup" if not report.get("startup", {}).get("ok") else
                              "acceptance" if not report["passed"] else None)
    ref = ctx.store.put("verification_report", {"report.json": to_json(report)},
                        produced_by="V5", inputs=[ref_of(state, "acceptance_suite")],
                        attempt=attempt)
    ctx.log.append("event", "verification", stage=STAGE, attempt=attempt,
                   passed=report["passed"], failed_stage=report["failed_stage"],
                   tests=f"{report['tests_passed']}/{report['tests_total']}",
                   artifact=ref.model_dump())
    history = list(state.get("history") or []) + [{
        "attempt": attempt, "failed_stage": report["failed_stage"],
        "tests": f"{report['tests_passed']}/{report['tests_total']}",
        "hinted": state.get("hinted", False)}]
    return {"attempt": attempt, "report": report, "history": history,
            "artifacts": {"verification_report": ref.model_dump()}}


def route_after_verify(state: VerifyState) -> str:
    ctx = get_context(state["run_id"])
    if state["report"]["passed"]:
        return "V_confirm_pass" if state.get("hinted") else "V_done"
    if state.get("auto_fixes", 0) < ctx.config.policy.budgets.verify_auto_fixes \
            and not state.get("hinted"):
        return "V6_fix"
    return "V_escalate"


def _failure_text(report: dict, cases: list[dict]) -> str:
    stage = report["failed_stage"]
    if stage == "build":
        return report["build"]["output_tail"]
    if stage == "startup":
        s = report["startup"]
        return f"{s['reason']}\nerror lines:\n" + "\n".join(s["error_lines"])
    by_name = {f"test_{c['id'].lower().replace('-', '_')}": c for c in cases}
    lines = []
    for name, r in sorted(report["acceptance"].items()):
        if not r["passed"]:
            case = by_name.get(name, {})
            lines.append(f"{name} ({case.get('covers')}: {case.get('title')})\n"
                         f"steps: {to_json(case.get('steps', []))[:1500]}\n"
                         f"failure: {r['message']}")
    missing = set(by_name) - set(report["acceptance"])
    lines += [f"{m}: did not run" for m in sorted(missing)]
    return "\n\n".join(lines)[:20000]


def _sources(ws: Path) -> str:
    parts, used = [], 0
    for p in sorted(ws.rglob("*")):
        if not p.is_file() or ".git" in p.parts or "target" in p.parts or \
                p.suffix not in SOURCE_SUFFIXES:
            continue
        text = p.read_text(errors="replace")
        if used + len(text) > 150_000:
            parts.append(f"--- {p.relative_to(ws)} (omitted: context budget) ---")
            continue
        used += len(text)
        parts.append(f"--- {p.relative_to(ws)} ---\n{text}")
    return "\n\n".join(parts)


@observed_node(STAGE, "V6_fix")
def v6_fix(state: VerifyState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ws = Path(state["workspace"])
    stack = _stack(ctx, state)
    report = state["report"]
    cases = ctx.store.read_json(ref_of(state, "test_plan"), "test_plan.json")
    design = ctx.store.read(ref_of(state, "design"))
    previous = "\n".join(f"attempt {h['attempt']}: failed at {h['failed_stage']}, tests "
                         f"{h['tests']}" + (f"; fix notes: {h.get('notes', '')}" if
                                            h.get("notes") else "")
                         for h in state.get("history", [])) or "none"
    role = "fallback" if state.get("auto_fixes", 0) + 1 >= \
        ctx.config.policy.budgets.verify_auto_fixes else "coding"
    result = ctx.llm.structured(
        stage=STAGE, node="V6_fix", purpose="verify.fix",
        system=_system(ctx, state),
        user=prompt(STAGE, "fix", failed_stage=report["failed_stage"],
                    failure=_failure_text(report, cases),
                    service_log=(report.get("startup") or {}).get("log_tail", "none")[-3000:],
                    openapi=design["openapi.yaml"], design=design["design.md"],
                    tree="\n".join(_tree(ws)), sources=_sources(ws), previous=previous,
                    hint=state.get("hint") or "none"),
        schema=FileWrites, role=role, effort="medium", max_tokens=32000,
    )
    files = {w.path: w.content for w in result.value.files}
    problems = code_guard.check_paths(list(files), stack, ctx.config.policy.paths.forbidden)
    problems += code_guard.check_suppressions(files)
    if not problems:
        for rel, content in files.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(content)
        if (ws / "pom.xml").is_file():
            problems += code_guard.check_maven_dependencies((ws / "pom.xml").read_text(), stack)
    repo = ProductRepo(ws)
    if problems:
        repo.reset_to(repo.head())
        ctx.log.append("event", "fix_rejected_by_guardrails", stage=STAGE, problems=problems)
    else:
        n = state.get("auto_fixes", 0) + (0 if state.get("hint") else 1)
        repo.commit_all(f"fix attempt {state['attempt']}: {report['failed_stage']}\n\n"
                        f"Run: {ctx.run_id}\nNotes: {result.value.notes[:500]}")
        ctx.log.append("decision", "fix_applied", made_by="agent:implementation",
                       basis=[result.call_id], notes=result.value.notes, files=list(files),
                       hinted=bool(state.get("hint")), auto_fix_number=n)
    history = list(state.get("history") or [])
    if history:
        history[-1] = {**history[-1], "notes": result.value.notes[:300]}
    hinted = bool(state.get("hint"))
    return {"auto_fixes": state.get("auto_fixes", 0) + (0 if hinted else 1), "history": history,
            "hinted": hinted, "hint": ""}


@observed_node(STAGE, "V_escalate")
def v_escalate(state: VerifyState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    report = state["report"]
    lines = [f"Build: {'✅' if report['build']['ok'] else '❌'}"]
    if "startup" in report:
        s = report["startup"]
        lines.append(f"Startup: {'✅' if s['ok'] else '❌ ' + s['reason']} "
                     f"({s['startup_ms']} ms)")
    if report.get("acceptance"):
        lines.append(f"Acceptance: {report['tests_passed']}/{report['tests_total']} passed")
        for name, r in sorted(report["acceptance"].items()):
            if not r["passed"]:
                lines.append(f"  ❌ {name}: {r['message'].splitlines()[0][:200]}")
    elif report["failed_stage"] in ("build", "startup"):
        lines.append("Acceptance tests were not run.")
        tail = report["build"]["output_tail"] if report["failed_stage"] == "build" else \
            report["startup"]["log_tail"]
        lines += ["", "Last output:", tail[-1500:]]
    lines += ["", "History: " + "; ".join(f"#{h['attempt']} {h['failed_stage'] or 'passed'} "
                                          f"{h['tests']}{' (hint)' if h['hinted'] else ''}"
                                          for h in state["history"])]
    decision = ask_choice("verify_escalation", "Stage 5 Verify · needs your input",
                          "\n".join(lines),
                          [option("h", "Give an implementation hint", needs_reason=True),
                           END_RUN])
    if decision["key"] == "h":
        ctx.log.append("decision", "verify_hint", made_by="human:" + ctx.config.app.approver_name,
                       hint=decision["reason"])
        return {"hint": decision["reason"], "next_step": "V6_fix"}
    ctx.log.append("decision", "run_ended", gate="verify_escalation",
                   made_by="human:" + ctx.config.app.approver_name, rationale=decision["reason"])
    return {"status": "ended", "status_reason": decision["reason"], "next_step": "rollback"}


@observed_node(STAGE, "V_confirm_pass")
def v_confirm_pass(state: VerifyState) -> dict[str, Any]:
    if ask_confirm("verify_pass", f"All {state['report']['tests_total']} acceptance tests "
                                  "passed after your hint. Move on to the next stage?"):
        return {"next_step": "V_done"}
    return {"next_step": "V_escalate", "hinted": False}


@observed_node(STAGE, "V_done")
def v_done(state: VerifyState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ref = ref_of(state, "verification_report")
    ctx.approvals.set_status(ref, "APPROVED", by="policy:all-acceptance-tests-passed")
    return {}


def build() -> StateGraph:
    g = StateGraph(VerifyState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("V1_entry", v1_entry)
    g.add_node("V2_V4_verify", verify)
    g.add_node("V6_fix", v6_fix)
    g.add_node("V_escalate", v_escalate)
    g.add_node("V_confirm_pass", v_confirm_pass)
    g.add_node("V_done", v_done)
    g.add_node("rollback", rollback_node(STAGE))
    g.add_edge(START, "V1_entry")
    g.add_edge("V1_entry", "V2_V4_verify")
    g.add_conditional_edges("V2_V4_verify", route_after_verify,
                            ["V_done", "V_confirm_pass", "V6_fix", "V_escalate"])
    g.add_edge("V6_fix", "V2_V4_verify")
    g.add_conditional_edges("V_escalate", lambda s: s["next_step"], ["V6_fix", "rollback"])
    g.add_conditional_edges("V_confirm_pass", lambda s: s["next_step"], ["V_done", "V_escalate"])
    g.add_edge("V_done", END)
    g.add_edge("rollback", END)
    return g

