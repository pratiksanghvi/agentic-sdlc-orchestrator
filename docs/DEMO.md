# Live walkthrough script (≈20–25 minutes)

Goal: show governed, stateful, non-linear orchestration — not just code generation. Keep a
recorded run open as a backup (`examples/`), because a live run takes 10–15 minutes.

## 0. Before the session (5 min)

```bash
.venv/bin/orchestrator check-config          # config + governance hashes
.venv/bin/pytest -q                          # 70+ tests, no API key needed
mvn -q -B dependency:go-offline -f examples/generated-url-shortener/pom.xml   # warm Maven cache
```

Open in tabs: `docs/ARCHITECTURE.md`, `examples/run-greenfield/ENGINEERING_SUMMARY.md`,
`policy/policy.yaml`, `catalog/nfr_catalog.yaml`, `catalog/stacks.yaml`.

## 1. Architecture in 3 minutes

* Show the stage diagram in the README; point at the five human gates and the three parallel joins
  (T1‖T2, 4a‖4b, S1‖S4, RR1‖RR2).
* "Agents propose, humans approve": approvals are bound to the exact artifact hash (show
  `artifacts/approvals.py`) — an edit after approval blocks the next stage.
* Bounded capability: show `catalog/nfr_catalog.yaml` — the orchestrator only promises NFRs it can
  build **and** validate; everything else gets a polite "not supported in MVP".

## 2. Start a greenfield run (keep it running)

```bash
.venv/bin/orchestrator run --requirement examples/requirements/greenfield-url-shortener.txt
```

Talking points while it runs:

| When you see | Say |
|---|---|
| Clarification questions | R2 classified ambiguities; only BLOCKING ones are asked; "reliability features" was vague, so the options are catalog entries. Answer with a number or Enter for the default. |
| Spec gate | Approve is hidden if deterministic validation fails. Every NFR must quote the user's words. Try **[r]** once with feedback to show the loop, then **[a]**. |
| Stack gate | ADR-001 with alternatives; unvalidated stacks are labelled; stacks without catalog implementations for requested NFRs are hidden. |
| Design gate | OpenAPI + SQLite DDL (executed in-memory) + traceability matrix, all validated by code. |
| Test plan gate | Catalog NFR cases (code) and functional cases (LLM) were generated in parallel and joined; every AC is covered. |
| Rollback question | A backup tag is always taken; this only decides whether to roll back if you end the run. |
| Stage 4/5 | Watch tasks compile and commit one by one; then build → SERVICE_READY → acceptance tests. |

## 3. While waiting: open the evidence of a recorded run

```bash
.venv/bin/orchestrator trace  <recorded_run_id> | less      # timeline
.venv/bin/orchestrator metrics <recorded_run_id>            # cost, tokens, first-pass, MTTR
.venv/bin/orchestrator verify-log <recorded_run_id>         # tamper check
```

* Show one `llm_call` record in `logs/events.jsonl`: full prompt, response, tokens, latency, cost,
  request id.
* Tamper demo: copy the run folder, edit one character in an old log line, run `verify-log` →
  "chain broken at N".
* Show the product repo: `git -C workspaces/<product> log --oneline --all --decorate` — task
  commits, fix commits, `pre-impl/*` backup tags, `failed/*` branch from a failed run, `v0.1.0`.

## 4. Show recovery (from the recorded failure run, or live)

* The fix agent's diagnosis in the log: in one run it identified a defect in the *test harness*,
  not the product — the tests are frozen, so it reported it instead of weakening them.
* Escalation screen: build / startup / acceptance status, history, hint or end.
* Rollback: confirmation, message, `failed/<run>` branch preserved, `master` untouched.

## 5. Final verdict

At the release gate show the readiness checklist and metrics, then **ACCEPT** → merge to `master`
and tag. Show `ENGINEERING_SUMMARY.md` (decision lineage section).

## 6. Brownfield and ambiguous (if time allows)

```bash
.venv/bin/orchestrator run --requirement examples/requirements/brownfield-link-expiry.txt \
    --product workspaces/<product>
.venv/bin/orchestrator run --requirement examples/requirements/ambiguous-url-shortener.txt
```

* Brownfield adds Stage 0: snapshot + impact analysis (endpoints, modules, tables, compatibility
  risks) approved by a human; the existing stack is kept; no re-scaffolding; releases `v0.2.0`.
* Ambiguous: the intake shows several BLOCKING questions and logs non-blocking defaults as
  assumptions in the spec.

## Prompts to try live

| Requirement | Shows |
|---|---|
| `Build a URL shortener service with core APIs, analytics, and reliability features.` | Clarification of vague NFRs into catalog options |
| `Build a URL shortener. Limit each client to 30 requests per minute. Redirects must respond in under 50 ms. Encrypt data at rest.` | RL-BASIC with the user's value; polite "not supported" for performance and encryption |
| `Make the links safer and the analytics more useful.` | Ambiguity handling and assumptions |
| `Add optional link expiry ... expired links return 410 Gone.` with `--product` | Brownfield impact analysis |
| A requirement containing a fake secret such as `aws_secret_access_key = '...'` | R1 intake guardrail rejects it before any model call |

## Questions to expect

* *Why LangGraph and not your own engine?* — durable interrupts, checkpoints, subgraphs and
  parallel joins are solved problems; the value is in the governance layered on top.
* *Why are acceptance tests not written by the LLM as code?* — the human approves a structured
  plan; code generation from it is deterministic, so the approved tests are exactly the executed
  tests.
* *What stops an agent from cheating?* — tests live outside the product repo and are
  hash-checked; path/dependency/suppression guardrails; approvals bound to hashes; the fix agent
  cannot touch tests.
* *Limitations?* — no OS sandbox, SQLite only, Java the only validated stack, resume/re-plan
  rules parked; see ARCHITECTURE "Deadline scope".
