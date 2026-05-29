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
  templates/
    ARCHITECTURE-template.md
    CLAUDE-template.md
    requirement-template.md
    plan-template.md
    review-template.md
```

Locate the skill directory, then read assets from there. Do not hardcode an absolute path —
resolve relative to where this skill is installed.

---

## Execution

### Step 1 — Detect project root and pre-flight

Confirm the current working directory is the project root (where the user wants implr).
If a `docs/implr/` already exists, this is a re-init — proceed in idempotent mode (fill gaps
only) and tell the user.

### Step 2 — Create folder structure

Create these directories (no error if they already exist):

```
docs/kb/
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

### Step 3 — Copy schemas (always safe — these are plugin-owned)

Copy every file from `assets/schemas/` into `docs/implr/schemas/`.
Schemas are plugin-owned reference files. On re-init, overwrite them so they stay current with
the installed plugin version. (They are not user-edited; user customisation goes in
DEV-STANDARDS.md and implr.config.yaml.)

### Step 4 — Copy templates (always safe — plugin-owned)

Copy every file from `assets/templates/` into `docs/implr/templates/`.
Overwrite on re-init for the same reason as schemas.

### Step 5 — Seed config (never overwrite)

**implr.config.yaml**: if `docs/implr/config/implr.config.yaml` does not exist, copy it from
`assets/config/implr.config.yaml`. Then interactively ask the user for:
- Project name → replace `REPLACE_ME` under `project.name`
- Stack hint → replace `REPLACE_ME` under `project.stack_hint`
- Jira project key (optional, can skip) → replace `REPLACE_ME` under `jira.project_key`

If it already exists, leave it untouched and report that.

**DEV-STANDARDS.md**: if `docs/implr/config/DEV-STANDARDS.md` does not exist, copy it from
`assets/config/DEV-STANDARDS.md`. This file is user-owned once created — never overwrite it on
re-init.

### Step 6 — Seed CLAUDE.md (never overwrite)

If `CLAUDE.md` does not exist at the project root, copy it from
`assets/templates/CLAUDE-template.md`, then replace `REPLACE_ME` with the project name.
If it exists, leave it and suggest the user add an implr section manually (point them to the
template).

### Step 7 — Report

```
✅ implr initialised
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Created:
  📁 docs/kb/                         (your knowledge base — add docs here)
  📁 docs/implr/                      (plugin workspace)
  📄 docs/implr/config/implr.config.yaml
  📄 docs/implr/config/DEV-STANDARDS.md
  📄 docs/implr/schemas/              (5 schema files)
  📄 docs/implr/templates/            (5 templates)
  📄 CLAUDE.md

Already present (left untouched):
  {list any skipped files}

Next steps:
  1. Fill in [FILL IN] sections of docs/implr/config/DEV-STANDARDS.md
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
| implr.config.yaml | copy + prompt | leave untouched |
| DEV-STANDARDS.md | copy | leave untouched (user-owned) |
| CLAUDE.md | copy + fill name | leave untouched |

Never delete anything. Never touch `docs/kb/` contents. Never touch `src/` or `tests/`.
