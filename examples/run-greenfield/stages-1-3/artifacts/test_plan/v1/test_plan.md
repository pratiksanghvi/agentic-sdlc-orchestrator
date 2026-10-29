# Acceptance test plan

| Case | Covers | Kind | Phase | Title |
|---|---|---|---|---|
| TC-1 | AC-1.1 | positive | main | Create short link for a valid https URL returns 201 with a non-empty short code |
| TC-2 | AC-1.2 | positive | main | Details of a just-created link return the original URL |
| TC-3 | AC-2.1 | positive | main | Redirect Location header equals the original long URL |
| TC-4 | AC-3.1 | positive | main | Redirect status code is exactly 302 |
| TC-5 | AC-4.1 | positive | main | Details return the same short code that was requested |
| TC-6 | AC-5.1 | positive | main | Three redirects produce a click count of 3 |
| TC-7 | AC-5.2 | positive | main | Clicks are counted per link independently (A=2, B=1) |
| TC-8 | AC-6.1 | positive | main | Last-click timestamp is present as a date-time after one redirect |
| TC-9 | AC-6.2 | edge | main | A second redirect updates the last-click timestamp |
| TC-10 | AC-7.1 | positive | main | Analytics after one click report count 1 and non-null last-click timestamp |
| TC-11 | AC-8.1 | positive | main | Two links for different URLs get different service-generated codes |
| TC-12 | AC-9.1 | edge | main | Same long URL submitted twice yields different short codes |
| TC-13 | AC-9.2 | edge | main | Links for the same URL count clicks independently |
| TC-14 | AC-10.1 | negative | main | ftp URL is rejected with 400 and no short code |
| TC-15 | AC-10.2 | negative | main | Relative path is rejected with 400 and no short code |
| TC-16 | AC-10.3 | edge | main | Plain http URL without path is accepted |
| TC-17 | AC-11.1 | positive | main | Details include short code, original URL and creation timestamp |
| TC-18 | AC-12.1 | negative | main | Redirect for unknown code returns 404 |
| TC-19 | AC-12.2 | negative | main | Details for unknown code return 404 |
| TC-20 | AC-12.3 | negative | main | Analytics for unknown code return 404 |
| TC-21 | AC-13.1 | edge | main | Never-clicked link reports 0 clicks and no last-click timestamp |
| TC-22 | AC-14.1 | edge | main | Five identical redirects from the same client count 5 clicks |
| TC-23 | AC-14.2 | negative | main | Redirect for unknown code does not increment an existing link's count |
| TC-24 | AC-15.1 | positive | main | All operations succeed without credentials |

## TC-1 — Create short link for a valid https URL returns 201 with a non-empty short code

1. Create short link: `POST /api/links` expect 201

## TC-2 — Details of a just-created link return the original URL

1. Create short link: `POST /api/links` expect 201
2. Get details: `GET /api/links/${code}` expect 200

## TC-3 — Redirect Location header equals the original long URL

1. Create short link: `POST /api/links` expect 201
2. Request redirect without following: `GET /${code}` expect 302

## TC-4 — Redirect status code is exactly 302

1. Create short link: `POST /api/links` expect 201
2. Request redirect without following: `GET /${code}` expect 302

## TC-5 — Details return the same short code that was requested

1. Create short link: `POST /api/links` expect 201
2. Get details: `GET /api/links/${code}` expect 200

## TC-6 — Three redirects produce a click count of 3

1. Create short link: `POST /api/links` expect 201
2. Verify initial click count is 0: `GET /api/links/${code}/analytics` expect 200
3. Redirect 3 times: `GET /${code}` ×3 expect 302
4. Get analytics: `GET /api/links/${code}/analytics` expect 200

## TC-7 — Clicks are counted per link independently (A=2, B=1)

1. Create link A: `POST /api/links` expect 201
2. Create link B: `POST /api/links` expect 201
3. Redirect A twice: `GET /${codeA}` ×2 expect 302
4. Redirect B once: `GET /${codeB}` expect 302
5. Analytics for A: `GET /api/links/${codeA}/analytics` expect 200
6. Analytics for B: `GET /api/links/${codeB}/analytics` expect 200

## TC-8 — Last-click timestamp is present as a date-time after one redirect

1. Create short link: `POST /api/links` expect 201
2. Redirect once: `GET /${code}` expect 302
3. Get analytics: `GET /api/links/${code}/analytics` expect 200

## TC-9 — A second redirect updates the last-click timestamp

1. Create short link: `POST /api/links` expect 201
2. First redirect: `GET /${code}` expect 302
3. Analytics after first click: `GET /api/links/${code}/analytics` expect 200
4. Second redirect: `GET /${code}` expect 302
5. Analytics after second click: `GET /api/links/${code}/analytics` expect 200

## TC-10 — Analytics after one click report count 1 and non-null last-click timestamp

1. Create short link: `POST /api/links` expect 201
2. Redirect once: `GET /${code}` expect 302
3. Get analytics: `GET /api/links/${code}/analytics` expect 200

## TC-11 — Two links for different URLs get different service-generated codes

1. Create first link: `POST /api/links` expect 201
2. Create second link: `POST /api/links` expect 201
3. Details of first link map to first URL: `GET /api/links/${codeA}` expect 200
4. Details of second link map to second URL: `GET /api/links/${codeB}` expect 200

## TC-12 — Same long URL submitted twice yields different short codes

1. Create first link for dup URL: `POST /api/links` expect 201
2. Create second link for dup URL: `POST /api/links` expect 201

## TC-13 — Links for the same URL count clicks independently

1. Create link A: `POST /api/links` expect 201
2. Create link B with same URL: `POST /api/links` expect 201
3. Redirect A once: `GET /${codeA}` expect 302
4. Analytics for A: `GET /api/links/${codeA}/analytics` expect 200
5. Analytics for B: `GET /api/links/${codeB}/analytics` expect 200

## TC-14 — ftp URL is rejected with 400 and no short code

1. Create with ftp URL: `POST /api/links` expect 400

## TC-15 — Relative path is rejected with 400 and no short code

1. Create with relative path: `POST /api/links` expect 400

## TC-16 — Plain http URL without path is accepted

1. Create with http://example.com: `POST /api/links` expect 201

## TC-17 — Details include short code, original URL and creation timestamp

1. Create short link: `POST /api/links` expect 201
2. Get details: `GET /api/links/${code}` expect 200

## TC-18 — Redirect for unknown code returns 404

1. Redirect unknown code: `GET /doesnotexist123` expect 404

## TC-19 — Details for unknown code return 404

1. Details unknown code: `GET /api/links/doesnotexist123` expect 404

## TC-20 — Analytics for unknown code return 404

1. Analytics unknown code: `GET /api/links/doesnotexist123/analytics` expect 404

## TC-21 — Never-clicked link reports 0 clicks and no last-click timestamp

1. Create short link: `POST /api/links` expect 201
2. Get analytics: `GET /api/links/${code}/analytics` expect 200

## TC-22 — Five identical redirects from the same client count 5 clicks

1. Create short link: `POST /api/links` expect 201
2. Redirect 5 times with identical headers: `GET /${code}` ×5 expect 302
3. Get analytics: `GET /api/links/${code}/analytics` expect 200

## TC-23 — Redirect for unknown code does not increment an existing link's count

1. Create short link: `POST /api/links` expect 201
2. Redirect unknown code: `GET /doesnotexist123` expect 404
3. Get analytics for existing link: `GET /api/links/${code}/analytics` expect 200

## TC-24 — All operations succeed without credentials

1. Create without credentials: `POST /api/links` expect 201
2. Redirect without credentials: `GET /${code}` expect 302
3. Details without credentials: `GET /api/links/${code}` expect 200
4. Analytics without credentials: `GET /api/links/${code}/analytics` expect 200
