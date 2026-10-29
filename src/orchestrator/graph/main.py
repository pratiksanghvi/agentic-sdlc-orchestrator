"""The run graph: stage subgraphs wired in SDLC order with entry checks between them."""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from orchestrator.runtime.context import RunContext
from orchestrator.stages import requirements
from orchestrator.stages.common import StageIO

STAGES = ["requirements"]


def _continue_or_stop(next_stage: str):
    def route(state: StageIO) -> str:
        return END if state.get("status") in ("ended", "failed") else next_stage
    return route


def build_graph(ctx: RunContext, stop_after: str | None = None):
    g = StateGraph(StageIO)
    g.add_node("requirements", requirements.build().compile())
    g.add_edge(START, "requirements")
    g.add_conditional_edges("requirements", _continue_or_stop(END), [END])
    conn = sqlite3.connect(ctx.run_dir / "checkpoints.sqlite", check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))
