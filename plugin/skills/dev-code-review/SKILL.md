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
- `docs/implr/config/standards-card.md` — read once and pass inline to each worker.
  Halt if missing: `❌ standards-card.md not found. Run /implr-init --refresh-card first.`

Do NOT pre-read `docs/ARCHITECTURE.md` or `docs/implr/config/DEV-STANDARDS.md` here —
workers read ARCHITECTURE.md themselves (full read needed for review), and standards-card
replaces DEV-STANDARDS.md.

## Preconditions

- `docs/implr/config/standards-card.md` exists (else: `❌ standards-card.md not found. Run
  /implr-init --refresh-card first.`).
- Each named plan is `status: done` — this is the ordering gate enforced in Phase 1; a plan
  that has not reached `done` is not reviewable yet.

## Parameters

- `/dev-code-review PLAN-F-001` — review one plan's output.
- `/dev-code-review PLAN-F-001 PLAN-F-002` — review several.
- `/dev-code-review --all` — review all `done` plans without a current review.
- `/dev-code-review --verbose` — include per-finding detail in aggregate report.
  Default: severity counts + verdicts only.

## Execution

### Phase 1 — Resolve scope

For named plans: validate they exist and are `status: done`.
For `--all`: read `plans-index.md`, pick `done` plans without an existing review file.

### Phase 2 — Dispatch `code-review-worker` per plan (parallel)

Before dispatch, compute `current_source_ref` by running `implr-validate
--source-ref <src_path> <tests_path>` (read `src`/`tests` from `implr.config.yaml` paths) and
use the printed value verbatim. **Never hand-compute this value** — the validator CLI is the
sole source.

Cap parallelism at 5.

Per dispatch scope: `{plan_path, requirement_path, review_path_out, src_path, tests_path, standards_card, current_source_ref, test_results_path}` where `standards_card` is the inline
content of `docs/implr/config/standards-card.md`, `current_source_ref` is the value just
computed, and `test_results_path` is `docs/implr/plans/test-results/<plan_id>-results.md` for
that plan.

The review paths follow: `docs/implr/reviews/REVIEW-F-NNN-<slug>.md` (numbering matches the
plan).

### Phase 3 — Aggregate verdicts

Collect verdicts and finding counts by severity.

### Phase 4 — Update `reviews-index.md`

Add entry per review with verdict and severity counts.

### Phase 4.5 — Reflect verdict on plan status

For each review with verdict `changes-required` or `rejected`: set the linked plan's
`status: in-progress` in `plans-index.md` AND in the plan file, and record the blocking finding
ids in the plan file's `## Risks and Notes` (or a `review_blockers:` frontmatter note). This
implements review-schema.md's required review→plan status write.

### Phase 5 — Report

```
🔍 dev-code-review complete  (v3.0)
Reviews: {n}   ✅{approved} ⚠️{warnings} ❌{changes} 🚫{rejected}
Findings: C={critical} H={high} M={medium} L={low} I={info}
Blocks merge: {plan ids with Critical or High; "none" if empty}

{With --verbose only:}
Per plan:
  PLAN-F-NNN — {verdict} — C={n} H={n} M={n} (review at {path})
```

## Verdict rules (enforced by worker)

- Critical present AND flagged unrecoverable → `rejected`
- Critical or High present (not flagged unrecoverable) → `changes-required`
- Only Medium/Low/Info findings → `approved-with-warnings`
- No findings → `approved`

Critical and High findings block merge.
