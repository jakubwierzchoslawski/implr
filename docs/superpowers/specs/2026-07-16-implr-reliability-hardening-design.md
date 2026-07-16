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
- **LLM** golden-output regression suite (deferred). One small *deterministic* validator
  fixture is in scope — see B.4 — but capturing expected LLM-generated digests/requirements is
  not.
- Converting the whole plugin to a compiled toolchain — it stays Markdown-native plus one
  validation script.
- Per-task change-flag delta planning (rejected in favor of the simpler idempotent executor;
  the task fingerprint in C.6 is an executor-side idempotency key, not planner-side plan
  diffing).

## Design

Eight coordinated workstreams. They are coupled through the status single-source-of-truth
(A), so they are designed together and implemented in a defined order.

### A. Single source of truth for all four state machines

Create **`scaffold/schemas/status-vocabulary.json`** as the single machine-readable definition
of legal states and transitions for **requirement**, **plan**, **review**, and **CR**. JSON
(not YAML) is deliberate: `implr-validate` parses it with the Python standard library, which has
no YAML parser (see B). A thin prose `status-vocabulary.md` links to it for humans but restates
no enum values. Every other file (prose schemas, README, WORKFLOW, agents, SKILLs) references
the vocabulary by name and **must not restate an enum inline**; `implr-validate` (B) fails if
any file hardcodes an enum value that diverges from the JSON. This makes the vocabulary the one
source of truth rather than creating N companion copies of it.

Canonical vocabularies (defined in the JSON; shown here for the design record):

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

Rather than per-schema companion files (which would become new copies to drift), the
machine-readable contract is **one** artefact — `status-vocabulary.json` (A) plus a small
`scaffold/schemas/frontmatter-rules.json` capturing required frontmatter fields per artefact
type. Both are **JSON**, parsed by the Python standard library. Prose schemas reference these
and restate nothing.

**Parsing without third-party deps.** `scripts/implr-validate` is Python 3 (3.8+),
cross-platform, and uses **only the standard library**. Two consequences drive the format
choices:

- Contract files are JSON (`json` module), not YAML — the stdlib has no YAML parser.
- The artefact `.md` files carry **YAML frontmatter**, which the validator must read. Since
  implr owns every template that produces frontmatter, the schemas define a **restricted
  frontmatter subset** — scalars, quoted strings, flat inline lists (`[a, b]`), block lists of
  scalars, one level of nested mapping (e.g. `jira:`), and lists of simple `{id, reason}`
  objects — and `implr-validate` ships a small dedicated parser for exactly that subset.
  Frontmatter outside the subset is itself a validation error (it means a template drifted).
  This keeps the validator dependency-free without hand-waving over YAML parsing.

Two **modes**:

- **`--repo`** — validates the plugin *source* tree before release: `scaffold/**`,
  `skills/**`, `.claude/agents/**`, `README.md`, `docs/WORKFLOW.md`. Catches the drift class
  the review found (enums restated and divergent, cache-path `.md` vs `.txt`, format-list
  mismatch, retired-status tokens).
- **`--workspace`** — validates an installed project's `docs/implr/**` artefacts.

Both modes check:

- Every artefact's frontmatter parses within the subset and has required fields with legal enum
  values (enums read from `status-vocabulary.json`, fields from `frontmatter-rules.json`).
- `status:` values are legal for the artefact type.
- Cross-references resolve (`linked_requirement`, `superseded_by`, CR `targets`, plan/req ID
  pairing PLAN-F-NNN ↔ REQ-F-NNN).
- Index files (`requirements-index.md`, `plans-index.md`, `cr-index.md`) agree with the files
  they list.

**`--repo` prose checks, with an explicit allowlist to avoid brittleness:**

- **Banned retired tokens** — `replan_required`/`impact-analysed`/`changes-required`-as-a-status
  fail everywhere *except* historical records: `CHANGELOG.md` and `docs/superpowers/**` (specs
  and plans are dated design history) are exempt.
- **Divergent restated enums** — the "no inline enum that diverges from the JSON" check runs
  only on *live contract surfaces*: `scaffold/schemas/*.md` prose, `skills/**`,
  `.claude/agents/**`, `README.md`, `docs/WORKFLOW.md`. Exempt from this check: the
  `status-vocabulary.*` files themselves (they *define* the enums), `CHANGELOG.md`, and
  `docs/superpowers/**`. The allowed/exempt list lives in `frontmatter-rules.json` so it is
  itself reviewable, not buried in the script.

Exit non-zero on any violation, with a human-readable report. Invoked manually and by the
precondition gates (F). No CI wiring in this phase.

**B.4 Minimal deterministic fixture.** Add `tests/fixtures/sample-kb/` containing a
hand-authored miniature workspace: two KB docs with one seeded
contradiction, one requirement, one additive CR, and one correction CR — plus an
`expected-validate.txt` capturing the exact `implr-validate --workspace` outcome (pass, and the
specific violations when a field is deliberately broken). This is a *deterministic* check of
the validator and the schema contracts; it captures **no** LLM-generated output, so it needs no
CI and no model run to be useful. It is the regression net for contract drift.

### C. Delta-safe, single-path CR lifecycle

This is the core of the reliability concern. Design chosen from brainstorm decisions.

**C.1 Explicit CR targets.** Add `targets: [REQ-F-NNN, ...]` to CR frontmatter. The author
fills what they know (empty allowed → "I'm not sure"). `cr-impact-analyzer` stays **read-only**:
it returns the confirmed + augmented target set in its summary but writes nothing. The `ba-cr`
orchestrator writes the resolved set back to the CR file **after the approval/confirmation
gate** — mutation stays centralized in `ba-cr`, preserving the "impact analysis is read-only"
principle.

Three distinct notions are kept separate so "selected" approval (E) is unambiguous:

- **`targets:`** (CR frontmatter) — *all confirmed affected requirements*, i.e. the full impact
  set, independent of what the user chose to apply. This is the durable "what does this CR
  affect" record.
- **`applied_targets`** / **`excluded_targets`** — the per-run split from the all/selected/none
  gate. These are **run state**, recorded in `cr-log.md` (E), not on the CR frontmatter, because
  a later re-run may apply a previously excluded target.

Matching thus becomes auditable rather than a pure Grep guess.

**C.2 One apply path.** `ba-cr` owns CR application end-to-end. `ba-requirements-gen
--reprocess` is reserved for **changed KB source documents only**, not CRs — removing the
dual-path ambiguity. (The `--reprocess <CR>` affordance and CR-schema "Consumed by
ba-requirements-gen (--reprocess)" line are updated accordingly.)

**C.3 New requirements from a CR are created by `ba-cr`.** When impact analysis finds a
genuinely new requirement is needed, `ba-cr` reuses the existing `requirements-domain-worker`
+ `.staging/` + post-hoc ID assignment machinery to draft it (`status: draft`, requires human
approval), instead of only reporting a count.

**C.4 First-class plan rework state, with an explicit transition contract.** Replace the
`replan_required: true` marker with plan status `needs-rework` plus `rework_cr: CR-NNN` and
`rework_reason:` fields. `cr-applier` sets these instead of writing a stub marker. The
transitions are exact and enforced by `implr-validate` and the SKILL preconditions:

- `cr-applier` is the **only** writer of `done → needs-rework`.
- `dev-planner --replan` is the **only** transition `needs-rework → ready` (it regenerates the
  plan body, preserving `plan_id`).
- `dev-executor` **never executes a `needs-rework` plan directly.** If asked to, it halts and
  tells the user to run `/dev-planner --replan <plan>` first. `dev-executor` only executes
  `ready` (and resumes `in-progress` via `--task`).

`plans-index.md` gains a "Needs Rework" section so the state is visible.

**C.5 Requirement-status transitions on CR** (finally exercising the unused `superseded`
machinery):

| Change kind | Requirement becomes | Plan effect |
|---|---|---|
| additive (new AC) | stays `approved` | plan gains new tasks; `needs-rework` |
| contradictory / correction | `under-review` | requires human re-approval before replan |
| override that replaces it | old → `superseded` (+`superseded_by`); new REQ created | new plan planned for the replacement |

Because `dev-planner` only replans `approved` requirements, contradictory/correction CRs force
re-approval — the intended human gate. This is made explicit in `WORKFLOW.md`.

**C.6 Delta execution via idempotent executor with a task fingerprint.** After
`dev-planner --replan` returns a plan to `ready`, `dev-executor` re-runs it, but `task-executor`
skips work that is genuinely still current. A pure "test passes + code exists" check is too
weak — it can skip a task whose AC text changed while a stale test still passes. So each task
carries an **executed fingerprint**:

```
task_fingerprint = sha256(canonical_json({
  task_body, ac_ids, ac_text, files, tests_first,
  requirement_updated_at, arch_excerpt_hash,
  interfaces_contracts, applied_nfrs,
  standards_card_hash, test_runner
}))
```

The extra fields matter: a task can be invalidated by a standards-card change, an NFR
constraint change, an interface/contract change, or a different test runner — none of which
touch the AC text. Including them means such changes correctly force re-implementation instead
of a false `already-satisfied` skip.

`plan-runner` records the fingerprint per task on completion (alongside `implemented_files`).
On re-execution, `task-executor` **skips and reports `already-satisfied` only when the recorded
fingerprint matches the freshly computed one AND the task's tests pass**; otherwise it
implements. This keeps the executor simple (no planner-side plan diff — consistent with the
rejected change-flag approach) while refusing to skip stale or under-tested work.

**C.7 Provenance.** On completion, `plan-runner` records `implemented_files:` and the per-task
`task_fingerprint` in plan frontmatter, so re-execution (C.6) and review (G) know what already
exists and whether it is current.

**C.8 Traceability.** `cr-log.md` (see E) records CR → resolved targets → requirement status
changes → plans reworked → tasks re-executed vs already-satisfied → files touched.
`requirements-index.md` traceability matrix is extended to record originating CRs.

**Docs:** WORKFLOW.md CR section rewritten to describe the single path, the transition table,
`needs-rework`, and the idempotent re-execution behavior; README's Plans and CR lifecycle
sections updated.

### D. Stable contradiction fingerprint

Add `fingerprint:` and `fingerprint_version:` to every contradiction row (domain synthesis,
master synthesis) and to both tables of `resolved-contradictions.md`. The algorithm is
**order-independent and versioned**, defined once in `kb-index-schema.md`:

```
# fingerprint_version: 1
sides = sorted([                      # sort so swapping A/B does not change the hash
  {source: normalize(source_a), statement: normalize(statement_a)},
  {source: normalize(source_b), statement: normalize(statement_b)},
], by canonical json)
fingerprint = sha256(canonical_json({ version: 1, type: normalize(type), sides: sides }))
```

`normalize` = trim, collapse internal whitespace, lowercase, strip trailing punctuation —
applied to **all** fields, not just one. `canonical_json` = sorted keys, no insignificant
whitespace. Bumping `fingerprint_version` is the sanctioned way to change the algorithm without
silently orphaning past decisions.

`ba-requirements-gen` Phase 0 idempotency keys on `(fingerprint_version, fingerprint)`, not
`C-xxx`. `C-xxx` remains a human-friendly display label only. Re-synthesis reusing the same
conflict — even with A/B swapped — keeps the human decision; a genuinely changed conflict yields
a new fingerprint and re-prompts.

**Docs:** WORKFLOW.md contradiction section updated to describe fingerprint-based matching.

### E. Complete the CR audit trail

Make `ba-cr` behavior match the schema it already ships:

- Stamp the CR file: `approved_at` at approval, `applied_at` + `status → applied` after all
  appliers succeed.
- Write `cr-log.md` (append-only, newest first) per `cr-schema.md`, recording this run's
  `applied_targets` and `excluded_targets` (the schema's **Excluded from apply** field).
- Approval gate becomes **all / selected / none** (matching `WORKFLOW.md:437`). The confirmed
  impact set is written to CR `targets:` (C.1); the applied/excluded split for *this run* is
  recorded in `cr-log.md` and the report.
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
- `dev-executor` → plan is `ready`; `standards-card.md` exists (already enforced). A
  `needs-rework` plan is **rejected** with a message to run `/dev-planner --replan` first
  (per C.4).
- `ba-cr` → a requirements set exists.

Also in this workstream (consistency fix): `dev-code-review` must set the linked plan back to
`in-progress` in `plans-index.md` on `changes-required`/`rejected`, as `review-schema.md:108`
and `WORKFLOW.md:269` require.

### G. Test-aware code review

`dev-executor` already tees each task's test output to a temp file. Have it persist a per-plan
`test-results.md` under the plan's review inputs. To be trustworthy the artefact must be
**attributable and fresh**, so each entry records: `plan_id`, `task_id`, the exact test
`command`, `exit_code`, pass/fail, a captured output tail, an ISO `run_at` timestamp, and the
`source_ref` (git commit or worktree hash the run was executed against).

Because `code-review-worker` is read-only (no Bash), it cannot compute the current source
state itself. The **`dev-code-review` orchestrator** (which runs in main and can shell out)
computes `current_source_ref` and passes it into the worker's dispatch scope. The deterministic
rule: `git rev-parse HEAD` combined with a short hash of `git diff -- <src> <tests>` (so
uncommitted changes are captured); documented **non-git fallback**: a hash of the sorted
(path, size, mtime) tuples of the src/tests trees.

`code-review-worker` then applies a **staleness rule** — it flags and downgrades its verdict to
at least `changes-required` when the test results are: missing, not tied to the reviewed
`plan_id`, whose recorded `source_ref` ≠ the passed `current_source_ref`, or whose `run_at` is
earlier than the plan's `executed_at`. Otherwise it fails the plan on any non-green covered
test. The review stays a read-through — it does not run code — but can no longer certify code
whose tests fail or whose evidence is stale.

### H. Safe commit default

Flip `plan-runner` default from `commit_mode: auto` to `defer` (no commit). Auto-commit only
when `/dev-executor --commit` is passed (which sets `commit_mode: auto` in the plan-runner
dispatch). Update `dev-executor`, `plan-runner`, README, and WORKFLOW accordingly.

## Data / Contract Changes Summary

| File | Change |
|---|---|
| `scaffold/schemas/status-vocabulary.json` (+ thin `.md`) | **New** — single machine-readable (JSON, stdlib-parseable) canonical states/transitions for all four machines |
| `scaffold/schemas/frontmatter-rules.json` | **New** — required frontmatter fields per artefact type + `--repo` grep allowlist/banned-token config |
| `scaffold/schemas/*-schema.md` | Reference the JSON vocab; **restate no enums**; cache path `.txt`; format enum; contradiction `fingerprint`/`fingerprint_version`; CR `targets`; plan `needs-rework`/`rework_cr`/`rework_reason`/`implemented_files`/per-task `task_fingerprint` |
| `scaffold/config/implr.config.yaml` | `kb_supported_formats` → full 18-format list |
| `scripts/implr-validate` | **New** — deterministic stdlib-only validator (`--repo`/`--workspace`); ships a restricted-frontmatter-subset parser |
| `tests/fixtures/sample-kb/` | **New** — minimal deterministic fixture + `expected-validate.txt` (B.4) |
| `skills/ba-cr/**` | Single apply path; **ba-cr writes CR targets** (analyzer stays read-only); new-req creation; CR stamping; cr-log.md; all/selected/none |
| `skills/dev-executor/**`, `.claude/agents/task-executor.md`, `plan-runner.md` | Idempotent per-task execution via `task_fingerprint`; halt on `needs-rework`; `implemented_files`; attributable `test-results.md`; commit default `defer` |
| `skills/dev-planner/**` | `needs-rework → ready` is the only replan transition; replan preserves `plan_id` |
| `skills/dev-code-review/**`, `.claude/agents/code-review-worker.md` | Orchestrator computes/passes `current_source_ref`; worker consumes `test-results.md` with staleness rule; write plan status back |
| `.claude/agents/cr-*.md` | `cr-impact-analyzer` returns targets (no writes); `cr-applier` sets `done → needs-rework` |
| `skills/doc-ingest/**`, `.claude/agents/doc-ingest-synthesizer.md` | Order-independent versioned contradiction fingerprint |
| `skills/**/SKILL.md` | Preconditions blocks |
| `README.md`, `docs/WORKFLOW.md` | Rewritten to match all of the above |

## Testing / Verification

- `implr-validate --repo` passes on the plugin source tree; `implr-validate --workspace` passes
  on a freshly scaffolded `docs/implr/` tree.
- The B.4 fixture: `implr-validate --workspace` against `tests/fixtures/sample-kb/` produces
  exactly `expected-validate.txt`, both in the clean state (pass) and with a deliberately broken
  field (the specific expected violation).
- Manual walkthrough of the CR lifecycle on a sample requirement: additive CR (stays
  approved, new task executed), contradictory CR (drops to under-review, gated), and an
  already-implemented plan re-executed (current tasks report `already-satisfied` via matching
  `task_fingerprint`; a task whose AC text changed is re-implemented).
- Grep sweep (part of `--repo`): no remaining `replan_required`/`impact-analysed`/
  `changes-required`-as-status tokens in README/WORKFLOW; no `cache/{slug}.md` references; no
  enum values restated in prose that diverge from `status-vocabulary.json`.

## Decomposition into Implementation Plans

Three coordinated plans, in order:

1. **Foundation — SSOT + validation + drift fixes** (A, B, D): machine-readable
   `status-vocabulary.json` + `frontmatter-rules.json`, `implr-validate` (`--repo` +
   `--workspace`), the B.4 fixture, cache path, formats, versioned contradiction fingerprint.
   Everything else depends on the canonical vocabularies existing.
2. **CR lifecycle** (C, E): single delta-safe path, `needs-rework`, new-req creation,
   idempotent executor, provenance, full audit trail.
3. **Review, gates & commit** (F, G, H): precondition gates, review→plan status write,
   test-aware review, safe commit default.

README.md and WORKFLOW.md updates land within each plan for the sections that plan touches, so
the docs never lag the behavior.
