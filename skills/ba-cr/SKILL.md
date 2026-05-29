---
name: ba-cr
description: >
  Manages Change Requests (CRs) — structured amendments to existing requirements and plans.
  Use this skill when the user wants to change a requirement, override a constraint, reduce
  scope, correct a misunderstood requirement, or introduce a new rule after requirements have
  already been generated. Also use when the user adds a new KB document that logically
  changes existing requirements (--ingest-file path). Triggers on: change requirement, update
  requirement, override constraint, reduce scope, add new rule, requirement change request,
  cr, change request, I want to change, limit X to Y, adjust requirement, new document
  changes requirements, apply new doc to requirements. Interviews the user to capture the
  change, creates a CR file in docs/kb/change-requests/, chains doc-ingest on that file,
  runs impact analysis across existing requirements and plans, presents an impact report,
  gates on human approval (per-requirement), then chains ba-requirements-gen --reprocess,
  dev-planner --replan, and optionally arch-gen --update for approved items.
---

# ba-cr Skill

You manage Requirement Change Requests. You translate a user's natural-language change
statement into a traceable CR document, identify every requirement and plan affected by the
change, and orchestrate the downstream updates — with a human approval gate before anything
is modified.

You never modify a requirement or plan without explicit approval. You never skip the impact
analysis. You never leave the CR in an inconsistent state.

---

## Reference

Read before executing:
- `docs/implr/schemas/cr-schema.md` — CR file structure, cr-index structure, cr-log structure
- `docs/implr/requirements/cr-index.md` — existing CRs and highest CR number
- `docs/implr/requirements/requirements-index.md` — traceability matrix and requirement titles
- `docs/implr/kb-index/master-synthesis.md` — current system state (used in Phase 0 to
  verify `before` values)

---

## Outputs You Own

```
docs/kb/change-requests/
  CR-NNN-slug.md

docs/implr/requirements/
  cr-index.md
  cr-log.md
```

---

## Parameters

```
/ba-cr                              # interactive interview → full flow
/ba-cr --file <path>                # skip interview; use existing CR file → full flow
/ba-cr --ingest-file <path>         # ingest new KB doc, auto-generate CR, full flow
/ba-cr --impact-only <path>         # impact analysis only; no downstream chains
/ba-cr --dry-run                    # full flow but write nothing and chain nothing
```

---

## Execution Pipeline

### PHASE 0 — Interview (cli-direct path only; skip if --file or --ingest-file)

Accept the user's free-form statement. Extract:

- `title` — derived from the statement
- `change_type` — infer from the statement:
  - cost cap, rate limit, SLA target → `constraint-change`
  - removing functionality → `scope-reduction`
  - adding new functionality → `scope-expansion`
  - new rule → `new-rule`
  - correcting a mistake → `correction`
  - reversing a decision → `override`
- `before` — extract the old value/behaviour from the statement. If not explicit, check
  `master-synthesis.md` for the current value and confirm with the user:
  "I found the current value is X — is that what you're replacing?"
- `after` — extract the new value/behaviour from the statement
- `rationale` — extract from the statement if stated

Ask interactively **only for what is missing**. One question at a time. Minimum questions.
Required fields: `title`, `change_type`, `before`, `after`, `rationale`.

Determine the next CR number by reading `cr-index.md` (highest existing cr_id + 1; CR-001
if none exist).

Write `docs/kb/change-requests/CR-NNN-slug.md` following the CR schema exactly.
Set `source: cli-direct`, `status: draft`, `created_at: {now ISO}`.

Update `cr-index.md`: add a new row with `status: draft` and empty `Applied At`.

Report:
```
📝 CR-NNN created: docs/kb/change-requests/CR-NNN-slug.md
```

### PHASE 0b — KB Document Ingest (--ingest-file path only; skip for /ba-cr and --file)

When invoked as `/ba-cr --ingest-file <path>`:

**Step 1 — Ingest the KB document**

Chain `/doc-ingest --file <path>`. This produces a digest, updates the domain synthesis for
the document's domain, and updates the master synthesis. Wait for completion.

**Step 2 — Extract change signals from the digest**

Read the new per-doc digest at `docs/implr/kb-index/digests/per-doc/{slug}-digest.md`.
Read the updated domain synthesis at `docs/implr/kb-index/domains/{domain}-synthesis.md`.

Extract:
- `title` — from the document's title and domain context
- `change_type` — infer from digest signals:
  - new numeric targets (cost, latency, capacity) → `constraint-change`
  - behaviours present in prior synthesis but absent in new digest → `scope-reduction`
  - new behaviours not in prior synthesis → `scope-expansion`
  - new business rules → `new-rule`
  - corrections to existing rules → `correction`
- `before` — summarise the prior domain synthesis value: "prior behaviour per {domain}-synthesis
  before {slug} was ingested"
- `after` — extract from the new digest's business rules and NFR signals
- `rationale` — derive from the document's stated purpose or the domain synthesis summary

**Step 3 — Auto-create the CR file**

Determine the next CR number from `cr-index.md`. Write
`docs/kb/change-requests/CR-NNN-slug.md` following the CR schema exactly.
Set `source: kb-document`, `status: draft`, `created_at: {now ISO}`.
Update `cr-index.md` with a new row.

Report:
```
📝 CR-NNN auto-generated from: {path}
   Source: kb-document | Change type: {change_type}
   Proceeding to impact analysis...
```

**Step 4 — Ingest the CR file itself**

Chain `/doc-ingest --file docs/kb/change-requests/CR-NNN-slug.md` so the CR is a
first-class KB document with its own digest. Then skip Phase 1 and continue to Phase 2.

### PHASE 1 — doc-ingest (CR file only; --ingest-file skips this — already done in Phase 0b Step 4)

Chain: `/doc-ingest --file docs/kb/change-requests/CR-NNN-slug.md`

This ingests only the CR file. It receives a digest, updates the `change-requests` domain
synthesis, and updates the master synthesis. The CR is now a first-class KB document.

Wait for doc-ingest to complete before continuing.

### PHASE 2 — Impact Analysis

**Step 1 — Domain narrowing**

Read `requirements-index.md` traceability matrix. Use the CR's `change_type`, `before`,
`after`, and the description body to infer which domains are likely affected. Extract
requirement IDs from those domains as candidates. If no domain can be reliably inferred,
treat all requirements as candidates.

**Step 2 — Candidate scan**

For each candidate requirement, read its file. Reason over its domain context, acceptance
criteria, measurable targets, and description to determine:
- Does the `before` value (or a close paraphrase) appear in an AC or measurable target?
- Does the requirement's domain context match the change area?
- Would applying the `after` value change any AC or measurable target?

Classify each candidate as: **confirmed affected** (MEDIUM or HIGH impact), **possibly
affected** (flag for human but do not force apply), or **not affected** (exclude; note why).

Impact levels:
- **HIGH** — a plan exists with status `done` or `in-progress`; the AC directly references
  the changed value
- **MEDIUM** — a plan exists or the AC indirectly references the changed area
- **LOW** — no plan yet; or AC is tangentially related

**Step 3 — Plan lookup**

For each confirmed affected requirement, check whether `PLAN-F-NNN` or `PLAN-N-NNN` exists
and read its current status (`ready`, `in-progress`, `done`, `blocked`).

**Present the impact report:**

```
📋 Impact Report — CR-NNN: {title}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Affected requirements:
  1. REQ-N-002  {title}      plan: PLAN-N-002 (done)      ← HIGH impact
  2. REQ-F-015  {title}      plan: PLAN-F-015 (done)      ← MEDIUM impact
  3. REQ-F-023  {title}      no plan yet                  ← LOW impact

Possibly affected (review recommended):
  4. REQ-F-031  {title}      (indirect reference — verify manually)

Not affected (excluded):
  REQ-N-001  {title}         (constraint not referenced in ACs)
```

### PHASE 3 — Approval Gate

Present the numbered list of confirmed-affected requirements and ask:

```
Apply this CR to which requirements?
  [all]        — apply to all confirmed-affected (1–3 above)
  [1 3]        — apply to selected numbers only
  [none]       — reject; do not apply
```

- **all** — proceed with all confirmed-affected requirements
- **selected** (e.g. "1 3") — apply only to the numbered requirements; note excluded ones
  in cr-log.md
- **none** — set CR `status: rejected`; write cr-log entry; stop

On approval (all or selected):
- CR `status` → `approved`, `approved_at` → now ISO
- `affected_domains` → derived from approved requirements' domain fields
- `jira.components` → set from `affected_domains`
- `jira.linked_issues` → populated from approved requirements' `jira.id` values
  (use `link_type: "relates to"` for each)
- Update cr-index.md row: set `Status: approved`, `Affected Reqs` column

### PHASE 4 — Downstream Chains

Execute in order for each approved requirement:

**4a — ba-requirements-gen**

For each approved requirement, chain:
```
/ba-requirements-gen --reprocess docs/kb/change-requests/CR-NNN-slug.md
```

ba-requirements-gen reads the CR as the triggering source document alongside the affected
requirement file. It applies the change, adds `CR-NNN-slug` to the requirement's
`source_docs` list, drops `status` to `under-review`, and appends a post-implementation
warning to `requirements-log.md` if a plan already exists.

Wait for each reprocess to complete before continuing to the plan step.

**4b — dev-planner**

For each approved requirement that has an existing plan, chain:
```
/dev-planner --replan REQ-NNN
```

Wait for each replan to complete.

**4c — arch-gen (conditional)**

If `affected_domains` includes `architecture` or `infrastructure`, chain:
```
/arch-gen --update
```

**4d — Finalise**

- CR `status` → `applied`, `applied_at` → now ISO
- Update cr-index.md row: `Status: applied`, `Applied At` → now date
- Append run entry to `cr-log.md`

**Final report:**

```
✅ CR-NNN applied
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Requirements updated:   {list, status → under-review}
Plans replanned:        {list, or none}
arch-gen triggered:     yes | no
Excluded from apply:    {list, or none}

Next steps:
  1. Review updated requirements in docs/implr/requirements/
  2. Resolve any open questions and re-approve requirements
  3. Run /dev-executor for any replanned plans ready for implementation
```

---

## Manual-File Trigger (--file path)

When invoked as `/ba-cr --file <path>`:

- Skip Phase 0 entirely
- Read the CR file at the given path
- Confirm `status: draft` before proceeding; if status is already `approved` or `applied`,
  report and stop
- Continue from Phase 1 (doc-ingest) onward

---

## Tone

Active voice. Confirm what you found before asking for decisions. Prefer "I found X — is that
right?" over "What is X?". Never leave the user uncertain about what will be changed or when.
