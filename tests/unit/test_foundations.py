import json
import os
import re
import stat
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from orchestrator.artifacts.approvals import GovernanceError
from orchestrator.artifacts.store import ArtifactStore, IntegrityError
from orchestrator.human.gate import Option
from orchestrator.llm.backends import FakeBackend
from orchestrator.llm.client import LLMError, RawResponse
from orchestrator.llm.costs import BudgetStop
from orchestrator.llm.schema import strict_json_schema
from orchestrator.observability.eventlog import EventLog
from orchestrator.observability.node import observed_node

SRC = Path(__file__).resolve().parents[2] / "src" / "orchestrator"


# ---------- artifact store (F1) ----------


def test_every_write_is_a_new_immutable_version(tmp_path):
    store = ArtifactStore(tmp_path)
    v1 = store.put("spec", {"spec.json": '{"a": 1}', "spec.md": "# A"}, produced_by="R4")
    v2 = store.put("spec", {"spec.json": '{"a": 2}', "spec.md": "# A"}, produced_by="R4",
                   inputs=[v1], attempt=2)
    assert (v1.version, v2.version) == (1, 2)
    assert v1.hash != v2.hash
    assert store.read(v1)["spec.json"] == '{"a": 1}'
    assert store.manifest(v2)["inputs"] == [v1.model_dump()]
    assert store.latest("spec") == v2
    mode = os.stat(store.path(v1) / "spec.json").st_mode
    assert not mode & stat.S_IWUSR


def test_json_hash_ignores_formatting(tmp_path):
    store = ArtifactStore(tmp_path)
    a = store.put("x", {"d.json": '{"b":1,"a":2}'}, produced_by="t")
    b = store.put("x", {"d.json": '{\n  "a": 2,\n  "b": 1\n}'}, produced_by="t")
    assert a.hash == b.hash


def test_tampering_is_detected(tmp_path):
    store = ArtifactStore(tmp_path)
    ref = store.put("design", {"openapi.yaml": "openapi: 3.0.0"}, produced_by="D4")
    target = store.path(ref) / "openapi.yaml"
    os.chmod(target, stat.S_IWUSR | stat.S_IRUSR)
    target.write_text("openapi: 3.1.0")
    with pytest.raises(IntegrityError, match="changed after it was written"):
        store.verify(ref)


def test_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        ArtifactStore(tmp_path).put("spec", {"../evil.txt": "x"}, produced_by="t")


# ---------- event log ----------


def test_event_log_chain_verifies_and_detects_edits(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    log.append("event", "a", n=1)
    log.append("decision", "b", n=2)
    log.append("event", "c", n=3)
    assert log.verify() == (True, None)
    # reopening continues the chain
    EventLog(log.path).append("event", "d", n=4)
    assert log.verify() == (True, None)
    lines = log.path.read_text().splitlines()
    record = json.loads(lines[1])
    record["data"]["n"] = 99
    lines[1] = json.dumps(record)
    log.path.write_text("\n".join(lines) + "\n")
    assert log.verify() == (False, 2)


def test_event_log_detects_deleted_line(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    for i in range(3):
        log.append("event", "e", i=i)
    lines = log.path.read_text().splitlines()
    log.path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert log.verify()[0] is False


# ---------- approvals bound to hashes (F2) ----------


def test_approval_covers_exact_version_only(make_run):
    ctx, _, _ = make_run()
    v1 = ctx.store.put("spec", {"spec.json": "{}"}, produced_by="R4")
    ctx.approvals.approve(v1, gate="spec", approver="reviewer")
    ctx.approvals.require_approved(v1)
    v2 = ctx.store.put("spec", {"spec.json": '{"x": 1}'}, produced_by="R4")
    with pytest.raises(GovernanceError, match="no approval"):
        ctx.approvals.require_approved(v2)


def test_edit_after_approval_blocks_consumption(make_run):
    ctx, _, _ = make_run()
    ref = ctx.store.put("design", {"design.md": "v1"}, produced_by="D4")
    ctx.approvals.approve(ref, gate="design", approver="reviewer")
    path = ctx.store.path(ref) / "design.md"
    os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
    path.write_text("edited")
    with pytest.raises(GovernanceError, match="changed after approval"):
        ctx.approvals.require_approved(ref)


# ---------- structured-output schema ----------


class Item(BaseModel):
    title: str = Field(min_length=1)
    count: int = 0


class Out(BaseModel):
    items: list[Item]
    note: str | None = None


def test_strict_schema_closes_objects_and_keeps_field_named_title():
    schema = strict_json_schema(Out)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["items", "note"]
    item = schema["$defs"]["Item"]
    assert "title" in item["properties"]
    assert item["required"] == ["title", "count"]
    assert "minLength" not in json.dumps(schema)


def test_free_form_dict_fields_are_rejected():
    class Bad(BaseModel):
        m: dict[str, str]

    with pytest.raises(TypeError):
        strict_json_schema(Bad)


# ---------- traced LLM client ----------


def _call(ctx, **kw):
    return ctx.llm.structured(stage="test", node="n", purpose="p", system="sys", user="u",
                              schema=Out, **kw)


def test_every_llm_attempt_is_logged_in_full(make_run):
    ctx, _, backend = make_run(scripts={"p": [{"items": []}, {"items": [{"title": "a",
                                                                         "count": 1}]}]})
    result = _call(ctx, validate=lambda out: [] if out.items else ["need at least one item"])
    assert result.value.items[0].title == "a"
    calls = ctx.log.records("llm_call")
    assert len(calls) == len(backend.calls) == 2
    first, second = (c["data"] for c in calls)
    assert first["status"] == "validation_error" and not first["parsed_ok"]
    assert second["status"] == "ok" and second["schema_retry"]
    assert second["call_id"] == result.call_id
    assert "need at least one item" in second["messages"][0]["content"]
    assert first["usage"]["input_tokens"] == 1000 and first["cost_usd"] > 0
    assert first["system"] == "sys" and first["response_text"]


def test_schema_error_exhausts_budget(make_run):
    bad = RawResponse(text="not json", stop_reason="end_turn", usage={})
    ctx, _, backend = make_run(scripts={"p": [bad, bad, bad]})
    with pytest.raises(LLMError, match="no valid output after 3 attempts"):
        _call(ctx)
    assert len(ctx.log.records("llm_call")) == 3


def test_truncated_output_retries_with_more_tokens(make_run):
    cut = RawResponse(text='{"items": [', stop_reason="max_tokens", usage={})
    ctx, _, backend = make_run(scripts={"p": [cut, {"items": []}]})
    _call(ctx, max_tokens=1000)
    assert [c["max_tokens"] for c in backend.calls] == [1000, 2000]


def test_api_error_is_logged_then_raised(make_run):
    ctx, _, _ = make_run(scripts={"p": [RuntimeError("boom")]})
    with pytest.raises(LLMError, match="boom"):
        _call(ctx)
    assert ctx.log.records("llm_call")[0]["data"]["status"] == "api_error"


def test_role_selects_configured_model(make_run):
    ctx, _, backend = make_run(scripts={"p": [{"items": []}]})
    _call(ctx, role="coding")
    assert backend.calls[0]["model"] == "claude-sonnet-5-5"


# ---------- cost ceiling ----------


def _expensive(n):
    return [RawResponse(text='{"items": [], "note": null}', stop_reason="end_turn",
                        usage={"input_tokens": 0, "output_tokens": 200_000})] * n


def test_cost_ceiling_asks_and_continues(make_run):
    # each call: 200k output tokens on Opus = $4.00; ceiling $5 → asked at $8, then at $12
    ctx, io, _ = make_run(answers=["y", "y"], scripts={"p": _expensive(3)})
    for _ in range(3):
        _call(ctx)
    asks = [r for r in ctx.log.records("human_interaction") if r["name"] == "cost_ceiling"]
    assert [a["data"]["answer"] for a in asks] == ["y", "y"]
    assert "$8.00" in asks[0]["data"]["title"] and "$12.00" in asks[1]["data"]["title"]


def test_cost_ceiling_declined_stops(make_run):
    ctx, _, _ = make_run(answers=[""], scripts={"p": _expensive(2)})
    _call(ctx)
    with pytest.raises(BudgetStop):
        _call(ctx)


# ---------- human gate ----------

OPTIONS = [
    Option("a", "Approve"),
    Option("r", "Reject with feedback", needs_reason=True),
    Option("x", "End run", needs_reason=True, confirm="End this run?"),
]


def test_gate_reprompts_requires_reason_and_logs(make_run):
    ctx, io, _ = make_run(answers=["q", "r", "short", "needs more endpoints"])
    decision = ctx.gate.choose("spec", "Approve spec v1", "summary", OPTIONS,
                               artifact={"type": "spec", "version": 1})
    assert (decision.key, decision.reason) == ("r", "needs more endpoints")
    rec = ctx.log.records("human_interaction")[-1]["data"]
    assert rec["answer"] == "r" and rec["reason"] == "needs more endpoints"
    assert [o["key"] for o in rec["options"]] == ["a", "r", "x"]
    assert rec["approver"] == "reviewer" and rec["wait_ms"] >= 0


def test_destructive_option_defaults_to_no(make_run):
    ctx, _, _ = make_run(answers=["x", "", "a"])
    assert ctx.gate.choose("spec", "t", "s", OPTIONS).key == "a"


def test_only_applicable_options_are_shown(make_run):
    ctx, io, _ = make_run(answers=["a"])
    decision = ctx.gate.choose("spec", "t", "s", [o for o in OPTIONS if o.key != "x"])
    assert decision.key == "a"
    assert "[x]" not in io.shown[-1][1]


# ---------- observed nodes ----------


def test_observed_node_logs_success_and_failure(make_run):
    ctx, _, _ = make_run()

    @observed_node("requirements", "R1")
    def ok(state):
        return {"done": True}

    @observed_node("requirements", "R2")
    def bad(state):
        raise ValueError("nope")

    ok({"run_id": ctx.run_id})
    with pytest.raises(ValueError):
        bad({"run_id": ctx.run_id})
    names = [(r["name"], r["data"].get("node")) for r in ctx.log.records("event")]
    assert ("node_finished", "R1") in names and ("node_failed", "R2") in names
    assert ctx.log.verify() == (True, None)


def test_run_started_records_governance_hashes(make_run):
    ctx, _, _ = make_run()
    started = ctx.log.records("event")[0]
    assert started["name"] == "run_started"
    assert set(started["data"]["governance_hashes"]) == {"policy", "stacks", "nfr"}


# ---------- choke points ----------


def test_only_backends_construct_anthropic_client_and_only_gate_reads_input():
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text()
        rel = path.relative_to(SRC).as_posix()
        if re.search(r"anthropic\.Anthropic\(", text) and rel != "llm/backends.py":
            offenders.append(rel)
        if re.search(r"(?<![\w.])input\(|\.input\(", text) and rel != "human/gate.py":
            offenders.append(rel)
    assert offenders == []


def test_fake_backend_requires_script():
    with pytest.raises(AssertionError):
        FakeBackend().complete(purpose="missing")
