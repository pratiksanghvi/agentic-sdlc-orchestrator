# Acceptance test plan

| Case | Covers | Kind | Phase | Title |
|---|---|---|---|---|
| TC-1 | AC-1.1 | positive | main | Create link with expiresInDays=7 returns 201 and Location /api/links/{code} |
| TC-2 | AC-2.1 | edge | main | Create link with minimum expiresInDays=1 returns 201 with exactly shortCode, longUrl, createdAt |
| TC-3 | AC-2.1 | edge | main | Create link with maximum expiresInDays=3650 returns 201 with exactly shortCode, longUrl, createdAt |
| TC-4 | AC-2.2 | positive | main | Link created with expiresInDays=3650 redirects immediately with 302 to the submitted URL |
| TC-5 | AC-3.1 | edge | main | expiresInDays=0 is rejected with 400 problem+json mentioning the expiry field |
| TC-6 | AC-3.1 | negative | main | expiresInDays=-1 is rejected with 400 problem+json mentioning the expiry field |
| TC-7 | AC-3.1 | negative | main | Fractional expiresInDays=1.5 is rejected with 400 problem+json mentioning the expiry field |
| TC-8 | AC-3.1 | negative | main | String expiresInDays "7" is rejected with 400 problem+json mentioning the expiry field |
| TC-9 | AC-3.1 | edge | main | expiresInDays=3651 (just above maximum) is rejected with 400 problem+json mentioning the expiry field |
| TC-10 | AC-3.2 | edge | main | Huge expiresInDays=99999999999999999999 returns 400 problem+json without stack trace |
| TC-11 | AC-4.1 | negative | main | Rejected create with expiresInDays=0 has no Location header and produces no short code |
| TC-12 | AC-4.1 | edge | main | Rejected create with out-of-range expiresInDays=3651 has no Location header and produces no short code |
| TC-13 | AC-4.2 | positive | main | Valid create after a rejected invalid-expiry create returns 201 and the valid link's details return 200 |
| TC-14 | AC-6.1 | positive | main | Link created with expiresInDays=2 redirects with 302 before its expiry instant (clock control not exposed by the contract; verified immediately after creation) |
| TC-15 | AC-7.1 | positive | main | Link created without expiresInDays redirects with 302 to the long URL (clock control not exposed by the contract) |
| TC-16 | AC-8.1 | edge | main | Create link with expiresInDays explicitly null returns 201 |
| TC-17 | AC-8.2 | positive | main | Link created with expiresInDays null redirects with 302 (clock control not exposed by the contract) |
| TC-18 | AC-9.1 | negative | main | expiresInDays=7.0 is rejected with 400 problem+json and no Location header |
| TC-19 | AC-9.1 | negative | main | expiresInDays=7e0 is rejected with 400 problem+json and no Location header |
| TC-20 | AC-11.1 | positive | main | Unexpired link redirects with 302, Location equal to long URL and Cache-Control no-store |
| TC-21 | AC-11.2 | positive | main | Two redirects of an unexpired link are counted: clickCount=2 and non-null lastClickedAt |
| TC-22 | AC-12.1 | negative | main | Redirect for unknown code zzzzzzz returns 404 problem+json |
| TC-23 | AC-13.1 | positive | main | Details of a link created with expiresInDays=1 return 200 with exactly shortCode, longUrl, createdAt (clock control not exposed by the contract) |
| TC-24 | AC-13.2 | positive | main | Analytics of a link created with expiresInDays=1 return 200 with exactly shortCode, clickCount, lastClickedAt (clock control not exposed by the contract) |
| TC-25 | AC-14.1 | positive | main | Create with expiresInDays=7 returns exactly shortCode, longUrl, createdAt and no expiresAt |
| TC-26 | AC-14.2 | positive | main | Create without expiresInDays returns 201 with Location and exactly shortCode, longUrl, createdAt |
| TC-27 | AC-14.2 | edge | main | Create with unknown alias property returns 201 with Location and exactly shortCode, longUrl, createdAt (alias ignored) |

## TC-1 — Create link with expiresInDays=7 returns 201 and Location /api/links/{code}

1. Create link with 7-day expiry: `POST /api/links` expect 201
2. Location target resolves to the created link: `GET /api/links/${code}` expect 200

## TC-2 — Create link with minimum expiresInDays=1 returns 201 with exactly shortCode, longUrl, createdAt

1. Create link with expiresInDays=1: `POST /api/links` expect 201

## TC-3 — Create link with maximum expiresInDays=3650 returns 201 with exactly shortCode, longUrl, createdAt

1. Create link with expiresInDays=3650: `POST /api/links` expect 201

## TC-4 — Link created with expiresInDays=3650 redirects immediately with 302 to the submitted URL

1. Create link with expiresInDays=3650: `POST /api/links` expect 201
2. Redirect immediately: `GET /${code}` expect 302

## TC-5 — expiresInDays=0 is rejected with 400 problem+json mentioning the expiry field

1. Create with expiresInDays=0: `POST /api/links` expect 400

## TC-6 — expiresInDays=-1 is rejected with 400 problem+json mentioning the expiry field

1. Create with expiresInDays=-1: `POST /api/links` expect 400

## TC-7 — Fractional expiresInDays=1.5 is rejected with 400 problem+json mentioning the expiry field

1. Create with expiresInDays=1.5: `POST /api/links` expect 400

## TC-8 — String expiresInDays "7" is rejected with 400 problem+json mentioning the expiry field

1. Create with expiresInDays="7": `POST /api/links` expect 400

## TC-9 — expiresInDays=3651 (just above maximum) is rejected with 400 problem+json mentioning the expiry field

1. Create with expiresInDays=3651: `POST /api/links` expect 400

## TC-10 — Huge expiresInDays=99999999999999999999 returns 400 problem+json without stack trace

1. Create with overflowing expiresInDays: `POST /api/links` expect 400

## TC-11 — Rejected create with expiresInDays=0 has no Location header and produces no short code

1. Create with expiresInDays=0: `POST /api/links` expect 400

## TC-12 — Rejected create with out-of-range expiresInDays=3651 has no Location header and produces no short code

1. Create with expiresInDays=3651: `POST /api/links` expect 400

## TC-13 — Valid create after a rejected invalid-expiry create returns 201 and the valid link's details return 200

1. Invalid create rejected: `POST /api/links` expect 400
2. Valid create succeeds: `POST /api/links` expect 201
3. Valid link details return 200: `GET /api/links/${code}` expect 200

## TC-14 — Link created with expiresInDays=2 redirects with 302 before its expiry instant (clock control not exposed by the contract; verified immediately after creation)

1. Create link with expiresInDays=2: `POST /api/links` expect 201
2. Redirect before expiry: `GET /${code}` expect 302

## TC-15 — Link created without expiresInDays redirects with 302 to the long URL (clock control not exposed by the contract)

1. Create link without expiresInDays: `POST /api/links` expect 201
2. Redirect: `GET /${code}` expect 302

## TC-16 — Create link with expiresInDays explicitly null returns 201

1. Create with expiresInDays=null: `POST /api/links` expect 201

## TC-17 — Link created with expiresInDays null redirects with 302 (clock control not exposed by the contract)

1. Create with expiresInDays=null: `POST /api/links` expect 201
2. Redirect: `GET /${code}` expect 302

## TC-18 — expiresInDays=7.0 is rejected with 400 problem+json and no Location header

1. Create with expiresInDays=7.0: `POST /api/links` expect 400

## TC-19 — expiresInDays=7e0 is rejected with 400 problem+json and no Location header

1. Create with expiresInDays=7e0: `POST /api/links` expect 400

## TC-20 — Unexpired link redirects with 302, Location equal to long URL and Cache-Control no-store

1. Create link with expiresInDays=5: `POST /api/links` expect 201
2. Redirect: `GET /${code}` expect 302

## TC-21 — Two redirects of an unexpired link are counted: clickCount=2 and non-null lastClickedAt

1. Create link with expiresInDays=5: `POST /api/links` expect 201
2. Analytics start at zero: `GET /api/links/${code}/analytics` expect 200
3. Redirect twice: `GET /${code}` ×2 expect 302
4. Analytics show two clicks: `GET /api/links/${code}/analytics` expect 200

## TC-22 — Redirect for unknown code zzzzzzz returns 404 problem+json

1. Redirect unknown code: `GET /zzzzzzz` expect 404

## TC-23 — Details of a link created with expiresInDays=1 return 200 with exactly shortCode, longUrl, createdAt (clock control not exposed by the contract)

1. Create link with expiresInDays=1: `POST /api/links` expect 201
2. Get link details: `GET /api/links/${code}` expect 200

## TC-24 — Analytics of a link created with expiresInDays=1 return 200 with exactly shortCode, clickCount, lastClickedAt (clock control not exposed by the contract)

1. Create link with expiresInDays=1: `POST /api/links` expect 201
2. Get link analytics: `GET /api/links/${code}/analytics` expect 200

## TC-25 — Create with expiresInDays=7 returns exactly shortCode, longUrl, createdAt and no expiresAt

1. Create link with expiresInDays=7: `POST /api/links` expect 201

## TC-26 — Create without expiresInDays returns 201 with Location and exactly shortCode, longUrl, createdAt

1. Create link with url only: `POST /api/links` expect 201

## TC-27 — Create with unknown alias property returns 201 with Location and exactly shortCode, longUrl, createdAt (alias ignored)

1. Create link with alias: `POST /api/links` expect 201
