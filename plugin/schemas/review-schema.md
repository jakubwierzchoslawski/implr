# Review Schema

Canonical structure for code review reports (REVIEW-F, REVIEW-N). Produced by `dev-code-review`
in a fresh context.

A review maps 1:1 to a plan: REVIEW-F-007 reviews PLAN-F-007.

---

## Review — full structure

```markdown
---
review_id: REVIEW-F-001
plan_id: PLAN-F-001
requirement_id: REQ-F-001
status: approved-with-warnings   # approved | approved-with-warnings | changes-required | rejected
reviewed_at: {ISO timestamp}
findings_summary:
  critical: 0
  high: 0
  warning: 2
  info: 1
ac_coverage: "3/3"
dod_complete: false
manual_actions_pending: 2
---

# REVIEW-F-001 — User Password Reset

## Verdict
**APPROVED WITH WARNINGS**

One paragraph explaining the verdict. If changes required, state the blockers plainly.

## Acceptance Criteria Verification
| AC | Status | Evidence |
|----|--------|---------|
| AC-001 | ✅ | auth.service.ts:requestPasswordReset() + test L45 |
| AC-002 | ✅ | token.service.ts:getExpiryDate() + test L78 |
| AC-003 | ❌ | No test verifies reused-token rejection |

Any ❌ is an automatic Critical finding.

## Definition of Done Status
| Item | Status |
|------|--------|
| All tasks complete | ✅ |
| Unit tests passing | ✅ |
| Migration applied | ⚠️ Manual action |

## Findings

### 🔴 CRITICAL (blocks merge)
None.

### 🔴 HIGH (blocks merge)
None.

### 🟡 WARNING (should fix before merge)

#### W-001 — {Short title}
**File**: {path:line}
**Rule**: {DEV-STANDARDS.md or ARCHITECTURE.md section, or universal principle}
**Finding**: {Specific description of what is wrong}
**Fix**: {Concrete suggested change}

### 🔵 INFO (optional)

#### I-001 — {Short title}
**File**: {path}
**Finding**: {Observation}

## Manual Actions Required Before Merge
1. {Action that cannot be verified or performed in review context}

## Files Reviewed
| File | Lines | Status |
|------|-------|--------|
| src/modules/auth/auth.service.ts | 134 | ✅ |
```

---

## Severity Reference

| Severity | Symbol | Merge policy | Examples |
|----------|--------|-------------|----------|
| Critical | 🔴 | Blocks merge | Missing AC coverage, security vulnerability, data-loss risk, broken/missing tests |
| High | 🔴 | Blocks merge | Architecture violation, SOLID violation with real maintenance risk, missing auth on protected route |
| Warning | 🟡 | Should fix | Missing test case, naming violation, unexported public interface, code smell |
| Info | 🔵 | Optional | Refactor suggestion, future extraction candidate, minor style note |

Security findings are never below High.

---

## Verdict Rules

| Condition | Verdict |
|-----------|---------|
| No findings at any level | approved |
| Only Warning and/or Info findings | approved-with-warnings |
| One or more High (no Critical) | changes-required |
| One or more Critical | rejected |

On `changes-required` or `rejected`, `dev-code-review` sets the linked plan status back to
`in-progress` in plans-index.md and records which findings are blocking.

---

## ID Conventions

| Type | Prefix | Example |
|------|--------|---------|
| Functional review | REVIEW-F- | REVIEW-F-001 |
| Non-functional review | REVIEW-N- | REVIEW-N-001 |

---

## reviews-index.md

Location: `docs/implr/reviews/reviews-index.md`. Maintained by `dev-code-review`.

```markdown
# Reviews Index

> Maintained by dev-code-review. Do not edit manually.
> Last updated: {ISO timestamp}

## Statistics
| Metric | Count |
|--------|-------|
| Total reviews | 0 |
| Approved | 0 |
| Approved with warnings | 0 |
| Changes required | 0 |
| Rejected | 0 |

## Reviews
| ID | Plan | Requirement | Verdict | Critical | High | Warning | Info | Date |
|----|------|-------------|---------|----------|------|---------|------|------|
```
