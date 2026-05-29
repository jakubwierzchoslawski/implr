# Changelog

All notable changes to implr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — 2026-05-29

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
