---
name: implr-init
description: >
  Configures the implr workspace after the installer has scaffolded docs/implr/. Asks 8
  setup questions (project name, frontend/backend/db stack, paths, TDD threshold, API
  versioning), substitutes placeholders in implr.config.yaml, DEV-STANDARDS.md, and
  CLAUDE.md, and creates <src>/frontend/ and <src>/backend/ subdirectories. Idempotent:
  re-running re-asks all questions and re-applies substitutions.
---

# implr-init Skill

You configure the implr workspace: collect project details and substitute placeholders in
three config files. The installer already created all directories and copied all files —
your only job is questions, substitutions, and two source subdirectory creates.

---

## Pre-flight

Check whether `docs/implr/config/implr.config.yaml` exists. If it does not, halt with:

```
Workspace not found. Run the installer first (install.sh / install.ps1 / install.bat),
then re-run /implr-init.
```

---

## Step 1 — Collect answers (one question at a time)

Ask all questions in order. Collect all answers before any file operation.
Accept the stated default silently if the user presses enter with no input.

| # | Question | Default |
|---|----------|---------|
| 1 | Project name? | _(required — no default)_ |
| 2a | Frontend technology? | `React` |
| 2b | Backend technology? | `Python` |
| 2c | Database + ORM? | `PostgreSQL 16, SQLAlchemy 2.0` |
| 3 | Source folder? | `src` |
| 4 | Tests folder? | `tests` |
| 5 | Default TDD threshold — M / L / XL? | `M` |
| 6 | API versioning strategy? | `/api/v1` |

On re-init (config files already contain real values, not REPLACE_ME), still ask all
questions. The substitution step replaces whatever current value is at each location.

---

## Step 2 — Create source subdirectories

Create these directories (idempotent — no error if they already exist):

```
<answer 3>/
<answer 3>/frontend/
<answer 3>/backend/
```

Example: user answers `dupajas` → create `dupajas/`, `dupajas/frontend/`, `dupajas/backend/`.

---

## Step 3 — Apply substitutions

Edit three files in-place. Apply all substitutions for each file in a single pass.
On re-init, replace whatever current value is at each target location — not just
REPLACE_ME literals. Asset files are opaque: do not deep-read them to reason about content.

### `docs/implr/config/implr.config.yaml`

| Field path | Replace current value with |
|------------|---------------------------|
| `project.name` value | answer 1 |
| `project.stack_hint` value | `"<answer 2a>, <answer 2b>, <answer 2c>"` |
| `paths.src` value | answer 3 (skip if answer equals default `src`) |
| `paths.tests` value | answer 4 (skip if answer equals default `tests`) |
| `behaviour.default_tdd_threshold` value | answer 5 (skip if answer equals default `M`) |

### `docs/implr/config/DEV-STANDARDS.md`

| Location | Replace current value with |
|----------|---------------------------|
| `REPLACE_ME_FRONTEND` in §1 | answer 2a |
| `REPLACE_ME_BACKEND` in §1 | answer 2b |
| `REPLACE_ME_DB` in §1 | answer 2c |
| `REPLACE_ME_VERSIONING` in §7 | answer 6 |

### `CLAUDE.md` (project root)

| Location | Replace current value with |
|----------|---------------------------|
| `REPLACE_ME` | answer 1 (project name) |

---

## Step 4 — Report

```
✅ implr configured
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  CLAUDE.md

Created:
  <answer 3>/frontend/
  <answer 3>/backend/

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
