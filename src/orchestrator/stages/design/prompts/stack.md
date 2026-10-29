<existing_system>
$existing
</existing_system>

<spec>
$spec
</spec>

<supported_stacks>
$stacks
</supported_stacks>

<review_feedback>
$feedback
</review_feedback>

Propose 2–3 stack options for this service (language, framework, build tool, persistence, test
framework). For each give pros, cons and fit with the spec, and say whether it is in
supported_stacks (give its stack_id, else null). Recommend exactly one stack_id from
supported_stacks, with a rationale, consequences, and why the alternatives were rejected (ADR style).
If <existing_system> describes an existing service, you must keep its stack.
Prefer a stack marked VALIDATED end-to-end unless the spec's constraints require a technology;
if they do, the recommendation must honor it when a supported stack does. If review_feedback is present, address it.
