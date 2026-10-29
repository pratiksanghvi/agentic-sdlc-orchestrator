"""Reliability and cost metrics derived only from a run's hash-chained event log."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from orchestrator.observability.eventlog import EventLog


def _ts(record: dict) -> datetime:
    return datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


def run_metrics(log: EventLog) -> dict[str, Any]:
    records = log.records()
    if not records:
        return {}
    start, end = _ts(records[0]), _ts(records[-1])
    total_ms = (end - start).total_seconds() * 1000
    llm = [r for r in records if r["kind"] == "llm_call"]
    humans = [r for r in records if r["kind"] == "human_interaction"]
    events = [r for r in records if r["kind"] == "event"]
    decisions = [r for r in records if r["kind"] == "decision"]

    per_stage: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    latencies: dict[str, list[int]] = defaultdict(list)
    for r in llm:
        d = r["data"]
        s = per_stage[d["stage"]]
        s["calls"] += 1
        s["input_tokens"] += d["usage"].get("input_tokens", 0)
        s["output_tokens"] += d["usage"].get("output_tokens", 0)
        s["cost_usd"] += d["cost_usd"]
        s["first_attempts"] += d["attempt"] == 1
        s["first_attempt_ok"] += d["attempt"] == 1 and d["status"] == "ok"
        latencies[d["stage"]].append(d["latency_ms"])
    for stage, s in per_stage.items():
        s["first_pass_rate"] = round(s["first_attempt_ok"] / s["first_attempts"], 3) \
            if s["first_attempts"] else None
        s["latency_p50_ms"] = int(median(latencies[stage]))
        s["latency_p95_ms"] = _p95(latencies[stage])
        s["cost_usd"] = round(s["cost_usd"], 4)

    human_wait = sum(r["data"].get("wait_ms", 0) for r in humans)
    tool_ms = sum(r["data"].get("duration_ms", 0) for r in events
                  if r["name"] in ("compile", "build", "acceptance_phase"))
    verifications = [r for r in events if r["name"] == "verification"]

    # MTTR: from a failed verification to the next passing one (total and automatic-only)
    episodes, start_fail = [], None
    for r in verifications:
        if not r["data"]["passed"] and start_fail is None:
            start_fail = r
        elif r["data"]["passed"] and start_fail is not None:
            span = (_ts(r) - _ts(start_fail)).total_seconds() * 1000
            waits = sum(h["data"].get("wait_ms", 0) for h in humans
                        if _ts(start_fail) <= _ts(h) <= _ts(r))
            episodes.append((span, span - waits))
            start_fail = None

    approvals = [d for d in decisions if d["name"] == "approval"]
    gates: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for a in approvals:
        gates[a["data"]["gate"]][a["data"]["decision"]] += 1
    verdict = next((d["data"]["decision"] for d in reversed(decisions)
                    if d["name"] == "final_verdict"), None)
    finished = next((r for r in reversed(events) if r["name"] == "graph_finished"), None)

    return {
        "run_id": records[0]["data"].get("run_id"),
        "status": finished["data"]["status"] if finished else "in_progress",
        "final_verdict": verdict,
        "end_to_end_ms": round(total_ms),
        "time_split_ms": {
            "human_wait": human_wait,
            "tools": tool_ms,
            "agent_and_orchestration": round(max(total_ms - human_wait - tool_ms, 0)),
        },
        "llm": {
            "calls": len(llm),
            "schema_retries": sum(1 for r in llm if r["data"]["schema_retry"]),
            "failed_calls": sum(1 for r in llm if r["data"]["status"] != "ok"),
            "input_tokens": sum(r["data"]["usage"].get("input_tokens", 0) for r in llm),
            "output_tokens": sum(r["data"]["usage"].get("output_tokens", 0) for r in llm),
            "cost_usd": round(sum(r["data"]["cost_usd"] for r in llm), 4),
            "per_stage": {k: dict(v) for k, v in per_stage.items()},
        },
        "reliability": {
            "step_retries": sum(1 for r in events if r["name"] == "step_retry"),
            "task_attempts_failed": sum(1 for r in events if r["name"] == "task_attempt_failed"),
            "verification_attempts": len(verifications),
            "fixes": sum(1 for d in decisions if d["name"] == "fix_applied"),
            "rollbacks": sum(1 for d in decisions if d["name"] == "rollback"),
            "mttr_ms": round(sum(e[0] for e in episodes) / len(episodes)) if episodes else None,
            "mttr_auto_only_ms": round(sum(e[1] for e in episodes) / len(episodes))
            if episodes else None,
        },
        "gates": {k: dict(v) for k, v in gates.items()},
        "audit_chain_intact": log.verify()[0],
    }


def all_runs(root: Path) -> dict[str, Any]:
    runs = []
    for path in sorted((root / "runs").glob("*/logs/events.jsonl")):
        m = run_metrics(EventLog(path))
        if m:
            runs.append(m)
    finished = [r for r in runs if r["status"] in ("completed", "ended", "failed")]
    accepted = [r for r in runs if r["final_verdict"] == "ACCEPT"]
    return {
        "runs": len(runs),
        "finished": len(finished),
        "accepted": len(accepted),
        "success_rate": round(len(accepted) / len(finished), 3) if finished else None,
        "total_cost_usd": round(sum(r["llm"]["cost_usd"] for r in runs), 4),
        "rollbacks": sum(r["reliability"]["rollbacks"] for r in runs),
        "fixes": sum(r["reliability"]["fixes"] for r in runs),
    }


def trace_lines(log: EventLog) -> list[str]:
    lines = []
    for r in log.records():
        d = r["data"]
        where = "/".join(x for x in (d.get("stage"), d.get("node")) if x)
        extra = ""
        if r["kind"] == "llm_call":
            extra = (f"{d['model']} {d['status']} {d['latency_ms']}ms "
                     f"in={d['usage'].get('input_tokens', 0)} "
                     f"out={d['usage'].get('output_tokens', 0)} ${d['cost_usd']:.4f}")
        elif r["kind"] == "human_interaction":
            extra = f"answer={d.get('answer')!r} wait={d.get('wait_ms')}ms"
        elif r["kind"] == "decision":
            extra = f"by={d.get('made_by', '')} {d.get('decision', '')}".strip()
        elif "duration_ms" in d:
            extra = f"{d['duration_ms']}ms"
        lines.append(f"{r['seq']:>5} {r['ts'][11:23]} {r['kind']:<17} {r['name']:<28} "
                     f"{where:<34} {extra}")
    return lines
