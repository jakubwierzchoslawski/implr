---
name: dev-executor
description: >
  Implements ready plans. For each in-wave plan: parses the plan once into per-task
  envelopes, dispatches arch-excerpter (Sonnet) once per plan for an arch_excerpt, then
  dispatches plan-runner subagents in parallel waves (cap 5). Each plan-runner dispatches
  one task-executor per task sequentially. Opus by default. Use when implementing plans.
---

# dev-executor Skill (v3.0 orchestrator)

You orchestrate plan execution. Per-plan implementation runs in `plan-runner` subagents
(parallel within dependency waves); each plan-runner dispatches one `task-executor` per
task sequentially. **You** parse each plan ONCE and write per-plan/per-task envelope files to a work dir —
neither plan-runner nor task-executor reads the plan file.

## Read first

- `docs/implr/config/implr.config.yaml` — for paths and agent model overrides.
- `docs/implr/config/standards-card.md` — written into `plan-context.md` in each plan's work dir. Halt if
  missing: `❌ docs/implr/config/standards-card.md not found. Run /implr-init (or /implr-init --refresh-card) first.`

Do NOT read `docs/ARCHITECTURE.md` — arch-excerpter handles that per plan.
Do NOT read `plan-schema.md` or `DEV-STANDARDS.md`.

## Preconditions

- `docs/implr/config/standards-card.md` exists (else the existing halt).
- Every in-scope plan is `status: ready`. A `needs-rework` plan is rejected with
  `❌ PLAN-F-NNN is needs-rework — run /dev-planner --replan first.`

## Parameters

- `/dev-executor PLAN-F-001` — execute one plan.
- `/dev-executor PLAN-F-001 PLAN-F-002` — execute several (deps validated).
- `/dev-executor --all` — execute all `ready` plans in dependency order.
- `/dev-executor --task PLAN-F-001 TASK-003` — resume from a single task.
- `/dev-executor --dry-run PLAN-F-001` — list files that would be touched; write nothing.
- `/dev-executor --verbose` — append per-task file lists to the report.
- `/dev-executor --review` — chain `/dev-code-review` for executed plans after success.
- `/dev-executor --commit ...` — commit each plan's changes after success (default: no
  commit; the worktree is left exactly as-is, nothing staged).

## Execution

### Phase 1 — Resolve scope

Identify plans to execute (per parameter). For `--all`, read `plans-index.md` for
`status: ready`. For named plans, validate existence and `status: ready` (`--task` mode
allowed on `in-progress` plans). For `--task`, identify the named task's plan.

If a named or `--all`-selected plan has `status: needs-rework`, do NOT execute it. Emit:
`❌ PLAN-F-NNN is needs-rework (CR {rework_cr}). Run /dev-planner --replan {plan} first.`
and skip it.

### Phase 2 — Validate dependencies

For each in-scope plan, every dependency in frontmatter `dependencies:` must be
`status: done`. Block plans whose deps are not done; report and skip.

### Phase 3 — Compute execution waves

Topological sort by plan dependencies. Each wave contains plans whose deps are all done.

### Phase 4 — Per-plan preparation (once per plan, before wave dispatch)

For EACH in-scope plan (run this preparation sequentially across all plans before
dispatching any wave):

**a. Parse the plan into tasks.**

Read the plan file. Extract:
- Frontmatter (YAML between first and second `---`)
- `task_fingerprints` from that frontmatter — a map `{TASK-NNN: "t1:<hash>"}` (may be
  empty or absent on a plan's first run, or for a task added since the last run; that's
  expected). Keep this map in memory for step f.
- `## Objective` body (lines after header until next `##`)
- `## Architecture Context` body (lines after header until next `##`)
- `### Interfaces and Contracts` body (within Component Design, lines after header until next `##`)
- `## Applied NFR Constraints` body (lines after header until next `##`; set to `"N/A"` if absent or content is just `N/A`)
- Each task block: starts at a line matching `^### TASK-(\d{3}): ` (note: actual header format is `### TASK-NNN: title · complexity/tdd-flag · files`). Parse:
  - `id` = `TASK-NNN` from the header
  - `title` = text between the colon+space and the first ` · `
  - `complexity` = first segment between the two ` · ` separators, before the `/`
  - `tdd_required` = true if the tdd-flag segment is `TDD`, false if `no-TDD`
  - `files` = comma-separated list in the third ` · ` segment (may be a single file)
  - `body` = all lines after the header until the next `### TASK-` or top-level `## ` header
  - `ac_covered` = parse `**AC covered**: AC-NNN, AC-NNN` line within body
  - `tests_first` = parse `**Tests to write first (TDD)**` bullet list within body (empty list if absent)
- If the header regex does not match OR `**AC covered**:` is absent for a task that the
  AC Coverage section lists: abort this plan with message:
  `❌ PLAN-F-NNN parse failed: <reason>. Fix template compliance and re-run.` Continue other plans.

**b. Resolve full AC text.**

Read the linked requirement (`linked_requirement:` frontmatter → look up in
`docs/implr/requirements/`). Extract each `- [ ] AC-NNN:` line. Build `ac_full` list.
Also read that requirement's `updated_at:` frontmatter value and capture it as
`requirement_updated_at` — every task in this plan shares the same linked requirement,
so this value is resolved once per plan and reused in every task fingerprint file written in
step f below.

**c. Dispatch arch-excerpter.**

Dispatch `arch-excerpter` (Sonnet) with `{plan_path}`. Capture the `excerpt:` block
from the return summary as `arch_excerpt`. If arch-excerpter fails or returns no excerpt:
fall back to reading the first 200 lines of `docs/ARCHITECTURE.md` and warn.

**d. Read standards-card.**

The content of `docs/implr/config/standards-card.md` (already in memory from "Read
first") is the `standards_card` value.

**e. Resolve model.**

Read `agents.task-executor` from `implr.config.yaml`; fall back to `opus`.
Read `agents.plan-runner` from `implr.config.yaml`; fall back to `sonnet`.

**f. Write the work directory.**

Envelopes are passed by file, never by value. Create `docs/implr/.work/<PLAN-ID>/`
(replace it if a stale one exists) containing a `.gitignore` with the single line `*`
(so the directory is never staged or committed), and write:

- `plan-context.md` — once per plan: `plan_objective`, `plan_arch_context`, `interfaces`,
  `applied_nfrs`, `arch_excerpt`, `standards_card`, each under its own `##` heading.
- `TASK-NNN.md` — one per task: id, title, complexity, `tdd_required`, `files`, `body`,
  `ac_covered`, `tests_first`, and the full text of the ACs it covers (from `ac_full`).
- `TASK-NNN.fp.json` — one per task: a JSON object with exactly the 11 fields that
  `python scripts/implr_validate --task-fingerprint` requires:

  | field                    | source                                                              |
  |--------------------------|---------------------------------------------------------------------|
  | `task_body`              | the task `body`                                                     |
  | `ac_ids`                 | `ac_covered` (list of AC ids)                                       |
  | `ac_text`                | for each id in `ac_covered`, its `text` from `ac_full`              |
  | `files`                  | the task `files`                                                    |
  | `tests_first`            | the task `tests_first` (empty list if absent)                       |
  | `requirement_updated_at` | `requirement_updated_at` from step b                                |
  | `arch_excerpt_hash`      | `arch_excerpt` (raw text passthrough, not a hash)                   |
  | `interfaces_contracts`   | `interfaces`                                                        |
  | `applied_nfrs`           | `applied_nfrs`                                                      |
  | `standards_card_hash`    | `standards_card` (raw text passthrough, not a hash)                 |
  | `test_runner`            | the configured test runner                                          |

- `meta.json` — `plan_id`, `plan_path`, `src_path`, `tests_path`, `test_runner`,
  `commit_mode` (`auto` only when `--commit` was passed, else `defer`), `task_ids`
  (the tasks scheduled for this run, in plan order), and `prior_fingerprints`
  (`task_fingerprints` map from step a; `{}` if none).

For `--task` mode: write only the named task's files and set `task_ids` to that one id;
set `resume_task` to the task id.

For `--dry-run`: do NOT write the work dir or dispatch. Print the `files` list of each
task per plan, then stop.

### Phase 5 — Dispatch `plan-runner` per plan (parallel within wave)

For each wave (in topological order), dispatch all wave plans IN PARALLEL (single message,
multiple Agent calls; cap 5). Each dispatch passes:

```
plan_id, plan_path, work_dir (docs/implr/.work/<PLAN-ID>), resume_task (empty unless --task mode),
task_executor_model
```

Nothing else is passed: the work dir files are the envelope. `plan-runner` finalizes the
plan itself (`implr_validate --finalize-plan`), which removes the work dir on `done`.

Wait for wave completion. Collect each plan-runner's return summary.

### Phase 6 — Aggregate and update indices

- Update `docs/implr/plans/plans-index.md` with new statuses.
- Append a run entry to `docs/implr/plans/plans-log.md`.

### Phase 7 — Report (concise default; `--verbose` adds detail)

**Default (one screen):**

```
🛠  dev-executor complete  (v3.0)
Plans executed: {n}    Waves: {n}
Tasks: {done}/{total}  Blocked: {n}
Files: +{new} ~{modified}
Tests: {added} added | {pass|fail}

{If manual actions:}
Manual actions:
  - {one line each}

Next:
  /dev-code-review --all   (or specific plan ids)
```

**With `--verbose`:** append per-plan detail: plan_id, tasks completed, files
created/modified, tests added, stopping_task if any.

### Phase 8 — Chain code-review (only with `--review`)

If `--review` was passed AND all plans reached `status: done`: invoke `/dev-code-review`
with the executed plan ids. Merge its verdict counts into this report.

## Failure handling

- `standards-card.md` missing → halt before any dispatch (message above).
- Plan is `needs-rework` → refuse to execute it; skip and report (message above).
- Plan parse failure → skip that plan; continue others; report skipped plans.
- Dependency not `done` → skip with warning unless explicitly named.
- `plan-runner` returns `tests_pass: false` → plan stays `in-progress`; surface to user;
  do not chain code-review even if `--review` was set.
- Manual actions reported → surface; plan stays `in-progress`.
- `arch-excerpter` failure → fall back to first 200 lines of ARCHITECTURE.md + warn; do
  not block execution.

## Definition of Done (see also docs/implr/DOD.md)

A plan reaches `status: done` only when:
1. All tasks complete.
2. All produced tests pass.
3. Every AC in the linked requirement is covered by ≥1 task and verified by ≥1 passing test.
4. No TODO/FIXME/XXX markers introduced.
5. `dev-code-review` (when run) has no Critical/High findings.
