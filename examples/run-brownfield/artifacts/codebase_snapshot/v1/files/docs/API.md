# API Reference

All operations are public (no authentication). Error responses use `application/problem+json` with fields `type`, `title`, `status`, `detail`.

Examples assume the service is listening on `localhost:8080` (i.e. `PORT=8080`).

## POST /api/links

Create a new short link for an absolute http/https URL. A new independent link is created on every call.

**Request**: `Content-Type: application/json`, body required.

| Field | Type | Description |
|-------|------|-------------|
| url | string (required) | Absolute URL with scheme http or https |

**Responses**

- `201` Short link created. Header `Location` is the path of the created link's details resource (`/api/links/{code}`). Body: ShortLink (`shortCode`, `longUrl`, `createdAt`).
- `400` Invalid request (missing/malformed body or URL that is not absolute http/https). No short link is created.
- `415` Request Content-Type is not application/json.
- `500` Unexpected server error.

**Example**

```
curl -i -X POST http://localhost:8080/api/links \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com/some/long/path"}'
```

## GET /api/links/{code}

Get a short link's details.

**Request**: path parameter `code` (string, required) - the service-generated short code.

**Responses**

- `200` Body: ShortLink with `shortCode`, `longUrl` (uri) and `createdAt` (date-time).
- `404` No short link exists for the given short code.
- `500` Unexpected server error.

**Example**

```
curl -i http://localhost:8080/api/links/aB3xK9q
```

## GET /api/links/{code}/analytics

Get a short link's click analytics.

**Request**: path parameter `code` (string, required).

**Responses**

- `200` Body: `shortCode` (string), `clickCount` (int64, minimum 0), `lastClickedAt` (date-time, nullable; null if never clicked).
- `404` No short link exists for the given short code.
- `500` Unexpected server error.

**Example**

```
curl -i http://localhost:8080/api/links/aB3xK9q/analytics
```

## GET /{code}

Redirect to the original URL and count the click.

**Request**: path parameter `code` (string, required).

**Responses**

- `302` Temporary redirect. Header `Location` is the original long URL; header `Cache-Control: no-store`. The click is counted.
- `404` No short link exists for the given short code.
- `500` Unexpected server error.

**Example**

```
curl -i http://localhost:8080/aB3xK9q
```
