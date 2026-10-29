# Design

Stack: `java21-springboot3-maven`

## Modules

- **com.example.shortener.ShortenerApplication** — Spring Boot entry point. Configures the SQLite DataSource (jdbc:sqlite file URL, Hikari maximum-pool-size=1 to serialize writes) and runs schema.sql on startup via spring.sql.init.mode=always. Has no authentication or security filter, so every operation is public. (FR-1, FR-2, FR-4, FR-7, FR-15)
- **com.example.shortener.api.LinkController** — REST controller for /api/links. POST /api/links accepts a CreateLinkRequest, delegates to LinkService and returns 201 with a ShortLink body and a Location header. GET /api/links/{code} returns the details (shortCode, longUrl, createdAt). GET /api/links/{code}/analytics returns clickCount and lastClickedAt, with null when the link has never been clicked. Any client-supplied alias field is ignored. (FR-1, FR-4, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13, FR-15)
- **com.example.shortener.api.RedirectController** — Handles GET /{code}. It calls LinkService.resolveAndCount and returns 302 Found with a Location header set to the original long URL and Cache-Control: no-store. It returns 404 when the code is unknown. (FR-2, FR-3, FR-5, FR-6, FR-12, FR-14, FR-15)
- **com.example.shortener.service.LinkService** — Business logic. create: validates the URL, generates a short code, stamps createdAt and inserts a new row on every call with no de-duplication by URL. If the short code collides with an existing one, it retries up to 5 times. getDetails and getAnalytics: look up a link by code and throw LinkNotFoundException if it is absent. resolveAndCount: atomically increments click_count by 1, sets last_clicked_at to the current Instant and returns the long URL. It throws LinkNotFoundException without touching any row when the code is unknown. Every successful redirect counts, with no filtering. (FR-1, FR-2, FR-5, FR-6, FR-7, FR-9, FR-10, FR-11, FR-12, FR-13, FR-14)
- **com.example.shortener.service.UrlValidator** — Accepts a value only when it parses as an absolute java.net.URI with scheme http or https (case-insensitive) and a non-empty host. Null, blank, relative, malformed and other-scheme values raise InvalidUrlException. (FR-10)
- **com.example.shortener.service.ShortCodeGenerator** — Generates service-owned short codes: 7 random base62 characters [A-Za-z0-9] produced with SecureRandom. (FR-1, FR-8, FR-9)
- **com.example.shortener.persistence.ShortLinkRepository** — JdbcTemplate data access to the short_links table. Operations: insert (which surfaces DuplicateKeyException on a short_code collision), findByCode, and incrementClick. incrementClick runs UPDATE short_links SET click_count = click_count + 1, last_clicked_at = ? WHERE short_code = ? and returns the affected row count; the long URL is then read in the same transaction. Timestamps are stored as ISO-8601 UTC text with microsecond precision. (FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-9, FR-11, FR-12, FR-13)
- **com.example.shortener.api.ProblemExceptionHandler** — @RestControllerAdvice that maps exceptions to RFC 7807 application/problem+json bodies containing type, title, status and detail. InvalidUrlException and unreadable or missing bodies map to 400. LinkNotFoundException maps to 404. An unsupported Content-Type maps to 415. Any other exception maps to 500. (FR-10, FR-12)

## Non-functional implementation (from catalog)

- none

## Primary flows

### Create short link (POST /api/links)

1. Client sends POST /api/links with a JSON body {"url": "..."} and no credentials (FR-15).
2. Spring deserializes the body. A missing or malformed body or a wrong Content-Type is handled by ProblemExceptionHandler and returns 400 or 415 as problem+json.
3. UrlValidator checks that the value is an absolute URI with scheme http/https and a host. If not, it throws InvalidUrlException, the handler returns 400 problem+json, and nothing is persisted (FR-10).
4. ShortCodeGenerator produces a random 7-character base62 code. Any client-supplied alias is ignored (FR-8).
5. LinkService sets createdAt = Instant.now() (UTC) and ShortLinkRepository inserts a new row with click_count=0 and last_clicked_at=NULL. There is no lookup by long_url, so each call creates an independent link (FR-9).
6. On a short_code unique violation (DuplicateKeyException), LinkService regenerates the code and retries, up to 5 attempts. If all attempts fail, the request returns 500.
7. The service responds 201 with Location: /api/links/{code} and the body {shortCode, longUrl, createdAt} (FR-1, FR-11).

### Redirect and count click (GET /{code})

1. Client sends GET /{code} with no credentials (FR-15).
2. RedirectController calls LinkService.resolveAndCount(code).
3. Inside one transaction, ShortLinkRepository runs UPDATE short_links SET click_count = click_count + 1, last_clicked_at = :now WHERE short_code = :code (FR-5, FR-6, FR-14).
4. If 0 rows are affected, LinkNotFoundException is thrown and the handler returns 404 problem+json. No counter is changed (FR-12).
5. Otherwise the repository SELECTs long_url for the code and the transaction commits.
6. The service responds 302 Found with Location: <long_url>, Cache-Control: no-store and an empty body (FR-2, FR-3).

### Get link details (GET /api/links/{code})

1. Client sends GET /api/links/{code} with no credentials (FR-15).
2. LinkService.getDetails calls ShortLinkRepository.findByCode. If no row exists, the handler returns 404 problem+json (FR-12).
3. The service responds 200 with {shortCode, longUrl, createdAt} (FR-4, FR-11).

### Get link analytics (GET /api/links/{code}/analytics)

1. Client sends GET /api/links/{code}/analytics with no credentials (FR-15).
2. LinkService.getAnalytics calls ShortLinkRepository.findByCode. If no row exists, the handler returns 404 problem+json (FR-12).
3. The service responds 200 with {shortCode, clickCount, lastClickedAt}. lastClickedAt is null when last_clicked_at is NULL, so a never-clicked link reports clickCount 0 and lastClickedAt null (FR-7, FR-13).

## Error model

All error responses use Content-Type application/problem+json (RFC 7807) with the body {"type": "about:blank", "title": <HTTP reason phrase>, "status": <code>, "detail": <human-readable explanation>}. ProblemExceptionHandler (@RestControllerAdvice) maps exceptions to statuses as follows:
(1) InvalidUrlException becomes 400 Bad Request, with a detail such as "url must be an absolute http or https URL" (FR-10).
(2) HttpMessageNotReadableException (malformed or missing JSON body) and a missing or blank url field also become 400 Bad Request (FR-10).
(3) HttpMediaTypeNotSupportedException becomes 415 Unsupported Media Type.
(4) LinkNotFoundException becomes 404 Not Found, with the detail "No short link exists for code '<code>'", on the redirect, details and analytics endpoints (FR-12).
(5) Any other uncaught exception, including exhausted short-code collision retries or a database failure, becomes 500 Internal Server Error with a generic detail; stack traces are logged, never returned.
No error path creates a link or modifies click counters: create validation runs before insert, and the redirect returns 404 when the UPDATE affects 0 rows. The service never returns 401 or 403 because there is no authentication (FR-15).

## Traceability

| Requirement | Endpoints | Modules | Catalog |
|---|---|---|---|
| FR-1 | POST /api/links | com.example.shortener.api.LinkController, com.example.shortener.service.LinkService, com.example.shortener.service.ShortCodeGenerator, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-2 | GET /{code} | com.example.shortener.api.RedirectController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-3 | GET /{code} | com.example.shortener.api.RedirectController | — |
| FR-4 | GET /api/links/{code} | com.example.shortener.api.LinkController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-5 | GET /{code}, GET /api/links/{code}/analytics | com.example.shortener.api.RedirectController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-6 | GET /{code}, GET /api/links/{code}/analytics | com.example.shortener.api.RedirectController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-7 | GET /api/links/{code}/analytics | com.example.shortener.api.LinkController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-8 | POST /api/links | com.example.shortener.api.LinkController, com.example.shortener.service.ShortCodeGenerator | — |
| FR-9 | POST /api/links | com.example.shortener.service.LinkService, com.example.shortener.service.ShortCodeGenerator, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-10 | POST /api/links | com.example.shortener.service.UrlValidator, com.example.shortener.service.LinkService, com.example.shortener.api.ProblemExceptionHandler | — |
| FR-11 | GET /api/links/{code}, POST /api/links | com.example.shortener.api.LinkController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-12 | GET /{code}, GET /api/links/{code}, GET /api/links/{code}/analytics | com.example.shortener.service.LinkService, com.example.shortener.api.ProblemExceptionHandler, com.example.shortener.api.RedirectController, com.example.shortener.api.LinkController | — |
| FR-13 | GET /api/links/{code}/analytics | com.example.shortener.api.LinkController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-14 | GET /{code} | com.example.shortener.api.RedirectController, com.example.shortener.service.LinkService, com.example.shortener.persistence.ShortLinkRepository | — |
| FR-15 | POST /api/links, GET /{code}, GET /api/links/{code}, GET /api/links/{code}/analytics | com.example.shortener.ShortenerApplication, com.example.shortener.api.LinkController, com.example.shortener.api.RedirectController | — |

## Dependencies

- org.springframework.boot:spring-boot-starter-parent
- org.springframework.boot:spring-boot-starter-web
- org.springframework.boot:spring-boot-starter-jdbc
- org.xerial:sqlite-jdbc
- org.springframework.boot:spring-boot-starter-test
- org.springframework.boot:spring-boot-maven-plugin
