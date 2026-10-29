# Architecture — Agentic SDLC Orchestrator

A governed, stateful orchestrator that takes a plain-language requirement through the full SDLC —
requirements → design → test design → implementation → verification → security → docs → release —
and produces a **working, verified service**. Agents (Claude) execute bounded work; **humans own
approvals and final quality**.

> **Success criterion.** The orchestrator is the product; the generated service is its output.
> If the orchestrator cannot produce a working service that passes the human-approved acceptance
> tests, the orchestrator has failed. A human gives the final verdict on every run.

## Status legend

Every design item below carries a status so reviewers can see exactly what is built.

| Mark | Meaning |
|---|---|
| ✅ | Implemented and tested (milestone noted) |
| 🔨 | Planned for this delivery (milestone noted) — not yet implemented |
| ✂️ | Designed, **cut for the delivery deadline** — see [Deadline scope](#deadline-scope) |
| 🔭 | Designed as a **future enhancement** |
| ⏸️ | **Parked** — open design question, deliberately undecided |

---

## 1. Principles

1. **Orchestrator is the product.** A run succeeds only when a human accepts a working, verified service.
2. **Controlled autonomy.** Agents never approve, never expand scope, never re-plan on their own; they propose, humans decide.
3. **Bounded, validated capability.** The orchestrator only promises what it can build *and* validate: a fixed stack catalog and a fixed non-functional (NFR) catalog. Everything else gets a polite "not supported in MVP".
4. **Requirement-agnostic.** Nothing is specific to URL shorteners; the URL shortener is the demonstration workload.
5. **Deterministic where possible.** Code checks, hashes and real tool runs decide pass/fail — never a model's opinion.
6. **Audit-grade traceability.** Every input, model call, decision and approval is logged in a tamper-evident chain and linked to the exact artifact versions involved.
7. **Zero extra installs.** Clone → `pip install` → add API key. (JDK + Maven are needed only because the generated service is Java.)

## 2. Technology

| Concern | Choice | Status |
|---|---|---|
| Orchestration | Python 3.12 + **LangGraph** (stateful graph, subgraphs, parallel branches, `interrupt()` human gates, SQLite checkpointer) | 🔨 M1+ |
| LLM | Anthropic Claude via official Python SDK (streaming) — `claude-opus-5-5` (reasoning stages + fallback), `claude-sonnet-5-5` (code generation); configurable | ✅ M1 |
| Structured output | `output_config.format` JSON schema generated from Pydantic models (objects closed, all fields required, value constraints enforced afterwards by Pydantic + semantic validators). Forced `tool_choice` is not supported on current models, so schema-constrained output is used instead | ✅ M1 |
| Config validation | Pydantic models for every config file | ✅ M0 |
| Console UI | `rich` | ✅ M1 (gates); live view 🔨 M8 |
| Secret scanning | `detect-secrets` (pip) | 🔨 M1/M7 |
| Generated service stacks | Java 21 + Spring Boot 3 + Maven + SQLite (**validated**); Python/FastAPI and Go/chi configured | Java 🔨 M5–M6; Python/Go ✂️ |
| Acceptance tests | Black-box **pytest + httpx** against the running service (stack-agnostic) | 🔨 M5–M6 |

## 3. Configuration and guardrail files

| File | Committed | Purpose | Status |
|---|---|---|---|
| `config/application.properties` | **No** (gitignored) | API key, approver name, model IDs; env vars override | ✅ M0 |
| `config/application.example.properties` | Yes | Template with placeholders | ✅ M0 |
| `config/pricing.yaml` | Yes | Per-model token prices for cost estimates | ✅ M0 |
| `policy/policy.yaml` | Yes | Limits, retry budgets, timeouts, startup contract, path rules, cost ceiling | ✅ M0 |
| `catalog/stacks.yaml` | Yes | Per stack: commands, versioned dependency allowlist, path allowlist, `validated` flag | ✅ M0 |
| `catalog/nfr_catalog.yaml` | Yes | Bounded NFR catalog: capability, params, per-stack implementation, validation recipe | ✅ M0 |

* All files are validated at startup (`orchestrator check-config`); invalid config **refuses to start**. ✅ M0
* SHA-256 of `policy.yaml`, `stacks.yaml`, `nfr_catalog.yaml` are computed at load and recorded on every run, so the audit shows which rules governed it. ✅ M0 (hashing) / ✅ M1 (recorded in `run_started`)

## 4. Lifecycle overview

```
1 Requirements   R1 intake → R2 analyze → R3 clarify ⟲ → R4 spec → R5 validate → [HUMAN approve]
2 Design         D1 entry → D2 stack → [HUMAN stack] → D3 NFR lookup → D4 architecture → D5 validate → [HUMAN design]
3 Test Design    T1 NFR cases ‖ T2 functional cases → T3 validate → [HUMAN approve] → freeze
   ── backup taken + "roll back on failure?" asked ──
4 Implementation 4a tasks one at a time (compile + commit each) ‖ 4b acceptance-test code → join
5 Build & Verify build+unit → start (SERVICE_READY) → acceptance; 3 auto-fixes → [HUMAN hint ⟲ | end → confirm rollback]
6 Security       S1 secrets ‖ S4 change control → report (awareness only)
7 Docs           facts → generate → validate (no approval)
8 Release        checklist ‖ metrics → summary → [HUMAN ACCEPT → merge + version tag | REJECT → restart stage | END]
```

Parallel paths with synchronization: **4a ‖ 4b**, **T1 ‖ T2** (✅ M4, joined at T3), **S1 ‖ S4**, **RR1 ‖ RR2** (each joins before the next step).

### Human gates

| Gate | Options | Status |
|---|---|---|
| R3 Clarify (only if blocking ambiguities) | Answer each question (number, own text, or Enter for the suggested default); max 2 rounds, then remaining items become flagged assumptions | ✅ M2 |
| R3b Ideas loop (propose new requirement ideas, unlimited rounds) | accept / reject / modify / more / done | ✂️ |
| R6 Spec approval | approve / reject + feedback / end run | ✅ M2 (edit ✂️) |
| Stack approval (after D2) | approve / choose another supported stack (stacks lacking a catalog implementation for a requested NFR are hidden; unvalidated stacks are labelled) / reject + feedback / end run | ✅ M3 |
| D6 Design approval | approve / reject + feedback → D4 / change the stack decision → D2 / end run | ✅ M3 (edit ✂️) |
| T4 Test-plan approval | approve / reject + feedback / end run | ✅ M4 (modify/remove/suggest ✂️) |
| Pre-implementation | "Roll back to pre-implementation version if verify fails? [y/N]" | 🔨 M5 |
| Stage 5 escalation | implementation hint / end run (with rollback confirmation) — unlimited tries, one fix + one verify per hint | 🔨 M6 (test-case change ✂️) |
| Stage 6 missing tool | proceed without the check / stop | 🔨 M7 |
| Stage 8 final verdict | accept / reject → restart from Requirements, Design or Test Design / end run | 🔨 M8 |
| Cost ceiling | "Run has used $X. Continue? [y/N]" at each multiple of `budgets.cost_usd_confirm` ($5) | ✅ M1 |

---

## 5. Stage designs

### Stage 1 — Requirements

Turns a raw requirement into an approved spec with numbered, testable acceptance criteria. Does **not** choose technology.
Implementation: `stages/requirements/` (graph, prompts, schemas, deterministic rules, rendering); human pauses use LangGraph `interrupt()` and are answered by `runtime/driver.py` through `HumanGate`; run state is checkpointed in SQLite per run.

| Step | Type | Behavior | Status |
|---|---|---|---|
| R1 Intake | code | Reject empty / > `input.max_bytes`; secret + PII scan; hash input; log verbatim | ✅ M2 |
| R2 Analyze | LLM | Intent; explicit FR/NFR with source quotes; ambiguities classified BLOCKING / NON_BLOCKING with recommended defaults; out of scope; NFR classification (supported / unsupported category / vague / not mentioned) | ✅ M2 |
| R3 Clarify | human | Only when BLOCKING items exist; vague in-category NFR asks become blocking questions offering catalog options | ✅ M2 |
| R4 Normalize | LLM | FR-n / NFR-n with priority MVP/LATER and source; AC-n.m in Given/When/Then with verification method; assumptions; out of scope; `not_supported[]` | ✅ M2 |
| R5 Validate | code | Schema; every MVP FR has ≥1 AC; unique IDs; no tech-stack terms; **every NFR maps to a catalog ID, is in a supported category, has source explicit/clarification, and its `source_quote` literally appears in the input or clarification answers** | ✅ M2 |
| R5 Critic | LLM | Coverage / invention / testability / conflict review | ✂️ |
| R6 Gate | human | Approve freezes the spec version and binds the approval to its hash | ✅ M2 |

**NFR rules** (all ✅ M2):
1. NFRs are captured in Requirements, not Design.
2. Supported categories: **rate limit, security, observability (logging + metrics)**.
3. Asks outside these categories — or inside them but not in the catalog (e.g. encryption at rest, OAuth2) — receive a fixed, polite template response, are listed as *Not supported in MVP*, and the run continues.
4. NFRs are not mandatory — no NFR code is built unless the user asked.
5. No NFRs from assumptions or "implied needs" — every NFR traces to user text.

### Stage 2 — Design

Implementation: `stages/design/`. Artifacts: `stack_adr` (ADR-001 + stack.json), `nfr_plan`, `design` (openapi.yaml, schema.sql, design.md, design.json, traceability.json).

| Step | Type | Behavior | Status |
|---|---|---|---|
| D1 Entry | code | Spec approved and its hash unchanged | ✅ M3 |
| D2 Stack | LLM | 2–3 options with pros/cons → ADR-001; recommendation must come from `stacks.yaml`, must have catalog implementations for every requested NFR (code-enforced), prefers validated stacks; a stack named in the requirement is honored | ✅ M3 |
| Stack gate | human | Approve, or pick another supported stack | ✅ M3 |
| D3 NFR lookup | code | `catalog[nfr_id].implementation[stack]` + validation recipe (no LLM) | ✅ M3 |
| D4 Architecture | LLM | Modules, **OpenAPI 3** contract, SQLite DDL, primary flows, error model, traceability matrix FR/NFR/AC → endpoint/component/catalog ID | ✅ M3 |
| D5 Validate | code | OpenAPI 3.x parses, every operation has responses, no operational paths; DDL executes in an in-memory SQLite; every MVP FR traced to an existing endpoint; every NFR traced with its catalog ID; modules exist; dependencies in the stack allowlist; bounded retries with findings fed back, then the gate (approve hidden while problems remain) | ✅ M3 |
| D5 Critic | LLM | Spec mismatches, over-engineering, light security review | ✂️ |
| D6 Gate | human | Approve / reject → D4 with feedback / change stack → D2 (D3 is deterministic, so there is nothing to re-run there) | ✅ M3 |

Data store: **SQLite only** (embedded, works in all three stacks, no setup). Postgres via Docker Compose 🔭.

### Stage 3 — Test Design

Implementation: `stages/test_design/`, `contract/openapi.py`. A test case is a list of HTTP steps (method, path with `${var}` placeholders, JSON body, repeat count, expected status or forbidden status, JSON-path / raw-body / header assertions, captures). Cases are tagged `phase: main` or `phase: isolated`; rate-limit cases are isolated because they exhaust a shared per-client budget, so Stage 5 runs them after a service restart. NFR cases use ids TC-900+.

| Step | Type | Behavior | Status |
|---|---|---|---|
| T1 NFR cases | code | Generated from each selected catalog entry's validation recipe and the OpenAPI contract: OBS-METRICS (call an endpoint, then `/metrics` contains `http_server_requests`); SEC-INPUT (per operation with a JSON body: missing required field, wrong type, oversized body → 400 problem+json, no stack trace); RL-BASIC (send `limit` requests, then expect 429 + `Retry-After`) | ✅ M4 |
| T2 Functional cases | LLM | Per AC: ≥1 positive + implied negative/edge cases; TC-n → AC-n.m; HTTP steps + expected status/body assertions; only endpoints/fields in the OpenAPI contract | ✅ M4 |
| T3 Validate | code | Every MVP AC and every planned NFR covered; each step's method + path matches an OpenAPI operation; functional expected statuses are declared for that operation; variables captured before use; JSON bodies parse; unique IDs; bounded retries, then the gate | ✅ M4 |
| T4 Gate | human | Approve / reject + feedback | ✅ M4 |
| T4 modify / remove / suggest + T5 suggestion converter (suggestion beyond spec → NEW_REQUIREMENT → offer re-plan; removing last test of an AC → logged waiver) | human + LLM | | ✂️ |

**Independence.** Acceptance tests are written by a separate agent from the approved contract only, stored **outside the product repo**, hidden from and immutable to the implementation agent, and hash-checked before they run.

### Stage 4 — Implementation (4a ‖ 4b)

Before Stage 4: a backup is **always** taken (git tag `pre-impl/<run_id>` on the product repo) and the user is asked once whether to roll back on failure. 🔨 M5

| Step | Type | Behavior | Status |
|---|---|---|---|
| I1 Plan | LLM (Sonnet) | 3–10 tasks with goal, files, `depends_on`, traces, done criteria; each catalog NFR is its own task; first task scaffolds the project | 🔨 M5 |
| I2 Validate plan | code | DAG acyclic; every design component covered; files within path allowlist | 🔨 M5 |
| I4 Execute tasks | LLM per task, **sequential** | Complete files via a write tool; only dependent files in context; unit tests in the product's language | 🔨 M5 |
| Guardrails after each task | code | Path allowlist; no access to acceptance tests; dependency allowlist (parsed from `pom.xml`); detect-secrets; startup contract present; no suppression comments | 🔨 M5 |
| Compile + checkpoint | code | Stack compile command; commit per task on branch `run/<run_id>` | 🔨 M5 |
| Retry / fallback | governed | 2 retries with errors fed back → 1 attempt on the stronger model → roll back to last checkpoint + report to human | 🔨 M5 |
| 4b Test code | LLM (Sonnet) | pytest + httpx, one `test_<tc_id>` per approved case; `BASE_URL` from env; no product source access; code check that every case has a function and collection succeeds; freeze + hash | 🔨 M5 |
| Parallel task execution | | | 🔭 |

No human intervention in Stage 4.

**Startup contract** (stack-agnostic readiness): the service reads `PORT` from the environment and prints exactly `SERVICE_READY port=<port>` once listening. The orchestrator does not rely on framework health endpoints.

### Stage 5 — Build & Verify

| Step | Behavior | Status |
|---|---|---|
| V1 Entry | 4a and 4b joined; acceptance-suite hash unchanged (else safe-stop) | 🔨 M6 |
| V2 Build + unit tests | Stack `build_and_unit_test` command | 🔨 M6 |
| V3 Start | Clean child environment (only `PORT`, DB path; **never the API key**); read stdout line by line; `SERVICE_READY` + TCP connect = started; process exit or error pattern = failed; 90 s timeout | 🔨 M6 |
| V4 Acceptance | Run the frozen suite with `BASE_URL`; JUnit XML; stop the service. **Skipped entirely if build or startup failed** | 🔨 M6 |
| V5 Evidence | AC → TC → pass/fail, build/unit results, startup time, fix history, MTTR | 🔨 M6 |
| V6 Fix | Shared budget of **3** automatic attempts across build, unit, startup and acceptance; product code only (tests frozen); diagnosis + fix; commit `fix attempt n` | 🔨 M6 |
| Escalation | Unlimited human tries: each hint → one fix → one verify → report; on all-pass the human confirms moving on; end run → confirm rollback → restore backup and show message | 🔨 M6 |
| Advisory `suspected_cause` (IMPLEMENTATION / TEST / DESIGN / REQUIREMENT) in the diagnosis | | ⏸️ |

### Stage 6 — Policy & Security (report only)

| Check | Tool | Status |
|---|---|---|
| S1 Secrets | detect-secrets | 🔨 M7 |
| S2 Code security (SAST) | Semgrep (pip) | ✂️ |
| S4 Change control | own code: approvals' hashes match current artifacts, commits trace to task/fix/run, path + dependency allowlists, acceptance-suite hash | 🔨 M7 |
| S3 Dependency CVEs (OSV-Scanner), gitleaks, license scan | external binaries | 🔭 |
| Automatic fixing of findings, false-positive waivers | | 🔭 |

The report is shown for awareness; the run continues automatically. If a scanner is unavailable, the user is asked whether to proceed without it, and the skipped check is recorded.

### Stage 7 — Documentation (no approval)

| Item | Status |
|---|---|
| DC1 assemble facts from approved artifacts + real commands + results | 🔨 M7 |
| DC2 generate `README.md` and `docs/API.md` for the generated service | 🔨 M7 |
| DC2 `docs/ARCHITECTURE.md` and `CHANGELOG.md` for the generated service | ✂️ |
| DC3 validate: README commands == stack commands; every OpenAPI endpoint in API.md and none extra; links resolve; no TODOs; no secrets; max 2 retries, leftovers become warnings | 🔨 M7 |

### Stage 8 — Release readiness and final verdict

| Item | Status |
|---|---|
| RR1 readiness checklist (informational) ‖ RR2 run metrics | 🔨 M8 |
| RR3 engineering summary — generated by code from the event log (plan, artifacts, validation, assumptions, limitations, unsupported requests, decision lineage, metrics) | 🔨 M8 |
| RR3 summary written by the model + RR4 facts-only validation | ✂️ |
| RR5 verdict: ACCEPT → merge `run/<id>` into `master` + incremental version tag (`v0.1.0`, `v0.2.0`, …); REJECT → choose restart stage; END → branch kept as `failed/<id>` | 🔨 M8 |
| Container image / deployment | 🔭 |

---

## 6. Cross-cutting design

### 6.1 Versioned artifacts and approvals (foundations F1–F3) — F1, F2 ✅ M1; F3 ✅ M2 (stages are subgraphs with shared `StageIO` input/output schemas and private working state)

* **F1 Versioned artifacts.** Every write creates `<type>/v<n>/` holding the complete file set plus an immutable `manifest.json` (type, version, producing step, attempt, timestamp, input references with hashes, per-file SHA-256, version hash). Retries and rejected drafts are versions too. JSON is hashed in canonical form. Status (DRAFT / APPROVED / REJECTED / SUPERSEDED) is recorded as events, not in the manifest.
* **F2 Approvals bound to hashes.** An approval records gate, artifact type, version, hash, approver, time. A stage's entry check re-hashes its inputs and requires a matching approval.
* **F3 Restartable stage contracts.** Each stage is a LangGraph subgraph declaring `requires` and `produces`; it reads only approved artifacts via the store and writes only its own outputs; its scratch state is discarded on exit. This makes every stage independently testable and restartable.

### 6.2 Observability — choke points, records, hash chain ✅ M1; metrics + views 🔨 M8

* Implementation: `observability/eventlog.py`, `llm/client.py`, `llm/backends.py`, `human/gate.py`, `observability/node.py`, `artifacts/store.py`, `artifacts/approvals.py`, `runtime/context.py`.
* **Single choke points:** `TracedAnthropicClient` (only way to call Claude), `HumanGate` (only way to prompt the user), `@observed_node` (every graph step). Tests enforce logged-call count == actual calls.
* **Records:** LLM call (full system prompt + messages, full response, stop reason, input/output/cache tokens, latency, estimated cost, request ID, schema-retry flag); human interaction (what was shown, options, verbatim answer, response wait); event (node start/finish, input/output hashes, retries, fixes, rollbacks, pause/resume, guardrail violations, re-plans); decision (type, made by human or agent, rationale, basis = LLM call IDs + input hashes).
* **Storage:** append-only JSONL, full prompts/responses inline; each line carries the hash of the previous line (tamper-evident; `verify-log`). API key never logged; run logs are gitignored.
* **Metrics:** run success rate (ACCEPT ÷ finished runs), first-pass success per stage, retry / fix / rollback frequency, MTTR (total and automatic-only), end-to-end time split into agent / tool / human-wait, tokens + cost per step/stage/run, LLM latency p50/p95, gate approve/reject counts, schema-retry rate.
* **Views:** live `rich` progress, `trace <run_id>`, `metrics`, `verify-log <run_id>` 🔨; `explain <decision_id>` ✂️.
* LangFuse / OpenTelemetry / Grafana 🔭.

### 6.3 Guardrails

| Guardrail | Where | Status |
|---|---|---|
| Input size, secret/PII scan, untrusted-data framing in prompts | R1, all prompts | ✅ M2 |
| Schema validation of every model output + bounded schema retries (truncated output retried with doubled `max_tokens`) | LLM client | ✅ M1 |
| Stack allowlist, catalog-only NFRs, `source_quote` check, SQLite only | R5, D2, D3 | 🔨 M2–M3 |
| Path allowlist, forbidden acceptance-test paths, startup contract, no suppression comments | Stage 4 | 🔨 M5 |
| Versioned dependency allowlist per stack | Stage 4 | 🔨 M5 |
| Only commands from `stacks.yaml` may run; timeouts; run inside the workspace | execution | 🔨 M5–M6 |
| Clean child environment for generated code (no API key / secrets) | execution | 🔨 M6 |
| Cost ceiling with human confirmation (asked at every multiple of the ceiling) | runtime | ✅ M1 |
| Step retry budgets + stronger-model fallback | stages | 🔨 M2+ |
| Approvals bound to hashes; governance file hashes per run | change control | ✅ M1 |
| OS/container sandbox for generated code | | 🔭 |

**Limitation:** generated code runs on the host. Command allowlisting and a clean environment reduce risk but are not process isolation.

### 6.4 Git model for the generated product — 🔨 M5/M8

The generated product lives in its own git repository under `workspaces/<name>/`, separate from this repo. Each run works on `run/<run_id>`; only human-accepted runs are merged to `master` and tagged; failed runs are kept as `failed/<run_id>` for audit. Per-task and per-fix commits carry run and task IDs.

### 6.5 Re-planning

| Item | Status |
|---|---|
| Gate reject loops back to the producing step with feedback | 🔨 M2–M4 |
| Final REJECT → user picks restart stage; downstream re-runs on new versions with fresh approvals | 🔨 M8 |
| Detection of edits made outside the orchestrator (re-approve or discard) | ⏸️ |
| NEW_REQUIREMENT routing from test suggestions; carrying rejected ideas across re-plans; counting re-plans in metrics | ⏸️ |
| Principle: agents never re-plan autonomously | ⏸️ (proposed) |
| Selective re-run of only the components traced to a changed requirement | 🔭 |

### 6.6 Run lifecycle — ⏸️ parked

Resume after shutdown (LangGraph SQLite checkpointer, `runs list` / `resume`, re-running only the interrupted step, integrity re-hash on resume, one active run per workspace), the exact on-disk artifact layout, and the full "end run" handling (where it is offered, mandatory reason, run-ended report) are designed in outline but parked as open questions. Ctrl+C pauses a run; the checkpointer is in place, but the resume UX is not part of this delivery.

### 6.7 Brownfield — 🔨 M10

Point the orchestrator at an existing product repository (for the demo: the accepted v0.1.0 URL shortener). A **codebase snapshot + impact analysis** step (code inventory, then an LLM pass identifying impacted modules, endpoints, tables and data flows) feeds Requirements and Design as additional approved inputs. The rest of the pipeline is reused unchanged (F3); the run works on a new branch of the same product repo and releases the next version.

---

## 7. Three scenarios

| Scenario | How it is exercised | Status |
|---|---|---|
| Greenfield | Loose requirement → new Java URL shortener v0.1.0 | 🔨 M2–M8 |
| Ambiguous | Vague requirement → R2 classifies blocking ambiguities → R3 clarification → assumptions logged → approval | ✅ M2 (no extra build) |
| Brownfield | Enhancement request against the accepted v0.1.0 → impact analysis → v0.2.0 | 🔨 M10 |

---

## Deadline scope

This delivery was built against a ~12-hour deadline. The full design above is the target architecture;
the following items were consciously cut and remain designed-only (✂️):

| Cut | Delivered instead |
|---|---|
| Python and Go stacks validated end-to-end | Java validated; Python/Go present in `stacks.yaml` with `validated: false` |
| R3b ideas loop | — |
| R5 / D5 critic model calls | Deterministic code checks |
| `[e]` edit-in-editor at gates | Reject with feedback |
| T4 modify / remove / suggest test cases | Approve or reject with feedback |
| Stage 5 test-case change via hint | Implementation hints only |
| Stage 6 Semgrep | detect-secrets + change-control checks |
| Stage 7 ARCHITECTURE / CHANGELOG for generated service | README + API docs |
| Stage 8 model-written summary | Code-generated summary from the event log |
| `explain` command | `trace` timeline |
| NFR catalog entries SEC-APIKEY, OBS-LOGS | RL-BASIC, SEC-INPUT, OBS-METRICS |

## Future enhancements (🔭)

* Postgres via Docker Compose as a selectable data store.
* Record/replay of Claude responses (deterministic tests, offline demo backup).
* Selective re-plan of only the components traced to a changed requirement.
* More NFR catalog entries and service archetypes (CLI, batch, UI).
* Full security stage with external scanners (gitleaks, OSV-Scanner, license scanning) and automatic fixing / waiver workflow — not in MVP because each is a separate install and OSV-Scanner needs network access.
* Container/sandbox isolation for running generated code.
* Container image build + deployment on release.
* Parallel execution of independent implementation tasks.
* Non-interactive gate answers file / scripted approvals.
* LangFuse / OpenTelemetry / Grafana integration.
* Web approval dashboard.
* Starting a new run from an existing approved design; `runs purge` and retention policy.
