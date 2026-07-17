# Test Results Schema

Per-plan record of test execution, written by `plan-runner` and consumed by
`code-review-worker` for the staleness rule. One file per plan.

Location: `docs/implr/plans/test-results/PLAN-F-NNN-results.md`

```markdown
---
plan_id: PLAN-F-001
run_at: {ISO timestamp}
source_ref: {output of implr_validate --source-ref src tests}
executed_at: {plan.executed_at at time of run}
---

# Test Results — PLAN-F-001

| Task | Command | Exit | Result | Output tail |
|------|---------|------|--------|-------------|
| TASK-001 | pytest tests/test_auth.py | 0 | pass | ...last lines... |
| TASK-002 | pytest tests/test_token.py | 1 | fail | ...last lines... |
```

## Staleness rule (enforced by code-review-worker)

A review downgrades to at least `changes-required` when this file is:
- missing for the reviewed plan, OR
- `plan_id` ≠ the reviewed plan, OR
- `source_ref` ≠ the review's `current_source_ref`, OR
- `run_at` earlier than the plan's `executed_at`.

Otherwise the review fails the plan on any covered test whose Result is not `pass`.
