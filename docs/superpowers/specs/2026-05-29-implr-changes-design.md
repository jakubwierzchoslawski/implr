# implr Changes Design — 2026-05-29

## Overview

This spec covers 12 targeted changes to the implr skill suite. They address four categories of
issues: missing log file initialisation, an under-interactive implr-init skill, overly
token-heavy execution, and several gaps in ba-requirements-gen and dev-planner behaviour around
real-world pipeline scenarios.

**Implementation order:** bottom-up by blast radius — safest/most isolated changes first,
most invasive last.

---

## Scope

| # | Change | Affected files |
|---|--------|----------------|
| 1 | Defensive log file creation | doc-ingest/SKILL.md, ba-requirements-gen/SKILL.md |
| 5 | Cache rationale documented | docs/WORKFLOW.md |
| 10 | Index vs log role clarification | docs/WORKFLOW.md |
| 11 | --all skips already-planned requirements | dev-planner/SKILL.md |
| 7 | Flip ingest default; remove auto_chain_doc_ingest | ba-requirements-gen/SKILL.md, implr.config.yaml |
| 12 | Open question batching + blocked status | dev-planner/SKILL.md |
| 6 | Explicit deep-dive conditions | ba-requirements-gen/SKILL.md |
| 8 | Requirement inference reasoning | ba-requirements-gen/SKILL.md |
| 9 | Post-implementation update flow | ba-requirements-gen/SKILL.md, dev-planner/SKILL.md, docs/WORKFLOW.md |
| 2+3+4 | implr-init full rewrite as pure executor | skills/implr-init/SKILL.md |

---

## Section 1 — Safe / Isolated Changes

### 1.1 Defensive log file creation (Change 1)

**Files:** `skills/doc-ingest/SKILL.md`, `skills/ba-requirements-gen/SKILL.md`

In each skill's "Update log" phase, insert a guard before appending:

> Before prepending the run entry, check whether the log file exists. If it does not, create it
> with a header line and the entry format as documented in the schema. Then append normally.

- `doc-ingest` owns `docs/implr/kb-index/digest-log.md`
- `ba-requirements-gen` owns `docs/implr/requirements/requirements-log.md`

No seed files are added. No other structural change to either skill. The header content mirrors
the schema definition for each respective log.

---

### 1.2 WORKFLOW.md — cache rationale (Change 5)

**File:** `docs/WORKFLOW.md`

Add a sub-section **"Why the text cache exists"** alongside the existing "Why digests exist"
section:

- Extract once, read many times
- Binary/structured formats (PDF, DOCX, XLSX, CSV) require external tool invocations —
  expensive to repeat on every skill run
- Cache checksum guards against re-extraction when source is unchanged
- `.md`/`.txt` are straight copies, but one consistent read path (`cache/{slug}.txt`) means
  downstream skills (ba-requirements-gen, arch-gen) never need to know the original format
- Skills always read from cache; never from the raw binary original

---

### 1.3 WORKFLOW.md — index vs log role clarification (Change 10)

**File:** `docs/WORKFLOW.md`

Add a section **"Log files vs Index files"**:

**`requirements-index.md`** — current-state register:
- What requirements exist right now
- Their IDs, titles, statuses, dependencies, linked plans
- Traceability matrix (source doc → requirement IDs)
- "Needs Human Review" section (open questions, unresolved contradictions)
- Used by: dev-planner to find approved requirements; humans to track status

**`requirements-log.md`** — append-only history:
- Every ba-requirements-gen run, timestamped
- Which domain syntheses were processed (with checksums)
- Which requirements were created/updated
- Contradictions surfaced
- Post-implementation update warnings
- Used by: ba-requirements-gen as the incremental gate (determines which synthesis checksums
  were last processed)

The log is what makes incremental processing possible. Without it, ba-requirements-gen cannot
know which synthesis checksums it last processed.

---

### 1.4 dev-planner — --all skip logic (Change 11)

**File:** `skills/dev-planner/SKILL.md`

In PHASE 0 — Validate input, add an explicit rule for `--all` mode:

> When `--all` is used, before processing each requirement check whether a matching plan file
> (`PLAN-F-NNN` or `PLAN-N-NNN`) already exists with `status: ready`, `in-progress`, or `done`.
> If yes, skip it and emit:
> ```
> ⏭  REQ-F-001 — already has PLAN-F-001 (ready). Skipping.
>    Use --replan REQ-F-001 to regenerate.
> ```
> Only `status: blocked` does not protect a plan from being regenerated. A plan that does not
> exist at all always triggers planning.

---

## Section 2 — Parameter Interface Changes

### 2.1 ba-requirements-gen — flip ingest default (Change 7)

**Files:** `skills/ba-requirements-gen/SKILL.md`, `skills/implr-init/assets/config/implr.config.yaml`

**Config:** Remove `auto_chain_doc_ingest: true` from `implr.config.yaml` entirely (hard remove).
New projects will not have the key. Existing projects that have it: ba-requirements-gen will
silently ignore it (no warning, no migration note).

**Parameters** — replace `--no-ingest` with three explicit modes:

| Invocation | Behaviour |
|---|---|
| `/ba-requirements-gen` | Use existing syntheses. No ingest. |
| `/ba-requirements-gen --ingest` | Run full doc-ingest on KB first, then generate. |
| `/ba-requirements-gen --ingest-file <path>` | Ingest one specific file first, then generate. |

`--no-ingest` is removed. PHASE 0 is rewritten to check for `--ingest` / `--ingest-file`
rather than a config flag.

**Ambiguity handling** (made explicit in PHASE 2): doc-ingest writes detected ambiguities into
each domain synthesis under "Ambiguities Detected". When ba-requirements-gen reads that
synthesis, for each ambiguity it either resolves from `cache/{slug}.txt` or surfaces as an
Open Question citing the source document. Ambiguities are never silently discarded.

---

### 2.2 dev-planner — open question batching and blocked status (Change 12)

**File:** `skills/dev-planner/SKILL.md`

PHASE 1 — Resolve open questions gains four explicit edge-case rules:

**Contradiction (two docs conflict):**
Present both source documents and the conflict. Ask for a decision. Write the answer back into
the requirement's Open Questions table as `✅ {date}: {decision}`. Continue planning.

**Gap (information missing from KB entirely):**
Present the question. If the user answers inline, record it. If the user says "proceed anyway",
create the plan with `status: blocked` and the open question still flagged as unresolved.
Never guess.

**Coherence failure across requirements (entity names don't match):**
Stop. Tell the user exactly what to align in the source requirements. Do not generate any plan
for the affected requirements until they are corrected and re-approved.

**Many open questions across multiple requirements:**
Batch by requirement. Resolve all open questions for REQ-F-001 fully before moving to
REQ-F-002. Never interleave questions from different requirements.

**`--all` with mixed requirements (some clean, some with open questions):**
Process the clean ones first, generating their plans. Then pause and report clearly what
remains so the user knows exactly what's left to resolve.

---

## Section 3 — Behavioural Changes

### 3.1 ba-requirements-gen — explicit deep-dive conditions (Change 6)

**File:** `skills/ba-requirements-gen/SKILL.md`

Replace "deep-dive only when needed" in PHASE 2 with explicit binary rules:

**Synthesis is sufficient when:**
- Information needed is behavioural (user journeys, business rules, what the system must do)
- No field-level data models beyond what the "Data Entities" section provides
- No precise wording from contracts, regulations, or SLAs required

**Go to `cache/{slug}.txt` when:**
- Domain synthesis flags an explicit ambiguity (`Ambiguities Detected: ...`)
- A requirement needs field-level data models not captured in digest entities
- An NFR needs a specific numeric target the digest paraphrased vaguely
- Digest `word_count` is very low relative to topic complexity (signals under-extraction)
- Quality gate cannot be met: cannot write 2 testable ACs from synthesis alone

**If no cache exists for a needed file:**
Flag it as an Open Question. Never attempt to read the raw binary original. Never fail the run.

---

### 3.2 ba-requirements-gen — requirement inference reasoning (Change 8)

**File:** `skills/ba-requirements-gen/SKILL.md`

Add an **"Inferring unstated requirements"** section to PHASE 2:

Real documentation describes a business domain, not system requirements. The BA reasoning rules:

- **From user journeys:** if a doc describes "a customer selects products and completes a
  purchase", cart management, payment initiation, order confirmation, and email notification
  are all implied — none may be explicit in the source
- **From entity lifecycles:** if `Invoice` has statuses `draft → sent → paid → overdue`,
  requirements to transition between each state are implied even if never stated
- **From integration mentions:** "the system notifies customers by email" implies an
  email-sending requirement even without an email service spec
- **From NFR signals:** "must handle high traffic during sales events" → Performance NFR with
  a measurable target (estimated from context, or flagged as needing specification)
- **When truly ambiguous:** if the requirement cannot be reasonably inferred without guessing,
  create it as `status: draft` with a populated Open Question citing the source and the gap

The quality gate (2 testable ACs minimum) is the forcing function — if the skill cannot write
concrete ACs, it must ask an Open Question or create a minimal draft flagging the gap.

---

### 3.3 Post-implementation update flow (Change 9)

**Files:** `skills/ba-requirements-gen/SKILL.md`, `skills/dev-planner/SKILL.md`, `docs/WORKFLOW.md`

**Scenario:** A new document is added to `docs/kb/` after a requirement has already been
planned and implemented.

**ba-requirements-gen — additions to PHASE 4 (when updating an existing requirement):**

- If changes are additive (new AC, new field) or contradictory (implementation may be wrong):
  drop status from `approved` to `under-review` (not `draft` — it was previously reviewed)
- If the change is a minor clarification only (no new ACs, no behavioural change): status
  stays `approved`
- Check whether `PLAN-F-NNN` / `PLAN-N-NNN` exists for this requirement
- If a plan exists, append a warning to `requirements-log.md`:
  ```
  ⚠️  REQ-F-007 updated post-implementation: {one-line summary of change}.
      PLAN-F-007 exists (status: done). Human review needed.
  ```
- Surface these under a "Post-implementation updates" heading in the PHASE 7 report

**dev-planner — additions to PHASE 4:**

When generating a plan for a requirement with `status: under-review` (set by ba-requirements-gen
after a post-implementation update), insert a warning block at the top of the plan file:

```
⚠️  SOURCE REQUIREMENT UPDATED AFTER IMPLEMENTATION
    Requirement updated: {date}
    Summary of change: {from requirements-log entry}
    Review whether existing implementation satisfies the updated requirement
    before re-executing.
```

This does NOT automatically invalidate the plan or trigger re-review. It surfaces the conflict
for human decision. The human then either re-approves the requirement as-is or triggers
`--replan`.

**WORKFLOW.md:** Add a section **"When a new document changes an existing requirement"** with
the full 6-step invocation flow:

```
1. /doc-ingest --file docs/kb/new-policy.md
   → detects new doc, rebuilds domain synthesis, flags contradiction

2. /ba-requirements-gen
   → sees changed domain synthesis
   → updates REQ-F-007: new AC + open question for contradiction
   → drops status to under-review
   → writes warning to requirements-log.md
   → warns: "REQ-F-007 updated. PLAN-F-007 exists (done). Human review needed."

3. Human reviews REQ-F-007 and the warning
   → option A: AC is additive, existing code handles it → re-approve, no re-planning needed
   → option B: new policy changes behaviour → set approved, run /dev-planner --replan REQ-F-007

4. /dev-planner --replan REQ-F-007    (if re-planning needed)
5. /dev-executor PLAN-F-007           (implements the delta)
6. /dev-code-review PLAN-F-007        (reviews)
```

---

### 3.4 implr-init full rewrite (Changes 2, 3, 4)

**File:** `skills/implr-init/SKILL.md`

**Guiding principle:** pure executor, not a reasoner. Claude asks questions, collects answers,
substitutes values, creates directories, copies files, reports. No narration, no prose
reasoning, no deep-reading of asset files.

**Interactive questions — asked one at a time, in this order, before any file operations:**

| # | Question | Target |
|---|----------|--------|
| 1 | Project name? | `implr.config.yaml` `project.name` + `CLAUDE.md` |
| 2 | Tech stack? (e.g. "Python, FastAPI, PostgreSQL") | `implr.config.yaml` `project.stack_hint` |
| 3 | Source folder? (default: src) | `implr.config.yaml` `paths.src` |
| 4 | Tests folder? (default: tests) | `implr.config.yaml` `paths.tests` |
| 5 | Default TDD threshold — M / L / XL? (default: M) | `implr.config.yaml` `behaviour.default_tdd_threshold` |
| 6 | Language + version? | `DEV-STANDARDS.md` §1 Project Stack |
| 7 | Framework? | `DEV-STANDARDS.md` §1 Project Stack |
| 8 | ORM + DB? | `DEV-STANDARDS.md` §1 Project Stack |
| 9 | Test runner? | `DEV-STANDARDS.md` §1 Project Stack |
| 10 | API versioning strategy? | `DEV-STANDARDS.md` §7 API Design |
| 11 | Git branch prefix convention? | `DEV-STANDARDS.md` §10 Git Conventions |
| 12 | Use Jira? (y/n) — if yes: Jira base URL + project key | `implr.config.yaml` `jira` block |

**Execution — six deterministic steps:**

1. Ask all questions (one at a time, collect all answers before proceeding)
2. Substitute all answers into the in-memory copies of config files
3. Create all required directories
4. Copy schemas and templates verbatim (plugin-owned; overwrite on re-init)
5. Write substituted config files (implr.config.yaml, DEV-STANDARDS.md, CLAUDE.md) — skip if already present (first init only)
6. Report (created vs already present)

**No step reads an asset file to reason about its contents.** Asset files are treated as opaque
substitution targets. Claude knows which placeholder strings to replace (listed explicitly in
the skill) and applies them in a single pass.

**Substitution targets — explicit list:**

`implr.config.yaml`:
- `REPLACE_ME` under `project.name` → answer 1
- `"REPLACE_ME"` under `project.stack_hint` → answer 2
- `src` under `paths.src` → answer 3 (only if different from default)
- `tests` under `paths.tests` → answer 4 (only if different from default)
- `M` under `behaviour.default_tdd_threshold` → answer 5 (only if different from default)
- `auto_chain_doc_ingest: true` line → remove entirely
- `REPLACE_ME` under `jira.project_key` → answer 12 Jira key (or leave placeholder if Jira skipped)
- `https://your-org.atlassian.net` under `jira.base_url` → answer 12 base URL (or leave if skipped)

`DEV-STANDARDS.md`:
- `e.g. TypeScript 5.x` language line → answers 6
- `e.g. NestJS 10...` framework line → answer 7
- `e.g. Prisma 5, PostgreSQL 16` ORM/DB line → answer 8
- `e.g. Vitest / Jest` test runner line → answer 9
- `[FILL IN] e.g. URL prefix /api/v1...` versioning → answer 10
- `feat/REQ-F-001-slug...` branch prefix example → answer 11

`CLAUDE.md`:
- `REPLACE_ME` → answer 1 (project name)

All other `[FILL IN]` markers in DEV-STANDARDS.md are left for the user — they require
project-specific knowledge beyond what init can collect.

---

## Idempotency Preservation

The rewrite preserves all existing idempotency rules:

| File / folder | First init | Re-init |
|---|---|---|
| Folders | create | leave (no error) |
| schemas/* | copy | overwrite (plugin-owned) |
| templates/* | copy | overwrite (plugin-owned) |
| implr.config.yaml | copy + substitute | leave untouched |
| DEV-STANDARDS.md | copy + substitute | leave untouched |
| CLAUDE.md | copy + substitute | leave untouched |

On re-init, the question phase is skipped for files that already exist. The report clearly
distinguishes created vs already-present.

---

## Out of Scope

- No seed log files added to `assets/` — defensive creation handles this in skill instructions
- No changes to `arch-gen`, `dev-executor`, or `dev-code-review` skills
- No changes to any schema files
- No Jira integration logic changes (jira block in config is populated but the ba-jira-populate skill is unchanged)
- No changes to installer scripts (install.sh / install.ps1 / install.bat)
- No changes to README.md or CONTRIBUTING.md
