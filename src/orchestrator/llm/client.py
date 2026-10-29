"""TracedLLM: the only way the orchestrator calls Claude.

Each call asks for JSON matching a Pydantic schema (structured outputs), validates it, retries
within the policy's schema-retry budget with the validation errors fed back, and logs every
attempt in full — prompt, response, tokens, latency, cost, request ID — to the run's audit log.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from orchestrator.llm.costs import CostTracker
from orchestrator.llm.schema import strict_json_schema
from orchestrator.observability.eventlog import EventLog

T = TypeVar("T", bound=BaseModel)
Role = Literal["reasoning", "coding", "fallback"]
MAX_TOKENS_CEILING = 64000


@dataclass
class RawResponse:
    text: str
    stop_reason: str
    usage: dict[str, int]
    request_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class LLMBackend(Protocol):
    def complete(
        self,
        *,
        purpose: str,
        model: str,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        max_tokens: int,
        effort: str,
    ) -> RawResponse: ...


class LLMError(Exception):
    """A structured call failed after exhausting its retry budget."""


@dataclass(frozen=True)
class Structured(Generic[T]):
    value: T
    call_id: str


SemanticValidator = Callable[[Any], list[str]]


class TracedLLM:
    def __init__(
        self,
        backend: LLMBackend,
        log: EventLog,
        costs: CostTracker,
        models: dict[Role, str],
        schema_retries: int,
        max_tokens: int,
    ) -> None:
        self.backend = backend
        self.log = log
        self.costs = costs
        self.models = models
        self.schema_retries = schema_retries
        self.max_tokens = max_tokens

    def structured(
        self,
        *,
        stage: str,
        node: str,
        purpose: str,
        system: str,
        user: str,
        schema: type[T],
        role: Role = "reasoning",
        effort: str = "high",
        validate: SemanticValidator | None = None,
        max_tokens: int | None = None,
    ) -> Structured[T]:
        model = self.models[role]
        json_schema = strict_json_schema(schema)
        tokens = max_tokens or self.max_tokens
        feedback: list[str] = []
        last_problem = ""
        for attempt in range(1, self.schema_retries + 2):
            prompt = user if not feedback else _with_feedback(user, feedback)
            call_id = f"llm-{uuid.uuid4().hex[:12]}"
            started = time.monotonic()
            try:
                response = self.backend.complete(
                    purpose=purpose,
                    model=model,
                    system=system,
                    user=prompt,
                    json_schema=json_schema,
                    max_tokens=tokens,
                    effort=effort,
                )
            except Exception as exc:  # SDK has already retried transient errors
                self._record(call_id, stage, node, purpose, model, attempt, system, prompt,
                             None, started, "api_error", str(exc))
                raise LLMError(f"{purpose}: model call failed: {exc}") from exc

            status, problem, value = self._check(response, schema, validate)
            self._record(call_id, stage, node, purpose, model, attempt, system, prompt,
                         response, started, status, problem)
            self.costs.check_ceiling()
            if status == "ok":
                return Structured(value, call_id)
            last_problem = problem
            if status == "truncated":
                tokens = min(tokens * 2, MAX_TOKENS_CEILING)
            else:
                feedback.append(problem)
        raise LLMError(f"{purpose}: no valid output after {self.schema_retries + 1} attempts: "
                       f"{last_problem}")

    def _check(self, response: RawResponse, schema: type[T], validate: SemanticValidator | None):
        if response.stop_reason == "refusal":
            return "refusal", "model declined the request", None
        if response.stop_reason == "max_tokens":
            return "truncated", "output hit max_tokens", None
        try:
            value = schema.model_validate(json.loads(response.text))
        except (ValueError, ValidationError) as exc:
            return "schema_error", f"output did not match the schema: {exc}", None
        problems = validate(value) if validate else []
        if problems:
            return "validation_error", "; ".join(problems), None
        return "ok", "", value

    def _record(self, call_id, stage, node, purpose, model, attempt, system, prompt,
                response: RawResponse | None, started, status, problem) -> None:
        usage = response.usage if response else {}
        cost = self.costs.add(model, usage) if response else 0.0
        self.log.append(
            "llm_call",
            purpose,
            call_id=call_id,
            stage=stage,
            node=node,
            model=model,
            attempt=attempt,
            schema_retry=attempt > 1,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            response_text=response.text if response else None,
            response_raw=response.raw if response else None,
            stop_reason=response.stop_reason if response else None,
            usage=usage,
            latency_ms=round((time.monotonic() - started) * 1000),
            cost_usd=round(cost, 6),
            request_id=response.request_id if response else None,
            status=status,
            parsed_ok=status == "ok",
            problem=problem,
        )


def _with_feedback(user: str, feedback: list[str]) -> str:
    notes = "\n".join(f"- {f}" for f in feedback)
    return (
        f"{user}\n\n<previous_attempt_rejected>\nYour previous output was rejected for these "
        f"reasons. Produce a corrected, complete output.\n{notes}\n</previous_attempt_rejected>"
    )
