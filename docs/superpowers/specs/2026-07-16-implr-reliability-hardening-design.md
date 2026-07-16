# implr Reliability Hardening — Design

**Date:** 2026-07-16
**Status:** Approved (brainstorm)
**Author:** implr maintainers

## Problem

An external review of the implr SDLC plugin found that the approach is sound but
**enforcement is weak**: the plugin is almost entirely prose-and-prompt Markdown, and
several of those prose contracts have drifted out of agreement with each other. A grounded
audit of the current files confirmed every finding and surfaced a few more.

Confirmed issues:

1. **Drift across four independent state machines.** The same fact is stated in multiple
   files that no longer agree:
   - Plan status: `plan-schema.md` says `ready | in-progress | done | blocked`; `README.md`
     uses `replan_required` (and drops `blocked`); `WORKFLOW.md` uses `changes-required` as a
     status; `cr-applier.md` writes a `replan_required: true` marker.
   - CR status: `README.md` invents an `impact-analysed` state absent from `cr-schema.md`.
   - Requirement status has its own vocabulary (`draft | under-review | approved | rejected |
     superseded`) — correct in the schema, not consistently reflected elsewhere.
2. **Cache path contract inconsistent.** Schema declares `cache/{slug}.md`; every producer
   and the digester use `cache/{slug}.txt`.
3. **Supported KB formats inconsistent.** README + extractor logic support 18 formats;
   `implr.config.yaml` defaults to 7; the digester validates against config, so fresh installs
   reject formats the README promises. README line 672 even shows a config value that does not
   match the shipped config file.
4. **Contradiction identity is a mutable `C-xxx` row ID** with no stable fingerprint. A
   regenerated synthesis can reassign IDs, stranding or misapplying human decisions.
5. **CR lifecycle under-specified vs its own schema.** `ba-cr` never stamps the CR file
   (`approved_at`, `applied_at`, `status → applied`), never writes `cr-log.md`, offers only
   `yes/no/impact-only` (no "selected" / exclusions), and drops `new_requirements_proposed`
   on the floor — no code path creates the new requirement file.
6. **Two unreconciled paths for applying a change to an existing requirement:** `/ba-cr`
   (in-place edit + `replan_required` marker) vs `/ba-requirements-gen --reprocess` (Phase 6,
   `approved → under-review`) — with different status semantics.
7. **`replan_required` is a limbo marker**, not a plan status value, so `plans-index.md`
   cannot represent it and `dev-executor --all` (keys off `status: ready`) never picks it up.
8. **No delta mechanism** when a CR touches an already-implemented plan: `--replan`
   regenerates the whole plan back to `ready` and re-execution re-runs every task even though
   the code exists.
9. **Code review cannot fail on failing tests.** `code-review-worker` is read-only (no Bash)
   and never consumes test output; the executor's self-reported `tests_pass` is not re-checked.
   `dev-code-review` also never performs the review→plan status write that `review-schema.md`
   and `WORKFLOW.md` both require.
10. **Unsafe commit default.** `plan-runner` defaults to `commit_mode: auto`, committing into
    whatever repo it runs in.
11. **No self-validation.** Prose schemas are not machine-checkable; there is no validation
    script, no fixtures, no ordering/precondition gates.

## Goals

- One canonical source of truth per fact; everything else references or is regenerated from it.
- A deterministic `implr-validate` command that catches drift and schema violations.
- A single, coherent, delta-safe CR → requirement → plan → code lifecycle, especially for the
  "requirement already implemented, new CR arrives" case.
- Stable contradiction identity that survives re-synthesis.
- A complete CR audit trail matching the shipped schema.
- Cheap precondition/ordering gates so skills refuse to run out of order.
- Test-aware code review and a safe commit default.
- **README.md and WORKFLOW.md kept in sync with every change above.**

## Non-Goals

- CI pipeline (deferred; `implr-validate` is run manually / by gates for now).
- Golden-fixture regression suite (deferred).
- Converting the whole plugin to a compiled toolchain — it stays Markdown-native plus one
  validation script.
- Per-task change-flag delta planning (rejected in favor of the simpler idempotent executor).

## Design

Eight coordinated workstreams. They are coupled through the status single-source-of-truth
(A), so they are designed together and implemented in a defined order.

### A. Single source of truth for all four state machines

Create `scaffold/schemas/status-vocabulary.md` as the sole definition of legal states and
transitions for **requirement**, **plan**, **review**, and **CR**. Every other file references
it by name; no file restates an enum inline.

Canonical vocabularies:

- **Requirement:** `draft | under-review | approved | rejected | superseded`
  (`superseded_by` points to the replacement). Unchanged from `requirement-schema.md`.
- **Plan:** `ready | in-progress | done | blocked | needs-rework` — `needs-rework` is **new**
  (see C.4), replacing the `replan_required` marker.
- **Review:** `approved | approved-with-warnings | changes-required | rejected`. Unchanged.
- **CR:** `draft | approved | rejected | applied`. Unchanged; README's `impact-analysed`
  removed.

Drift corrections made against this file:

- Remove `replan_required` (as a plan status) and `changes-required` (as a plan status) from
  `README.md` and `WORKFLOW.md`; restore `blocked`; add `needs-rework`.
- Remove `impact-analysed` from `README.md`'s CR lifecycle.
- Cache path: standardize on **`cache/{slug}.txt`** everywhere. Update `kb-index-schema.md`
  (the outlier) to `.txt`.
- Formats: set `implr.config.yaml` `kb_supported_formats` to the full 18-format list
  (`md, pdf, docx, xlsx, pptx, odp, odt, ods, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff,
  bmp`), matching README and the extractor. Update the `format` enum comment in
  `kb-index-schema.md`. Fix README line 672 to show the shipped value.

**Docs:** README.md and WORKFLOW.md status/lifecycle sections rewritten to cite
`status-vocabulary.md`.

### B. Machine-checkable schemas + `implr-validate`

For each prose schema, add a machine-readable companion capturing frontmatter field rules and
allowed enums (enums sourced from workstream A). Add `scripts/implr-validate` (Python 3, no
third-party deps, cross-platform) that walks `docs/implr/**` and checks:

- Every artefact's frontmatter has required fields with legal enum values.
- `status:` values are legal for the artefact type.
- Cross-references resolve (`linked_requirement`, `superseded_by`, CR `targets`, plan/req ID
  pairing PLAN-F-NNN ↔ REQ-F-NNN).
- Index files (`requirements-index.md`, `plans-index.md`, `cr-index.md`) agree with the files
  they list.

Exit non-zero on any violation, with a human-readable report. Invoked manually and by the
precondition gates (F). No CI wiring in this phase.

### C. Delta-safe, single-path CR lifecycle

This is the core of the reliability concern. Design chosen from brainstorm decisions.

**C.1 Explicit CR targets.** Add `targets: [REQ-F-NNN, ...]` to CR frontmatter. The author
fills what they know (empty allowed → "I'm not sure"). `cr-impact-analyzer` confirms and
augments the set and writes the resolved targets back to the CR file, so matching is auditable
rather than a pure Grep guess.

**C.2 One apply path.** `ba-cr` owns CR application end-to-end. `ba-requirements-gen
--reprocess` is reserved for **changed KB source documents only**, not CRs — removing the
dual-path ambiguity. (The `--reprocess <CR>` affordance and CR-schema "Consumed by
ba-requirements-gen (--reprocess)" line are updated accordingly.)

**C.3 New requirements from a CR are created by `ba-cr`.** When impact analysis finds a
genuinely new requirement is needed, `ba-cr` reuses the existing `requirements-domain-worker`
+ `.staging/` + post-hoc ID assignment machinery to draft it (`status: draft`, requires human
approval), instead of only reporting a count.

**C.4 First-class plan rework state.** Replace the `replan_required: true` marker with plan
status `needs-rework` plus `rework_cr: CR-NNN` and `rework_reason:` fields. `cr-applier` sets
these instead of writing a stub marker. `plans-index.md` gains a "Needs Rework" reflection;
`dev-executor` and `dev-planner` recognize `needs-rework`.

**C.5 Requirement-status transitions on CR** (finally exercising the unused `superseded`
machinery):

| Change kind | Requirement becomes | Plan effect |
|---|---|---|
| additive (new AC) | stays `approved` | plan gains new tasks; `needs-rework` |
| contradictory / correction | `under-review` | requires human re-approval before replan |
| override that replaces it | old → `superseded` (+`superseded_by`); new REQ created | new plan planned for the replacement |

Because `dev-planner` only replans `approved` requirements, contradictory/correction CRs force
re-approval — the intended human gate. This is made explicit in `WORKFLOW.md`.

**C.6 Delta execution via idempotent executor.** `dev-planner --replan` regenerates the plan
(status → `ready`, preserving `plan_id`). `dev-executor` re-runs the plan, but `task-executor`
becomes idempotent per task: run the task's test first; **if it already passes and the code
exists, skip and report `already-satisfied`**; otherwise implement. No plan-level task diff.
This avoids re-implementing everything while keeping the executor logic simple. `dev-executor`
picks up `needs-rework` plans (which `--replan` returns to `ready`).

**C.7 Provenance.** On completion, `dev-executor`/`plan-runner` records `implemented_files:` in
plan frontmatter so re-execution and review know what already exists.

**C.8 Traceability.** `cr-log.md` (see E) records CR → resolved targets → requirement status
changes → plans reworked → tasks re-executed vs already-satisfied → files touched.
`requirements-index.md` traceability matrix is extended to record originating CRs.

**Docs:** WORKFLOW.md CR section rewritten to describe the single path, the transition table,
`needs-rework`, and the idempotent re-execution behavior; README's Plans and CR lifecycle
sections updated.

### D. Stable contradiction fingerprint

Add `fingerprint:` to every contradiction row (domain synthesis, master synthesis) and to both
tables of `resolved-contradictions.md`:

```
fingerprint = hash(normalize(source_a) + source_b + statement_a + statement_b + type)
```

`ba-requirements-gen` Phase 0 idempotency keys on `fingerprint`, not `C-xxx`. `C-xxx` remains a
human-friendly display label only. The synthesizer computes the fingerprint deterministically;
the algorithm (normalization + hash) is defined once in `kb-index-schema.md`. Re-synthesis
reusing the same conflict keeps the human decision; a genuinely changed conflict yields a new
fingerprint and re-prompts.

**Docs:** WORKFLOW.md contradiction section updated to describe fingerprint-based matching.

### E. Complete the CR audit trail

Make `ba-cr` behavior match the schema it already ships:

- Stamp the CR file: `approved_at` at approval, `applied_at` + `status → applied` after all
  appliers succeed.
- Write `cr-log.md` (append-only, newest first) per `cr-schema.md`, including the
  **Excluded from apply** list.
- Approval gate becomes **all / selected / none** (matching `WORKFLOW.md:437`); record
  excluded targets in both `cr-log.md` and the report.
- Partial failure: if one applier fails, others stay applied (current behavior), but the CR
  file is **not** stamped `applied` — it stays `approved` with the failure recorded in
  `cr-log.md`.

**Docs:** README/WORKFLOW CR sections reflect the all/selected/none gate and the audit
artefacts.

### F. Precondition / ordering gates

Each SKILL.md gains a short **Preconditions** block checked at start; it may shell out to
`implr-validate` for the structural checks:

- `doc-ingest` → KB source docs exist.
- `ba-requirements-gen` → `master-synthesis.md` + `requirements-card.md` exist.
- `dev-planner` → `ARCHITECTURE.md` exists (already enforced) + target requirement `approved`.
- `dev-executor` → plan `ready` (or `needs-rework` returned to `ready`); `standards-card.md`
  exists (already enforced).
- `ba-cr` → a requirements set exists.

Also in this workstream (consistency fix): `dev-code-review` must set the linked plan back to
`in-progress` in `plans-index.md` on `changes-required`/`rejected`, as `review-schema.md:108`
and `WORKFLOW.md:269` require.

### G. Test-aware code review

`dev-executor` already tees each task's test output to a temp file. Have it persist a per-plan
`test-results.md` (pass/fail + captured output tail per task) under the plan's review inputs.
`code-review-worker` (read-only) reads that artefact and **must flag and downgrade its verdict**
(at least `changes-required`) if any covered test is not green. The review stays a read-through
— it does not run code — but can no longer certify code whose tests fail.

### H. Safe commit default

Flip `plan-runner` default from `commit_mode: auto` to `defer` (no commit). Auto-commit only
when `/dev-executor --commit` is passed (which sets `commit_mode: auto` in the plan-runner
dispatch). Update `dev-executor`, `plan-runner`, README, and WORKFLOW accordingly.

## Data / Contract Changes Summary

| File | Change |
|---|---|
| `scaffold/schemas/status-vocabulary.md` | **New** — canonical states for all four machines |
| `scaffold/schemas/*-schema.md` | Reference status-vocabulary; add machine-readable companions; cache path `.txt`; format enum; contradiction `fingerprint`; CR `targets`; plan `needs-rework`/`rework_cr`/`rework_reason`/`implemented_files` |
| `scaffold/config/implr.config.yaml` | `kb_supported_formats` → full 18-format list |
| `scripts/implr-validate` | **New** — deterministic validator |
| `skills/ba-cr/**` | Single apply path; new-req creation; CR stamping; cr-log.md; all/selected/none |
| `skills/dev-executor/**`, `.claude/agents/task-executor.md`, `plan-runner.md` | Idempotent per-task execution; `needs-rework` handling; `implemented_files`; `test-results.md`; commit default `defer` |
| `skills/dev-planner/**` | `needs-rework` recognition; replan returns to `ready` |
| `skills/dev-code-review/**`, `.claude/agents/code-review-worker.md` | Consume `test-results.md`; write plan status back |
| `.claude/agents/cr-*.md` | Explicit targets; set `needs-rework`; stamp CR |
| `skills/doc-ingest/**`, `.claude/agents/doc-ingest-synthesizer.md` | Contradiction fingerprint |
| `skills/**/SKILL.md` | Preconditions blocks |
| `README.md`, `docs/WORKFLOW.md` | Rewritten to match all of the above |

## Testing / Verification

- `implr-validate` run against a freshly scaffolded `docs/implr/` tree must pass.
- Manual walkthrough of the CR lifecycle on a sample requirement: additive CR (stays
  approved, new task executed), contradictory CR (drops to under-review, gated), and an
  already-implemented plan re-executed (unchanged tasks report `already-satisfied`).
- Grep sweep: no remaining `replan_required`/`impact-analysed`/`changes-required`-as-status
  tokens in README/WORKFLOW; no `cache/{slug}.md` references.

## Decomposition into Implementation Plans

Three coordinated plans, in order:

1. **Foundation — SSOT + validation + drift fixes** (A, B, D): status-vocabulary,
   machine-readable schemas + `implr-validate`, cache path, formats, contradiction
   fingerprint. Everything else depends on the canonical vocabularies existing.
2. **CR lifecycle** (C, E): single delta-safe path, `needs-rework`, new-req creation,
   idempotent executor, provenance, full audit trail.
3. **Review, gates & commit** (F, G, H): precondition gates, review→plan status write,
   test-aware review, safe commit default.

README.md and WORKFLOW.md updates land within each plan for the sections that plan touches, so
the docs never lag the behavior.
