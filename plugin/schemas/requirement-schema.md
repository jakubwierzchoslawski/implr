# Requirement Schema

Canonical structure for functional (REQ-F) and non-functional (REQ-N) requirements.
Produced by `ba-requirements-gen`. Consumed by `dev-planner`, `dev-code-review`, and
(future) `ba-jira-populate`.

Both types share the same base. NFRs add four fields. The Jira block is present on all
requirements but left mostly blank until `ba-jira-populate` runs.

---

## Functional Requirement — full structure

```markdown
---
req_id: REQ-F-001
slug: user-password-reset
title: User Password Reset
type: functional
status: draft                    # draft | under-review | approved | rejected | superseded
complexity: M                    # XS | S | M | L | XL
tdd_required: true               # derived from complexity (M/L/XL = true), overridable
source_docs:
  - auth-flow.md
dependencies:
  - { id: REQ-F-002, reason: "User entity must exist before reset can target a user" }
  - { id: REQ-N-001, reason: "Reset endpoint must meet the latency NFR" }
superseded_by:                   # REQ-F-NNN if status is superseded, else blank
jira:
  id:                            # filled by ba-jira-populate (e.g. STOK-142)
  issue_type: Story              # Epic | Story | Task | Bug
  epic_link:                     # REQ id of parent epic, or blank
  priority: Medium               # Critical | High | Medium | Low
  labels: [backend, auth]
  story_points:                  # blank until estimated
  components: [authentication]
created_at: {ISO timestamp}
updated_at: {ISO timestamp}
---

# REQ-F-001 — User Password Reset

## Domain Context
The business domain or system area this requirement belongs to.

## Summary
One or two sentences. The highest-level statement of what the system must do.

## Detailed Description
Full BA narrative. The business need, who is affected, conditions to understand, references to
source documents (e.g. "As described in auth-flow.md §3").

## Desired Outcome
Success from the user/stakeholder perspective.

## Acceptance Criteria
Independently testable statements.

- [ ] AC-001: {Condition} — {Expected result}
- [ ] AC-002: {Condition} — {Expected result}

## Acceptance Notes
Optional. Atypical completion requirements beyond the canonical DoD in docs/implr/DOD.md.
Omit section entirely when empty.

## Out of Scope
- {Explicit exclusion}

## Open Questions
| # | Question | Source of Ambiguity | Raised | Resolved |
|---|----------|--------------------|--------|----------|
| 1 | {Question} | {Contradiction or gap, with doc references and approx lines} | {date} | ☐ |

Resolved column: `☐` unresolved, or `✅ {date}: {decision}` once answered.

## Data Models
```
Entity: User
  - id: UUID
  - email: string (unique)
```
If none: `N/A`

## Process Sequence
1. {Actor} {action}
2. {Actor} {action}

If none: `N/A`

## Subtasks
Developer-level tasks with complexity each.

- [ ] ST-001: {Task} — complexity: S
- [ ] ST-002: {Task} — complexity: M

## Source Document References
| Document | Relevant Section | Contribution |
|----------|-----------------|-------------|
| auth-flow.md | §3 Reset Flow | Defines token expiry and email step |
```

### Optional-sections rule

`dev-planner` and `ba-requirements-gen` MUST omit these sections entirely when they have no
content: `## Acceptance Notes`, `## Open Questions`. For `## Data Models` and
`## Process Sequence`: emit a single `N/A` line OR omit the section entirely — either is valid.

---

## Non-Functional Requirement — additional fields

NFR frontmatter adds `nfr_category`. NFR body adds a `## NFR-Specific Fields` section before
Source Document References.

```markdown
---
req_id: REQ-N-001
type: non-functional
nfr_category: Performance        # Performance | Security | Scalability | Reliability |
                                 # Maintainability | Usability | Compliance | Observability
# ... all other base fields identical ...
---
```

```markdown
## NFR-Specific Fields

### Measurable Target
Quantified, with metric, value, and conditions.
Example: "p99 API response time < 200ms under 1,000 concurrent users on reference hardware"

### Verification Method
- Method: Load test | Penetration test | Code review | Static analysis | Audit | Manual test | Automated test | Chaos engineering
- Tool/Process: {specific tool or suite}
- Frequency: One-time at launch | Per release | Continuous CI | Annual audit
- Owner: QA | Security | DevOps | External auditor

### Category Rationale
Why this NFR category was assigned and how it relates to the business context.
```

---

## Field Reference

### complexity → tdd_required

| Complexity | Meaning | tdd_required |
|------------|---------|--------------|
| XS | Trivial — config, copy, simple mapping | false |
| S | Simple — single endpoint, basic CRUD | false |
| M | Moderate — branching logic, external calls | true |
| L | Complex — cross-service, stateful flows | true |
| XL | High risk — security-critical, migration, distributed | true |

The threshold is set by `default_tdd_threshold` in `implr.config.yaml` (default M).
A requirement's `complexity` is derived by aggregating subtask complexities (highest dominates,
with multiple M's escalating to L).

### dependencies
List of objects `{ id, reason }`. A dependency means the referenced requirement must be
implemented first, shares data models that must align, or (for NFRs) applies as a constraint.
`ba-requirements-gen` populates these by detecting shared entities and cross-references; humans
may adjust.

### status lifecycle
```
draft → under-review → approved
                     ↘ rejected
approved → superseded (superseded_by points to replacement)
```
Claude creates requirements as `draft`. Only humans promote status.
`dev-planner` and `ba-jira-populate` only process `approved` requirements.

---

## ID Conventions

| Type | Prefix | Example |
|------|--------|---------|
| Functional | REQ-F- | REQ-F-001 |
| Non-Functional | REQ-N- | REQ-N-001 |

Sequential, zero-padded to 3 digits, never reused.
