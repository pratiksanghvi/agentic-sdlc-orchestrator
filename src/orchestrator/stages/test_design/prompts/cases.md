<acceptance_criteria>
$criteria
</acceptance_criteria>

<openapi>
$openapi
</openapi>

<review_feedback>
$feedback
</review_feedback>

Design functional test cases (ids TC-$first_id, TC-$second_id, ...):
- For each acceptance criterion, at least one positive case plus the negative and edge cases that
  criterion implies (invalid input, unknown ids, boundary values) — normally 1–3 cases per
  criterion.
- kind: positive | negative | edge. phase: always "main".
- Steps: method, path, headers (Content-Type: application/json when sending a body), body_json as
  a JSON string or null, repeat 1, expect_status exact (or expect_status_not), assertions,
  captures, follow_redirects false.
If review_feedback is present, address every item and keep everything else unchanged.
