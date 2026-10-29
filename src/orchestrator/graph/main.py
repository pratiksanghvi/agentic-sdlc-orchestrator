"""The run graph: stage subgraphs wired in SDLC order with entry checks between them."""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from orchestrator.runtime.context import RunContext
from orchestrator.stages import design, requirements
from orchestrator.stages.common import StageIO

STAGES = ["requirements", "design"]


def _continue_or_stop(next_stage: str):
    def route(state: StageIO) -> str:
        return END if state.get("status") in ("ended", "failed") else next_stage
    return route


def build_graph(ctx: RunContext, stop_after: str | None = None):
    g = StateGraph(StageIO)
    builders = {"requirements": requirements.build, "design": design.build}
    order = STAGES[: STAGES.index(stop_after) + 1] if stop_after else STAGES
    for name in order:
        g.add_node(name, builders[name]().compile())
    g.add_edge(START, order[0])
    for current, nxt in zip(order, [*order[1:], END], strict=True):
        g.add_conditional_edges(current, _continue_or_stop(nxt), [nxt, END] if nxt != END
                                else [END])
    conn = sqlite3.connect(ctx.run_dir / "checkpoints.sqlite", check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))
