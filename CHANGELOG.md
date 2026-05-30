# Changelog

All notable changes to implr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [2.0.0] — 2026-05-30

Major release: orchestrator + dedicated subagent execution model. Typical end-to-end
pipeline runs cost **3–4× fewer tokens** than v1.x with no measurable quality loss on the
default model assignments.

### Breaking changes
- **Removed `/ba-requirements-gen --ingest`.** Run `/doc-ingest --digest` first, then
  `/ba-requirements-gen`. Passing `--ingest` now emits a clear error pointing to the
  replacement command.
- **Removed `/ba-requirements-gen --ingest-file <path>`.** Run
  `/doc-ingest --file <path> --digest` first, then `/ba-requirements-gen`. Same error
  handling.
- **Flipped `/doc-ingest` default.** `/doc-ingest` now performs a fast registry-only scan;
  the full pipeline (per-doc digests + per-domain syntheses + master synthesis) requires
  `/doc-ingest --digest`.
- **Removed `/doc-ingest --no-digest`.** The flag is now redundant with the new default.

### Added
- **`.claude/agents/`** ships with ten dedicated subagent definitions:
  `doc-ingest-extractor` (haiku), `doc-ingest-digester` (sonnet),
  `doc-ingest-synthesizer` (sonnet), `arch-drafter` (sonnet),
  `requirements-domain-worker` (sonnet), `cr-impact-analyzer` (sonnet),
  `cr-applier` (sonnet), `plan-worker` (sonnet), `executor-worker` (**opus** —
  TDD + SOLID need a strong model), `code-review-worker` (sonnet). The installer copies
  them alongside `.claude/skills/`.
- **`skills/<skill>/phases/`** per-skill phase prompt files used as dispatch payloads
  (`extract`, `digest`, `synthesize-domain`, `draft`, `domain`, `impact`, `apply`,
  `plan-one`, `execute-plan`, `review-plan`).
- **`agents:` section in `implr.config.yaml`** — per-agent model override.
  Values: `haiku`, `sonnet`, `opus`. Omit a line to use the agent's built-in default.
  Resolution: config value wins; falls back to `default_model` in the agent file.
- **README §"How You Interact With implr"** — interaction-mode table per skill + the three
  human gates.
- **README §"Status Flows"** — short ASCII state diagrams + transition tables for
  requirements, plans, and CRs, pointing to WORKFLOW.md for full detail.
- **README §"Customising Model Tiers"** — when and how to override agent models.
- **README §"Performance & Token Efficiency"** — explains the orchestrator + subagent
  architecture and where the savings come from.
- **README §"Migrating from v1.x to v2.0"** — six-step migration checklist.
- **WORKFLOW.md §"Subagent Dispatch Model (v2.0)"** — per-phase dispatch table, model
  override mechanism, dispatch payload contract, stable-reads-first convention, savings
  rationale.
- **CONTRIBUTING.md** — sections on authoring a dedicated agent, prompt-cache-friendly
  ordering, and phase prompt file conventions.

### Changed
- All eight skills rewritten as **orchestrators** that dispatch heavy phases to dedicated
  subagents. Same external command surface (minus removed flags), same outputs.
- **`doc-ingest`** — Phase 3 (extract), Phase 4 (digest), Phase 5 (domain synthesis) all
  run as parallel subagent dispatches (cap 5 per wave). Master synthesis stays in skill.
- **`ba-requirements-gen`** — Phase 3 dispatches `requirements-domain-worker` in parallel
  per domain. Workers write to a staging area with slug-only filenames; the orchestrator
  performs **post-hoc sequential ID assignment** in Phase 5 to avoid coordination overhead.
- **`ba-cr`** — Phase 2 dispatches `cr-impact-analyzer` (read-only); Phase 4 dispatches
  `cr-applier` in parallel per affected requirement or plan.
- **`dev-planner`** — Phase 5 dispatches `plan-worker` per requirement in dependency
  waves. Phase 6 uses the built-in `Explore` subagent for cross-requirement coherence.
- **`dev-executor`** — Phase 4 dispatches `executor-worker` per plan in waves (Opus by
  default; tasks stay sequential inside the subagent).
- **`dev-code-review`** — Phase 2 dispatches `code-review-worker` per plan in parallel.
- **Installer scripts** (`install.sh`, `install.ps1`, `install.bat`) — copy
  `.claude/agents/` alongside `.claude/skills/`, with source-existence guards and (in
  `install.bat`) explicit errorlevel check so a failed copy no longer reports success.
- **`implr-init`** — seed `implr.config.yaml` now includes the v2.0 `agents:` block
  (commented, showing defaults).

### Migration
- Re-run the installer from your project root. See
  [Migrating from v1.x to v2.0](README.md#migrating-from-v1x-to-v20) in README.
- Removed flags emit clear error messages pointing to the replacement command. No silent
  breakage.

---

## [1.2.0] — 2026-05-30

### Added
- **ba-cr skill:** manage Change Requests to amend requirements and plans after generation.
  Supports three paths: CLI interview (`/ba-cr`), manual-file (`/ba-cr --file <path>`),
  and KB-document (`/ba-cr --ingest-file <path>` — ingests a new KB doc, auto-generates
  a CR from its digest, and runs the full impact and cascade flow).
  Chains doc-ingest, ba-requirements-gen --reprocess, dev-planner --replan, and optionally
  arch-gen --update. Per-requirement approval gate before any changes are applied.
- **cr-schema.md:** canonical structure for CR files, cr-index.md, and cr-log.md
- **cr-template.md:** blank template for manual change request authoring
- **implr-init:** scaffolds `docs/kb/change-requests/`, cr-schema, cr-template, cr-index
- **doc-ingest:** detects new CR files in `docs/kb/change-requests/` and prompts to run
  `/ba-cr --file`; emits a hint to run `/ba-cr --ingest-file` when new regular KB docs are
  ingested and requirements already exist
- **ba-requirements-gen:** documented CR file behaviour for `--reprocess` flag — adds CR
  to requirement `source_docs` for full traceability
- **WORKFLOW.md:** full state flow tables for requirements, plans, and CRs; "Change
  Requests" section with all three trigger paths (CLI, manual-file, KB-document)
- **README.md:** ba-cr in skills table; "Changing Requirements" section with all three paths

## [1.1.0] — 2026-05-29

### Added
- **implr-init:** interactive setup now collects 12 questions upfront (project name, stack,
  src/tests folders, TDD threshold, language, framework, ORM/DB, test runner, API versioning,
  git branch convention, optional Jira config) and applies all substitutions in a single pass
  to `implr.config.yaml`, `DEV-STANDARDS.md`, and `CLAUDE.md`. Report lists remaining
  `[FILL IN]` sections so users know exactly what still needs manual editing.
- **ba-requirements-gen:** explicit rules for when synthesis is sufficient vs. when to
  deep-dive into `cache/{slug}.txt`. Five inference-reasoning patterns for deriving unstated
  requirements from user journeys, entity lifecycles, integration mentions, and NFR signals.
- **ba-requirements-gen:** post-implementation update detection — when a new document changes
  an existing approved requirement, status drops to `under-review`, a warning is appended to
  `requirements-log.md`, and the PHASE 7 report surfaces a "Post-implementation updates"
  section.
- **dev-planner:** explicit open-question edge-case handling: contradiction resolution,
  gap → `status: blocked`, coherence-failure halt, batching by requirement, and `--all` with
  mixed clean/pending requirements.
- **dev-planner:** plans generated for `under-review` requirements receive a visible warning
  block citing the update date and change summary; human decides whether to re-plan.
- **WORKFLOW.md:** "Why the text cache exists" subsection explaining the extract-once pattern.
- **WORKFLOW.md:** "When a New Document Changes an Existing Requirement" section with the
  full 6-step invocation flow.
- **WORKFLOW.md:** "Log Files vs Index Files" section clarifying the distinct roles of
  `requirements-index.md` (current state) and `requirements-log.md` (append-only history).

### Changed
- **implr-init:** rewritten as a pure executor — no narration, no deep-reading of asset files,
  strict step checklist. Asset files are treated as opaque substitution targets.
- **ba-requirements-gen:** default behaviour is now no-ingest. Ingest must be requested
  explicitly via `--ingest` (full KB) or `--ingest-file <path>` (single file). The `--no-ingest`
  flag is removed.
- **dev-planner:** `--all` now explicitly skips any requirement that already has a plan with
  `status: ready`, `in-progress`, or `done`. Only `status: blocked` allows regeneration.
  Emits a clear skip message with a `--replan` hint.

### Fixed
- **doc-ingest:** `digest-log.md` is created with a header on first write if absent, rather
  than failing or producing an inconsistent state.
- **ba-requirements-gen:** `requirements-log.md` is created with a header on first write if
  absent.

### Removed
- `auto_chain_doc_ingest` config key removed from `implr.config.yaml` template and README
  example. Ingest chaining is now controlled entirely by CLI flags on `ba-requirements-gen`.

---

## [1.0.0] — initial release

### Added
- Seven skills: implr-init, doc-ingest, arch-gen, ba-requirements-gen, dev-planner,
  dev-executor, dev-code-review.
- Incremental knowledge-base ingestion with per-doc digests, per-domain syntheses, and a
  master synthesis. Supports md, pdf, docx, xlsx, csv, txt.
- Contradiction detection at domain and master-synthesis level.
- Architecture generation from the knowledge base with inferred-decision confirmation and
  diff-on-update.
- Functional and non-functional requirement generation with acceptance criteria, dependencies,
  complexity, TDD flags, and a Jira data block.
- Implementation planning with cross-requirement coherence checks, SOLID at design level,
  NFR injection, and an optional --brainstorm design-exploration mode.
- Plan execution with TDD enforcement for M/L/XL tasks and SOLID in code.
- Fresh-context code review with severity-graded findings and merge-blocking verdicts.
- Canonical schemas for requirements, plans, reviews, the KB index, and Jira mapping.
- Cross-platform installers: install.sh, install.ps1, install.bat.
- Forward Jira integration contract (jira-schema.md) for a future ba-jira-populate skill.
