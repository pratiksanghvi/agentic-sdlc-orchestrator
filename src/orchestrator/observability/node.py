"""@observed_node: wraps every LangGraph node so each step's start, end, duration and outcome
is logged. A human-gate interrupt is logged as a pause, not a failure."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from langgraph.errors import GraphInterrupt

from orchestrator.runtime.context import get_context


def observed_node(stage: str, name: str) -> Callable:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(state: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
            log = get_context(state["run_id"]).log
            log.append("event", "node_started", stage=stage, node=name)
            started = time.monotonic()

            def finish(event: str, **extra: Any) -> None:
                elapsed = round((time.monotonic() - started) * 1000)
                log.append("event", event, stage=stage, node=name, duration_ms=elapsed, **extra)

            try:
                result = fn(state, *args, **kwargs)
            except GraphInterrupt:
                finish("node_paused")
                raise
            except Exception as exc:
                finish("node_failed", error=f"{type(exc).__name__}: {exc}")
                raise
            finish("node_finished")
            return result

        wrapper.observed = True  # type: ignore[attr-defined]
        return wrapper

    return decorator
