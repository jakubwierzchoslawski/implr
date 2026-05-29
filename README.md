# implr

**Automate your SDLC from documentation to reviewed code — inside [Claude Code](https://claude.ai/code).**

implr is a plugin of eight skills that take a project from a folder of business and technical
documentation, through requirements, architecture, planning, and implementation, to a
fresh-context code review — each stage structured, traceable, and incremental.

```
docs/kb/  →  doc-ingest  →  arch-gen  →  ba-requirements-gen
                                              │
                                       (human approves)
                                              │
                          dev-planner  →  dev-executor  →  dev-code-review  →  reviewed code
```

---

## Table of Contents

- [Why implr](#why-implr)
- [The Skills](#the-skills)
- [Installation](#installation)
- [Updating implr](#updating-implr)
- [Required Folder Structure](#required-folder-structure)
- [Quick Start](#quick-start)
- [The Full Pipeline](#the-full-pipeline)
- [Skills Reference](#skills-reference)
- [Changing Requirements](#changing-requirements)
- [Knowledge Base Guide](#knowledge-base-guide)
- [Configuration](#configuration)
- [Schemas](#schemas)
- [Auto-Managed Files](#auto-managed-files)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Why implr

Most of the SDLC's early phases are structured work that is repeated on every feature: reading
documentation, distilling requirements, checking them for contradictions, planning an
implementation that respects the architecture, writing code to standards, and reviewing it.
implr encodes that structure as a set of Claude Code skills so the repetitive parts are
automated and the human stays in control of the decisions that matter — approving requirements,
resolving contradictions, and choosing between design options.

Key properties:

- **Traceable** — every requirement links to source documents; every plan to a requirement;
  every review to a plan. Nothing appears without provenance.
- **Incremental** — change one document and only the affected digests, syntheses, and
  requirements are reprocessed. The knowledge base can grow large without overwhelming context.
- **Standards-driven** — architecture and development standards are first-class inputs that the
  planning, implementation, and review skills all enforce.
- **Human-gated** — Claude generates; humans approve. Requirements only flow to planning once a
  person marks them approved.

---

## The Skills

| Skill | Role | Command |
|-------|------|---------|
| `implr-init` | Scaffolds the plugin workspace | `/implr-init` |
| `doc-ingest` | Indexes and digests the knowledge base | `/doc-ingest` |
| `arch-gen` | Generates `ARCHITECTURE.md` from the KB | `/arch-gen` |
| `ba-requirements-gen` | Generates functional and non-functional requirements | `/ba-requirements-gen` |
| `ba-cr` | Creates and applies Change Requests to amend requirements and plans | `/ba-cr` |
| `dev-planner` | Creates implementation plans (with optional brainstorming) | `/dev-planner` |
| `dev-executor` | Implements plans as production code | `/dev-executor` |
| `dev-code-review` | Reviews produced code in a fresh context | `/dev-code-review` |


A future `ba-jira-populate` skill will push approved requirements into Jira; its data contract is
already part of the requirement schema.

---

## Installation

implr installs as a set of Claude Code skills plus a project workspace. The installer does both:
copies the skills and scaffolds the workspace.

### macOS / Linux

```bash
git clone https://github.com/your-org/implr.git
cd /path/to/your-project
/path/to/implr/install.sh
```

### macOS / Windows (PowerShell)

```powershell
git clone https://github.com/your-org/implr.git
cd C:\path\to\your-project
& C:\path\to\implr\install.ps1
```

### Windows (CMD)

```bat
git clone https://github.com/your-org/implr.git
cd C:\path\to\your-project
C:\path\to\implr\install.bat
```

### Install options

| Flag | Effect |
|------|--------|
| (none) | Install skills to `./.claude/skills` and scaffold `./docs/implr` |
| `--global` / `-Global` | Install skills to `~/.claude/skills` (available in all projects) |
| `--skills-only` / `-SkillsOnly` | Install skills only; scaffold later with `/implr-init` |

The installer is **idempotent**: re-running it refreshes the plugin-owned schemas and templates
but never overwrites your `DEV-STANDARDS.md`, `implr.config.yaml`, `CLAUDE.md`, or anything in
`docs/kb/`.

> **Note on skill packaging.** Claude Code reads skills from unpacked folders (each containing a
> `SKILL.md`), not from `.skill` archives. The installer copies unpacked folders, so the skills
> appear in Claude Code immediately.

---

## Updating implr

To update from any previous version, pull the latest implr and re-run the installer from
your project root. The installer is **idempotent** — it is safe to run on an existing project.

### macOS / Linux

```bash
cd /path/to/implr
git pull
cd /path/to/your-project
/path/to/implr/install.sh
```

### macOS / Windows (PowerShell)

```powershell
cd C:\path\to\implr
git pull
cd C:\path\to\your-project
& C:\path\to\implr\install.ps1
```

### Windows (CMD)

```bat
cd C:\path\to\implr
git pull
cd C:\path\to\your-project
C:\path\to\implr\install.bat
```

### What the update does

| What | Action |
|------|--------|
| Skills (`.claude/skills/`) | Always replaced with the new version |
| Schemas (`docs/implr/schemas/`) | Always replaced — plugin-owned |
| Templates (`docs/implr/templates/`) | Always replaced — plugin-owned |
| New folders (e.g. `docs/kb/change-requests/`) | Created if missing |
| `docs/implr/config/implr.config.yaml` | **Never overwritten** — your config is preserved |
| `docs/implr/config/DEV-STANDARDS.md` | **Never overwritten** — your standards are preserved |
| `CLAUDE.md` | **Never overwritten** — your file is preserved |
| Everything in `docs/kb/` | **Never touched** — your documents are preserved |

### After updating

If the new version adds new skills, they are available immediately in Claude Code after the
installer runs — no restart needed.

If the new version adds new folders or index files (e.g. `cr-index.md` in v1.2.0), the
installer creates them. You can also run `/implr-init` inside Claude Code to pick up any
new scaffolding interactively.

---

## Required Folder Structure

After install, your project looks like this. Folders marked *(you)* are yours to manage;
everything under `docs/implr/` except config is auto-managed by the skills.

```
your-project/
├── .claude/skills/                 eight installed skills (SKILL.md each)
├── docs/
│   ├── kb/                         (you) knowledge base — any subfolder structure
│   │   └── change-requests/        (you) drop CR files here for manual change requests
│   ├── ARCHITECTURE.md             generated by arch-gen
│   └── implr/                      plugin workspace
│       ├── config/
│       │   ├── implr.config.yaml   (you) plugin configuration
│       │   └── DEV-STANDARDS.md    (you) development standards (SOLID pre-filled)
│       ├── schemas/                canonical schemas (plugin-owned)
│       ├── templates/              templates (plugin-owned)
│       ├── kb-index/               index, digests, syntheses (doc-ingest)
│       ├── requirements/           REQ-F-*, REQ-N-* (ba-requirements-gen)
│       ├── plans/                  PLAN-F-*, PLAN-N-* (dev-planner)
│       └── reviews/                REVIEW-F-* (dev-code-review)
├── src/                            (you) implementation (dev-executor writes here)
├── tests/                          (you) tests (dev-executor writes here)
└── CLAUDE.md                       project briefing for Claude Code
```

---

## Quick Start

```bash
# 1. Install (from your project root)
/path/to/implr/install.sh

# 2. Fill in your standards
#    Edit docs/implr/config/DEV-STANDARDS.md — complete the [FILL IN] sections

# 3. Add documentation to the knowledge base
cp ~/specs/*.md docs/kb/
#    organise into subfolders by domain if you like: docs/kb/auth/, docs/kb/billing/, ...
```

Then, inside Claude Code:

```
/doc-ingest                 # index + digest the KB
/arch-gen                   # generate docs/ARCHITECTURE.md (confirms inferred decisions)
/ba-requirements-gen        # generate requirements (auto-runs doc-ingest first)

# review docs/implr/requirements/requirements-index.md
# resolve open questions, set status: approved on ready requirements

/dev-planner --all          # plan all approved requirements
/dev-executor --all         # implement all ready plans in dependency order
/dev-code-review --all      # review everything that was built
```

---

## The Full Pipeline

```
1. SETUP
   /implr-init (or the installer) scaffolds docs/implr and seeds config + standards

2. DOCUMENT
   You add .md/.pdf/.docx/.xlsx/.csv/.txt files to docs/kb/

3. INGEST            /doc-ingest
   Scans the KB, computes checksums, extracts text, writes per-doc digests,
   per-domain syntheses, and a master synthesis. Detects contradictions. Incremental.

4. ARCHITECT         /arch-gen
   Reads the master synthesis + architecture-tagged docs, drafts docs/ARCHITECTURE.md,
   confirms any inferred decisions with you, and (on re-run) proposes a diff.

5. REQUIREMENTS      /ba-requirements-gen
   Reads syntheses (not every raw doc), generates REQ-F-* and REQ-N-* with acceptance
   criteria, dependencies, complexity, and TDD flags. Flags contradictions as open questions.

6. APPROVE  (human)
   Review the requirements index, resolve open questions, set status: approved.

7. PLAN              /dev-planner   (add --brainstorm to explore design options)
   Resolves remaining open questions, checks cross-requirement coherence, applies SOLID at
   the design level, injects NFR constraints, and writes PLAN-F-* with task-level TDD flags.

8. IMPLEMENT         /dev-executor
   Writes production code and tests to your src/ and tests/, enforcing TDD for M/L/XL tasks
   and SOLID in code. Respects plan dependency order. Notes manual actions it cannot perform.

9. REVIEW            /dev-code-review
   Fresh context. Verifies every acceptance criterion, checks architecture/SOLID/security,
   audits tests, and issues a verdict with findings by severity. Blocks merge on
   Critical/High findings.
```

---

## Skills Reference

### implr-init
Scaffolds `docs/implr/`, seeds `implr.config.yaml` and `DEV-STANDARDS.md`, copies schemas and
templates, creates `CLAUDE.md`. Idempotent.

```
/implr-init
```

### doc-ingest
Indexes and digests the KB.

```
- `/doc-ingest` — default incremental run (registry + digest + synthesis)
- `/doc-ingest --no-digest` — registry only: update index.md and cache, skip digests/syntheses
- `/doc-ingest --file <path>` — process a single file regardless of checksum
- `/doc-ingest --dry-run` — report what would change; write nothing
- `/doc-ingest --rebuild` — ignore all checksums; reprocess everything from scratch
```

Supported formats: `md, pdf, docx, xlsx, csv, txt` (configurable). Unsupported files are
registered but not digested.

### arch-gen
Generates `docs/ARCHITECTURE.md`.

```
- `/arch-gen` — generate (or, if ARCHITECTURE.md exists, propose a diff for confirmation)
- `/arch-gen --update` — explicitly refresh an existing ARCHITECTURE.md (diff + confirm)
- `/arch-gen --dry-run` — show what would be produced; write nothing
```

Mark KB docs as architecture-relevant by placing them under `docs/kb/architecture/`, adding
`implr_tags: [architecture]` to their frontmatter, or via a sibling `{name}.meta.yaml`. arch-gen
also auto-detects architectural content and asks you to confirm inferred decisions.

### ba-requirements-gen
Generates requirements from the KB.

```
- `/ba-requirements-gen` — use existing syntheses as-is; no ingest step
- `/ba-requirements-gen --ingest` — run full doc-ingest on the KB first, then generate
- `/ba-requirements-gen --ingest-file <path>` — ingest one specific file first, then generate
- `/ba-requirements-gen --domain <name>` — generate only for one domain
- `/ba-requirements-gen --reprocess <doc>` — re-derive requirements from a specific source doc
- `/ba-requirements-gen --dry-run` — preview; write nothing, do not advance log state
```

### ba-cr
Creates and applies Change Requests to amend requirements and plans after generation.

```
- `/ba-cr` — interactive CLI interview; creates a CR, analyses impact, chains updates on approval
- `/ba-cr --file <path>` — apply a manually-authored CR file (impact analysis + approval gate)
- `/ba-cr --ingest-file <path>` — ingest a new/updated KB document, auto-generate a CR, apply
- `/ba-cr --impact-only <path>` — run impact analysis on an existing CR; do not apply changes
- `/ba-cr --dry-run` — preview impact and downstream changes; write nothing
```

See [Changing Requirements](#changing-requirements) for the three trigger paths in detail.

### dev-planner
Creates implementation plans from approved requirements.

```
- `/dev-planner REQ-F-001` — plan a single requirement
- `/dev-planner REQ-F-001 REQ-F-002 REQ-N-001` — plan several (dependency order respected)
- `/dev-planner --all` — plan all approved requirements without a current plan
- `/dev-planner --replan REQ-F-001` — regenerate an existing plan (preserve plan_id)
- `/dev-planner --brainstorm REQ-F-001` — interactive design exploration before planning
- `/dev-planner --dry-run REQ-F-001` — preview; write nothing

```

`--brainstorm` combines with a requirement id or `--all`. `--dry-run` combines with any mode.

### dev-executor
Implements plans.

```
- `/dev-executor PLAN-F-001` — execute one plan
- `/dev-executor PLAN-F-001 PLAN-F-002` — execute several in the given order (deps validated)
- `/dev-executor --all` — execute all `ready` plans in dependency order from plans-index.md
- `/dev-executor --task PLAN-F-001 TASK-003` — execute a single task (resume work)
- `/dev-executor --dry-run PLAN-F-001` — list files that would be created/modified; write nothing
```

### dev-code-review
Reviews produced code in a fresh context.

```
- `/dev-code-review PLAN-F-001` — review one plan's output
- `/dev-code-review PLAN-F-001 PLAN-F-002` — review several (one report each)
- `/dev-code-review --all` — review all `done` plans without a current review
```

Verdicts: `approved`, `approved-with-warnings`, `changes-required`, `rejected`. Critical and
High findings block merge.

---

## Changing Requirements

After requirements and plans are generated, use `ba-cr` to change them. Three paths are available:

**CLI path** — tell ba-cr what you want to change in plain language:
```
/ba-cr
```
ba-cr interviews you, creates a Change Request document, analyses impact across all
requirements and plans, shows you what will change, and chains the downstream updates on
approval.

**Manual-file path** — author the CR file yourself, then apply it:
```
1. Copy docs/implr/templates/cr-template.md → docs/kb/change-requests/CR-NNN.md
2. Fill in the required fields
3. /doc-ingest          ← detects the new CR, prompts you to run ba-cr
4. /ba-cr --file docs/kb/change-requests/CR-NNN.md
```

**KB-document path** — added a new or updated doc to the KB that changes requirements:
```
/ba-cr --ingest-file docs/kb/your-new-doc.md
```
ba-cr ingests the document, auto-generates a CR from the digest, runs impact analysis,
and cascades updates on approval — no manual CR authoring needed.

See [WORKFLOW.md](docs/WORKFLOW.md) for the full state flow diagrams for requirements, plans, and change requests.

---

## Knowledge Base Guide

`docs/kb/` is yours. Organise it however suits your project — implr derives a **domain** from
each top-level subfolder:

```
docs/kb/
├── architecture/          → domain "architecture" (auto arch-relevant)
│   └── system-design.md
├── auth/                  → domain "auth"
│   ├── auth-flow.md
│   └── security-policy.md
├── billing/               → domain "billing"
│   └── billing-model.md
└── glossary.md            → domain "root"
```

- Files directly under `docs/kb/` belong to the `root` domain.
- Each subfolder is a domain; contradiction detection runs within each domain and across
  domains at the master-synthesis level.
- Mix formats freely: `.md`, `.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt`.
- When a decision changes, prefer adding a new document over editing the old one — implr detects
  the new file incrementally and flags any contradiction with the existing one.

---

## Configuration

`docs/implr/config/implr.config.yaml` controls behaviour:

```yaml
project:
  name: stokai
  stack_hint: "TypeScript, NestJS, PostgreSQL, Vitest"

paths:
  kb: docs/kb
  architecture: docs/ARCHITECTURE.md
  dev_standards: docs/implr/config/DEV-STANDARDS.md
  src: src
  tests: tests

behaviour:
  default_tdd_threshold: M        # complexity at/above which TDD is enforced
  require_approved_status: true   # dev-planner only processes approved requirements
  contradictions_block: false     # false = open questions; true = halt on conflict
  kb_supported_formats: [md, pdf, docx, xlsx, csv, txt]

jira:
  base_url: https://your-org.atlassian.net
  project_key: STOK
  api_token_env: JIRA_API_TOKEN   # env var name only; never the token itself
  # ... (used by the future ba-jira-populate skill)
```

`docs/implr/config/DEV-STANDARDS.md` defines your development standards. SOLID, a testing
baseline, and a security baseline are pre-filled and enforced by default; project-specific
sections are marked `[FILL IN]`.

---

## Schemas

Canonical schemas live in `docs/implr/schemas/` and are the contract every skill follows:

| Schema | Defines |
|--------|---------|
| `kb-index-schema.md` | index entry, per-doc digest, domain synthesis, master synthesis, digest log |
| `requirement-schema.md` | REQ-F / REQ-N structure incl. complexity, TDD, dependencies, Jira block |
| `plan-schema.md` | PLAN-F / PLAN-N structure incl. tasks, AC coverage, brainstorm decisions |
| `review-schema.md` | REVIEW structure, severity levels, verdict rules |
| `jira-schema.md` | requirement→Jira mapping for the future ba-jira-populate skill |
| `cr-schema.md` | CR-NNN structure incl. before/after, impact, status lifecycle, Jira block |

### ID conventions

| Prefix | Artefact |
|--------|----------|
| `REQ-F-` / `REQ-N-` | functional / non-functional requirement |
| `PLAN-F-` / `PLAN-N-` | functional / non-functional plan |
| `REVIEW-F-` / `REVIEW-N-` | review report |
| `CR-` | change request |

IDs are sequential, zero-padded to three digits, and never reused. A plan's number always
matches its requirement's number.

### Complexity → TDD

| Complexity | TDD enforced |
|------------|-------------|
| XS, S | no |
| M, L, XL | yes (threshold configurable) |

---

## Auto-Managed Files

Do not edit these by hand — they are owned by the skills:

| File / folder | Owner |
|---------------|-------|
| `docs/implr/kb-index/**` | doc-ingest |
| `docs/ARCHITECTURE.md` | arch-gen |
| `docs/implr/requirements/**` | ba-requirements-gen |
| `docs/implr/requirements/cr-index.md` | ba-cr |
| `docs/implr/plans/**` | dev-planner |
| `docs/implr/reviews/**` | dev-code-review |
| `docs/implr/schemas/**`, `docs/implr/templates/**` | plugin (refreshed on install) |

`docs/kb/change-requests/` is **yours** — place manually authored CR files there. ba-cr reads
them; doc-ingest detects them and prompts you to run `/ba-cr --file`.

To change a requirement after generation, use `/ba-cr` rather than editing the generated
requirement file directly. See [Changing Requirements](#changing-requirements).

---

## Troubleshooting

**Skills don't appear in Claude Code.** Claude Code reads unpacked skill folders containing a
`SKILL.md`, not `.skill` archives. Confirm `.claude/skills/<skill>/SKILL.md` exists. Restart
Claude Code if needed.

**arch-gen says there's no master synthesis.** Run `/doc-ingest` first.

**ba-requirements-gen produces shallow requirements.** Your KB documents may be too sparse, or
`DEV-STANDARDS.md`/KB lack detail. Check the open questions in the requirement files — they point
to the gaps.

**dev-planner skips a requirement.** It only plans requirements with `status: approved`. Promote
the requirement in its frontmatter.

**dev-executor warns about `[FILL IN]`.** Complete the relevant sections of
`docs/implr/config/DEV-STANDARDS.md` so generated code uses the right stack and conventions.

**A contradiction wasn't caught.** Contradictions are detected at domain-synthesis time. Ensure
both documents are in the same domain folder (or run `/doc-ingest --rebuild` to re-synthesise
everything).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: skills are plain `SKILL.md` instruction files;
schemas and templates live under `skills/implr-init/assets/`. Keep skills thin, keep the schemas
authoritative, and include before/after examples in PRs that change skill behaviour.

---

## License

MIT — see [LICENSE](LICENSE).
