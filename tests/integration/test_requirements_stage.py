import pytest

from orchestrator.graph.main import build_graph
from orchestrator.runtime.driver import run_graph

REQ = "Build a URL shortener with core APIs. Limit clients to 60 requests per minute. " \
      "Redirects must respond under 50 ms."


def analysis(blocking=False, nfr_asks=None):
    return {
        "intent": "Shorten URLs",
        "functional_needs": [{"statement": "Create short links", "source_quote": "URL shortener"}],
        "nfr_asks": nfr_asks if nfr_asks is not None else [
            {"text": "Limit clients to 60 requests per minute",
             "source_quote": "Limit clients to 60 requests per minute",
             "category": "rate_limit", "classification": "SUPPORTED", "catalog_id": "RL-BASIC"},
            {"text": "Redirects must respond under 50 ms",
             "source_quote": "Redirects must respond under 50 ms",
             "category": "performance", "classification": "UNSUPPORTED_CATEGORY",
             "catalog_id": None},
        ],
        "ambiguities": [{
            "id": "Q-1", "question": "Should links expire?", "why_it_matters": "data kept",
            "recommended_default": "No expiry", "severity": "BLOCKING" if blocking else
            "NON_BLOCKING", "options": ["No expiry", "30 days"],
        }],
        "out_of_scope": [],
        "stack_constraint": None,
    }


def spec(nfr_quote="Limit clients to 60 requests per minute", with_ac=True):
    return {
        "title": "URL shortener",
        "functional_requirements": [{
            "id": "FR-1", "statement": "Create a short link for a URL", "priority": "MVP",
            "source": "explicit", "source_quote": "URL shortener"}],
        "non_functional_requirements": [{
            "id": "NFR-1", "catalog_id": "RL-BASIC", "statement": "60 requests per minute",
            "params": [{"name": "limit", "value": "60"}], "source": "explicit",
            "source_quote": nfr_quote}],
        "acceptance_criteria": [{
            "id": "AC-1.1", "requirement_id": "FR-1", "given": "a valid URL",
            "when": "the client creates a link", "then": "a 201 response with a short code",
            "verification_method": "HTTP request and response assertion"}] if with_ac else [],
        "assumptions": [{"id": "A-1", "text": "Links never expire"}],
        "out_of_scope": [],
    }


def run(make_run, answers, scripts, requirement=REQ):
    ctx, io, backend = make_run(answers=answers, scripts=scripts)
    result = run_graph(ctx, build_graph(ctx), {"run_id": ctx.run_id, "requirement_text":
                                               requirement, "artifacts": {}, "status": "running"})
    return ctx, io, backend, result


def test_happy_path_approves_spec_with_polite_not_supported(make_run):
    ctx, io, _, result = run(make_run, ["a"], {
        "requirements.analyze": [analysis()], "requirements.normalize": [spec()]})
    assert result["status"] == "running"
    ref = result["artifacts"]["spec"]
    from orchestrator.artifacts.store import ArtifactRef
    spec_ref = ArtifactRef(**ref)
    assert ctx.approvals.is_approved(spec_ref)
    saved = ctx.store.read_json(spec_ref, "spec.json")
    assert saved["not_supported"][0]["request"] == "Redirects must respond under 50 ms"
    assert "Not supported in MVP" in saved["not_supported"][0]["message"]
    assert "Redirects must respond under 50 ms" in io.shown[0][1]  # shown at the gate
    assert ctx.log.verify() == (True, None)


def test_blocking_question_is_asked_then_answer_used(make_run):
    ctx, io, backend, result = run(make_run, ["2", "a"], {
        "requirements.analyze": [analysis(blocking=True), analysis()],
        "requirements.normalize": [spec()]})
    assert result["status"] == "running"
    assert "Should links expire?" in io.shown[0][1]
    second_analyze = backend.calls[1]["user"]
    assert "Should links expire? → 30 days" in second_analyze
    clar = ctx.store.read_json(ctx.store.latest("clarifications"), "clarifications.json")
    assert clar[0]["answer"] == "30 days"


def test_nfr_not_traced_to_user_words_is_rejected_then_fixed(make_run):
    bad = spec(nfr_quote="add rate limiting for safety")  # model invented it
    ctx, io, backend, result = run(make_run, ["a"], {
        "requirements.analyze": [analysis()],
        "requirements.normalize": [bad, spec()]})
    assert result["status"] == "running"
    retry_prompt = backend.calls[-1]["user"]
    assert "NFRs may only be built when the user asked" in retry_prompt


def test_approve_hidden_while_problems_remain(make_run):
    no_ac = spec(with_ac=False)
    ctx, io, _, result = run(make_run, ["r", "please add acceptance criteria", "a"], {
        "requirements.analyze": [analysis()],
        "requirements.normalize": [no_ac, no_ac, no_ac, spec()]})
    first_gate = io.shown[0][1]
    assert "[a] Approve" not in first_gate and "FR-1 is MVP but has no acceptance" in first_gate
    assert result["status"] == "running"
    assert "Human reviewer: please add acceptance criteria" in \
        ctx.log.records("llm_call")[-1]["data"]["messages"][0]["content"]


def test_end_run_requires_reason_and_confirmation(make_run):
    ctx, io, _, result = run(make_run, ["x", "y", "not what we need now"], {
        "requirements.analyze": [analysis()], "requirements.normalize": [spec()]})
    assert result["status"] == "ended"
    assert result["status_reason"] == "not what we need now"


def test_secret_in_requirement_is_rejected_before_any_llm_call(make_run):
    secret = "\naws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
    ctx, _, backend, result = run(make_run, [], {}, requirement=REQ + secret)
    assert result["status"] == "failed" and "secret" in result["status_reason"]
    assert backend.calls == []


@pytest.mark.parametrize("bad_id", ["RL-FAST", None])
def test_analysis_with_bad_catalog_id_is_retried(make_run, bad_id):
    wrong = analysis(nfr_asks=[{"text": "limit", "source_quote": "Limit clients",
                                "category": "rate_limit", "classification": "SUPPORTED",
                                "catalog_id": bad_id}])
    ctx, _, backend, result = run(make_run, ["a"], {
        "requirements.analyze": [wrong, analysis()], "requirements.normalize": [spec()]})
    assert result["status"] == "running"
    assert "is not one of" in backend.calls[1]["user"]
