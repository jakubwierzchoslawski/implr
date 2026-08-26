# Definition of Done

Canonical completion criteria enforced by `dev-executor` (gate to plan `done`) and
`dev-code-review` (gate to verdict `approved` / `approved-with-warnings`).

Individual requirements and plans MAY add atypical items under `## Acceptance Notes`.
This file lists what applies to every plan unless explicitly overridden.

## Per plan

1. All tasks in the plan are complete (`task_status: done` for each).
2. All unit tests for produced code pass.
3. All integration tests for produced code pass.
4. Every acceptance criterion (AC-NNN) in the linked requirement is covered by at least
   one task and verified by at least one passing test.
5. No `TODO` / `FIXME` / `XXX` markers introduced by the implementation.
6. `dev-code-review` produces verdict `approved` or `approved-with-warnings` (no
   Critical / High findings).

## Out of scope of the canonical DoD

These are NOT auto-enforced (require explicit Acceptance Notes per requirement):

- Manual QA sign-off
- Deployment to staging
- Product Owner approval
- Documentation site updates
- External smoke tests

If a requirement needs any of these, list them in its `## Acceptance Notes` section.
