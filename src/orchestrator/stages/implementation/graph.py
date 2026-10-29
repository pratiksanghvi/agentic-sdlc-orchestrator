"""Stage 4 — Implementation (4a product code ‖ 4b acceptance suite), no human gate.

Before work starts a backup tag is always taken and the human is asked once whether to roll
back on failure. 4a plans tasks, then implements them one at a time — guardrails, compile and a
checkpoint commit after each. 4b turns the approved test plan into a frozen pytest suite. The
branches join before Stage 5. If a task cannot be made to compile, the human gets the errors and
may give unlimited hints or end the run.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from orchestrator.execution import runner
from orchestrator.execution.git_ops import ProductRepo
from orchestrator.guardrails import code as code_guard
from orchestrator.guardrails.secrets import scan_files
from orchestrator.llm.client import LLMError
from orchestrator.observability.node import observed_node
from orchestrator.runtime.context import get_context
from orchestrator.stages.common import (
    END_RUN,
    StageIO,
    ask_choice,
    ask_confirm,
    llm_step,
    option,
    prompt,
    ref_of,
    rollback_node,
    to_json,
)
from orchestrator.testkit import generator

STAGE = "implementation"
SCAFFOLD_RULE = ("- T-1 scaffolds the project: build file, application entry point with the "
                 "startup contract,\n  configuration, and the SQLite schema. It must compile on "
                 "its own.")
BROWNFIELD_RULE = ("- The project already exists (see file_tree): do NOT re-scaffold. Modify "
                   "existing files and add new\n  ones; keep existing behavior and existing tests "
                   "passing.")
MAX_CONTEXT_CHARS = 120_000


class FileRef(BaseModel):
    path: str
    action: str = Field(description='"create" or "modify"')


class Task(BaseModel):
    id: str = Field(pattern=r"^T-\d+$")
    goal: str
    files: list[FileRef]
    depends_on: list[str]
    traces: list[str]
    done_criteria: str


class TaskPlan(BaseModel):
    tasks: list[Task]


class FileWrite(BaseModel):
    path: str
    content: str


class FileWrites(BaseModel):
    files: list[FileWrite]
    notes: str


class ImplementationState(StageIO, total=False):
    task_plan: list[dict]
    task_index: int
    last_good: str
    errors: str
    hint: str
    task_failed: bool
    contract_fix_tried: bool
    suite_ready: bool


# ---------- helpers ----------


def _slug(text: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-").split("-")
    return "-".join(words[:4]) or "product"


def _design_inputs(ctx, state) -> dict[str, str]:
    files = ctx.store.read(ref_of(state, "design"))
    plan = ctx.store.read_json(ref_of(state, "nfr_plan"), "nfr_plan.json")
    return {"design": files["design.md"], "openapi": files["openapi.yaml"],
            "schema_sql": files["schema.sql"], "nfr_plan": to_json(plan["plan"])}


def _stack(ctx, state):
    stack_id = ctx.store.read_json(ref_of(state, "stack_adr"), "stack.json")["chosen_stack"]
    return stack_id, ctx.config.stacks.stacks[stack_id]


def _system(ctx, state) -> str:
    stack_id, stack = _stack(ctx, state)
    deps = "\n".join(f"  {k}: {v}" for k, v in stack.dependencies.items())
    return prompt(STAGE, "system", paths=", ".join(stack.path_allowlist), dependencies=deps,
                  stack_id=stack_id, guidance=stack.guidance or "none")


def _tree(ws: Path) -> list[str]:
    return sorted(str(p.relative_to(ws)) for p in ws.rglob("*")
                  if p.is_file() and ".git" not in p.parts and "target" not in p.parts)


def _existing_context(ws: Path, task: dict, plan: list[dict]) -> str:
    wanted: list[str] = [f["path"] for f in task["files"]]
    by_id = {t["id"]: t for t in plan}
    for dep in task["depends_on"]:
        wanted += [f["path"] for f in by_id.get(dep, {}).get("files", [])]
    for always in ("pom.xml", "src/main/resources/application.properties"):
        wanted.append(always)
    parts, used, seen = [], 0, set()
    for rel in wanted:
        path = ws / rel
        if rel in seen or not path.is_file():
            continue
        seen.add(rel)
        text = path.read_text(encoding="utf-8", errors="replace")
        if used + len(text) > MAX_CONTEXT_CHARS:
            parts.append(f"--- {rel} (omitted: context budget) ---")
            continue
        used += len(text)
        parts.append(f"--- {rel} ---\n{text}")
    return "\n\n".join(parts) or "none"


def _contract_present(ws: Path, port_env: str) -> bool:
    texts = [p.read_text(errors="replace") for p in ws.rglob("*")
             if p.is_file() and ".git" not in p.parts and "target" not in p.parts
             and p.suffix in (".java", ".py", ".go", ".properties", ".yaml", ".yml")]
    blob = "\n".join(texts)
    return "SERVICE_READY port=" in blob and port_env in blob


# ---------- 4a: product code ----------


@observed_node(STAGE, "I0_rollback_question")
def i0_rollback_question(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ctx.approvals.require_approved(*(ref_of(state, t) for t in
                                     ("spec", "stack_adr", "design", "test_plan")))
    if state.get("mode") == "brownfield" and not state.get("workspace"):
        raise ValueError("brownfield run without a workspace")
    opt_in = ask_confirm("rollback_opt_in", "A backup is taken before implementation. If "
                         "verification fails and you end the run, roll back to it?")
    return {"rollback_opt_in": bool(opt_in)}


@observed_node(STAGE, "I0_setup")
def i0_setup(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    spec = ctx.store.read_json(ref_of(state, "spec"), "spec.json")
    ws = Path(state["workspace"]) if state.get("workspace") else \
        ctx.root / "workspaces" / _slug(spec["title"])
    repo = ProductRepo(ws)
    repo.ensure()
    tag = repo.backup(ctx.run_id)
    branch = repo.start_run_branch(ctx.run_id)
    ctx.log.append("event", "workspace_ready", stage=STAGE, workspace=str(ws), backup_tag=tag,
                   branch=branch, head=repo.head(), rollback_opt_in=state["rollback_opt_in"])
    return {"workspace": str(ws), "last_good": repo.head()}


def _validate_plan(plan: TaskPlan, stack) -> list[str]:
    ids = [t.id for t in plan.tasks]
    problems = []
    if not plan.tasks:
        return ["the task plan is empty"]
    if len(ids) != len(set(ids)):
        problems.append("task ids must be unique")
    seen: set[str] = set()
    for t in plan.tasks:
        for dep in t.depends_on:
            if dep not in seen:
                problems.append(f"{t.id} depends on {dep}, which is not an earlier task")
        seen.add(t.id)
        problems += code_guard.check_paths([f.path for f in t.files], stack, [])
    return problems


@observed_node(STAGE, "I1_plan")
def i1_plan(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    _, stack = _stack(ctx, state)
    tree = "\n".join(_tree(Path(state["workspace"])))
    result = llm_step(
        ctx, stage=STAGE, node="I1_plan", purpose="implementation.plan", role="coding",
        system=_system(ctx, state),
        user=prompt(STAGE, "plan", **_design_inputs(ctx, state), tree=tree or "empty",
                    scaffold_rule=SCAFFOLD_RULE if not tree else BROWNFIELD_RULE),
        schema=TaskPlan, validate=lambda p: _validate_plan(p, stack), effort="medium",
    )
    tasks = [t.model_dump() for t in result.value.tasks]
    ref = ctx.store.put("task_plan", {"task_plan.json": to_json(tasks)}, produced_by="I1",
                        inputs=[ref_of(state, "design")])
    ctx.approvals.set_status(ref, "APPROVED", by="policy:auto-approve-sandbox-code")
    ctx.log.append("decision", "task_plan", made_by="agent:implementation",
                   basis=[result.call_id], artifact=ref.model_dump(),
                   auto_approved_by_policy=True, tasks=[t["id"] for t in tasks])
    return {"task_plan": tasks, "task_index": 0, "errors": "", "hint": "",
            "artifacts": {"task_plan": ref.model_dump()}}


def _apply_and_check(ctx, state, ws: Path, writes: FileWrites, stack) -> list[str]:
    files = {w.path: w.content for w in writes.files}
    problems = code_guard.check_paths(list(files), stack, ctx.config.policy.paths.forbidden)
    problems += code_guard.check_suppressions(files)
    if problems:
        return problems
    for rel, content in files.items():
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if (ws / "pom.xml").is_file():
        problems += code_guard.check_maven_dependencies((ws / "pom.xml").read_text(), stack)
    for finding in scan_files([ws / rel for rel in files], base=ws):
        problems.append(f"{finding.file}:{finding.line} looks like a secret ({finding.type})")
    if problems:
        return problems
    result = runner.run(stack.commands.compile, ws, ctx.config.policy.timeouts.compile_s)
    ctx.log.append("event", "compile", stage=STAGE, ok=result.ok, command=result.command,
                   duration_ms=result.duration_ms, output_tail=result.tail(60))
    return [] if result.ok else [f"compile failed:\n{result.tail(80)}"]


@observed_node(STAGE, "I4_task")
def i4_task(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ws = Path(state["workspace"])
    repo = ProductRepo(ws)
    _, stack = _stack(ctx, state)
    plan = state["task_plan"]
    task = plan[state["task_index"]]
    inputs = _design_inputs(ctx, state)
    budgets = ctx.config.policy.budgets
    roles = ["coding"] * (budgets.step_retries + 1) + ["fallback"] * budgets.stronger_model_attempts
    errors = state.get("errors") or ""
    for attempt, role in enumerate(roles, 1):
        try:
            result = ctx.llm.structured(
                stage=STAGE, node="I4_task", purpose=f"implementation.task.{task['id']}",
                system=_system(ctx, state),
                user=prompt(STAGE, "task", **inputs, plan=to_json(plan),
                            tree="\n".join(_tree(ws)) or "empty",
                            existing=_existing_context(ws, task, plan), task=to_json(task),
                            errors=errors or "none", hint=state.get("hint") or "none"),
                schema=FileWrites, role=role, effort="medium", max_tokens=32000,
            )
        except LLMError as exc:  # e.g. API unavailable or out of credit: hand to the human
            ctx.log.append("event", "task_attempt_failed", stage=STAGE, task=task["id"],
                           attempt=attempt, role=role, problems=[str(exc)[:500]])
            return {"task_failed": True, "errors": f"model call failed: {exc}"}
        problems = _apply_and_check(ctx, state, ws, result.value, stack)
        if not problems:
            commit = repo.commit_all(f"{task['id']}: {task['goal']}\n\nRun: {ctx.run_id}\n"
                                     f"Task: {task['id']}\nTraces: {', '.join(task['traces'])}")
            ctx.log.append("event", "task_done", stage=STAGE, task=task["id"], attempt=attempt,
                           commit=commit, llm_call=result.call_id)
            return {"task_index": state["task_index"] + 1, "last_good": repo.head(),
                    "errors": "", "hint": "", "task_failed": False}
        errors = "\n".join(problems)
        ctx.log.append("event", "task_attempt_failed", stage=STAGE, task=task["id"],
                       attempt=attempt, role=role, problems=problems[:20])
        repo.reset_to(state["last_good"])  # roll back the failed attempt to the checkpoint
    return {"task_failed": True, "errors": errors}


def route_after_task(state: ImplementationState) -> str:
    if state.get("task_failed"):
        return "I4_escalate"
    return "I4_task" if state["task_index"] < len(state["task_plan"]) else "I4_done"


@observed_node(STAGE, "I4_escalate")
def i4_escalate(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    task = state["task_plan"][state["task_index"]]
    summary = (f"Task {task['id']} ({task['goal']}) could not be completed after automatic "
               f"retries. The workspace is at the last good checkpoint.\n\nLast errors:\n"
               f"{state['errors'][-3000:]}")
    decision = ask_choice("implementation_escalation",
                          f"Stage 4 Implementation · {task['id']} needs help", summary,
                          [option("h", "Give an implementation hint", needs_reason=True),
                           END_RUN])
    if decision["key"] == "h":
        ctx.log.append("decision", "implementation_hint", made_by="human:"
                       + ctx.config.app.approver_name, task=task["id"], hint=decision["reason"])
        return {"hint": decision["reason"], "task_failed": False}
    return {"status": "ended", "status_reason": decision["reason"]}


@observed_node(STAGE, "I4_done")
def i4_done(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    ws = Path(state["workspace"])
    if _contract_present(ws, ctx.config.policy.contract.port_env) or state.get(
            "contract_fix_tried"):
        return {}
    # one extra task to restore the mandatory startup contract
    fix = {"id": f"T-{len(state['task_plan']) + 1}", "goal": "Implement the startup contract: "
           "read PORT and print 'SERVICE_READY port=<port>' once listening",
           "files": [], "depends_on": [], "traces": [], "done_criteria": "contract present"}
    return {"task_plan": state["task_plan"] + [fix], "contract_fix_tried": True}


def route_after_done(state: ImplementationState) -> str:
    return "I4_task" if state["task_index"] < len(state["task_plan"]) else "I4_complete"


# ---------- 4b: acceptance suite ----------


@observed_node(STAGE, "X_acceptance_suite")
def x_acceptance_suite(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    plan_ref = ref_of(state, "test_plan")
    cases = ctx.store.read_json(plan_ref, "test_plan.json")
    files = generator.generate(cases)
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in files.items():
            (Path(tmp) / name).write_text(content)
        collect = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", tmp],
                                 capture_output=True, text=True, cwd=tmp,
                                 env={**runner.clean_env(), "BASE_URL": "http://unused"})
    collected = set(re.findall(r"::(test_\w+)", collect.stdout))
    missing = generator.expected_test_names(cases) - collected
    if collect.returncode != 0 or missing:
        raise RuntimeError(f"acceptance suite failed collection (missing {sorted(missing)}):\n"
                           f"{collect.stdout[-2000:]}{collect.stderr[-2000:]}")
    ref = ctx.store.put("acceptance_suite", files, produced_by="X", inputs=[plan_ref])
    ctx.approvals.set_status(ref, "APPROVED", by="policy:derived-from-approved-test-plan")
    ctx.log.append("event", "acceptance_suite_frozen", stage=STAGE, artifact=ref.model_dump(),
                   tests=len(collected))
    return {"artifacts": {"acceptance_suite": ref.model_dump()}, "suite_ready": True}


@observed_node(STAGE, "I5_join")
def i5_join(state: ImplementationState) -> dict[str, Any]:
    ctx = get_context(state["run_id"])
    if state.get("status") == "ended":
        return {}
    ws = Path(state["workspace"])
    if not _contract_present(ws, ctx.config.policy.contract.port_env):
        ctx.log.append("event", "startup_contract_missing", stage=STAGE)
    ctx.log.append("event", "implementation_joined", stage=STAGE,
                   head=ProductRepo(ws).head(), tasks=len(state["task_plan"]))
    return {}


def i4_complete(state: ImplementationState) -> dict[str, Any]:
    """End of branch 4a (join point with 4b)."""
    return {}


def build() -> StateGraph:
    g = StateGraph(ImplementationState, input_schema=StageIO, output_schema=StageIO)
    g.add_node("I0_rollback_question", i0_rollback_question)
    g.add_node("I0_setup", i0_setup)
    g.add_node("I1_plan", i1_plan)
    g.add_node("I4_task", i4_task)
    g.add_node("I4_escalate", i4_escalate)
    g.add_node("I4_done", i4_done)
    g.add_node("X_acceptance_suite", x_acceptance_suite)
    g.add_node("I4_complete", i4_complete)
    g.add_node("I5_join", i5_join)
    g.add_node("rollback", rollback_node(STAGE))
    g.add_edge(START, "I0_rollback_question")
    g.add_edge("I0_rollback_question", "I0_setup")
    g.add_edge("I0_setup", "I1_plan")              # 4a ...
    g.add_edge("I0_setup", "X_acceptance_suite")   # ... in parallel with 4b
    g.add_edge("I1_plan", "I4_task")
    g.add_conditional_edges("I4_task", route_after_task, ["I4_task", "I4_escalate", "I4_done"])
    g.add_conditional_edges("I4_escalate", lambda s: "I4_done" if s.get("status") == "ended"
                            else "I4_task", ["I4_task", "I4_done"])
    g.add_conditional_edges("I4_done", lambda s: "I4_complete" if s.get("status") == "ended"
                            else route_after_done(s), ["I4_task", "I4_complete"])
    g.add_edge(["I4_complete", "X_acceptance_suite"], "I5_join")   # join 4a + 4b
    g.add_conditional_edges("I5_join", lambda s: "rollback" if s.get("status") == "ended"
                            else END, ["rollback", END])
    g.add_edge("rollback", END)
    return g

