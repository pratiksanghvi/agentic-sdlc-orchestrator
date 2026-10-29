"""Read an OpenAPI 3 document into the small model the orchestrator needs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
_VAR = re.compile(r"^(\{[^}]+\}|\$\{[^}]+\})$")


@dataclass
class Operation:
    method: str
    path: str
    statuses: set[int]
    request_schema: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"


def load(openapi_yaml: str) -> dict[str, Any]:
    return yaml.safe_load(openapi_yaml)


def resolve(doc: dict[str, Any], node: Any, depth: int = 0) -> Any:
    """Inline local $refs (bounded depth)."""
    if depth > 10:
        return node
    if isinstance(node, dict):
        if "$ref" in node and node["$ref"].startswith("#/"):
            target: Any = doc
            for part in node["$ref"][2:].split("/"):
                target = target.get(part, {})
            return resolve(doc, target, depth + 1)
        return {k: resolve(doc, v, depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [resolve(doc, v, depth + 1) for v in node]
    return node


def operations(doc: dict[str, Any]) -> list[Operation]:
    ops = []
    for path, item in (doc.get("paths") or {}).items():
        for method, op in (item or {}).items():
            if method.lower() not in HTTP_METHODS or not isinstance(op, dict):
                continue
            statuses = {int(code) for code in (op.get("responses") or {})
                        if str(code).isdigit()}
            schema = None
            content = ((op.get("requestBody") or {}).get("content") or {})
            json_body = content.get("application/json")
            if json_body and json_body.get("schema"):
                schema = resolve(doc, json_body["schema"])
            ops.append(Operation(method.upper(), path, statuses, schema, op))
    return ops


def match(ops: list[Operation], method: str, path: str) -> Operation | None:
    """Match a concrete or variable path (/links/${code}) against OpenAPI templates."""
    segments = [s for s in path.split("?")[0].split("/") if s]
    for op in ops:
        if op.method != method.upper():
            continue
        template = [s for s in op.path.split("/") if s]
        if len(template) != len(segments):
            continue
        if all(t == s or _VAR.match(t) or _VAR.match(s) or (t.startswith("{"))
               for t, s in zip(template, segments, strict=True)):
            return op
    return None


def sample_value(name: str, schema: dict[str, Any]) -> Any:
    kind = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "integer":
        return 1
    if kind == "number":
        return 1.5
    if kind == "boolean":
        return True
    if kind == "array":
        return [sample_value(name, schema.get("items") or {"type": "string"})]
    if kind == "object":
        return {k: sample_value(k, v) for k, v in (schema.get("properties") or {}).items()}
    if "url" in name.lower() or schema.get("format") == "uri":
        return "https://example.com/some/long/path"
    return "sample"


def wrong_type_value(schema: dict[str, Any]) -> Any:
    return "not-a-number" if schema.get("type") in ("integer", "number") else 12345
