# Per-Task Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor executor-worker from a per-plan TDD implementer into a thin orchestrator that dispatches a new task-executor agent for each task, reducing context growth from ~100k to ~25k per task.

**Architecture:** executor-worker reads the plan and dispatches `task-executor` once per task sequentially, carrying a compact `prior_decisions_summary` forward between dispatches. Each task-executor starts with a prompt-cached stable prefix (schema + ARCHITECTURE.md + DEV-STANDARDS.md + config + plan), then receives only the task_id and decisions log as dynamic input (~1k tokens). Bash output is capped at 80 lines per run.

**Tech Stack:** Markdown (agent definitions), YAML frontmatter.

**Spec:** `docs/superpowers/specs/2026-06-01-per-task-executor-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `.claude/agents/task-executor.md` | Create | New agent: implements one task (full TDD loop), cache-optimised prompt structure, Bash output cap |
| `.claude/agents/executor-worker.md` | Rewrite | Thin per-plan orchestrator: reads plan, dispatches task-executor sequentially, carries decisions log, commits at end |
| `skills/dev-executor/phases/execute-plan.md` | Edit | Clarify commit_mode applies after all tasks complete, not per-task; add `commit_mode` field to scope block |

---

## Task 1: Create `task-executor.md`

**Files:**
- Create: `.claude/agents/task-executor.md`

- [ ] **Step 1: Create the file**

Write `.claude/agents/task-executor.md` with the following exact content:

```markdown
---
name: task-executor
description: Implements one task from a plan end-to-end. Reads stable prefix (schema, ARCHITECTURE.md, DEV-STANDARDS.md, config, plan) for prompt caching, receives task_id and prior_decisions_summary, enforces TDD for tdd_required tasks, caps Bash output at 80 lines.
tools: [Read, Write, Edit, Bash, Grep, Glob]
default_model: opus
---

# task-executor

You implement exactly one task from one plan. You enforce TDD when `tdd_required: true`.
You apply SOLID. You continue established patterns from `prior_decisions_summary` — do not
reinvent choices already made in earlier tasks.

## Read first (stable prefix — cache-friendly order)

Read these in order before anything else. The same files appear in every task dispatch for
the same plan, so Anthropic's prompt cache reuses this prefix across dispatches.

1. `docs/implr/schemas/plan-schema.md`
2. `docs/ARCHITECTURE.md`
3. `docs/implr/config/DEV-STANDARDS.md`
4. `docs/implr/config/implr.config.yaml` — for `src` and `tests` paths.
5. `{plan_path}` — read the full plan for design context.

## Inputs (from executor-worker)

```
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
task_id: T-NNN
prior_decisions_summary: |
  completed_tasks:
    - task_id: T-NNN
      files_created: [...]
      files_modified: [...]
      interfaces_added: [...]
      decisions:
        - "<decision and why>"
      tests_pass: true
  # empty list on the first task dispatch
```

## Work

1. Locate the task definition in the plan using `task_id`.
2. Read all files the task will touch — before writing anything.
3. Read `prior_decisions_summary`. Continue every pattern listed. Do not make a different
   choice for anything already decided (e.g. if DI via constructor is established, keep it).
4. If `tdd_required: true`:
   a. Write the failing test(s) named in the task's AC list.
   b. Run the test runner with output cap:
      `<runner-command> 2>&1 | tee /tmp/implr-test-{plan_id}.txt | head -80`
      Replace `{plan_id}` with the plan's ID (e.g. `PLAN-F-007`).
   c. Verify the test fails. If 80 lines is not enough to diagnose, read
      `/tmp/implr-test-{plan_id}.txt` for the full output.
   d. Implement the minimal code to pass.
   e. Run the test runner again (same command); verify pass.
   f. Refactor if needed; re-verify.
5. If not TDD-required (XS, S below threshold): write code and any smoke tests.
6. Note any manual action you cannot perform (missing credentials, env-specific config).
   Do not invent secrets.

Do NOT commit. Do NOT update plan status. executor-worker handles both.

## Output

Implementation files under `src/` and `tests/` per config paths.

## Return summary (your one final message)

```
task_id: T-NNN
task_status: done | blocked | failed
files_created:
  - <path>
files_modified:
  - <path>
interfaces_added:
  - <name>
decisions:
  - "<pattern or choice made, and why — one line>"
tests_added: <n>
tests_pass: true | false
manual_actions:
  - <description if any>
```

List every decision that a subsequent task could replicate. If you chose a pattern that
isn't in `prior_decisions_summary`, add it here so the next task can continue it.
```

- [ ] **Step 2: Verify frontmatter**

Read `.claude/agents/task-executor.md`. Confirm:
- `name: task-executor` matches the filename
- `tools:` list includes `[Read, Write, Edit, Bash, Grep, Glob]`
- `default_model: opus`

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/task-executor.md
git commit -m "feat(agents): add task-executor for per-task TDD dispatch"
```

---

## Task 2: Rewrite `executor-worker.md` as thin orchestrator

**Files:**
- Modify: `.claude/agents/executor-worker.md`

- [ ] **Step 1: Read the current file**

Read `.claude/agents/executor-worker.md` to understand what will be replaced.

- [ ] **Step 2: Overwrite the file**

Write `.claude/agents/executor-worker.md` with the following exact content:

```markdown
---
name: executor-worker
description: Thin per-plan orchestrator. Reads the plan, dispatches one task-executor subagent per task sequentially, carries a prior_decisions_summary forward between dispatches, updates plan status after all tasks complete, commits if commit_mode is auto.
tools: [Read, Write, Edit, Bash, Grep, Glob]
default_model: opus
---

# executor-worker

You orchestrate the execution of one plan. You dispatch `task-executor` once per task in
plan order. You do NOT implement code, write tests, or run the test runner yourself — that
is task-executor's job.

## Read first

1. `docs/implr/schemas/plan-schema.md`
2. `docs/implr/config/implr.config.yaml` — for `src`, `tests` paths and agent model overrides.

## Inputs (from dev-executor)

```
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
resume_task: <task-id or omitted>
commit_mode: auto | defer       # default: auto
```

## Work

### 1. Read the plan

Read `plan_path`. Identify all tasks in order, their `task_id` values, and
`tdd_required` flags.

If `resume_task` is set, skip all tasks before that `task_id`. Start the `decisions_log`
empty (no prior context is available for skipped tasks — task-executor will infer from
existing code on disk).

### 2. Resolve task-executor model

Read `docs/implr/config/implr.config.yaml`. If `agents.task-executor` is set, use that
model. Otherwise use `opus`.

### 3. Dispatch task-executor per task (sequential)

For each task in order, dispatch `task-executor` with:

```
plan_path: <plan_path>
task_id: <task_id>
prior_decisions_summary: |
  completed_tasks:
    <decisions_log entries so far>
```

Wait for the return summary before dispatching the next task.

After each return:
- Append the task's return summary to `decisions_log`.
- If `task_status: blocked` or `task_status: failed`: stop dispatching. Record the
  blocking task_id and reason.
- If `tests_pass: false`: stop dispatching. Record which task failed.

Do NOT update plan status fields between task dispatches — only after all tasks complete
(see step 4). This preserves the prompt cache prefix for subsequent task-executor dispatches.

### 4. Update plan status

After all tasks complete (or on stop condition):
- All tasks done, all tests pass → set plan `status: done`.
- Any task blocked or failed → set plan `status: in-progress`; annotate the blocking task.

Edit the plan file directly to update the `status` field.

### 5. Commit (if commit_mode: auto)

```bash
git add -A
git commit -m "feat(<plan_id>): implement plan tasks"
```

If `commit_mode: defer`, leave changes staged; do not invoke `git commit`.

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
```

- [ ] **Step 3: Verify the file**

Read `.claude/agents/executor-worker.md`. Confirm:
- `name: executor-worker` is unchanged
- `description` mentions "thin per-plan orchestrator" and "task-executor"
- The Work section dispatches `task-executor` and does NOT contain a TDD loop
- Plan status update is in step 4, after all dispatches complete

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/executor-worker.md
git commit -m "refactor(agents): executor-worker becomes thin orchestrator dispatching task-executor"
```

---

## Task 3: Update `execute-plan.md` dispatch prompt

**Files:**
- Modify: `skills/dev-executor/phases/execute-plan.md`

- [ ] **Step 1: Read the current file**

Read `skills/dev-executor/phases/execute-plan.md`.

Current content:

```markdown
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
```

- [ ] **Step 2: Overwrite the file**

Write `skills/dev-executor/phases/execute-plan.md` with the following exact content:

```markdown
# Phase: execute-plan

Dispatch prompt for `executor-worker`. One dispatch per plan in scope.

## Read first
- `docs/implr/schemas/plan-schema.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
plan_path: {{PLAN_PATH}}
resume_task: {{RESUME_TASK}}      # empty if starting from the first task
commit_mode: {{COMMIT_MODE}}      # auto (default) | defer
```

## Task
Orchestrate plan execution by dispatching one `task-executor` subagent per task in order.
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
```

Key changes from the previous version:
- `## Read first` is trimmed: removed ARCHITECTURE.md, DEV-STANDARDS.md (executor-worker
  no longer reads them — task-executor reads them per-dispatch).
- `## Task` paragraph updated: states orchestration role and clarifies commit_mode timing.

- [ ] **Step 3: Verify the file**

Read `skills/dev-executor/phases/execute-plan.md`. Confirm:
- `## Read first` contains only `plan-schema.md` and `implr.config.yaml` (not ARCHITECTURE.md)
- `## Task` mentions "dispatching one `task-executor` subagent per task"
- `## Task` states "`commit_mode` applies after ALL tasks complete"
- Return summary block is unchanged

- [ ] **Step 4: Commit**

```bash
git add skills/dev-executor/phases/execute-plan.md
git commit -m "fix(dev-executor): trim execute-plan.md reads; clarify commit_mode is post-all-tasks"
```

---

## Task 4: Smoke test

No automated test runner applies to agent definition files. Verify the three-file set is
internally consistent.

- [ ] **Step 1: Confirm task-executor is referenced in executor-worker**

```bash
grep -n "task-executor" .claude/agents/executor-worker.md
```

Expected output includes lines referencing `task-executor` dispatch in the Work section.

- [ ] **Step 2: Confirm executor-worker no longer has a TDD loop**

```bash
grep -n "tdd_required\|red.*green\|failing test\|test runner" .claude/agents/executor-worker.md
```

Expected: no matches (all TDD language should be in task-executor, not executor-worker).

- [ ] **Step 3: Confirm task-executor has the Bash output cap**

```bash
grep -n "head -80\|tee /tmp/implr-test" .claude/agents/task-executor.md
```

Expected: both strings appear in the Work section.

- [ ] **Step 4: Confirm task-executor reads stable prefix before dynamic inputs**

```bash
grep -n "Read first\|plan_path\|task_id\|prior_decisions" .claude/agents/task-executor.md | head -20
```

Expected: "Read first" section appears before "Inputs" section (line numbers should be lower).

- [ ] **Step 5: Confirm execute-plan.md no longer lists ARCHITECTURE.md**

```bash
grep -n "ARCHITECTURE" skills/dev-executor/phases/execute-plan.md
```

Expected: no matches.

- [ ] **Step 6: Final commit (if any fixes were needed in steps 1–5)**

```bash
git add .claude/agents/ skills/dev-executor/phases/
git commit -m "fix(agents): per-task executor smoke test corrections"
```

Only commit if there were corrections. Skip if steps 1–5 all passed cleanly.
