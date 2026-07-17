# Phase: apply

Dispatch prompt for `cr-applier`. One dispatch per applied target: each requirement in
`applied_targets` (the subset the human approved this run, not the full `confirmed_targets`
impact set) and each plan linked to those requirements.

## Read first
- `docs/implr/schemas/cr-schema.md`
- The schema for your target (`requirement-schema.md` or `plan-schema.md`)
- `docs/implr/config/implr.config.yaml`

## Your scope
```
cr_path: {{CR_PATH}}
target_path: {{TARGET_PATH}}
target_kind: {{TARGET_KIND}}      # requirement | plan
action: {{ACTION}}                # patch | replan
status_change: {{STATUS_CHANGE}}
```

## Task
Apply the CR change exactly as described in the CR's `before`/`after` fields. Update
`source_docs` and `status` per scope.

## Return summary
```
target_path: <path>
target_kind: requirement | plan
action_applied: patch | replan | needs_rework_set
fields_changed:
  - source_docs
  - status: <old> → <new>
  - acceptance_criteria: +<n>
status: applied | needs-rework
```
