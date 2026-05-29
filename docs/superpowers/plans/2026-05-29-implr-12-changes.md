# implr 12 Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply 12 targeted fixes to the implr skill suite, fixing missing log initialisation, an under-interactive implr-init, broken ingest defaults, and several ba-requirements-gen / dev-planner behavioural gaps.

**Architecture:** All changes are edits to Markdown skill instruction files and one YAML config template. No code is written; each task is a precise text replacement or insertion. Bottom-up order: safest/most isolated changes first, full implr-init rewrite last.

**Tech Stack:** Markdown, YAML — no dependencies beyond a text editor and git.

---

## File Map

| File | Tasks that touch it |
|------|---------------------|
| `skills/doc-ingest/SKILL.md` | Task 1 |
| `skills/ba-requirements-gen/SKILL.md` | Tasks 2, 6, 8, 9, 10 |
| `docs/WORKFLOW.md` | Tasks 3, 4, 10 |
| `skills/dev-planner/SKILL.md` | Tasks 5, 7, 10 |
| `skills/implr-init/assets/config/implr.config.yaml` | Task 6 |
| `skills/implr-init/SKILL.md` | Task 11 |

---

## Phase 1 — Safe / Isolated Changes

---

### Task 1: doc-ingest — defensive log file creation

**Files:**
- Modify: `skills/doc-ingest/SKILL.md` (PHASE 8, lines 150-153)

- [ ] **Step 1: Open the file and locate PHASE 8**

  Confirm the current text of PHASE 8 reads exactly:

  ```
  ### PHASE 8 — Update digest-log.md (skip writing if --dry-run)

  Prepend a run entry: timestamp, trigger, mode, files processed with checksums and actions,
  domains rebuilt, whether master was rebuilt, contradictions detected, warnings.
  ```

- [ ] **Step 2: Replace PHASE 8 text**

  Replace the block above with:

  ```
  ### PHASE 8 — Update digest-log.md (skip writing if --dry-run)

  If `docs/implr/kb-index/digest-log.md` does not exist, create it now with this header:

  ```
  # digest-log
  # Append-only run history for doc-ingest. Newest entry first.
  # Format: see kb-index-schema.md § digest-log entry.
  ```

  Then prepend a run entry: timestamp, trigger, mode, files processed with checksums and
  actions, domains rebuilt, whether master was rebuilt, contradictions detected, warnings.
  ```

- [ ] **Step 3: Verify**

  Read lines 148-160 of `skills/doc-ingest/SKILL.md`. Confirm the "does not exist, create it" guard appears before the "Prepend a run entry" sentence and that PHASE 9 header is still intact immediately after.

- [ ] **Step 4: Commit**

  ```
  git add skills/doc-ingest/SKILL.md
  git commit -m "fix(doc-ingest): create digest-log.md on first write if absent"
  ```

---

### Task 2: ba-requirements-gen — defensive log file creation

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md` (PHASE 6, lines 129-132)

- [ ] **Step 1: Locate PHASE 6**

  Confirm current text reads:

  ```
  ### PHASE 6 — Update requirements-log.md (skip if --dry-run)

  Prepend a run entry: timestamp, trigger, domains processed (with synthesis checksums),
  requirements created/updated, contradictions surfaced, open questions raised.
  ```

- [ ] **Step 2: Replace PHASE 6 text**

  Replace with:

  ```
  ### PHASE 6 — Update requirements-log.md (skip if --dry-run)

  If `docs/implr/requirements/requirements-log.md` does not exist, create it now with this
  header:

  ```
  # requirements-log
  # Append-only run history for ba-requirements-gen. Newest entry first.
  # Format: see requirement-schema.md § requirements-log entry.
  ```

  Then prepend a run entry: timestamp, trigger, domains processed (with synthesis checksums),
  requirements created/updated, contradictions surfaced, open questions raised.
  ```

- [ ] **Step 3: Verify**

  Read lines 127-140 of `skills/ba-requirements-gen/SKILL.md`. Confirm the guard block appears before "prepend a run entry" and PHASE 7 header follows immediately.

- [ ] **Step 4: Commit**

  ```
  git add skills/ba-requirements-gen/SKILL.md
  git commit -m "fix(ba-requirements-gen): create requirements-log.md on first write if absent"
  ```

---

### Task 3: WORKFLOW.md — document text cache rationale

**Files:**
- Modify: `docs/WORKFLOW.md` (after "Why digests exist" subsection, before "---" at line 88)

- [ ] **Step 1: Locate the insertion point**

  Find the line that reads:

  ```
  This mirrors how a human BA works: read the briefing, then go to source only for the details
  that matter.

  ---

  ## Contradiction Detection
  ```

- [ ] **Step 2: Insert new subsection**

  Replace the `---` separator between "Why digests exist" and "Contradiction Detection" with:

  ```
  This mirrors how a human BA works: read the briefing, then go to source only for the details
  that matter.

  ### Why the text cache exists

  - **Extract once, read many times.** Binary and structured formats (PDF, DOCX, XLSX, CSV)
    require external tool invocations (`pdftotext`, `python-docx`, `openpyxl`) — expensive to
    repeat on every skill run.
  - **Checksum gate.** doc-ingest writes `cache/{slug}.txt` once per file and records the source
    checksum. On subsequent runs, if the checksum is unchanged, the cache is read directly —
    no tool invocation needed.
  - **One consistent read path.** `.md` and `.txt` files are straight copies into cache, but
    having a single path (`cache/{slug}.txt`) means every downstream skill (ba-requirements-gen,
    arch-gen) never needs to know the original format or invoke extraction tools.
  - **Never read the binary original downstream.** Skills always read from cache. If a cache
    entry is absent for a file that is needed, the skill flags it as an Open Question rather
    than attempting to read the raw binary.

  ---

  ## Contradiction Detection
  ```

- [ ] **Step 3: Verify**

  Read the "Incremental Processing" section of `docs/WORKFLOW.md`. Confirm "Why the text cache exists" appears between "Why digests exist" and "Contradiction Detection" with correct markdown heading level (###).

- [ ] **Step 4: Commit**

  ```
  git add docs/WORKFLOW.md
  git commit -m "docs(workflow): document text cache rationale"
  ```

---

### Task 4: WORKFLOW.md — index vs log role clarification

**Files:**
- Modify: `docs/WORKFLOW.md` (after "What Each Skill Reads and Writes" section, before "Extending implr")

- [ ] **Step 1: Locate the insertion point**

  Find the line that reads:

  ```
  ---

  ## Extending implr
  ```

  (This separator appears after the "What Each Skill Reads and Writes" table and its note.)

- [ ] **Step 2: Insert new section before "Extending implr"**

  Replace:

  ```
  ---

  ## Extending implr
  ```

  With:

  ```
  ---

  ## Log Files vs Index Files

  Two files that sound similar but serve distinct purposes:

  **`requirements-index.md`** — current-state register:
  - What requirements exist right now: IDs, titles, statuses, dependencies, linked plans
  - Traceability matrix (source document → requirement IDs)
  - "Needs Human Review" section for open questions and unresolved contradictions
  - Read by: dev-planner (to find approved requirements), humans tracking status

  **`requirements-log.md`** — append-only history:
  - Every ba-requirements-gen run, timestamped
  - Which domain syntheses were processed and their checksums at processing time
  - Which requirements were created or updated in each run
  - Contradictions surfaced and post-implementation update warnings
  - Read by: ba-requirements-gen as its incremental gate — without it, ba-requirements-gen
    cannot know which synthesis checksums it last processed and would reprocess everything

  The same pattern applies to `digest-log.md` (owned by doc-ingest): it is the history record,
  not the index. `index.md` is the current state of the KB file registry.

  ---

  ## Extending implr
  ```

- [ ] **Step 3: Verify**

  Read the bottom portion of `docs/WORKFLOW.md`. Confirm "Log Files vs Index Files" section appears between "What Each Skill Reads and Writes" and "Extending implr", with correct ## heading level.

- [ ] **Step 4: Commit**

  ```
  git add docs/WORKFLOW.md
  git commit -m "docs(workflow): clarify requirements-index vs requirements-log roles"
  ```

---

### Task 5: dev-planner — explicit --all skip logic

**Files:**
- Modify: `skills/dev-planner/SKILL.md` (PHASE 0, lines 67-72)

- [ ] **Step 1: Locate PHASE 0**

  Confirm current text of PHASE 0 reads:

  ```
  ### PHASE 0 — Validate input

  For each target requirement:
  - File exists; `status: approved` (else skip with a clear message, unless
    `require_approved_status` is false in config)
  - Load it fully: acceptance criteria, data models, process sequence, dependencies, linked NFRs
  ```

- [ ] **Step 2: Replace PHASE 0 text**

  Replace with:

  ```
  ### PHASE 0 — Validate input

  For each target requirement:
  - File exists; `status: approved` (else skip with a clear message, unless
    `require_approved_status` is false in config)
  - Load it fully: acceptance criteria, data models, process sequence, dependencies, linked NFRs

  **`--all` skip rule:** Before processing any requirement under `--all`, check whether a
  matching plan file already exists (`docs/implr/plans/functional/PLAN-F-NNN-*.md` or
  `docs/implr/plans/non-functional/PLAN-N-NNN-*.md`) with `status: ready`, `in-progress`, or
  `done`. If yes, skip it and emit:

  ```
  ⏭  REQ-F-001 — already has PLAN-F-001 (ready). Skipping.
     Use --replan REQ-F-001 to regenerate.
  ```

  Only `status: blocked` does not protect an existing plan — it is treated as if no plan
  exists and planning proceeds. A plan file that does not exist at all always triggers planning.
  ```

- [ ] **Step 3: Verify**

  Read lines 65-85 of `skills/dev-planner/SKILL.md`. Confirm the `--all` skip rule block appears inside PHASE 0 and PHASE 1 header is still intact immediately after.

- [ ] **Step 4: Commit**

  ```
  git add skills/dev-planner/SKILL.md
  git commit -m "fix(dev-planner): --all explicitly skips requirements that already have a plan"
  ```

---

## Phase 2 — Parameter Interface Changes

---

### Task 6: ba-requirements-gen — flip ingest default + remove config key

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md` (Parameters section + PHASE 0)
- Modify: `skills/implr-init/assets/config/implr.config.yaml` (remove auto_chain_doc_ingest)

- [ ] **Step 1: Update the Parameters section**

  Find and replace the entire Parameters block:

  ```
  ## Parameters

  - `/ba-requirements-gen` — default: chain doc-ingest, then generate from new/changed content
  - `/ba-requirements-gen --no-ingest` — skip the doc-ingest chain; use existing syntheses as-is
  - `/ba-requirements-gen --domain <name>` — generate only for one domain
  - `/ba-requirements-gen --reprocess <doc>` — re-derive requirements from a specific source doc
  - `/ba-requirements-gen --dry-run` — preview; write nothing, do not advance log state
  ```

  Replace with:

  ```
  ## Parameters

  - `/ba-requirements-gen` — use existing syntheses as-is; no ingest step
  - `/ba-requirements-gen --ingest` — run full doc-ingest on the KB first, then generate
  - `/ba-requirements-gen --ingest-file <path>` — ingest one specific file first, then generate
  - `/ba-requirements-gen --domain <name>` — generate only for one domain
  - `/ba-requirements-gen --reprocess <doc>` — re-derive requirements from a specific source doc
  - `/ba-requirements-gen --dry-run` — preview; write nothing, do not advance log state
  ```

- [ ] **Step 2: Update PHASE 0**

  Find and replace the entire PHASE 0 block:

  ```
  ### PHASE 0 — Chain doc-ingest (unless --no-ingest)

  If `auto_chain_doc_ingest` is true in config and `--no-ingest` is not set, run the doc-ingest
  skill first to ensure syntheses are current. Capture which domains changed.

  ```
  🔄 Step 0: Running doc-ingest to refresh the knowledge base...
  ```

  If `--no-ingest`, skip and use existing syntheses. If no master synthesis exists at all, stop
  and tell the user to run doc-ingest.
  ```

  Replace with:

  ```
  ### PHASE 0 — Optionally chain doc-ingest

  If `--ingest` was passed, run the doc-ingest skill in full before continuing. Capture which
  domains changed.

  If `--ingest-file <path>` was passed, run doc-ingest with `--file <path>` only. Capture
  whether the file's domain synthesis changed.

  ```
  🔄 Step 0: Running doc-ingest to refresh the knowledge base...
  ```

  If neither flag was passed, skip ingest entirely and proceed with existing syntheses.

  In all cases: if no master synthesis exists at all, stop and tell the user to run
  `/doc-ingest` first.

  **Ambiguity propagation:** doc-ingest writes ambiguities detected during synthesis into each
  domain synthesis under an "Ambiguities Detected" section. When ba-requirements-gen reads a
  domain synthesis in PHASE 2, it checks this section. For each ambiguity it either resolves
  it from `cache/{slug}.txt` (if the cached text is unambiguous) or surfaces it as an Open
  Question citing the source document. Ambiguities are never silently discarded.
  ```

- [ ] **Step 3: Remove auto_chain_doc_ingest from config template**

  In `skills/implr-init/assets/config/implr.config.yaml`, find and remove this line:

  ```
    auto_chain_doc_ingest: true      # ba-requirements-gen runs doc-ingest first by default
  ```

  The `behaviour:` block should read after the removal:

  ```
  behaviour:
    default_tdd_threshold: M         # complexity at/above which TDD is enforced (XS/S skip)
    require_approved_status: true    # dev-planner only processes approved requirements
    contradictions_block: false      # false = generate with open questions; true = halt on conflict
    kb_supported_formats: [md, pdf, docx, xlsx, csv, txt]
  ```

- [ ] **Step 4: Verify**

  Read the Parameters section and PHASE 0 of `skills/ba-requirements-gen/SKILL.md`. Confirm:
  - `--no-ingest` is gone
  - `--ingest` and `--ingest-file` are present
  - PHASE 0 no longer references `auto_chain_doc_ingest`
  - Ambiguity propagation note is present

  Read `skills/implr-init/assets/config/implr.config.yaml`. Confirm `auto_chain_doc_ingest` line is absent.

- [ ] **Step 5: Commit**

  ```
  git add skills/ba-requirements-gen/SKILL.md skills/implr-init/assets/config/implr.config.yaml
  git commit -m "fix(ba-requirements-gen): flip ingest default to explicit --ingest flag; remove auto_chain_doc_ingest config key"
  ```

---

### Task 7: dev-planner — open question batching and blocked status

**Files:**
- Modify: `skills/dev-planner/SKILL.md` (PHASE 1, lines 74-91)

- [ ] **Step 1: Locate PHASE 1**

  Confirm current PHASE 1 ends with:

  ```
  Write each answer back into the requirement's Open Questions table as `✅ {date}: {decision}`,
  bump `updated_at`, and continue. Only proceed once all are resolved.
  ```

- [ ] **Step 2: Replace PHASE 1 text**

  Find the entire PHASE 1 block:

  ```
  ### PHASE 1 — Resolve open questions (interactive)

  For each unresolved Open Questions row (`Resolved` is `☐`), present it to the user one at a time:

  ```
  ⚠️  REQ-F-007 has unresolved open questions. Resolving before planning.

  Question 1 of 2:
  {question}

  Source of ambiguity:
  {the conflict or gap, with document references}

  Your decision:
  ```

  Write each answer back into the requirement's Open Questions table as `✅ {date}: {decision}`,
  bump `updated_at`, and continue. Only proceed once all are resolved.
  ```

  Replace with:

  ```
  ### PHASE 1 — Resolve open questions (interactive)

  For each unresolved Open Questions row (`Resolved` is `☐`), present it to the user one at a time:

  ```
  ⚠️  REQ-F-007 has unresolved open questions. Resolving before planning.

  Question 1 of 2:
  {question}

  Source of ambiguity:
  {the conflict or gap, with document references}

  Your decision:
  ```

  Write each answer back into the requirement's Open Questions table as `✅ {date}: {decision}`,
  bump `updated_at`, and continue. Only proceed once all are resolved.

  **Edge cases:**

  **Contradiction (two source documents conflict):** Present both sources and the conflict
  explicitly. Ask the user to decide. Write the decision back as `✅ {date}: {decision}`. Never
  guess the resolution.

  **Gap (information missing from the KB entirely):** Present the question. If the user answers
  inline, record it and continue. If the user says "proceed anyway", create the plan with
  `status: blocked` and leave the open question flagged as unresolved — never guess the answer.

  **Coherence failure across requirements (e.g. entity name in REQ-F-001 does not match
  REQ-F-002):** Stop. Tell the user exactly which field names or concepts need to be aligned
  and in which requirement files. Do not generate any plan for the affected requirements until
  they are corrected and re-approved.

  **Many open questions across multiple requirements:** Batch by requirement. Resolve all open
  questions for REQ-F-001 fully before moving to REQ-F-002. Never present questions from
  different requirements in the same exchange.

  **`--all` with mixed requirements:** Process requirements that have no open questions first,
  generating their plans without interruption. Then pause and present each requirement with open
  questions individually. Report clearly at the end what was planned and what still needs
  resolution:

  ```
  ✅ Planned: PLAN-F-001, PLAN-F-003
  ⏸  Paused (open questions to resolve):
     REQ-F-002 — 2 questions  →  resolve then re-run /dev-planner REQ-F-002
     REQ-F-005 — 1 question   →  resolve then re-run /dev-planner REQ-F-005
  ```
  ```

- [ ] **Step 3: Verify**

  Read lines 74-120 of `skills/dev-planner/SKILL.md`. Confirm all five edge-case rules are present inside PHASE 1 and PHASE 2 header follows immediately.

- [ ] **Step 4: Commit**

  ```
  git add skills/dev-planner/SKILL.md
  git commit -m "fix(dev-planner): add open question batching rules and blocked status for unresolvable gaps"
  ```

---

## Phase 3 — Behavioural Changes

---

### Task 8: ba-requirements-gen — explicit deep-dive conditions

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md` (PHASE 2, lines 90-92)

- [ ] **Step 1: Locate the deep-dive paragraph**

  Find the exact text:

  ```
  **Deep-dive only when needed:** when a domain synthesis flags an ambiguity, or when writing
  detailed acceptance criteria or data models requires specifics, read the per-doc digest and, if
  still insufficient, the raw cached text for that document. Do not read all raw docs.
  ```

- [ ] **Step 2: Replace with explicit conditions**

  Replace with:

  ```
  **When synthesis is sufficient (do not deep-dive):**
  - Information needed is behavioural: user journeys, business rules, what the system must do —
    the digest captures this fully
  - No field-level data models are needed beyond what the "Data Entities" section provides
  - No precise wording from contracts, regulations, or SLAs is required

  **Go to `cache/{slug}.txt` when any of these is true:**
  - The domain synthesis has an "Ambiguities Detected" section flagging this document
  - A requirement needs field-level data models not captured in the digest entities
  - An NFR needs a specific numeric target that the digest paraphrased vaguely (e.g. "high
    performance" with no figure)
  - The digest `word_count` is very low relative to the topic's apparent complexity (signals
    under-extraction from a sparse or complex source document)
  - The quality gate cannot be met: cannot write 2 independently testable ACs from the
    synthesis alone

  **If no cache entry exists for a file you need to deep-dive:** flag the gap as an Open
  Question citing the document and the specific missing information. Never attempt to read the
  raw binary original. Never fail the run.

  Do not read all raw docs. Deep-dive only on the specific documents that trigger one of the
  conditions above.
  ```

- [ ] **Step 3: Verify**

  Read PHASE 2 of `skills/ba-requirements-gen/SKILL.md`. Confirm the explicit "sufficient" and "go to cache" rule blocks are present and the old one-liner is gone. Confirm PHASE 3 header follows.

- [ ] **Step 4: Commit**

  ```
  git add skills/ba-requirements-gen/SKILL.md
  git commit -m "fix(ba-requirements-gen): replace vague deep-dive hint with explicit conditions"
  ```

---

### Task 9: ba-requirements-gen — requirement inference reasoning

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md` (PHASE 2, after the deep-dive rules block, before PHASE 3)

- [ ] **Step 1: Locate the insertion point**

  Find the text that ends PHASE 2 (the line immediately before `### PHASE 3 — Contradictions`):

  ```
  Do not read all raw docs. Deep-dive only on the specific documents that trigger one of the
  conditions above.

  ### PHASE 3 — Contradictions
  ```

- [ ] **Step 2: Insert inference reasoning section**

  Replace the above with:

  ```
  Do not read all raw docs. Deep-dive only on the specific documents that trigger one of the
  conditions above.

  **Inferring unstated requirements:**

  Real documentation describes a business domain, not system requirements. Bridge from domain
  description to requirements using these reasoning patterns:

  - **From user journeys:** if a doc describes "a customer selects products and completes a
    purchase", requirements for cart management, payment initiation, order confirmation, and
    confirmation email are all implied — none may be stated explicitly. Derive them from the
    narrative.
  - **From entity lifecycles:** if `Invoice` is defined with statuses `draft`, `sent`, `paid`,
    `overdue`, then requirements to transition between each state are implied even if no
    "the system shall change invoice status" sentence exists.
  - **From integration mentions:** "the system notifies customers by email" implies an
    email-sending requirement even without an email service specification.
  - **From NFR signals:** "must handle high traffic during sales events" → create a Performance
    NFR. Estimate the measurable target from context clues, or flag it as needing specification
    in the Open Questions if no figure can be reasonably inferred.
  - **When truly ambiguous:** if the requirement cannot be reasonably inferred without guessing,
    create it as `status: draft` with a populated Open Question: cite the source document and
    state exactly what information would resolve the ambiguity.

  The quality gate (2 testable ACs minimum) is the forcing function: if you cannot write
  concrete, independently verifiable ACs from the synthesis plus any cached text, you must
  either create an Open Question or produce a minimal draft explicitly flagging the gap.

  ### PHASE 3 — Contradictions
  ```

- [ ] **Step 3: Verify**

  Read PHASE 2 and PHASE 3 of `skills/ba-requirements-gen/SKILL.md`. Confirm the inference reasoning block sits between the deep-dive rules and the PHASE 3 header. Confirm the five bullet patterns are present.

- [ ] **Step 4: Commit**

  ```
  git add skills/ba-requirements-gen/SKILL.md
  git commit -m "feat(ba-requirements-gen): document requirement inference reasoning patterns"
  ```

---

### Task 10: post-implementation update flow (three files)

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md` (PHASE 4 + PHASE 7)
- Modify: `skills/dev-planner/SKILL.md` (PHASE 4)
- Modify: `docs/WORKFLOW.md` (new section before "Extending implr")

#### Part A — ba-requirements-gen PHASE 4

- [ ] **Step 1: Locate end of PHASE 4**

  Find the line that currently closes PHASE 4:

  ```
  All requirements are created with `status: draft`.
  ```

- [ ] **Step 2: Append post-implementation update logic to PHASE 4**

  Replace:

  ```
  All requirements are created with `status: draft`.
  ```

  With:

  ```
  All requirements are created with `status: draft`.

  **When updating an existing requirement** (not creating new):

  - If the update is additive (new AC, new field) or contradictory (the implementation may now
    be wrong): drop `status` from `approved` to `under-review`. Do not drop to `draft` — the
    requirement was previously reviewed and that history is preserved.
  - If the update is a minor clarification only (no new ACs, no change to described behaviour):
    leave `status: approved`.
  - Check whether a plan file `PLAN-F-NNN` or `PLAN-N-NNN` exists for this requirement.
  - If a plan exists, append the following warning line to `requirements-log.md`:

    ```
    ⚠️  {REQ-ID} updated post-implementation: {one-line summary of what changed}.
        {PLAN-ID} exists (status: {plan status}). Human review needed.
    ```
  ```

#### Part B — ba-requirements-gen PHASE 7 report

- [ ] **Step 3: Locate PHASE 7 report block**

  Find the closing lines of the PHASE 7 report template:

  ```
  Needs your review:
    ⚠️  REQ-F-003 — {title} (contradiction: auth-flow.md vs security-policy.md)

  Next steps:
    1. Review docs/implr/requirements/requirements-index.md
    2. Resolve open questions and set status: approved on ready requirements
    3. Run /dev-planner REQ-F-001  (or /dev-planner --all)
  ```

- [ ] **Step 4: Add post-implementation updates heading to report**

  Replace with:

  ```
  Needs your review:
    ⚠️  REQ-F-003 — {title} (contradiction: auth-flow.md vs security-policy.md)

  Post-implementation updates (requirement changed after planning/execution):
    ⚠️  REQ-F-007 — {title} → now under-review. PLAN-F-007 exists (done). Review needed.

  Next steps:
    1. Review docs/implr/requirements/requirements-index.md
    2. Resolve open questions and set status: approved on ready requirements
    3. Run /dev-planner REQ-F-001  (or /dev-planner --all)
  ```

  (The "Post-implementation updates" section only renders when there are such updates; omit it
  when empty.)

- [ ] **Step 5: Commit ba-requirements-gen changes**

  ```
  git add skills/ba-requirements-gen/SKILL.md
  git commit -m "feat(ba-requirements-gen): detect and warn on post-implementation requirement updates"
  ```

#### Part C — dev-planner PHASE 4 warning block

- [ ] **Step 6: Locate start of PHASE 4 in dev-planner**

  Find:

  ```
  ### PHASE 4 — Generate plans

  Process in topological order. For each requirement, write a complete plan following the schema.
  ```

- [ ] **Step 7: Insert under-review warning rule**

  Replace with:

  ```
  ### PHASE 4 — Generate plans

  Process in topological order. For each requirement, write a complete plan following the schema.

  **If the requirement has `status: under-review`** (set by ba-requirements-gen after a
  post-implementation update), insert this warning block at the very top of the generated plan
  file, before any other content:

  ```
  ⚠️  SOURCE REQUIREMENT UPDATED AFTER IMPLEMENTATION
      Requirement updated: {updated_at date from requirement frontmatter}
      Summary of change:   {one-line summary from the requirements-log warning entry}
      Review whether the existing implementation still satisfies the updated requirement
      before re-executing this plan.
  ```

  Do NOT automatically set the plan to `blocked` or trigger re-review. Surface the conflict;
  leave the decision to the human. The human then either re-approves the requirement as-is
  (no re-planning needed) or runs `/dev-planner --replan {REQ-ID}`.
  ```

- [ ] **Step 8: Commit dev-planner change**

  ```
  git add skills/dev-planner/SKILL.md
  git commit -m "feat(dev-planner): add post-implementation update warning to plans for under-review requirements"
  ```

#### Part D — WORKFLOW.md invocation flow

- [ ] **Step 9: Locate insertion point in WORKFLOW.md**

  Find the separator and heading (added by Task 4 — Task 4 must be complete before this step):

  ```
  ---

  ## Log Files vs Index Files
  ```

- [ ] **Step 10: Insert the post-implementation scenario section before "Log Files vs Index Files"**

  Replace:

  ```
  ---

  ## Log Files vs Index Files
  ```

  With:

  ```
  ---

  ## When a New Document Changes an Existing Requirement

  The most important real-world scenario: a new document is added to `docs/kb/` after a
  requirement has already been planned and possibly implemented.

  ```
  1. /doc-ingest --file docs/kb/new-policy.md
     → detects new doc, rebuilds domain synthesis, flags any contradiction

  2. /ba-requirements-gen
     → sees changed domain synthesis
     → updates REQ-F-007: new AC added + open question for contradiction
     → drops status from approved → under-review
     → appends warning to requirements-log.md
     → reports: "REQ-F-007 updated. PLAN-F-007 exists (done). Human review needed."

  3. Human reviews REQ-F-007 and the warning
     Option A: new AC is additive, existing code handles it
               → set status: approved; no re-planning needed
     Option B: new policy changes described behaviour
               → set status: approved; run /dev-planner --replan REQ-F-007

  4. /dev-planner --replan REQ-F-007    (only if Option B)
  5. /dev-executor PLAN-F-007           (implements the delta)
  6. /dev-code-review PLAN-F-007        (reviews)
  ```

  Key rules:
  - ba-requirements-gen never drops an `approved` requirement back to `draft` — only to
    `under-review`, preserving the review history
  - dev-planner never automatically invalidates a plan — it adds a visible warning and leaves
    the decision to the human
  - Only material changes (new ACs, changed behaviour) trigger `under-review`; minor
    clarifications leave `approved` untouched

  ---

  ## Log Files vs Index Files
  ```

- [ ] **Step 11: Verify all three files**

  - Read PHASE 4 and PHASE 7 of `skills/ba-requirements-gen/SKILL.md` — confirm update logic and report section present.
  - Read PHASE 4 of `skills/dev-planner/SKILL.md` — confirm warning block present and "do NOT set blocked" instruction present.
  - Read `docs/WORKFLOW.md` — confirm "When a New Document Changes an Existing Requirement" section appears before "Log Files vs Index Files" with 6-step flow.

- [ ] **Step 12: Commit WORKFLOW.md**

  ```
  git add docs/WORKFLOW.md
  git commit -m "docs(workflow): document post-implementation requirement update invocation flow"
  ```

---

## Phase 3 — Most Invasive Change

---

### Task 11: implr-init — full rewrite as pure executor

**Files:**
- Modify: `skills/implr-init/SKILL.md` (Steps 1-7 execution section, entire body below the Asset Source section)

This is a full replacement of the Execution and Idempotency sections. The frontmatter, description, and Asset Source section are preserved unchanged.

- [ ] **Step 1: Identify the section to replace**

  The content to replace starts at `## Execution` (line 53) and runs to the end of the file (line 152). The Asset Source section above it (lines 27-51) is preserved.

- [ ] **Step 2: Replace the Execution section**

  Find:

  ```
  ## Execution

  ### Step 1 — Detect project root and pre-flight
  ```

  Replace everything from that line to the end of file with:

  ```
  ## Execution

  You are a pure executor. You ask questions, collect answers, substitute values, create
  directories, copy files, report. You do not narrate, reason aloud, or deep-read asset files.
  Asset files are opaque substitution targets — you know which placeholder strings to replace
  and you apply them in one pass.

  ---

  ### Step 0 — Collect answers (one question at a time)

  Before any file operation, ask the user these questions one at a time in this order. Accept
  the default silently if the user presses enter with no input on questions that have one.

  | # | Question | Default | Target |
  |---|----------|---------|--------|
  | 1 | Project name? | _(required)_ | `implr.config.yaml` `project.name` + `CLAUDE.md` |
  | 2 | Tech stack? (e.g. "Python, FastAPI, PostgreSQL") | _(required)_ | `implr.config.yaml` `project.stack_hint` |
  | 3 | Source folder? | `src` | `implr.config.yaml` `paths.src` |
  | 4 | Tests folder? | `tests` | `implr.config.yaml` `paths.tests` |
  | 5 | Default TDD threshold — M / L / XL? | `M` | `implr.config.yaml` `behaviour.default_tdd_threshold` |
  | 6 | Language + version? (e.g. "Python 3.12") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
  | 7 | Framework? (e.g. "FastAPI 0.111") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
  | 8 | ORM + DB? (e.g. "SQLAlchemy 2, PostgreSQL 16") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
  | 9 | Test runner? (e.g. "pytest") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
  | 10 | API versioning strategy? (e.g. "URL prefix /api/v1") | _(required)_ | `DEV-STANDARDS.md` §7 API Design |
  | 11 | Git branch prefix convention? (e.g. "feat/", "feature/") | `feat/` | `DEV-STANDARDS.md` §10 Git Conventions |
  | 12 | Use Jira? (y/n) | `n` | — |
  | 13 | _(only if Q12 = y)_ Jira base URL? | — | `implr.config.yaml` `jira.base_url` |
  | 14 | _(only if Q12 = y)_ Jira project key? | — | `implr.config.yaml` `jira.project_key` |

  On **re-init** (docs/implr/ already exists): skip this step entirely — config files are
  never overwritten, so questions have no target to write to.

  ---

  ### Step 1 — Detect project root and pre-flight

  Confirm the working directory is the intended project root. If `docs/implr/` already exists,
  this is a re-init — proceed in idempotent mode (fill gaps only) and tell the user.

  ---

  ### Step 2 — Create folder structure

  Create these directories (no error if they already exist):

  ```
  docs/kb/
  docs/implr/config/
  docs/implr/schemas/
  docs/implr/templates/
  docs/implr/kb-index/cache/
  docs/implr/kb-index/digests/per-doc/
  docs/implr/kb-index/domains/
  docs/implr/requirements/functional/
  docs/implr/requirements/non-functional/
  docs/implr/plans/functional/
  docs/implr/plans/non-functional/
  docs/implr/reviews/
  ```

  ---

  ### Step 3 — Copy schemas and templates (plugin-owned — overwrite on re-init)

  Copy every file from `assets/schemas/` into `docs/implr/schemas/`.
  Copy every file from `assets/templates/` into `docs/implr/templates/`.
  Overwrite on re-init — these are plugin-owned; user customisation lives in DEV-STANDARDS.md
  and implr.config.yaml.

  ---

  ### Step 4 — Write substituted config files (first init only — never overwrite)

  For each file below: if it does not already exist at the target path, read it from assets,
  apply the substitutions listed, and write it to the target. If it already exists, skip it
  and add it to the "Already present" list in the report.

  **`docs/implr/config/implr.config.yaml`** ← from `assets/config/implr.config.yaml`

  Substitutions (apply all in one pass):
  - `REPLACE_ME` under `project.name` → answer 1
  - `"REPLACE_ME"` under `project.stack_hint` → `"{answer 2}"`
  - value under `paths.src` → answer 3 (skip if default `src`)
  - value under `paths.tests` → answer 4 (skip if default `tests`)
  - value under `behaviour.default_tdd_threshold` → answer 5 (skip if default `M`)
  - `REPLACE_ME` under `jira.project_key` → answer 14 if Jira enabled, else leave as-is
  - `https://your-org.atlassian.net` under `jira.base_url` → answer 13 if Jira enabled, else leave as-is

  **`docs/implr/config/DEV-STANDARDS.md`** ← from `assets/config/DEV-STANDARDS.md`

  Substitutions (apply all in one pass):
  - `e.g. TypeScript 5.x` (Language line in §1) → answer 6
  - `e.g. NestJS 10 / Express 4 / Fastify 4` (Framework line in §1) → answer 7
  - `e.g. Prisma 5, PostgreSQL 16` (ORM/DB line in §1) → answer 8
  - `e.g. Vitest / Jest` (Test runner line in §1) → answer 9
  - `[FILL IN] e.g. URL prefix /api/v1 or header API-Version` (Versioning line in §7) → answer 10
  - `feat/REQ-F-001-slug, fix/REQ-F-001-slug, chore/description` (Branch line in §10) → `{answer 11}REQ-F-001-slug` (adjust example to use provided prefix)

  All other `[FILL IN]` markers in DEV-STANDARDS.md are left for the user — they require
  project-specific knowledge that cannot be collected at init time.

  **`CLAUDE.md`** ← from `assets/templates/CLAUDE-template.md`

  Substitutions:
  - `REPLACE_ME` → answer 1 (project name)

  ---

  ### Step 5 — Report

  ```
  ✅ implr initialised
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Created:
    📁 docs/kb/                         (your knowledge base — add docs here)
    📁 docs/implr/                      (plugin workspace)
    📄 docs/implr/config/implr.config.yaml
    📄 docs/implr/config/DEV-STANDARDS.md
    📄 docs/implr/schemas/              (5 schema files)
    📄 docs/implr/templates/            (5 templates)
    📄 CLAUDE.md

  Already present (left untouched):
    {list any skipped files}

  Remaining [FILL IN] sections in DEV-STANDARDS.md (open in your editor):
    §2 Folder Structure
    §3 Naming Conventions
    §4 Architecture Patterns (DI, Error Handling, Validation)
    §9 Logging and Observability
    §11 Environment Configuration

  Next steps:
    1. Complete the remaining [FILL IN] sections of docs/implr/config/DEV-STANDARDS.md
    2. Add your documentation (.md, .pdf, .docx, .xlsx, .csv, .txt) to docs/kb/
    3. Run /doc-ingest to index and digest your knowledge base
    4. Run /arch-gen to generate docs/ARCHITECTURE.md
    5. Run /ba-requirements-gen to generate requirements
  ```

  ---

  ## Idempotency Rules

  | File / folder | First init | Re-init |
  |---------------|-----------|---------|
  | Folders | create | leave (no error) |
  | schemas/* | copy | overwrite (plugin-owned) |
  | templates/* | copy | overwrite (plugin-owned) |
  | implr.config.yaml | copy + substitute | leave untouched |
  | DEV-STANDARDS.md | copy + substitute | leave untouched |
  | CLAUDE.md | copy + substitute | leave untouched |

  Never delete anything. Never touch `docs/kb/` contents. Never touch `src/` or `tests/`.
  ```

- [ ] **Step 3: Verify**

  Read `skills/implr-init/SKILL.md` in full. Confirm:
  - Step 0 (questions table) is present and lists 14 questions including the conditional Jira pair
  - Step 4 (substitutions) lists all targets explicitly — no `REPLACE_ME` references remain as vague instructions
  - Step 5 (report) lists "Remaining [FILL IN] sections" so the user knows what still needs manual editing
  - Old narrative prose ("you are careful and idempotent...", "Then interactively ask the user for:") is gone
  - Idempotency table is still present

- [ ] **Step 4: Commit**

  ```
  git add skills/implr-init/SKILL.md
  git commit -m "feat(implr-init): rewrite as pure executor with upfront questions and explicit substitution targets"
  ```

---

## Final Verification

- [ ] **Check all 12 changes are covered**

  | Change | Task | Commit |
  |--------|------|--------|
  | 1 — defensive log creation | Tasks 1 + 2 | ✓ |
  | 2 — implr-init interactive questions | Task 11 | ✓ |
  | 3+4 — implr-init pure executor | Task 11 | ✓ |
  | 5 — cache rationale docs | Task 3 | ✓ |
  | 6 — explicit deep-dive conditions | Task 8 | ✓ |
  | 7 — flip ingest default + config key | Task 6 | ✓ |
  | 8 — inference reasoning | Task 9 | ✓ |
  | 9 — post-implementation update flow | Task 10 | ✓ |
  | 10 — index vs log clarification | Task 4 | ✓ |
  | 11 — --all skip logic | Task 5 | ✓ |
  | 12 — open question batching + blocked | Task 7 | ✓ |

- [ ] **Verify no REPLACE_ME or [FILL IN] leaks into skill instructions**

  ```
  grep -r "REPLACE_ME" skills/
  grep -r "\[FILL IN\]" skills/implr-init/SKILL.md
  ```

  The first grep should return nothing. The second should return nothing (all `[FILL IN]` markers live in the DEV-STANDARDS.md asset, not in SKILL.md instructions).

- [ ] **Verify auto_chain_doc_ingest is fully removed**

  ```
  grep -r "auto_chain_doc_ingest" skills/ docs/
  ```

  Should return no matches.
