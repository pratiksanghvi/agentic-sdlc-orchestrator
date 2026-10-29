<failure stage="$failed_stage">
$failure
</failure>

<service_log_tail>
$service_log
</service_log_tail>

<openapi>
$openapi
</openapi>

<design>
$design
</design>

<file_tree>
$tree
</file_tree>

<source_files>
$sources
</source_files>

<previous_attempts>
$previous
</previous_attempts>

<human_hint>
$hint
</human_hint>

The approved acceptance tests are frozen: you cannot see or change them, and they verify the
behavior defined by the OpenAPI contract. Diagnose the root cause in `notes` (one paragraph),
then fix the PRODUCT code: return every file you change with its complete content.
- Do not repeat a fix listed in previous_attempts.
- If you believe a test contradicts the approved contract, say so in notes and still make the
  product satisfy the contract.
- If human_hint is present, follow it.
