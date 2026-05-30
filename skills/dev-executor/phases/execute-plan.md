# Phase: execute-plan

Dispatch prompt for `executor-worker`. One dispatch per plan in scope.

## Read first
- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
plan_path: {{PLAN_PATH}}
resume_task: {{RESUME_TASK}}      # empty if starting from the first task
commit_mode: {{COMMIT_MODE}}      # auto (default) | defer
```

## Task
Implement the plan task-by-task in order. Enforce TDD for `tdd_required: true` tasks.
Apply SOLID. Flag any manual action you cannot perform.

## Return summary
```
plan_id: PLAN-F-NNN
tasks_completed: <n>
tasks_blocked: <n>
manual_actions_required:
  - <description>
files_created: <n>
files_modified: <n>
tests_added: <n>
tests_pass: true | false
plan_status: in-progress | done | blocked
```
