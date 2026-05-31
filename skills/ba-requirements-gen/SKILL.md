---
name: ba-requirements-gen
description: >
  Generates functional and non-functional requirements from the digested knowledge base.
  Reads syntheses, dispatches one requirements-domain-worker subagent per in-scope domain
  in parallel, assigns sequential IDs after workers return, resolves contradictions in Phase 0, writes
  REQ-F-* and REQ-N-* files. Removed in v2.0: --ingest and --ingest-file flags (run
  /doc-ingest --digest first). Triggers on: generate requirements, create requirements,
  ba requirements, analyse kb, requirements gen.
---

# ba-requirements-gen Skill (v2.0 orchestrator)

You orchestrate requirements generation. Per-domain analysis runs in parallel
`requirements-domain-worker` subagents writing slug-only files to a staging dir; you assign
sequential IDs and finalise after all workers return.

## Read first

- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/kb-index/master-synthesis.md`  (stop if missing — tell user to run /doc-ingest --digest)
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/ba-requirements-gen` — use existing syntheses; no ingest.
- `/ba-requirements-gen --domain <name>` — restrict to one domain.
- `/ba-requirements-gen --reprocess <doc>` — re-derive from a specific source doc (CR file
  supported).
- `/ba-requirements-gen --dry-run` — preview; write nothing; do not advance log state.

**Removed in v2.0** — produce this exact error and stop:

- `--ingest` →
  ```
  ❌ --ingest removed in v2.0.0. Run /doc-ingest --digest first, then /ba-requirements-gen.
  ```
- `--ingest-file <path>` →
  ```
  ❌ --ingest-file removed in v2.0.0. Run /doc-ingest --file <path> --digest first, then /ba-requirements-gen.
  ```

## Execution

### Phase 0 — Contradiction Resolution

Run before Phase 1. Resolves outstanding C-xxx contradictions so workers generate
requirements with correct data — resolved contradictions never become Open Questions.

**Step 1 — Collect C-IDs**

Read every `docs/implr/kb-index/domains/*-synthesis.md` and gather all rows from their
`Contradictions Detected` tables. Read `docs/implr/kb-index/master-synthesis.md` and gather
rows from `Cross-Domain Contradictions`. De-duplicate by C-ID.

**Step 2 — Load existing resolutions**

Read `docs/implr/requirements/resolved-contradictions.md` (skip if absent).
Build `already_handled = resolved_ids ∪ deferred_ids`.

**Step 3 — Prompt for unresolved**

If `already_handled` contains all collected C-IDs: log
`No unresolved contradictions. Skipping Phase 0 interactive prompts.` and proceed
directly to Step 5.

Otherwise, for each C-ID not in `already_handled`, present to user:

```
C-001 [Hard conflict]
Source A: docs/kb/spec-v1.md §3.2 — "Token TTL must be 15 minutes"
Source B: docs/kb/spec-v2.md §1.4 — "Token TTL must be 30 minutes"
Problem:  Auth token TTL: 15 min vs 30 min

Decision (or type 'defer' + reason):
```

**Step 4 — Write resolutions**

Append new rows to `docs/implr/requirements/resolved-contradictions.md` in a
single pass. Resolved decisions go to the `## Resolved` table; deferred items go to the
`## Deferred` table. If the file does not yet exist, create it at
`docs/implr/requirements/resolved-contradictions.md` with this structure:

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

**Step 5 — Build dispatch maps**

After writing (or confirming the file is up to date), re-read the complete
`docs/implr/requirements/resolved-contradictions.md` to build maps reflecting the complete current state of the file (current session plus any prior runs):
- `resolved_map`: `{C-001: {problem: "...", decision: "..."}, ...}` — one entry per Resolved row
- `deferred_list`: `["C-003", "C-004"]` — C-IDs from the Deferred table

Keys in `resolved_map` are normalised to uppercase with no surrounding whitespace (e.g. `C-001`) to ensure reliable lookup.

These are passed to every worker dispatch in Phase 3.

### Phase 1 — Load state and determine scope

Read `requirements-log.md` (create with header if absent). Determine scope:
- `--domain <name>` → one domain
- `--reprocess <doc>` → infer domain from doc path; mode=reprocess
- Otherwise → domains whose synthesis checksum changed since last run, or all domains on
  first run

Read `requirements-index.md` for existing IDs and the highest REQ-F / REQ-N numbers.

### Phase 2 — Create staging area

```
docs/implr/requirements/.staging/
```

If `.staging/` already exists, delete it before proceeding.
- Windows: `cmd /c "rd /s /q <path>"` — do NOT use `Remove-Item -Recurse -Force`; it hangs when files are locked by antivirus or an IDE.
- Unix/macOS: `rm -rf <path>`

### Phase 3 — Dispatch `requirements-domain-worker` per domain (parallel)

For each in-scope domain, dispatch with scope `{domain, synthesis_path, master_synthesis_path,
digests_dir, staging_dir, existing_reqs_index, mode, reprocess_target,
resolved_contradictions, deferred_contradictions}`. Cap parallelism at 5.

Where `resolved_contradictions` is `resolved_map` and `deferred_contradictions` is
`deferred_list` built in Phase 0 Step 5.

Each worker writes to `staging/<domain>/<slug>.md` (functional) or `staging/<domain>/n-<slug>.md`
(non-functional) with empty `req_id` fields.

### Phase 4 — Aggregate returns; collect contradictions and open questions

Sum functional_count, non_functional_count, open_questions, contradictions across all
worker returns.
Note: `contradictions_resolved_via_map` from worker returns is informational only; the
authoritative resolved (`{r}`) and deferred (`{d}`) counts for the Phase 10 report come
from `resolved_map` and `deferred_list` built in Phase 0 Step 5.

If `contradictions_block: true` in config AND any contradictions present, halt and report
to user before any rename/move.

### Phase 5 — Post-hoc ID assignment

For each staged file:
- Read its frontmatter (type: functional or non-functional)
- Allocate next sequential `REQ-F-NNN` or `REQ-N-NNN` continuing from existing highest
- Rewrite `req_id:` field in the staged file
- Move to final path: `docs/implr/requirements/functional/REQ-F-NNN-<slug>.md` or
  `non-functional/REQ-N-NNN-<slug>.md`

All requirements are created with `status: draft`.

### Phase 6 — Updates to existing requirements

If a worker produced a file for a slug that already exists in the final tree (replan path,
or reprocess mode): merge per the existing rules:
- Additive (new AC, new field) or contradictory → drop status from approved to under-review
- Minor clarification → leave status approved
- If a plan exists for the requirement, append the post-implementation warning to
  `requirements-log.md`

### Phase 7 — Update `requirements-index.md`

Recount statistics, update tables, maintain traceability matrix mapping each source doc to
derived REQ IDs.

**"Needs Human Review" section must be derived by reading the actual final REQ files** —
read each moved file's `open_questions` field directly. Do not use worker-return summaries
or synthesis memory: question wording and placement in the files may differ from what
workers reported, causing incorrect REQ↔question associations.

### Phase 8 — Update `requirements-log.md` (skip if `--dry-run`)

Prepend a run entry per schema.

### Phase 9 — Optional coherence sweep

Dispatch the built-in `Explore` subagent (read-only) with scope:
"Cross-check the requirements at <paths> for unresolved cross-references, duplicated AC
sets, or dependency cycles. Report any issues; do not modify files."

Include findings in the report.

### Phase 10 — Report

```
✅ Requirements generation complete  (v2.0)
Domains processed: {list}
Requirements created: {n} ({f} functional, {nfr} non-functional)
Requirements updated: {n}
Contradictions: {r} resolved, {d} deferred in Phase 0
Open questions: {n} (from deferred contradictions and synthesis ambiguities)
Needs your review: {list of REQ ids}
Post-implementation updates: {list, if any}

Next steps:
  1. Review docs/implr/requirements/requirements-index.md
  2. Resolve open questions; set status: approved on ready requirements
  3. Run /dev-planner --all  (or /dev-planner REQ-F-NNN)
```

## Quality gate (enforced by each domain worker)

- Testable Desired Outcome
- ≥ 2 independently verifiable ACs
- ≥ 1 subtask
- ≥ 1 source doc referenced
- NFRs have a quantified Measurable Target
- Deferred contradictions captured as open questions (resolved contradictions are applied as authoritative content — never as open questions)
- ≥ 1 Out of Scope entry
- complexity and tdd_required set; dependencies populated with reasons

## Incremental guarantees

- A domain whose synthesis checksum is unchanged is not reprocessed (unless `--reprocess`).
- `--dry-run` writes nothing and does not advance log state.
- Existing requirements are updated in place (preserve req_id, created_at, jira, status).

## Tone

BA briefing a dev team: active voice, specific, testable, neutral on implementation, always
traceable.
