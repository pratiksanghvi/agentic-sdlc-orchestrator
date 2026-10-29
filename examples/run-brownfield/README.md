# Recorded brownfield run

A real end-to-end brownfield run with live Claude calls: the change request
`examples/requirements/brownfield-link-expiry.txt` (optional link expiry, expired links return
410 Gone) applied to the accepted `v0.1.0` URL shortener from `../run-greenfield/`.

Run `live-brown-2`, all stages 0–8 in one run:

| Stage | Result |
|---|---|
| 0 Codebase | Snapshot of the v0.1.0 repo; impact analysis of endpoints, modules, tables, impacted areas and compatibility risks (see `IMPACT_ANALYSIS.md`), approved |
| 1–3 | Spec for the new behavior only; Java stack kept (enforced); OpenAPI describing the complete service; approved test plan |
| 4 | 7 tasks modifying the existing project (no re-scaffold), each compiled and committed |
| 5 | Build + unit tests passed; **33/33 acceptance tests passed on the first attempt** (no fixes) |
| 6–8 | 0 security findings; docs regenerated; ACCEPT → merged and tagged **`v0.2.0`** |

18 LLM calls, all valid on the first attempt; estimated cost $2.31.

Gates were answered by a scripted operator (accept suggested defaults, approve, accept) so the run
could proceed unattended; a live demo uses the interactive CLI.

Files: `artifacts/` (every versioned artifact with manifest and hashes), `events.jsonl` (the
hash-chained audit log), `trace.txt`, `metrics.json`, `ENGINEERING_SUMMARY.md`,
`IMPACT_ANALYSIS.md`, `v0.1.0-to-v0.2.0.diff` (the code change the orchestrator made: 20 files,
+610/−80) and `product-git-log.txt` (branches, backup tags, releases).

An earlier attempt (`live-brown-1`, not included) stopped during Stage 4 because the API account
ran out of credit; that run led to the safe-stop handling for unrecoverable model errors.
