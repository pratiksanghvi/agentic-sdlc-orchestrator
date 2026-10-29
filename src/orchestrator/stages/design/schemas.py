"""Structured outputs for the Design stage."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StackOption(BaseModel):
    name: str
    stack_id: str | None = Field(description="id from supported_stacks, or null if not supported")
    language: str
    framework: str
    build_tool: str
    persistence: str
    test_framework: str
    pros: list[str]
    cons: list[str]
    fit: str


class StackDecision(BaseModel):
    options: list[StackOption]
    recommended_stack_id: str
    rationale: str
    consequences: list[str]
    rejected_alternatives: list[str]


class Module(BaseModel):
    name: str
    responsibility: str
    traces: list[str]


class Flow(BaseModel):
    name: str
    steps: list[str]


class TraceRow(BaseModel):
    requirement_id: str
    endpoints: list[str]
    modules: list[str]
    catalog_ids: list[str]


class Design(BaseModel):
    modules: list[Module]
    openapi_yaml: str
    schema_sql: str
    flows: list[Flow]
    error_model: str
    traceability: list[TraceRow]
    dependencies: list[str]
