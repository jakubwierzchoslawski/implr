# Requirements Card

> AUTO-GENERATED from docs/implr/schemas/requirement-schema.md + docs/implr/config/DEV-STANDARDS.md by /implr-init.
> Do not edit by hand — run `/implr-init --refresh-card` to regenerate.
> Read by: requirements-domain-worker.
> Full schema (with examples) lives in requirement-schema.md.
> Full standards live in DEV-STANDARDS.md.

## Frontmatter — required fields (orchestrator fills `req_id`)
slug · title · type (functional | non-functional)
status: draft · complexity: XS|S|M|L|XL · tdd_required (derived)
source_docs[] · dependencies[{id, reason}] · created_at · updated_at

## Complexity → tdd_required
XS, S → false   |   M, L, XL → true (overridable per-requirement)
Effective threshold per project: {{TDD_THRESHOLD}} (everything at or above is TDD)

## Non-functional additions (when type = non-functional)
nfr_category: Performance | Security | Scalability | Reliability | Maintainability | Usability | Compliance | Observability
Body MUST include: `### Measurable Target` (quantified), `### Verification Method`, `### Category Rationale`

## Section order (canonical)
Frontmatter → `# {req_id} — {Title}` → `## Domain Context` → `## Summary` →
`## Detailed Description` → `## Desired Outcome` → `## Acceptance Criteria` →
`[## Acceptance Notes]` → `## Out of Scope` → `[## Open Questions]` →
`## Data Models` → `## Process Sequence` → `## Subtasks` →
`[## NFR-Specific Fields]` (only when type=non-functional) →
`## Source Document References`

## Optional sections — OMIT entirely when empty
`## Acceptance Notes` · `## Open Questions`
`## Data Models` — emit `N/A` OR omit
`## Process Sequence` — emit `N/A` OR omit

## Quality gate (fail the requirement if any miss)
- Testable Desired Outcome
- ≥ 2 independently verifiable ACs
- ≥ 1 subtask
- ≥ 1 source doc referenced
- NFRs: quantified Measurable Target with metric + value + conditions
- ≥ 1 Out of Scope entry
- complexity + tdd_required set; dependencies populated with reasons
- Deferred contradictions → Open Questions; resolved contradictions → authoritative content (never Open Questions)

## NFR baselines (apply when deriving NFRs from synthesis)
Security: validate at boundary; never log secrets / tokens / PII / payment data; parameterised queries only; auth required by default on endpoints; rate-limit public mutation endpoints; bcrypt/argon2 cost ≥ 10; no stack traces to clients; verify resource ownership (IDOR).
Performance: state quantified p50/p95/p99 targets when present in source; otherwise mark for human input as an Open Question.
Testing: TDD enforced when tdd_required=true. Unit tests for services/validators/transformers; integration tests for repos/endpoints; E2E only on critical journeys.

## Tone
BA briefing a dev team: active voice, specific, testable, neutral on implementation,
always traceable to a source document.
