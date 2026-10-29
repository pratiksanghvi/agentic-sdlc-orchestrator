# URL Shortener API

A public URL shortener service (API version 1.1.0). It creates short links for long URLs, redirects short codes to the long URL, and reports link details and click analytics. Short links can optionally expire after a whole number of days; an expired link returns `410 Gone` on redirect.

## Features

- Create a short link with `POST /api/links`, optionally with `expiresInDays` (integer 1 to 3650).
- Redirect with `GET /{code}` (302, `Cache-Control: no-store`, click counted).
- Expired links return 410 with `application/problem+json` and no `Location` header; the click is not counted.
- Links created without `expiresInDays` (or with `null`) never expire. This includes all links that existed before this change.
- Get link details with `GET /api/links/{code}` and analytics with `GET /api/links/{code}/analytics`; both return 200 even for expired links.
- No `expiresAt` field is exposed in any response.

The field name `expiresInDays` rests on assumption A-1 (open question Q-1, pending reviewer confirmation).

## Expiry rules

- Expiry instant = creation time + N x 24 hours (UTC). The link is expired when the current time is >= the expiry instant.
- Accepted: whole-number JSON integer from 1 to 3650 inclusive.
- Rejected with 400: zero, negative, fractional, string (e.g. `"7"`), out of range, and numbers written with a fraction or exponent (`7.0`, `7e0`). Nothing is persisted on rejection.
- Unknown request properties (e.g. `alias`) are ignored.

## Prerequisites

- Java 21
- Maven

Stack: java21-springboot3-maven.

## Build and test

```
mvn -q -B verify
```

## Run

```
sh -c java -jar target/*.jar
```

## Configuration

| Variable | Description |
|---|---|
| `PORT` | HTTP port (required) |
| `DB_PATH` | SQLite database file path (default `app.db`) |

## Readiness

On startup the service prints:

```
SERVICE_READY port=<port>
```

## Non-functional requirements

Not specified.

## API documentation

See [docs/API.md](docs/API.md).
