# Changelog

All notable changes to implr are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
