"""Test-plan model shared by Test Design (cases) and the acceptance-test writer (code)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Header(BaseModel):
    name: str
    value: str


class Assertion(BaseModel):
    target: str = Field(description='JSON path like "$.shortCode", or a header name for headers')
    op: Literal["equals", "exists", "not_exists", "contains", "not_contains", "matches"]
    value: str | None = Field(description="expected value as a string; null for exists checks")


class Capture(BaseModel):
    var: str = Field(description="variable name usable later as ${var}")
    json_path: str


class Step(BaseModel):
    name: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(description="path from the OpenAPI document; use ${var} for captured values")
    headers: list[Header]
    body_json: str | None = Field(description="JSON request body as a string, or null")
    repeat: int = Field(description="send the same request this many times; normally 1")
    expect_status: int | None = Field(description="exact status expected on the last send")
    expect_status_not: int | None = Field(description="status that must NOT be returned")
    body_assertions: list[Assertion]
    header_assertions: list[Assertion]
    capture: list[Capture]
    follow_redirects: bool = Field(description="always false for redirect checks")


class TestCase(BaseModel):
    __test__ = False  # not a pytest class

    id: str = Field(pattern=r"^TC-\d+$")
    covers: str = Field(description="the AC id (or NFR id for non-functional cases) verified")
    title: str
    kind: Literal["positive", "negative", "edge", "nfr"]
    phase: Literal["main", "isolated"] = Field(
        description='"isolated" only for cases that exhaust shared limits (rate limiting)')
    steps: list[Step]


class FunctionalCases(BaseModel):
    cases: list[TestCase]
