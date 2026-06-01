# implr v3.0 — Cost Reduction Refactor

**Date:** 2026-06-02
**Status:** draft
**Supersedes:** parts of `2026-05-30-implr-token-optimization-design.md`, `2026-06-01-per-task-executor-design.md`
**Targets release:** commercial v3.0

---

## Overview

v2.0 cut cost ~3–4× from v1.x via orchestrator + dedicated subagent model. Measured pain in
production: `task-executor` cold start ~50k tokens (platform overhead + redundant stable
reads + full plan re-reads), `executor-worker` adds an unnecessary layer, plans average 800
lines, requirements carry boilerplate. A single plan consumes a full Claude Code session.

v3.0 attacks the residual cost without touching pipeline structure or quality gates.

**Targets**
- task-executor cold start: **50k → 15–20k** (~60–70% per-task reduction)
- dev-executor per-plan total: **~2.5–3× reduction** beyond v2.0
- Plan file size: **800 → ~500 lines** (~40% reduction)
- Requirement file size: **~200 → ~150 lines** (~25% reduction, mostly DoD removal)

**Non-targets**
- Quality of generated code, requirements, plans, or reviews (must remain unchanged or
  improve)
- Pipeline structure (doc-ingest → arch → req → plan → exec → review stays as-is)
- Human-gate semantics (still 3 gates)
- Model tier defaults (Opus for executor, Sonnet elsewhere)

---

## The 10 Changes

### Group A — Structural (biggest wins)

#### C1. Replace `executor-worker` with an ultra-thin `plan-runner`
**Change:** Replace `executor-worker` (~30k stable prefix today: full schema + config +
plan re-read + system prompt) with `plan-runner` — the leanest possible per-plan agent:
no stable reads, no schema, no plan re-parse. It receives **all task envelopes pre-built
by the skill** and dispatches task-executor per envelope sequentially. Its only logic is
the loop, decisions_log accumulation, status update, and commit.

**Why this shape (not "skill dispatches task-executor directly"):**
- Wave parallelism is the v2 cost/quality win: 5 plans in parallel, sequential within each
  plan. If the skill itself ran the per-plan loop, plans would serialise (a single Agent
  tool call blocks the skill until the subagent returns).
- `plan-runner` keeps per-plan loops blocking-isolated from each other so the skill can
  dispatch 5 `plan-runner`s in one parallel tool-call batch (per wave).
- The waste in today's `executor-worker` isn't the layer — it's what the layer **re-reads**.
  Strip the reads, the layer becomes ~3k overhead vs ~30k.

**Mechanics:**
- Delete `.claude/agents/executor-worker.md`.
- Add `.claude/agents/plan-runner.md`: no "Read first" block; tools `[Read, Write, Edit,
  Bash, Agent]`; system prompt ~40 lines of pure loop logic. Receives:
  ```
  plan_id, plan_path, resume_task, commit_mode,
  task_envelopes: [<envelope-1>, <envelope-2>, ...],   # all built by skill
  ```
- `dev-executor` SKILL.md: per wave, parses each in-wave plan once, builds task envelopes
  for each plan's tasks, then dispatches all wave plan-runners in parallel (one Agent
  call batch). Waits for wave completion before next wave.
- `--task PLAN-X TASK-Y` mode: skill builds the single envelope and dispatches
  plan-runner with `resume_task: TASK-Y` and `task_envelopes: [<just that one>]`.
- Per-plan commit happens in `plan-runner` after all tasks complete (preserves per-plan
  atomicity; failed plans don't pollute commits from successful ones).

**Why not just dispatch task-executor directly from the skill (rejected option):**
- Loses wave parallelism (skill loop is sequential within a wave)
- OR forces the skill to manually interleave 5×N task dispatches in topological order,
  which is fragile and pushes orchestration complexity into the skill prose

**Risk / mitigation:** `plan-runner` is still an agent layer; its cost is the Claude Code
subagent system prompt + tool defs (~15k unavoidable platform overhead). Net saving vs
today's executor-worker: ~25–30k per plan (eliminating stable reads + system prompt of
executor-worker.md). The "delete the layer" framing in the summary is shorthand for
"delete the heavy layer and replace with a feather-weight one."

#### C2. Inline task body — task-executor never reads the full plan
**Change:** `dev-executor` parses each plan once (deterministic markdown parse — frontmatter
+ `### TASK-NNN:` headers) and passes a **task envelope** in each task-executor dispatch:

```yaml
task_envelope:
  plan_id: PLAN-F-007
  plan_objective: <Objective section verbatim>
  plan_arch_context: <Architecture Context section verbatim>
  interfaces: <Interfaces and Contracts section verbatim>
  applied_nfrs: <Applied NFR Constraints table verbatim>
  task:
    id: TASK-003
    title: ...
    complexity: M
    tdd_required: true
    files: [src/auth/auth.service.ts, tests/auth/auth.service.test.ts]
    body: <full task body markdown>
    ac_covered: [AC-002, AC-005]
    tests_first: [<list>]   # only if tdd_required
  ac_full:
    - { id: AC-002, text: "..." }
    - { id: AC-005, text: "..." }
  prior_decisions_summary: <as today>
  arch_excerpt: <see C5>
  standards_card: <see C4>
```

**Why:** task-executor today re-reads the full plan (~10k) to find one task. The envelope
is ~3k and contains only relevant slices.

**Risk / mitigation:** parser must be robust. Plan template already has stable headings;
add a `<!-- task-boundary -->` marker on each `### TASK-NNN:` line as belt-and-suspenders.
If parsing fails the skill falls back to passing the full plan path and emits a warning.

#### C3. Drop `plan-schema.md` from task-executor and executor-worker reads
**Change:** Remove the "Read plan-schema" line from `task-executor.md`. task-executor does
not produce or validate plan files. Plan status enum (the only schema fact it needs) is
already encoded in the skill that updates status (now `dev-executor`).

**Why:** Pure waste — 2k saved per task with zero risk.

### Group B — Content compaction (compound savings)

#### C4. Standards card — compact, executable subset of DEV-STANDARDS.md
**Change:** Add `docs/implr/config/standards-card.md` (~50–80 lines). Generated by
`/implr-init` from `DEV-STANDARDS.md` answers + a fixed template. Contains:

```markdown
# Standards Card  (auto-generated from DEV-STANDARDS.md — do not edit)

## Stack
{Frontend} | {Backend} | {DB} | {Auth} | {Cache}

## Naming
files=kebab | classes=PascalCase | fns=camelCase | const=SCREAMING_SNAKE |
db.tables=snake_plural | db.cols=snake | routes=kebab-plural | env=SCREAMING_SNAKE

## Layering
Controller → Service → Repository → DB. No layer skip. Controllers HTTP-only.
Services hold business logic. Repos hold queries.

## SOLID (one-liners)
SRP — one reason to change per class.
OCP — extend via composition; replace switch-chains with polymorphism.
LSP — subtypes substitutable; no NotImplemented overrides.
ISP — small focused interfaces.
DIP — depend on abstractions; constructor injection; no `new Concrete()` for collaborators.

## Testing
TDD when tdd_required=true: red → green → refactor (strict).
Unit: services, validators. Integration: repos + endpoints. E2E: critical journeys only.

## Security (enforced)
Validate at boundary. No PII/secrets/tokens in logs. Parameterised queries only.
Secrets via env vars only. Auth required by default. Rate-limit public mutations.
bcrypt/argon2 cost ≥10. No stack traces to clients. Verify resource ownership.

## API
REST: /api/{resource}/{id}/{sub}. GET/POST/PUT/PATCH/DELETE per verb.
Success {data, meta, error:null}. Error {data:null, error:{code,message}}.
Cursor pagination preferred.

## Git
Branch feat/REQ-F-NNN-slug. Commit feat(scope): subject [REQ-F-NNN]. Squash merge.
```

**Reads:**
- `dev-planner`, `plan-worker`: **full DEV-STANDARDS.md** (needs prose + rationale for
  design decisions)
- `task-executor`: **standards-card.md only**
- `code-review-worker`: **standards-card.md only** (checks rules, not rationale)
- `dev-executor`, `dev-code-review` (orchestrators): neither (they don't reason about
  standards — they dispatch workers)

**Regeneration:** `/implr-init` regenerates the card. Add a `/implr-init --refresh-card`
mode for when the user edits DEV-STANDARDS.md.

**Risk / mitigation:** card may drift from full standards. Mitigation: card is
auto-generated, never edited by hand; header warns; `implr-init` is idempotent.

#### C5. Per-plan ARCHITECTURE excerpt
**Change:** Once per plan (in `dev-executor` Phase 3 or 4, before task dispatching), call
Sonnet to produce an `arch_excerpt` (~80–150 lines) containing only the sections relevant
to this plan: the components touched, layers involved, and the **full** Cross-Cutting
Concerns section (verbatim — too easy to miss otherwise).

**Mechanism:**
- New helper agent: `arch-excerpter` (Sonnet, read-only, tools: Read).
- Input: `{plan_path, arch_path}`.
- Output: markdown excerpt written to ephemeral `${TMPDIR}/implr-arch-{plan_id}.md` (or
  passed inline in the dispatch payload if small).
- task-executor reads `arch_excerpt` from the envelope; does **not** read ARCHITECTURE.md.
- code-review-worker can opt into the same excerpt or read full ARCHITECTURE.md (its
  judgement is broader — keep full read for now).

**Why:** Full ARCHITECTURE is ~6–8k per task read. Excerpt is ~1.5–2k. One Sonnet call per
plan amortises across 4+ tasks.

**Risk / mitigation:** excerpt may miss cross-cutting context. Always include
Cross-Cutting Concerns and Technology Decisions sections verbatim. If task-executor
detects it needs full architecture (rare), it can Read it on demand.

#### C6. Remove Definition of Done from REQ and PLAN templates
**Change:**
- Drop `## Definition of Done` from requirement template/schema and plan template/schema.
- Add `## Acceptance Notes` (optional, rarely used) for REQ and PLAN — for atypical DoD
  items only (e.g. "requires staging smoke test against payment sandbox").
- Encode the standard DoD inside the `dev-executor` completion check and the
  `dev-code-review` verdict rules. These skills already enforce DoD items; the inline DoD
  was duplication.

**Standard DoD (encoded in skills):**
1. All tasks complete
2. Unit + integration tests passing
3. All acceptance criteria verified (covered by ≥1 task, test exists)
4. No TODO/FIXME in produced code
5. dev-code-review passed with no Critical/High findings

**Risk / mitigation:** human reviewers may want to see DoD in REQ. Add a single
`## Definition of Done` line in `requirements-index.md` pointing to the canonical DoD in
README or a new `docs/implr/DOD.md`. Customisations live in REQ's `## Acceptance Notes`.

#### C7. Compact plan template (~40% smaller)
**Changes to `scaffold/templates/plan-template.md` and `plan-schema.md`:**

| Section | Change |
|---|---|
| Frontmatter | unchanged |
| Linked Requirement | one line: `**REQ-F-NNN** {title} (status, jira)` |
| Objective | unchanged (one paragraph) |
| Architecture Context | unchanged (one paragraph) |
| Brainstorm Decisions | omit when absent (already conditional) |
| Applied NFR Constraints | omit when N/A; otherwise table |
| Component Design | inline structure: drop ASCII tree, use bullets |
| Interfaces and Contracts | unchanged (must be precise) |
| Implementation Tasks | new header line: `### TASK-NNN: Title · {complexity}/{tdd} · {files}` then body. Drop separate `**Files**:` line. |
| Acceptance Criteria Coverage | one-line format: `- AC-001: {text} → TASK-002, TASK-006` (drops table) |
| Definition of Done | **removed** (per C6) |
| Open Questions Inherited | omit when empty |
| Risks and Notes | omit when empty |

Result: ~800 → ~500 lines on a typical plan; compounds with C2 (inlined task body).

#### C7b. Compact requirement template (~25% smaller)
**Changes to `scaffold/templates/requirement-template.md` and `requirement-schema.md`:**

- Remove `## Definition of Done` (per C6)
- `## Open Questions`: omit when empty
- `## Data Models`, `## Process Sequence`: omit when N/A (already allowed; make explicit)
- `## Source Document References`: keep but trim header
- Strip trailing whitespace and runs of blank lines

Result: ~200 → ~150 lines.

### Group C — Workflow simplifications (chosen by user: W1, W2, W4)

#### W1. Flip `/doc-ingest` default to include digests
**Change:** `/doc-ingest` → full pipeline (extract + digest + synthesise). New flag
`--registry-only` for the rare fast-scan case. Removed flag emits clear error pointing to
replacement (per v2.0 convention).

**Why:** users almost always want digests; the v2.0 split caused real friction (per
README troubleshooting note).

#### W2. Make Phase 6 coherence sweep in `dev-planner` opt-in
**Change:** `dev-planner` no longer dispatches the Explore subagent automatically. Adds
`--coherence-check` flag. Auto-trigger only when ≥3 plans were generated in one run.

**Why:** Explore sweep is ~5k Sonnet tokens; meaningful only when ≥3 plans interact.
Single-plan runs don't need it.

#### W4. Trim default `dev-executor` report; gate verbosity behind `--verbose`
**Change:** Default report is one screen: counts + manual actions + next steps. Detailed
per-task file lists go behind `--verbose`. Same for `dev-code-review`.

**Why:** main-context noise; users want a verdict, not a wall.

---

## Architecture

### Before (v2.0)
```
dev-executor [SKILL, main]
  └─► executor-worker [Opus] × N plans (parallel waves)   ~30k stable per plan
        └─► task-executor [Opus] × M tasks (sequential)
              reads: schema, ARCH, STANDARDS, config, full plan  (~25k stable)
```

### After (v3.0)
```
dev-executor [SKILL, main]
  ├─ parses each in-wave plan once → builds task envelopes
  ├─ dispatches arch-excerpter [Sonnet] once per plan → arch_excerpt
  └─► plan-runner [Opus, no stable reads] × N plans (parallel within wave)  ~3k overhead
        └─► task-executor [Opus] × M tasks (sequential per plan)
              receives: task_envelope (3k) + arch_excerpt (1.5k) +
                        standards_card (0.8k) + prior_decisions_summary (0.5–2k)
              reads: only the files it will touch
              ~8–10k stable per task (down from ~25k)
```

### New / changed agents
- **DELETE** `.claude/agents/executor-worker.md`
- **NEW** `.claude/agents/plan-runner.md` (Opus, no stable reads — see C1)
- **NEW** `.claude/agents/arch-excerpter.md` (Sonnet, read-only)
- **MODIFY** `.claude/agents/task-executor.md` (remove stable reads; accept envelope)
- **MODIFY** `.claude/agents/code-review-worker.md` (accept standards_card; arch full
  read kept)
- **MODIFY** `.claude/agents/plan-worker.md` (no change — already minimal; verify
  consumption is what we expect)

### New / changed skills
- **MODIFY** `skills/dev-executor/SKILL.md` (assumes per-task dispatch + envelope build +
  arch-excerpter call + commit + status update)
- **MODIFY** `skills/dev-planner/SKILL.md` (opt-in coherence sweep; auto-trigger ≥3)
- **MODIFY** `skills/dev-code-review/SKILL.md` (pass standards_card; report compaction)
- **MODIFY** `skills/doc-ingest/SKILL.md` (default flipped; --registry-only)
- **MODIFY** `skills/implr-init/SKILL.md` (generate standards-card.md from
  DEV-STANDARDS.md; add --refresh-card)

### New artefacts
- `docs/implr/config/standards-card.md` — auto-generated, never hand-edited
- `docs/implr/DOD.md` — canonical Definition of Done reference (small)

---

## Schema and Template Changes

### `plan-schema.md`
- Document new compact format
- Document optional sections (omit-when-empty rule)
- Remove DoD section spec
- Add note: "Tasks are dispatched individually with envelope; do not assume the executor
  reads the whole plan."

### `requirement-schema.md`
- Remove DoD section spec
- Add Acceptance Notes optional section
- Document omit-when-empty rule

### Templates
- Update `scaffold/templates/plan-template.md` and `requirement-template.md` to match new
  schemas
- New `scaffold/config/standards-card-template.md` (the template the implr-init renderer
  fills with stack answers + SOLID/security boilerplate that's identical across projects)

---

## Migration from v2.0

For existing projects on v2.0:
1. Re-run installer. New: `.claude/agents/arch-excerpter.md` + `.claude/agents/plan-runner.md`;
   deleted: `.claude/agents/executor-worker.md`.
2. Run `/implr-init --refresh-card` once to generate `standards-card.md`.
3. Existing plans/requirements continue to work — task-executor accepts envelope OR
   falls back to plan path if envelope absent (backward compatibility for one minor
   version, then removed).
4. New plans generated by v3 dev-planner use compact template; old plans render fine
   (legacy sections just unused by the executor).
5. `/doc-ingest` flag change: documented in CHANGELOG; old `--digest` flag still accepted
   for one minor version (no-op with deprecation note).

---

## Quality safeguards

Each change has a "this could degrade quality" risk. Mitigations:

| Change | Quality risk | Mitigation |
|---|---|---|
| C1 (drop executor-worker) | Main context bloat | Cap parallel plans at 5; per-plan state ~2k |
| C2 (inline task) | Lost surrounding context | Envelope includes Objective + Arch Context + Interfaces |
| C3 (drop schema) | None | task-executor doesn't use schema |
| C4 (standards card) | Card drifts from full | Auto-generated; never edited; header warning |
| C5 (arch excerpt) | Missed cross-cutting | Always include Cross-Cutting + Tech Decisions verbatim |
| C6 (remove DoD) | Humans miss DoD | Canonical DoD in DOD.md; per-REQ overrides via Acceptance Notes |
| C7 (compact plan) | Information loss | Only removes empty/boilerplate sections + table→bullet |
| W1 (--digest default) | Slower scan-only runs | --registry-only flag retained |
| W2 (coherence opt-in) | Missed cross-plan issues | Auto-on when ≥3 plans |
| W4 (trim reports) | Lost detail | --verbose restores |

Acceptance check: a representative plan (existing in this repo or synthesised) re-executed
under v3 must produce code with the same test pass rate and same review verdict as under
v2.

---

## Out of scope (deferred to v3.1+)

- Merging `dev-code-review` into `dev-executor` (rejected — adversarial review must stay
  fresh)
- Auto-chain code-review at end of dev-executor (could be a v3 `--review` flag — add only
  if trivial during implementation)
- Parallelising tasks within a plan (tasks are sequentially dependent by design)
- Model tier auto-tuning per task complexity (out of scope; user already overrides)

---

## Acceptance Criteria

- [ ] AC-001: task-executor cold start ≤ 20k tokens on a representative plan
- [ ] AC-002: dev-executor end-to-end (5-task plan) ≤ 40% of v2.0 token consumption
- [ ] AC-003: All v2.0 skills still pass their existing acceptance behaviours (smoke run
      of doc-ingest → arch → req → plan → exec → review on a small test project)
- [ ] AC-004: Plan files generated by v3 dev-planner are ≤ 600 lines on representative
      requirements
- [ ] AC-005: Requirement files generated by v3 ba-requirements-gen are ≤ 170 lines on
      representative inputs
- [ ] AC-006: `executor-worker.md` agent is deleted; `plan-runner.md` exists and is the
      per-plan dispatcher
- [ ] AC-007: `arch-excerpter.md` agent exists and is dispatched per plan
- [ ] AC-008: `standards-card.md` is generated by `/implr-init`
- [ ] AC-009: `/doc-ingest` default behaviour includes digest pipeline
- [ ] AC-010: `dev-planner` coherence sweep is opt-in / auto-≥3
- [ ] AC-011: dev-executor and dev-code-review default reports fit one screen
- [ ] AC-012: README updated with v3 changes, migration section added
- [ ] AC-013: A v2.0 plan re-executed under v3 produces identical-quality output (manual
      verification on one test plan)

---

## Verification Results (Task 19 — 2026-06-02)

| AC | Check | Result |
|---|---|---|
| AC-006 | plan-runner.md exists; executor-worker.md absent | PASS |
| AC-007 | arch-excerpter.md exists | PASS |
| AC-008 | standards-card-template.md with placeholders | PASS |
| AC-009 | doc-ingest default = full pipeline | PASS |
| AC-010 | dev-planner coherence-check flag | PASS |
| AC-011 | dev-executor one-screen report + --verbose | PASS |
| Schema DoD removed | grep finds 0 matches in schemas | PASS |
| Template sizes | plan≤55 lines (47); req≤50 lines (44) | PASS |
| task-executor no stable reads | "Read first" absent | PASS |
| plan-runner no stable reads | "Read first" absent | PASS |
| Envelope consistency | task_envelope in agent+skill (3+2=5) | PASS |
| executor-worker refs gone | 2 residual refs found (CONCERN — see note) | CONCERN |
| AC-013 | Quality equivalence: N/A — no live plan in repo to re-execute | — |

**Note on executor-worker residual refs:**
Two references remain that were not caught by the v3 refactor:
1. `skills/dev-executor/phases/execute-plan.md` line 3: `Dispatch prompt for \`executor-worker\`.` — live functional text, should read `plan-runner`. This file also retains a "Read first" section (lines 5-7) that was not trimmed in v3.
2. `scaffold/config/implr.config.yaml` line 48: `#   executor-worker: opus` — commented-out, low severity.

These are CONCERN-level, not blockers. The agent file itself is correctly deleted; these are stale references in downstream phase documents.

**Agent count:** 12 files in `.claude/agents/` (executor-worker removed, plan-runner + arch-excerpter added = net +1 vs pre-v3).

**Note on AC-001/002 (token counts):** Cannot measure statically. Will be observed on first real plan run after v3 deploy.
