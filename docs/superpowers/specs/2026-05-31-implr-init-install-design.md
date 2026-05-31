# implr-init: Move Workspace Scaffolding to Installer — Design (2026-05-31)

## Overview

`/implr-init` currently uses the LLM to create directories, copy files, and apply config
substitutions. The file operations are slow and add no value — they are mechanical work the
installer can do faster and more reliably. This spec moves all file operations into the install
scripts and reduces `/implr-init` to a pure config configurator: ask questions, substitute
placeholders, create the two source subfolders.

---

## Goals and Non-Goals

**Goals**
- Move directory creation and file copying entirely into `install.sh`, `install.ps1`, `install.bat`.
- Reduce `/implr-init` to 8 questions + in-place substitutions + two subfolder creates.
- Simplify the question set: remove language/framework/test-runner/git-prefix/Jira questions; split
  stack into three focused defaults (frontend, backend, db+orm).
- Preserve full idempotency: re-running the installer is safe; re-running `/implr-init` re-asks
  all questions and re-applies substitutions.

**Non-Goals**
- No changes to any other skill (doc-ingest, arch-gen, ba-requirements-gen, etc.).
- No changes to schemas, agents, or `docs/WORKFLOW.md`.
- No changes to the `--global` install flag behavior (workspace scaffolding is always local).

---

## Repo Structure Change

### New `scaffold/` directory

All assets currently at `skills/implr-init/assets/` move to a new top-level `scaffold/`
directory. `skills/implr-init/assets/` is deleted.

```
scaffold/
  config/
    implr.config.yaml        REPLACE_ME placeholders for project name, stack_hint, paths, jira
    DEV-STANDARDS.md         Updated §1: frontend / backend / db+orm placeholders (test runner row removed)
  schemas/
    kb-index-schema.md
    requirement-schema.md
    plan-schema.md
    review-schema.md
    jira-schema.md
    cr-schema.md
  templates/
    ARCHITECTURE-template.md
    CLAUDE-template.md       REPLACE_ME for project name
    requirement-template.md
    plan-template.md
    review-template.md
    cr-template.md
  seeds/
    cr-index.md              Static empty table header; seeded to docs/implr/requirements/cr-index.md
```

`skills/implr-init/` retains only `SKILL.md`. No `assets/` subtree.

---

## Install Script Changes

All three scripts (`install.sh`, `install.ps1`, `install.bat`) gain a `scaffold_workspace`
function that runs after the existing skill/agent copy. The `--global` flag does not affect
scaffolding — it always targets the current working directory.

### Directory creation (idempotent — no error if already exists)

```
docs/kb/
docs/kb/change-requests/
docs/implr/config/
docs/implr/schemas/
docs/implr/templates/
docs/implr/kb-index/cache/
docs/implr/kb-index/digests/per-doc/
docs/implr/kb-index/domains/
docs/implr/requirements/functional/
docs/implr/requirements/non-functional/
docs/implr/plans/functional/
docs/implr/plans/non-functional/
docs/implr/reviews/
```

### File copy rules

| Source (relative to implr repo) | Destination (relative to target project) | Rule |
|---------------------------------|------------------------------------------|------|
| `scaffold/schemas/*` | `docs/implr/schemas/` | Always overwrite (plugin-owned) |
| `scaffold/templates/*` | `docs/implr/templates/` | Always overwrite (plugin-owned) |
| `scaffold/templates/CLAUDE-template.md` | `CLAUDE.md` | Skip if already exists |
| `scaffold/config/implr.config.yaml` | `docs/implr/config/implr.config.yaml` | Skip if already exists |
| `scaffold/config/DEV-STANDARDS.md` | `docs/implr/config/DEV-STANDARDS.md` | Skip if already exists |
| `scaffold/seeds/cr-index.md` | `docs/implr/requirements/cr-index.md` | Skip if already exists |

### Output message change

Old:
```
Next step: Open your project in Claude Code and run: /implr-init
```

New:
```
Workspace scaffolded. Open your project in Claude Code and run /implr-init
to configure your project name, stack, and standards.
```

---

## `/implr-init` Skill Rewrite

### Pre-flight

If `docs/implr/config/implr.config.yaml` does not exist, halt:

```
Workspace not found. Run the installer first (install.sh / install.ps1 / install.bat),
then re-run /implr-init.
```

### Question phase

Ask all 8 questions one at a time, in order, before any file operations. On re-init (config
files already have values), still ask all questions — answers re-apply substitutions so users
can update their stack or conventions.

| # | Question | Default |
|---|----------|---------|
| 1 | Project name? | _(required)_ |
| 2a | Frontend technology? | `React` |
| 2b | Backend technology? | `Python` |
| 2c | Database + ORM? | `PostgreSQL 16, SQLAlchemy 2.0` |
| 3 | Source folder? | `src` |
| 4 | Tests folder? | `tests` |
| 5 | TDD threshold — M / L / XL? | `M` |
| 6 | API versioning strategy? | `/api/v1` |

### Source folder subfolder creation

After collecting answer 3, create these directories (idempotent):

```
<answer>/
<answer>/frontend/
<answer>/backend/
```

Example: user answers `dupajas` → creates `dupajas/`, `dupajas/frontend/`, `dupajas/backend/`.

These directories are not tracked in `implr.config.yaml` beyond `paths.src: <answer>`.

### Substitution phase

In-place edits on three already-present files. Apply all substitutions in a single pass per
file. Do not deep-read files — substitution targets are listed explicitly below.

On re-init the files already contain real values (not REPLACE_ME). The skill must replace
whatever the current value is at each target location, not search for a literal placeholder.

**`docs/implr/config/implr.config.yaml`**

| Placeholder | Replacement |
|-------------|-------------|
| `REPLACE_ME` under `project.name` | answer 1 |
| `"REPLACE_ME"` under `project.stack_hint` | `"<2a>, <2b>, <2c>"` (composed) |
| value under `paths.src` | answer 3 (only if not default `src`) |
| value under `paths.tests` | answer 4 (only if not default `tests`) |
| value under `behaviour.default_tdd_threshold` | answer 5 (only if not default `M`) |

**`docs/implr/config/DEV-STANDARDS.md`**

| Placeholder | Replacement |
|-------------|-------------|
| `REPLACE_ME_FRONTEND` in §1 | answer 2a |
| `REPLACE_ME_BACKEND` in §1 | answer 2b |
| `REPLACE_ME_DB` in §1 | answer 2c |
| `REPLACE_ME_VERSIONING` in §7 | answer 6 |

**`CLAUDE.md`** (project root)

| Placeholder | Replacement |
|-------------|-------------|
| `REPLACE_ME` | answer 1 (project name) |

### Report

```
✅ implr configured
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  CLAUDE.md

Created:
  <src>/frontend/
  <src>/backend/

Remaining [FILL IN] sections in DEV-STANDARDS.md (open in your editor):
  §2 Folder Structure
  §3 Naming Conventions
  §4 Architecture Patterns (DI, Error Handling, Validation)
  §9 Logging and Observability
  §11 Environment Configuration

Next steps:
  1. Complete the remaining [FILL IN] sections of docs/implr/config/DEV-STANDARDS.md
  2. Add your documentation to docs/kb/
  3. Run /doc-ingest to index and digest your knowledge base
  4. Run /arch-gen to generate docs/ARCHITECTURE.md
  5. Run /ba-requirements-gen to generate requirements
```

---

## Idempotency Rules

### Installer (re-running install script)

| Target | Rule |
|--------|------|
| `.claude/skills/**` | Always overwrite |
| `.claude/agents/**` | Always overwrite |
| `docs/implr/schemas/**` | Always overwrite (plugin-owned) |
| `docs/implr/templates/**` | Always overwrite (plugin-owned) |
| `docs/implr/config/implr.config.yaml` | Skip if exists |
| `docs/implr/config/DEV-STANDARDS.md` | Skip if exists |
| `CLAUDE.md` | Skip if exists |
| `docs/implr/requirements/cr-index.md` | Skip if exists |
| All directories | Create if not exists; no-op otherwise |

### `/implr-init` (re-running the skill)

Re-asks all questions and re-applies substitutions — even to files that already have values.
Never deletes anything. Never touches `docs/kb/`, `src/`, or `tests/`.

---

## Complete File Change List

| File | Action |
|------|--------|
| `scaffold/` (new dir) | Create; move all files from `skills/implr-init/assets/`; add `seeds/cr-index.md` |
| `scaffold/config/DEV-STANDARDS.md` | Update §1: replace language/framework/ORM/test-runner fields with `REPLACE_ME_FRONTEND`, `REPLACE_ME_BACKEND`, `REPLACE_ME_DB`; update §7 versioning placeholder to `REPLACE_ME_VERSIONING` |
| `skills/implr-init/assets/` | Delete entirely |
| `skills/implr-init/SKILL.md` | Rewrite: pre-flight, 8 questions, source subfolders, in-place substitutions, report |
| `install.sh` | Add `scaffold_workspace` function |
| `install.ps1` | Add `Scaffold-Workspace` function |
| `install.bat` | Add `:scaffold_workspace` section |
| `README.md` | Update "What the installer creates", "Quick Start Step 2", and `implr-init` skill reference |
