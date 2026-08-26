# Phase: review-plan

Dispatch prompt for `code-review-worker`. One dispatch per plan in scope.

## Read first
- `docs/implr/schemas/review-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- Plan and requirement (paths in scope)

## Your scope
```
plan_path: {{PLAN_PATH}}
requirement_path: {{REQUIREMENT_PATH}}
review_path_out: {{REVIEW_PATH_OUT}}
src_path: src
tests_path: tests
```

## Task
Verify each AC, check architecture/SOLID/security, audit tests. Issue verdict per schema.

## Return summary
(review report per agent system prompt)
