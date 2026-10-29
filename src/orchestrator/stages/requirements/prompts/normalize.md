<requirement>
$requirement
</requirement>

<clarifications>
$clarifications
</clarifications>

<analysis>
$analysis
</analysis>

<review_feedback>
$feedback
</review_feedback>

Write the engineering spec for the MVP:
- Functional requirements FR-1, FR-2, ... each with priority (MVP or LATER), source and an exact
  source_quote. Unanswered NON_BLOCKING ambiguities are resolved with their recommended default and
  listed as assumptions (A-1, ...); requirements that rest on an assumption use source "assumption".
- Non-functional requirements NFR-1, ... ONLY for analysis items classified SUPPORTED. Each has the
  catalog_id, params (name/value pairs using the catalog's parameter names; use catalog defaults
  unless the user stated a value), source explicit or clarification, and the exact source_quote.
- Acceptance criteria AC-<n>.<m> for every MVP functional requirement (1–4 each), in
  Given/When/Then form with a concrete, measurable outcome observable through the HTTP API, and a
  verification_method (e.g. "HTTP request and response assertion").
  Use only behavior the requirement or clarifications support; no vague words like "fast".
- Out of scope list.
Do not mention technologies, frameworks or databases in requirements or criteria.
If review_feedback is present, address every item in it and keep everything else unchanged.
