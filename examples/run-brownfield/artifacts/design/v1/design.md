# Design

Stack: `java21-springboot3-maven`

## Modules

- **config.ClockConfig** — Defines a java.time.Clock bean (Clock.systemUTC() in production). Tests replace it with an adjustable clock so that creation time and the current time used for expiry checks can be controlled (A-6). All 'now' values in LinkService come from this bean instead of Instant.now(). (FR-6, FR-5, FR-7, FR-10, FR-11)
- **api.CreateLinkRequest** — Request DTO for POST /api/links with String url and an optional expiresInDays field typed as com.fasterxml.jackson.databind.JsonNode. The raw JSON node is kept so that Jackson cannot coerce "7" to 7 or truncate 1.9 to 1, and so integer literals can be told apart from 7.0 and 7e0. Absent and explicit null both yield a null or NullNode value. Global ObjectMapper settings are unchanged, so unknown properties such as alias are still ignored. (FR-1, FR-3, FR-8, FR-9, FR-14)
- **api.LinkController** — POST /api/links passes url and the raw expiresInDays node to LinkService.create and returns 201 with Location /api/links/{code} and the unchanged ShortLinkResponse (shortCode, longUrl, createdAt). GET /api/links/{code} and GET /api/links/{code}/analytics are unchanged and ignore expiry, so they return 200 for expired links. toResponse does not map expiresAt. (FR-1, FR-2, FR-13, FR-14)
- **api.ShortLinkResponse / api.LinkAnalyticsResponse** — Existing response records, left unchanged with no expiresAt field. Create and details return exactly shortCode, longUrl and createdAt. Analytics returns exactly shortCode, clickCount and lastClickedAt. (FR-13, FR-14)
- **api.RedirectController** — GET /{code} calls LinkService.resolveAndCount. On success it returns 302 with Location set to the long URL and Cache-Control: no-store. LinkNotFoundException and LinkExpiredException propagate to ProblemExceptionHandler, which returns 404 or 410 with no Location header. (FR-5, FR-11, FR-12)
- **api.ProblemExceptionHandler** — Existing problem+json mapping, extended. A new handler maps InvalidExpiryException to 400 (title 'Bad Request') with an expiry-specific detail. A new handler maps LinkExpiredException to 410 (title 'Gone', detail 'short link has expired') with the header Cache-Control: no-store. The existing handlers stay as they are: InvalidUrlException 400, malformed body 400, 415, LinkNotFoundException 404, and the catch-all 500. (FR-3, FR-5, FR-9, FR-12, FR-15)
- **service.ExpiryPolicy** — Validates and converts the raw expiresInDays node. A null or NullNode value returns Optional.empty() (never expires). A node is accepted only if isIntegralNumber() is true, which covers JSON integer literals (Int, Long or BigInteger nodes). Its value is compared as a BigInteger against the range 1..3650, so 99999999999999999999 cannot overflow. Any other value throws InvalidExpiryException: zero, negative, out of range, a float literal such as 1.5, 7.0 or 7e0, a string, a boolean, an object or an array. computeExpiresAt(createdAt, days) returns createdAt.plus(Duration.ofHours(24L * days)). The 3650-day cap keeps timestamps within the fixed-width year range. (FR-2, FR-3, FR-6, FR-8, FR-9)
- **service.LinkService** — create(url, expiresInDaysNode) validates the URL (existing logic) and then the expiry through ExpiryPolicy, before any database write. It takes createdAt = clock.instant() once and derives expiresAt from that same instant (null if no expiry). Both are passed on every collision-retry insert. resolveAndCount(code) runs in the existing transaction. It sets now = clock.instant() and calls repository.incrementClickIfNotExpired(code, now). If one row is updated, it returns findLongUrl(code). If none is updated, it throws LinkExpiredException when existsByCode(code) is true and LinkNotFoundException otherwise. Expired links are therefore never counted. (FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, FR-10, FR-11, FR-12)
- **service.InvalidExpiryException / service.LinkExpiredException** — New domain exceptions. InvalidExpiryException carries the detail 'expiresInDays must be a whole-number JSON integer from 1 to 3650' and maps to 400, separate from the URL validation message. LinkExpiredException maps to 410 Gone. (FR-3, FR-5, FR-9, FR-15)
- **persistence.ShortLinkRecord** — Gains an Instant expiresAt component, which is null when the link never expires. The MAPPER and all constructor call sites are updated. (FR-6, FR-7)
- **persistence.ShortLinkRepository** — insert(code, url, createdAt, expiresAt) writes expires_at using the same fixed-width UTC microsecond format() as the other timestamps, or NULL. The existing insert(code, url, createdAt) is kept as an overload that delegates with null. findByCode SELECT and MAPPER include expires_at. A new method, incrementClickIfNotExpired(code, now), runs: UPDATE short_links SET click_count = click_count + 1, last_clicked_at = ? WHERE short_code = ? AND (expires_at IS NULL OR expires_at > ?). The predicate means a link is expired when now >= expires_at. A new existsByCode(code) method is added. findLongUrl is unchanged. The repository depends on SchemaMigrator, so the column exists before any query runs. (FR-4, FR-6, FR-7, FR-10, FR-11, FR-12)
- **persistence.SchemaMigrator** — Idempotent startup migration. It is an InitializingBean annotated @DependsOnDatabaseInitialization, so it runs after schema.sql. It reads PRAGMA table_info(short_links) and runs ALTER TABLE short_links ADD COLUMN expires_at TEXT only when the column is missing. Pre-existing rows therefore get NULL (never expire). A fresh database already has the column and is skipped, and every later restart is a no-op. (FR-7)
- **resources/schema.sql** — CREATE TABLE IF NOT EXISTS short_links, now including the nullable expires_at column for fresh databases. It contains no ALTER statements, because the script runs on every boot. (FR-6, FR-7)
- **docs (docs/API.md, README.md)** — Documents the optional expiresInDays request field and its validation rules, the 410 Gone response on GET /{code}, the expiry semantics (N x 24h from createdAt, expired when now >= expiry), and that details and analytics are unaffected. (FR-1, FR-5, FR-6, FR-13)

## Non-functional implementation (from catalog)

- none

## Primary flows

### Startup schema initialisation and migration

1. Spring SQL init runs schema.sql. CREATE TABLE IF NOT EXISTS creates short_links with expires_at on a fresh database, and does nothing on an existing one.
2. SchemaMigrator (@DependsOnDatabaseInitialization) runs PRAGMA table_info(short_links).
3. If expires_at is missing, which is the case for a database created before this change, it runs ALTER TABLE short_links ADD COLUMN expires_at TEXT. Existing rows get NULL and never expire.
4. If expires_at is present, nothing happens, so the second and later restarts succeed.
5. ShortLinkRepository, which depends on SchemaMigrator, becomes available and the web server begins serving.

### Create short link (POST /api/links)

1. Jackson binds the body to CreateLinkRequest. url is a String and expiresInDays is a raw JsonNode, so no coercion happens. Unknown properties such as alias are ignored. A malformed body returns 400 and a non-JSON content type returns 415.
2. LinkService validates the URL. If it is invalid, InvalidUrlException produces 400 with the URL detail and nothing is persisted.
3. ExpiryPolicy validates expiresInDays. A null or NullNode value means no expiry. An integral node with a BigInteger value in 1..3650 is accepted. Anything else (0, negative, 3651, 99999999999999999999, 1.5, 7.0, 7e0, "7", or a boolean, object or array) throws InvalidExpiryException, giving 400 with the expiry detail. Nothing is persisted.
4. createdAt = clock.instant(). expiresAt = createdAt + days x 24h, or null.
5. A random 7-character base62 code is generated and repository.insert(code, url, createdAt, expiresAt) is called. On a code collision the service retries with a new code and the same createdAt and expiresAt.
6. The controller returns 201 with Location /api/links/{code} and a body of exactly shortCode, longUrl and createdAt.

### Redirect (GET /{code})

1. RedirectController calls LinkService.resolveAndCount(code) in a transaction, with now = clock.instant().
2. The repository runs UPDATE short_links SET click_count = click_count + 1, last_clicked_at = :now WHERE short_code = :code AND (expires_at IS NULL OR expires_at > :now).
3. If one row is updated, the service reads long_url and the controller returns 302 with Location set to the long URL and Cache-Control: no-store.
4. If no row is updated and existsByCode(code) is true, LinkExpiredException is thrown. The handler returns 410 problem+json with title 'Gone', detail 'short link has expired' and Cache-Control: no-store, and no Location header. Clicks are unchanged.
5. If no row is updated and the code does not exist, LinkNotFoundException is thrown and the handler returns 404 problem+json.

### Link details (GET /api/links/{code})

1. LinkController calls the repository's findByCode(code).
2. If the link is found, the controller returns 200 with exactly shortCode, longUrl and createdAt, whether or not the link has expired. expiresAt is not exposed.
3. If the link is not found, the response is 404 problem+json.

### Link analytics (GET /api/links/{code}/analytics)

1. LinkController loads the record by code.
2. If the link is found, the controller returns 200 with exactly shortCode, clickCount and lastClickedAt (null if never clicked), whether or not the link has expired.
3. If the link is not found, the response is 404 problem+json.

## Error model

All errors are returned as application/problem+json with the fields type, title, status and detail. Stack traces are never included. Mappings by ProblemExceptionHandler:
- 400 Bad Request, malformed or unreadable JSON body (HttpMessageNotReadableException): existing behaviour.
- 400 Bad Request, InvalidUrlException: existing detail 'url must be an absolute http or https URL'.
- 400 Bad Request, InvalidExpiryException (new): detail 'expiresInDays must be a whole-number JSON integer from 1 to 3650'. It covers 0, negative values, values above 3650 including huge integers (compared as BigInteger, so no overflow and no 500), fractional or exponent literals (1.5, 7.0, 7e0), strings ("7"), booleans, objects and arrays. Validation runs before any insert, so nothing is persisted.
- 415 Unsupported Media Type, non-JSON content type: existing behaviour.
- 404 Not Found, LinkNotFoundException: unknown code on GET /{code}, GET /api/links/{code} or GET /api/links/{code}/analytics. An unknown code on GET /{code} is never reported as 410.
- 410 Gone, LinkExpiredException (new): only on GET /{code} for an existing link where now >= expires_at. Title 'Gone', detail 'short link has expired', header Cache-Control: no-store, no Location header. The click count and last-click time are not changed, because the conditional UPDATE matched no row.
- 500 Internal Server Error, catch-all for unexpected exceptions: existing behaviour, with a generic detail.

## Traceability

| Requirement | Endpoints | Modules | Catalog |
|---|---|---|---|
| FR-1 | POST /api/links | api.CreateLinkRequest, api.LinkController, service.LinkService, docs (docs/API.md, README.md) | — |
| FR-2 | POST /api/links | service.ExpiryPolicy, service.LinkService, api.LinkController | — |
| FR-3 | POST /api/links | api.CreateLinkRequest, service.ExpiryPolicy, service.InvalidExpiryException / service.LinkExpiredException, api.ProblemExceptionHandler | — |
| FR-4 | POST /api/links | service.LinkService, persistence.ShortLinkRepository | — |
| FR-5 | GET /{code} | api.RedirectController, service.LinkService, service.InvalidExpiryException / service.LinkExpiredException, api.ProblemExceptionHandler, config.ClockConfig | — |
| FR-6 | POST /api/links, GET /{code} | service.ExpiryPolicy, service.LinkService, persistence.ShortLinkRepository, persistence.ShortLinkRecord, resources/schema.sql, config.ClockConfig | — |
| FR-7 | POST /api/links, GET /{code} | persistence.SchemaMigrator, resources/schema.sql, persistence.ShortLinkRepository, persistence.ShortLinkRecord, service.LinkService | — |
| FR-8 | POST /api/links | api.CreateLinkRequest, service.ExpiryPolicy, service.LinkService | — |
| FR-9 | POST /api/links | api.CreateLinkRequest, service.ExpiryPolicy, api.ProblemExceptionHandler | — |
| FR-10 | GET /{code}, GET /api/links/{code}/analytics | service.LinkService, persistence.ShortLinkRepository, config.ClockConfig | — |
| FR-11 | GET /{code} | api.RedirectController, service.LinkService, persistence.ShortLinkRepository | — |
| FR-12 | GET /{code} | service.LinkService, persistence.ShortLinkRepository, api.ProblemExceptionHandler, api.RedirectController | — |
| FR-13 | GET /api/links/{code}, GET /api/links/{code}/analytics | api.LinkController, api.ShortLinkResponse / api.LinkAnalyticsResponse | — |
| FR-14 | POST /api/links, GET /api/links/{code} | api.CreateLinkRequest, api.LinkController, api.ShortLinkResponse / api.LinkAnalyticsResponse | — |
| FR-15 | GET /{code} | api.ProblemExceptionHandler, service.InvalidExpiryException / service.LinkExpiredException | — |

## Dependencies

- org.springframework.boot:spring-boot-starter-parent
- org.springframework.boot:spring-boot-starter-web
- org.springframework.boot:spring-boot-starter-jdbc
- org.xerial:sqlite-jdbc
- org.springframework.boot:spring-boot-starter-test
- org.springframework.boot:spring-boot-maven-plugin
