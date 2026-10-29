# API Reference

URL Shortener API, version 1.1.0. Errors use `application/problem+json` with fields `type`, `title`, `status`, `detail`.

## POST /api/links

Create a new short link, optionally with an expiry in days.

**Request** (`application/json`):

- `url` (string, required): absolute http or https URL.
- `expiresInDays` (integer, optional, nullable): whole-number JSON integer 1 to 3650. Absent or null means the link never expires. Strings, fractions or exponents (`7.0`, `7e0`), zero, negative and out-of-range values are rejected with 400.
- Unknown properties (e.g. `alias`) are ignored.

**Responses**:

- `201` Short link created. `Location` header is `/api/links/{code}`. Body: `shortCode`, `longUrl`, `createdAt`. Same with or without expiry.
- `400` Invalid or malformed body, invalid URL, or invalid `expiresInDays` (the detail describes the expiry problem). Nothing is persisted.
- `415` Content type is not `application/json`.
- `500` Unexpected error.

**Example**:

```
curl -i -X POST http://localhost:$PORT/api/links -H 'Content-Type: application/json' -d '{"url":"https://example.com/page","expiresInDays":7}'
```

## GET /api/links/{code}

Get link details. Returns 200 even if the link has expired.

**Request**: path parameter `code` (7-character base62 short code).

**Responses**:

- `200` Body: `shortCode`, `longUrl`, `createdAt` (date-time).
- `404` Unknown short code.
- `500` Unexpected error.

**Example**:

```
curl -i http://localhost:$PORT/api/links/abc1234
```

## GET /api/links/{code}/analytics

Get click analytics. Returns 200 even if the link has expired.

**Request**: path parameter `code`.

**Responses**:

- `200` Body: `shortCode`, `clickCount` (int64), `lastClickedAt` (date-time, null if never clicked).
- `404` Unknown short code.
- `500` Unexpected error.

**Example**:

```
curl -i http://localhost:$PORT/api/links/abc1234/analytics
```

## GET /{code}

Redirect to the long URL and count the click. Returns 410 if the link has expired (click not counted).

**Request**: path parameter `code`.

**Responses**:

- `302` Redirect. `Location` is the long URL; `Cache-Control: no-store`. `clickCount` increases by one and `lastClickedAt` is updated.
- `404` Unknown short code (unknown codes never return 410).
- `410` The link exists but has expired. Problem body with title `Gone`, status 410 and a generic detail such as `short link has expired`; `Cache-Control: no-store`; no `Location` header. `clickCount` and `lastClickedAt` are unchanged.
- `500` Unexpected error.

**Example**:

```
curl -i http://localhost:$PORT/abc1234
```
