# Agentic SDLC Orchestrator

A governed, stateful orchestrator that turns a plain-language requirement into a **working, verified
service** by running the SDLC end to end — requirements, design, test design, implementation,
verification, security, documentation and release — with **human approval gates** at every
high-impact decision.

* Orchestrator: Python 3.12 + LangGraph + Anthropic Claude
* Generated service (validated stack): Java 21 + Spring Boot 3 + Maven + SQLite
* Full design, with what is implemented vs designed-only: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Setup

Requirements: Python 3.11+, JDK 21+, Maven 3.9+ (JDK/Maven are only needed to build the generated Java service).

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp config/application.example.properties config/application.properties
# edit config/application.properties and set anthropic.api_key
#   (or export ANTHROPIC_API_KEY — environment variables override the file)
.venv/bin/orchestrator check-config
```

`config/application.properties` is gitignored; never commit it.

## Development

```bash
.venv/bin/ruff check src tests
.venv/bin/pytest -q
```

Tests use a fake LLM and need no API key.

## Run

```bash
.venv/bin/orchestrator run --requirement examples/requirements/greenfield-url-shortener.txt
.venv/bin/orchestrator verify-log <run_id>
```

Each run writes `runs/<run_id>/` (gitignored): versioned artifacts, the hash-chained audit log `logs/events.jsonl`, and LangGraph checkpoints.

## Status

Built milestone by milestone; see the status marks in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

| Milestone | Scope | Status |
|---|---|---|
| M0 | Skeleton, config loading + validation, CI | ✅ |
| M1 | Foundations: versioned artifacts, hash-chained event log, traced LLM client, human gates, cost ceiling | ✅ |
| M2 | Requirements stage (intake guardrail, analysis, clarification, spec, deterministic validation, approval gate) | ✅ |
| M3 | Design stage (stack ADR + approval, NFR catalog lookup, OpenAPI + SQLite DDL + traceability, deterministic validation, design approval) | ✅ |
| M4 | Test Design stage | 🔨 |
| M5–M6 | Implementation ‖ acceptance-test code, Build & Verify with fix loop | 🔨 |
| M7–M8 | Security report, docs, release verdict, metrics | 🔨 |
| M10 | Brownfield | 🔨 |
| M9 | Hardening, demo script, recorded example run | 🔨 |
