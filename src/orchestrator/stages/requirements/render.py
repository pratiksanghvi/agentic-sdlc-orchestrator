"""Human-readable views of the spec (requirements.md and the gate summary)."""

from __future__ import annotations


def _ac_line(ac: dict) -> str:
    return f"  - {ac['id']}: Given {ac['given']}, when {ac['when']}, then {ac['then']}"


def requirements_markdown(spec: dict) -> str:
    lines = [f"# {spec['title']}", "", "## Functional requirements", ""]
    acs_by_req: dict[str, list[dict]] = {}
    for ac in spec["acceptance_criteria"]:
        acs_by_req.setdefault(ac["requirement_id"], []).append(ac)
    for fr in spec["functional_requirements"]:
        tag = f"**{fr['id']}** [{fr['priority']}]"
        lines.append(f"- {tag} {fr['statement']} _(source: {fr['source']})_")
        for ac in acs_by_req.get(fr["id"], []):
            lines.append(_ac_line(ac))
    lines += ["", "## Non-functional requirements", ""]
    for nfr in spec["non_functional_requirements"]:
        params = ", ".join(f"{p['name']}={p['value']}" for p in nfr["params"]) or "defaults"
        lines.append(f"- **{nfr['id']}** ({nfr['catalog_id']}; {params}) {nfr['statement']}")
        for ac in acs_by_req.get(nfr["id"], []):
            lines.append(_ac_line(ac))
    if not spec["non_functional_requirements"]:
        lines.append("- none requested")
    lines += ["", "## Not supported in MVP", ""]
    lines += [f"- {n['message']}" for n in spec["not_supported"]] or ["- none"]
    lines += ["", "## Assumptions", ""]
    lines += [f"- **{a['id']}** {a['text']}" for a in spec["assumptions"]] or ["- none"]
    lines += ["", "## Constraints", ""]
    lines += [f"- {c}" for c in spec["constraints"]] or ["- none"]
    lines += ["", "## Out of scope", ""]
    lines += [f"- {o}" for o in spec["out_of_scope"]] or ["- none"]
    if spec["clarifications"]:
        lines += ["", "## Clarifications", ""]
        lines += [f"- {c['question']} → **{c['answer']}**" for c in spec["clarifications"]]
    return "\n".join(lines) + "\n"


def gate_summary(spec: dict, problems: list[str], path: str) -> str:
    mvp = [f for f in spec["functional_requirements"] if f["priority"] == "MVP"]
    lines = [
        f"[bold]{spec['title']}[/]",
        f"Functional: {len(spec['functional_requirements'])} ({len(mvp)} MVP)   "
        f"NFRs: {len(spec['non_functional_requirements'])}   "
        f"Acceptance criteria: {len(spec['acceptance_criteria'])}   "
        f"Assumptions: {len(spec['assumptions'])}",
        "",
    ]
    for fr in spec["functional_requirements"]:
        lines.append(f"  {fr['id']} [{fr['priority']}] {fr['statement']}")
    for nfr in spec["non_functional_requirements"]:
        lines.append(f"  {nfr['id']} {nfr['catalog_id']}: {nfr['statement']}")
    if spec["not_supported"]:
        lines += ["", "[yellow]Not supported in MVP (will not be built):[/]"]
        lines += [f"  - {n['request']}" for n in spec["not_supported"]]
    if spec["assumptions"]:
        lines += ["", "Assumptions:"] + [f"  {a['id']} {a['text']}" for a in spec["assumptions"]]
    if problems:
        lines += ["", "[red]Validation problems (approve is unavailable until fixed):[/]"]
        lines += [f"  - {p}" for p in problems]
    lines += ["", f"Full spec: {path}"]
    return "\n".join(lines)
