# Existing system and change impact

A public (unauthenticated) Spring Boot 3 / Java 21 URL shortener backed by SQLite through JdbcTemplate. Clients POST an absolute http/https URL and receive a new, independent short link with a random 7-character base62 code. GET /{code} returns a 302 redirect to the long URL and atomically increments the click count and last-click timestamp. Separate endpoints return link details and click analytics. Errors are returned as application/problem+json, and unknown codes return 404.

## Endpoints

- `POST /api/links` — Create a new short link from JSON {url}. Returns 201 with a Location header /api/links/{code} and a ShortLink body (shortCode, longUrl, createdAt). Returns 400 for an invalid or malformed body, 415 for a non-JSON content type, and 500 for unexpected errors.
- `GET /api/links/{code}` — Return link details (shortCode, longUrl, createdAt). Returns 404 if the code is unknown.
- `GET /api/links/{code}/analytics` — Return click analytics (shortCode, clickCount, lastClickedAt, which is null if the link was never clicked). Returns 404 if the code is unknown.
- `GET /{code}` — Return a 302 redirect with Location set to the long URL and Cache-Control: no-store, and count the click. Returns 404 if the code is unknown.

## Impacted

- **resources/schema.sql (table short_links)** — Needs a new nullable column, e.g. expires_at TEXT, where NULL means the link never expires. CREATE TABLE IF NOT EXISTS will not add the column to existing app.db files. An idempotent migration is required. SQLite has no ADD COLUMN IF NOT EXISTS, and the script runs on every startup, so a plain ALTER TABLE would fail on the second start. A PRAGMA table_info check in Java or a migration tool is needed.
- **api.CreateLinkRequest** — Add an optional expiry-in-days field (name to be decided, e.g. expiresInDays, as Integer/Long so that 'absent' is distinguishable).
- **service.LinkService.create** — Validate the optional days value: reject zero, negative, non-integral and too-large values with 400. Compute expiresAt = createdAt + days and pass it to the repository.
- **Validation / new exception** — InvalidUrlException's handler hard-codes the detail 'url must be an absolute http or https URL'. Expiry validation needs its own exception, or a generalised handler, so the 400 detail is accurate.
- **service.LinkService.resolveAndCount** — Must detect expiry and fail with a new LinkExpiredException instead of redirecting. Today it increments before reading, so an expired link would still be counted unless the logic changes. One option is UPDATE ... WHERE short_code=? AND (expires_at IS NULL OR expires_at > now), then a lookup to tell unknown (404) apart from expired (410).
- **service.LinkExpiredException (new)** — New domain exception that maps to 410 Gone.
- **api.ProblemExceptionHandler** — Add a handler for LinkExpiredException that returns 410 problem+json with title 'Gone'. Without it, the catch-all would return 500.
- **GET /{code} (RedirectController)** — Gains a new 410 response for expired links. The 302 and 404 behaviour is otherwise unchanged.
- **POST /api/links (LinkController.create)** — Accepts the new optional field and passes it to the service. The response likely gains an expiresAt field.
- **api.ShortLinkResponse and LinkController.toResponse** — Optionally expose expiresAt (null when the link never expires) in create and details responses. This is an additive response field.
- **persistence.ShortLinkRecord** — Add an Instant expiresAt component. This changes the canonical constructor, so the MAPPER and all constructor call sites must be updated.
- **persistence.ShortLinkRepository** — Changes needed in: insert (signature and SQL), the MAPPER and the SELECT column list in findByCode, and incrementClick/findLongUrl (expiry-aware query or a separate expiry lookup). expires_at must use the same fixed-width format() so SQLite text comparison orders correctly.
- **GET /api/links/{code} and /analytics** — Not required to change by the request, but must be explicitly decided. The assumption is that they keep returning 200 for expired links. Details may show expiresAt.
- **Time source (Instant.now in LinkService)** — Testing expiry measured in days needs an injectable java.time.Clock bean, or direct DB manipulation in tests.
- **Tests: ShortLinkRepositoryTest** — Calls repo.insert(code, url, instant) and will break if the signature changes, unless an overload is kept. Needs new tests for storing and reading expiry.
- **Tests: LinkServiceTest** — Needs new cases: expiry computation, invalid days, an expired link throwing LinkExpiredException without incrementing clicks, and links without expiry never expiring.
- **Tests: LinkApiTest** — Needs new cases: create with expiry, 400 for bad expiry values, 410 problem+json on an expired redirect, 404 still returned for unknown codes, and details/analytics behaviour for expired links. Existing tests should pass unchanged.
- **Tests: ShortenerApplicationTests** — Schema-apply smoke test. It should also confirm that the migration runs on a fresh DB and on a pre-existing DB.
- **docs/API.md and README.md** — Document the new request field, the response field, the 410 response on GET /{code}, and the expiry semantics.

## Compatibility risks

- Create requests without an expiry field must still return 201 with the same Location and body. The resulting links must never expire. A required field or a non-null default would break existing clients.
- Existing databases created before the change lack expires_at. If schema.sql only edits CREATE TABLE IF NOT EXISTS, every SELECT or INSERT that references expires_at fails with a 500 on upgraded deployments. A non-idempotent ALTER TABLE in schema.sql would make the second startup fail, because the script runs on every boot. Existing rows must end up with NULL (never expire).
- Unknown JSON properties are currently ignored: LinkApiTest sends "alias":"mine" and expects 201. Enabling strict deserialization to validate the new field would break this and the 'no custom alias' contract.
- GET /{code} for an unknown code must stay 404, not 410. Valid, non-expired links must keep the 302 with the Location header and Cache-Control: no-store.
- Click semantics: each successful redirect increments click_count by exactly one and updates last_clicked_at. With the current increment-then-read order, a naive expiry check placed after the increment would count clicks on expired links. Product needs to confirm that 410 responses are not counted. The expiry check and increment should be atomic (single UPDATE with an expiry predicate, or check-then-update within the existing transaction).
- Details and analytics endpoints must keep returning 200 with their current fields for every existing link. Whether expired links return 200 or 410 there is unspecified; returning 410 would change existing contracts.
- Adding expiresAt to ShortLinkResponse is additive, but Jackson serialises nulls by default. Non-expiring links would then show "expiresAt": null, which strict clients may not expect. This is acceptable but must be documented.
- Error format must stay application/problem+json with type, title, status and detail. The new 410 must follow it with title 'Gone'. A missing handler would produce a 500 via the catch-all.
- Validation of days: Jackson by default coerces strings ('7'→7) and truncates floats (1.9→1). Very large values can overflow Instant.plus and produce a 500, or yield years beyond 9999 that break the fixed-width timestamp format and lexicographic comparison. Zero and negative values need a defined 400. Validation failures must not persist a row, mirroring the 'invalid URL persists nothing' guarantee.
- Boundary semantics at exactly expiresAt (expired when now >= expiresAt?) and the meaning of 'days' (24h multiples from createdAt vs calendar days) must be defined. All comparisons must use the same UTC microsecond text format so SQLite string comparison stays correct.
- Changing the ShortLinkRecord constructor and ShortLinkRepository.insert signature breaks compilation of existing callers and ShortLinkRepositoryTest unless overloads are kept or the tests are updated.
- Retry-on-collision logic in create must still pass expiresAt on every attempt, and createdAt and expiresAt must be derived from the same instant.
