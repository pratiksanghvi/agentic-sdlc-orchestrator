# AI usage

This project was designed and built with an AI coding assistant (Claude Code) working under my
direction. This file records how: what I asked for, what I decided, and where I overrode or
narrowed the assistant's proposals. (At runtime, the orchestrator logs every one of its own model
calls — prompt, response, tokens, latency and cost — in each run's audit log.)

## How I worked with the assistant

1. **Requirements first, no design until the gaps were closed.** I asked the assistant to read the
   assignment, summarize it and list requirement-gap questions with recommended answers — and
   explicitly not to start design. I answered the questions myself and turned them into stated
   assumptions.
2. **Stage-by-stage design review.** I reviewed every SDLC stage separately (steps, prompts,
   gates) before moving on, and parked topics I wanted to think about rather than letting them be
   decided by default.
3. **Milestone builds with commits only when testable**, a live run after each stage, and the
   design document kept current with implemented / designed-only / cut / future / parked marks.
4. **Every prompt and decision was logged** in a running decision log during the work.

## Key decisions I made (and where I overrode the assistant)

| Topic | Assistant proposed | My decision |
|---|---|---|
| Framing | Orchestrator vs. product ambiguity | The orchestrator is the product; if it cannot produce a working service, it failed. A human confirms the outcome. |
| Scope order | All three scenarios together | Greenfield first; brownfield and ambiguous as orchestrator enhancements |
| Framework | Own DAG engine to show depth | **LangGraph** — no home-grown workflow engine to build and maintain |
| Tech stack | Fixed Java | The orchestrator's Design stage proposes the stack per requirement; human approves. Java/Python/Go supported; Java validated |
| Replay mode | Record/replay for tests and demo backup | Not in MVP — build to the requirement; every response saved for traceability instead |
| NFRs | Always-on baseline | NFRs only when the user asks, only rate limit / security / observability, mapped to a bounded catalog the orchestrator can build **and** validate; polite "not supported" for everything else; never from assumptions |
| Health check | `/actuator/health` | Rejected (Java-specific): stack-agnostic readiness via a `SERVICE_READY port=<port>` log line |
| Tests | Test agent placement | Generate the test plan after design, human approves it, tests implemented in parallel with code and run after |
| Failure handling | Best-so-far rollback | Always back up; ask once whether to roll back; confirm before rolling back; unlimited human hints, one fix + one verify each |
| Security stage | External scanners | Report-only and zero extra installs; external scanners documented as future work |
| Docs | Approval gate | No approval — humans edit docs directly |
| Data store | H2 / Postgres | SQLite in MVP; Postgres via Docker as a future enhancement |
| Re-planning | Full rule set | Built the three foundations (versioned artifacts, hash-bound approvals, restartable stage contracts); parked the rest |
| Deadline | Full design | Approved a cut list to fit the deadline; everything cut stays documented as designed-only |

## Notable moments

* The assistant found during the build that the current Claude models reject forced tool choice,
  so structured output switched to schema-constrained responses validated by Pydantic.
* A live run surfaced a bug in the acceptance-test harness (captured variables were not
  substituted in assertion values). The orchestrator's own fix agent diagnosed it as a harness
  defect rather than a product defect; the harness was fixed and the next run passed 24/24.
* A live run showed the stack agent preferring an unvalidated stack; the prompt and gate were
  changed to prefer and label validated stacks.

## Design choices the assistant made that I accepted

* Acceptance tests are generated **deterministically** from the approved, structured test plan
  (no LLM), so nothing can be added, weakened or skipped between approval and execution.
* Startup error-pattern lines are reported but do not fail a start on their own (frameworks log
  benign "ERROR" text); readiness is the `SERVICE_READY` line plus a TCP connect.
* Brownfield adds a Stage 0 (codebase snapshot + impact analysis + approval) in front of the
  unchanged pipeline.
