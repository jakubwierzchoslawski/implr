---
name: implr-init
description: >
  Scaffolds the implr plugin workspace in a project. Use this skill when the user wants to
  initialise implr, set up the plugin, create the implr folder structure, or start using implr
  in a new project. Triggers on: implr init, initialise implr, set up implr, scaffold implr,
  create implr structure, start implr. Creates docs/kb/, docs/implr/ (config, schemas,
  templates, kb-index, requirements, plans, reviews), a pre-populated DEV-STANDARDS.md, the
  implr.config.yaml, and CLAUDE.md. Idempotent — never overwrites existing files. Run once per
  project before any other implr skill.
---

# implr-init Skill

You scaffold the implr plugin workspace. You create the folder structure and seed configuration,
schemas, and templates so the rest of the implr pipeline can operate. You are careful and
idempotent: you never overwrite a file that already exists, and you report clearly what you
created versus what was already present.

This skill carries its own asset files under the skill's `assets/` directory. You copy from
there into the project's `docs/implr/` workspace.

---

## Asset Source

This skill's bundled assets (relative to this SKILL.md):

```
assets/
  config/
    implr.config.yaml
    DEV-STANDARDS.md
  schemas/
    kb-index-schema.md
    requirement-schema.md
    plan-schema.md
    review-schema.md
    jira-schema.md
    cr-schema.md
  templates/
    ARCHITECTURE-template.md
    CLAUDE-template.md
    requirement-template.md
    plan-template.md
    review-template.md
    cr-template.md
```

Locate the skill directory, then read assets from there. Do not hardcode an absolute path —
resolve relative to where this skill is installed.

---

## Execution

You are a pure executor. You ask questions, collect answers, substitute values, create
directories, copy files, report. You do not narrate, reason aloud, or deep-read asset files.
Asset files are opaque substitution targets — you know which placeholder strings to replace
and you apply them in one pass.

---

### Step 0 — Collect answers (one question at a time)

Before any file operation, ask the user these questions one at a time in this order. Accept
the default silently if the user presses enter with no input on questions that have one.

| # | Question | Default | Target |
|---|----------|---------|--------|
| 1 | Project name? | _(required)_ | `implr.config.yaml` `project.name` + `CLAUDE.md` |
| 2 | Tech stack? (e.g. "Python, FastAPI, PostgreSQL") | _(required)_ | `implr.config.yaml` `project.stack_hint` |
| 3 | Source folder? | `src` | `implr.config.yaml` `paths.src` |
| 4 | Tests folder? | `tests` | `implr.config.yaml` `paths.tests` |
| 5 | Default TDD threshold — M / L / XL? | `M` | `implr.config.yaml` `behaviour.default_tdd_threshold` |
| 6 | Language + version? (e.g. "Python 3.12") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
| 7 | Framework? (e.g. "FastAPI 0.111") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
| 8 | ORM + DB? (e.g. "SQLAlchemy 2, PostgreSQL 16") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
| 9 | Test runner? (e.g. "pytest") | _(required)_ | `DEV-STANDARDS.md` §1 Project Stack |
| 10 | API versioning strategy? (e.g. "URL prefix /api/v1") | _(required)_ | `DEV-STANDARDS.md` §7 API Design |
| 11 | Git branch prefix convention? (e.g. "feat/", "feature/") | `feat/` | `DEV-STANDARDS.md` §10 Git Conventions |
| 12 | Use Jira? (y/n) | `n` | — |
| 13 | _(only if Q12 = y)_ Jira base URL? | — | `implr.config.yaml` `jira.base_url` |
| 14 | _(only if Q12 = y)_ Jira project key? | — | `implr.config.yaml` `jira.project_key` |

On **re-init** (`docs/implr/` already exists): skip this step entirely — config files are
never overwritten, so questions have no target to write to.

---

### Step 1 — Detect project root and pre-flight

Confirm the working directory is the intended project root. If `docs/implr/` already exists,
this is a re-init — proceed in idempotent mode (fill gaps only) and tell the user.

---

### Step 2 — Create folder structure

Create these directories (no error if they already exist):

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

---

### Step 3 — Copy schemas and templates (plugin-owned — overwrite on re-init)

Copy every file from `assets/schemas/` into `docs/implr/schemas/`.
Copy every file from `assets/templates/` into `docs/implr/templates/`.
Overwrite on re-init — these are plugin-owned; user customisation lives in DEV-STANDARDS.md
and implr.config.yaml.

After copying schemas and templates, initialise these empty index files if they do not
already exist (never overwrite):
- `docs/implr/requirements/cr-index.md` — copy the cr-index.md structure from
  `docs/implr/schemas/cr-schema.md` § cr-index.md (the empty table header only)

---

### Step 4 — Write substituted config files (first init only — never overwrite)

For each file below: if it does not already exist at the target path, read it from assets,
apply the substitutions listed, and write it to the target. If it already exists, skip it
and add it to the "Already present" list in the report.

**`docs/implr/config/implr.config.yaml`** ← from `assets/config/implr.config.yaml`

Substitutions (apply all in one pass):
- `REPLACE_ME` under `project.name` → answer 1
- `"REPLACE_ME"` under `project.stack_hint` → `"{answer 2}"`
- value under `paths.src` → answer 3 (skip if default `src`)
- value under `paths.tests` → answer 4 (skip if default `tests`)
- value under `behaviour.default_tdd_threshold` → answer 5 (skip if default `M`)
- `REPLACE_ME` under `jira.project_key` → answer 14 if Jira enabled, else leave as-is
- `https://your-org.atlassian.net` under `jira.base_url` → answer 13 if Jira enabled, else leave as-is

**`docs/implr/config/DEV-STANDARDS.md`** ← from `assets/config/DEV-STANDARDS.md`

Substitutions (apply all in one pass):
- `e.g. TypeScript 5.x` (Language line in §1) → answer 6
- `e.g. NestJS 10 / Express 4 / Fastify 4` (Framework line in §1) → answer 7
- `e.g. Prisma 5, PostgreSQL 16` (ORM/DB line in §1) → answer 8
- `e.g. Vitest / Jest` (Test runner line in §1) → answer 9
- `[FILL IN] e.g. URL prefix /api/v1 or header API-Version` (Versioning line in §7) → answer 10
- `feat/REQ-F-001-slug, fix/REQ-F-001-slug, chore/description` (Branch line in §10) → `{answer 11}REQ-F-001-slug` (adjust example to use provided prefix)

All other `[FILL IN]` markers in DEV-STANDARDS.md are left for the user — they require
project-specific knowledge that cannot be collected at init time.

**`CLAUDE.md`** ← from `assets/templates/CLAUDE-template.md`

Substitutions:
- `REPLACE_ME` → answer 1 (project name)

---

### Step 5 — Report

```
✅ implr initialised
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Created:
  📁 docs/kb/                         (your knowledge base — add docs here)
  📁 docs/implr/                      (plugin workspace)
  📄 docs/implr/config/implr.config.yaml
  📄 docs/implr/config/DEV-STANDARDS.md
  📄 docs/implr/schemas/              (6 schema files)
  📄 docs/implr/templates/            (6 templates)
  📁 docs/kb/change-requests/         (drop CR files here for manual change requests)
  📄 CLAUDE.md

Already present (left untouched):
  {list any skipped files}

Remaining [FILL IN] sections in DEV-STANDARDS.md (open in your editor):
  §2 Folder Structure
  §3 Naming Conventions
  §4 Architecture Patterns (DI, Error Handling, Validation)
  §9 Logging and Observability
  §11 Environment Configuration

Next steps:
  1. Complete the remaining [FILL IN] sections of docs/implr/config/DEV-STANDARDS.md
  2. Add your documentation (.md, .pdf, .docx, .xlsx, .csv, .txt) to docs/kb/
  3. Run /doc-ingest to index and digest your knowledge base
  4. Run /arch-gen to generate docs/ARCHITECTURE.md
  5. Run /ba-requirements-gen to generate requirements
```

---

## Idempotency Rules

| File / folder | First init | Re-init |
|---------------|-----------|---------|
| Folders | create | leave (no error) |
| schemas/* | copy | overwrite (plugin-owned) |
| templates/* | copy | overwrite (plugin-owned) |
| implr.config.yaml | copy + substitute | leave untouched |
| DEV-STANDARDS.md | copy + substitute | leave untouched |
| CLAUDE.md | copy + substitute | leave untouched |

Never delete anything. Never touch `docs/kb/` contents. Never touch `src/` or `tests/`.
