# Design Spec: ba-cr — Change Request Skill

**Date:** 2026-05-30  
**Status:** Approved for implementation  
**Author:** jakubwierzchoslawski

---

## Problem

Requirements and plans in implr are generated from KB documents. When a user wants to change
a requirement directly (e.g. "limit Azure costs to $20–50/month" instead of the $500/month
baked into existing requirements and plans), there is no structured path to do so. The user
must either edit requirement files manually (losing traceability) or create a KB document and
re-run the full pipeline (losing the targeted, change-scoped nature of the update).

---

## Solution Overview

Introduce a **Change Request (CR)** artefact and a new **`ba-cr`** skill that:

1. Interviews the user to capture the change in natural language
2. Creates a CR file in `docs/kb/change-requests/` (first-class KB document, fully traceable)
3. Ingests the CR through doc-ingest (CR only)
4. Analyses impact across existing requirements and plans
5. Presents an impact report and asks for approval (per-requirement granularity)
6. On approval, chains `ba-requirements-gen --reprocess`, `dev-planner --replan`, and
   optionally `arch-gen --update`

A second entry point: users who prefer to author CR files manually can drop them into
`docs/kb/change-requests/` and run `/doc-ingest`. Doc-ingest detects the new file and prompts
the user to run `/ba-cr --file <path>` to trigger the impact and apply flow.

---

## Approach Selected

**Approach B — ba-cr creates the CR, chains doc-ingest + impact analysis, stops at approval gate.**

- ba-cr is responsible for the CR lifecycle up to and including downstream chains
- doc-ingest is unchanged except for detecting new CR files and emitting a prompt
- ba-jira-populate (future) pushes CRs to Jira using the `jira:` block in the CR schema
- The human approval gate is explicit and per-requirement — the user can approve all,
  approve selected, or reject

---

## CR Schema

Location: `docs/kb/change-requests/CR-NNN-slug.md`

```markdown
---
cr_id: CR-001
slug: azure-cost-cap-reduction
title: Reduce Azure Monthly Cost Cap from $500 to $20–50
status: draft           # draft | approved | rejected | applied
change_type: constraint-change
                        # constraint-change | scope-reduction | scope-expansion
                        # new-rule | correction | override
source: cli-direct      # cli-direct | manual-file | kb-document
affected_domains: []    # populated by ba-cr after impact analysis
before: "$500/month Azure cost ceiling"   # auto-extracted by ba-cr from user input
after: "$20–50/month Azure cost ceiling"  # auto-extracted by ba-cr from user input
rationale: ""           # captured during ba-cr interview if not provided
created_at: {ISO timestamp}
approved_at:            # stamped when human approves
applied_at:             # stamped when all downstream chains complete
jira:
  id:                   # filled by ba-jira-populate (e.g. PROJ-99)
  issue_type: Task      # Task or Story depending on project convention
  priority: Medium      # derived from change_type severity
  labels: [change-request]
  components: []        # derived from affected_domains after impact analysis
  story_points:         # blank until estimated
  epic_link:            # optional, if CR belongs to an epic
  linked_issues: []     # populated after impact analysis
                        # [{id: PROJ-12, link_type: "relates to"}]
---

# CR-001 — Reduce Azure Monthly Cost Cap from $500 to $20–50

## Description of Change
Plain-language explanation of what is changing and why.

## Expected Impact (Human Note, optional)
Human's own assessment of what this will touch.
```

**Schema rules:**
- `before` and `after` are auto-extracted by ba-cr from natural language input, not entered
  by the user directly. They play the role of a structured description and are used during
  impact analysis to match constraint values in requirement files.
- `rationale` is the one field ba-cr asks for explicitly if it cannot be derived from the
  user's statement.
- `jira.linked_issues` is populated after impact analysis confirms affected requirements,
  linking to their Jira IDs.
- `affected_domains` is initially empty; ba-cr populates it after impact analysis.
- For `kb-document` source, `before`/`after` and `rationale` are auto-extracted from the
  new document's digest rather than from user input. No interview is conducted — the digest
  provides the signal for what changed.

---

## ba-cr Skill Flow

### Parameters

```
/ba-cr                              # interactive interview → create CR → full flow
/ba-cr --file CR-NNN.md             # skip interview, apply an existing CR file
/ba-cr --ingest-file <path>         # ingest new KB doc, auto-generate CR, full flow
/ba-cr --impact-only CR-NNN.md      # impact analysis only, no downstream chains
/ba-cr --dry-run                    # full flow but write nothing, chain nothing
```

### Phase 0 — Interview (cli-direct path only)

Accept the user's free-form statement. Extract:
- `title` — derived from the statement
- `change_type` — inferred (e.g. cost cap → `constraint-change`)
- `before` / `after` — extracted from the statement where possible; if `before` is not
  explicit, ba-cr checks the master-synthesis for the current value and confirms with the
  user before writing it
- `rationale` — the user's stated reason, if any

Ask interactively **only for what is missing** from required fields. One question at a time.
Minimum questions.

Write `docs/kb/change-requests/CR-NNN-slug.md` with `status: draft`, `source: cli-direct`.
Update `cr-index.md` with a new row.

### Phase 0b — KB Document Ingest (--ingest-file path only)

When invoked as `/ba-cr --ingest-file <path>`:

1. Chain `/doc-ingest --file <path>` to ingest the new KB document. This produces a digest,
   updates the domain synthesis for that document's domain, and updates the master synthesis.

2. Read the resulting domain synthesis diff. Extract from the digest:
   - `title` — derived from the document's title and its domain
   - `change_type` — inferred from the digest's business rules and NFR signals:
     - new numeric targets → `constraint-change`
     - removed behaviours → `scope-reduction`
     - new behaviours not in prior synthesis → `scope-expansion`
     - new business rules → `new-rule`
     - corrections to existing rules → `correction`
   - `before` — prior domain synthesis value for the changed area (read from the existing
     synthesis before the ingest run, or summarised as "prior behaviour per {domain}-synthesis")
   - `after` — new value from the fresh digest
   - `rationale` — derived from the document's stated purpose or context

3. Auto-create `docs/kb/change-requests/CR-NNN-slug.md` with `source: kb-document`,
   `status: draft`. Write the extracted values; do not interview the user.
   Update `cr-index.md` with a new row.

4. Report:
   ```
   📝 CR-NNN auto-generated from: {path}
      Source: kb-document | Change type: {change_type}
      Proceeding to impact analysis...
   ```

5. Continue directly to Phase 2 (skip Phase 1 — the KB doc is already ingested).
   Chain `/doc-ingest --file docs/kb/change-requests/CR-NNN-slug.md` to ingest the CR file
   itself for traceability, then proceed to Phase 2.

### Phase 1 — doc-ingest (CR file only; skip for --ingest-file after step 5 above)

Chain `/doc-ingest --file docs/kb/change-requests/CR-NNN-slug.md`.

Only the CR file is ingested. It receives a digest, updates the `change-requests` domain
synthesis, and updates the master synthesis. The CR is now a first-class KB document with
full traceability.

### Phase 2 — Impact Analysis

**Step 1 — Domain narrowing:** Read the requirements-index traceability matrix. Use the
CR's domain keywords and the `change-requests` domain synthesis to identify candidate
requirement IDs. If no domain can be derived, all requirements are candidates.

**Step 2 — Candidate scan:** Read each candidate requirement file. Reason over its domain
context, ACs, and measurable targets to determine whether the changed constraint (the
`before` value, keywords from the CR description) is referenced. Confirm or exclude each
candidate.

**Step 3 — Plan lookup:** For each confirmed affected requirement, check whether a
`PLAN-F-NNN` or `PLAN-N-NNN` exists and its current status.

**Impact report presented to the user:**

```
📋 Impact Report — CR-001: Reduce Azure Monthly Cost Cap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Affected requirements:
  REQ-N-002  Azure Cost Constraint NFR      plan: PLAN-N-002 (done)    ← HIGH impact
  REQ-F-015  Infrastructure Provisioning    plan: PLAN-F-015 (done)    ← MEDIUM impact
  REQ-F-023  Monitoring & Alerting          no plan yet                ← LOW impact

Not affected (reviewed, excluded):
  REQ-N-001  Response Time SLA             (cost constraint not referenced)
```

### Phase 3 — Approval Gate

Ask: approve all, approve selected, or reject.

- **Approve all** — proceeds with all confirmed affected requirements
- **Approve selected** — ba-cr lists each affected requirement by number; user states which
  to include (e.g. "1 and 3"); others are skipped and noted in cr-log.md as excluded
- **Reject** — CR `status` set to `rejected`; nothing downstream runs

On approval: CR `status` → `approved`, `approved_at` stamped,
`jira.linked_issues` populated from approved requirements' Jira IDs,
`affected_domains` updated from confirmed candidates.

### Phase 4 — Downstream Chains (on approval)

Executed in order for each approved requirement:

1. `/ba-requirements-gen --reprocess <CR-file>` — ba-requirements-gen treats the CR as
   the triggering source document. It reads the CR alongside the affected requirement and
   applies the change, drops `status` to `under-review`, appends a post-implementation
   warning to `requirements-log.md` if a plan exists. The CR `cr_id` is added to the
   requirement's `source_docs` list so the traceability chain is preserved.
2. `/dev-planner --replan REQ-NNN` — regenerates the plan for each affected requirement
   that has an existing plan
3. `/arch-gen --update` — triggered only if `affected_domains` includes `architecture` or
   `infrastructure`

CR `status` → `applied`, `applied_at` stamped when all chains complete.
`cr-log.md` entry appended.

---

## Manual-File Trigger

If the user drops a CR file manually into `docs/kb/change-requests/` and runs
`/doc-ingest`, doc-ingest detects the `change-requests/` subfolder as a special domain.
After ingesting the file it emits:

```
⚠️  New change request detected: CR-NNN-slug.md
    Run /ba-cr --file docs/kb/change-requests/CR-NNN-slug.md to analyse impact and apply.
```

Doc-ingest does **not** auto-chain ba-cr. The user must explicitly run `/ba-cr --file ...`.

**Manual-file path (full sequence):**
```
1. Create CR-NNN.md (using cr-template.md as a guide)
2. Drop it into docs/kb/change-requests/
3. /doc-ingest                                            ← ingests file, emits prompt
4. /ba-cr --file docs/kb/change-requests/CR-NNN-slug.md  ← you trigger this explicitly
```

This two-step sequence must be documented in WORKFLOW.md and README.md.

---

## New Artefacts

### `docs/implr/requirements/cr-index.md`

Current-state register for all CRs. Mirrors the pattern of `requirements-index.md`.

```markdown
# CR Index
> Maintained by ba-cr. Do not edit manually.

## Change Requests

| CR ID  | Title                    | Status   | Change Type       | Affected Reqs        | Applied At |
|--------|--------------------------|----------|-------------------|----------------------|------------|
| CR-001 | Reduce Azure Cost Cap    | applied  | constraint-change | REQ-N-002, REQ-F-015 | 2026-05-30 |

## Pending Human Action
  ⚠️  CR-002 approved but not yet applied — run /ba-cr --file CR-002-gdpr-retention.md
```

### `docs/implr/requirements/cr-log.md`

Append-only run history. Each ba-cr run appends: timestamp, CR ID, phases executed,
requirements updated, plans replanned, arch-gen triggered (yes/no).

---

## State Flows

These state flows must be documented in detail in `WORKFLOW.md` and referenced from
`README.md`. They are the authoritative lifecycle for each artefact.

### Requirement states (existing)
```
draft → under-review → approved → superseded
                     ↘ rejected
```
- ba-requirements-gen creates `draft`
- Humans promote to `under-review` or `approved`
- ba-cr can drop `approved` → `under-review` (never to `draft`)
- `superseded` requires `superseded_by` pointing to the replacement requirement

### Plan states (existing)
```
ready → in-progress → done
  ↑                     │
  └── changes-required ◄┘
blocked → ready
```
- dev-planner creates `ready`
- dev-executor sets `in-progress` → `done`
- dev-code-review can set `changes-required` → returns plan to `in-progress`
- `blocked` set when a dependency is unresolved; cleared manually or by dev-planner

### CR states (new)
```
draft → approved → applied
      ↘ rejected
```
- ba-cr creates `draft` after interview
- Human approves or rejects at the approval gate (Phase 3)
- ba-cr sets `applied` after all downstream chains complete
- A `rejected` CR is terminal — create a new CR to supersede it

---

## Changes to Existing Skills

### implr-init

Scaffold on initialisation:
- `docs/kb/change-requests/` (with `.gitkeep`)
- `docs/implr/schemas/cr-schema.md`
- `docs/implr/templates/cr-template.md`
- `docs/implr/requirements/cr-index.md` (empty table)

### doc-ingest

Two additions to PHASE 9 — Report:

**1. Change request detection** — if any NEW file lives under `docs/kb/change-requests/`,
emit:
```
⚠️  New change request detected: {filename}
    Run /ba-cr --file docs/kb/change-requests/{filename} to analyse impact and apply.
```

**2. New KB document hint** — if any NEW file lives under `docs/kb/` (outside
`change-requests/`) and requirements already exist (`requirements-index.md` is non-empty),
emit a non-blocking hint:
```
💡 New KB document ingested: {filename}
   If this document changes existing requirements, run:
   /ba-cr --ingest-file {original_path}
```

Neither prompt auto-chains ba-cr. Both are informational only. The hint for regular KB docs
fires only when requirements already exist — on a fresh project with no requirements yet,
it is suppressed.

### ba-jira-populate (future skill)

When it runs, push any `status: approved` or `status: applied` CR entries from `cr-index.md`
as Jira Tasks, with `linked_issues` populated. No change needed now — the CR schema already
carries the full `jira:` block.

### WORKFLOW.md

Add the following content (do not replace existing content):
- "Change Requests" section: CLI path, manual-file path, and KB-document path (`--ingest-file`),
  with explicit step sequences for each
- Full state flow diagrams for requirement, plan, and CR (see State Flows above)
- Update the artefact graph to include the CR input path

### README.md

Add:
- `ba-cr` row in the skills table
- "Changing Requirements" section in the workflow narrative, covering both trigger paths
- Reference to `WORKFLOW.md` for full state flow details (not duplicated inline)

---

## Updated Artefact Graph

```
docs/kb/**                          source documents (you own these)
docs/kb/change-requests/CR-NNN.md  change requests (you own these)
   │
   ▼  doc-ingest
docs/implr/kb-index/
   │
   ├──▶ ba-cr (impact + approval + chains)
   │       │
   │       ├──▶ ba-requirements-gen --reprocess  (affected reqs → under-review)
   │       ├──▶ dev-planner --replan             (affected plans regenerated)
   │       └──▶ arch-gen --update               (only if architecture domain touched)
   │
   ▼  ba-requirements-gen
docs/implr/requirements/
   │
   ▼  dev-planner
docs/implr/plans/
   │
   ▼  dev-executor
src/**  tests/**
   │
   ▼  dev-code-review
docs/implr/reviews/
```

Traceability chain extended:
`CR file → digest → synthesis → ba-cr → requirement update → plan update → code → review`

---

## Out of Scope

- Auto-chaining ba-cr from doc-ingest (doc-ingest prompts and hints, but never chains ba-cr)
- Merging or grouping multiple CRs into a single apply run (each CR is applied independently)
- CR versioning or amendment (a rejected CR is terminal; create a new CR to replace it)
- ba-jira-populate implementation (schema contract already defined; skill is future work)
- Automatic diff computation between old and new KB document versions (ba-cr reads the
  domain synthesis diff, not a raw file diff — structural changes in the domain are the signal)
