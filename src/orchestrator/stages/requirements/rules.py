"""Deterministic checks and fixed texts for the Requirements stage (R5 + NFR policy)."""

from __future__ import annotations

import re

from orchestrator.config.models import NfrCatalog

CATEGORY_LABELS = {
    "rate_limit": "rate limiting",
    "security": "security",
    "observability_metrics": "observability (metrics)",
    "observability_logging": "observability (logging)",
    "performance": "performance",
    "scalability": "scalability",
    "availability": "availability",
    "data_durability": "data durability",
    "compliance_privacy": "compliance / privacy",
    "other": "non-functional",
}

SUPPORTED_SUMMARY = (
    "rate limiting (per-client request limits), security (input validation against the API "
    "contract) and observability (request metrics)"
)

TECH_TERMS = re.compile(
    r"\b(java|spring|springboot|python|fastapi|flask|django|golang|node\.?js|express|postgres(ql)?|"
    r"mysql|sqlite|redis|mongodb|kafka|docker|kubernetes|react|maven|gradle)\b",
    re.IGNORECASE,
)


def not_supported_message(text: str, category: str, classification: str) -> str:
    label = CATEGORY_LABELS.get(category, "non-functional")
    if classification == "NOT_IN_CATALOG":
        why = (f"It is a {label} requirement, but the MVP catalog has no entry that the "
               "orchestrator can build and validate for it")
    else:
        why = f"It is a {label} requirement, which the MVP does not support"
    return (
        f'Thanks for including "{text}". {why}. The orchestrator MVP supports non-functional '
        f"requirements for {SUPPORTED_SUMMARY} only, so this item has been recorded as "
        "Not supported in MVP and will not be built or validated. It is listed in the final "
        "engineering summary for future consideration."
    )


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip(" .,;:!?\"'")


def quote_in_sources(quote: str, sources: list[str]) -> bool:
    q = normalize(quote)
    return bool(q) and any(q in normalize(s) for s in sources)


def validate_analysis(analysis, catalog: NfrCatalog) -> list[str]:
    problems = []
    ids = [a.id for a in analysis.ambiguities]
    if len(ids) != len(set(ids)):
        problems.append("ambiguity ids must be unique")
    for ask in analysis.nfr_asks:
        if ask.classification == "SUPPORTED" and ask.catalog_id not in catalog.entries:
            problems.append(
                f'NFR "{ask.text}" is SUPPORTED but catalog_id {ask.catalog_id!r} is not one of '
                f"{sorted(catalog.entries)}"
            )
        if ask.classification != "SUPPORTED" and ask.catalog_id:
            problems.append(f'NFR "{ask.text}": catalog_id must be null unless SUPPORTED')
    return problems


def validate_spec(spec: dict, catalog: NfrCatalog, sources: list[str]) -> list[str]:
    """R5 deterministic checks. `sources` = raw requirement + clarification answers."""
    problems: list[str] = []
    frs = spec["functional_requirements"]
    nfrs = spec["non_functional_requirements"]
    acs = spec["acceptance_criteria"]

    for label, items in (("functional requirement", frs), ("NFR", nfrs),
                         ("acceptance criterion", acs), ("assumption", spec["assumptions"])):
        ids = [i["id"] for i in items]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            problems.append(f"duplicate {label} ids: {', '.join(dupes)}")

    req_ids = {r["id"] for r in frs} | {n["id"] for n in nfrs}
    covered = {ac["requirement_id"] for ac in acs}
    for ac in acs:
        if ac["requirement_id"] not in req_ids:
            problems.append(f"{ac['id']} refers to unknown requirement {ac['requirement_id']}")
    for fr in frs:
        if fr["priority"] == "MVP" and fr["id"] not in covered:
            problems.append(f"{fr['id']} is MVP but has no acceptance criterion")
        if fr["source"] != "assumption" and not quote_in_sources(fr["source_quote"], sources):
            problems.append(f"{fr['id']} source_quote is not found in the user's words")

    for nfr in nfrs:
        entry = catalog.entries.get(nfr["catalog_id"])
        if entry is None:
            problems.append(f"{nfr['id']} uses unknown catalog id {nfr['catalog_id']}")
            continue
        if nfr["source"] not in ("explicit", "clarification"):
            problems.append(f"{nfr['id']} must come from the user (explicit or clarification)")
        if not quote_in_sources(nfr["source_quote"], sources):
            problems.append(
                f"{nfr['id']} source_quote \"{nfr['source_quote']}\" is not found in the user's "
                "words; NFRs may only be built when the user asked for them"
            )
        unknown = {p["name"] for p in nfr["params"]} - set(entry.params)
        if unknown:
            problems.append(f"{nfr['id']} has params not in the catalog: {sorted(unknown)}")

    for item in frs:
        if TECH_TERMS.search(item["statement"]):
            problems.append(f"{item['id']} names a technology; requirements must be tech-neutral")
    for ac in acs:
        text = " ".join((ac["given"], ac["when"], ac["then"]))
        if TECH_TERMS.search(text):
            problems.append(f"{ac['id']} names a technology; criteria must be tech-neutral")
    if not frs:
        problems.append("the spec has no functional requirements")
    return problems
