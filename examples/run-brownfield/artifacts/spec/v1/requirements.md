# Optional link expiry for short links (410 Gone on expired redirects)

## Functional requirements

- **FR-1** [MVP] POST /api/links accepts an optional expiry field named expiresInDays in the JSON request body, giving the number of days until the link expires. The field name rests on assumption A-1 (open question Q-1, pending reviewer confirmation). _(source: assumption)_
  - AC-1.1: Given The service is running, when A client sends POST /api/links with body {"url":"https://example.com/a","expiresInDays":7}, then The response status is 201 and a Location header /api/links/{code} is present
  - AC-1.2: Given A link was created with expiresInDays=1, when The test clock is advanced by 24 hours and the client sends GET /{code}, then The response status is 410, which shows the expiresInDays field took effect
- **FR-2** [MVP] An expiresInDays value that is a whole-number JSON integer from 1 to 3650 inclusive is accepted. The link is created with 201, and the Location header and body are the same as for a create request without expiry. _(source: clarification)_
  - AC-2.1: Given The service is running, when A client sends POST /api/links with expiresInDays=1, and separately with expiresInDays=3650, then Both responses are 201 with a body containing exactly shortCode, longUrl and createdAt
  - AC-2.2: Given A link was created with expiresInDays=3650, when The client immediately sends GET /{code}, then The response status is 302 with Location equal to the submitted URL
- **FR-3** [MVP] An expiresInDays value that is zero, negative, fractional, a string (e.g. "7") or outside 1..3650 is rejected with 400 application/problem+json. The detail describes the expiry problem and does not use the URL validation message. _(source: clarification)_
  - AC-3.1: Given The service is running, when A client sends POST /api/links with a valid url and expiresInDays set to each of 0, -1, 1.5, "7", 3651, then Each response has status 400 and Content-Type application/problem+json, and its detail mentions the expiry field rather than the URL
  - AC-3.2: Given The service is running, when A client sends POST /api/links with expiresInDays=99999999999999999999, then The response status is 400 (not 500) with Content-Type application/problem+json and no stack trace in the body
- **FR-4** [MVP] When a create request is rejected because of its expiry value, no link is persisted. _(source: clarification)_
  - AC-4.1: Given The service is running, when A client sends POST /api/links with expiresInDays=0 and receives 400, then The response has no Location header, and no new short code is retrievable through GET /api/links/{code} for any code produced by the request
  - AC-4.2: Given An invalid-expiry create request was rejected with 400, when A subsequent valid create request is sent, then It returns 201 normally, and only the valid link exists (its details return 200)
- **FR-5** [MVP] GET /{code} for an existing link whose expiry has passed returns 410 instead of a 302 redirect. The response is application/problem+json with type, title 'Gone', status 410 and detail, and it has no Location header. _(source: explicit)_
  - AC-5.1: Given A link was created with expiresInDays=1 and the test clock was advanced by 25 hours, when The client sends GET /{code}, then The response status is 410, Content-Type is application/problem+json, the body contains type, title 'Gone', status 410 and detail, and there is no Location header
- **FR-6** [MVP] A link's expiry instant is its creation time plus N × 24 hours (UTC), where N is expiresInDays. The link is expired when the current time is greater than or equal to the expiry instant (assumption A-4). _(source: assumption)_
  - AC-6.1: Given A link was created with expiresInDays=2, when The test clock is set to 1 millisecond before creation + 48 hours and GET /{code} is sent, then The response status is 302
  - AC-6.2: Given A link was created with expiresInDays=2, when The test clock is set to exactly creation + 48 hours and GET /{code} is sent, then The response status is 410
- **FR-7** [MVP] A link created without expiresInDays never expires and keeps redirecting with 302 indefinitely. This includes every link that existed before this change. _(source: explicit)_
  - AC-7.1: Given A link was created without the expiresInDays field, when The test clock is advanced by 3651 days and GET /{code} is sent, then The response status is 302 with Location equal to the long URL
  - AC-7.2: Given A link existed in the data store before the service was upgraded to this version, when The upgraded service starts (including a second restart) and GET /{code} is sent for that link, then The service starts successfully each time, and the response status is 302 with Location equal to the link's long URL
- **FR-8** [MVP] An explicit JSON null for expiresInDays is treated the same as an absent field. The request returns 201 and the link never expires (assumption A-2). _(source: assumption)_
  - AC-8.1: Given The service is running, when A client sends POST /api/links with body {"url":"https://example.com/a","expiresInDays":null}, then The response status is 201
  - AC-8.2: Given A link was created with expiresInDays explicitly null, when The test clock is advanced by 3651 days and GET /{code} is sent, then The response status is 302
- **FR-9** [MVP] A JSON number with an integral value but written with a fraction or exponent (e.g. 7.0 or 7e0) is not a whole-number JSON integer. It is rejected with 400 application/problem+json, and nothing is persisted (assumption A-3). _(source: assumption)_
  - AC-9.1: Given The service is running, when A client sends POST /api/links with a valid url and expiresInDays set to 7.0, and separately to 7e0, then Each response has status 400 with Content-Type application/problem+json and no Location header
- **FR-10** [MVP] A 410 response for an expired link does not change the link's clickCount or lastClickedAt. Only successful 302 redirects are counted. _(source: clarification)_
  - AC-10.1: Given A link was created with expiresInDays=1, redirected once (clickCount=1), and the test clock was then advanced by 25 hours, when The client sends GET /{code} three times, each returning 410, and then GET /api/links/{code}/analytics, then The analytics response shows clickCount=1 and lastClickedAt equal to the value recorded after the single successful redirect
  - AC-10.2: Given A link was created with expiresInDays=1, never redirected, and the test clock was advanced by 25 hours, when The client sends GET /{code}, which returns 410, and then GET /api/links/{code}/analytics, then The analytics response shows clickCount=0 and lastClickedAt=null
- **FR-11** [MVP] For a link with an expiry that has not yet passed, GET /{code} returns 302 with Location set to the long URL and Cache-Control: no-store. It also increments clickCount by exactly one and updates lastClickedAt. _(source: clarification)_
  - AC-11.1: Given A link was created with expiresInDays=5 and has not expired, when The client sends GET /{code}, then The response status is 302, Location equals the long URL, and Cache-Control is no-store
  - AC-11.2: Given A link was created with expiresInDays=5 and has clickCount=0, when The client sends GET /{code} twice and then GET /api/links/{code}/analytics, then The analytics response shows clickCount=2 and a non-null lastClickedAt
- **FR-12** [MVP] GET /{code} for an unknown code still returns 404, not 410. 410 is returned only for existing links that have expired. _(source: explicit)_
  - AC-12.1: Given No link exists with code 'zzzzzzz', when The client sends GET /zzzzzzz, then The response status is 404 with Content-Type application/problem+json
- **FR-13** [MVP] For an expired link, GET /api/links/{code} and GET /api/links/{code}/analytics keep returning 200 with their current fields. Only the redirect endpoint returns 410. _(source: clarification)_
  - AC-13.1: Given A link was created with expiresInDays=1 and the test clock was advanced by 25 hours, when The client sends GET /api/links/{code}, then The response status is 200 with a body containing exactly shortCode, longUrl and createdAt
  - AC-13.2: Given A link was created with expiresInDays=1 and the test clock was advanced by 25 hours, when The client sends GET /api/links/{code}/analytics, then The response status is 200 with a body containing exactly shortCode, clickCount and lastClickedAt
- **FR-14** [MVP] No new response field (such as expiresAt) is added. Create and details responses keep exactly their current fields, whether or not an expiry was given. Unknown request properties other than expiresInDays (e.g. "alias") are still ignored, and the request still returns 201. _(source: clarification)_
  - AC-14.1: Given The service is running, when A client sends POST /api/links with {"url":"https://example.com/a","expiresInDays":7}, then The response is 201 with a body containing exactly the fields shortCode, longUrl and createdAt, and no expiresAt field
  - AC-14.2: Given The service is running, when A client sends POST /api/links with {"url":"https://example.com/a"}, and separately with {"url":"https://example.com/a","alias":"mine"}, then Both responses are 201 with Location /api/links/{code} and a body containing exactly shortCode, longUrl and createdAt
- **FR-15** [MVP] The 410 response carries a generic detail such as 'short link has expired' and the header Cache-Control: no-store (assumption A-5). _(source: assumption)_
  - AC-15.1: Given A link was created with expiresInDays=1 and the test clock was advanced by 25 hours, when The client sends GET /{code}, then The 410 response includes the header Cache-Control: no-store, and its detail states that the short link has expired

## Non-functional requirements

- none requested

## Not supported in MVP

- none

## Assumptions

- **A-1** The optional request field is named expiresInDays. This is the recommended default for BLOCKING question Q-1, which the clarifications did not answer. The reviewer must confirm or change the name before approval.
- **A-2** An explicit JSON null for expiresInDays is treated as absent. The request returns 201 and the link never expires.
- **A-3** Only JSON integer literals count as whole-number JSON integers. Integral values written with a fraction or exponent (7.0, 7e0) are rejected with 400.
- **A-4** The expiry instant is creation time + N × 24 hours (UTC). A link is expired when the current time is greater than or equal to the expiry instant.
- **A-5** The 410 problem+json response uses title 'Gone', a generic detail such as 'short link has expired', and Cache-Control: no-store, as on the redirect.
- **A-6** Acceptance tests that need time to pass can control the service's notion of current time, for example with an adjustable test clock.

## Constraints

- none

## Out of scope

- Adding any new response field (e.g. expiresAt) to the create or details responses (per C-4)
- Returning 410 from GET /api/links/{code} or GET /api/links/{code}/analytics for expired links (per C-3)
- Counting clicks or updating lastClickedAt on 410 responses (per C-2)
- Expiry units other than whole days, and values outside 1..3650 (per C-1)
- Changing or removing a link's expiry after creation (not requested)
- Deleting or purging expired links (not requested)
- Any non-functional requirements such as rate limiting, additional security controls or metrics (none requested)
- Existing behavior of the service that this change does not alter

## Clarifications

- Which expiry values are valid, and what happens with invalid ones (zero, negative, fractional, numeric strings like "7", or very large numbers)? → **Accept only whole-number JSON integers from 1 to 3650 inclusive. Reject zero, negative, fractional, string and out-of-range values with 400 application/problem+json whose detail describes the expiry problem. Persist nothing on rejection.**
- Should a GET /{code} that returns 410 for an expired link increase the click count or update the last-click time? → **No. Only successful 302 redirects are counted. A 410 response leaves clickCount and lastClickedAt unchanged.**
- What should GET /api/links/{code} and GET /api/links/{code}/analytics return for an expired link? → **Keep returning 200 with the current fields. Only the redirect endpoint returns 410.**
- Should the link's computed expiry timestamp (e.g. expiresAt) be exposed in the create (POST /api/links) and details (GET /api/links/{code}) responses? If so, how should it appear for links that never expire? → **Do not add any new response field. Keep create and details responses exactly as today, per C-3's 'current fields'.**
