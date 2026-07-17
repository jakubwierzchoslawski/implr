# implr Workflow — Deep Dive

This document explains how implr works internally: how data flows between skills, how
incremental processing works, and how the artefacts relate. Read the [README](../README.md)
first for installation and commands.

---

## The Artefact Graph

Every artefact implr produces traces back to source documentation:

```
docs/kb/**                      source documents (you own these)
   │
   ▼  doc-ingest
docs/implr/kb-index/
   ├── cache/{slug}.txt        normalised text per file
   ├── digests/per-doc/         one structured digest per file
   ├── domains/{domain}-synthesis.md   consolidated per domain + contradictions
   └── master-synthesis.md      system-wide view (bounded size)
   │
   ├──────────────▼  arch-gen
   │           docs/ARCHITECTURE.md
   │
   ▼  ba-requirements-gen
docs/implr/requirements/
   ├── functional/REQ-F-*.md
   └── non-functional/REQ-N-*.md
   │
   ▼  dev-planner   (reads ARCHITECTURE.md + DEV-STANDARDS.md)
docs/implr/plans/
   ├── functional/PLAN-F-*.md
   └── non-functional/PLAN-N-*.md
   │
   ▼  dev-executor  (reads ARCHITECTURE.md + DEV-STANDARDS.md)
src/**  tests/**
docs/implr/plans/test-results/{plan_id}-results.md   (written by plan-runner)
   │
   ▼  dev-code-review  (fresh context; test-aware — staleness rule on the file above)
docs/implr/reviews/REVIEW-F-*.md
```

Traceability chain: `source doc → digest → domain synthesis → requirement → plan → code → review`.

---

## Subagent Dispatch Model (v3.0)

Every skill in v2.0 is an **orchestrator** that runs in the main conversation context. It
handles user interaction (questions, confirmations) and dispatches heavy phases to dedicated
subagents living under `.claude/agents/`. Each subagent has a focused system prompt, a
restricted tool allowlist, and a tier-appropriate model.

### Which phases dispatch

| Skill | Phase | Subagent | Default model | Parallel? |
|---|---|---|---|---|
| doc-ingest | Phase 3 (extract) | doc-ingest skill (inline) | shell-only: cp / pdftotext / python; no LLM token cost | — |
| doc-ingest | Phase 4 (digest) | doc-ingest-digester | sonnet | Yes (cap 5) |
| doc-ingest | Phase 5 (domain synthesis) | doc-ingest-synthesizer | sonnet | Yes (cap 5) |
| arch-gen | Phase 4 (draft) | arch-drafter | sonnet | No (single dispatch) |
| ba-requirements-gen | Phase 3 (per-domain) | requirements-domain-worker | sonnet | Yes (cap 5) |
| ba-requirements-gen | Phase 9 (coherence) | Explore (built-in) | n/a | No |
| ba-cr | Phase 2 (impact) | cr-impact-analyzer | sonnet | No |
| ba-cr | Phase 4 (apply) | cr-applier | sonnet | Yes (cap 5) |
| dev-planner | Phase 5 (plan-one) | plan-worker | sonnet | Yes per wave (cap 5) |
| dev-planner | Phase 6 (coherence) | Explore (built-in) | n/a | No |
| dev-executor | Phase 4 (arch excerpt) | arch-excerpter | sonnet | One per plan, before dispatch |
| dev-executor | Phase 5 (plan execute) | plan-runner | **opus** | Yes per wave (cap 5) |
| dev-executor | Phase 5 (per-task) | task-executor | **opus** | Sequential within each plan-runner |
| dev-code-review | Phase 2 (review) | code-review-worker | sonnet | Yes (cap 5) |

> **v3.1:** Text extraction is now inline in the `doc-ingest` skill (direct shell calls).
> The `doc-ingest-extractor` subagent has been removed — file content no longer enters an
> LLM context window during extraction.

> **v3.1:** `ba-requirements-gen` builds an inline `domain_envelope` per dispatch.
> `requirements-domain-worker` no longer reads `requirement-schema.md`,
> `implr.config.yaml`, `DEV-STANDARDS.md`, or `master-synthesis.md` — the orchestrator
> reads them once, packages the executable subset as `requirements_card` (auto-generated
> by `/implr-init`), and embeds them inline. Mirrors the v3.0 `task-executor` envelope
> contract.

### Model override

Users override per agent in `docs/implr/config/implr.config.yaml` under the `agents:`
key. Values: `haiku`, `sonnet`, `opus`. Resolution: config value wins; falls back to the
agent's `default_model` declared in `.claude/agents/<name>.md`.

### Dispatch payload contract

Each dispatch carries a small scope payload (file path, requirement id, domain name —
whatever the worker needs to act on). The orchestrator never sends the full phase
instructions inline; they live in `skills/<skill>/phases/*.md` and in the agent's system
prompt body. This keeps payloads small and prompt-cache hits high.

### Stable-reads-first convention

Every skill and every phase prompt reads stable inputs (schemas, `implr.config.yaml`,
`DEV-STANDARDS.md`) **before** any dynamic input (the file being processed, the
requirement being planned). This makes Anthropic's 5-minute prompt cache reuse the prefix
across dispatches within a session.

### Why this saves tokens

- Per-task envelopes: task-executor never re-reads the full plan, schema, ARCHITECTURE.md, or DEV-STANDARDS.md.
- plan-runner has no stable reads — replaces v2's per-plan dispatcher (~30k stable prefix gone).
- standards-card (~55 lines auto-generated) replaces DEV-STANDARDS.md reads in task-executor and code-review-worker.
- arch-excerpter runs once per plan (Sonnet); amortises over all tasks in that plan.
- Independent units still dispatch in parallel — same wall-clock, lower per-token spend.

Typical end-to-end runs cost 6–10× fewer tokens than v1.x.

---

## Incremental Processing — How It Stays Fast

The core idea: **checksums gate every stage**, so unchanged inputs are never reprocessed.

### Checksum propagation

```
file checksum (md5 of original bytes)
   │ change here ...
   ▼
per-doc digest (records source checksum)
   │ ... forces rebuild here ...
   ▼
domain synthesis (synthesis_checksum = hash of its source digest checksums)
   │ ... forces rebuild here ...
   ▼
master synthesis (master_checksum = hash of domain synthesis_checksums)
   │ ... brings the domain back into scope here ...
   ▼
requirements for that domain
```

If a file's checksum is unchanged, nothing downstream of it is touched. If one file in a
50-document KB changes, doc-ingest re-digests that one file, rebuilds that one domain synthesis,
rebuilds the master synthesis, and ba-requirements-gen reprocesses only that domain.

### Why digests exist

A large knowledge base cannot all fit usefully in one context window. Reading 50 raw documents
to generate requirements produces shallow output. So:

- **doc-ingest** reads raw documents once and produces a complete structured digest per file —
  every business rule, behaviour, entity, and integration point enumerated.
- **Domain syntheses** consolidate digests per domain and catch contradictions.
- **The master synthesis** is a bounded, system-wide briefing.
- **ba-requirements-gen** workers read domain and master syntheses. When a synthesis is
  insufficient they fall back to the per-doc digest — never to the raw cache. The digest is
  the complete structured extraction; the cache is the raw text used only by the digester.

This mirrors how a human BA works: read the briefing, then go to the structured notes only
for the details that matter — not back to the original raw document.

### Why the text cache exists

- **Extract once.** Binary and structured formats (PDF, DOCX, XLSX, CSV) require extraction
  tools — expensive to repeat. The cache is written once and only re-extracted when the source
  checksum changes.
- **Digester's input only.** The cache is the input to `doc-ingest-digester` and nothing else.
  Downstream skills (`ba-requirements-gen`, `arch-gen`) never read cache directly — they read
  digests, which are the complete structured extraction of each source file.
- **Checksum gate.** `cache/{slug}.txt` is written with the source checksum recorded. On
  subsequent runs, if the checksum is unchanged the cache is skipped and the existing digest
  is reused — no re-extraction needed.

---

## Contradiction Detection

Contradictions are found at synthesis time, resolved before requirement generation.

1. When a document changes, its digest is rebuilt.
2. The domain synthesis is rebuilt by reading **all** digests in that domain together — so a new
   document is automatically compared against every existing document in its domain.
3. Contradictions are classified: Hard conflict, Soft conflict, Version drift, Scope overlap.
   Each is given a stable `(fingerprint_version, fingerprint)` — a versioned SHA-256 over its
   normalised, order-independent fields, computed by `scripts/implr_validate --fingerprint`
   (an LLM must not hand-compute it). A `C-xxx` ID is also assigned as a display label only.
4. Cross-domain contradictions are caught when the master synthesis is rebuilt from domain
   syntheses.
5. When you run `/ba-requirements-gen`, **Phase 0** reads all C-xxx IDs from the domain and
   master syntheses, presents each unresolved one to you with both conflicting sources, and
   records your decision in `docs/implr/requirements/resolved-contradictions.md`.
6. Workers receive the resolved decisions map. Resolved contradictions are used as authoritative
   content — they do not become Open Questions. Deferred contradictions become Open Questions
   with the C-ID preserved in the Source column (`Source: C-003 (deferred)`).

`resolved-contradictions.md` is append-only. Re-running `/ba-requirements-gen` only prompts
for contradictions whose `(fingerprint_version, fingerprint)` is not already in the file —
matching is by fingerprint, never by `C-xxx` label. To change a decision, edit the file
manually and re-run.

To halt on any deferred contradictions that become Open Questions, set
`contradictions_block: true` in `docs/implr/config/implr.config.yaml`.

---

## The Human Gates

implr deliberately stops for human judgement at three points:

1. **Requirement approval.** ba-requirements-gen creates requirements as `draft`. dev-planner
   only processes `approved` ones. A human reviews, resolves open questions, and promotes status.

2. **Architectural decisions.** arch-gen marks inferred decisions and asks for confirmation
   before writing ARCHITECTURE.md. On re-runs it proposes a diff rather than overwriting.

3. **Design decisions (optional).** `dev-planner --brainstorm` presents design options and
   records the human's choices before generating the plan.

Everything else is automated.

---

## Ordering Gates

Separate from the human-judgement gates above, five stages each carry a machine-checked
precondition: a required artefact or status that must already be in place before the stage
runs. Each stage's own `SKILL.md` states this under a `## Preconditions` heading; this is
where a reader checks the exact gate for any given stage.

| Stage | Precondition | On failure |
|---|---|---|
| doc-ingest | At least one KB source document exists under `docs/kb/`. | Halts: "No KB documents found under docs/kb/. Add source docs first." |
| ba-requirements-gen | `docs/implr/kb-index/master-synthesis.md` exists, and `docs/implr/config/requirements-card.md` exists. | Halts pointing at `/doc-ingest` (missing synthesis) or the Phase 0 setup error (missing requirements-card). |
| dev-planner | `docs/ARCHITECTURE.md` exists, and each in-scope requirement is `status: approved` (unless named explicitly or `require_approved_status: false`). | Halts pointing at `/arch-gen` for the missing architecture doc. |
| dev-executor | `docs/implr/config/standards-card.md` exists, and every in-scope plan is `status: ready`. | Halts before any dispatch if the card is missing; a `needs-rework` plan is rejected outright, pointing at `/dev-planner --replan`. |
| ba-cr | A requirements set exists under `docs/implr/requirements/`. | Warns that a CR with no requirements to target can only create genuinely-new ones. |

These gates are ordering constraints, not judgement calls — they exist so a stage never runs
against an artefact that doesn't exist yet or a plan/requirement whose status says it isn't
ready for this stage.

---

## Status Lifecycles

### Requirement

```
draft → under-review → approved → superseded
                     ↘ rejected
```

| Transition | Who | Condition |
|-----------|-----|-----------|
| `draft` → `under-review` | Human | Requirement needs discussion before approval |
| `draft` → `approved` | Human | Requirement is correct and complete |
| `under-review` → `approved` | Human | Open questions resolved |
| `under-review` → `rejected` | Human | Requirement is invalid or out of scope |
| `approved` → `under-review` | ba-requirements-gen or cr-applier | A source doc changed, or a CR is contradictory/a correction, and the requirement may be affected |
| `approved` → `superseded` | cr-applier | An override CR replaces this requirement (`superseded_by` set; ba-cr creates the new requirement) |

Claude only ever creates `draft`. Only humans promote to `approved`. ba-requirements-gen
and cr-applier can drop `approved` → `under-review` but never to `draft` (preserving review
history). See [Requirement Transitions from a CR](#requirement-transitions-from-a-cr) in
[Change Requests](#change-requests) for the exact change-kind → status mapping cr-applier
uses.

*In v2.0, the requirement-write transitions are performed by the `requirements-domain-worker`
subagent (one per domain, in parallel) dispatched from the `ba-requirements-gen`
orchestrator. The orchestrator does post-hoc sequential ID assignment after all workers
return.*

---

### Plan

```
ready → in-progress → done
  ↑                     │
  │                     ├─► in-progress   (review verdict of changes-required or rejected)
  │                     └─► needs-rework  (a CR mandates plan changes, set by cr-applier)
blocked → ready               (once the blocker is resolved)
needs-rework → ready          (dev-planner --replan regenerates the plan)
```

Legal plan states and transitions are defined once in
`docs/implr/schemas/status-vocabulary.json`; this table mirrors it. `changes-required` is a
**review** verdict, not a plan status.

| Transition | Who | Condition |
|-----------|-----|-----------|
| `ready` | dev-planner | Plan created; ready for a developer to start |
| `ready` → `in-progress` | dev-executor | Developer starts implementation |
| `in-progress` → `done` | dev-executor | All tasks complete; code submitted for review |
| `done` → `in-progress` | dev-executor | Review verdict is changes-required or rejected; developer reopens the plan |
| `done` → `needs-rework` | cr-applier | A CR mandates plan changes |
| `needs-rework` → `ready` | dev-planner | `dev-planner --replan` regenerates the plan (only exit from needs-rework) |
| `ready` → `blocked` | dev-planner | A required dependency has no plan yet |
| `in-progress` → `blocked` | dev-executor | A hard blocker halts implementation |
| `blocked` → `ready` | Human or dev-planner | Blocker resolved |

Committing to git is **not** part of this transition table's side effects. `plan-runner`'s
`commit_mode` defaults to `defer`: reaching `done` leaves the worktree exactly as-is (no
`git add`/`git commit`). Only `/dev-executor --commit` switches a run to `commit_mode: auto`,
which makes `plan-runner` run `git add -A` and commit once the plan reaches `done`.

### Test-aware review

Alongside code, `plan-runner` writes a per-plan test-results artefact —
`docs/implr/plans/test-results/<plan_id>-results.md`, per
`docs/implr/schemas/test-results-schema.md` — recording `plan_id`, `run_at`, `source_ref`
(the same `implr_validate --source-ref` value used below), `executed_at`, and one row per
task: `Task`, `Command`, `Exit`, `Result` (`pass`/`fail`/`skip`), `Output tail`. `Result` is
`skip` only when no test ran for a task that doesn't require one — `skip` is never treated as
a failure.

Each `code-review-worker` dispatch computes `current_source_ref` (via
`implr_validate --source-ref`) and, before checking any acceptance criterion, reads that
plan's test-results file and applies the **staleness rule**: the review downgrades to at
least `changes-required` when the file is missing, its `plan_id` doesn't match the reviewed
plan, its `source_ref` doesn't match `current_source_ref`, or its `run_at` predates the
plan's `executed_at`. When the file passes freshness, any AC-covering test row whose `Result`
is `fail` is a Critical finding; `skip` rows are never a failure. Either way, a review can
never approve code whose tests are stale or failing.

### Review verdict → plan effect
| Verdict | Plan effect |
|---------|------------|
| approved / approved-with-warnings | plan stays `done` |
| changes-required / rejected | plan set back to `in-progress`, blocking findings noted |

`dev-code-review` performs this write itself (Phase 4.5 of the orchestrator): for every
review verdict of `changes-required` or `rejected`, it sets the linked plan's `status` to
`in-progress` in both `plans-index.md` and the plan file, and records the blocking finding
ids in the plan's `## Risks and Notes`.

*In v3.0, plan creation is performed by parallel `plan-worker` subagents (one per requirement per dependency wave). Plan execution is orchestrated by `dev-executor`: it parses each plan into per-task envelopes, dispatches `arch-excerpter` (Sonnet) once per plan, then dispatches `plan-runner` (Opus) per plan in parallel waves. Each plan-runner dispatches one `task-executor` (Opus) per task sequentially, then writes the plan's test-results.md and commits only if `commit_mode: auto`. Plan review is performed by parallel `code-review-worker` subagents (one per plan, receiving `standards-card` inline and applying the test-results staleness rule above).*

---

### Change Request (CR)

```
draft → approved → applied
      ↘ rejected
```

| Transition | Who | Condition |
|-----------|-----|-----------|
| `draft` | ba-cr | CR created from CLI interview, manual file, or auto-generated from KB doc |
| `draft` → `approved` | Human | Chooses `all` or `selected` at the ba-cr approval gate |
| `draft` → `rejected` | Human | Chooses `none` at the ba-cr approval gate |
| `approved` → `applied` | ba-cr | Every dispatched `cr-applier` succeeded across all `applied_targets` |

`rejected` is a terminal state. Create a new CR to supersede a rejected one. A CR is never
edited after creation — it is a point-in-time record of intent.

The CR's `targets:` field is author-optional: name candidate requirement IDs while authoring
the CR, or leave it empty and let impact analysis find them. Either way, `cr-impact-analyzer`
(read-only) returns the full `confirmed_targets` set — it never writes to the CR file. At the
gate, `ba-cr` writes `confirmed_targets` to the CR's `targets:` frontmatter, then dispatches
`cr-applier` only against the subset the human approved (`applied_targets`); the rest of
`confirmed_targets` become `excluded_targets` for this run and are recorded in `cr-log.md`.

`cr-applier` applies the change-kind-specific requirement transitions (see
[Requirement Transitions from a CR](#requirement-transitions-from-a-cr)) and, for a plan that
needs full regeneration, sets `status: needs-rework` — never `ready` directly; the only exit
is `dev-planner --replan` (see [Plan](#plan) above). The CR is stamped `applied` only once
every applied target succeeds.

*In v2.0, impact analysis is performed by `cr-impact-analyzer` (read-only); applying the
CR is performed by parallel `cr-applier` dispatches, one per applied target (requirement or
plan). The `ba-cr` skill orchestrates both phases, and dispatches
`requirements-domain-worker` (Phase 4.5) to draft any genuinely new requirement the impact
analysis proposes.*

---

## TDD Enforcement

Complexity drives TDD. Each requirement and each plan task carries a complexity rating; the
`default_tdd_threshold` in config (default `M`) decides where TDD becomes mandatory.

| Complexity | Meaning | TDD |
|------------|---------|-----|
| XS | Trivial | after |
| S | Simple | after |
| M | Moderate | tests first |
| L | Complex | tests first |
| XL | High risk | tests first |

For TDD tasks, dev-planner lists the exact tests to write first, and dev-executor writes them
before the implementation (red → green → refactor). dev-code-review checks that the produced
tests match the plan's "tests first" list.

---

## What Each Skill Reads and Writes

| Skill | Reads | Writes |
|-------|-------|--------|
| implr-init | bundled assets | docs/implr structure, config, CLAUDE.md |
| doc-ingest | docs/kb/**, config | kb-index/** (index, cache, digests, syntheses, log) |
| arch-gen | master-synthesis, arch docs, template | docs/ARCHITECTURE.md |
| ba-requirements-gen | syntheses, requirement schema, config | requirements/** |
| dev-planner | approved requirements, ARCHITECTURE.md, DEV-STANDARDS.md, plan schema | plans/** |
| dev-executor | plans, standards-card.md (arch-excerpter reads ARCHITECTURE.md once per plan) | src/**, tests/**, plan status, plans/test-results/*-results.md; commits only with `--commit` (default: worktree untouched) |
| dev-code-review | plan, requirement, code, ARCHITECTURE.md, standards-card.md, review schema, plans/test-results/*-results.md | reviews/**, plan status (on changes-required/rejected) |

Note the clean separation: only doc-ingest writes kb-index; only ba-requirements-gen writes
requirements; only dev-planner writes plans; only dev-executor writes code; only dev-code-review
writes reviews. No skill edits another skill's artefacts except for status fields a downstream
skill is explicitly responsible for (dev-executor and dev-code-review update plan status).

---

## When a New Document Changes an Existing Requirement

The most important real-world scenario: a new document is added to `docs/kb/` after a
requirement has already been planned and possibly implemented.

```
1. /doc-ingest --file docs/kb/new-policy.md
   → detects new doc, rebuilds domain synthesis, flags any contradiction

2. /ba-requirements-gen
   → sees changed domain synthesis
   → updates REQ-F-007: new AC added + open question for contradiction
   → drops status from approved → under-review
   → appends warning to requirements-log.md
   → reports: "REQ-F-007 updated. PLAN-F-007 exists (done). Human review needed."

3. Human reviews REQ-F-007 and the warning
   Option A: new AC is additive, existing code handles it
             → set status: approved; no re-planning needed
   Option B: new policy changes described behaviour
             → set status: approved; run /dev-planner --replan REQ-F-007

4. /dev-planner --replan REQ-F-007    (only if Option B)
5. /dev-executor PLAN-F-007           (implements the delta)
6. /dev-code-review PLAN-F-007        (reviews)
```

Key rules:
- ba-requirements-gen never drops an `approved` requirement back to `draft` — only to
  `under-review`, preserving the review history
- dev-planner never automatically invalidates a plan — it adds a visible warning and leaves
  the decision to the human
- Only material changes (new ACs, changed behaviour) trigger `under-review`; minor
  clarifications leave `approved` untouched

---

## Log Files vs Index Files

Two files that sound similar but serve distinct purposes:

**`requirements-index.md`** — current-state register:
- What requirements exist right now: IDs, titles, statuses, dependencies, linked plans
- Traceability matrix (source document → requirement IDs)
- "Needs Human Review" section for open questions and unresolved contradictions
- Read by: dev-planner (to find approved requirements), humans tracking status

**`requirements-log.md`** — append-only history:
- Every ba-requirements-gen run, timestamped
- Which domain syntheses were processed and their checksums at processing time
- Which requirements were created or updated in each run
- Contradictions surfaced and post-implementation update warnings
- Read by: ba-requirements-gen as its incremental gate — without it, ba-requirements-gen
  cannot know which synthesis checksums it last processed and would reprocess everything

The same pattern applies to `digest-log.md` (owned by doc-ingest): it is the history record,
not the index. `index.md` is the current state of the KB file registry.

---

## Extending implr

To add a skill (for example the planned `ba-jira-populate`):

1. Create `skills/<name>/SKILL.md` with frontmatter (name, description with trigger phrases).
2. If it needs schemas or templates, add them under `scaffold/schemas/` or `scaffold/seeds/`.
   The installer copies `scaffold/schemas/` to `docs/implr/schemas/` and `scaffold/seeds/` files
   to `docs/implr/` as skip-if-exists seeds.
3. Reference `docs/implr/` paths from the SKILL.md — never bundle data inside the skill.
4. Add the skill to the installer's skill list and to the README skills table.
5. Validate before release.

Keep skills thin (instructions only) and the schemas authoritative (data structures live in one
place that every skill references).

---

## Change Requests

A Change Request (CR) is the structured path for amending requirements after they have
already been generated — whether to correct a constraint, reduce scope, introduce a new rule,
or override a prior decision.

CRs live in `docs/kb/change-requests/` as first-class KB documents. They are ingested,
digested, and synthesised by `doc-ingest` exactly like any other source document. Every
requirement update triggered by a CR is traceable: the CR file is added to the requirement's
`source_docs` list.

### The delta-safe flow, end to end

```
author (optional) targets:  →  cr-impact-analyzer (read-only)  →  confirmed_targets
                                                                        │
                                                       all / selected / none / impact-only
                                                                        │
                             ba-cr writes targets: = confirmed_targets ▼
                             ba-cr dispatches cr-applier only to applied_targets
                             ba-cr creates genuinely-new requirements (Phase 4.5) if proposed
                                                                        │
                    cr-applier: requirement transitions + done → needs-rework on plans
                                                                        │
                              dev-planner --replan  (sole path back to ready)
                                                                        │
                          CR stamped applied + cr-log.md (applied/excluded targets)
```

The author may name candidate requirement IDs in the CR's `targets:` field, or leave it
empty. `cr-impact-analyzer` never trusts (or requires) that list blindly — it confirms each
named target still exists and is affected, discovers any additional affected requirement,
and returns the union as `confirmed_targets`. It writes nothing; only `ba-cr`, after the
human gate, persists `confirmed_targets` to the CR's `targets:` frontmatter.

### CLI path (most common)

```
1. Tell ba-cr what you want to change (free-form statement)
   /ba-cr  →  "I want to limit Azure costs to $20–50/month"

2. ba-cr interviews you for any missing required fields, then creates:
   docs/kb/change-requests/CR-NNN-slug.md

3. ba-cr dispatches `cr-impact-analyzer` to analyse impact across all requirements/plans;
   it returns `confirmed_targets` (read-only — the CR file is not written yet)

4. ba-cr presents the impact report with affected requirements, their plans, and any
   genuinely-new requirements the analysis proposes

5. You approve:
   all         — apply to every confirmed target
   selected    — you pick which requirement IDs to apply; the rest are recorded as
                 excluded_targets for this run
   none        — do not apply
   impact-only — persist the impact report to the CR and stop without applying

6. ba-cr writes the full `confirmed_targets` set to the CR's `targets:` frontmatter
   (regardless of which option was chosen), then — on `all`/`selected` — dispatches
   parallel `cr-applier` subagents against `applied_targets` only (one per affected
   requirement, one per affected plan). If the impact analysis proposed genuinely-new
   requirements, ba-cr dispatches `requirements-domain-worker` to draft them (Phase 4.5)
   and adds them as `draft` — they still need human approval before planning.

7. Plans the applier set to `needs-rework` are queued; ba-cr offers to run
   `/dev-planner --replan` for them — the only transition out of `needs-rework`.
   `/arch-gen --update` is suggested only if the architecture domain was touched.

8. Once every applied target succeeds, ba-cr stamps the CR `status: applied` and
   `applied_at`, then prepends an entry to `cr-log.md` recording `Applied targets` and
   `Excluded targets` for this run.
```

### Requirement Transitions from a CR

`cr-applier` sets requirement status according to the CR's change kind — never a generic
rule. This table is authoritative for what a CR-driven apply does to a requirement:

| Change kind | Requirement status effect |
|-------------|---------------------------|
| additive | Requirement stays `approved`; the new acceptance criteria are appended, existing ACs untouched |
| contradictory / correction | Requirement set to `under-review`; the rule is replaced; an Open Question citing the CR is added |
| override that replaces | Old requirement set to `superseded` (`superseded_by` set to the new requirement's id); a new requirement is created |

`source_docs` on the target requirement always gains the CR filename, regardless of change
kind. Legal requirement states and transitions are defined once in
`docs/implr/schemas/status-vocabulary.json`; this table describes the CR-specific subset of
the `approved → under-review` and `approved → superseded` transitions already listed in
[Requirement](#requirement) above.

### Manual-file path

Use when you prefer to author the CR file yourself (e.g. drafting offline, team review).

```
1. Copy docs/implr/templates/cr-template.md → docs/kb/change-requests/CR-NNN-slug.md
2. Fill in the required fields (title, change_type, before, after, rationale)
3. /doc-ingest
   → doc-ingest detects the new CR file and prints:
     ⚠️  New change request detected: CR-NNN-slug.md
         Run /ba-cr --file docs/kb/change-requests/CR-NNN-slug.md to analyse impact and apply.
4. /ba-cr --file docs/kb/change-requests/CR-NNN-slug.md
   → skips the interview; continues from doc-ingest chain onward
```

**Important:** doc-ingest never auto-chains ba-cr. Step 4 is always an explicit user action.

### KB-document path (--ingest-file)

Use when you've added a new or updated document to the KB that logically changes existing
requirements — without writing a CR file yourself.

```
1. Add the new document to docs/kb/
   (e.g. a new version of a pricing policy, a revised architecture spec)

2. /ba-cr --ingest-file docs/kb/{your-new-doc}.md

   ba-cr automatically:
   a. Runs /doc-ingest --file on the new document
   b. Reads the domain synthesis diff to understand what changed
   c. Auto-generates CR-NNN with source: kb-document
   d. Runs /doc-ingest --file on the CR file itself
   e. Runs impact analysis → presents impact report with confirmed_targets
   f. Waits for your approval: all / selected / none / impact-only (same gate as CLI path)
   g. On approval: same apply path as the CLI path from step 6 onward — ba-cr writes
      targets:, dispatches cr-applier to applied_targets, creates new requirements via
      Phase 4.5 if proposed, queues needs-rework plans for /dev-planner --replan, and
      suggests /arch-gen --update only if the architecture domain was touched

Alternatively, run /doc-ingest first (to refresh the KB), then use the hint it prints:
   💡 New KB document ingested: {filename}
      If this document changes existing requirements, run:
      /ba-cr --ingest-file {original_path}
```

All three paths produce the same CR artefact and cr-log entry. The only difference is how
the CR content is captured: interview (cli-direct), manual file, or digest extraction
(kb-document).

### CR artefacts

| File | Purpose |
|------|---------|
| `docs/kb/change-requests/CR-NNN-slug.md` | The CR document (source of truth) |
| `docs/implr/requirements/cr-index.md` | Current-state register of all CRs |
| `docs/implr/requirements/cr-log.md` | Append-only history of ba-cr runs |
| `docs/implr/schemas/cr-schema.md` | Canonical CR, cr-index, cr-log structures |
| `docs/implr/templates/cr-template.md` | Blank template for manual CR authoring |

Each `cr-log.md` entry records, per run: requirements updated, plans replanned, whether
arch-gen was triggered, and — the audit trail for the approval gate — `Applied targets`
(requirement IDs actually dispatched to `cr-applier` this run) and `Excluded targets`
(confirmed targets the human declined this run). `targets:` on the CR frontmatter is the
durable full impact set; `applied_targets`/`excluded_targets` are per-run, since a later run
may apply a target excluded earlier.
