# Phase: plan-one

Dispatch prompt for `plan-worker`.

## Read first
- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
requirement_path: {{REQUIREMENT_PATH}}
plan_path_out: {{PLAN_PATH_OUT}}
mode: {{MODE}}                                # create | replan
existing_plan_path: {{EXISTING_PLAN_PATH}}    # only when mode=replan
existing_reqs_index: docs/implr/requirements/requirements-index.md
existing_plans_index: docs/implr/plans/plans-index.md
brainstorm_decisions:
{{DECISIONS_BLOCK}}
cycle_siblings: {{CYCLE_SIBLINGS}}   # empty list unless this req is part of a Phase 4 cycle group
```

## Task
Produce one plan file per agent system prompt. Surface blockers; do not stub missing
dependency plans. If `cycle_siblings` is non-empty, those requirements are being planned in
this same wave precisely because they mutually depend on each other — do not treat a sibling's
absent plan as a blocker; instead plan against the sibling's requirement file directly (already
available via `existing_reqs_index`) and note the mutual-dependency handling in the plan's
notes/assumptions.

## Return summary
(plan-worker report per agent system prompt)
