"""Structured outputs for the Requirements stage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NfrCategory = Literal[
    "rate_limit",
    "security",
    "observability_metrics",
    "observability_logging",
    "performance",
    "scalability",
    "availability",
    "data_durability",
    "compliance_privacy",
    "other",
]
NfrClass = Literal["SUPPORTED", "NOT_IN_CATALOG", "UNSUPPORTED_CATEGORY", "VAGUE"]


class Need(BaseModel):
    statement: str = Field(min_length=1)
    source_quote: str = Field(description="exact words from the requirement or clarification")


class NfrAsk(BaseModel):
    text: str
    source_quote: str
    category: NfrCategory
    classification: NfrClass
    catalog_id: str | None = Field(description="catalog ID when SUPPORTED, else null")


class Ambiguity(BaseModel):
    id: str = Field(pattern=r"^Q-\d+$")
    question: str
    why_it_matters: str
    recommended_default: str
    severity: Literal["BLOCKING", "NON_BLOCKING"]
    options: list[str]


class Analysis(BaseModel):
    intent: str
    functional_needs: list[Need]
    nfr_asks: list[NfrAsk]
    ambiguities: list[Ambiguity]
    out_of_scope: list[str]
    stack_constraint: str | None = Field(description="technology the user explicitly required")


class FunctionalRequirement(BaseModel):
    id: str = Field(pattern=r"^FR-\d+$")
    statement: str
    priority: Literal["MVP", "LATER"]
    source: Literal["explicit", "clarification", "assumption"]
    source_quote: str


class NfrParam(BaseModel):
    name: str
    value: str


class NonFunctionalRequirement(BaseModel):
    id: str = Field(pattern=r"^NFR-\d+$")
    catalog_id: str
    statement: str
    params: list[NfrParam]
    source: Literal["explicit", "clarification"]
    source_quote: str


class AcceptanceCriterion(BaseModel):
    id: str = Field(pattern=r"^AC-\d+\.\d+$")
    requirement_id: str
    given: str
    when: str
    then: str
    verification_method: str


class Assumption(BaseModel):
    id: str = Field(pattern=r"^A-\d+$")
    text: str


class SpecDraft(BaseModel):
    title: str
    functional_requirements: list[FunctionalRequirement]
    non_functional_requirements: list[NonFunctionalRequirement]
    acceptance_criteria: list[AcceptanceCriterion]
    assumptions: list[Assumption]
    out_of_scope: list[str]
