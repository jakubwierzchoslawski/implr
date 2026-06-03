---
name: implr-init
description: >
  Configures the implr workspace after the installer has scaffolded docs/implr/. Asks 8
  setup questions (project name, frontend/backend/db stack, paths, TDD threshold, API
  versioning), substitutes placeholders in implr.config.yaml, DEV-STANDARDS.md, and
  CLAUDE.md, creates <src>/frontend/ and <src>/backend/ subdirectories, and generates
  docs/implr/config/standards-card.md and docs/implr/config/requirements-card.md.
  Idempotent: re-running re-asks all questions and re-applies substitutions.
  Supports --refresh-card to regenerate standards-card.md and requirements-card.md.
---

# implr-init Skill

You configure the implr workspace: collect project details and substitute placeholders in
three config files. The installer already created all directories and copied all files —
your only job is questions, substitutions, and two source subdirectory creates.

---

## Parameters

| Invocation | Behaviour |
|------------|-----------|
| `/implr-init` | Full setup: ask 8 questions, apply substitutions, create source subdirectories, generate `docs/implr/config/standards-card.md` and `docs/implr/config/requirements-card.md` |
| `/implr-init --refresh-card` | Regenerate `docs/implr/config/standards-card.md` AND `docs/implr/config/requirements-card.md` from current `docs/implr/config/DEV-STANDARDS.md` and `docs/implr/config/implr.config.yaml` — no questions re-asked |

---

## Refresh-card-only mode

When invoked with `--refresh-card`:

1. Read `docs/implr/config/DEV-STANDARDS.md` and extract the following values:
   - **FRONTEND** — the value on the line starting with `Frontend:` inside the §1 Project Stack block
   - **BACKEND** — the value on the line starting with `Backend:` inside the §1 Project Stack block
   - **DB** — the value on the line starting with `Database + ORM:` inside the §1 Project Stack block
   - **VERSIONING** — the value on the line starting with `Versioning:` inside the §7 block

2. Additionally read `docs/implr/config/implr.config.yaml` and extract
   `behaviour.default_tdd_threshold` (treat the literal token after the colon, stripping
   inline comments and whitespace).

3. Run Step 4 (generate `docs/implr/config/standards-card.md`) and Step 5 (generate
   `docs/implr/config/requirements-card.md`) using these extracted values. Skip Step 1
   (no questions) and Step 2 (no source subdirectories).

4. Print:
   ```
   ✅ standards-card.md and requirements-card.md regenerated
   ```

5. Stop. Do not proceed to any other step.

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

## Step 4 — Generate standards-card

1. Read `docs/implr/templates/standards-card-template.md`.

2. Substitute placeholders:

   | Placeholder | Value |
   |-------------|-------|
   | `{{FRONTEND}}` | answer 2a (or FRONTEND extracted in refresh-card mode) |
   | `{{BACKEND}}` | answer 2b (or BACKEND extracted in refresh-card mode) |
   | `{{DB}}` | answer 2c (or DB extracted in refresh-card mode) |
   | `{{VERSIONING}}` | answer 6 (or VERSIONING extracted in refresh-card mode) |

3. Write the result to `docs/implr/config/standards-card.md`. ALWAYS overwrite — this file
   is auto-managed and must never be hand-edited.

---

## Step 5 — Generate requirements-card

1. Read `docs/implr/templates/requirements-card-template.md`.

2. Substitute placeholders:

   | Placeholder | Value |
   |-------------|-------|
   | `{{TDD_THRESHOLD}}` | answer 5 (or `default_tdd_threshold` extracted in refresh-card mode) |

3. Write the result to `docs/implr/config/requirements-card.md`. ALWAYS overwrite — this
   file is auto-managed and must never be hand-edited.

---

## Step 6 — Report

```
✅ implr configured
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  CLAUDE.md
  docs/implr/config/standards-card.md       (auto-generated; do not hand-edit)
  docs/implr/config/requirements-card.md    (auto-generated; do not hand-edit)

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
