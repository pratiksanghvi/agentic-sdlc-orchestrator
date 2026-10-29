import json

from orchestrator.artifacts.store import ArtifactRef
from orchestrator.graph.main import build_graph
from orchestrator.runtime.driver import run_graph

from .test_design_stage import design, stack_decision
from .test_requirements_stage import REQ, analysis, spec

OPENAPI = """
openapi: 3.0.3
info: {title: URL shortener, version: "1.0"}
paths:
  /links:
    post:
      requestBody:
        content:
          application/json:
            schema: {$ref: '#/components/schemas/CreateLink'}
      responses:
        "201": {description: created}
        "400": {description: bad request}
  /links/{code}:
    get:
      responses:
        "200": {description: ok}
        "404": {description: not found}
components:
  schemas:
    CreateLink:
      type: object
      required: [url]
      properties:
        url: {type: string}
"""


def step(name, method, path, body=None, status=201, capture=None):
    return {"name": name, "method": method, "path": path, "headers": [], "body_json": body,
            "repeat": 1, "expect_status": status, "expect_status_not": None,
            "body_assertions": [], "header_assertions": [], "capture": capture or [],
            "follow_redirects": False}


def cases(path="/links/${code}", status=200):
    return {"cases": [{
        "id": "TC-1", "covers": "AC-1.1", "title": "create then read", "kind": "positive",
        "phase": "main", "steps": [
            step("create", "POST", "/links", '{"url": "https://a.example"}',
                 capture=[{"var": "code", "json_path": "$.code"}]),
            step("read", "GET", path, status=status)]}]}


def scripts(**over):
    base = {"requirements.analyze": [analysis()], "requirements.normalize": [spec()],
            "design.stack": [stack_decision()],
            "design.architecture": [design(OPENAPI, endpoint="POST /links")],
            "test_design.cases": [cases()]}
    base.update(over)
    return base


def run(make_run, answers, scripts):
    ctx, io, backend = make_run(answers=answers, scripts=scripts)
    result = run_graph(ctx, build_graph(ctx, stop_after="test_design"), {
        "run_id": ctx.run_id, "requirement_text": REQ, "artifacts": {}, "status": "running"})
    return ctx, io, backend, result


def plan_of(ctx, result):
    return ctx.store.read_json(ArtifactRef(**result["artifacts"]["test_plan"]), "test_plan.json")


def test_plan_joins_functional_and_catalog_nfr_cases(make_run):
    ctx, io, _, result = run(make_run, ["a", "a", "a", "a"], scripts())
    plan = plan_of(ctx, result)
    assert {c["id"] for c in plan} == {"TC-1", "TC-900"}
    rl = next(c for c in plan if c["kind"] == "nfr")
    assert rl["covers"] == "NFR-1" and rl["phase"] == "isolated"
    assert rl["steps"][0]["repeat"] == 60 and rl["steps"][1]["expect_status"] == 429
    assert ctx.approvals.is_approved(ArtifactRef(**result["artifacts"]["test_plan"]))
    events = [r["data"].get("node") for r in ctx.log.records("event")
              if r["name"] == "node_finished"]
    assert "T1_nfr_cases" in events and "T2_functional_cases" in events


def test_case_using_unknown_endpoint_or_status_is_sent_back(make_run):
    ctx, _, backend, result = run(make_run, ["a", "a", "a", "a"], scripts(**{
        "test_design.cases": [cases(path="/nope/${code}", status=418), cases()]}))
    retry = [c for c in backend.calls if c["purpose"] == "test_design.cases"][1]["user"]
    assert "GET /nope/${code} is not in the OpenAPI" in retry
    assert {c["id"] for c in plan_of(ctx, result)} == {"TC-1", "TC-900"}


def test_uncovered_criterion_blocks_approval_until_reject(make_run):
    empty = {"cases": []}
    ctx, io, _, result = run(make_run, ["a", "a", "a", "r", "cover AC-1.1 please", "a"],
                             scripts(**{"test_design.cases": [empty, empty, empty, cases()]}))
    gate = next(body for title, body in io.shown if "approve test_plan" in title)
    assert "AC-1.1 has no test case" in gate and "[a] Approve" not in gate
    assert result["status"] == "running"


def test_security_input_cases_generated_from_contract():
    from orchestrator.contract.openapi import load
    from orchestrator.stages.test_design.rules import nfr_cases

    plan = [{"catalog_id": "SEC-INPUT", "requirement_id": "NFR-2",
             "params": {"max_body_bytes": 100}}]
    generated = nfr_cases(plan, load(OPENAPI), 900)
    assert [c.steps[0].expect_status for c in generated] == [400, 400, 400]
    bodies = [json.loads(c.steps[0].body_json) for c in generated]
    assert "url" not in bodies[0]                      # missing required field
    assert bodies[1]["url"] == 12345                   # wrong type
    assert len(bodies[2]["url"]) > 100                 # oversized
    assert generated[0].steps[0].header_assertions[0].value == "application/problem+json"
