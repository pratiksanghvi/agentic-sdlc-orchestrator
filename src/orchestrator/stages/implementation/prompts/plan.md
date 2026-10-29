<file_tree>
$tree
</file_tree>

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

Break the implementation into 3–8 ordered tasks (ids T-1, T-2, ...). Each task: goal, the files it
creates or modifies, depends_on (earlier task ids), traces (requirement ids), done_criteria.
$scaffold_rule
- Each later task must leave the project compiling.
- Each catalog NFR in the plan gets its own task that follows the catalog implementation text.
- Include unit tests in the task that adds the code they test.
