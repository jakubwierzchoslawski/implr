# Work-dir envelopes and `--finalize-plan` — design

Date: 2026-10-22

## Problem

`task-executor` runs reach hundreds of thousands of tokens of context. The static parts
(standards card, arch excerpt) are small; the bloat comes from how work is passed around:

- `dev-executor` builds every task envelope for every plan in its own context, then
  re-emits them as dispatch parameters.
- Each envelope repeats the plan-level blocks (objective, arch context, interfaces, NFRs,
  `arch_excerpt`, `standards_card`), so `plan-runner` receives N copies and must re-type a
  full envelope on every `task-executor` dispatch (expensive output tokens).
- `plan-runner` (Opus) does deterministic bookkeeping by hand: frontmatter edits,
  fingerprints via a mapping table duplicated in two agents, optional commit,
  `source_ref`, `test-results.md`.

## Goals

1. Pass envelopes by file, not by value: plan-level context written once per plan, task
   body once per task.
2. Move plan finalization into deterministic code (`implr_validate --finalize-plan`),
   leaving `plan-runner` a thin dispatch loop (Sonnet).

Out of scope: trimming `prior_decisions_summary`, task-executor read discipline, model per
complexity, prompt ordering for cache.

## Work directory

`docs/implr/.work/<PLAN-ID>/`, created by `dev-executor` Phase 4. It contains a `.gitignore`
with `*`, so it never needs repo-level ignore changes and `git add -A` never picks it up.
Removed by `--finalize-plan` when the plan reaches `done`; kept on failure/block for
debugging and `--task` resume.

| file | writer | content |
|------|--------|---------|
| `plan-context.md` | dev-executor | objective, arch context, interfaces, applied NFRs, `arch_excerpt`, `standards_card` |
| `TASK-NNN.md` | dev-executor | id, title, complexity, `tdd_required`, files, body, `ac_covered`, `tests_first`, full text of covered ACs |
| `TASK-NNN.fp.json` | dev-executor | the 11 `task_fingerprint()` fields, ready to pass to `--task-fingerprint` |
| `meta.json` | dev-executor | `plan_id`, `plan_path`, `src_path`, `tests_path`, `test_runner`, `commit_mode`, `task_ids` (tasks scheduled this run, in order), `prior_fingerprints` |
| `TASK-NNN.result.json` | plan-runner | task-executor's return summary as JSON |

Because the `.fp.json` is prebuilt, the field-mapping tables in `task-executor` and
`plan-runner` disappear.

## Agents

- **dev-executor**: Phase 4 writes the files above instead of building in-memory
  envelopes; Phase 5 passes `plan-runner` only `plan_id`, `plan_path`, `work_dir`,
  `resume_task`, `task_executor_model`.
- **plan-runner** (default model `sonnet`): for each id in `meta.task_ids` (after resume
  filtering) dispatches `task-executor` with `work_dir`, `task_id` and
  `prior_decisions_summary`; writes the return to `TASK-NNN.result.json`; stops on
  blocked/failed/`tests_pass:false`; then runs `python scripts/implr_validate
  --finalize-plan <work_dir>` and returns its JSON summary.
- **task-executor**: reads `plan-context.md` and `TASK-NNN.md`; skip check uses
  `--task-fingerprint TASK-NNN.fp.json` with `prior_fingerprints[TASK-NNN]` from `meta.json`.

## `--finalize-plan WORKDIR` (new `finalize.py`)

Reads `meta.json`, `*.fp.json`, `*.result.json`. `--root` is the repo root (default cwd);
`plan_path`, `src_path`, `tests_path` are relative to it.

1. A scheduled task with no result file means the runner stopped early.
   Plan is `done` iff every scheduled task has `task_status: done` and `tests_pass: true`.
2. Plan frontmatter: `done` → `status: done`, `executed_at: now`, `blocked_reason` cleared,
   `implemented_files` = dedup union of existing + all created/modified,
   `task_fingerprints` = existing merged with fingerprints of scheduled tasks.
   Otherwise `status: in-progress`; `blocked_reason` set when a task reported `blocked`.
3. `commit_mode: auto` → `git add -A` + `git commit -m "feat(<plan_id>): implement plan tasks"`
   (skipped when nothing is staged). `defer` → git is untouched.
4. `source_ref` computed after the commit; `docs/implr/plans/test-results/<plan_id>-results.md`
   written per `test-results-schema.md` (`skip` row when `test_exit_code` is null).
5. On `done`, the work dir is deleted.
6. stdout: JSON summary (`plan_id`, `plan_status`, `tasks_completed`, `tasks_blocked`,
   `files_created`, `files_modified`, `tests_added`, `tests_pass`, `stopping_task`,
   `stopping_reason`, `manual_actions`). Exit 0 on success, 1 on bad input.

Behaviour matches the previous manual steps; only the executor changes.

## Testing

`tests/test_finalize.py`: all done; stop on failed/`tests_pass:false`; blocked sets
`blocked_reason`; missing result = early stop; resume merges `implemented_files` and
`task_fingerprints`; skip row; `commit_mode` defer leaves git untouched and auto commits;
work dir removed only on done; fingerprint equals `task_fingerprint()` of the `.fp.json`;
CLI wiring in `tests/test_cli.py`. Repo prose validation (`--repo`) must stay clean.
