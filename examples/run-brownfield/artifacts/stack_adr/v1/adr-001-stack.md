# ADR-001: Technology stack

## Status

Proposed

## Decision

Use **java21-springboot3-maven**.

## Rationale

Context: the spec adds optional link expiry (FR-1..FR-15) to an existing Spring Boot 3 / Java 21 / SQLite (JdbcTemplate) URL shortener. Decision: keep java21-springboot3-maven. The existing system must keep its stack, this stack is the only one VALIDATED end-to-end, and the spec has no constraints or NFRs that require any other technology. Every requirement is a localized delta to existing components. FR-1/2/3/9 add an Integer expiresInDays to CreateLinkRequest, with a field-scoped strict deserializer (accepting only JSON integer tokens in 1..3650 and treating null as absent per FR-8) that throws a dedicated InvalidExpiryException mapped to 400 problem+json with an expiry-specific detail. Because validation happens before any insert, FR-4 holds. FR-6 sets expiresAt = createdAt + N×24h, both derived from one Clock instant and stored in the fixed-width UTC text format. FR-7 adds a nullable expires_at column through an idempotent startup migration, so existing rows get NULL and never expire. FR-5/10/11/12/15 use an expiry-aware atomic UPDATE in resolveAndCount followed by an existence lookup to choose between 404 and LinkExpiredException, which maps to 410 'Gone' with Cache-Control: no-store. FR-13/14 leave the details, analytics and response DTOs unchanged and keep global unknown-property tolerance.

## Options considered

### Java 21 + Spring Boot 3 + Maven (existing stack) (java21-springboot3-maven)

java · Spring Boot 3 (Spring Web MVC, JdbcTemplate, ProblemDetail error handling) · maven · SQLite via JdbcTemplate (existing short_links table, plus a nullable expires_at TEXT column added by an idempotent PRAGMA table_info startup migration) · JUnit 5 + Spring Boot Test (MockMvc) with an injectable java.time.Clock bean for time control

Fit: Excellent. This is the mandated existing stack. Every MVP requirement (FR-1..FR-15) maps onto existing components: CreateLinkRequest, LinkService, ShortLinkRepository, ProblemExceptionHandler, RedirectController and schema migration. No response DTO changes are needed (FR-14).

Pros: This is the existing service's stack, so the change is incremental and needs no rewrite (FR-1..FR-15 are all deltas to existing classes).; VALIDATED end-to-end in this orchestrator.; Spring's ProblemExceptionHandler already produces application/problem+json. Adding a LinkExpiredException handler (410, title 'Gone', Cache-Control: no-store) satisfies FR-5 and FR-15 directly.; Jackson can be configured on the expiresInDays field only (e.g. a custom deserializer that accepts only VALUE_NUMBER_INT tokens and range-checks 1..3650). This meets FR-3 and FR-9 without enabling global strict deserialization, so unknown properties like 'alias' are still ignored (FR-14).; A single UPDATE ... WHERE short_code=? AND (expires_at IS NULL OR expires_at > ?) inside the existing transaction gives atomic expiry-aware click counting (FR-10, FR-11). A follow-up lookup separates 404 from 410 (FR-12).; An injectable java.time.Clock bean enables the controllable-clock acceptance tests (AC-1.2, AC-6.x, AC-7.1, AC-10.x, AC-13.x, AC-15.1; assumption A-6).

Cons: SQLite lacks ADD COLUMN IF NOT EXISTS. An idempotent Java-side migration (PRAGMA table_info check, then ALTER TABLE) is required for AC-7.2.; Changing the ShortLinkRepository.insert and ShortLinkRecord signatures breaks existing callers and tests, which must be updated in the same change.; Jackson's default coercions (string to int, float truncation, BigInteger overflow) must be explicitly defeated for this field, otherwise FR-3, FR-9 and AC-3.2 fail.

### Python 3.12 + FastAPI (python312-fastapi)

python · FastAPI (Pydantic v2) · pip / uv · SQLite via sqlite3 / SQLAlchemy Core · pytest + httpx TestClient

Fit: Poor. The existing system is Java/Spring Boot and must be kept. Switching stacks for an incremental feature is unjustified.

Pros: Pydantic strict int with ge=1, le=3650 expresses FR-2, FR-3 and FR-9 concisely.; Lightweight, with fast iteration.

Cons: Requires rewriting the entire existing Java service, which is out of scope ('existing behavior ... that this change does not alter').; Not yet validated end-to-end.; Would need a data migration and full re-verification of all existing contracts (404, problem+json, Cache-Control, click semantics).

### Go 1.22 + chi (go122-chi)

go · chi router + net/http · go modules · SQLite via database/sql (modernc.org/sqlite or mattn/go-sqlite3) · go test + httptest

Fit: Poor. It violates the requirement to keep the existing service's stack and adds risk with no spec-driven benefit.

Pros: Small static binary with a simple deployment.; json.Number decoding makes rejecting non-integer literals for FR-9 straightforward.

Cons: Requires a full rewrite of the existing Java service.; Not yet validated end-to-end.; problem+json handling, migrations and click semantics would all need re-implementing and re-verifying.

## Consequences

- The service stays on Java 21, Spring Boot 3, Maven and SQLite/JdbcTemplate, so there is no migration of runtime, build or deployment.
- An idempotent Java-side schema migration (PRAGMA table_info check, then ALTER TABLE short_links ADD COLUMN expires_at TEXT) must run on every startup and be safe on both fresh and pre-existing databases (FR-7, AC-7.2).
- A java.time.Clock bean is introduced and injected into LinkService, replacing direct Instant.now calls, so tests can control time (A-6, FR-6, FR-10).
- ShortLinkRecord, the ShortLinkRepository.insert, MAPPER and SELECT columns, and the click-increment query change signatures. Existing ShortLinkRepositoryTest and other callers must be updated in the same change.
- New exceptions are added: InvalidExpiryException (400) and LinkExpiredException (410). ProblemExceptionHandler gains handlers so the catch-all 500 is never hit (FR-3, FR-5, AC-3.2).
- Strict integer handling is scoped to the expiresInDays field only. Global FAIL_ON_UNKNOWN_PROPERTIES stays disabled, so 'alias' is still ignored (FR-14).
- ShortLinkResponse and the analytics DTO are not changed, and no expiresAt is exposed (FR-14, C-4).
- Field name expiresInDays rests on assumption A-1 (BLOCKING Q-1). The reviewer must confirm it at approval, and a rename would be a single-point change in CreateLinkRequest.

## Rejected alternatives

- python312-fastapi: rejected because it would require rewriting the existing Java service, contradicting the mandate to keep the existing stack. It is also not validated end-to-end, and the spec has no constraint favouring Python.
- go122-chi: rejected because it would require a full rewrite and re-verification of all existing contracts. It is not validated end-to-end, and nothing in the spec requires Go.
