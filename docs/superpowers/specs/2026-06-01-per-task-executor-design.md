# Per-Task Executor — Design

**Date:** 2026-06-01
**Status:** approved

## Overview

Refactors the `executor-worker` agent from a per-plan implementer (all tasks in one growing
context) into a thin per-plan orchestrator that dispatches a new `task-executor` agent for
each task sequentially. This reduces executor-worker's token consumption from ~100k to
~15k per plan, and bounds each task-executor context to ~25k — a 60–70% reduction in
effective billed input tokens for a typical 5-task plan.

Code quality is preserved through:
- Each task-executor reads the full plan (knows overall design intent)
- A compact `prior_decisions_summary` carries forward key choices from completed tasks
- Each task-executor reads all files it will touch before writing (filesystem state is truth)
- Stable reads (ARCHITECTURE.md, DEV-STANDARDS.md, schema, config) are prompt-cached
  across sequential task dispatches within one executor-worker session

---

## Goals and Non-Goals

**Goals**
- Reduce executor-worker token consumption by 60–70% on typical plans.
- Preserve full TDD discipline (red → green → refactor) and SOLID enforcement per task.
- Preserve design consistency across tasks via a decisions log passed between dispatches.
- Keep dev-executor SKILL.md unchanged — the executor-worker dispatch contract is identical.
- No schema changes.

**Non-Goals**
- Parallelising tasks within a plan (tasks are sequentially dependent by definition).
- Changing model tiers (task-executor defaults to Opus, same as executor-worker today).
- Changing the dev-executor orchestration layer or any other skill.

---

## Architecture

### Execution hierarchy

```
dev-executor (SKILL.md orchestrator, main context)
  │  dispatches per plan, parallel waves, cap 5
  ▼
executor-worker (agent, Opus, ~15k context per plan)
  │  reads plan, dispatches tasks sequentially, carries decisions log forward
  ▼
task-executor (NEW agent, Opus, ~25k context per task)
     stable prefix [cached]: schema + ARCHITECTURE.md + DEV-STANDARDS.md + config + plan
     dynamic suffix [~1k]:   task_id + prior_decisions_summary
     work: full TDD loop for ONE task
     returns: files_created/modified, decisions_made, tests_pass
```

### Token budget comparison

| | Before | After |
|---|---|---|
| executor-worker context peak | ~100k | ~15k |
| task-executor context peak | n/a | ~25k (bounded) |
| Stable reads cost (5-task plan) | full price × many turns in growing context | cached at ~10% after first dispatch |
| Effective billed input (5-task plan) | ~500k+ | ~80–120k |

### Why context stays bounded in task-executor

The stable prefix (schema + ARCHITECTURE.md + DEV-STANDARDS.md + config + plan file) is
read first and is identical across all task dispatches for a given plan. Anthropic's 5-minute
prompt cache reuses this prefix, so dispatches 2–N pay ~10% of full input cost on those
tokens.

The dynamic suffix changes per task but is small (~1k). The TDD work loop (reads, writes,
Bash runs) is bounded to ONE task — it does not accumulate prior tasks' tool results.

Bash output is capped at 80 lines per run. Full output is written to a temp file the agent
can read if the truncated output is insufficient to diagnose a failure.

---

## Component Specifications

### executor-worker (refactored)

**New responsibilities — orchestration only, no TDD, no file writes:**

1. Read the plan file.
2. For each task in plan order:
   a. Resolve model for task-executor from `implr.config.yaml` `agents.task-executor`;
      fall back to `default_model: opus`.
   b. Dispatch `task-executor` with scope `{plan_path, task_id, prior_decisions_summary}`.
   c. Receive structured return summary.
   d. Append to `decisions_log` (accumulates across tasks for the next dispatch).
   e. On `tests_pass: false` or `task_status: blocked` → stop dispatching; record state.
3. When all tasks complete (or blocked/failed):
   - Update plan `status` field (in-progress → done, or in-progress if blocked/failed).
   - Commit changes if `commit_mode: auto`.
4. Return plan-level summary to dev-executor.

**`prior_decisions_summary` format** (passed to each task-executor):

```yaml
completed_tasks:
  - task_id: T-001
    files_created: [src/users/user_store.py]
    files_modified: []
    interfaces_added: [IUserStore]
    decisions:
      - "Repository pattern for UserStore — matches existing AccountRepository"
      - "Constructor injection — per DEV-STANDARDS §3.2"
    tests_pass: true
  - task_id: T-002
    ...
```

Size: ~1–2k tokens per completed task. For a 5-task plan: ~8k by the final task dispatch.

**executor-worker context budget:**
- Plan file: ~5k
- Task dispatches × (payload sent + summary received): ~2k × N tasks
- Opus turns: minimal (orchestration only)
- Total peak: ~15k for a 5-task plan

### task-executor (new agent)

**Prompt structure:**

```
[STABLE PREFIX — prompt-cached across dispatches]
  1. docs/implr/schemas/plan-schema.md
  2. docs/ARCHITECTURE.md
  3. docs/implr/config/DEV-STANDARDS.md
  4. docs/implr/config/implr.config.yaml
  5. {plan_path}   ← same file content, same position → cache hit on dispatches 2–N

[DYNAMIC SUFFIX — changes per dispatch, ~1k]
  task_id: {task_id}
  prior_decisions_summary:
    {prior_decisions_summary}
```

The stable prefix is read first in every dispatch. This ordering is required for cache hits.

**Work loop (one task):**

1. Locate the task definition in the plan (already in context from plan read).
2. Read all files the task will touch — before writing anything.
3. Apply `prior_decisions_summary`: continue established patterns; do not invent new ones
   for decisions already made.
4. If `tdd_required: true`:
   a. Write the failing test(s) named in the task's AC list.
   b. Run test runner: `<runner> 2>&1 | tee /tmp/test-last-full.txt | head -80`
   c. Verify failure (if output truncated, read `/tmp/test-last-full.txt`).
   d. Implement minimal code to pass.
   e. Run test runner again (same command); verify pass.
   f. Refactor if needed; re-verify.
5. If not TDD-required: write code and any smoke tests.
6. Note any manual actions that cannot be performed.
7. Return structured summary.

**Return summary:**

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
  - "<decision made and why — one line>"
tests_added: <n>
tests_pass: true | false
manual_actions:
  - <description>
```

**Model:** `default_model: opus` (TDD + SOLID enforcement unchanged).

**Tools:** `[Read, Write, Edit, Bash, Grep, Glob]` (same as executor-worker today).

---

## File Changes

```
NEW:
  .claude/agents/task-executor.md

MODIFIED:
  .claude/agents/executor-worker.md        refactor: thin orchestrator (no TDD loop)
  skills/dev-executor/phases/execute-plan.md   minor: clarify commit_mode applies
                                               after all tasks complete, not per-task
```

**dev-executor SKILL.md — unchanged.** The dispatch contract for executor-worker is identical:
`{plan_path, resume_task, commit_mode}`. dev-executor is unaware of task-executor.

`resume_task` handling: when executor-worker receives a non-empty `resume_task`, it skips
task-executor dispatches for all tasks before that task_id and starts the decisions log from
scratch (no prior context is available for the skipped tasks — the implementer must infer
from existing code on disk).

No schema changes. No changes to any other skill or agent.

---

## Quality Gates

A change qualifies as complete when:

- [ ] `task-executor.md` exists with correct frontmatter (`name`, `tools`, `default_model: opus`).
- [ ] executor-worker dispatches task-executor and does NOT perform TDD or file writes itself.
- [ ] executor-worker correctly builds and forwards `prior_decisions_summary` across tasks.
- [ ] executor-worker stops on `tests_pass: false` or `task_status: blocked` and surfaces state.
- [ ] task-executor reads stable prefix before dynamic suffix in every dispatch.
- [ ] task-executor caps Bash output at 80 lines and writes full output to `/tmp/test-last-full.txt`.
- [ ] task-executor reads all files it will modify before writing.
- [ ] task-executor applies `prior_decisions_summary` patterns — does not reinvent choices.
- [ ] execute-plan.md updated: `commit_mode` note clarifies post-all-tasks timing.
- [ ] On a sample plan (3+ TDD tasks), executor-worker context stays under 20k tokens.
- [ ] On the same sample plan, all tests pass and generated code is consistent across tasks.

---

## Risks

- **Decisions log incomplete.** If task-executor omits a key decision from its return summary,
  a later task may diverge in style. Mitigation: task-executor instructions explicitly require
  recording any pattern choice that another task could replicate.

- **Cache miss on plan file.** If executor-worker modifies the plan file (status updates)
  between task dispatches, the plan file content changes and the cache prefix is invalidated.
  Mitigation: executor-worker updates plan status fields only AFTER all tasks complete, not
  between dispatches.

- **Bash temp file collisions.** Parallel executor-workers (multiple plans in a wave) would
  overwrite each other's `/tmp/test-last-full.txt`. Mitigation: use a plan-scoped temp path,
  e.g. `/tmp/implr-test-{plan_id}.txt`.
