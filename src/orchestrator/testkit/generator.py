"""4b — turn the approved, structured test plan into an executable pytest suite.

Generation is deterministic (no LLM): every approved case becomes exactly one `test_tc_<n>`
function, so nothing can be added, weakened or skipped between approval and execution.
"""

from __future__ import annotations

import json
import re
from importlib import resources

CONFTEST = '''import os

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ["BASE_URL"]
'''


def _fn(case_id: str) -> str:
    return "test_" + re.sub(r"\W", "_", case_id.lower())


def _module(cases: list[dict], phase: str) -> str:
    lines = [
        f'"""Acceptance tests, phase {phase!r}. Generated from the approved test plan; '
        'do not edit."""',
        "",
        "import json",
        "from pathlib import Path",
        "",
        "from acceptance_support import run_case",
        "",
        'CASES = {c["id"]: c for c in json.loads((Path(__file__).parent / "cases.json")'
        '.read_text())}',
        "",
    ]
    for case in cases:
        title = case["title"].replace('"""', "'")
        lines += ["", f"def {_fn(case['id'])}(base_url):",
                  f'    """{case["id"]} ({case["covers"]}): {title}"""',
                  f'    run_case(CASES["{case["id"]}"], base_url)', ""]
    return "\n".join(lines)


def generate(cases: list[dict]) -> dict[str, str]:
    support = resources.files("orchestrator.testkit").joinpath("acceptance_support.py")
    files = {
        "acceptance_support.py": support.read_text(encoding="utf-8"),
        "conftest.py": CONFTEST,
        "cases.json": json.dumps(cases, indent=2),
    }
    for phase in ("main", "isolated"):
        selected = [c for c in cases if c["phase"] == phase]
        if selected:
            files[f"test_acceptance_{phase}.py"] = _module(selected, phase)
    return files


def expected_test_names(cases: list[dict]) -> set[str]:
    return {_fn(c["id"]) for c in cases}
