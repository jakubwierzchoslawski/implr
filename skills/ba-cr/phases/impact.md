# Phase: impact

Dispatch prompt for `cr-impact-analyzer`.

## Read first
- `docs/implr/schemas/cr-schema.md`
- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/schemas/plan-schema.md`

## Your scope
```
cr_path: {{CR_PATH}}
requirements_dir: docs/implr/requirements/
plans_dir: docs/implr/plans/
```

## Task
Analyse impact of the CR across all requirements and plans. Read-only.

## Return summary
```
cr_id: CR-NNN
target_summary: <one-line>
affected_requirements:
  - id: REQ-F-NNN
    change_kind: additive | contradictory | scope_expansion | scope_cut | rewording
    current_status: <status>
    proposed_status: <status>
    plan_exists: true | false
    plan_action: none | patch | replan
  - ...
affected_plans:
  - id: PLAN-F-NNN
    action: none | patch | replan
    reason: <short>
new_requirements_proposed: <n>
contradictions_with_existing: <n>
risks:
  - <short description of each material risk>
```
