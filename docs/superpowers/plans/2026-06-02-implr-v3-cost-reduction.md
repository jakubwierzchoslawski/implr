# implr v3.0 Cost-Reduction Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut implr's per-plan token cost ~2.5–3× beyond v2.0 by eliminating redundant
stable reads, replacing the heavy `executor-worker` agent with a feather-weight
`plan-runner`, packaging task context as inline envelopes, and compacting templates —
without changing pipeline structure, human gates, or output quality.

**Architecture:** All changes are to markdown skill prompts, agent prompts, schemas, and
templates. No application code exists in this repo — the plugin IS prompts. Implementation
order moves from leaves (templates, schemas) inward (new agents) to the orchestration
core (`dev-executor` SKILL.md), so each layer can be verified before the next consumes it.

**Tech Stack:** Markdown skill/agent prompts; PowerShell/Bash/Batch installer scripts;
YAML config; no runtime code.

**Source spec:** `docs/superpowers/specs/2026-06-02-implr-v3-cost-reduction-design.md`

**Verification model:** This plugin has no unit tests. Each task's verification is one of:
(a) re-read the modified file and confirm structural assertions; (b) run installer
end-to-end against a scratch directory; (c) end-of-plan smoke run of the full pipeline
on a representative input (Task 19). Steps below specify which.

---

## File Structure

### New files
| Path | Purpose |
|---|---|
| `.claude/agents/plan-runner.md` | Replaces executor-worker; per-plan dispatcher with NO stable reads |
| `.claude/agents/arch-excerpter.md` | Sonnet; once per plan; produces arch_excerpt for envelope |
| `scaffold/templates/standards-card-template.md` | Skeleton for the auto-generated standards card |
| `scaffold/seeds/DOD.md` | Canonical Definition of Done (seeded once to project) |

### Modified files
| Path | Change |
|---|---|
| `.claude/agents/task-executor.md` | Drop stable reads (schema, ARCH, STANDARDS, config); accept envelope inputs |
| `.claude/agents/code-review-worker.md` | Read standards-card instead of full DEV-STANDARDS |
| `skills/dev-executor/SKILL.md` | Per-plan parse, envelope build, arch-excerpter dispatch, plan-runner dispatch, concise report |
| `skills/dev-planner/SKILL.md` | Coherence sweep opt-in / auto-≥3; remove DoD requirement from generated plans |
| `skills/dev-code-review/SKILL.md` | Pass standards_card_path to worker; concise report |
| `skills/doc-ingest/SKILL.md` | Default flipped to full; `--registry-only` flag added; `--digest` deprecated no-op |
| `skills/implr-init/SKILL.md` | Generate `standards-card.md`; add `--refresh-card` |
| `scaffold/schemas/plan-schema.md` | Remove DoD; document optional sections; document task envelope |
| `scaffold/schemas/requirement-schema.md` | Remove DoD; add Acceptance Notes; optional sections |
| `scaffold/templates/plan-template.md` | Compact format (~40% smaller) |
| `scaffold/templates/requirement-template.md` | Compact format; no DoD |
| `install.ps1` | Seed `DOD.md`; ensure new templates/agents copy |
| `install.sh` | Same |
| `install.bat` | Same |
| `README.md` | v3 changes, migration section, new agents list |
| `docs/WORKFLOW.md` | New dispatch chart; plan-runner; new artefacts |

### Deleted files
| Path | Reason |
|---|---|
| `.claude/agents/executor-worker.md` | Replaced by `plan-runner.md` |

---

## Task 1: Update plan-schema.md (C6, C7)

**Files:**
- Modify: `scaffold/schemas/plan-schema.md`

- [ ] **Step 1: Read current schema**

Read `scaffold/schemas/plan-schema.md` end-to-end so you understand current structure before editing.

- [ ] **Step 2: Remove the Definition of Done section from the template block**

In the markdown code block under "Plan — full structure", delete these lines:

```
## Definition of Done
Plan-specific DoD, derived from the requirement DoD and enriched with implementation specifics.

- [ ] All tasks complete
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] All acceptance criteria verified
- [ ] No TODO/FIXME in produced code
- [ ] dev-code-review run and Critical/High findings resolved
```

Replace with:

```
## Acceptance Notes
Optional. List atypical completion requirements that supplement the canonical DoD in
docs/implr/DOD.md (e.g. "requires staging smoke test against payment sandbox"). Omit when empty.
```

- [ ] **Step 3: Convert Acceptance Criteria Coverage to compact one-line format**

Replace the existing block:

```
## Acceptance Criteria Coverage
| AC | Description | Covered by |
|----|-------------|-----------|
| AC-001 | {text} | TASK-002, TASK-006 |

Every acceptance criterion in the linked requirement must appear here, covered by at least
one task.
```

With:

```
## Acceptance Criteria Coverage
One line per AC. Every AC in the linked requirement appears here, covered by ≥1 task.

- AC-001: {text} → TASK-002, TASK-006
- AC-002: {text} → TASK-003
```

- [ ] **Step 4: Compact the Implementation Tasks task-header format**

Replace the existing TASK example block:

```
### TASK-001: {Title}
**Complexity**: S | **TDD**: false
**Files**: {paths}

{Description of what to build.}

**Tests to write first (TDD)**: only present when TDD is true for this task.
- {Test case description}

**Acceptance criteria covered**: {AC ids, or "enables AC-00x"}
```

With:

```
### TASK-001: {Title} · {complexity}/{tdd-flag} · {comma-separated files}

{Description of what to build.}

**Tests to write first (TDD)** (only when tdd_required for this task):
- {Test case description}

**AC covered**: AC-001, AC-002
```

Note: `{tdd-flag}` is literal `TDD` when tdd_required=true, literal `no-TDD` otherwise.
Example header: `### TASK-001: Hash password · M/TDD · src/auth/auth.service.ts, tests/auth/auth.service.test.ts`

- [ ] **Step 5: Add the optional-sections rule**

After the closing ``` of the plan structure block, add a new subsection:

```
---

## Optional sections — omit when empty

dev-planner MUST omit these sections when they have no content (do not emit empty headers):
- `## Brainstorm Decisions` — present only when --brainstorm was used
- `## Applied NFR Constraints` — emit `N/A` line instead of empty table, OR omit entire section
- `## Acceptance Notes` — present only when atypical DoD items exist
- `## Open Questions Inherited` — omit when empty
- `## Risks and Notes` — omit when empty

Rationale: every line saved here is read by task-executor envelopes and code-review-worker
on every invocation.
```

- [ ] **Step 6: Add task-envelope dispatch note**

After the optional-sections rule, add:

```
---

## Task dispatch in v3.0

`task-executor` does **not** read this plan file directly. `dev-executor` parses the plan
once and dispatches each task as an inline **task envelope** containing only:
- The frontmatter
- `## Objective`, `## Architecture Context`, `## Interfaces and Contracts`, `## Applied NFR Constraints`
- The single `### TASK-NNN:` block being executed (parsed by the `### TASK-` header)
- The full AC list (resolved from the linked requirement)

Plan authors (dev-planner / plan-worker) MUST keep `### TASK-NNN:` headers parseable:
the literal prefix `### TASK-` followed by a 3-digit zero-padded number and a colon.
```

- [ ] **Step 7: Verify**

Re-read `scaffold/schemas/plan-schema.md`. Confirm:
- No occurrence of the string `## Definition of Done`
- The string `## Acceptance Notes` appears once
- The string `Task dispatch in v3.0` appears
- File line count is reasonable (140–180 lines; was 197)

Run: `wc -l scaffold/schemas/plan-schema.md`
Expected: line count in 140–180 range.

- [ ] **Step 8: Commit**

```bash
git add scaffold/schemas/plan-schema.md
git commit -m "feat(schema): compact plan-schema; remove DoD; add envelope dispatch contract [v3]"
```

---

## Task 2: Update requirement-schema.md (C6, C7b)

**Files:**
- Modify: `scaffold/schemas/requirement-schema.md`

- [ ] **Step 1: Remove DoD from the functional requirement structure block**

In the markdown code block under "Functional Requirement — full structure", delete:

```
## Definition of Done
- [ ] Code implemented and peer-reviewed
- [ ] Unit tests passing (tests first if tdd_required)
- [ ] Integration tests passing
- [ ] All acceptance criteria verified
- [ ] Documentation updated
- [ ] Deployed to staging and smoke-tested
- [ ] Product Owner sign-off
```

Replace with:

```
## Acceptance Notes
Optional. Atypical completion requirements beyond the canonical DoD in docs/implr/DOD.md.
Omit section entirely when empty.
```

- [ ] **Step 2: Add optional-sections rule**

After the requirement structure closing ```, add:

```
---

## Optional sections — omit when empty

ba-requirements-gen MUST omit these sections when they have no content:
- `## Acceptance Notes` — only present when atypical DoD items exist
- `## Open Questions` — omit when no open questions
- `## Data Models` — emit `N/A` line OR omit section
- `## Process Sequence` — emit `N/A` line OR omit section
```

- [ ] **Step 3: Verify**

Run: `grep -n "Definition of Done" scaffold/schemas/requirement-schema.md`
Expected: no matches.

Run: `wc -l scaffold/schemas/requirement-schema.md`
Expected: 150–180 lines (was 183).

- [ ] **Step 4: Commit**

```bash
git add scaffold/schemas/requirement-schema.md
git commit -m "feat(schema): compact requirement-schema; remove DoD; mark optional sections [v3]"
```

---

## Task 3: Update plan-template.md (C7)

**Files:**
- Modify: `scaffold/templates/plan-template.md`

- [ ] **Step 1: Replace the entire file with the compact version**

Overwrite `scaffold/templates/plan-template.md` with:

```markdown
---
plan_id: PLAN-F-000
slug: REPLACE-ME
title: REPLACE ME
linked_requirement: REQ-F-000
type: functional
status: ready
blocked_reason:
complexity: M
tdd_required: true
linked_nfrs: []
dependencies: []
executed_at:
reviewed_at:
review_id:
created_at:
updated_at:
---

# PLAN-F-000 — REPLACE ME

## Linked Requirement
**REQ-F-000** — REPLACE ME (status: approved, jira: )

## Objective

## Architecture Context

## Component Design

### New Components
- {Component} ({path}) — {responsibility}

### Modified Components
| File | Change | Reason |
|------|--------|--------|

### Interfaces and Contracts

## Implementation Tasks

### TASK-001: {title} · S/no-TDD · {files}

{description}

**AC covered**: AC-001

## Acceptance Criteria Coverage

- AC-001: {text} → TASK-001
```

This is the canonical compact template. Sections `## Brainstorm Decisions`,
`## Applied NFR Constraints`, `## Acceptance Notes`, `## Open Questions Inherited`,
`## Risks and Notes` are intentionally absent — they appear only when populated.

- [ ] **Step 2: Verify**

Run: `wc -l scaffold/templates/plan-template.md`
Expected: 35–45 lines (was 66).

Run: `grep -n "Definition of Done" scaffold/templates/plan-template.md`
Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add scaffold/templates/plan-template.md
git commit -m "feat(template): compact plan-template; remove DoD; remove always-empty sections [v3]"
```

---

## Task 4: Update requirement-template.md (C7b)

**Files:**
- Modify: `scaffold/templates/requirement-template.md`

- [ ] **Step 1: Overwrite the template**

Write `scaffold/templates/requirement-template.md`:

```markdown
---
req_id: REQ-F-000
slug: REPLACE-ME
title: REPLACE ME
type: functional
status: draft
complexity: M
tdd_required: true
source_docs: []
dependencies: []
superseded_by:
jira:
  id:
  issue_type: Story
  epic_link:
  priority: Medium
  labels: []
  story_points:
  components: []
created_at:
updated_at:
---

# REQ-F-000 — REPLACE ME

## Domain Context

## Summary

## Detailed Description

## Desired Outcome

## Acceptance Criteria
- [ ] AC-001:

## Subtasks
- [ ] ST-001: — complexity: S

## Source Document References
| Document | Section | Contribution |
|----------|---------|-------------|
```

Sections `## Acceptance Notes`, `## Out of Scope`, `## Open Questions`, `## Data Models`,
`## Process Sequence` are emitted only when populated.

- [ ] **Step 2: Verify**

Run: `wc -l scaffold/templates/requirement-template.md`
Expected: 35–45 lines (was 64).

Run: `grep -n "Definition of Done" scaffold/templates/requirement-template.md`
Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add scaffold/templates/requirement-template.md
git commit -m "feat(template): compact requirement-template; remove DoD [v3]"
```

---

## Task 5: Create canonical DOD seed (C6)

**Files:**
- Create: `scaffold/seeds/DOD.md`

- [ ] **Step 1: Create the DOD seed**

Write `scaffold/seeds/DOD.md`:

```markdown
# Definition of Done

Canonical completion criteria enforced by `dev-executor` (gate to plan `done`) and
`dev-code-review` (gate to verdict `approved` / `approved-with-warnings`).

Individual requirements and plans MAY add atypical items under `## Acceptance Notes`.
This file lists what applies to every plan unless explicitly overridden.

## Per plan

1. All tasks in the plan are complete (`task_status: done` for each).
2. All unit tests for produced code pass.
3. All integration tests for produced code pass.
4. Every acceptance criterion (AC-NNN) in the linked requirement is covered by at least
   one task and verified by at least one passing test.
5. No `TODO` / `FIXME` / `XXX` markers introduced by the implementation.
6. `dev-code-review` produces verdict `approved` or `approved-with-warnings` (no
   Critical / High findings).

## Out of scope of the canonical DoD

These are NOT auto-enforced (require explicit Acceptance Notes per requirement):

- Manual QA sign-off
- Deployment to staging
- Product Owner approval
- Documentation site updates
- External smoke tests

If a requirement needs any of these, list them in its `## Acceptance Notes` section.
```

- [ ] **Step 2: Verify**

Run: `wc -l scaffold/seeds/DOD.md`
Expected: 25–40 lines.

Run: `grep -c "^[0-9]\." scaffold/seeds/DOD.md`
Expected: 6 (the six numbered DoD items).

- [ ] **Step 3: Commit**

```bash
git add scaffold/seeds/DOD.md
git commit -m "feat(seeds): add canonical DOD.md; encodes per-plan completion criteria [v3]"
```

---

## Task 6: Create standards-card template (C4)

**Files:**
- Create: `scaffold/templates/standards-card-template.md`

- [ ] **Step 1: Create the template**

Write `scaffold/templates/standards-card-template.md`:

```markdown
# Standards Card

> AUTO-GENERATED from docs/implr/config/DEV-STANDARDS.md by /implr-init.
> Do not edit by hand — run `/implr-init --refresh-card` to regenerate.
> Read by: task-executor, code-review-worker.
> Full standards (with rationale, optional sections, [FILL IN] hints) live in DEV-STANDARDS.md.

## Stack
Frontend: {{FRONTEND}}
Backend:  {{BACKEND}}
Database: {{DB}}

## Naming
files=kebab-case · classes=PascalCase · fns=camelCase · const=SCREAMING_SNAKE
db.tables=snake_plural · db.cols=snake · routes=kebab-plural · env=SCREAMING_SNAKE

## Layering
Controller → Service → Repository → DB. No layer-skipping.
Controllers: HTTP-only (parse, validate, delegate, respond). Services: business logic.
Repositories: queries only.

## SOLID
SRP — one reason to change per class.
OCP — extend via composition; replace switch-chains with polymorphism / strategy.
LSP — subtypes substitutable; no NotImplemented overrides.
ISP — small focused interfaces; no fat dependencies.
DIP — depend on abstractions; constructor injection; no `new Concrete()` for collaborators.

## Testing
TDD when `tdd_required: true`: red → green → refactor (strict).
Unit: services, validators, transformers. Integration: repos + endpoints. E2E: critical journeys only.
Do not unit-test framework internals or migrations.

## Security (enforced)
- Validate and sanitise external input at the boundary.
- Never log secrets / tokens / PII / payment data.
- Parameterised queries only.
- Secrets only via env vars.
- Auth required by default; opt out explicitly.
- Rate-limit public mutation endpoints.
- bcrypt or argon2 cost ≥ 10.
- No stack traces returned to clients.
- Verify resource ownership on every lookup (prevent IDOR).

## API
REST: `/api/{resource}/{id}/{sub}`. Verbs: GET / POST / PUT / PATCH / DELETE.
Success envelope: `{ "data": ..., "meta": ..., "error": null }`.
Error envelope: `{ "data": null, "error": { "code": "...", "message": "..." } }`.
Cursor pagination preferred for large sets.
Versioning: {{VERSIONING}}

## Git
Branch: `feat/REQ-F-NNN-slug` / `fix/REQ-F-NNN-slug` / `chore/description`.
Commit: `feat(scope): subject [REQ-F-NNN]`.
PR title: `[REQ-F-NNN] {summary}`.
Squash merge.
```

The three placeholders `{{FRONTEND}}`, `{{BACKEND}}`, `{{DB}}`, `{{VERSIONING}}` are
filled by `implr-init` from the user's answers.

- [ ] **Step 2: Verify**

Run: `wc -l scaffold/templates/standards-card-template.md`
Expected: 55–70 lines.

Run: `grep -c "{{" scaffold/templates/standards-card-template.md`
Expected: at least 4 (one per placeholder).

- [ ] **Step 3: Commit**

```bash
git add scaffold/templates/standards-card-template.md
git commit -m "feat(template): add standards-card-template; compact subset for task-executor [v3]"
```

---

## Task 7: Update implr-init SKILL — generate standards-card (C4)

**Files:**
- Modify: `skills/implr-init/SKILL.md`

- [ ] **Step 1: Add `--refresh-card` parameter doc near the top**

Edit `skills/implr-init/SKILL.md`. After the `## Pre-flight` section, BEFORE `## Step 1`,
insert:

```markdown
---

## Parameters

- `/implr-init` — full setup: ask 8 questions, substitute, generate standards-card.
- `/implr-init --refresh-card` — regenerate ONLY `docs/implr/config/standards-card.md`
  from the current DEV-STANDARDS.md (stack values) without re-asking questions or
  touching CLAUDE.md / implr.config.yaml.
```

- [ ] **Step 2: In `--refresh-card` mode, branch early**

After Pre-flight and Parameters, add a new step BEFORE Step 1:

```markdown
---

## Refresh-card-only mode

If invoked as `/implr-init --refresh-card`:
1. Read current values for FRONTEND/BACKEND/DB from `docs/implr/config/DEV-STANDARDS.md`
   §1 Project Stack block (lines after `Frontend:`, `Backend:`, `Database + ORM:`).
2. Read current VERSIONING from §7 line `Versioning:`.
3. Run Step 5 (Generate standards-card) only.
4. Print: `✅ standards-card.md regenerated from DEV-STANDARDS.md`
5. Stop.
```

- [ ] **Step 3: Add Step 5 (Generate standards-card) before Step 4 (Report)**

Find `## Step 4 — Report` and INSERT before it:

```markdown
## Step 5 — Generate standards-card

> Step number sequence is intentional: this step runs whether full init or
> `--refresh-card` was invoked.

Read `docs/implr/templates/standards-card-template.md`. Substitute placeholders:

| Placeholder | Source |
|------------|--------|
| `{{FRONTEND}}` | answer 2a (or DEV-STANDARDS §1 `Frontend:` in refresh-card mode) |
| `{{BACKEND}}` | answer 2b (or §1 `Backend:` in refresh-card mode) |
| `{{DB}}` | answer 2c (or §1 `Database + ORM:` in refresh-card mode) |
| `{{VERSIONING}}` | answer 6 (or §7 `Versioning:` in refresh-card mode) |

Write the substituted content to `docs/implr/config/standards-card.md` (overwrite if
present — this file is auto-managed, never hand-edited).
```

- [ ] **Step 4: Renumber and update Step 4 — Report**

Edit `## Step 4 — Report` (which will visually appear after Step 5 in the file — leave
as is, but update its content) to list standards-card.md among created files. Find:

```
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  CLAUDE.md
```

Replace with:

```
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  docs/implr/config/standards-card.md  (auto-generated; do not hand-edit)
  CLAUDE.md
```

- [ ] **Step 5: Update the description frontmatter**

At the top of the file, replace the `description:` block with:

```yaml
description: >
  Configures the implr workspace after the installer has scaffolded docs/implr/. Asks 8
  setup questions (project name, frontend/backend/db stack, paths, TDD threshold, API
  versioning), substitutes placeholders in implr.config.yaml, DEV-STANDARDS.md, CLAUDE.md,
  and generates docs/implr/config/standards-card.md (compact subset for task-executor and
  code-review-worker). Use --refresh-card to regenerate only standards-card.md from
  current DEV-STANDARDS.md values. Idempotent.
```

- [ ] **Step 6: Verify**

Run: `grep -c "standards-card" skills/implr-init/SKILL.md`
Expected: ≥ 4 (frontmatter, parameter doc, refresh-card step, generate step, report).

Run: `grep -c "refresh-card" skills/implr-init/SKILL.md`
Expected: ≥ 3.

- [ ] **Step 7: Commit**

```bash
git add skills/implr-init/SKILL.md
git commit -m "feat(implr-init): generate standards-card.md; add --refresh-card flag [v3]"
```

---

## Task 8: Create arch-excerpter agent (C5)

**Files:**
- Create: `.claude/agents/arch-excerpter.md`

- [ ] **Step 1: Write the agent definition**

Write `.claude/agents/arch-excerpter.md`:

```markdown
---
name: arch-excerpter
description: Produces a compact, plan-specific excerpt of docs/ARCHITECTURE.md. Returns only the components, layers, and concerns referenced by the named plan, plus the full Cross-Cutting Concerns and Technology Decisions sections verbatim. Read-only. Dispatched once per plan by dev-executor before any task-executor dispatches.
tools: [Read, Grep, Glob]
default_model: sonnet
---

# arch-excerpter

You produce a compact architecture excerpt for one plan. Your output is consumed inline by
`task-executor` dispatches as `arch_excerpt` — task-executor will NOT read ARCHITECTURE.md
itself.

## Read (in this order — cache prefix)

1. `docs/ARCHITECTURE.md`
2. The plan at `{plan_path}` (skim only — you need its Component Design and Architecture
   Context sections).

## Inputs (from dev-executor)

```
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
```

## Work

1. Read the plan's `## Architecture Context` and `## Component Design` sections. List
   every component name, module name, layer, and architectural concept the plan
   references.
2. From `docs/ARCHITECTURE.md`, extract:
   a. The rows of `## Component / Module Map` whose Component matches any name from (1).
   b. Any sections under `## Data Architecture` whose described entities are owned by
      a matched component.
   c. The **entire** `## Cross-Cutting Concerns` section verbatim. Never abbreviate.
   d. The **entire** `## Technology Decisions` table verbatim.
   e. Rows of `## Non-Functional Architecture` whose linked NFR id appears in the plan's
      `linked_nfrs:` frontmatter list.
3. If you cannot match a referenced component to any architecture section, add a
   `> ⚠️ Component '{name}' referenced in plan but not found in ARCHITECTURE.md` line
   under a `## Gaps` heading at the end. Do not invent content.

## Output format

Return your excerpt as a single markdown document. Cap at ~150 lines. Structure:

```markdown
# Architecture Excerpt for {plan_id}

## Components Touched
{table rows from Component/Module Map}

## Data Architecture (relevant)
{relevant entity ownership}

## Cross-Cutting Concerns
{verbatim copy of section}

## Technology Decisions
{verbatim copy of table}

## NFR Constraints (matched to plan)
{matched rows or "none"}

## Gaps
{warnings if any, else omit section}
```

## Return summary (final message)

```
plan_id: PLAN-F-NNN
arch_excerpt_lines: <n>
components_matched: <n>
gaps: <n>
excerpt: |
  <full markdown excerpt body>
```

The `excerpt:` block is the payload `dev-executor` will pass to each `task-executor` as
`arch_excerpt`. Do NOT write the excerpt to disk — return it inline.
```

- [ ] **Step 2: Verify**

Run: `head -5 .claude/agents/arch-excerpter.md`
Expected: starts with `---` and includes `name: arch-excerpter`.

Run: `grep -c "Cross-Cutting" .claude/agents/arch-excerpter.md`
Expected: ≥ 2 (referenced in extraction rules AND in output format).

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/arch-excerpter.md
git commit -m "feat(agent): add arch-excerpter; per-plan Sonnet preprocess of ARCHITECTURE.md [v3]"
```

---

## Task 9: Refactor task-executor (C2, C3, C4, C5)

**Files:**
- Modify: `.claude/agents/task-executor.md`

- [ ] **Step 1: Replace the entire agent file**

Overwrite `.claude/agents/task-executor.md`:

```markdown
---
name: task-executor
description: Implements one task from one plan end-to-end. Receives a task envelope (objective, arch context, interfaces, single task body, AC list) and helper context (arch_excerpt, standards_card, prior_decisions_summary) from plan-runner — does NOT read plan-schema, ARCHITECTURE.md, DEV-STANDARDS.md, the full plan, or config. Enforces TDD when tdd_required=true; applies SOLID; caps Bash output at 80 lines.
tools: [Read, Write, Edit, Bash, Grep, Glob]
default_model: opus
---

# task-executor

You implement exactly one task from one plan. You enforce TDD when `tdd_required: true`.
You apply SOLID. You continue established patterns from `prior_decisions_summary` — do not
reinvent choices already made in earlier tasks.

## You do NOT read

- `docs/implr/schemas/plan-schema.md` — you do not write or validate plans.
- `docs/ARCHITECTURE.md` — the relevant excerpt is provided as `arch_excerpt`.
- `docs/implr/config/DEV-STANDARDS.md` — the executable subset is provided as
  `standards_card`.
- `docs/implr/config/implr.config.yaml` — paths and config you need are in the envelope.
- The full plan file — your single task and the surrounding plan context are in the
  envelope.

Reading any of these wastes tokens. The envelope is authoritative for everything you need
to start. Read source files in `src/` and `tests/` as required to implement the task.

## Inputs (from plan-runner)

```yaml
task_envelope:
  plan_id: PLAN-F-NNN
  plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md   # for git/log reference only; do not read
  plan_objective: |
    <Objective section verbatim>
  plan_arch_context: |
    <Architecture Context section verbatim>
  interfaces: |
    <Interfaces and Contracts section verbatim>
  applied_nfrs: |
    <Applied NFR Constraints section verbatim or "N/A">
  task:
    id: TASK-NNN
    title: <title>
    complexity: XS|S|M|L|XL
    tdd_required: true|false
    files: [<paths>]
    body: |
      <full task description from plan>
    ac_covered: [AC-001, AC-002]
    tests_first: [<list>]   # only present when tdd_required
  ac_full:
    - { id: AC-001, text: "..." }
    - { id: AC-002, text: "..." }
arch_excerpt: |
  <markdown excerpt from arch-excerpter>
standards_card: |
  <contents of docs/implr/config/standards-card.md>
prior_decisions_summary: |
  completed_tasks:
    - task_id: TASK-NNN
      files_created: [...]
      files_modified: [...]
      interfaces_added: [...]
      decisions:
        - "<pattern or choice made, and why>"
      tests_pass: true
  # empty list on first dispatch of a plan
src_path: src
tests_path: tests
test_runner: <project test runner command, e.g. "pytest" or "npm test">
plan_id_for_log: PLAN-F-NNN
```

## Work

1. Read `task_envelope.task` — that is your scope. Read `prior_decisions_summary` and
   commit to continuing every pattern listed (no different DI strategy, no different
   error-handling style, etc.).
2. Read the source files listed in `task.files` BEFORE writing anything. If
   `prior_decisions_summary.completed_tasks` is empty (resume scenario or first task),
   also Grep for patterns in adjacent files to spot established conventions.
3. Cross-check `task.body` against `arch_excerpt` (components and layers) and
   `standards_card` (SOLID, naming, security). Where a tension exists, follow the
   standards_card.
4. If `task.tdd_required` is true:
   a. Write the failing test(s) named in `task.tests_first`. If `tests_first` is empty
      but `tdd_required` is true, derive minimal failing tests from `task.ac_covered`
      via `ac_full`.
   b. Run the test runner with output cap:
      ```
      <test_runner> 2>&1 | tee "${TMPDIR:-/tmp}/implr-test-{plan_id_for_log}-{task.id}.txt" | head -80
      ```
   c. Verify the test fails. If 80 lines is insufficient, Read the full file in `$TMPDIR`.
   d. Implement the minimal code to pass.
   e. Re-run the test runner; verify pass.
   f. Refactor if needed; re-verify.
5. If `tdd_required` is false: implement the change and add smoke tests appropriate to
   complexity.
6. Note any manual action you cannot perform (missing credentials, env-specific config).
   Do not invent secrets.

Do NOT commit. Do NOT update plan status. Do NOT modify the plan file. plan-runner
handles all three.

## Return summary (your one final message)

```yaml
task_id: TASK-NNN
task_status: done | blocked | failed
files_created: [<paths>]
files_modified: [<paths>]
interfaces_added: [<names>]
decisions:
  - "<pattern or choice made, and why — one line>"
tests_added: <n>
tests_pass: true | false
manual_actions:
  - <description if any>
```

List every decision a subsequent task could replicate. If you chose a pattern that isn't
in `prior_decisions_summary`, add it here so the next task can continue it.
```

- [ ] **Step 2: Verify**

Run: `grep -c "Read first" .claude/agents/task-executor.md`
Expected: 0 (the heavy stable-reads block is gone).

Run: `grep -c "task_envelope" .claude/agents/task-executor.md`
Expected: ≥ 3 (in inputs description, work, and possibly description).

Run: `wc -l .claude/agents/task-executor.md`
Expected: 95–125 lines (was 88; slightly grew due to envelope schema but no stable-read content).

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/task-executor.md
git commit -m "feat(agent): refactor task-executor to envelope-only input; drop all stable reads [v3]"
```

---

## Task 10: Create plan-runner, delete executor-worker (C1)

**Files:**
- Create: `.claude/agents/plan-runner.md`
- Delete: `.claude/agents/executor-worker.md`

- [ ] **Step 1: Write plan-runner**

Write `.claude/agents/plan-runner.md`:

```markdown
---
name: plan-runner
description: Per-plan dispatcher. Receives pre-built task envelopes from dev-executor and dispatches one task-executor per envelope sequentially. Accumulates prior_decisions_summary between dispatches. Does NOT parse the plan, read schemas, read ARCHITECTURE.md, or read DEV-STANDARDS.md — all context is in the envelopes. Updates plan status field after all tasks complete; commits if commit_mode=auto.
tools: [Read, Write, Edit, Bash, Agent]
default_model: opus
---

# plan-runner

You orchestrate execution of exactly one plan. You receive everything you need from
`dev-executor` — there are no stable files to read. Your job is the per-plan task loop,
decisions log, status update, and (optional) commit.

## You do NOT read

- `docs/implr/schemas/plan-schema.md` — only the status enum matters and it is encoded below.
- `docs/ARCHITECTURE.md` — already pre-excerpted by dev-executor.
- `docs/implr/config/DEV-STANDARDS.md` — task-executors receive the standards card.
- `docs/implr/config/implr.config.yaml` — pre-resolved values are in your inputs.

Reading any of these wastes tokens. The only file you Read is the plan file at the end
to update its `status:` frontmatter field.

## Inputs (from dev-executor)

```yaml
plan_id: PLAN-F-NNN
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
resume_task: <task-id or empty>
commit_mode: auto | defer
task_envelopes:
  - <envelope-1>     # complete envelope per task-executor's input schema
  - <envelope-2>
  - ...
arch_excerpt: |
  <shared across all envelopes — already inlined into each envelope by dev-executor>
standards_card: |
  <shared across all envelopes — already inlined>
task_executor_model: opus     # resolved by dev-executor from config
```

If `resume_task` is non-empty, skip envelopes whose `task.id` is earlier in the plan
order. Start `decisions_log` empty (filesystem state is the source of truth for skipped
tasks).

## Work

### 1. Dispatch task-executor per envelope, in order

For each envelope (post-resume filtering), dispatch the `task-executor` agent with:

```
<the full envelope, with prior_decisions_summary set as below>
```

The first dispatch sets `prior_decisions_summary.completed_tasks: []`.

After each task-executor returns:

a. Parse its return summary (task_id, task_status, files_created, files_modified,
   interfaces_added, decisions, tests_added, tests_pass, manual_actions).
b. Append a `completed_tasks` entry to the running decisions_log:
   ```
   - task_id: <returned id>
     files_created: <list>
     files_modified: <list>
     interfaces_added: <list>
     decisions: <list>
     tests_pass: <bool>
   ```
c. Update the NEXT envelope's `prior_decisions_summary.completed_tasks` to be the
   accumulated list before dispatching it.
d. **Stop dispatching** if:
   - `task_status: blocked` or `task_status: failed`, OR
   - `tests_pass: false`.
   Record the stopping task_id and reason.

Do NOT update the plan file between dispatches.

### 2. Update plan status

When all envelopes are processed (or on stop condition), Edit `plan_path` to update its
frontmatter `status:` field. Status values:

- All envelopes done AND every `tests_pass: true` → `status: done`
- Any task blocked / failed / `tests_pass: false` → `status: in-progress` (annotate the
  stopping task in a `blocked_reason:` line if blocked)

Also update `executed_at: <ISO timestamp>` in frontmatter.

### 3. Commit (if commit_mode: auto)

```
git add -A
git commit -m "feat(<plan_id>): implement plan tasks"
```

If `commit_mode: defer`: leave changes staged; do not commit.

## Return summary (your one final message)

```yaml
plan_id: PLAN-F-NNN
tasks_completed: <n>
tasks_blocked: <n>
manual_actions_required:
  - <description>
files_created: <n>
files_modified: <n>
tests_added: <n>
tests_pass: true | false
plan_status: done | in-progress | blocked
stopping_task: <task_id or empty>
stopping_reason: <text or empty>
```
```

- [ ] **Step 2: Delete executor-worker**

Run: `rm .claude/agents/executor-worker.md`

- [ ] **Step 3: Verify**

Run: `ls .claude/agents/`
Expected: `executor-worker.md` is absent; `plan-runner.md` is present; `arch-excerpter.md` is present.

Run: `grep -c "default_model: opus" .claude/agents/plan-runner.md`
Expected: 1.

Run: `wc -l .claude/agents/plan-runner.md`
Expected: 100–135 lines (intentionally lean).

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/plan-runner.md .claude/agents/executor-worker.md
git commit -m "feat(agent): replace executor-worker with feather-weight plan-runner [v3]"
```

---

## Task 11: Refactor dev-executor SKILL (C1, C2, C5)

**Files:**
- Modify: `skills/dev-executor/SKILL.md`

- [ ] **Step 1: Replace the entire SKILL file**

Overwrite `skills/dev-executor/SKILL.md`:

```markdown
---
name: dev-executor
description: >
  Implements ready plans. For each in-wave plan, parses the plan once into per-task
  envelopes, dispatches arch-excerpter (Sonnet) once to produce a per-plan
  arch_excerpt, then dispatches a plan-runner subagent per plan in parallel waves (cap 5).
  Each plan-runner dispatches one task-executor per task sequentially. Opus by default
  for plan-runner and task-executor (TDD + SOLID need a strong model). Use when
  implementing plans.
---

# dev-executor Skill (v3.0 orchestrator)

You orchestrate plan execution. Per-plan implementation runs in `plan-runner` subagents
(parallel within dependency waves); each plan-runner dispatches one `task-executor` per
task sequentially. **You** parse each plan ONCE and build per-task envelopes — neither
plan-runner nor task-executor reads the plan file.

## Read first (cache-friendly)

- `docs/implr/config/implr.config.yaml` — for paths, agent model overrides, test runner.
- `docs/implr/config/standards-card.md` — passed inline in every envelope. Halt if missing
  with: `❌ docs/implr/config/standards-card.md not found. Run /implr-init (or /implr-init --refresh-card) first.`

You do **not** read `docs/ARCHITECTURE.md` directly here — `arch-excerpter` handles that
per-plan. You do **not** read `plan-schema.md` — the format you parse is documented inline
below.

## Parameters

- `/dev-executor PLAN-F-001` — execute one plan.
- `/dev-executor PLAN-F-001 PLAN-F-002` — execute several (deps validated).
- `/dev-executor --all` — execute all `ready` plans in dependency order.
- `/dev-executor --task PLAN-F-001 TASK-003` — resume from a single task.
- `/dev-executor --dry-run PLAN-F-001` — list files that would be touched; write nothing.
- `/dev-executor --verbose` — append per-task file lists to the report (default: counts only).
- `/dev-executor --review` — after successful execution, chain `/dev-code-review` for
  executed plans.

## Execution

### Phase 1 — Resolve scope

Identify plans to execute (per parameter). For `--all`, read `plans-index.md` for
`status: ready`. For named plans, validate existence and `status: ready` (or `--task`
mode allowed on in-progress). For `--task`, locate the named task inside the named plan.

### Phase 2 — Validate dependencies

For each in-scope plan, every dependency listed in frontmatter `dependencies:` must be
`status: done`. Block plans whose deps are not done; report.

### Phase 3 — Compute execution waves

Topologically sort by plan dependencies. Each wave contains plans whose deps are done.

### Phase 4 — Per-plan preparation

For each in-scope plan (across all waves — do this once per plan up front):

a. **Read the plan file.**
b. **Parse into envelopes** using these rules:

   - Frontmatter = block between the first `---` and the second `---` at the top.
   - `## Objective` body = lines after `## Objective` until next `##`.
   - `## Architecture Context` body = lines after that header until next `##`.
   - `## Interfaces and Contracts` body = lines after `### Interfaces and Contracts`
     until next `##` (note: this is a `###` under Component Design).
   - `## Applied NFR Constraints` body = lines after that header until next `##`; if
     section absent or content is just `N/A`, set `applied_nfrs: "N/A"`.
   - **Each task** starts at a line matching the regex `^### TASK-(\d{3}): (.+)$`.
     Parse the header line for `complexity` and `tdd_required` from the format
     `### TASK-NNN: title · {complexity}/{tdd-flag} · {files}` where `{tdd-flag}` is
     `TDD` (=true) or `no-TDD` (=false). The `files` segment is a comma-separated list.
   - Task body = everything until the next `### TASK-` or next `## ` header.
   - Parse `**AC covered**: AC-NNN, AC-NNN` line within task body into `ac_covered`.
   - Parse `**Tests to write first (TDD)**` bullet list into `tests_first`.

   If parsing fails for any task (header regex mismatch, missing `**AC covered**` when
   the plan's AC Coverage section references that task), **abort the plan** with
   warning: `❌ PLAN-F-NNN parse failed at TASK-NNN: <reason>. Plan skipped — fix template
   compliance and re-run.` Continue with other plans.

c. **Resolve full AC text** by reading the linked requirement file
   (`linked_requirement:` from plan frontmatter → `docs/implr/requirements/.../REQ-*.md`).
   Extract each `- [ ] AC-NNN:` line; map id → text.

d. **Dispatch `arch-excerpter`** (Sonnet) with `{plan_path}`. Wait for return. Capture
   `excerpt` block as `arch_excerpt`. If arch-excerpter fails, fall back to reading
   first 200 lines of `docs/ARCHITECTURE.md` verbatim as `arch_excerpt` and warn.

e. **Build the envelope list** for this plan: for each parsed task, construct the
   envelope per `task-executor`'s input schema, embedding the shared `arch_excerpt`,
   the file contents of `docs/implr/config/standards-card.md`, the shared plan context
   (objective, arch context, interfaces, applied_nfrs), and the resolved `ac_full`.

f. Resolve `task_executor_model` from config: `agents.task-executor` if set, else
   `opus`.

### Phase 5 — Dispatch `plan-runner` per plan (parallel within wave)

For each wave (in topological order):

Dispatch all wave plans IN PARALLEL (single message, multiple Agent tool calls; cap 5).
Each dispatch passes:

```
plan_id, plan_path, resume_task, commit_mode (auto unless --dry-run),
task_envelopes (the prepared list), arch_excerpt, standards_card,
task_executor_model
```

For `--task` mode: build only the envelope for the named task; dispatch one plan-runner
with `resume_task: <task-id>` and a single-element `task_envelopes` list.

For `--dry-run`: do NOT dispatch. Instead, print the file list extracted from envelopes
per plan, then stop.

Wait for the wave to complete. Collect each plan-runner's return summary.

### Phase 6 — Aggregate and update indices

- Update `docs/implr/plans/plans-index.md` with new statuses (`done`, `in-progress`,
  `blocked`).
- Append a run entry to `docs/implr/plans/plans-log.md` (timestamp, plans processed,
  tasks completed, blockers).

### Phase 7 — Report (concise default; `--verbose` adds detail)

**Default report (one screen):**

```
🛠  dev-executor complete  (v3.0)
Plans executed: {n}    Waves: {n}
Tasks: {done}/{total}  Blocked: {n}
Files: +{new} ~{modified}
Tests: {added} added | {pass | fail}

{If any blockers or manual actions:}
Manual actions:
  - {one line each}

Next:
  /dev-code-review --all   (or specify plan ids)
```

**With `--verbose`:** also list per-plan files-created / files-modified / tests-added
under each plan id.

### Phase 8 — Chain code-review (only if `--review`)

If `--review` was passed AND no plan finished in `in-progress` or `blocked` state:
invoke `/dev-code-review` with the list of executed plan ids. Suppress its leading
banner; merge its verdict counts into this report.

## Failure handling

- Standards-card missing → halt before any dispatch with the message above.
- Plan parse failure → skip that plan; continue others; report skipped.
- Dependency not `done` → skip that plan with warning unless explicitly named.
- plan-runner returns `tests_pass: false` → plan status stays `in-progress`; surface
  failing task to user; do not chain code-review even if `--review` was set.
- Manual actions reported → surface; plan status stays `in-progress`.
- arch-excerpter failure → fall back to first 200 lines of ARCHITECTURE.md + warn; do
  not block execution.

## Definition of Done (canonical — also see docs/implr/DOD.md)

A plan reaches `status: done` only when:
1. All tasks complete.
2. All produced tests pass.
3. Every AC in the linked requirement is covered by ≥1 task and verified by ≥1 passing test.
4. No TODO/FIXME/XXX markers introduced.
5. Code-review (when run) has no Critical/High findings.

Items 1–4 are enforced by this skill; item 5 is enforced by `dev-code-review`.
```

- [ ] **Step 2: Verify**

Run: `grep -c "executor-worker" skills/dev-executor/SKILL.md`
Expected: 0 (no references to the deleted agent).

Run: `grep -c "plan-runner" skills/dev-executor/SKILL.md`
Expected: ≥ 3.

Run: `grep -c "arch-excerpter" skills/dev-executor/SKILL.md`
Expected: ≥ 2.

Run: `grep -c "standards-card" skills/dev-executor/SKILL.md`
Expected: ≥ 2.

Run: `wc -l skills/dev-executor/SKILL.md`
Expected: 160–210 lines (was 93; intentional growth for parser spec + envelope build).

- [ ] **Step 3: Commit**

```bash
git add skills/dev-executor/SKILL.md
git commit -m "feat(skill): rewrite dev-executor for v3 envelope dispatch; arch-excerpter + plan-runner [v3]"
```

---

## Task 12: code-review-worker reads standards-card (C4)

**Files:**
- Modify: `.claude/agents/code-review-worker.md`

- [ ] **Step 1: Update the agent file**

Read `.claude/agents/code-review-worker.md`.

Find the `## Read first` block:

```
## Read first

1. `docs/implr/schemas/review-schema.md`
2. `docs/ARCHITECTURE.md`
3. `docs/implr/config/DEV-STANDARDS.md`
4. The plan and the requirement (paths in inputs).
```

Replace with:

```
## Read first

1. `docs/implr/schemas/review-schema.md`
2. `docs/ARCHITECTURE.md` (full — review needs broad context)
3. The plan and the requirement (paths in inputs).

You do NOT read `docs/implr/config/DEV-STANDARDS.md`. The compact executable subset is
passed as `standards_card` in your inputs.
```

- [ ] **Step 2: Add standards_card to the inputs block**

Find:

```
## Inputs

```
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
requirement_path: docs/implr/requirements/.../REQ-F-NNN-<slug>.md
review_path_out: docs/implr/reviews/REVIEW-F-NNN-<slug>.md
src_path: src
tests_path: tests
```
```

Replace with:

```
## Inputs

```
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
requirement_path: docs/implr/requirements/.../REQ-F-NNN-<slug>.md
review_path_out: docs/implr/reviews/REVIEW-F-NNN-<slug>.md
src_path: src
tests_path: tests
standards_card: |
  <contents of docs/implr/config/standards-card.md — passed inline by dev-code-review>
```
```

- [ ] **Step 3: Verify**

Run: `grep -c "standards_card" .claude/agents/code-review-worker.md`
Expected: ≥ 2.

Run: `grep -c "DEV-STANDARDS.md" .claude/agents/code-review-worker.md`
Expected: 1 (the "you do NOT read" reference).

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/code-review-worker.md
git commit -m "feat(agent): code-review-worker reads standards-card inline; drops DEV-STANDARDS read [v3]"
```

---

## Task 13: dev-code-review skill — pass standards_card + concise report (C4, W4)

**Files:**
- Modify: `skills/dev-code-review/SKILL.md`

- [ ] **Step 1: Update Read first**

Find:

```
## Read first

- `docs/implr/schemas/review-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
```

Replace with:

```
## Read first

- `docs/implr/schemas/review-schema.md`
- `docs/implr/config/standards-card.md` — passed inline to each worker. Halt if missing
  with: `❌ standards-card.md missing. Run /implr-init --refresh-card first.`

Do NOT pre-read `docs/ARCHITECTURE.md` or `docs/implr/config/DEV-STANDARDS.md` — the
workers read ARCHITECTURE themselves (full read), and standards-card replaces DEV-STANDARDS.
```

- [ ] **Step 2: Update Parameters**

Find the `## Parameters` block and append:

```
- `/dev-code-review --verbose` — include per-finding detail in the aggregate report.
  Default: severity counts + verdicts only.
```

- [ ] **Step 3: Update Phase 2 dispatch payload**

Find:

```
Per dispatch scope: `{plan_path, requirement_path, review_path_out, src_path, tests_path}`.
```

Replace with:

```
Per dispatch scope: `{plan_path, requirement_path, review_path_out, src_path, tests_path,
standards_card}` where `standards_card` is the inline content of
`docs/implr/config/standards-card.md`.
```

- [ ] **Step 4: Trim Phase 5 report**

Replace the existing Phase 5 report block:

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

With:

```
🔍 dev-code-review complete  (v3.0)
Reviews: {n}   ✅{approved} ⚠️{warnings} ❌{changes} 🚫{rejected}
Findings: C={n} H={n} M={n} L={n} I={n}
Blocks merge: {list of plan ids with Critical or High; "none" if empty}

{With --verbose:}
Per plan:
  PLAN-F-NNN — {verdict} — C={n} H={n} M={n} (review at {path})
```

- [ ] **Step 5: Verify**

Run: `grep -c "standards-card" skills/dev-code-review/SKILL.md`
Expected: ≥ 3.

Run: `grep -c "DEV-STANDARDS.md" skills/dev-code-review/SKILL.md`
Expected: 1 (the negative reference).

Run: `grep -c "verbose" skills/dev-code-review/SKILL.md`
Expected: ≥ 2.

- [ ] **Step 6: Commit**

```bash
git add skills/dev-code-review/SKILL.md
git commit -m "feat(skill): dev-code-review passes standards_card; concise default report [v3]"
```

---

## Task 14: doc-ingest default flip (W1)

**Files:**
- Modify: `skills/doc-ingest/SKILL.md`

- [ ] **Step 1: Update description frontmatter**

Replace the `description:` block at the top:

```yaml
description: >
  Indexes and digests the knowledge base under docs/kb/. Use when adding/updating docs,
  refreshing the KB index, or asking to ingest/scan/digest. Default in v3.0 is FULL
  pipeline (extract + digest + syntheses + master). Pass --registry-only for the fast
  scan that just refreshes the file registry without digesting. Dispatches parallel
  subagents for extract, digest, and per-domain synthesis. Detects contradictions.
  Incremental — only reprocesses changed files.
```

- [ ] **Step 2: Update Parameters block**

Replace the `## Parameters` block:

```markdown
## Parameters

- `/doc-ingest` — **full pipeline** (extract + digest + syntheses + master). New default in v3.0.
- `/doc-ingest --registry-only` — fast scan: registry refresh only, no digests / syntheses.
- `/doc-ingest --file <path>` — process one file (full pipeline by default; combine with
  `--registry-only` to register without digesting).
- `/doc-ingest --rebuild` — reprocesses everything from scratch (full pipeline).
- `/doc-ingest --dry-run` — report what would change; write nothing; do not advance log.

**Removed in v3.0:** `--digest` (now the default; flag is redundant — accepted with a
deprecation warning for one minor version, then will error).

**Renamed from v2.0 default:** the registry-only behaviour now needs explicit
`--registry-only`.
```

- [ ] **Step 3: Replace Phase-4 / Phase-5 / Phase-6 skip gates**

Find every line of the form `**Skip ... if `--digest` was not passed.**` (three occurrences in Phases 4, 5, 6).

Replace each with: `**Skip entirely if `--registry-only` was passed.**`

- [ ] **Step 4: Add legacy --digest handling**

After the Parameters block, insert:

```markdown
---

## Legacy flag handling

- If the invocation includes `--digest`: print a one-line deprecation note
  (`ℹ️  --digest is now the default in v3.0; flag accepted for backward compatibility.`)
  and treat as a no-op (full pipeline runs regardless).
- If both `--digest` and `--registry-only` are passed: `--registry-only` wins; warn the
  user about the conflicting flags.
```

- [ ] **Step 5: Verify**

Run: `grep -c "registry-only" skills/doc-ingest/SKILL.md`
Expected: ≥ 5.

Run: `grep -c "v3.0" skills/doc-ingest/SKILL.md`
Expected: ≥ 2.

Run: `grep -n "Skip" skills/doc-ingest/SKILL.md`
Expected: each occurrence references `--registry-only`, not `--digest`.

- [ ] **Step 6: Commit**

```bash
git add skills/doc-ingest/SKILL.md
git commit -m "feat(skill): flip /doc-ingest default to full pipeline; add --registry-only [v3 W1]"
```

---

## Task 15: dev-planner coherence sweep opt-in (W2) + drop DoD requirement (C6)

**Files:**
- Modify: `skills/dev-planner/SKILL.md`

- [ ] **Step 1: Add the --coherence-check parameter**

In the `## Parameters` block, append:

```
- `/dev-planner --coherence-check ...` — force the cross-plan coherence sweep (Phase 6).
  Default: sweep auto-runs only when ≥3 plans were generated in this invocation.
```

- [ ] **Step 2: Rewrite Phase 6**

Replace the entire `### Phase 6 — Cross-requirement coherence sweep` section with:

```
### Phase 6 — Cross-requirement coherence sweep (opt-in / auto-≥3)

Run this phase ONLY if:
- `--coherence-check` was passed on the command line, OR
- The number of plans generated in this invocation is ≥ 3.

Otherwise: skip with a one-line note `Coherence sweep skipped ({n} plan(s) — pass
--coherence-check to force).`

When running: dispatch the built-in `Explore` subagent (read-only) with scope:
"Check plans at <paths> for: duplicate task definitions across plans, missing AC
coverage, inconsistent task ordering vs requirement dependencies."

Include findings in the report; do not modify plans.
```

- [ ] **Step 3: Drop DoD generation from plan-worker dispatch contract**

In Phase 5 (plan-worker dispatch), confirm no instruction to populate `## Definition of
Done` is present. The plan-worker.md agent already follows the schema/template, both of
which (after Tasks 1 and 3) have no DoD section. If `plan-worker.md` references DoD
generation, this task's verification will catch it. Continue.

- [ ] **Step 4: Verify**

Run: `grep -c "coherence-check" skills/dev-planner/SKILL.md`
Expected: ≥ 2.

Run: `grep -c "Definition of Done" skills/dev-planner/SKILL.md`
Expected: 0.

- [ ] **Step 5: Audit plan-worker for DoD references**

Run: `grep -n "Definition of Done\|DoD" .claude/agents/plan-worker.md`
Expected: no matches. If matches exist, edit `.claude/agents/plan-worker.md` to remove
them in a sub-step before commit.

- [ ] **Step 6: Commit**

```bash
git add skills/dev-planner/SKILL.md .claude/agents/plan-worker.md
git commit -m "feat(skill): dev-planner coherence sweep opt-in / auto-≥3; drop DoD generation [v3 W2 C6]"
```

---

## Task 16: Update installer scripts (all three)

**Files:**
- Modify: `install.ps1`
- Modify: `install.sh`
- Modify: `install.bat`

The installers copy `.claude/agents/*.md` wholesale, so the new `plan-runner.md` and
`arch-excerpter.md` files (and absence of `executor-worker.md`) propagate automatically.
The installers copy `scaffold/templates/*.md` wholesale, so `standards-card-template.md`
propagates automatically. Only two additions are needed:

1. Seed `scaffold/seeds/DOD.md` to `docs/implr/DOD.md` (skip-if-exists).
2. Print v3 deletion note for any pre-existing `executor-worker.md` in target.

- [ ] **Step 1: Patch install.ps1 — DOD seed**

Find the existing skip-if-exists seed block for `cr-index.md` and pattern-match a new
block immediately after the `resolved-contradictions.md` seed:

Locate the closing `}` of the `resolved-contradictions.md` block (line ~89), and INSERT
after it (before `Write-Host "  workspace scaffolded"`):

```powershell
    # Skip if exists: DOD.md seed at docs/implr/DOD.md
    if (-not (Test-Path "docs\implr\DOD.md")) {
        Copy-Item (Join-Path $ScaffoldSrc "seeds\DOD.md") "docs\implr\DOD.md"
        Write-Host "  created docs\implr\DOD.md"
    } else {
        Write-Host "  kept existing docs\implr\DOD.md"
    }

    # Cleanup: remove deprecated v2 executor-worker.md if present
    $oldAgent = Join-Path $AgentsDest "executor-worker.md"
    if (Test-Path $oldAgent) {
        Remove-Item -Force $oldAgent
        Write-Host "  removed deprecated agent: executor-worker.md (replaced by plan-runner.md in v3)"
    }
```

Note: `$AgentsDest` is defined later in the script — this block must execute AFTER the
agents-copy step. Place this cleanup block AFTER the line `Write-Host "  installed
$agentCount agents"` near line 122. Specifically: split the change into TWO insertions:
- The DOD seed block goes INSIDE `Scaffold-Workspace` function before `Write-Host "  workspace scaffolded"`.
- The cleanup block goes AFTER `Write-Host "  installed $agentCount agents"`.

- [ ] **Step 2: Patch install.sh — same two additions**

Read `install.sh` to locate the equivalent points (seed loop + agents-copy). Apply the
same two patches with bash syntax:

DOD seed (inside workspace scaffolding block):

```bash
# Skip if exists: DOD.md seed
if [ ! -f "docs/implr/DOD.md" ]; then
  cp "$SCRIPT_DIR/scaffold/seeds/DOD.md" "docs/implr/DOD.md"
  echo "  created docs/implr/DOD.md"
else
  echo "  kept existing docs/implr/DOD.md"
fi
```

Cleanup (after agents copy):

```bash
if [ -f "$AGENTS_DEST/executor-worker.md" ]; then
  rm -f "$AGENTS_DEST/executor-worker.md"
  echo "  removed deprecated agent: executor-worker.md (replaced by plan-runner.md in v3)"
fi
```

- [ ] **Step 3: Patch install.bat — same two additions**

Read `install.bat`. Apply equivalent patches:

DOD seed:

```bat
if not exist "docs\implr\DOD.md" (
  copy /Y "%SCRIPT_DIR%scaffold\seeds\DOD.md" "docs\implr\DOD.md" >nul
  echo   created docs\implr\DOD.md
) else (
  echo   kept existing docs\implr\DOD.md
)
```

Cleanup:

```bat
if exist "%AGENTS_DEST%\executor-worker.md" (
  del /Q "%AGENTS_DEST%\executor-worker.md"
  echo   removed deprecated agent: executor-worker.md ^(replaced by plan-runner.md in v3^)
)
```

- [ ] **Step 4: Run installer dry-test against a scratch directory**

```bash
mkdir -p /tmp/implr-install-test && cd /tmp/implr-install-test && bash <repo-root>/install.sh && ls .claude/agents/ && ls docs/implr/
```

Expected output:
- `.claude/agents/` lists `plan-runner.md` and `arch-excerpter.md`, does NOT list `executor-worker.md`.
- `docs/implr/` lists `DOD.md`.
- `docs/implr/templates/` lists `standards-card-template.md`.

Clean up: `rm -rf /tmp/implr-install-test`

- [ ] **Step 5: Commit**

```bash
git add install.ps1 install.sh install.bat
git commit -m "feat(installer): seed DOD.md; cleanup deprecated executor-worker.md on update [v3]"
```

---

## Task 17: README v3 changes + migration section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the opening paragraph and skill mention**

Find the line `In v2.0, each skill runs as an **orchestrator**...` and replace the paragraph with:

```
In v3.0, the cost model is rebuilt: `dev-executor` parses plans into inline task envelopes
and dispatches them to feather-weight `plan-runner` agents (replacing `executor-worker`).
`task-executor` no longer reads schemas, ARCHITECTURE.md, or DEV-STANDARDS.md — everything
arrives inline. End-to-end runs cost **6–10× fewer tokens** than v1.x and **2.5–3× fewer
than v2.0** on a typical plan.
```

- [ ] **Step 2: Update the Skills table**

Find `dev-executor` row and update its parenthetical:

`(parallel plan-runner per plan → task-executor per task, Opus by default; envelope-based dispatch)`

Find `doc-ingest` row and update:

`(full pipeline by default; parallel extract/digest/synthesize; --registry-only for fast scan)`

- [ ] **Step 3: Update the Customising Model Tiers default-agents YAML block**

Find the `agents:` YAML block. Remove the `executor-worker:` line. Add:

```yaml
  plan-runner: opus                 # per-plan dispatcher (no stable reads)
  arch-excerpter: sonnet            # per-plan ARCHITECTURE excerpt
```

- [ ] **Step 4: Update the Performance & Token Efficiency section**

Replace the v2.0 bullets with:

```markdown
implr v3.0 takes the orchestrator-+-subagent model further:

- **Inline task envelopes** — `dev-executor` parses each plan once and dispatches each task
  as a self-contained envelope. `task-executor` no longer re-reads the full plan, the
  schema, ARCHITECTURE.md, or DEV-STANDARDS.md per task.
- **Standards card** — a compact (~50-line) auto-generated subset of DEV-STANDARDS.md is
  passed inline to task-executor and code-review-worker; the full prose stays for
  dev-planner.
- **Per-plan ARCHITECTURE excerpt** — `arch-excerpter` (Sonnet, one call per plan)
  extracts only the sections each plan touches, plus Cross-Cutting Concerns verbatim.
- **plan-runner instead of executor-worker** — feather-weight per-plan agent with NO
  stable reads; the 30k stable prefix of v2.0's executor-worker is gone.
- **Compact plan & requirement templates** — DoD moved to a single canonical
  `docs/implr/DOD.md`; always-empty sections omitted; one-line task headers; one-line AC
  coverage rows.

Typical end-to-end runs cost **6–10× fewer tokens** than v1.x.
```

- [ ] **Step 5: Add the Migration section**

Find `## Migrating from v1.x to v2.0` and INSERT a new section BEFORE it:

```markdown
## Migrating from v2.0 to v3.0

1. **Pull and re-run the installer** from your project root. The installer:
   - Copies new agents: `plan-runner.md`, `arch-excerpter.md`.
   - Removes deprecated `executor-worker.md` if present.
   - Seeds `docs/implr/DOD.md` (canonical Definition of Done).
   - Refreshes schemas and templates (compact plan/requirement formats).

2. **Generate standards-card.md:** run `/implr-init --refresh-card`. This reads your
   current `DEV-STANDARDS.md` stack/versioning values and writes the executable subset to
   `docs/implr/config/standards-card.md`. task-executor and code-review-worker now read
   this card instead of full DEV-STANDARDS.

3. **Existing plans:** generated under v2.0 still execute under v3 as long as their
   `### TASK-NNN:` headers match the regex `^### TASK-(\d{3}): `. If you want to regenerate
   them in the compact format, run `/dev-planner --replan <REQ-ID>` per requirement.

4. **Existing requirements:** continue to work. DoD sections in old requirements are
   inert — dev-executor and dev-code-review use `docs/implr/DOD.md` plus any per-REQ
   `## Acceptance Notes`. You may strip the inline DoD when convenient.

5. **Flag changes:**
   - `/doc-ingest` now runs the full pipeline by default. Use `--registry-only` for the
     v2.0 fast-scan behaviour. `--digest` still accepted (deprecation warning).
   - `/dev-planner` cross-plan coherence sweep is now opt-in (`--coherence-check`) or
     auto-on when ≥3 plans were generated.
   - `/dev-executor` default report is now one screen. Use `--verbose` for v2.0 detail.
   - `/dev-code-review` default report compacted; `--verbose` for detail.
   - `/dev-executor --review` chains code-review automatically.

6. **Config:** in `docs/implr/config/implr.config.yaml`, remove any `executor-worker:`
   line under `agents:`. Optionally add `plan-runner:` and `arch-excerpter:` overrides
   (defaults: opus and sonnet respectively).
```

- [ ] **Step 6: Verify**

Run: `grep -c "plan-runner" README.md`
Expected: ≥ 4.

Run: `grep -c "arch-excerpter" README.md`
Expected: ≥ 3.

Run: `grep -c "v3.0" README.md`
Expected: ≥ 5.

Run: `grep -c "executor-worker" README.md`
Expected: 1 (only in the v3 migration section, "remove any executor-worker: line").

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs(readme): v3 changes; migration section; updated skills table and config block [v3]"
```

---

## Task 18: Update WORKFLOW.md

**Files:**
- Modify: `docs/WORKFLOW.md`

- [ ] **Step 1: Update the v2.0 dispatch table**

Find the markdown table headed "Which phases dispatch". Replace the `dev-executor` rows:

OLD:
```
| dev-executor | Phase 4 (execute) | executor-worker | **opus** | Yes per wave (cap 5) |
| dev-executor | Phase 4 (per-task) | task-executor | **opus** | Sequential within each executor-worker |
```

NEW:
```
| dev-executor | Phase 4 (arch excerpt) | arch-excerpter | sonnet | One per plan (sequential within prep phase) |
| dev-executor | Phase 5 (plan execute) | plan-runner | **opus** | Yes per wave (cap 5) |
| dev-executor | Phase 5 (per-task) | task-executor | **opus** | Sequential within each plan-runner |
```

Also update the section heading "## Subagent Dispatch Model (v2.0)" → "## Subagent Dispatch Model (v3.0)".

- [ ] **Step 2: Update the "Why this saves tokens" subsection**

Find and replace its bullet list:

```
- Per-task envelopes mean task-executor never re-reads the full plan, the schema,
  ARCHITECTURE.md, or DEV-STANDARDS.md.
- plan-runner has no stable reads — replaces v2's heavy executor-worker.
- standards-card is a compact auto-generated subset (~50 lines) of DEV-STANDARDS.md
  passed inline.
- arch-excerpter runs once per plan; its output amortises across all tasks.
- Independent units dispatch in parallel — same wall-clock, lower per-token spend on
  cheaper tiers.

Typical end-to-end runs cost 6–10× fewer tokens than v1.x.
```

- [ ] **Step 3: Update the Plan section's v2 note**

Find the note `*In v2.0, plan creation is performed by parallel...` and update to:

```
*In v3.0, plan creation is performed by parallel `plan-worker` subagents (one per
requirement per dependency wave). Plan execution is orchestrated by `dev-executor`:
it parses each plan into per-task envelopes, dispatches `arch-excerpter` (Sonnet) once
per plan, then dispatches `plan-runner` (Opus) per plan in parallel waves. Each
plan-runner dispatches one `task-executor` (Opus) per task sequentially. Plan review is
performed by parallel `code-review-worker` subagents (one per plan, reading
`standards-card` inline).*
```

- [ ] **Step 4: Verify**

Run: `grep -c "plan-runner" docs/WORKFLOW.md`
Expected: ≥ 3.

Run: `grep -c "executor-worker" docs/WORKFLOW.md`
Expected: 0.

Run: `grep -c "arch-excerpter" docs/WORKFLOW.md`
Expected: ≥ 3.

- [ ] **Step 5: Commit**

```bash
git add docs/WORKFLOW.md
git commit -m "docs(workflow): update dispatch model for v3; plan-runner + arch-excerpter [v3]"
```

---

## Task 19: Smoke verification (AC-013, end-to-end gate)

**Files:** none modified — pure verification.

This task is the quality-equivalence gate from the spec's AC-013. It must run after all
prior tasks merge. The aim is to confirm that a v2.0 plan re-executed under v3.0
produces same-quality output.

- [ ] **Step 1: Pick or synthesise a representative test plan**

Inspect this repo for any existing plan files we can use as a regression fixture:

```bash
find . -path '*/plans/*' -name 'PLAN-*.md' | head -5
```

If at least one PLAN-*.md exists, pick the most complex (most tasks). If none exist,
create a synthetic plan: write a trivial requirement (e.g. "REQ-F-001: in-memory string
reverser with edge-case handling") under `docs/implr/requirements/functional/`, then run
`/dev-planner REQ-F-001` to produce a v3-compact plan.

Record the chosen plan path and its task count.

- [ ] **Step 2: Verify plan parses correctly under the new parser rules**

Manually scan the plan for compliance with the new template:
- Frontmatter present and parseable.
- `## Objective` and `## Architecture Context` sections present.
- Each `### TASK-NNN:` header matches the regex `^### TASK-(\d{3}): (.+?) · (XS|S|M|L|XL)/(TDD|no-TDD) · (.+)$`.
- AC Coverage section uses one-line format.

If any task fails the regex (e.g. legacy v2 plans), record this — it confirms the
parser-failure abort path will trigger, and is itself a successful negative test.

- [ ] **Step 3: Dry-run dev-executor**

Run `/dev-executor --dry-run <PLAN-ID>` and confirm:
- It prints files that would be touched, derived from envelopes.
- No errors about missing `standards-card.md` (run `/implr-init --refresh-card` first if
  needed).
- No errors about missing `plan-runner` or `arch-excerpter` agents.

- [ ] **Step 4: Live-run dev-executor on the test plan**

Run `/dev-executor <PLAN-ID>`. Observe:
- arch-excerpter dispatch happens once for the plan.
- One plan-runner dispatch per plan.
- task-executor dispatches sequentially within the plan.
- Final report fits one screen.
- Plan status updated to `done` or `in-progress` correctly.

Capture approximate token consumption (visible via `/cost` or session usage report).
Compare against any prior v2.0 run on the same plan if available.

- [ ] **Step 5: Run dev-code-review on the executed plan**

Run `/dev-code-review <PLAN-ID>`. Observe:
- code-review-worker dispatched once.
- Review file produced.
- Verdict emitted in concise report format.

- [ ] **Step 6: Record results**

Append to the spec's AC checklist (in
`docs/superpowers/specs/2026-06-02-implr-v3-cost-reduction-design.md`) the actual
measurements observed:

```
## Verification Results (filled in at Task 19)

- AC-001 task-executor cold start: <observed tokens>
- AC-002 dev-executor end-to-end: <observed tokens> ; v2.0 baseline: <if known>
- AC-003 smoke run: PASS / FAIL — <notes>
- AC-004 plan file size: <observed lines>
- AC-005 requirement file size: <observed lines>
- AC-013 quality equivalence: PASS / FAIL — <notes>
```

If any AC fails, do NOT close the v3 release. File follow-up tasks.

- [ ] **Step 7: Commit verification results**

```bash
git add docs/superpowers/specs/2026-06-02-implr-v3-cost-reduction-design.md
git commit -m "docs(spec): record v3 verification results [v3]"
```

---

## Task 20: Final tag and changelog

**Files:**
- Create / modify: `CHANGELOG.md` (create if absent)

- [ ] **Step 1: Add a v3.0 entry**

If `CHANGELOG.md` does not exist at repo root, create it with header
`# Changelog`. Prepend a v3.0 section:

```markdown
## v3.0.0 — 2026-06-02

### Cost reduction
- New `plan-runner` agent replaces `executor-worker`; no stable reads (saves ~30k per plan).
- `task-executor` now receives an inline task envelope; no longer reads plan-schema,
  ARCHITECTURE.md, DEV-STANDARDS.md, or the full plan (saves ~17k per task).
- New `arch-excerpter` agent (Sonnet) produces a per-plan architecture excerpt; one call
  per plan amortised across all tasks.
- New `docs/implr/config/standards-card.md` (auto-generated): compact executable subset
  of DEV-STANDARDS.md consumed by task-executor and code-review-worker.
- Compact plan template (~40% smaller); compact requirement template (~25% smaller).
- Definition of Done moved out of REQ/PLAN bodies into canonical `docs/implr/DOD.md`;
  optional `## Acceptance Notes` for per-artefact overrides.

### Workflow simplifications
- `/doc-ingest` now defaults to the full pipeline. `--registry-only` for v2 fast-scan.
  `--digest` deprecated (no-op with warning).
- `/dev-planner` cross-plan coherence sweep is opt-in (`--coherence-check`) or
  auto-on when ≥3 plans generated.
- `/dev-executor` and `/dev-code-review` default reports compacted to one screen;
  `--verbose` for detail.
- `/dev-executor --review` chains code-review after successful execution.

### Migration
See README "Migrating from v2.0 to v3.0".

### Breaking
- `.claude/agents/executor-worker.md` removed (replaced by `plan-runner.md`). Installer
  auto-cleans on update.
- Default behaviour of `/doc-ingest` changed (now includes digests).
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "chore(release): v3.0.0 changelog entry"
```

---

## Self-review (per writing-plans skill)

Run the self-review checklist once after writing the plan. Fix issues inline.

### 1. Spec coverage

Walk the spec's 10 changes (C1–C7 + W1, W2, W4) and 13 ACs; map to tasks:

| Spec item | Implementing task(s) |
|---|---|
| C1 plan-runner replaces executor-worker | Task 10, Task 11 |
| C2 inline task envelope | Task 9 (task-executor), Task 11 (dev-executor parser) |
| C3 drop plan-schema from task-executor | Task 9 |
| C4 standards-card | Task 6, Task 7, Task 12, Task 13 |
| C5 arch-excerpter | Task 8, Task 11 |
| C6 DoD removal | Task 1, Task 2, Task 3, Task 4, Task 5, Task 15 |
| C7 compact plan template | Task 1, Task 3 |
| C7b compact requirement template | Task 2, Task 4 |
| W1 /doc-ingest default flip | Task 14 |
| W2 dev-planner coherence opt-in | Task 15 |
| W4 trim default reports | Task 11 (dev-executor), Task 13 (dev-code-review) |
| AC-001..005 measurable targets | Task 19 |
| AC-006 executor-worker deleted | Task 10 |
| AC-007 arch-excerpter exists | Task 8 |
| AC-008 standards-card generated | Task 7 |
| AC-009 doc-ingest default | Task 14 |
| AC-010 coherence sweep opt-in | Task 15 |
| AC-011 reports one screen | Task 11, Task 13 |
| AC-012 README + migration | Task 17 |
| AC-013 quality equivalence | Task 19 |

All spec items covered.

### 2. Placeholder scan

No "TBD", "TODO", "fill in", or vague "handle edge cases" steps. Each step has concrete
content or an exact command.

### 3. Type / name consistency

- Agent file is `plan-runner.md` everywhere ✓
- Agent file is `arch-excerpter.md` everywhere ✓
- Standards card is `docs/implr/config/standards-card.md` everywhere ✓
- DoD seed is at `docs/implr/DOD.md` everywhere ✓
- Task-envelope field names match between Task 9 (task-executor spec) and Task 11
  (dev-executor parser/builder) — both use `task_envelope.task.id`, `task.tdd_required`,
  `task.files`, `ac_full`, `arch_excerpt`, `standards_card`, `prior_decisions_summary` ✓
- Task-header regex `^### TASK-(\d{3}): (.+)$` referenced in Task 1 (schema), Task 11
  (parser), Task 19 (verification) — consistent ✓

All consistent.
