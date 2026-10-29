"""Runtime for generated acceptance tests (copied verbatim into every acceptance suite).

Executes the approved, structured test cases as black-box HTTP calls against BASE_URL.
Depends only on httpx and the standard library so the suite runs for any service stack.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

_VAR = re.compile(r"\$\{(\w+)\}")
_PATH_TOKEN = re.compile(r"\.([A-Za-z_][\w-]*)|\[(\d+)\]")


class StepFailure(AssertionError):
    pass


def json_path(data: Any, path: str) -> tuple[bool, Any]:
    """Minimal JSON path: $.a.b[0].c  -> (found, value)."""
    if path in ("$", ""):
        return True, data
    if not path.startswith("$"):
        path = "$." + path
    current = data
    for name, index in _PATH_TOKEN.findall(path[1:]):
        if name:
            if not isinstance(current, dict) or name not in current:
                return False, None
            current = current[name]
        else:
            i = int(index)
            if not isinstance(current, list) or i >= len(current):
                return False, None
            current = current[i]
    return True, current


def _substitute(text: str | None, variables: dict[str, Any]) -> str | None:
    if text is None:
        return None
    return _VAR.sub(lambda m: str(variables[m.group(1)]), text)


def _check(op: str, found: bool, actual: Any, expected: str | None, label: str) -> None:
    rendered = actual if isinstance(actual, str) else json.dumps(actual)
    if op == "exists":
        ok = found
    elif op == "not_exists":
        ok = not found
    elif op == "equals":
        ok = found and (rendered == expected or str(actual) == expected
                        or (isinstance(actual, bool) and str(actual).lower() == expected))
    elif op == "contains":
        ok = found and expected is not None and expected in rendered
    elif op == "not_contains":
        ok = not found or expected is None or expected not in rendered
    elif op == "matches":
        ok = found and expected is not None and re.search(expected, rendered) is not None
    else:
        raise StepFailure(f"unknown assertion op {op!r}")
    if not ok:
        raise StepFailure(f"{label}: expected {op} {expected!r}, got {rendered!r}")


def run_step(client: httpx.Client, step: dict[str, Any], variables: dict[str, Any]) -> None:
    path = _substitute(step["path"], variables)
    body = _substitute(step.get("body_json"), variables)
    headers = {h["name"]: _substitute(h["value"], variables) for h in step.get("headers", [])}
    if body is not None:
        headers.setdefault("Content-Type", "application/json")
    response = None
    for _ in range(max(1, step.get("repeat", 1))):
        response = client.request(step["method"], path, content=body, headers=headers,
                                  follow_redirects=step.get("follow_redirects", False))
        forbidden = step.get("expect_status_not")
        if forbidden is not None and response.status_code == forbidden:
            raise StepFailure(f"{step['name']}: {step['method']} {path} returned forbidden "
                              f"status {forbidden}: {response.text[:300]}")
    assert response is not None
    expected = step.get("expect_status")
    if expected is not None and response.status_code != expected:
        raise StepFailure(f"{step['name']}: {step['method']} {path} expected {expected}, got "
                          f"{response.status_code}: {response.text[:500]}")
    try:
        payload: Any = response.json()
        is_json = True
    except ValueError:
        payload, is_json = None, False
    for a in step.get("body_assertions", []):
        if a["target"] == "$body":
            _check(a["op"], True, response.text, a["value"], f"{step['name']} body")
        else:
            found, value = json_path(payload, a["target"]) if is_json else (False, None)
            _check(a["op"], found, value, a["value"], f"{step['name']} {a['target']}")
    for a in step.get("header_assertions", []):
        value = response.headers.get(a["target"])
        _check(a["op"], value is not None, value, a["value"],
               f"{step['name']} header {a['target']}")
    for cap in step.get("capture", []):
        found, value = json_path(payload, cap["json_path"]) if is_json else (False, None)
        if not found:
            raise StepFailure(f"{step['name']}: could not capture {cap['json_path']} from "
                              f"{response.text[:300]}")
        variables[cap["var"]] = value


def run_case(case: dict[str, Any], base_url: str) -> None:
    variables: dict[str, Any] = {}
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        for step in case["steps"]:
            run_step(client, step, variables)
