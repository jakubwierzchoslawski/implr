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

If none: `N/A`

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

### TASK-001: {Title}
**Complexity**: S | **TDD**: false
**Files**: {paths}

{Description of what to build.}

**Tests to write first (TDD)**: only present when TDD is true for this task.
- {Test case description}

**Acceptance criteria covered**: {AC ids, or "enables AC-00x"}

## Acceptance Criteria Coverage
| AC | Description | Covered by |
|----|-------------|-----------|
| AC-001 | {text} | TASK-002, TASK-006 |

Every acceptance criterion in the linked requirement must appear here, covered by at least
one task.

## Definition of Done
Plan-specific DoD, derived from the requirement DoD and enriched with implementation specifics.

- [ ] All tasks complete
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] All acceptance criteria verified
- [ ] No TODO/FIXME in produced code
- [ ] dev-code-review run and Critical/High findings resolved

## Open Questions Inherited
| # | Question | Resolution |
|---|----------|-----------|
| 1 | {Question from requirement} | {How it was resolved during planning} |

## Risks and Notes
- {Implementation risk, gotcha, or decision the developer should know}
```

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
