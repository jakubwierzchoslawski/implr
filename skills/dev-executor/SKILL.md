---
name: dev-executor
description: >
  Implements ready plans. Dispatches one executor-worker subagent (Opus by default — TDD
  and SOLID need strong model) per plan. Independent plans dispatched in parallel waves;
  tasks within each plan stay sequential inside the subagent. Use when implementing plans.
---

# dev-executor Skill (v2.0 orchestrator)

You orchestrate plan execution. Per-plan implementation runs in `executor-worker`
subagents. Plan dependencies define the execution waves.

## Read first

- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/dev-executor PLAN-F-001` — execute one plan.
- `/dev-executor PLAN-F-001 PLAN-F-002` — execute several in the given order (deps validated).
- `/dev-executor --all` — execute all `ready` plans in dependency order from `plans-index.md`.
- `/dev-executor --task PLAN-F-001 TASK-003` — execute a single task (resume).
- `/dev-executor --dry-run PLAN-F-001` — list files that would be created/modified.

## Execution

### Phase 1 — Resolve scope

Identify plans to execute. For `--all`, read `plans-index.md` and pick `status: ready`.
For named plans, validate they exist and are `ready`. For `--task`, locate the named task
inside the named plan.

### Phase 2 — Validate dependencies

For each plan, every dependent PLAN must be `status: done`. Block plans whose deps are not
done; report.

### Phase 3 — Compute execution waves

Topologically sort by plan dependencies. Each wave contains plans whose deps are done.

### Phase 4 — Dispatch `executor-worker` per plan (parallel within wave)

For each wave, dispatch all in-wave plans (cap 5):

Scope: `{plan_path, resume_task, commit_mode}` (`resume_task` empty for fresh plan
execution; `commit_mode` defaults to `auto`).

Wait for wave completion before next wave.

For `--task` mode: single dispatch with `resume_task` set to the named task; do not run
subsequent tasks.

For `--dry-run`: do not dispatch; instead, read each plan and list files it would touch.

### Phase 5 — Aggregate returns

Collect: tasks completed, blocked, manual actions, files created/modified, test
pass/fail, plan status updates.

Update `plans-index.md` with new statuses. Append entries to `plans-log.md`.

### Phase 6 — Report

```
🛠  dev-executor complete  (v2.0)
Plans executed: {n}    Waves: {n}
Tasks completed: {n}    Tasks blocked: {n}
Files: +{n} new, ~{n} modified
Tests: {n} added, status: pass | fail
Manual actions required:
  - {list}

Next steps:
  1. Review changes in src/ and tests/
  2. Run /dev-code-review --all (or specific plans)
```

## Failure handling

- Plan not ready → skip with warning unless explicitly named.
- Executor-worker reports `tests_pass: false` → mark plan status `in-progress` (not `done`),
  report failing tests.
- Manual actions required → leave plan `in-progress`, surface to user.
- Worker returns blocked task → mark plan `in-progress` with the blocking task highlighted.
