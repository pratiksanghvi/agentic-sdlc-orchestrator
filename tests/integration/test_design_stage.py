from orchestrator.artifacts.store import ArtifactRef
from orchestrator.graph.main import build_graph
from orchestrator.runtime.driver import run_graph

from .test_requirements_stage import REQ, analysis, spec

JAVA = "java21-springboot3-maven"

OPENAPI = """
openapi: 3.0.3
info: {title: URL shortener, version: "1.0"}
paths:
  /links:
    post:
      responses:
        "201": {description: created}
        "400": {description: bad request}
"""
SQL = "CREATE TABLE links (code TEXT PRIMARY KEY, url TEXT NOT NULL);"


def stack_decision(stack_id=JAVA):
    return {
        "options": [{"name": "Spring Boot", "stack_id": stack_id, "language": "java",
                     "framework": "Spring Boot", "build_tool": "Maven", "persistence": "SQLite",
                     "test_framework": "JUnit 5", "pros": ["mature"], "cons": ["verbose"],
                     "fit": "good"}],
        "recommended_stack_id": stack_id,
        "rationale": "Mature ecosystem",
        "consequences": ["JVM required"],
        "rejected_alternatives": ["Go: fewer validated recipes"],
    }


def design(openapi=OPENAPI, sql=SQL, endpoint="POST /links", deps=None):
    return {
        "modules": [{"name": "links", "responsibility": "create links", "traces": ["FR-1"]},
                    {"name": "ratelimit", "responsibility": "limit", "traces": ["NFR-1"]}],
        "openapi_yaml": openapi,
        "schema_sql": sql,
        "flows": [{"name": "create", "steps": ["validate", "store", "respond"]}],
        "error_model": "problem+json",
        "traceability": [
            {"requirement_id": "FR-1", "endpoints": [endpoint], "modules": ["links"],
             "catalog_ids": []},
            {"requirement_id": "NFR-1", "endpoints": [], "modules": ["ratelimit"],
             "catalog_ids": ["RL-BASIC"]},
        ],
        "dependencies": deps or ["org.springframework.boot:spring-boot-starter-web"],
    }


def scripts(**over):
    base = {"requirements.analyze": [analysis()], "requirements.normalize": [spec()],
            "design.stack": [stack_decision()], "design.architecture": [design()]}
    base.update(over)
    return base


def run(make_run, answers, scripts):
    ctx, io, backend = make_run(answers=answers, scripts=scripts)
    result = run_graph(ctx, build_graph(ctx), {"run_id": ctx.run_id, "requirement_text": REQ,
                                               "artifacts": {}, "status": "running"})
    return ctx, io, backend, result


def test_spec_stack_and_design_are_approved_in_order(make_run):
    ctx, io, _, result = run(make_run, ["a", "a", "a"], scripts())
    arts = result["artifacts"]
    for t in ("spec", "stack_adr", "nfr_plan", "design"):
        assert t in arts
    design_ref = ArtifactRef(**arts["design"])
    assert ctx.approvals.is_approved(design_ref)
    plan = ctx.store.read_json(ArtifactRef(**arts["nfr_plan"]), "nfr_plan.json")
    assert plan["stack"] == JAVA
    assert plan["plan"][0]["params"]["limit"] == "60"  # user's value overrides catalog default
    assert plan["plan"][0]["params"]["window_seconds"] == 60
    assert ctx.store.manifest(design_ref)["inputs"][0]["type"] == "spec"
    assert ctx.log.verify() == (True, None)


def test_stacks_without_nfr_implementation_are_hidden(make_run):
    # spec requests RL-BASIC, which only has a Java implementation in the catalog
    ctx, io, _, _ = run(make_run, ["a", "a", "a"], scripts())
    stack_gate = next(body for title, body in io.shown if "approve stack" in title)
    assert "python312-fastapi" not in stack_gate and "go122-chi" not in stack_gate


def test_unsupported_recommendation_is_retried(make_run):
    ctx, io, backend, result = run(make_run, ["a", "a", "a"], scripts(**{
        "design.stack": [stack_decision("node-express"), stack_decision()]}))
    stack_calls = [c for c in backend.calls if c["purpose"] == "design.stack"]
    assert "is not one of" in stack_calls[1]["user"]
    assert result["artifacts"]["stack_adr"]


def test_invalid_design_is_sent_back_with_findings(make_run):
    bad = design(sql="CREATE TABLE links (code TEXT PRIMARY KEY,", endpoint="GET /nope")
    ctx, io, backend, result = run(make_run, ["a", "a", "a"], scripts(**{
        "design.architecture": [bad, design()]}))
    retry = [c for c in backend.calls if c["purpose"] == "design.architecture"][1]["user"]
    assert "not valid SQLite" in retry and "'GET /nope', which is not in OpenAPI" in retry
    assert ctx.approvals.is_approved(ArtifactRef(**result["artifacts"]["design"]))


def test_disallowed_dependency_blocks_approval(make_run):
    bad = design(deps=["org.evil:backdoor"])
    ctx, io, _, result = run(make_run, ["a", "a", "r", "use only allowed deps please", "a"],
                             scripts(**{"design.architecture": [bad, bad, bad, design()]}))
    gate = next(body for title, body in io.shown if "approve design" in title)
    assert "not in the allowlist" in gate and "[a] Approve" not in gate
    assert ctx.approvals.is_approved(ArtifactRef(**result["artifacts"]["design"]))


def test_reject_design_and_change_stack_loops_back_to_d2(make_run):
    ctx, io, backend, result = run(
        make_run, ["a", "a", "k", "reconsider the stack choice", "a", "a"],
        scripts(**{"design.stack": [stack_decision(), stack_decision()],
                   "design.architecture": [design(), design()]}))
    stack_calls = [c for c in backend.calls if c["purpose"] == "design.stack"]
    assert len(stack_calls) == 2 and "reconsider the stack choice" in stack_calls[1]["user"]
    assert result["status"] == "running"


def test_human_can_override_stack_when_no_nfrs(make_run):
    no_nfr = spec()
    no_nfr["non_functional_requirements"] = []
    no_nfr_design = design(deps=["github.com/go-chi/chi/v5"])
    no_nfr_design["traceability"] = no_nfr_design["traceability"][:1]
    ctx, io, _, result = run(make_run, ["a", "2", "team prefers Go here", "a"], scripts(**{
        "requirements.normalize": [no_nfr], "design.architecture": [no_nfr_design]}))
    stack = ctx.store.read_json(ArtifactRef(**result["artifacts"]["stack_adr"]), "stack.json")
    assert stack["chosen_stack"] == "go122-chi"
    assert stack["override_reason"] == "team prefers Go here"
    assert ctx.approvals.is_approved(ArtifactRef(**result["artifacts"]["stack_adr"]))


def test_operational_endpoint_in_openapi_is_flagged(make_run):
    with_metrics = OPENAPI + (
        "  /metrics:\n    get:\n      responses:\n        '200': {description: ok}\n")
    ctx, io, backend, _ = run(make_run, ["a", "a", "a"], scripts(**{
        "design.architecture": [design(openapi=with_metrics), design()]}))
    retry = [c for c in backend.calls if c["purpose"] == "design.architecture"][1]["user"]
    assert "/metrics is an operational endpoint" in retry


def test_table_names_parsed_from_ddl():
    from orchestrator.stages.design.rules import table_names

    sql = 'CREATE TABLE IF NOT EXISTS links (a TEXT);\ncreate table "clicks" (b INT);'
    assert table_names(sql) == ["links", "clicks"]


def test_unvalidated_recommendation_is_labelled(make_run):
    no_nfr = spec()
    no_nfr["non_functional_requirements"] = []
    d = design(deps=["fastapi"])
    d["traceability"] = d["traceability"][:1]
    ctx, io, _, _ = run(make_run, ["a", "a", "a"], scripts(**{
        "requirements.normalize": [no_nfr], "design.stack": [stack_decision("python312-fastapi")],
        "design.architecture": [d]}))
    gate = next(body for title, body in io.shown if "approve stack" in title)
    assert "[a] Approve python312-fastapi (not validated end-to-end)" in gate
