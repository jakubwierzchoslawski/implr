# Plan Schema

Canonical structure for implementation plans (PLAN-F, PLAN-N). Produced by `dev-planner`.
Consumed by `dev-executor` and `dev-code-review`.

A plan maps 1:1 to a requirement: PLAN-F-007 always corresponds to REQ-F-007.

---

## Plan — full structure

```markdown
---
plan_id: PLAN-F-001
slug: user-password-reset
title: User Password Reset Implementation
linked_requirement: REQ-F-001
type: functional                 # functional | non-functional
status: ready                    # ready | in-progress | done | blocked
blocked_reason:                  # text if status is blocked, else blank
complexity: M
tdd_required: true
linked_nfrs:
  - { id: REQ-N-001, reason: "Latency constraint applies to reset endpoint" }
dependencies:
  - { id: PLAN-F-002, reason: "User entity must exist" }
brainstorm_decisions:            # present only if --brainstorm was used, else omit
  - decision: Token Storage Strategy
    options_considered: [DB hashed token, JWT stateless, Redis HMAC]
    chosen: DB hashed token
    rationale: "Redis not in confirmed stack; statelessness risks single-use enforcement"
    decided_at: {ISO timestamp}
executed_at:                     # filled by dev-executor
reviewed_at:                     # filled by dev-code-review
review_id:                       # REVIEW-F-NNN, filled by dev-code-review
created_at: {ISO timestamp}
updated_at: {ISO timestamp}
---

# PLAN-F-001 — User Password Reset Implementation

## Linked Requirement
**REQ-F-001** — User Password Reset
Status: approved | Jira: {jira.id or blank}

## Objective
One paragraph. The technical interpretation of the business requirement — what will be built,
in concrete terms.

## Architecture Context
How this plan fits the system architecture. Layers touched, modules extended, modules
introduced. Reference specific sections of docs/ARCHITECTURE.md.

## Brainstorm Decisions
Present only if --brainstorm was used. Summarises each design decision and the chosen approach.
Omit this section entirely otherwise.

## Applied NFR Constraints
| NFR | Constraint | Impact on this plan |
|-----|-----------|---------------------|
| REQ-N-001 | p99 < 200ms | Index added in TASK-001; no synchronous email in request path |

## Component Design

### New Components
```
Module: AuthModule (src/modules/auth/)
  ├── AuthController     — HTTP routing + validation only
  ├── AuthService        — business logic
  ├── AuthRepository     — DB access (interface + implementation)
  └── Interfaces:
      └── IAuthRepository
```

### Modified Components
| File | Change | Reason |
|------|--------|--------|
| src/app.module.ts | Register AuthModule | Wire new module |

### Interfaces and Contracts
Precise interface definitions the executor must implement exactly.

```
interface IAuthRepository {
  findUserByEmail(email: string): Promise<User | null>;
  createResetToken(userId: string, tokenHash: string, expiresAt: Date): Promise<void>;
}
```

## Implementation Tasks
Ordered. Each task carries complexity and a TDD flag derived from the plan and task scope.

### TASK-001: {Title} · S/no-TDD · {comma-separated files}

{Description of what to build.}

**Tests to write first (TDD)**: only present when TDD is true for this task.
- {Test case description}

**Acceptance criteria covered**: {AC ids, or "enables AC-00x"}

## Acceptance Criteria Coverage
Every acceptance criterion in the linked requirement must appear here, covered by at least one task.

- AC-001: {text} → TASK-002, TASK-006

## Acceptance Notes
Optional. Present only when completion requires atypical steps (e.g. manual deployment, external
sign-off, environment-specific verification). Omit this section entirely if not needed.

## Open Questions Inherited
| # | Question | Resolution |
|---|----------|-----------|
| 1 | {Question from requirement} | {How it was resolved during planning} |

## Risks and Notes
- {Implementation risk, gotcha, or decision the developer should know}
```

---

## Optional-sections rule

`dev-planner` MUST omit the following sections entirely when they have no content — do not emit
a heading with "N/A" or an empty body:

- **Brainstorm Decisions** — omit unless `--brainstorm` was used and decisions were recorded
- **Applied NFR Constraints** — omit when no NFRs apply to this plan
- **Acceptance Notes** — omit unless atypical completion requirements exist
- **Open Questions Inherited** — omit when the requirement carried no unresolved questions
- **Risks and Notes** — omit when there are no known risks or implementation caveats

---

## Task dispatch in v3.0

`task-executor` does NOT read the plan file directly. `dev-executor` parses the plan and
dispatches each task as an inline task envelope passed to the executor agent.

**Parseable task-header format:**

```
### TASK-001: {Title} · {complexity}/{tdd-flag} · {comma-separated files}
```

- `{tdd-flag}` is `TDD` when `tdd_required: true` for the task, otherwise `no-TDD`
- `^### TASK-(\d{3}): ` is the required prefix regex used by dev-executor to locate tasks
- Everything on the header line after the title is machine-readable metadata; do not reorder fields

---

## Status Lifecycle

```
ready → in-progress → done
  ↑                     |
  └──── (changes-required from review) ←┘
blocked → ready (once blocker resolved)
```

- `dev-planner` creates plans as `ready` (or `blocked` if it cannot fully specify).
- `dev-executor` sets `in-progress` at start, `done` on completion.
- `dev-code-review` may set back to `in-progress` if the verdict is changes-required/rejected.

---

## ID Conventions

| Type | Prefix | Example |
|------|--------|---------|
| Functional plan | PLAN-F- | PLAN-F-001 |
| Non-functional plan | PLAN-N- | PLAN-N-001 |

Plan ID number always matches its linked requirement number.

---

## plans-index.md

Location: `docs/implr/plans/plans-index.md`. Maintained by `dev-planner`.

```markdown
# Plans Index

> Maintained by dev-planner. Do not edit manually.
> Last updated: {ISO timestamp}

## Statistics
| Metric | Count |
|--------|-------|
| Total plans | 0 |
| Ready | 0 |
| In progress | 0 |
| Done | 0 |
| Blocked | 0 |

## Functional Plans
| ID | Title | Requirement | Complexity | TDD | Status | File |
|----|-------|-------------|-----------|-----|--------|------|

## Non-Functional Plans
| ID | Title | Requirement | Complexity | TDD | Status | File |
|----|-------|-------------|-----------|-----|--------|------|

## Execution Order
Topologically sorted by dependencies. This is the order dev-executor --all follows.

1. PLAN-F-001 — {title} [no dependencies]
2. PLAN-F-002 — {title} [depends on PLAN-F-001]

## Blocked Plans
| ID | Reason |
|----|--------|
```
