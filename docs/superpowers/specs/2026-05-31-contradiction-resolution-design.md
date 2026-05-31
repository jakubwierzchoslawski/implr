# Contradiction Resolution — Design (2026-05-31)

## Overview

Contradictions between knowledge-base documents are currently detected at synthesis time and
assigned C-xxx IDs, but the IDs are lost when `requirements-domain-worker` converts them into
unnamed Open Questions in REQ files. If the same contradiction affects multiple requirements,
dev-planner asks the user the same question multiple times. There is no consolidated record
of decisions.

This spec adds a **Phase 0** to `ba-requirements-gen` that resolves all outstanding C-xxx
contradictions before any requirement is generated, and persists decisions in a new
`resolved-contradictions.md` file. Workers receive the resolved map and generate requirements
with correct data from the start — deferred items are the only contradictions that become
Open Questions.

---

## Goals and Non-Goals

**Goals**
- Resolve each contradiction once, before requirements are generated.
- Persist decisions in `docs/implr/requirements/resolved-contradictions.md`.
- Propagate resolutions automatically to all affected requirements (no repeated prompts).
- Preserve deferred contradictions as Open Questions with their C-ID intact.
- Keep `requirements-index.md` "Needs Human Review" clean: only genuinely unresolved items.
- Make re-runs fast: already-resolved/deferred C-IDs are skipped.

**Non-Goals**
- No changes to synthesis files (domain-synthesis, master-synthesis, digest-log are immutable
  records of the kb state — they are never updated with decisions).
- No changes to dev-planner (deferred contradictions still reach it as Open Questions).
- No changes to doc-ingest or any other skill outside ba-requirements-gen and its worker.
- No `--resolve-only` flag (YAGNI — can be added later if needed).

---

## New File: `resolved-contradictions.md`

Lives at `docs/implr/requirements/resolved-contradictions.md` alongside
`requirements-index.md` and `cr-index.md`.

Schema is defined in `scaffold/schemas/kb-index-schema.md`.

### Structure

```markdown
# Resolved Contradictions
> Maintained by ba-requirements-gen. To change a decision, edit this file and re-run `/ba-requirements-gen`.

## Resolved
| C-ID  | Type          | Source A                | Source B                | Problem                          | Decision                      | Resolved   |
|-------|---------------|-------------------------|-------------------------|----------------------------------|-------------------------------|------------|
| C-001 | Hard conflict | docs/kb/spec-v1.md §3.2 | docs/kb/spec-v2.md §1.4 | Auth token TTL: 15 min vs 30 min | Use 30-minute auth token TTL  | 2026-05-31 |

## Deferred
| C-ID  | Type          | Source A            | Source B            | Problem                         | Notes                     | Deferred   |
|-------|---------------|---------------------|---------------------|---------------------------------|---------------------------|------------|
| C-003 | Scope overlap | docs/kb/roadmap.md  | docs/kb/mvp.md      | Feature X: in MVP scope or not? | Needs product owner input | 2026-05-31 |
```

### Column definitions

**Resolved table**

| Column | Source | Notes |
|--------|--------|-------|
| C-ID | domain synthesis | Assigned at synthesis time |
| Type | domain synthesis | Hard conflict / Soft conflict / Version drift / Scope overlap |
| Source A | domain synthesis | File path + section if available |
| Source B | domain synthesis | File path + section if available |
| Problem | domain synthesis contradiction description | Short summary, copied verbatim |
| Decision | user input during Phase 0 | Authoritative; used by workers |
| Resolved | date Phase 0 ran | ISO date |

**Deferred table**

Same columns except `Decision` is replaced by `Notes` (user's reason for deferring) and
`Resolved` is replaced by `Deferred`.

### Idempotency rules

- File is **append-only**. Re-running `ba-requirements-gen` never overwrites existing rows.
- Only new C-IDs (absent from both tables) are presented in Phase 0.
- To change a decision: edit the file manually and re-run `ba-requirements-gen`.

---

## `ba-requirements-gen` Changes

### New Phase 0 — Contradiction Resolution

Runs before any worker is dispatched. Inserted before the current Phase 1.

**Steps:**

1. Collect all C-xxx IDs from:
   - `docs/implr/kb-index/domains/*/domain-synthesis.md` → `Contradictions Detected` tables
   - `docs/implr/kb-index/master-synthesis.md` → `Cross-Domain Contradictions` table
   De-duplicate by C-ID.

2. Read `docs/implr/requirements/resolved-contradictions.md` (skip if absent).
   Build `already_handled = resolved_ids ∪ deferred_ids`.

3. For each C-ID not in `already_handled`, present to user:
   ```
   C-001 [Hard conflict]
   Source A: docs/kb/spec-v1.md §3.2 — "Token TTL must be 15 minutes"
   Source B: docs/kb/spec-v2.md §1.4 — "Token TTL must be 30 minutes"
   Problem:  Auth token TTL: 15 min vs 30 min

   Decision (or type 'defer' + reason):
   ```

4. Collect all answers, then write/append to `resolved-contradictions.md` in a single pass.

5. If zero unresolved C-IDs exist → log "No unresolved contradictions. Skipping Phase 0."
   and continue immediately.

### Phase 4 — Worker dispatch (updated)

Each worker dispatch scope gains two new fields:

```
resolved_contradictions: { C-001: { problem: "...", decision: "..." }, ... }
deferred_contradictions: ["C-003", "C-004"]
```

These are built from `resolved-contradictions.md` immediately after Phase 0.

### Phase 7 — requirements-index.md (updated)

"Needs Human Review" is populated by scanning REQ files for non-empty Open Questions —
behavior unchanged. After a clean Phase 0 the section will only contain deferred
contradictions and genuine synthesis ambiguities; resolved contradictions will not appear.

---

## `requirements-domain-worker` Changes

Workers receive `resolved_contradictions` and `deferred_contradictions` in their dispatch
scope. When a domain synthesis contains a C-xxx reference, workers apply this rule:

| Contradiction state | Worker action |
|---------------------|---------------|
| In `resolved_contradictions` | Use `decision` as authoritative content. Do NOT create an Open Question. |
| In `deferred_contradictions` | Create an Open Question: `Source: C-xxx (deferred)`, question text = problem summary. |
| Not a contradiction (regular ambiguity) | Existing behavior — create Open Question as before. |

The C-ID is preserved in the `Source` column of deferred Open Questions so dev-planner
users can trace the question back to its origin.

---

## Installer Changes

### New seed file

`scaffold/seeds/resolved-contradictions.md` — empty tables, same structure as the schema.

```markdown
# Resolved Contradictions
> Maintained by ba-requirements-gen. To change a decision, edit this file and re-run `/ba-requirements-gen`.

## Resolved
| C-ID | Type | Source A | Source B | Problem | Decision | Resolved |
|------|------|----------|----------|---------|----------|----------|

## Deferred
| C-ID | Type | Source A | Source B | Problem | Notes | Deferred |
|------|------|----------|----------|---------|-------|----------|
```

### Copy rule

| Source | Destination | Rule |
|--------|-------------|------|
| `scaffold/seeds/resolved-contradictions.md` | `docs/implr/requirements/resolved-contradictions.md` | Skip if exists |

Applies to `install.sh`, `install.ps1`, and `install.bat`.

---

## Schema Changes (`kb-index-schema.md`)

Add a new `## resolved-contradictions.md` section documenting the two-table structure,
column definitions, and idempotency rules. Position it after the `requirements-index.md`
section.

---

## `docs/WORKFLOW.md` Changes

Update the **Contradiction Detection** section:

- Describe the full C-xxx lifecycle: detection → synthesis → Phase 0 resolution → worker
  generation.
- Explain `resolved-contradictions.md` and its role.
- Clarify that deferred contradictions propagate as Open Questions; resolved ones do not.
- Remove the stale note about adding schemas/templates under `skills/implr-init/assets/`
  (now `scaffold/`).

---

## `README.md` Changes

- In the Full Pipeline table, add `resolved-contradictions.md` as an output of
  `/ba-requirements-gen`.
- In the skill description for `/ba-requirements-gen`, mention Phase 0 (contradiction
  resolution).

---

## Complete File Change List

| File | Action |
|------|--------|
| `scaffold/schemas/kb-index-schema.md` | Add `resolved-contradictions.md` schema section |
| `scaffold/seeds/resolved-contradictions.md` | New seed file (empty tables) |
| `install.sh` | Copy seed with skip-if-exists |
| `install.ps1` | Copy seed with skip-if-exists |
| `install.bat` | Copy seed with skip-if-exists |
| `skills/ba-requirements-gen/SKILL.md` | Add Phase 0; update Phase 4 dispatch scope; update Phase 7 notes |
| `.claude/agents/requirements-domain-worker.md` | Accept resolved/deferred maps; apply resolution rule |
| `docs/WORKFLOW.md` | Update Contradiction Detection section; fix stale assets path |
| `README.md` | Minor: mention resolved-contradictions.md in pipeline output |
