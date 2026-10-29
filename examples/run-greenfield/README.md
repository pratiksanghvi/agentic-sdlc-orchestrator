# Recorded greenfield run

Evidence of a real end-to-end greenfield run with live Claude calls, recorded while building the
orchestrator.

| Folder | Run | Stages | Result |
|---|---|---|---|
| `stages-1-3/` | `live-td-1` | Requirements → Design → Test Design | spec v1, Java stack, design with OpenAPI + DDL, 24 approved test cases; 8 LLM calls, $0.90 |
| `stages-4-8/` | `live-impl-2` | Implementation → Verify → Security → Docs → Release | 5 tasks; first build failed (SQLite constraint mapping), 1 automatic fix; **24/24 acceptance tests passed**; 0 security findings; ACCEPT → `v0.1.0`; 8 LLM calls, $0.43 |

How it was recorded (stated plainly):

* Gates were answered by a **scripted operator** (accept suggested defaults, approve, accept) so
  the run could proceed unattended while development continued. A live demo uses the interactive
  CLI instead.
* The run was executed in two parts: `live-impl-2` was seeded with the approved artifacts of
  `live-td-1` (its log records those approvals as `seed:*` gates by `dev-seed`) and started at the
  Implementation stage. Everything from Stage 4 on ran live.
* An earlier attempt (`live-impl-1`, not included) exercised the failure path: it hit a bug in the
  acceptance-test harness (captured variables were not substituted in assertions), used all
  3 automatic fixes, escalated, ended, and rolled the workspace back after confirmation. The fix
  agent's diagnosis correctly pointed at the harness, which was then fixed.

Contents of each part: `artifacts/` (every versioned artifact with its manifest and hashes),
`events.jsonl` (the hash-chained audit log with every prompt, response, token count, latency,
human answer and decision), `trace.txt` (`orchestrator trace`), `metrics.json`
(`orchestrator metrics`). `ENGINEERING_SUMMARY.md` is the Stage 8 summary;
`product-git-log.txt` shows the product repository's branches, tags and commits;
`../generated-url-shortener/` is the generated Java service at tag `v0.1.0`.

Verify the audit chain of a recorded log:

```bash
.venv/bin/python -c "from pathlib import Path; from orchestrator.observability.eventlog import EventLog; print(EventLog(Path('examples/run-greenfield/stages-4-8/events.jsonl')).verify())"
```
