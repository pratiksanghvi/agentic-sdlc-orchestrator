"""LLM backends: the real Anthropic API and a scripted fake for tests."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any

from orchestrator.llm.client import RawResponse


class AnthropicBackend:
    """Streams every request (long outputs stay clear of HTTP timeouts) with a JSON schema."""

    def __init__(self, api_key: str, timeout_s: float) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=2)

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
    ) -> RawResponse:
        with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": effort,
                "format": {"type": "json_schema", "schema": json_schema},
            },
        ) as stream:
            message = stream.get_final_message()
            response = getattr(stream, "response", None)
            request_id = response.headers.get("request-id") if response is not None else None
        text = next((b.text for b in message.content if b.type == "text"), "")
        usage = message.usage
        return RawResponse(
            text=text,
            stop_reason=message.stop_reason or "",
            usage={
                "input_tokens": usage.input_tokens or 0,
                "output_tokens": usage.output_tokens or 0,
                "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0,
                "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
            },
            request_id=request_id or getattr(message, "_request_id", None),
            raw=message.to_dict(),
        )


class FakeBackend:
    """Scripted responses keyed by call purpose.

    Queue values may be a dict/list (returned as JSON), a RawResponse, or an Exception to raise.
    """

    def __init__(self, scripts: dict[str, list[Any]] | None = None) -> None:
        self.scripts: dict[str, deque] = defaultdict(deque)
        self.calls: list[dict[str, Any]] = []
        for purpose, items in (scripts or {}).items():
            self.scripts[purpose].extend(items)

    def add(self, purpose: str, *items: Any) -> None:
        self.scripts[purpose].extend(items)

    def complete(self, **kwargs: Any) -> RawResponse:
        self.calls.append(kwargs)
        purpose = kwargs["purpose"]
        if not self.scripts[purpose]:
            raise AssertionError(f"FakeBackend has no scripted response for {purpose!r}")
        item = self.scripts[purpose].popleft()
        if isinstance(item, Exception):
            raise item
        if isinstance(item, RawResponse):
            return item
        return RawResponse(
            text=json.dumps(item),
            stop_reason="end_turn",
            usage={"input_tokens": 1000, "output_tokens": 500},
            request_id="req_fake",
        )

