<requirement>
$requirement
</requirement>

<clarifications>
$clarifications
</clarifications>

Analyze the requirement:
1. State the core intent in one sentence.
2. List the functional needs the user stated (with exact source quotes). Include needs settled by
   clarification answers.
3. List and classify every non-functional ask per the NFR policy.
4. List ambiguities with ids Q-1, Q-2, ... For each: the question, why it matters, a recommended
   default, severity and 2–4 answer options. BLOCKING only if a wrong guess would change the
   externally visible behavior or the data kept; otherwise NON_BLOCKING. Do not repeat questions
   already answered in <clarifications>. Keep BLOCKING questions to the few that truly matter.
5. List what is explicitly out of scope.
6. Record any technology the user explicitly required as stack_constraint (else null).
