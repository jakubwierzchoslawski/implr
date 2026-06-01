# Phase: execute-plan

Dispatch prompt for `plan-runner`. One dispatch per plan in scope.

> Note: `plan-runner` receives pre-built envelopes and does NOT read schema/ARCHITECTURE/DEV-STANDARDS files.

## Your scope
```
plan_path: {{PLAN_PATH}}
resume_task: {{RESUME_TASK}}      # empty if starting from the first task
commit_mode: {{COMMIT_MODE}}      # auto (default) | defer
```

## Task
Orchestrate plan execution by dispatching one `task-executor` subagent (`.claude/agents/task-executor.md`) per task in order.
Do not implement code directly. `commit_mode` applies after ALL tasks in the plan complete —
not per-task. Flag any manual actions reported by task-executor.

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
