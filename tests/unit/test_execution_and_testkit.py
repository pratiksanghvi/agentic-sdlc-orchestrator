import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from orchestrator.config import load_config
from orchestrator.execution import runner
from orchestrator.execution.git_ops import ProductRepo
from orchestrator.execution.service import ServiceProcess
from orchestrator.guardrails import code as code_guard
from orchestrator.observability.eventlog import EventLog
from orchestrator.observability.metrics import run_metrics
from orchestrator.stages.release.graph import next_version
from orchestrator.testkit import acceptance_support as support
from orchestrator.testkit import generator

# ---------- acceptance runtime against a tiny real HTTP server ----------


class _Handler(BaseHTTPRequestHandler):
    store: dict = {}

    def log_message(self, *args):
        pass

    def _send(self, status, body=None, headers=None):
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        data = json.dumps(body).encode() if body is not None else b""
        if body is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        code = f"c{len(self.store) + 1}"
        self.store[code] = payload["url"]
        self._send(201, {"code": code})

    def do_GET(self):
        code = self.path.rsplit("/", 1)[-1]
        if code in self.store:
            self._send(302, None, {"Location": self.store[code]})
        else:
            self._send(404, {"title": "not found"})


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def _step(**kw):
    base = {"name": "s", "method": "GET", "path": "/", "headers": [], "body_json": None,
            "repeat": 1, "expect_status": None, "expect_status_not": None,
            "body_assertions": [], "header_assertions": [], "capture": [],
            "follow_redirects": False}
    return {**base, **kw}


CASE = {"id": "TC-1", "covers": "AC-1.1", "title": "create then redirect", "kind": "positive",
        "phase": "main", "steps": [
            _step(name="create", method="POST", path="/links", body_json='{"url": "https://x.io"}',
                  expect_status=201, capture=[{"var": "code", "json_path": "$.code"}],
                  body_assertions=[{"target": "$.code", "op": "matches", "value": "^c\\d+$"}]),
            _step(name="redirect", path="/r/${code}", expect_status=302,
                  header_assertions=[{"target": "location", "op": "equals",
                                      "value": "https://x.io"}])]}


def test_run_case_passes_and_fails_precisely(server):
    support.run_case(CASE, server)
    bad = json.loads(json.dumps(CASE))
    bad["steps"][1]["expect_status"] = 301
    with pytest.raises(support.StepFailure, match="expected 301, got 302"):
        support.run_case(bad, server)


def test_assertion_values_use_captured_variables(server):
    case = json.loads(json.dumps(CASE))
    case["steps"].append(_step(name="again", method="POST", path="/links",
                               body_json='{"url": "https://y.io"}', expect_status=201,
                               body_assertions=[{"target": "$.code", "op": "not_contains",
                                                 "value": "${code}"}]))
    support.run_case(case, server)


def test_json_path():
    data = {"a": {"b": [{"c": 1}]}}
    assert support.json_path(data, "$.a.b[0].c") == (True, 1)
    assert support.json_path(data, "$.a.x") == (False, None)


def test_generated_suite_runs_with_pytest(tmp_path, server):
    for name, content in generator.generate([CASE]).items():
        (tmp_path / name).write_text(content)
    result = runner.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                        tmp_path, 60, env={"BASE_URL": server, "PYTHONPATH": str(tmp_path)})
    assert result.ok, result.output
    assert generator.expected_test_names([CASE]) == {"test_tc_1"}


# ---------- runner, service readiness, git ----------


def test_clean_env_never_passes_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    env = runner.clean_env({"PORT": "1"})
    assert "ANTHROPIC_API_KEY" not in env and env["PORT"] == "1"


def test_runner_timeout(tmp_path):
    result = runner.run([sys.executable, "-c", "import time; time.sleep(5)"], tmp_path, 1)
    assert result.timed_out and not result.ok


SERVER_SCRIPT = """
import os, socket, sys, time
port = int(os.environ["PORT"])
s = socket.socket(); s.bind(("127.0.0.1", port)); s.listen()
print(f"SERVICE_READY port={port}", flush=True)
time.sleep(30)
"""


def test_service_ready_via_log_line(tmp_path):
    script = tmp_path / "svc.py"
    script.write_text(SERVER_SCRIPT)
    svc = ServiceProcess([sys.executable, str(script)], tmp_path, tmp_path / "svc.log", "PORT",
                         r"^SERVICE_READY port=(\d+)$", "Traceback", {})
    result = svc.start(20)
    svc.stop()
    assert result.ok and result.reason == "ready"


def test_service_exit_before_ready_fails_fast(tmp_path):
    svc = ServiceProcess([sys.executable, "-c", "raise SystemExit(3)"], tmp_path,
                         tmp_path / "svc.log", "PORT", r"^SERVICE_READY port=(\d+)$", "x", {})
    result = svc.start(20)
    assert not result.ok and "exited with code 3" in result.reason


def test_product_repo_branch_backup_rollback_release(tmp_path):
    repo = ProductRepo(tmp_path / "product")
    repo.ensure()
    assert repo.backup("run-1") == "pre-impl/run-1"
    repo.start_run_branch("run-1")
    (repo.path / "a.txt").write_text("x")
    assert repo.commit_all("T-1\n\nRun: run-1")
    failed = repo.rollback("run-1")
    assert failed == "failed/run-1" and not (repo.path / "a.txt").exists()
    repo.start_run_branch("run-2")
    (repo.path / "b.txt").write_text("y")
    repo.commit_all("T-1\n\nRun: run-2")
    repo.release("run-2", "v0.1.0")
    assert (repo.path / "b.txt").exists() and repo.tags() == ["v0.1.0"]


# ---------- guardrails ----------

POM = """<project xmlns="http://maven.apache.org/POM/4.0.0">
<parent><groupId>org.springframework.boot</groupId>
<artifactId>spring-boot-starter-parent</artifactId><version>3.5.7</version></parent>
<dependencies>
 <dependency><groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-web</artifactId></dependency>
 <dependency><groupId>org.xerial</groupId><artifactId>sqlite-jdbc</artifactId>
  <version>3.0.0</version></dependency>
 <dependency><groupId>com.evil</groupId><artifactId>miner</artifactId></dependency>
</dependencies>
<build><plugins><plugin><artifactId>maven-surefire-plugin</artifactId></plugin></plugins></build>
</project>"""


@pytest.fixture
def java_stack():
    root = Path(__file__).resolve().parents[2]
    return load_config(root, env={"ANTHROPIC_API_KEY": "k"}).stacks.stacks[
        "java21-springboot3-maven"]


def test_maven_allowlist(java_stack):
    problems = code_guard.check_maven_dependencies(POM, java_stack)
    assert any("com.evil:miner" in p for p in problems)
    assert any("must use version 3.50.3.0" in p for p in problems)
    assert len(problems) == 2


def test_path_guardrails(java_stack):
    problems = code_guard.check_paths(
        ["src/main/java/A.java", "../x", "acceptance/test.py", "Dockerfile"], java_stack,
        ["**/acceptance/**", "acceptance/**"])
    assert len(problems) == 3


def test_suppression_markers_rejected():
    assert code_guard.check_suppressions({"A.java": "// NOSONAR"})


# ---------- release + metrics ----------


def test_next_version():
    assert next_version([]) == "v0.1.0"
    assert next_version(["v0.1.0", "v0.2.0", "junk"]) == "v0.3.0"


def test_metrics_from_log(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    log.append("event", "run_started", run_id="r")
    log.append("llm_call", "p", stage="s", node="n", model="m", attempt=1, schema_retry=False,
               usage={"input_tokens": 10, "output_tokens": 5}, latency_ms=100, cost_usd=0.01,
               status="ok")
    log.append("event", "verification", passed=False)
    log.append("human_interaction", "g", wait_ms=50)
    log.append("event", "verification", passed=True)
    log.append("decision", "final_verdict", decision="ACCEPT")
    m = run_metrics(log)
    assert m["llm"]["calls"] == 1 and m["llm"]["per_stage"]["s"]["first_pass_rate"] == 1.0
    assert m["reliability"]["verification_attempts"] == 2
    assert m["reliability"]["mttr_ms"] is not None
    assert m["final_verdict"] == "ACCEPT" and m["audit_chain_intact"]
