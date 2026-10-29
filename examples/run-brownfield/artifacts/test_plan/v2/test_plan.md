# Acceptance test plan

| Case | Covers | Kind | Phase | Title |
|---|---|---|---|---|
| TC-1 | AC-1.1 | positive | main | Create link with expiresInDays=7 returns 201 and Location /api/links/{code} |
| TC-2 | AC-1.2 | edge | main | Link created with expiresInDays=1 is accepted and redirects before expiry (pre-advance portion; the contract exposes no test-clock control) |
| TC-3 | AC-2.1 | edge | main | Create with minimum expiresInDays=1 returns 201 with exactly shortCode, longUrl, createdAt |
| TC-4 | AC-2.1 | edge | main | Create with maximum expiresInDays=3650 returns 201 with exactly shortCode, longUrl, createdAt |
| TC-5 | AC-2.2 | positive | main | Link with expiresInDays=3650 redirects immediately with 302 to submitted URL |
| TC-6 | AC-3.1 | edge | main | expiresInDays=0 rejected with 400 problem+json mentioning expiry |
| TC-7 | AC-3.1 | negative | main | expiresInDays=-1 rejected with 400 problem+json mentioning expiry |
| TC-8 | AC-3.1 | negative | main | expiresInDays=1.5 rejected with 400 problem+json mentioning expiry |
| TC-9 | AC-3.1 | negative | main | expiresInDays="7" (string) rejected with 400 problem+json mentioning expiry |
| TC-10 | AC-3.1 | edge | main | expiresInDays=3651 rejected with 400 problem+json mentioning expiry |
| TC-11 | AC-3.2 | edge | main | Huge expiresInDays rejected with 400 (not 500) and no stack trace |
| TC-12 | AC-4.1 | negative | main | Rejected expiresInDays=0 produces no Location header and no short code |
| TC-13 | AC-4.2 | positive | main | Valid create after rejected invalid-expiry create succeeds and the valid link exists |
| TC-14 | AC-5.1 | edge | main | Link with expiresInDays=1 is live before expiry and is not answered with 410 (pre-advance portion; the contract exposes no test-clock control) |
| TC-15 | AC-6.1 | edge | main | Link with expiresInDays=2 redirects with 302 before the 48h boundary |
| TC-16 | AC-6.2 | edge | main | Link with expiresInDays=2 is not yet gone before creation + 48h (pre-boundary portion; the contract exposes no test-clock control) |
| TC-17 | AC-7.1 | positive | main | Link created without expiresInDays redirects with 302 to long URL |
| TC-18 | AC-7.2 | edge | main | Upgraded service is running and a non-expiring link redirects with 302 to its long URL (API-observable portion; data-store upgrade and restarts are performed outside the contract) |
| TC-19 | AC-8.1 | positive | main | expiresInDays explicitly null is accepted with 201 |
| TC-20 | AC-8.2 | positive | main | Link created with expiresInDays=null redirects with 302 |
| TC-21 | AC-9.1 | negative | main | expiresInDays=7.0 rejected with 400 problem+json and no Location |
| TC-22 | AC-9.1 | negative | main | expiresInDays=7e0 rejected with 400 problem+json and no Location |
| TC-23 | AC-10.1 | edge | main | Single successful redirect on a 1-day link records clickCount=1 and a stable lastClickedAt (pre-advance portion; the contract exposes no test-clock control) |
| TC-24 | AC-10.2 | edge | main | Never-redirected 1-day link shows clickCount=0 and lastClickedAt=null (pre-advance portion; the contract exposes no test-clock control) |
| TC-25 | AC-11.1 | positive | main | Unexpired 5-day link redirects 302 with Location and Cache-Control no-store |
| TC-26 | AC-11.2 | positive | main | Two redirects on an unexpired 5-day link yield clickCount=2 and non-null lastClickedAt |
| TC-27 | AC-12.1 | negative | main | Unknown code zzzzzzz returns 404 problem+json |
| TC-28 | AC-13.1 | positive | main | Details of a 1-day link return 200 with exactly shortCode, longUrl, createdAt |
| TC-29 | AC-13.2 | positive | main | Analytics of a 1-day link return 200 with exactly shortCode, clickCount, lastClickedAt |
| TC-30 | AC-14.1 | positive | main | Create with expiresInDays=7 returns exactly shortCode, longUrl, createdAt and no expiresAt |
| TC-31 | AC-14.2 | positive | main | Create without expiresInDays returns 201 with Location and exactly the three fields |
| TC-32 | AC-14.2 | edge | main | Unknown alias property is ignored: 201 with Location and exactly the three fields |
| TC-33 | AC-15.1 | edge | main | Redirect responses for a 1-day link carry Cache-Control: no-store (pre-advance portion; the contract exposes no test-clock control) |

## TC-1 — Create link with expiresInDays=7 returns 201 and Location /api/links/{code}

1. Create link with 7-day expiry: `POST /api/links` expect 201
2. Location target resolves to link details: `GET /api/links/${code}` expect 200

## TC-2 — Link created with expiresInDays=1 is accepted and redirects before expiry (pre-advance portion; the contract exposes no test-clock control)

1. Create link with 1-day expiry: `POST /api/links` expect 201
2. Before 24h has elapsed the link is not gone: `GET /${code}` expect 302

## TC-3 — Create with minimum expiresInDays=1 returns 201 with exactly shortCode, longUrl, createdAt

1. Create link with expiresInDays=1: `POST /api/links` expect 201

## TC-4 — Create with maximum expiresInDays=3650 returns 201 with exactly shortCode, longUrl, createdAt

1. Create link with expiresInDays=3650: `POST /api/links` expect 201

## TC-5 — Link with expiresInDays=3650 redirects immediately with 302 to submitted URL

1. Create link with expiresInDays=3650: `POST /api/links` expect 201
2. Redirect: `GET /${code}` expect 302

## TC-6 — expiresInDays=0 rejected with 400 problem+json mentioning expiry

1. Create with expiresInDays=0: `POST /api/links` expect 400

## TC-7 — expiresInDays=-1 rejected with 400 problem+json mentioning expiry

1. Create with expiresInDays=-1: `POST /api/links` expect 400

## TC-8 — expiresInDays=1.5 rejected with 400 problem+json mentioning expiry

1. Create with expiresInDays=1.5: `POST /api/links` expect 400

## TC-9 — expiresInDays="7" (string) rejected with 400 problem+json mentioning expiry

1. Create with string expiresInDays: `POST /api/links` expect 400

## TC-10 — expiresInDays=3651 rejected with 400 problem+json mentioning expiry

1. Create with expiresInDays=3651: `POST /api/links` expect 400

## TC-11 — Huge expiresInDays rejected with 400 (not 500) and no stack trace

1. Create with expiresInDays=99999999999999999999: `POST /api/links` expect 400

## TC-12 — Rejected expiresInDays=0 produces no Location header and no short code

1. Create with expiresInDays=0: `POST /api/links` expect 400

## TC-13 — Valid create after rejected invalid-expiry create succeeds and the valid link exists

1. Invalid create with expiresInDays=0: `POST /api/links` expect 400
2. Valid create: `POST /api/links` expect 201
3. Valid link details return 200: `GET /api/links/${code}` expect 200

## TC-14 — Link with expiresInDays=1 is live before expiry and is not answered with 410 (pre-advance portion; the contract exposes no test-clock control)

1. Create link with 1-day expiry: `POST /api/links` expect 201
2. Redirect before expiry: `GET /${code}` expect 302

## TC-15 — Link with expiresInDays=2 redirects with 302 before the 48h boundary

1. Create link with 2-day expiry: `POST /api/links` expect 201
2. Redirect before boundary: `GET /${code}` expect 302

## TC-16 — Link with expiresInDays=2 is not yet gone before creation + 48h (pre-boundary portion; the contract exposes no test-clock control)

1. Create link with 2-day expiry: `POST /api/links` expect 201
2. Redirect well before boundary is not 410: `GET /${code}` expect 302

## TC-17 — Link created without expiresInDays redirects with 302 to long URL

1. Create link without expiry: `POST /api/links` expect 201
2. Redirect: `GET /${code}` expect 302

## TC-18 — Upgraded service is running and a non-expiring link redirects with 302 to its long URL (API-observable portion; data-store upgrade and restarts are performed outside the contract)

1. Create link without expiry (as a pre-existing link would have): `POST /api/links` expect 201
2. Redirect for link without expiry: `GET /${code}` expect 302

## TC-19 — expiresInDays explicitly null is accepted with 201

1. Create with expiresInDays=null: `POST /api/links` expect 201

## TC-20 — Link created with expiresInDays=null redirects with 302

1. Create with expiresInDays=null: `POST /api/links` expect 201
2. Redirect: `GET /${code}` expect 302

## TC-21 — expiresInDays=7.0 rejected with 400 problem+json and no Location

1. Create with expiresInDays=7.0: `POST /api/links` expect 400

## TC-22 — expiresInDays=7e0 rejected with 400 problem+json and no Location

1. Create with expiresInDays=7e0: `POST /api/links` expect 400

## TC-23 — Single successful redirect on a 1-day link records clickCount=1 and a stable lastClickedAt (pre-advance portion; the contract exposes no test-clock control)

1. Create link with 1-day expiry: `POST /api/links` expect 201
2. Single successful redirect: `GET /${code}` expect 302
3. Analytics after one redirect: `GET /api/links/${code}/analytics` expect 200
4. Analytics reads do not change recorded values: `GET /api/links/${code}/analytics` expect 200

## TC-24 — Never-redirected 1-day link shows clickCount=0 and lastClickedAt=null (pre-advance portion; the contract exposes no test-clock control)

1. Create link with 1-day expiry: `POST /api/links` expect 201
2. Analytics for never-redirected link: `GET /api/links/${code}/analytics` expect 200

## TC-25 — Unexpired 5-day link redirects 302 with Location and Cache-Control no-store

1. Create link with 5-day expiry: `POST /api/links` expect 201
2. Redirect: `GET /${code}` expect 302

## TC-26 — Two redirects on an unexpired 5-day link yield clickCount=2 and non-null lastClickedAt

1. Create link with 5-day expiry: `POST /api/links` expect 201
2. Initial analytics shows zero clicks: `GET /api/links/${code}/analytics` expect 200
3. Redirect twice: `GET /${code}` ×2 expect 302
4. Analytics after two redirects: `GET /api/links/${code}/analytics` expect 200

## TC-27 — Unknown code zzzzzzz returns 404 problem+json

1. Redirect unknown code: `GET /zzzzzzz` expect 404

## TC-28 — Details of a 1-day link return 200 with exactly shortCode, longUrl, createdAt

1. Create link with 1-day expiry: `POST /api/links` expect 201
2. Get link details: `GET /api/links/${code}` expect 200

## TC-29 — Analytics of a 1-day link return 200 with exactly shortCode, clickCount, lastClickedAt

1. Create link with 1-day expiry: `POST /api/links` expect 201
2. Get analytics: `GET /api/links/${code}/analytics` expect 200

## TC-30 — Create with expiresInDays=7 returns exactly shortCode, longUrl, createdAt and no expiresAt

1. Create link with 7-day expiry: `POST /api/links` expect 201

## TC-31 — Create without expiresInDays returns 201 with Location and exactly the three fields

1. Create link with url only: `POST /api/links` expect 201

## TC-32 — Unknown alias property is ignored: 201 with Location and exactly the three fields

1. Create link with ignored alias: `POST /api/links` expect 201

## TC-33 — Redirect responses for a 1-day link carry Cache-Control: no-store (pre-advance portion; the contract exposes no test-clock control)

1. Create link with 1-day expiry: `POST /api/links` expect 201
2. Redirect response has no-store: `GET /${code}` expect 302
