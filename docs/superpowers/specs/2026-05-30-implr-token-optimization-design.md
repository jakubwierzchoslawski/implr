# implr Token Optimization — Design (v2.0.0)

## Overview

This spec covers the v2.0.0 restructuring of implr to cut token consumption by **3–4×**
without measurable quality loss. The change moves every heavy phase out of the main
conversation context and into dedicated, model-tier-optimized subagents, removes the most
wasteful default flows, and adds a small configuration surface so users can tune model tiers
per agent.

The data model and skill commands you already know — requirements, plans, change requests,
ARCHITECTURE.md, doc-ingest — are unchanged. What changes is **how** each skill executes
internally, and two specific user-facing flags that were silently expensive.

**Implementation order:** new agent layer + config first (no behavioural change), then
per-skill orchestrator rewrites, then breaking flag changes, then documentation.

---

## Goals and Non-Goals

**Goals**

- Reduce end-to-end token consumption by 3–4× for a typical pipeline run.
- Preserve every quality property already documented: traceability, contradiction detection,
  TDD discipline, SOLID enforcement, schema conformance.
- Let users tune model tiers per agent via `implr.config.yaml`.
- Keep the user-facing command surface as close to today as possible. Only flags that were
  structurally wasteful are removed.
- Update README and WORKFLOW.md so a new user can understand the full lifecycle and status
  flows without reading skill internals.

**Non-Goals**

- No change to the schemas (`requirement-schema.md`, `plan-schema.md`, `kb-index-schema.md`,
  `cr-schema.md`, `review-schema.md`, `jira-schema.md`).
- No change to file paths under `docs/implr/` (still owned by the same skills).
- No change to the high-level pipeline order (ingest → arch → reqs → approve → plan →
  execute → review).
- No new skills.

---

## Architecture

### Orchestrator + dedicated subagent model

Every skill becomes an **orchestrator** that runs in the main conversation context, handles
any interactive decisions (questions, confirmations, approvals), and dispatches mechanical or
analytical work to **dedicated subagents**. Each subagent runs in an isolated context window
with a focused system prompt, a minimal tool allowlist, and a model tier picked for the job.
Subagents return one summary message; the main context only grows by the dispatch payload and
the summary, never by the intermediate work.

This is hybrid execution: interactive parts stay in main for UX reasons; heavy parts run
isolated for token reasons.

### File layout

```
.claude/
├── skills/
│   ├── doc-ingest/
│   │   ├── SKILL.md                  thin orchestrator
│   │   └── phases/
│   │       ├── extract.md            dispatch prompt for doc-ingest-extractor
│   │       ├── digest.md             dispatch prompt for doc-ingest-digester
│   │       └── synthesize-domain.md  dispatch prompt for doc-ingest-synthesizer
│   ├── arch-gen/
│   │   ├── SKILL.md
│   │   └── phases/draft.md
│   ├── ba-requirements-gen/
│   │   ├── SKILL.md
│   │   └── phases/domain.md
│   ├── ba-cr/
│   │   ├── SKILL.md
│   │   └── phases/
│   │       ├── impact.md
│   │       └── apply.md
│   ├── dev-planner/
│   │   ├── SKILL.md
│   │   └── phases/plan-one.md
│   ├── dev-executor/
│   │   ├── SKILL.md
│   │   └── phases/execute-plan.md
│   ├── dev-code-review/
│   │   ├── SKILL.md
│   │   └── phases/review-plan.md
│   └── implr-init/SKILL.md           no phases — one-shot scaffolder
└── agents/                            NEW — dedicated subagent definitions
    ├── doc-ingest-extractor.md
    ├── doc-ingest-digester.md
    ├── doc-ingest-synthesizer.md
    ├── arch-drafter.md
    ├── requirements-domain-worker.md
    ├── cr-impact-analyzer.md
    ├── cr-applier.md
    ├── plan-worker.md
    ├── executor-worker.md
    └── code-review-worker.md
```

### Agent definition contract

Each file in `.claude/agents/<agent-name>.md` carries YAML frontmatter and a body that is the
agent's system prompt:

```markdown
---
name: doc-ingest-extractor
description: One-shot text extractor — reads one KB file, normalises text, writes cache entry.
tools: [Read, Write, Bash]
default_model: haiku
---

# System prompt body

You are a text extraction worker for the implr knowledge base. ...
```

Fields:

| Field | Meaning |
|---|---|
| `name` | Subagent type passed to the `Agent` tool. Must match filename. |
| `description` | One-line role summary. Used by the Agent tool catalogue. |
| `tools` | Allowlist. Worker has access to exactly these tools. |
| `default_model` | `haiku` \| `sonnet` \| `opus`. Used when `implr.config.yaml` does not override. |

### Dispatch contract

When an orchestrator dispatches a phase:

1. It resolves the model: `agents.<agent-name>` from `implr.config.yaml` if present, else the
   agent's `default_model`.
2. It calls `Agent(subagent_type=<agent-name>, model=<resolved>, prompt=<scope payload>)`.
3. The dispatch payload is a small, scope-specific input only — never the full phase prompt,
   which lives inside the agent's system prompt + the `phases/*.md` file the agent reads
   on first action.
4. The subagent reads stable inputs (schemas, config, CLAUDE.md) **first** so Anthropic's
   5-minute prompt cache reuses that prefix across dispatches.
5. The subagent writes its outputs to files and returns one final message with a structured
   summary the orchestrator can parse (file paths, counts, flags).

Independent dispatches are made **in parallel** in a single tool-use block; dependent
dispatches are sequenced into waves.

### Phase prompt file contract

Each `phases/*.md` file is the worker's task instruction. Orchestrator points the agent at it
via the dispatch payload (e.g. `"Read phases/extract.md and process file X"`). Keeping these
in files (not inline) is what makes them prompt-cache friendly.

The file is structured: stable preamble (what to read first), task description, output
contract, return-summary format.

---

## Per-Skill Changes

### implr-init

- No subagent dispatch — one-shot scaffolding stays inline.
- Updated to scaffold `.claude/agents/` alongside `.claude/skills/`.
- Updated to inject the `agents:` block into the seeded `implr.config.yaml` (with all
  defaults shown commented out, so users can uncomment and edit).
- SKILL.md description tightened.

### doc-ingest

**Flags after change:**

| Flag | After |
|------|------|
| `/doc-ingest` | Registry only (NEW default — no digests, no syntheses) |
| `/doc-ingest --digest` | Full pipeline (registry + per-doc digests + domain syntheses + master) |
| `/doc-ingest --file <path>` | Process one file (registry only unless `--digest` also passed) |
| `/doc-ingest --rebuild` | Reprocess everything (implies `--digest`) |
| `/doc-ingest --dry-run` | Preview, write nothing |
| `--no-digest` | **Removed** — redundant with new default |

**Phase mapping after change:**

| Phase | Where it runs |
|------|------|
| 1. Scan | Orchestrator |
| 2. Classify | Orchestrator |
| 3. Extract text to cache | **Parallel** `doc-ingest-extractor` (Haiku), one per NEW/CHANGED file |
| 4. Per-doc digest | **Parallel** `doc-ingest-digester` (Sonnet), one per NEW/CHANGED file. Skipped without `--digest` |
| 5. Domain syntheses | **Parallel** `doc-ingest-synthesizer` (Sonnet), one per affected domain. Skipped without `--digest` |
| 6. Master synthesis | Orchestrator (single integrative pass). Skipped without `--digest` |
| 7. Index update | Orchestrator |
| 8. Digest-log update | Orchestrator |
| 9. Report + post-report prompts | Orchestrator |

### arch-gen

Interactive (confirms inferred decisions). Mostly main, one heavy phase dispatched.

| Step | Where |
|------|------|
| Read master synthesis, identify decisions needing confirmation | Orchestrator |
| Ask user to confirm each inferred decision | Orchestrator (main) |
| Draft ARCHITECTURE.md from confirmed decisions + synthesis | **Dispatch** `arch-drafter` (Sonnet) |
| Show draft, optional user edits, write final | Orchestrator |

Flags unchanged.

### ba-requirements-gen

**Flags after change:**

| Flag | After |
|------|------|
| `/ba-requirements-gen` | Generate from existing syntheses |
| `/ba-requirements-gen --domain <name>` | Restrict to one domain |
| `/ba-requirements-gen --reprocess <doc>` | Re-derive from a specific source doc |
| `/ba-requirements-gen --dry-run` | Preview, write nothing |
| `--ingest` | **Removed**. Error: `--ingest removed in v2.0.0. Run /doc-ingest --digest first, then /ba-requirements-gen.` |
| `--ingest-file <path>` | **Removed**. Error points to `/doc-ingest --file <path> --digest` then `/ba-requirements-gen`. |

**Phase mapping after change:**

| Phase | Where |
|------|------|
| 0. Chain doc-ingest | **Removed** (flag gone) |
| 1. Load state, determine scope | Orchestrator |
| 2. Analyse per-domain | **Parallel** `requirements-domain-worker` (Sonnet), one per in-scope domain. Each writes REQs to a staging dir with slug-only filenames; returns file list + open questions + complexity tallies. |
| 3. Contradictions surfaced | Orchestrator aggregates from worker returns |
| 4. Generate requirement files | **Orchestrator does post-hoc ID assignment**: reads highest existing IDs, renames staged files to `REQ-F-NNN-slug.md` / `REQ-N-NNN-slug.md`, rewrites `req_id` inside each, moves to final paths. |
| 5. Update requirements-index.md | Orchestrator |
| 6. Update requirements-log.md | Orchestrator |
| 7. Report | Orchestrator |

The orchestrator dispatches a final `Explore` subagent for the cross-requirement coherence
sweep — read-only, no new agent file.

### ba-cr

Interactive (CLI interview). Hybrid.

| Step | Where |
|------|------|
| CLI interview (no `--file`) | Orchestrator (main) |
| Read CR file (`--file` / `--ingest-file`) | Orchestrator |
| Impact analysis across all requirements + plans | **Dispatch** `cr-impact-analyzer` (Sonnet, read-heavy: Read/Grep/Glob) |
| Show impact, get user approval | Orchestrator (main) |
| Apply CR-described diffs | **Parallel** `cr-applier` (Sonnet), one per affected REQ + one per affected PLAN |
| Update cr-index.md, log entry | Orchestrator |

Flags unchanged.

### dev-planner

Semi-interactive (`--brainstorm`). Hybrid.

| Step | Where |
|------|------|
| Parse args; if `--brainstorm`, brainstorming dialogue | Orchestrator (main) |
| Per-requirement plan generation | **Parallel** `plan-worker` (Sonnet), one per requirement. Dependent reqs sequenced into waves. |
| Cross-requirement coherence pass | Built-in `Explore` subagent (read-only) |
| Write plans-index, plans-log, report | Orchestrator |

Flags unchanged.

### dev-executor

Non-interactive. Hybrid.

| Step | Where |
|------|------|
| Parse args, validate plan deps, determine waves | Orchestrator |
| Implementation per plan | **Dispatch** `executor-worker` (**Opus** — TDD + SOLID need strong model). Tasks inside a plan stay sequential (TDD red→green→refactor). Independent plans dispatched in parallel waves. |
| Update plan status, log, report | Orchestrator |

Flags unchanged.

### dev-code-review

Non-interactive. Hybrid.

| Step | Where |
|------|------|
| Parse args, identify plans | Orchestrator |
| Per-plan review | **Parallel** `code-review-worker` (Sonnet, Read/Grep/Glob), one per plan. Returns verdict + finding counts by severity. |
| Write review index, aggregate, report | Orchestrator |

Flags unchanged.

---

## Configuration

### New `agents:` section in `implr.config.yaml`

```yaml
# Per-agent model selection. Values: haiku | sonnet | opus.
# Omit an entry (or comment it out) to fall back to the agent's built-in default_model.
agents:
  doc-ingest-extractor: haiku       # mechanical text extraction
  doc-ingest-digester: sonnet       # per-doc digest
  doc-ingest-synthesizer: sonnet    # per-domain synthesis
  arch-drafter: sonnet              # architecture draft
  requirements-domain-worker: sonnet
  cr-impact-analyzer: sonnet
  cr-applier: sonnet
  plan-worker: sonnet
  executor-worker: opus             # TDD + SOLID enforcement
  code-review-worker: sonnet
```

**Resolution order at dispatch time:**

1. `agents.<agent-name>` from `implr.config.yaml` — if present, wins.
2. `default_model` from `.claude/agents/<agent-name>.md` frontmatter — fallback.

The installer never overwrites `implr.config.yaml`, so user-customised models survive plugin
updates. New agents added by future implr versions appear with their built-in defaults until
the user adds them to the config.

---

## Breaking Changes (v2.0.0)

| Change | User impact | Migration |
|---|---|---|
| `/doc-ingest` default flipped to registry-only | Users wanting full synthesis must add `--digest` | Add `--digest` to existing invocations that need synthesis |
| `/doc-ingest --no-digest` flag removed | Flag now redundant | Drop the flag |
| `/ba-requirements-gen --ingest` removed | Two-command flow required | Run `/doc-ingest --digest` first, then `/ba-requirements-gen` |
| `/ba-requirements-gen --ingest-file <path>` removed | Same | Run `/doc-ingest --file <path> --digest` first, then `/ba-requirements-gen` |
| `.claude/agents/` is now required | New install artefact | Re-run installer; agents are plugin-owned (always replaced like skills) |
| `implr.config.yaml` gains optional `agents:` section | Backward-compatible | No action required; section is optional |

Each removed flag produces a clear error message pointing to the replacement command. No
silent breakage.

---

## Documentation Updates

### README.md — full rewrite of structure

The README must let a new user understand the whole plugin lifecycle — requirements, plans,
change requests, statuses, user interaction points — without reading skill internals or
WORKFLOW.md.

**Final section order:**

1. **What implr does** — one-paragraph elevator pitch + the pipeline diagram.
2. **Why implr** — traceability / incremental / standards-driven / human-gated.
3. **The Skills** — table (current style, updated).
4. **Installation** — current content, with `.claude/agents/` mention.
5. **Updating implr** — current content; explicit note that updates to v2.0 require re-running
   the installer to pick up `.claude/agents/`.
6. **Required Folder Structure** — current diagram, with `.claude/agents/` added.
7. **Quick Start** — updated for v2.0 commands (`/doc-ingest --digest` shown explicitly).
8. **The Full Pipeline** — current step-by-step, updated for the two-step ingest flow.
9. **How You Interact With implr** — NEW. The user-interaction summary. See subsections below.
10. **Status Flows** — NEW. Three small state diagrams + tables. See subsections below.
11. **Skills Reference** — per-skill flag tables, updated for v2.0.
12. **Changing Requirements** — current section, kept.
13. **Knowledge Base Guide** — current section, kept.
14. **Configuration** — current section, with new `agents:` block documented.
15. **Customising Model Tiers** — NEW. Short subsection under Configuration. Per-agent model
    override, resolution order, example of downgrading executor-worker for cheaper runs.
16. **Performance & Token Efficiency** — NEW. Brief explanation of the orchestrator + subagent
    model, why it saves tokens, where prompt-cache friendliness fits.
17. **Schemas** — current section, kept.
18. **Auto-Managed Files** — current section, kept.
19. **Migrating from v1.x to v2.0** — NEW. Five-step migration checklist.
20. **Troubleshooting** — current section, kept; one entry added about agent-not-found.
21. **Contributing** — current section, kept; cross-references CONTRIBUTING.md.
22. **License** — kept.

**Section 9 — "How You Interact With implr"** must include:

- The interaction summary at a glance: which skills are non-interactive (you run them and
  wait), which are interactive (they ask you questions), and which are semi-interactive
  (interactive when invoked with specific flags).
- An ASCII table:

  | Skill | Interaction mode | When the skill asks for input |
  |---|---|---|
  | implr-init | Interactive | Project name, paths, stack hint — once at scaffold |
  | doc-ingest | Non-interactive | Never |
  | arch-gen | Interactive | Confirms each inferred architecture decision |
  | ba-requirements-gen | Non-interactive | Never (open questions surfaced in files) |
  | ba-cr | Interactive (default), non-interactive with `--file` | CR interview without `--file` |
  | dev-planner | Non-interactive (default), interactive with `--brainstorm` | Design exploration if `--brainstorm` |
  | dev-executor | Non-interactive | Never (manual actions flagged in report) |
  | dev-code-review | Non-interactive | Never |

- The "human gates" that block flow regardless of skill: approving requirements before
  planning, approving CR impact before applying, resolving Critical/High review findings
  before merge.
- A pointer: "See `docs/WORKFLOW.md` for full diagrams of every state transition."

**Section 10 — "Status Flows"** must include:

Three short subsections, each with a small diagram (ASCII or text-rendered Mermaid) and the
table of state transitions. Pulled from WORKFLOW.md in summary form, with a sentence pointing
to WORKFLOW.md for the full text.

- **10.1 Requirements** — `draft → approved → under-review → approved` (with `blocked` as a
  side-state when open questions can't be resolved). What triggers each transition; who can
  make it (Claude vs human).
- **10.2 Plans** — `ready → in-progress → done` (with `replan` triggered by CRs). What
  triggers each; what dev-executor and dev-planner do.
- **10.3 Change Requests** — `draft → impact-analysed → approved → applied` (with `rejected`
  as a terminal alt). Three entry paths (CLI / manual file / KB doc) shown.

Each subsection ends with: "Full diagrams and edge cases in [WORKFLOW.md](docs/WORKFLOW.md)."

### docs/WORKFLOW.md

- Update existing diagrams to show parallel subagent dispatch where relevant (purely
  illustrative — does not change semantics).
- New section: **"Subagent Dispatch Model"** — explains the orchestrator/worker split,
  which workers are dispatched at which phase, model tiers used, and how config overrides
  resolve. This is the technical companion to README §16.
- Update Change Request flow diagrams to reflect that impact analysis and CR application now
  go through dedicated subagents.
- Keep the existing requirement/plan/CR state-flow content intact; README §10 will summarise
  it, this file remains the authoritative source.

### CHANGELOG.md

v2.0.0 entry covering:

- Breaking: `--ingest` and `--ingest-file` removed from ba-requirements-gen.
- Breaking: `/doc-ingest` default flipped (digest now opt-in via `--digest`).
- Breaking: `--no-digest` flag removed (redundant).
- New: `.claude/agents/` shipped with ten dedicated agents.
- New: `agents:` section in `implr.config.yaml` for per-agent model overrides.
- New: `phases/` subfolder inside each heavy skill.
- Expected token savings: 3–4× on typical end-to-end runs.

### CONTRIBUTING.md

Add:

- **Authoring a dedicated agent** — where to put the file, frontmatter contract, tool
  allowlist principles, `default_model` selection guidance.
- **Prompt-cache-friendly ordering** — convention that stable reads (schema, config) come
  first in any SKILL.md or phase prompt, before dynamic inputs.
- **Phase files** — naming, location under `skills/<skill>/phases/`, how SKILL.md references
  them in dispatch payloads.

### Installer scripts (`install.sh`, `install.ps1`, `install.bat`)

- Copy `.claude/agents/` directory alongside `.claude/skills/`.
- Idempotency rule: agents are plugin-owned, always replaced like skills.
- Refuse to overwrite `implr.config.yaml` (existing behaviour preserved).
- When seeding a fresh `implr.config.yaml`, include a commented-out `agents:` block with all
  ten defaults shown.

---

## Validation / Quality Gates

A change qualifies as complete only when:

- [ ] All ten agent files exist under `.claude/agents/` with the documented frontmatter.
- [ ] All ten phase files exist under `skills/<skill>/phases/` (where applicable).
- [ ] Each rewritten SKILL.md compiles to ≤ 100 lines (orchestrator-only).
- [ ] Each rewritten SKILL.md reads stable inputs (schema, config) before dynamic inputs.
- [ ] `--ingest`, `--ingest-file`, `--no-digest` produce the documented error messages.
- [ ] `/doc-ingest` without `--digest` writes registry only; with `--digest` runs the full
      pipeline.
- [ ] `implr.config.yaml` `agents:` section, when present, correctly overrides agent defaults
      at dispatch time.
- [ ] Installer copies `.claude/agents/` on a fresh install and on update.
- [ ] README §9 and §10 exist and contain the documented content; cross-references to
      WORKFLOW.md are correct.
- [ ] CHANGELOG v2.0.0 entry lists every breaking change and the new config surface.
- [ ] Migrating-from-v1 section in README walks through the five steps without ambiguity.
- [ ] On a sample KB (5 domains, 30 docs), the new pipeline produces structurally identical
      output files to v1 (same REQ IDs, same plans, same digests at the same checksums) when
      run with `--digest`.

---

## Out of Scope

- New skills (none added).
- Schema changes (none).
- Changes to file paths owned by skills (none).
- Jira integration changes (out of scope; `jira:` block unchanged).
- Replacing the `Explore` built-in subagent with custom ones (Explore is fit-for-purpose
  for read-only sweeps).
- Tier 2 changes (SKILL.md split into rules + reference.md, lazy schema reads) — deferred
  to v2.1 or later.

---

## Risks

- **Subagent overhead defeats savings on tiny KBs.** A 3-document KB pays the dispatch
  overhead without benefiting from parallelism. Mitigation: orchestrator skips dispatch
  when fewer than 2 units would be processed (inline path), keeping single-doc operations
  efficient. This threshold is implementation-level, not user-facing.
- **Worker model too cheap for the job.** A Sonnet worker may produce shallower requirements
  than today's Opus-default run on complex domains. Mitigation: `requirements-domain-worker`
  defaults to Sonnet; the README documents how to override to Opus via config when quality
  matters.
- **Phase prompt drift from SKILL.md.** Two files per skill (SKILL.md + phases/*.md) increases
  the surface to keep in sync. Mitigation: CONTRIBUTING.md authoring guidance + the
  validation checklist above.
- **Parallel dispatch hits rate limits.** A 20-domain ba-requirements-gen run would spawn 20
  concurrent dispatches. Mitigation: orchestrator caps parallelism at a sensible default
  (e.g. 5 concurrent) and sequences additional work into waves.
