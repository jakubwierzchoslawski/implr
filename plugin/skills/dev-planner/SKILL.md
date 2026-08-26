---
name: dev-planner
description: >
  Creates implementation plans from approved requirements. Dispatches one plan-worker
  subagent per requirement in parallel (dependent reqs sequenced into waves). Optional
  interactive --brainstorm phase runs in main before dispatch. Cross-requirement coherence
  sweep via built-in Explore subagent. Use when planning approved requirements.
---

# dev-planner Skill (v2.0 orchestrator)

You orchestrate plan generation. `--brainstorm` runs in main; per-requirement planning runs
in parallel `plan-worker` subagents respecting dependency waves.

## Read first

- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`  (stop if missing — tell user to run `/arch-gen` first)
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Preconditions

- `docs/ARCHITECTURE.md` exists (else: `❌ Run /arch-gen first.`).
- Each in-scope requirement is `status: approved` (unless named explicitly / require_approved_status:false).

## Parameters

- `/dev-planner REQ-F-001` — plan one requirement.
- `/dev-planner REQ-F-001 REQ-F-002 REQ-N-001` — plan several (deps respected).
- `/dev-planner --all` — plan all approved requirements without a current plan. **Skips
  requirements that already have a plan** (per v1.x fix).
- `/dev-planner --replan REQ-F-001` — regenerate an existing plan (preserve plan_id). Valid when
  the plan is `ready`, `done`, or `needs-rework`. Regeneration sets the plan back to `ready` and
  clears `rework_cr`/`rework_reason`. This is the ONLY transition out of `needs-rework`.
- `/dev-planner --brainstorm REQ-F-001` — interactive design exploration before planning.
- `/dev-planner --dry-run REQ-F-001` — preview; write nothing.
- `/dev-planner --coherence-check ...` — force the cross-plan coherence sweep (Phase 6). Default: only auto-runs when ≥3 plans generated in this invocation.

## Execution

### Phase 1 — Resolve scope and validate

Read each requirement; verify `status: approved` (unless `require_approved_status: false`).
For `--all`, read `requirements-index.md` and pick approved reqs without an existing plan.

For each in-scope req, check dependencies — every required REQ must have an existing plan.
If not, mark blocked. Surface blockers up front.

When replanning a `needs-rework` plan, read its `rework_cr`/`rework_reason` and incorporate
the CR-driven changes; after writing, set `status: ready` and blank the rework fields.

### Phase 2 — Brainstorm (if `--brainstorm`)

Run interactive design exploration in main:
- Present 2–3 design options per significant decision
- Trade-offs explicit
- User picks
- Capture decisions as a structured list

### Phase 3 — Open-question batching

For each requirement with unresolved open questions, batch-prompt the user:
```
REQ-F-NNN has {n} open questions:
1. ...
2. ...
Resolve, or mark requirement blocked? (resolve / blocked)
```

Update requirement status if user marks blocked.

### Phase 4 — Compute dispatch waves

Build the dependency graph among in-scope reqs (edges = `dependencies[].id`, restricted to
other in-scope reqs).

**Cycle detection (run before topological sort):** Find strongly-connected components of
size ≥ 2 in this graph (e.g. REQ-A depends on REQ-B and REQ-B depends on REQ-A, directly or
via a longer loop). For each cycle found:

- Collapse the whole cycle into a single dispatch group — every req in the cycle enters the
  **same wave**, dispatched together. Do not treat the cycle as a blocker requiring a
  pre-existing plan from a sibling still inside the same cycle.
- Pass each requirement in the group the full list of sibling requirement paths in its cycle
  (`cycle_siblings`) as part of its `plan-worker` scope, so each worker plans with awareness
  of the others it's being planned alongside.
- Record the cycle (member req IDs) for the Phase 8 report. This is a default, silent
  resolution policy — do not stop to ask the user unless `--brainstorm` is active or a cycle
  member also has an unresolved open question (Phase 3 already handles that separately).

After cycles are collapsed to single wave-groups, topological sort the remaining graph
(cycle-groups counted as one node) into waves, where each wave contains reqs/groups whose
dependencies are already planned.

### Phase 5 — Dispatch `plan-worker` per requirement (parallel within wave)

For each wave, dispatch all reqs in parallel (cap 5):

Scope per dispatch: `{requirement_path, plan_path_out, mode, existing_plan_path,
existing_reqs_index, existing_plans_index, brainstorm_decisions, cycle_siblings}`.
`cycle_siblings` is empty unless this req is part of a Phase 4 cycle group.

Wait for the wave to complete before dispatching the next wave.

Aggregate returns. Collect blockers, AC coverage stats, tasks counts.

### Phase 6 — Cross-requirement coherence sweep

**Run this phase ONLY if:**
- `--coherence-check` flag was passed, OR
- The number of plans generated in this invocation is ≥ 3.

Otherwise, skip with one line: `Coherence sweep skipped ({n} plan(s) — pass --coherence-check to force).`

When running: dispatch the built-in `Explore` subagent (read-only) with scope:
"Check plans at <paths> for: duplicate task definitions across plans, missing AC coverage,
inconsistent task ordering vs requirement dependencies."

Include findings in the report; do not modify plans.

### Phase 7 — Update `plans-index.md` and `plans-log.md`

Recount, update tables, add entries.

### Phase 8 — Report

```
🧭 dev-planner complete  (v2.0)
Plans created: {n}    Plans replanned: {n}
Waves dispatched: {n}
Dependency cycles resolved: {n}  {list of cycle groups, e.g. [REQ-F-003, REQ-F-004]}
Blockers: {list}
Average AC coverage: {pct}
Cross-plan findings: {n}

Next steps:
  1. Review docs/implr/plans/plans-index.md
  2. Run /dev-executor --all  (or /dev-executor PLAN-F-NNN)
```

## Failure handling

- `docs/ARCHITECTURE.md` missing → stop immediately:
  ```
  ❌ docs/ARCHITECTURE.md not found. Run /arch-gen first, then re-run dev-planner.
  ```
- Requirement not approved → skip with warning unless explicitly named on command line.
- Plan-worker reports blockers → do not mark plan as ready; surface to user.
- Dependent plan missing → block the dependent requirement; do not stub.
