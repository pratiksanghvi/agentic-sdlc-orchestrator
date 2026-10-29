# Agentic SDLC Orchestrator

A governed, stateful orchestrator that turns a plain-language requirement into a **working,
verified service** by running the SDLC end to end — requirements, design, test design,
implementation, verification, security, documentation and release — with **human approval gates**
at every high-impact decision.

> Agents execute bounded work. Humans approve the spec, the stack, the design, the test plan and
> the final release. A run succeeds only when a human accepts a service that passed the
> human-approved acceptance tests.

* Orchestrator: Python 3.12 · LangGraph (subgraphs, parallel branches, `interrupt()` gates, SQLite
  checkpoints) · Anthropic Claude (Opus 5.5 for reasoning stages, Sonnet 5.5 for code)
* Generated service (validated stack): Java 21 · Spring Boot 3 · Maven · SQLite
* **Full design, with what is implemented vs designed-only:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
* Live walkthrough script: [docs/DEMO.md](docs/DEMO.md) · How AI was used to build this: [AI_USAGE.md](AI_USAGE.md)

```
0 Codebase (brownfield only)  snapshot → impact analysis → [HUMAN approve]
1 Requirements   intake guardrail → analyze → clarify ⟲ → spec → validate → [HUMAN approve]
2 Design         stack ADR → [HUMAN stack] → NFR catalog lookup → OpenAPI + DDL + trace → validate → [HUMAN]
3 Test Design    catalog NFR cases ‖ functional cases → validate → [HUMAN approve]
4 Implementation backup + rollback opt-in → tasks (compile + commit each) ‖ frozen acceptance suite
5 Verify         build+unit → start (SERVICE_READY) → acceptance; 3 auto-fixes → [HUMAN hints ⟲ | end + rollback]
6 Security       secrets ‖ change control → report (awareness)
7 Docs           README + API docs, checked against real commands and the contract
8 Release        checklist ‖ metrics → engineering summary → [HUMAN ACCEPT → merge + tag | REJECT → restart | END]
```

## Setup

Requirements: Python 3.11+, JDK 21+ and Maven 3.9+ (JDK/Maven only build the generated Java
service), network access to the Anthropic API and Maven Central.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp config/application.example.properties config/application.properties
# edit config/application.properties: set anthropic.api_key (or export ANTHROPIC_API_KEY)
.venv/bin/orchestrator check-config
```

`config/application.properties` is gitignored — never commit it. Invalid configuration refuses
to start.

## Run

```bash
# Greenfield: build a new service
.venv/bin/orchestrator run --requirement examples/requirements/greenfield-url-shortener.txt

# Ambiguous requirement: watch clarification questions and logged assumptions
.venv/bin/orchestrator run --requirement examples/requirements/ambiguous-url-shortener.txt

# Brownfield: change an existing product repository (e.g. the accepted v0.1.0)
.venv/bin/orchestrator run --requirement examples/requirements/brownfield-link-expiry.txt \
    --product workspaces/<product>

# Inspect any run
.venv/bin/orchestrator trace <run_id>        # timeline of every step, model call and decision
.venv/bin/orchestrator metrics [run_id]      # cost, tokens, first-pass rate, fixes, MTTR, time split
.venv/bin/orchestrator verify-log <run_id>   # tamper check of the hash-chained audit log
```

Each run writes `runs/<run_id>/` (gitignored): versioned, immutable artifacts
(`artifacts/<type>/v<n>/` + manifest with hashes), the hash-chained audit log
`logs/events.jsonl` (every prompt, response, token count, latency, human answer and decision),
verification evidence, and LangGraph checkpoints. The generated product lives in its own git
repository under `workspaces/<product>/`: each run works on `run/<run_id>`, only human-accepted
runs reach `master` with a version tag, failed runs are kept as `failed/<run_id>`.

A full run takes roughly 10–15 minutes (Opus calls take 20–90 s each) and costs about $1–2.

## Example

`examples/run-greenfield/` contains a recorded successful run: the approved spec, design, test
plan, verification report, engineering summary, metrics and the audit-log trace, plus
`examples/generated-url-shortener/` with the generated Java service at its accepted tag.

## Development

```bash
.venv/bin/ruff check src tests
.venv/bin/pytest -q
```

Tests use a scripted fake LLM and scripted human answers; they need no API key (CI runs them on
every push).

## Status

| Milestone | Scope | Status |
|---|---|---|
| M0 | Skeleton, config loading + validation, CI | ✅ |
| M1 | Foundations: versioned artifacts, hash-chained audit log, traced LLM client, human gates, cost ceiling | ✅ |
| M2 | Requirements stage | ✅ |
| M3 | Design stage | ✅ |
| M4 | Test Design stage | ✅ |
| M5 | Implementation (4a tasks ‖ 4b frozen acceptance suite) | ✅ |
| M6 | Build & Verify with fix loop, escalation, rollback | ✅ |
| M7 | Security report, documentation | ✅ |
| M8 | Release verdict, metrics, trace | ✅ |
| M10 | Brownfield (codebase snapshot + impact analysis) | ✅ |
| M9 | Docs, demo script, recorded example run | ✅ |

Known limitations and items designed but not built are listed in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#deadline-scope).
