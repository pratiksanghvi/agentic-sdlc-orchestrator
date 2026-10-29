"""Drives a run: invokes the graph and turns each pause (interrupt) into a HumanGate prompt."""

from __future__ import annotations

from typing import Any

from langgraph.types import Command

from orchestrator.human.gate import Option
from orchestrator.runtime.context import RunContext


def answer_interrupt(ctx: RunContext, payload: dict[str, Any]) -> Any:
    gate = ctx.gate
    kind = payload["kind"]
    if kind == "choose":
        decision = gate.choose(
            payload["gate"],
            payload["title"],
            payload["summary"],
            [Option(o["key"], o["label"], o["needs_reason"], o["confirm"])
             for o in payload["options"]],
            artifact=payload.get("artifact"),
        )
        return {"key": decision.key, "reason": decision.reason}
    if kind == "questions":
        answers = []
        for q in payload["questions"]:
            opts = "\n".join(f"  {i}. {o}" for i, o in enumerate(q["options"], 1))
            text = f"{q['id']}: {q['question']}\n  ({q['why']})\n{opts}\nAnswer with a number, " \
                   "your own text, or Enter for the default."
            raw = gate.text(payload["gate"], text, default=q["default"])
            if raw.isdigit() and 1 <= int(raw) <= len(q["options"]):
                raw = q["options"][int(raw) - 1]
            answers.append({"id": q["id"], "answer": raw})
        return answers
    if kind == "confirm":
        return gate.confirm(payload["gate"], payload["question"])
    raise ValueError(f"unknown interrupt kind: {kind}")


def run_graph(ctx: RunContext, graph, initial: dict[str, Any]) -> dict[str, Any]:
    config = {"configurable": {"thread_id": ctx.run_id}, "recursion_limit": 200}
    ctx.log.append("event", "graph_started")
    result = graph.invoke(initial, config)
    while result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        result = graph.invoke(Command(resume=answer_interrupt(ctx, payload)), config)
    status = result.get("status", "running")
    ctx.log.append("event", "graph_finished", status=status,
                   reason=result.get("status_reason", ""), artifacts=result.get("artifacts", {}))
    return result
