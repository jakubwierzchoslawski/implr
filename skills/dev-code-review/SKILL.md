---
name: dev-code-review
description: >
  Reviews produced code per plan. Dispatches one code-review-worker subagent per plan in
  parallel. Each verifies acceptance criteria, checks architecture/SOLID/security, audits
  tests, and writes a review file. Use when asked to review built code.
---

# dev-code-review Skill (v2.0 orchestrator)

You orchestrate code review. Per-plan review runs in parallel `code-review-worker`
subagents in a fresh context per plan.

## Read first

- `docs/implr/schemas/review-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`

## Parameters

- `/dev-code-review PLAN-F-001` — review one plan's output.
- `/dev-code-review PLAN-F-001 PLAN-F-002` — review several.
- `/dev-code-review --all` — review all `done` plans without a current review.

## Execution

### Phase 1 — Resolve scope

For named plans: validate they exist and are `status: done`.
For `--all`: read `plans-index.md`, pick `done` plans without an existing review file.

### Phase 2 — Dispatch `code-review-worker` per plan (parallel)

Cap parallelism at 5.

Per dispatch scope: `{plan_path, requirement_path, review_path_out, src_path, tests_path}`.

The review paths follow: `docs/implr/reviews/REVIEW-F-NNN-<slug>.md` (numbering matches the
plan).

### Phase 3 — Aggregate verdicts

Collect verdicts and finding counts by severity.

### Phase 4 — Update `reviews-index.md`

Add entry per review with verdict and severity counts.

### Phase 5 — Report

```
🔍 dev-code-review complete  (v2.0)
Reviews written: {n}
Verdicts:
  ✅ approved: {n}
  ⚠️  approved-with-warnings: {n}
  ❌ changes-required: {n}
  🚫 rejected: {n}
Findings totals:
  Critical: {n}   High: {n}   Medium: {n}   Low: {n}   Info: {n}

Blocks merge: {list of plan ids with Critical or High findings}
```

## Verdict rules (enforced by worker)

- Critical present AND flagged unrecoverable → `rejected`
- Critical or High present (not flagged unrecoverable) → `changes-required`
- Only Medium/Low/Info findings → `approved-with-warnings`
- No findings → `approved`

Critical and High findings block merge.
