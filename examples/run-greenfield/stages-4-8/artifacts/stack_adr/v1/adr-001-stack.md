# ADR-001: Technology stack

## Status

Proposed

## Decision

Use **java21-springboot3-maven**.

## Rationale

The spec has no constraints that mandate a technology and no NFRs (C-1 answered 'none'), so the choice rests on delivery risk and on fit with the functional requirements. java21-springboot3-maven is the only supported stack VALIDATED end-to-end, and it fully covers the MVP scope:
- Create: POST, with service-generated codes (FR-1, FR-8), an independent row per submission (FR-9), and http/https absolute-URL validation that returns 400 (FR-10).
- Redirect: GET, returning 302 with a Location header (FR-2, FR-3). An atomic SQL UPDATE increments click_count and sets last_click_at only on a successful redirect (FR-5, FR-6, FR-14).
- Details: GET, returning code, longUrl and createdAt (FR-4, FR-11).
- Analytics: a separate GET returning clickCount and lastClickAt, where lastClickAt is null when the link has never been clicked (FR-7, FR-13).
- Errors and access: 404 for unknown codes on redirect, details and analytics (FR-12), and no authentication layer (FR-15).
SQLite is the stack's datastore and is enough to persist links and counters.

## Options considered

### Java 21 + Spring Boot 3 + Maven + SQLite (java21-springboot3-maven)

java · Spring Boot 3 (Spring Web MVC) · Maven · SQLite (via JDBC / Spring JDBC) · JUnit 5 with Spring Boot Test (MockMvc / TestRestTemplate)

Fit: Strong fit. It covers all MVP FRs (FR-1 to FR-15) with a single short_link table (code, long_url, created_at, click_count, last_click_at) and endpoints for create, redirect, details and analytics. It adds no NFRs, which is consistent with C-1 and the empty NFR list.

Pros: Only stack marked VALIDATED end-to-end in the orchestrator, which lowers delivery risk; Spring Web MVC handles the needed status codes directly: ResponseEntity with 302 plus a Location header (FR-2, FR-3), 404 for unknown codes (FR-12) and 4xx for validation failures (FR-10); java.net.URI makes it simple to accept only absolute http/https URLs (FR-10); An atomic SQL UPDATE (clicks = clicks + 1, last_click_at = now) gives exactly-once counting per successful redirect (FR-5, FR-6, FR-14); HTTP-level tests that do not follow redirects map directly onto every acceptance criterion (AC-1.1 to AC-15.1); No Spring Security dependency is needed, so all endpoints stay unauthenticated (FR-15)

Cons: More verbose and slower to start than the Python or Go options; Spring Boot is heavier than this small service strictly needs; SQLite serializes writes, so concurrent redirect increments are serialized. This is acceptable because the spec has no throughput NFR.

### Python 3.12 + FastAPI + SQLite (python312-fastapi)

python · FastAPI · pip / uv (pyproject.toml) · SQLite (sqlite3 standard library) · pytest with httpx / FastAPI TestClient

Fit: Functionally adequate for FR-1 to FR-15. It is less preferred only because it has not been validated end-to-end.

Pros: Very concise code for four endpoints; RedirectResponse(status_code=302) covers FR-3 directly; Fast test cycle with pytest

Cons: Not yet validated end-to-end in the orchestrator pipeline, so the build, test and deploy path carries more risk; FastAPI/Pydantic return 422 on validation errors by default. That still satisfies the 4xx in FR-10, but the behavior needs care.; The TestClient follows redirects by default, so tests must disable this explicitly for AC-2.1 and AC-3.1

### Go 1.22 + chi + SQLite (go122-chi)

go · chi router (net/http) · go modules (go build / go test) · SQLite (database/sql with a SQLite driver) · go test with net/http/httptest

Fit: Functionally adequate for FR-1 to FR-15. It is less preferred because it has not been validated end-to-end and the SQLite driver adds build complexity.

Pros: Small, fast binary that starts quickly; net/http gives explicit control over 302 and Location headers (FR-2, FR-3); httptest allows simple HTTP-level assertions

Cons: Not yet validated end-to-end in the orchestrator pipeline; SQLite drivers either need cgo (mattn) or carry an extra dependency (modernc), which complicates the build; More hand-written boilerplate for JSON handling and validation

## Consequences

- Persistence is a single SQLite table, short_link(code PK, long_url, created_at, click_count default 0, last_click_at nullable), which traces to FR-1, FR-5, FR-6, FR-9, FR-11 and FR-13.
- Click counting uses one atomic UPDATE statement per successful redirect, so no click is lost or double-counted. Unknown codes never touch any row (FR-14, AC-14.2).
- Short codes are random, service-generated strings, and a uniqueness check retries on collision (FR-8, FR-9).
- Spring Security, rate limiting, problem+json validation and Prometheus metrics are not included. No NFR was selected (C-1), and authentication is out of scope (FR-15).
- The service exposes no update, delete, expiration, custom alias or UI endpoints, in line with the out_of_scope list.
- Tests are HTTP-level JUnit 5 / Spring Boot tests with redirect following disabled, one or more per acceptance criterion from AC-1.1 to AC-15.1.
- The service accepts JVM startup time and footprint as costs, since the spec sets no performance NFR.

## Rejected alternatives

- python312-fastapi: functionally suitable and concise, but not yet validated end-to-end in the orchestrator, and the spec has no constraint requiring Python. Its default 422 validation responses and redirect-following test client would also need extra care.
- go122-chi: functionally suitable and lightweight, but not yet validated end-to-end. The SQLite driver choice (cgo or a pure-Go driver) adds build risk, and the spec has no constraint requiring Go.
- Non-supported options such as Node.js/Express or a Redis-backed counter store were considered for comparison only. They cannot be selected because they are not in supported_stacks, and Redis would also add infrastructure that no requirement asks for.
