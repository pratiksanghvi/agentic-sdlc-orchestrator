<design>
$design
</design>

<openapi>
$openapi
</openapi>

<schema_sql>
$schema_sql
</schema_sql>

<nfr_plan>
$nfr_plan
</nfr_plan>

<task_plan>
$plan
</task_plan>

<file_tree>
$tree
</file_tree>

<existing_files>
$existing
</existing_files>

<current_task>
$task
</current_task>

<previous_attempt_errors>
$errors
</previous_attempt_errors>

<human_hint>
$hint
</human_hint>

Implement the current task. Return every file you create or modify with its complete content.
If previous_attempt_errors is present, fix those errors without changing unrelated code.
If human_hint is present, follow it.
