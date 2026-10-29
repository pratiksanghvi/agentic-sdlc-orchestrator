"""The run graph: stage subgraphs wired in SDLC order with entry checks between them."""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from orchestrator.runtime.context import RunContext
from orchestrator.stages import (
    codebase,
    design,
    docs,
    implementation,
    release,
    requirements,
    security,
    test_design,
    verify,
)
from orchestrator.stages.common import StageIO

STAGES = ["codebase", "requirements", "design", "test_design", "implementation", "verify",
          "security", "docs", "release"]
BUILDERS = {
    "codebase": codebase.build,
    "requirements": requirements.build,
    "design": design.build,
    "test_design": test_design.build,
    "implementation": implementation.build,
    "verify": verify.build,
    "security": security.build,
    "docs": docs.build,
    "release": release.build,
}


def _continue_or_stop(next_stage: str):
    def route(state: StageIO) -> str:
        return END if state.get("status") in ("ended", "failed") else next_stage
    return route


def _after_release(state: StageIO) -> str:
    if state.get("status") == "restart":  # final REJECT: re-run from the chosen stage
        return state["restart_at"]
    return END


def build_graph(ctx: RunContext, stop_after: str | None = None, start_at: str | None = None):
    g = StateGraph(StageIO)
    order = STAGES[: STAGES.index(stop_after) + 1] if stop_after else STAGES
    if start_at:  # developer aid: resume a pipeline from seeded, approved artifacts
        order = order[order.index(start_at):]
    for name in order:
        g.add_node(name, BUILDERS[name]().compile())
    g.add_edge(START, order[0])
    for current, nxt in zip(order, [*order[1:], END], strict=True):
        if current == "release":
            targets = [s for s in ("requirements", "design", "test_design") if s in order]
            g.add_conditional_edges(current, _after_release, [*targets, END])
        else:
            g.add_conditional_edges(current, _continue_or_stop(nxt),
                                    [nxt, END] if nxt != END else [END])
    conn = sqlite3.connect(ctx.run_dir / "checkpoints.sqlite", check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))
