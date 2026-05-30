# Phase: apply

Dispatch prompt for `cr-applier`. One dispatch per affected target.

## Read first
- `docs/implr/schemas/cr-schema.md`
- The schema for your target (`requirement-schema.md` or `plan-schema.md`)

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
(applier report per agent system prompt)
