"""Convert Pydantic models into JSON schemas accepted by structured outputs.

Structured outputs need every object closed (`additionalProperties: false`) with every
property required. Value constraints (lengths, ranges, patterns) are stripped from the wire
schema and enforced afterwards by Pydantic validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_STRIP = {
    "title",
    "default",
    "examples",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "format",
}
# keys whose values are maps of user-chosen names (field names, definition names)
_NAME_MAPS = {"properties", "$defs"}


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _close(model.model_json_schema())


def _close(node: Any) -> Any:
    if isinstance(node, list):
        return [_close(n) for n in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _NAME_MAPS:
            out[key] = {name: _close(sub) for name, sub in value.items()}
        elif key not in _STRIP:
            out[key] = _close(value)
    if out.get("type") == "object" or "properties" in out:
        if isinstance(node.get("additionalProperties"), dict):
            raise TypeError(
                "LLM output schemas cannot contain free-form dict fields; use a list of objects"
            )
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}))
    return out
