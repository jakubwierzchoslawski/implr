---
name: ba-cr
description: >
  Creates and applies Change Requests to amend requirements and plans. Interactive CLI
  interview to author a CR (or --file to apply an existing one, or --ingest-file to derive
  one from a new KB doc). Dispatches cr-impact-analyzer for read-only impact analysis,
  then parallel cr-applier subagents to apply diffs to affected requirements and plans
  after user approval.
---

# ba-cr Skill (v2.0 orchestrator)

You orchestrate the Change Request lifecycle. Interview happens in main; impact analysis
runs in `cr-impact-analyzer`; per-target application runs in parallel `cr-applier`s.

## Read first

- `docs/implr/schemas/cr-schema.md`
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/ba-cr` — interactive CLI interview; create a CR, analyse impact, chain updates on approval.
- `/ba-cr --file <path>` — apply a manually-authored CR file.
- `/ba-cr --ingest-file <path>` — ingest a new/updated KB document, auto-generate a CR from
  its digest, apply.
- `/ba-cr --impact-only <path>` — run impact analysis only; do not apply.
- `/ba-cr --dry-run` — preview impact + downstream changes; write nothing.

## Execution

### Phase 1 — Acquire the CR

`ba-cr` is the only path that applies a CR. `/ba-requirements-gen --reprocess` is for
re-deriving from changed KB source documents, not for CRs.

Branch on the parameter:

**Interactive (no flag):** Run the CLI interview in the main context:
- What is the change? (one-line)
- Which requirements does it touch? (or "I'm not sure" → impact-analyzer will find out)
- Why is the change needed? (business / regulatory / technical)
- Before/after for each rule changed
- Acceptance criteria affected
- Risks / out of scope

Compose a CR file at `docs/kb/change-requests/CR-NNN-<slug>.md` per the schema. Allocate
the next sequential CR ID.

**`--file <path>`:** Read the file. Validate against schema. If invalid, report the
fields missing and stop.

**`--ingest-file <path>`:** Ensure the KB document has been ingested with `--digest`
(check `index.md`). If not, prompt the user to run `/doc-ingest --file <path> --digest`
first. Once ingested, read the digest, auto-generate a draft CR from its rule changes,
present to the user for review before continuing.

### Phase 2 — Dispatch `cr-impact-analyzer`

Resolve model. Dispatch with scope `{cr_path, requirements_dir, plans_dir}`.

Read the return summary. If `--impact-only`, print and stop.

### Phase 3 — Present impact and get approval

```
📋 CR-NNN impact:
Affected requirements: {list with change_kind, current_status → proposed_status}
Affected plans: {list with action: none/patch/replan}
New requirements proposed: {n}
Contradictions with existing: {n}
Risks: {n}

Approve and apply?
  all      — apply to every affected requirement/plan
  selected — you pick which requirement IDs to apply; the rest are excluded this run
  none     — do not apply (optionally save impact report)
  impact-only — save the impact report to the CR and stop
```

If `--dry-run`, print and stop without dispatching appliers.

On `selected`, prompt for the requirement IDs to apply. Record `applied_targets` (chosen)
and `excluded_targets` (the rest of `confirmed_targets`). On `none`/`impact-only`, stop
without applying.

Write the full `confirmed_targets` set to the CR file's `targets:` frontmatter. Set the CR
`status: approved` and stamp `approved_at: <ISO timestamp>`.

### Phase 4 — Dispatch `cr-applier` per applied target (parallel)

For each requirement in `applied_targets` and each plan linked to those requirements:
- Resolve model
- Dispatch `cr-applier` with scope `{cr_path, target_path, target_kind, action, status_change}`
- Cap parallelism at 5

### Phase 5 — Handle replan markers

For plans the applier set to `needs-rework`, queue them. After all appliers
return, present the user with:
```
The following plans need replanning: {list}
Run /dev-planner --replan {list} now? (yes / no)
```

If yes, invoke `/dev-planner --replan` for each.

### Phase 6 — Stamp CR, write logs and indices

1. If every dispatched applier succeeded: set the CR file `status: applied` and stamp
   `applied_at: <ISO timestamp>`. If any applier failed: leave `status: approved` and do not
   stamp applied_at.
2. Prepend an entry to `docs/implr/requirements/cr-log.md` per cr-schema.md, including
   `Applied targets` and `Excluded targets` for this run, and any failures.
3. Add/update the CR row in `cr-index.md`.
4. Append entries to `requirements-log.md` for each applied requirement and to `plans-log.md`
   for each affected plan.

### Phase 7 — Report

```
✅ CR-NNN applied  (v2.0)
Title: ...
Affected: {f} requirements, {p} plans
Status changes: {summary}
Replan needed: {list of plans}
Open questions added: {n}
```

## Failure handling

- CR file invalid → stop with field list.
- Impact analyzer returns empty (no affected targets) → warn user; still allow apply for
  documentation purposes.
- Applier fails on one target → report which; leave successfully-applied targets applied; do
  NOT roll back; do NOT stamp the CR `applied`. Record the failure in `cr-log.md`. The CR
  stays `approved` so a re-run can complete it.
