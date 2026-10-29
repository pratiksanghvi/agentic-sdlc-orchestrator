# Engineering summary — Optional link expiry for short links (410 Gone on expired redirects)

Run: `live-brown-2`

## Plan & rationale

- Stack: `java21-springboot3-maven` — Context: the spec adds optional link expiry (FR-1..FR-15) to an existing Spring Boot 3 / Java 21 / SQLite (JdbcTemplate) URL shortener. Decision: keep java21-springboot3-maven. The existing system must keep its stack, this stack is the only one VALIDATED end-to-end, and the spec has no constraints or NFRs that require any other technology. Every requirement is a localized delta to existing components. FR-1/2/3/9 add an Integer expiresInDays to CreateLinkRequest, with a field-scoped strict deserializer (accepting only JSON integer tokens in 1..3650 and treating null as absent per FR-8) that thr
- 15 functional requirements, 0 NFRs, 26 acceptance criteria.

## Artifacts

- acceptance_suite: v1 `sha256:cf83f53ea258`
- analysis: v3 `sha256:134ab3e3b5c1`
- clarifications: v2 `sha256:4af9e0f8bf4c`
- codebase_analysis: v1 `sha256:19add5e4a4c8`
- codebase_snapshot: v1 `sha256:6c4a8a47cb17`
- design: v1 `sha256:6a7f3b25068f`
- docs: v1 `sha256:617043c81cdc`
- nfr_plan: v1 `sha256:30709677c82b`
- requirement_input: v1 `sha256:9d7e2b8e5f8e`
- security_report: v1 `sha256:c37304f792b3`
- spec: v1 `sha256:364e3610e591`
- stack_adr: v1 `sha256:4fb9a16b0d9e`
- task_plan: v1 `sha256:c7ba04440e7b`
- test_plan: v2 `sha256:ff3b9aab5ca8`
- verification_report: v1 `sha256:432c308b9069`

## Validation

- Acceptance tests: 33/33 passed (verification attempt 1).
- Build + unit tests: passed.
- Security/policy findings: 0.

## Readiness checklist

- ✅ spec approved and unchanged
- ✅ stack_adr approved and unchanged
- ✅ design approved and unchanged
- ✅ test_plan approved and unchanged
- ✅ acceptance_suite approved and unchanged
- ✅ acceptance tests 33/33
- ✅ security findings: 0 (awareness)
- ✅ documentation warnings: 0
- ✅ product working tree clean

## Assumptions

- A-1: The optional request field is named expiresInDays. This is the recommended default for BLOCKING question Q-1, which the clarifications did not answer. The reviewer must confirm or change the name before approval.
- A-2: An explicit JSON null for expiresInDays is treated as absent. The request returns 201 and the link never expires.
- A-3: Only JSON integer literals count as whole-number JSON integers. Integral values written with a fraction or exponent (7.0, 7e0) are rejected with 400.
- A-4: The expiry instant is creation time + N × 24 hours (UTC). A link is expired when the current time is greater than or equal to the expiry instant.
- A-5: The 410 problem+json response uses title 'Gone', a generic detail such as 'short link has expired', and Cache-Control: no-store, as on the redirect.
- A-6: Acceptance tests that need time to pass can control the service's notion of current time, for example with an adjustable test clock.

## Not supported in MVP (requested but not built)

- none

## Risks, trade-offs and limitations

- Generated code runs on the host without an OS sandbox.
- SQLite only; single instance; no authentication unless requested.
- SAST and dependency-CVE scanning are not part of this MVP.

## Decision lineage

- 2026-10-29T18:00:03 impact_analysis codebase_analysis  by agent:codebase-analyst
- 2026-10-29T18:00:03 approval impact_approval APPROVE by human:reviewer
- 2026-10-29T18:00:37 requirements_analyzed analysis  by agent:requirements-analyst
- 2026-10-29T18:01:11 requirements_analyzed analysis  by agent:requirements-analyst
- 2026-10-29T18:01:49 requirements_analyzed analysis  by agent:requirements-analyst
- 2026-10-29T18:02:45 spec_drafted spec  by agent:requirements-analyst
- 2026-10-29T18:02:45 approval spec_approval APPROVE by human:reviewer
- 2026-10-29T18:03:11 stack_proposed stack_adr  by agent:solution-architect
- 2026-10-29T18:03:11 approval stack_approval APPROVE by human:reviewer
- 2026-10-29T18:04:42 design_drafted design  by agent:solution-architect
- 2026-10-29T18:04:42 approval design_approval APPROVE by human:reviewer
- 2026-10-29T18:06:24 test_cases_designed   by agent:qa-test-designer
- 2026-10-29T18:08:18 test_cases_designed   by agent:qa-test-designer
- 2026-10-29T18:08:18 approval test_plan_approval APPROVE by human:reviewer
- 2026-10-29T18:08:32 task_plan task_plan  by agent:implementation

## Run metrics

```json
{
  "run_id": "live-brown-2",
  "status": "in_progress",
  "final_verdict": null,
  "end_to_end_ms": 723991,
  "time_split_ms": {
    "human_wait": 0,
    "tools": 11255,
    "agent_and_orchestration": 712736
  },
  "llm": {
    "calls": 18,
    "schema_retries": 0,
    "failed_calls": 0,
    "input_tokens": 227125,
    "output_tokens": 99136,
    "cost_usd": 2.3054,
    "per_stage": {
      "codebase": {
        "calls": 1.0,
        "input_tokens": 16188.0,
        "output_tokens": 6972.0,
        "cost_usd": 0.2042,
        "first_attempts": 1.0,
        "first_attempt_ok": 1.0,
        "first_pass_rate": 1.0,
        "latency_p50_ms": 63387,
        "latency_p95_ms": 63387
      },
      "requirements": {
        "calls": 4.0,
        "input_tokens": 25495.0,
        "output_tokens": 18377.0,
        "cost_usd": 0.4695,
        "first_attempts": 4.0,
        "first_attempt_ok": 4.0,
        "first_pass_rate": 1.0,
        "latency_p50_ms": 36238,
        "latency_p95_ms": 55681
      },
      "design": {
        "calls": 2.0,
        "input_tokens": 23602.0,
        "output_tokens": 14429.0,
        "cost_usd": 0.383,
        "first_attempts": 2.0,
        "first_attempt_ok": 2.0,
        "first_pass_rate": 1.0,
        "latency_p50_ms": 58615,
        "latency_p95_ms": 91257
      },
      "test_design": {
        "calls": 2.0,
        "input_tokens": 16469.0,
        "output_tokens": 29853.0,
        "cost_usd": 0.6629,
        "first_attempts": 2.0,
        "first_attempt_ok": 2.0,
        "first_pass_rate": 1.0,
        "latency_p50_ms": 107753,
        "latency_p95_ms": 113942
      },
      "implementation": {
        "calls": 8.0,
        "input_tokens": 141490.0,
        "output_tokens": 27475.0,
        "cost_usd": 0.5577,
        "first_attempts": 8.0,
        "first_attempt_ok": 8.0,
        "first_pass_rate": 1.0,
        "latency_p50_ms": 14486,
        "latency_p95_ms": 32221
      },
      "docs": {
        "calls": 1.0,
        "input_tokens": 3881.0,
        "output_tokens": 2030.0,
        "cost_usd": 0.0281,
        "first_attempts": 1.0,
        "first_attempt_ok": 1.0,
        "first_pass_rate": 1.0,
        "latency_p50_ms": 11860,
        "latency_p95_ms": 11860
      }
    }
  },
  "reliability": {
    "step_retries": 0,
    "task_attempts_failed": 0,
    "verification_attempts": 1,
    "fixes": 0,
    "rollbacks": 0,
    "mttr_ms": null,
    "mttr_auto_only_ms": null
  },
  "gates": {
    "impact_approval": {
      "APPROVE": 1
    },
    "spec_approval": {
      "APPROVE": 1
    },
    "stack_approval": {
      "APPROVE": 1
    },
    "design_approval": {
      "APPROVE": 1
    },
    "test_plan_approval": {
      "APPROVE": 1
    }
  },
  "audit_chain_intact": true
}
```
