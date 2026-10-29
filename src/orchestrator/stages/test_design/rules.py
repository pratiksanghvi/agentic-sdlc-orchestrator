"""T1 (NFR cases from catalog recipes, by code) and T3 (deterministic plan validation)."""

from __future__ import annotations

import json
import re
from typing import Any

from orchestrator.contract import openapi
from orchestrator.stages.test_design.schemas import Assertion, Header, Step, TestCase

_VAR_USE = re.compile(r"\$\{(\w+)\}")
NO_STACK_TRACE = [
    Assertion(target="$body", op="not_contains", value="Exception"),
    Assertion(target="$body", op="not_contains", value="Traceback"),
    Assertion(target="$body", op="not_contains", value="at java."),
]
PROBLEM_JSON = Assertion(target="content-type", op="contains", value="application/problem+json")


def _step(name, method, path, body=None, *, status=None, status_not=None, repeat=1,
          body_asserts=(), header_asserts=()) -> Step:
    return Step(
        name=name, method=method, path=path,
        headers=[Header(name="Content-Type", value="application/json")] if body is not None
        else [],
        body_json=body, repeat=repeat, expect_status=status, expect_status_not=status_not,
        body_assertions=list(body_asserts), header_assertions=list(header_asserts),
        capture=[], follow_redirects=False,
    )


def nfr_cases(plan: list[dict], doc: dict[str, Any], first_id: int) -> list[TestCase]:
    ops = openapi.operations(doc)
    writes = [o for o in ops if o.method in ("POST", "PUT", "PATCH", "DELETE")]
    body_ops = [o for o in writes if o.request_schema and o.request_schema.get("properties")]
    reads = [o for o in ops if o.method == "GET" and "{" not in o.path]
    cases: list[TestCase] = []

    def add(covers, title, steps, phase="main"):
        cases.append(TestCase(id=f"TC-{first_id + len(cases)}", covers=covers, title=title,
                              kind="nfr", phase=phase, steps=steps))

    for item in plan:
        cid, req, params = item["catalog_id"], item["requirement_id"], item["params"]
        if cid == "OBS-METRICS":
            probe = (reads or ops)[0]
            path = re.sub(r"\{[^}]+\}", "nonexistent0", probe.path)
            add(req, "Metrics expose request count and latency per route", [
                _step("call an endpoint", probe.method if probe.method == "GET" else "GET", path,
                      status_not=500),
                _step("read metrics", "GET", "/metrics", status=200, body_asserts=[
                    Assertion(target="$body", op="contains", value="http_server_requests")]),
            ])
        elif cid == "SEC-INPUT":
            limit = int(params.get("max_body_bytes") or 65536)
            for op in body_ops:
                props = op.request_schema["properties"]
                required = op.request_schema.get("required") or list(props)
                valid = {k: openapi.sample_value(k, v) for k, v in props.items()}
                path = re.sub(r"\{[^}]+\}", "x", op.path)
                missing = {k: v for k, v in valid.items() if k != required[0]}
                wrong = {**valid, required[0]: openapi.wrong_type_value(props[required[0]])}
                oversized = {**valid, required[0]: "a" * (limit + 1024)}
                for title, body in ((f"missing required field '{required[0]}'", missing),
                                    (f"wrong type for '{required[0]}'", wrong),
                                    ("oversized body", oversized)):
                    add(req, f"{op.key} rejects {title} with problem+json", [
                        _step(title, op.method, path, json.dumps(body), status=400,
                              body_asserts=NO_STACK_TRACE, header_asserts=[PROBLEM_JSON])])
        elif cid == "RL-BASIC":
            limit = int(params.get("limit") or 60)
            target = (body_ops or writes or ops)[0]
            body = None
            if target.request_schema and target.request_schema.get("properties"):
                body = json.dumps({k: openapi.sample_value(k, v) for k, v in
                                   target.request_schema["properties"].items()})
            path = re.sub(r"\{[^}]+\}", "x", target.path)
            add(req, f"Rate limit of {limit} requests per window returns 429 with Retry-After", [
                _step("consume the limit", target.method, path, body, status_not=429,
                      repeat=limit),
                _step("exceed the limit", target.method, path, body, status=429,
                      header_asserts=[Assertion(target="retry-after", op="exists", value=None)]),
            ], phase="isolated")
    return cases


def validate_plan(cases: list[TestCase], spec: dict, plan: list[dict],
                  doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    ops = openapi.operations(doc)
    ids = [c.id for c in cases]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"duplicate test case ids: {', '.join(dupes)}")
    mvp = {f["id"] for f in spec["functional_requirements"] if f["priority"] == "MVP"}
    acs = {a["id"] for a in spec["acceptance_criteria"] if a["requirement_id"] in mvp}
    nfr_ids = {p["requirement_id"] for p in plan}
    covered = {c.covers for c in cases}
    for ac in sorted(acs - covered):
        problems.append(f"{ac} has no test case")
    for nfr in sorted(nfr_ids - covered):
        problems.append(f"{nfr} has no test case")
    for case in cases:
        if case.covers not in acs | nfr_ids:
            problems.append(f"{case.id} covers {case.covers}, which is not an MVP AC or NFR")
        captured: set[str] = set()
        for step in case.steps:
            where = f"{case.id} step '{step.name}'"
            for var in _VAR_USE.findall(step.path + (step.body_json or "")):
                if var not in captured:
                    problems.append(f"{where} uses ${{{var}}} before capturing it")
            captured |= {c.var for c in step.capture}
            if step.body_json is not None:
                try:
                    json.loads(step.body_json)
                except ValueError:
                    problems.append(f"{where} body_json is not valid JSON")
            if step.repeat < 1:
                problems.append(f"{where} repeat must be >= 1")
            if case.kind == "nfr" and step.path == "/metrics":
                continue
            op = openapi.match(ops, step.method, step.path)
            if op is None:
                problems.append(f"{where}: {step.method} {step.path} is not in the OpenAPI")
            elif (case.kind != "nfr"  # NFR statuses (429, 400) come from the catalog recipes
                  and step.expect_status and op.statuses
                  and step.expect_status not in op.statuses):
                problems.append(f"{where}: status {step.expect_status} is not declared for "
                                f"{op.key} (declared: {sorted(op.statuses)})")
    return problems


def plan_markdown(cases: list[TestCase]) -> str:
    lines = ["# Acceptance test plan", "", "| Case | Covers | Kind | Phase | Title |",
             "|---|---|---|---|---|"]
    lines += [f"| {c.id} | {c.covers} | {c.kind} | {c.phase} | {c.title} |" for c in cases]
    for c in cases:
        lines += ["", f"## {c.id} — {c.title}", ""]
        for i, s in enumerate(c.steps, 1):
            expect = (f"expect {s.expect_status}" if s.expect_status else
                      f"expect not {s.expect_status_not}" if s.expect_status_not else "")
            times = f" ×{s.repeat}" if s.repeat > 1 else ""
            lines.append(f"{i}. {s.name}: `{s.method} {s.path}`{times} {expect}")
    return "\n".join(lines) + "\n"
