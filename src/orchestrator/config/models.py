"""Typed configuration, validated at startup. Invalid config refuses to start."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------- application.properties (secrets + user-specific) ----------


class AppSettings(Strict):
    anthropic_api_key: str = Field(repr=False)
    approver_name: str = "reviewer"
    model_reasoning: str = "claude-opus-5-5"
    model_coding: str = "claude-sonnet-5-5"
    model_fallback: str = "claude-opus-5-5"

    @field_validator("anthropic_api_key")
    @classmethod
    def _key_present(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "anthropic.api_key is empty: set it in config/application.properties "
                "or the ANTHROPIC_API_KEY environment variable"
            )
        return v.strip()


# ---------- policy.yaml ----------


class InputPolicy(Strict):
    max_bytes: int = Field(gt=0)


class LlmPolicy(Strict):
    schema_retries: int = Field(ge=0, le=5)
    max_tokens: int = Field(gt=0)
    request_timeout_s: int = Field(gt=0)


class Budgets(Strict):
    step_retries: int = Field(ge=0, le=5)
    stronger_model_attempts: int = Field(ge=0, le=3)
    verify_auto_fixes: int = Field(ge=0, le=10)
    clarification_rounds: int = Field(ge=0, le=5)
    cost_usd_confirm: float = Field(gt=0)


class Timeouts(Strict):
    compile_s: int = Field(gt=0)
    build_s: int = Field(gt=0)
    test_s: int = Field(gt=0)
    startup_s: int = Field(gt=0)
    acceptance_s: int = Field(gt=0)


class Contract(Strict):
    port_env: str
    ready_line_regex: str
    startup_error_regex: str

    @field_validator("ready_line_regex", "startup_error_regex")
    @classmethod
    def _compiles(cls, v: str) -> str:
        re.compile(v)
        return v


class PathPolicy(Strict):
    forbidden: list[str]


class GatePolicy(Strict):
    min_reason_chars: int = Field(ge=0)


class SemgrepPolicy(Strict):
    report_severities: list[Literal["ERROR", "WARNING", "INFO"]]


class Policy(Strict):
    input: InputPolicy
    llm: LlmPolicy
    budgets: Budgets
    timeouts: Timeouts
    contract: Contract
    paths: PathPolicy
    gates: GatePolicy
    semgrep: SemgrepPolicy


# ---------- stacks.yaml ----------


class StackCommands(Strict):
    compile: list[str] = Field(min_length=1)
    build_and_unit_test: list[str] = Field(min_length=1)
    run: list[str] = Field(min_length=1)


class Stack(Strict):
    validated: bool
    language: Literal["java", "python", "go"]
    datastore: Literal["sqlite"]
    commands: StackCommands
    path_allowlist: list[str] = Field(min_length=1)
    dependencies: dict[str, str]
    guidance: str = ""  # stack-specific instructions given to the implementation agent


class StackCatalog(Strict):
    stacks: dict[str, Stack] = Field(min_length=1)


# ---------- nfr_catalog.yaml ----------

NfrCategory = Literal["rate_limit", "security", "observability"]


class NfrEntry(Strict):
    category: NfrCategory
    capability: str
    params: dict[str, Any]
    implementation: dict[str, str]
    validation: str


class NfrCatalog(Strict):
    supported_categories: list[NfrCategory]
    entries: dict[str, NfrEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _entries_in_supported_categories(self) -> NfrCatalog:
        for nfr_id, entry in self.entries.items():
            if entry.category not in self.supported_categories:
                raise ValueError(f"{nfr_id}: category {entry.category} is not supported")
        return self


# ---------- pricing.yaml ----------


class ModelPrice(Strict):
    input: float = Field(ge=0)
    output: float = Field(ge=0)
    cache_write: float = Field(ge=0)
    cache_read: float = Field(ge=0)


class Pricing(Strict):
    models: dict[str, ModelPrice] = Field(min_length=1)


# ---------- everything together ----------


class Config(Strict):
    app: AppSettings
    policy: Policy
    stacks: StackCatalog
    nfr: NfrCatalog
    pricing: Pricing
    # sha256 of each governance file, recorded on every run (change control)
    governance_hashes: dict[str, str]

    @model_validator(mode="after")
    def _cross_checks(self) -> Config:
        for model in {self.app.model_reasoning, self.app.model_coding, self.app.model_fallback}:
            if model not in self.pricing.models:
                raise ValueError(f"model {model} has no entry in config/pricing.yaml")
        for nfr_id, entry in self.nfr.entries.items():
            for stack_id in entry.implementation:
                if stack_id not in self.stacks.stacks:
                    raise ValueError(f"{nfr_id}: implementation for unknown stack {stack_id}")
        return self
