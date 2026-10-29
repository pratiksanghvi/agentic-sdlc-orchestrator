"""Deterministic Design checks (D2 stack rules, D3 NFR lookup, D5 validation) and rendering."""

from __future__ import annotations

import re
import sqlite3

import yaml

from orchestrator.config.models import Config

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
OPERATIONAL_PATHS = {"/metrics", "/health"}


def stacks_for_spec(config: Config, spec: dict) -> dict[str, list[str]]:
    """stack_id -> NFR catalog ids that have no implementation for that stack."""
    needed = {n["catalog_id"] for n in spec["non_functional_requirements"]}
    return {
        stack_id: sorted(c for c in needed if stack_id not in config.nfr.entries[c].implementation)
        for stack_id in config.stacks.stacks
    }


def validate_stack(decision, config: Config, spec: dict,
                   existing: str | None = None) -> list[str]:
    missing = stacks_for_spec(config, spec)
    sid = decision.recommended_stack_id
    if existing and sid != existing:
        return [f"this is a change to an existing {existing} service; keep that stack"]
    if sid not in config.stacks.stacks:
        return [f"recommended_stack_id {sid!r} is not one of {sorted(config.stacks.stacks)}"]
    if missing[sid]:
        return [f"{sid} has no catalog implementation for {missing[sid]}; choose another stack"]
    return []


def nfr_plan(config: Config, spec: dict, stack_id: str) -> list[dict]:
    plan = []
    for nfr in spec["non_functional_requirements"]:
        entry = config.nfr.entries[nfr["catalog_id"]]
        params = {name: p.get("default") for name, p in entry.params.items()}
        params.update({p["name"]: p["value"] for p in nfr["params"]})
        plan.append({
            "requirement_id": nfr["id"],
            "catalog_id": nfr["catalog_id"],
            "category": entry.category,
            "params": params,
            "implementation": entry.implementation[stack_id],
            "validation": entry.validation,
        })
    return plan


def openapi_operations(openapi_yaml: str) -> tuple[set[str], list[str]]:
    """Return ({"METHOD /path"}, problems)."""
    try:
        doc = yaml.safe_load(openapi_yaml)
    except yaml.YAMLError as exc:
        return set(), [f"openapi_yaml is not valid YAML: {exc}"]
    if not isinstance(doc, dict) or not str(doc.get("openapi", "")).startswith("3."):
        return set(), ["openapi_yaml must be an OpenAPI 3.x document"]
    paths = doc.get("paths") or {}
    if not paths:
        return set(), ["openapi_yaml has no paths"]
    ops, problems = set(), []
    for path, item in paths.items():
        if path in OPERATIONAL_PATHS:
            problems.append(f"{path} is an operational endpoint added by the platform; remove it")
        for method, op in (item or {}).items():
            if method.lower() not in HTTP_METHODS:
                continue
            ops.add(f"{method.upper()} {path}")
            if not (op or {}).get("responses"):
                problems.append(f"{method.upper()} {path} declares no responses")
    return ops, problems


_TABLE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?[\"`\[]?(\w+)", re.IGNORECASE)


def table_names(schema_sql: str) -> list[str]:
    return _TABLE.findall(schema_sql)


def validate_sql(schema_sql: str) -> list[str]:
    if "create table" not in schema_sql.lower():
        return ["schema_sql has no CREATE TABLE statement"]
    try:
        conn = sqlite3.connect(":memory:")
        conn.executescript(schema_sql)
        conn.close()
    except sqlite3.Error as exc:
        return [f"schema_sql is not valid SQLite: {exc}"]
    return []


def validate_design(design, spec: dict, plan: list[dict], allowed_deps: set[str]) -> list[str]:
    ops, problems = openapi_operations(design.openapi_yaml)
    problems += validate_sql(design.schema_sql)
    rows = {r.requirement_id: r for r in design.traceability}
    module_names = {m.name for m in design.modules}
    for fr in spec["functional_requirements"]:
        if fr["priority"] != "MVP":
            continue
        row = rows.get(fr["id"])
        if row is None or not row.endpoints:
            problems.append(f"{fr['id']} is not traced to any endpoint")
    plan_ids = {p["requirement_id"]: p["catalog_id"] for p in plan}
    for req_id, catalog_id in plan_ids.items():
        row = rows.get(req_id)
        if row is None or catalog_id not in row.catalog_ids:
            problems.append(f"{req_id} must be traced with catalog id {catalog_id}")
    known_reqs = {f["id"] for f in spec["functional_requirements"]} | set(plan_ids)
    for row in design.traceability:
        if row.requirement_id not in known_reqs:
            problems.append(f"traceability row {row.requirement_id} is not a spec requirement")
        for ep in row.endpoints:
            if ep not in ops:
                problems.append(f"{row.requirement_id} traces to {ep!r}, which is not in OpenAPI")
        for mod in row.modules:
            if mod not in module_names:
                problems.append(f"{row.requirement_id} traces to unknown module {mod!r}")
    for dep in design.dependencies:
        if dep not in allowed_deps:
            problems.append(f"dependency {dep!r} is not in the allowlist")
    return problems


def adr_markdown(decision: dict, chosen: str, override_reason: str = "") -> str:
    lines = ["# ADR-001: Technology stack", "", "## Status", "", "Proposed", "",
             "## Decision", "", f"Use **{chosen}**.", ""]
    if override_reason:
        lines += [f"Human override of the recommended `{decision['recommended_stack_id']}`: "
                  f"{override_reason}", ""]
    lines += ["## Rationale", "", decision["rationale"], "", "## Options considered", ""]
    for o in decision["options"]:
        supported = o["stack_id"] or "not supported by the orchestrator"
        lines += [f"### {o['name']} ({supported})", "",
                  f"{o['language']} · {o['framework']} · {o['build_tool']} · {o['persistence']} · "
                  f"{o['test_framework']}", "", f"Fit: {o['fit']}", "",
                  "Pros: " + "; ".join(o["pros"]), "", "Cons: " + "; ".join(o["cons"]), ""]
    lines += ["## Consequences", ""] + [f"- {c}" for c in decision["consequences"]]
    lines += ["", "## Rejected alternatives", ""] + [f"- {r}" for r in
                                                       decision["rejected_alternatives"]]
    return "\n".join(lines) + "\n"


def design_markdown(design: dict, stack_id: str, plan: list[dict]) -> str:
    lines = ["# Design", "", f"Stack: `{stack_id}`", "", "## Modules", ""]
    lines += [f"- **{m['name']}** — {m['responsibility']} ({', '.join(m['traces'])})"
              for m in design["modules"]]
    lines += ["", "## Non-functional implementation (from catalog)", ""]
    lines += [f"- {p['requirement_id']} {p['catalog_id']} {p['params']}: {p['implementation']}"
              for p in plan] or ["- none"]
    lines += ["", "## Primary flows", ""]
    for f in design["flows"]:
        lines += [f"### {f['name']}", ""] + [f"{i}. {s}" for i, s in enumerate(f["steps"], 1)]
        lines.append("")
    lines += ["## Error model", "", design["error_model"], "", "## Traceability", "",
              "| Requirement | Endpoints | Modules | Catalog |", "|---|---|---|---|"]
    lines += [f"| {r['requirement_id']} | {', '.join(r['endpoints']) or '—'} | "
              f"{', '.join(r['modules'])} | {', '.join(r['catalog_ids']) or '—'} |"
              for r in design["traceability"]]
    lines += ["", "## Dependencies", ""] + [f"- {d}" for d in design["dependencies"]]
    return "\n".join(lines) + "\n"
