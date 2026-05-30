# implr Token Optimization Implementation Plan (v2.0.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce implr token consumption by 3–4× by introducing dedicated subagents for heavy phases, making model tiers configurable, and removing two wasteful default flows — without changing the schemas or breaking the high-level pipeline.

**Architecture:** Each skill becomes an orchestrator running in the main conversation context that dispatches mechanical/analytical work to dedicated subagents. Subagents have focused system prompts, restricted tool allowlists, and tier-appropriate models (Haiku/Sonnet/Opus). Phase prompts live in `skills/<skill>/phases/*.md` files for prompt-cache friendliness. Per-agent model overrides are configurable in `implr.config.yaml`.

**Tech Stack:** Markdown (skills, agents, phase files, docs), YAML (config), shell scripts (installers), Claude Code Agent tool.

**Spec:** `docs/superpowers/specs/2026-05-30-implr-token-optimization-design.md`

---

## File Structure

### New files

```
.claude/agents/                                  (10 agent definitions)
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

skills/<skill>/phases/                           (10 phase prompts)
├── doc-ingest/phases/extract.md
├── doc-ingest/phases/digest.md
├── doc-ingest/phases/synthesize-domain.md
├── arch-gen/phases/draft.md
├── ba-requirements-gen/phases/domain.md
├── ba-cr/phases/impact.md
├── ba-cr/phases/apply.md
├── dev-planner/phases/plan-one.md
├── dev-executor/phases/execute-plan.md
└── dev-code-review/phases/review-plan.md
```

### Modified files

```
skills/doc-ingest/SKILL.md                       full rewrite (orchestrator)
skills/arch-gen/SKILL.md                         full rewrite
skills/ba-requirements-gen/SKILL.md              full rewrite
skills/ba-cr/SKILL.md                            full rewrite
skills/dev-planner/SKILL.md                      full rewrite
skills/dev-executor/SKILL.md                     full rewrite
skills/dev-code-review/SKILL.md                  full rewrite
skills/implr-init/SKILL.md                       updated (description + agents/ scaffold)
skills/implr-init/assets/implr.config.yaml       updated (commented agents: block)
install.sh                                       updated (copy .claude/agents/)
install.ps1                                      updated
install.bat                                      updated
README.md                                        major restructure
docs/WORKFLOW.md                                 add Subagent Dispatch Model section
CHANGELOG.md                                     v2.0.0 entry
CONTRIBUTING.md                                  add agent + phase authoring section
```

---

## Conventions Used Throughout

### Agent file frontmatter contract

```yaml
---
name: <agent-name>                # MUST match filename without .md
description: <one-line role>      # Used by Agent tool catalogue
tools: [Read, Write, Bash, ...]   # Allowlist; only these are callable
default_model: haiku|sonnet|opus  # Used when implr.config.yaml has no override
---
```

### Orchestrator dispatch pattern (every heavy phase)

1. Resolve model: read `docs/implr/config/implr.config.yaml`; if `agents.<agent-name>` is set, use it; otherwise use the agent's `default_model`.
2. Dispatch with `Agent(subagent_type=<agent-name>, model=<resolved>, prompt=<small scope payload>)`.
3. Dispatch in parallel where units are independent (single tool-use block containing N Agent calls). Cap concurrency at 5; sequence remainder into waves.
4. Parse the return summary (structured plain-text key/value lines).
5. Aggregate into the orchestrator's final report.

### Stable-reads-first ordering (every SKILL.md and phase file)

Every orchestrator and every phase prompt MUST read stable inputs (schemas, `implr.config.yaml`, `CLAUDE.md` if relevant) **before** any dynamic input (the file being processed, the requirement being planned, etc.). This is required for prompt-cache hits.

---

## Task 1: Create the ten dedicated agent definitions

**Files:**
- Create: `.claude/agents/doc-ingest-extractor.md`
- Create: `.claude/agents/doc-ingest-digester.md`
- Create: `.claude/agents/doc-ingest-synthesizer.md`
- Create: `.claude/agents/arch-drafter.md`
- Create: `.claude/agents/requirements-domain-worker.md`
- Create: `.claude/agents/cr-impact-analyzer.md`
- Create: `.claude/agents/cr-applier.md`
- Create: `.claude/agents/plan-worker.md`
- Create: `.claude/agents/executor-worker.md`
- Create: `.claude/agents/code-review-worker.md`

These files live at the repo root (not under `skills/`) because the installer must copy them to `.claude/agents/` independently of skills.

- [ ] **Step 1: Create `.claude/agents/` directory at repo root**

```bash
mkdir -p .claude/agents
```

- [ ] **Step 2: Write `.claude/agents/doc-ingest-extractor.md`**

```markdown
---
name: doc-ingest-extractor
description: One-shot text extractor — reads one knowledge-base file, normalises its text, and writes the cache entry. Returns the cache path and word count.
tools: [Read, Write, Bash]
default_model: haiku
---

# doc-ingest-extractor

You are a text-extraction worker for the implr knowledge base. You have one job per dispatch:
read a single file at the path the orchestrator gives you, extract its text content to a
normalised UTF-8 string, and write that string to `docs/implr/kb-index/cache/<slug>.txt`.

You never analyse content. You only extract and write.

## Read first (cache-friendly order)

1. `docs/implr/config/implr.config.yaml` — to confirm `kb_supported_formats`.

## Inputs (from the orchestrator)

```
file_path: docs/kb/<domain>/<name>.<ext>
slug: <pre-computed-slug>
```

## Extraction rules

| Format | How to extract |
|---|---|
| md, txt | Direct Read |
| pdf | `pdftotext "<file>" -` preferred; fallback `python3 -c "import pymupdf; doc=pymupdf.open('<file>'); print('\n'.join(p.get_text() for p in doc))"` |
| docx | `python3 -c "from docx import Document; d=Document('<file>'); print('\n'.join(p.text for p in d.paragraphs))"` |
| xlsx | `python3 -c "from openpyxl import load_workbook; ..."` — each sheet rendered as labelled rows |
| csv | Direct Read; preserve header row |
| other | Do not extract. Return `status: unsupported`. |

If extraction fails or a tool is unavailable, return `status: extraction_failed` with the
error message. Do not write a partial cache file.

## Output

Write the extracted text to `docs/implr/kb-index/cache/<slug>.txt`.

## Return summary (your one final message)

```
slug: <slug>
cache_path: docs/implr/kb-index/cache/<slug>.txt
word_count: <n>
status: extracted | unsupported | extraction_failed
error: <if extraction_failed>
```

Nothing else.
```

- [ ] **Step 3: Write `.claude/agents/doc-ingest-digester.md`**

```markdown
---
name: doc-ingest-digester
description: Produces one per-document digest from a cached text file. Extracts business rules, system behaviours, entities, integration points, NFR signals, ambiguities, and arch signals per the kb-index schema.
tools: [Read, Write]
default_model: sonnet
---

# doc-ingest-digester

You produce exactly one per-document digest file from one cached text file. You write to
`docs/implr/kb-index/digests/per-doc/<slug>-digest.md` following the kb-index schema.

## Read first

1. `docs/implr/schemas/kb-index-schema.md` — for the per-doc digest structure.
2. `docs/implr/config/implr.config.yaml` — for behaviour flags.

## Inputs (from the orchestrator)

```
slug: <slug>
cache_path: docs/implr/kb-index/cache/<slug>.txt
source_path: docs/kb/<domain>/<name>.<ext>
domain: <domain>
```

## Work

Read the cache file. Produce a digest with all schema-required sections: business rules,
system behaviours, data entities, integration points, NFR signals, ambiguities,
architecture signals.

Determine `arch_relevant`:
- `true` — file is under `docs/kb/architecture/`, OR has `implr_tags: [architecture]` in
  markdown frontmatter, OR has a sibling `<name>.meta.yaml` containing that tag (look for
  these alongside `source_path`)
- `auto` — content shows architecture signals (topology, layering, technology decisions,
  integration patterns) but no explicit tag
- `false` — otherwise

Compute the digest checksum per schema (sha256 of the canonical sorted body sections).

## Output

Write to `docs/implr/kb-index/digests/per-doc/<slug>-digest.md`.

## Return summary

```
slug: <slug>
digest_path: docs/implr/kb-index/digests/per-doc/<slug>-digest.md
digest_checksum: <sha256>
arch_relevant: true | auto | false
ambiguities_count: <n>
contradiction_signals: <n>
```
```

- [ ] **Step 4: Write `.claude/agents/doc-ingest-synthesizer.md`**

```markdown
---
name: doc-ingest-synthesizer
description: Rebuilds the synthesis for one domain by reading all current per-doc digests in that domain. Detects intra-domain contradictions and computes the synthesis checksum.
tools: [Read, Write, Glob]
default_model: sonnet
---

# doc-ingest-synthesizer

You rebuild exactly one domain synthesis. You write to
`docs/implr/kb-index/domains/<domain>-synthesis.md`.

## Read first

1. `docs/implr/schemas/kb-index-schema.md` — for the domain-synthesis structure.

## Inputs (from the orchestrator)

```
domain: <domain>
digests_glob: docs/implr/kb-index/digests/per-doc/<domain-prefix>*-digest.md
```

(The orchestrator gives you the glob covering the domain's digests. Use Glob to enumerate.)

## Work

Read every per-doc digest in the domain. Consolidate and deduplicate business rules.
**Detect contradictions across all digests in the domain** — classify each as Hard
conflict, Soft conflict, Version drift, or Scope overlap. Record cross-domain dependencies
and NFR candidates. Surface any "Ambiguities Detected" section consolidating ambiguities
across the domain's digests.

Compute `synthesis_checksum` from the sorted source digest checksums.

## Output

Write to `docs/implr/kb-index/domains/<domain>-synthesis.md` following the schema.

## Return summary

```
domain: <domain>
synthesis_path: docs/implr/kb-index/domains/<domain>-synthesis.md
synthesis_checksum: <sha256>
contradictions: <n>
ambiguities: <n>
nfr_candidates: <n>
arch_relevant_files: <n>
```
```

- [ ] **Step 5: Write `.claude/agents/arch-drafter.md`**

```markdown
---
name: arch-drafter
description: Drafts the ARCHITECTURE.md document from the master synthesis and a list of human-confirmed architectural decisions.
tools: [Read, Write]
default_model: sonnet
---

# arch-drafter

You draft `docs/ARCHITECTURE.md` based on the master synthesis and decisions the user has
already confirmed in the main conversation. You do not ask for more decisions.

## Read first

1. `docs/implr/kb-index/master-synthesis.md` — primary input.
2. `docs/implr/config/DEV-STANDARDS.md` — for stack/conventions context.
3. `docs/implr/config/implr.config.yaml` — for `project.name` and `stack_hint`.

## Inputs (from the orchestrator)

```
mode: create | update
existing_path: docs/ARCHITECTURE.md   (only when mode=update)
confirmed_decisions:
  - id: D1, summary: ..., choice: ...
  - id: D2, summary: ..., choice: ...
```

## Work

Produce a complete `docs/ARCHITECTURE.md` covering: system context, component map,
technology stack, integration patterns, data flow, security posture, deployment topology.
Use the confirmed decisions as authoritative for any contested choice. Reference
arch-relevant KB docs by path in a Traceability section.

For `mode: update`: produce a diff-style proposal. Highlight what changes versus the
existing file and why. Write the new full file content.

## Output

Write to `docs/ARCHITECTURE.md`.

## Return summary

```
arch_path: docs/ARCHITECTURE.md
mode: create | update
sections_written: <n>
decisions_applied: <n>
traceability_entries: <n>
```
```

- [ ] **Step 6: Write `.claude/agents/requirements-domain-worker.md`**

```markdown
---
name: requirements-domain-worker
description: Generates functional and non-functional requirements for one domain by reading the domain synthesis (plus the cache when ambiguity is flagged). Writes REQ files to a staging directory with slug-only filenames.
tools: [Read, Write, Glob]
default_model: sonnet
---

# requirements-domain-worker

You generate requirements for exactly one domain. You write REQ files with slug-only
filenames to a staging directory the orchestrator gives you. The orchestrator will rename
them with sequential IDs after all workers return.

## Read first

1. `docs/implr/schemas/requirement-schema.md` — the exact REQ structure.
2. `docs/implr/config/implr.config.yaml` — for `default_tdd_threshold` and TDD mapping.
3. `docs/implr/config/DEV-STANDARDS.md` — relevant non-functional baselines.

## Inputs (from the orchestrator)

```
domain: <domain>
synthesis_path: docs/implr/kb-index/domains/<domain>-synthesis.md
master_synthesis_path: docs/implr/kb-index/master-synthesis.md
cache_dir: docs/implr/kb-index/cache/
staging_dir: docs/implr/requirements/.staging/<domain>/
existing_reqs_index: docs/implr/requirements/requirements-index.md   (may not exist)
mode: create | reprocess
reprocess_target: <doc-or-cr-path>   (only when mode=reprocess)
```

## Work

Read the domain synthesis. Check its "Ambiguities Detected" section. For each ambiguity
either resolve it from `cache/<slug>.txt` (if the cache text is unambiguous) or surface
it as an Open Question citing the source document.

Generate one REQ per: distinct user-facing behaviour, business rule, data lifecycle event,
external integration. Generate one NFR per distinct cross-cutting quality constraint
(read the master synthesis for global NFR candidates).

When the synthesis is sufficient, do not deep-dive. Go to `cache/<slug>.txt` only when:
- The domain synthesis flags an ambiguity for that doc
- Field-level data models are needed
- An NFR needs a specific numeric target that the digest paraphrased
- A requirement cannot meet the quality gate (≥ 2 testable ACs) from the synthesis alone

Apply requirement inference (user journeys, entity lifecycles, integration mentions, NFR
signals) per the schema. Set `complexity` from subtask aggregation; derive `tdd_required`
from complexity vs `default_tdd_threshold`.

For `mode: reprocess` with a CR target: read the CR alongside the affected requirement and
apply the change described in the CR's `before`/`after` fields. Drop status to
`under-review`.

## Output

Write each requirement to:
- `<staging_dir>/<slug>.md` for functional reqs (orchestrator picks `REQ-F-` prefix later)
- `<staging_dir>/n-<slug>.md` for non-functional reqs (prefix `n-` so orchestrator picks
  `REQ-N-`)

Leave `req_id:` field empty in frontmatter — the orchestrator fills it.

## Return summary

```
domain: <domain>
files_written:
  - <staging_dir>/<slug>.md (type: functional, complexity: <X>)
  - <staging_dir>/n-<slug>.md (type: non-functional, complexity: <X>)
functional_count: <n>
non_functional_count: <n>
open_questions: <n>
contradictions_flagged: <n>
```
```

- [ ] **Step 7: Write `.claude/agents/cr-impact-analyzer.md`**

```markdown
---
name: cr-impact-analyzer
description: Analyses the impact of a Change Request across all requirements and plans. Returns the set of REQ/PLAN files affected and the kind of change required for each.
tools: [Read, Grep, Glob]
default_model: sonnet
---

# cr-impact-analyzer

You read one Change Request and determine which requirements and plans it affects and how.
You do not modify any files. Read-only.

## Read first

1. `docs/implr/schemas/cr-schema.md`
2. `docs/implr/schemas/requirement-schema.md`
3. `docs/implr/schemas/plan-schema.md`

## Inputs

```
cr_path: docs/kb/change-requests/CR-NNN-<slug>.md
requirements_dir: docs/implr/requirements/
plans_dir: docs/implr/plans/
```

## Work

Read the CR. Identify its target (single requirement, multiple requirements, system-wide
behaviour). For each affected requirement:
- Determine change kind: additive AC, contradictory rule, scope expansion, scope cut,
  rewording-only
- Check whether a plan exists; if so, determine whether the plan needs full replan or
  patch only

Use Grep to find all references to changed entities/behaviours across requirements and
plans. Cross-check every CR-described change against existing AC sets.

## Output

No file writes. Your return summary is the impact report.

## Return summary

```
cr_id: CR-NNN
target_summary: <one-line>
affected_requirements:
  - id: REQ-F-NNN
    change_kind: additive | contradictory | scope_expansion | scope_cut | rewording
    current_status: <status>
    proposed_status: <status>
    plan_exists: true | false
    plan_action: none | patch | replan
  - ...
affected_plans:
  - id: PLAN-F-NNN
    action: none | patch | replan
    reason: <short>
new_requirements_proposed: <n>
contradictions_with_existing: <n>
risks: <n>
```
```

- [ ] **Step 8: Write `.claude/agents/cr-applier.md`**

```markdown
---
name: cr-applier
description: Applies one Change Request's specified diff to one target file (a requirement or a plan). Updates status, source_docs, and writes the change.
tools: [Read, Write, Edit]
default_model: sonnet
---

# cr-applier

You apply a CR-described change to exactly one target file. You make a focused edit; you do
not invent additional changes.

## Read first

1. `docs/implr/schemas/cr-schema.md`
2. The schema for your target type (`requirement-schema.md` OR `plan-schema.md`).

## Inputs

```
cr_path: docs/kb/change-requests/CR-NNN-<slug>.md
target_path: docs/implr/requirements/.../REQ-F-NNN-<slug>.md
                 OR docs/implr/plans/.../PLAN-F-NNN-<slug>.md
target_kind: requirement | plan
action: patch | replan
status_change: <new-status>
```

## Work

Read the CR. Read the target. Apply the change exactly as described in the CR's
`before`/`after` fields. For requirements:
- Add the CR filename to `source_docs`
- Update `status` per `status_change`
- For an additive change, append the new AC(s); do not rewrite existing ACs.
- For a contradictory change, replace the rule and add an Open Question entry citing the CR.

For plans:
- For `action: patch`, apply the specific task additions/removals.
- For `action: replan`, write a stub `replan_required: true` marker; the orchestrator will
  invoke dev-planner separately. Do not regenerate the plan body yourself.

## Return summary

```
target_path: <path>
target_kind: requirement | plan
action_applied: patch | replan | replan_marker_set
fields_changed:
  - source_docs
  - status: <old> → <new>
  - acceptance_criteria: +<n>
status: applied | replan_required
```
```

- [ ] **Step 9: Write `.claude/agents/plan-worker.md`**

```markdown
---
name: plan-worker
description: Produces one implementation plan for one approved requirement. Applies SOLID at design level, injects NFR constraints, sets per-task TDD flags.
tools: [Read, Write, Grep, Glob]
default_model: sonnet
---

# plan-worker

You produce exactly one plan file for exactly one requirement. You apply SOLID and
DEV-STANDARDS to the design. You set per-task TDD flags from task complexity.

## Read first

1. `docs/implr/schemas/plan-schema.md`
2. `docs/ARCHITECTURE.md`
3. `docs/implr/config/DEV-STANDARDS.md`
4. `docs/implr/config/implr.config.yaml` — for TDD threshold and paths.

## Inputs

```
requirement_path: docs/implr/requirements/.../REQ-F-NNN-<slug>.md
plan_path_out: docs/implr/plans/functional/PLAN-F-NNN-<slug>.md
            OR docs/implr/plans/non-functional/PLAN-N-NNN-<slug>.md
mode: create | replan
existing_plan_path: <only when mode=replan>
existing_reqs_index: docs/implr/requirements/requirements-index.md
existing_plans_index: docs/implr/plans/plans-index.md
brainstorm_decisions: <list of design decisions reached in main; may be empty>
```

## Work

Read the requirement. Read the architecture and standards. Use Grep to identify related
existing components in `src/`. Decompose the requirement into ordered tasks. Each task
carries: title, files touched, complexity, tdd flag, AC coverage list.

If `brainstorm_decisions` is non-empty, treat them as authoritative for any design choice
they cover.

If a dependent requirement's plan is missing, surface as a blocker — do not write a stub
plan for that dependency.

## Output

Write to `plan_path_out`. Preserve `plan_id` and `created_at` when `mode: replan`.

## Return summary

```
plan_path: <path>
plan_id: PLAN-F-NNN
tasks_count: <n>
ac_coverage_pct: <n>
blockers: <list of REQ ids whose plans are missing>
brainstorm_decisions_applied: <n>
```
```

- [ ] **Step 10: Write `.claude/agents/executor-worker.md`**

```markdown
---
name: executor-worker
description: Implements one plan end-to-end. Runs tasks in plan order, enforces TDD for tasks at or above the configured threshold, applies SOLID in code.
tools: [Read, Write, Edit, Bash, Grep, Glob]
default_model: opus
---

# executor-worker

You implement one plan, task by task in the order defined by the plan. You enforce TDD for
tasks where `tdd_required: true`. You apply SOLID in code, not just at design level.

## Read first

1. `docs/implr/schemas/plan-schema.md`
2. `docs/ARCHITECTURE.md`
3. `docs/implr/config/DEV-STANDARDS.md`
4. `docs/implr/config/implr.config.yaml` — for `src` and `tests` paths.

## Inputs

```
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
resume_task: <task-id or omitted>
```

## Work

Read the plan. For each task in order:

- If the task is `tdd_required: true`:
  1. Write the failing test(s) named in the task's AC list.
  2. Run the test runner; verify failure.
  3. Implement the minimal code to pass.
  4. Run the test runner; verify pass.
  5. Refactor if needed; re-verify.
  6. Commit (or note commit-ready state if commits are deferred).
- If the task is not TDD-required (XS, S complexity below threshold): write the code and
  any included smoke tests.

Note any manual action you cannot perform (missing credentials, environment-specific
config). Do not invent secrets.

Update plan status fields as you complete tasks.

## Output

Implementation files under `src/` and `tests/` per config paths.

## Return summary

```
plan_id: PLAN-F-NNN
tasks_completed: <n>
tasks_blocked: <n>
manual_actions_required:
  - <description>
files_created: <n>
files_modified: <n>
tests_added: <n>
tests_pass: true | false
plan_status: in-progress | done | blocked
```
```

- [ ] **Step 11: Write `.claude/agents/code-review-worker.md`**

```markdown
---
name: code-review-worker
description: Reviews one plan's output in a fresh context. Verifies acceptance criteria, checks architecture/SOLID/security, audits tests, issues a verdict.
tools: [Read, Grep, Glob, Write]
default_model: sonnet
---

# code-review-worker

You review the code produced by exactly one plan. You verify each acceptance criterion is
met, check architecture conformance, SOLID, security baseline, and tests. You issue a
verdict and write the review file.

## Read first

1. `docs/implr/schemas/review-schema.md`
2. `docs/ARCHITECTURE.md`
3. `docs/implr/config/DEV-STANDARDS.md`
4. The plan and the requirement (paths in inputs).

## Inputs

```
plan_path: docs/implr/plans/.../PLAN-F-NNN-<slug>.md
requirement_path: docs/implr/requirements/.../REQ-F-NNN-<slug>.md
review_path_out: docs/implr/reviews/REVIEW-F-NNN-<slug>.md
src_path: src
tests_path: tests
```

## Work

For each AC in the requirement, locate the implementing code and the verifying test.
Verify the test would actually fail without the code (read-through; you do not run code).
Check SOLID violations, architecture deviations, security baseline (input validation,
authn/authz, secret handling, output encoding). Audit test design (coverage of the AC,
not just lines).

Classify findings by severity per schema: Critical, High, Medium, Low, Info. Choose
verdict per schema rules: Critical or High present → `changes-required` (or `rejected`
for Critical without recoverable path). All Mediums/below → `approved-with-warnings`. No
findings → `approved`.

## Output

Write to `review_path_out`.

## Return summary

```
review_path: <path>
plan_id: PLAN-F-NNN
verdict: approved | approved-with-warnings | changes-required | rejected
findings:
  critical: <n>
  high: <n>
  medium: <n>
  low: <n>
  info: <n>
ac_coverage: <n>/<total>
```
```

- [ ] **Step 12: Commit**

```bash
git add .claude/agents/
git commit -m "feat(agents): add 10 dedicated subagent definitions for v2.0.0"
```

---

## Task 2: Create the ten phase prompt files

**Files:**
- Create: `skills/doc-ingest/phases/extract.md`
- Create: `skills/doc-ingest/phases/digest.md`
- Create: `skills/doc-ingest/phases/synthesize-domain.md`
- Create: `skills/arch-gen/phases/draft.md`
- Create: `skills/ba-requirements-gen/phases/domain.md`
- Create: `skills/ba-cr/phases/impact.md`
- Create: `skills/ba-cr/phases/apply.md`
- Create: `skills/dev-planner/phases/plan-one.md`
- Create: `skills/dev-executor/phases/execute-plan.md`
- Create: `skills/dev-code-review/phases/review-plan.md`

Phase files are short — they restate the agent's task in the dispatch context, with placeholders the orchestrator fills. They exist primarily so the SKILL.md stays small and prompt-cache friendly.

Each phase file follows this template:

```markdown
# Phase: <name>

This is the dispatch prompt for the `<agent-name>` subagent. The orchestrator passes the
filled-in version of this prompt when dispatching.

## Context to read first
<bullet list of stable inputs — schema, config>

## Your scope (this dispatch)
<placeholders the orchestrator fills>

## Task
<short restatement; refer to agent system prompt for full instructions>

## Return summary format
<exact key/value lines expected back>
```

- [ ] **Step 1: Create `skills/doc-ingest/phases/` directory and write `extract.md`**

```markdown
# Phase: extract

Dispatch prompt for `doc-ingest-extractor`.

## Read first
- `docs/implr/config/implr.config.yaml`

## Your scope
```
file_path: {{FILE_PATH}}
slug: {{SLUG}}
```

## Task
Extract text from `{{FILE_PATH}}` per the format rules in your system prompt. Write to
`docs/implr/kb-index/cache/{{SLUG}}.txt`. If the format is unsupported or extraction fails,
do not write a cache file; return the appropriate status.

## Return summary
```
slug: {{SLUG}}
cache_path: <path or empty>
word_count: <n>
status: extracted | unsupported | extraction_failed
error: <if extraction_failed>
```
```

- [ ] **Step 2: Write `skills/doc-ingest/phases/digest.md`**

```markdown
# Phase: digest

Dispatch prompt for `doc-ingest-digester`.

## Read first
- `docs/implr/schemas/kb-index-schema.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
slug: {{SLUG}}
cache_path: {{CACHE_PATH}}
source_path: {{SOURCE_PATH}}
domain: {{DOMAIN}}
```

## Task
Read `{{CACHE_PATH}}` and produce a per-doc digest at
`docs/implr/kb-index/digests/per-doc/{{SLUG}}-digest.md` per the schema. Determine
`arch_relevant` per the rules in your system prompt.

## Return summary
```
slug: {{SLUG}}
digest_path: <path>
digest_checksum: <sha256>
arch_relevant: true | auto | false
ambiguities_count: <n>
contradiction_signals: <n>
```
```

- [ ] **Step 3: Write `skills/doc-ingest/phases/synthesize-domain.md`**

```markdown
# Phase: synthesize-domain

Dispatch prompt for `doc-ingest-synthesizer`.

## Read first
- `docs/implr/schemas/kb-index-schema.md`

## Your scope
```
domain: {{DOMAIN}}
digests_glob: docs/implr/kb-index/digests/per-doc/*-digest.md
```

(The glob includes all per-doc digests; filter by reading each digest's `domain:` field
in frontmatter and keeping only those matching `{{DOMAIN}}`.)

## Task
Rebuild `docs/implr/kb-index/domains/{{DOMAIN}}-synthesis.md`. Detect intra-domain
contradictions, consolidate rules, surface ambiguities. Compute `synthesis_checksum`.

## Return summary
```
domain: {{DOMAIN}}
synthesis_path: <path>
synthesis_checksum: <sha256>
contradictions: <n>
ambiguities: <n>
nfr_candidates: <n>
arch_relevant_files: <n>
```
```

- [ ] **Step 4: Create `skills/arch-gen/phases/` and write `draft.md`**

```markdown
# Phase: draft

Dispatch prompt for `arch-drafter`.

## Read first
- `docs/implr/kb-index/master-synthesis.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
mode: {{MODE}}              # create | update
existing_path: {{EXISTING_PATH}}   # only when mode=update; else omit
confirmed_decisions:
{{DECISIONS_BLOCK}}
```

## Task
Produce a complete `docs/ARCHITECTURE.md` per the rules in your system prompt. Treat
confirmed decisions as authoritative.

## Return summary
```
arch_path: docs/ARCHITECTURE.md
mode: {{MODE}}
sections_written: <n>
decisions_applied: <n>
traceability_entries: <n>
```
```

- [ ] **Step 5: Create `skills/ba-requirements-gen/phases/` and write `domain.md`**

```markdown
# Phase: domain

Dispatch prompt for `requirements-domain-worker`.

## Read first
- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/config/implr.config.yaml`
- `docs/implr/config/DEV-STANDARDS.md`

## Your scope
```
domain: {{DOMAIN}}
synthesis_path: docs/implr/kb-index/domains/{{DOMAIN}}-synthesis.md
master_synthesis_path: docs/implr/kb-index/master-synthesis.md
cache_dir: docs/implr/kb-index/cache/
staging_dir: docs/implr/requirements/.staging/{{DOMAIN}}/
existing_reqs_index: docs/implr/requirements/requirements-index.md
mode: {{MODE}}                                # create | reprocess
reprocess_target: {{REPROCESS_TARGET}}        # only when mode=reprocess
```

## Task
Generate REQ files in `{{staging_dir}}` with slug-only filenames (no IDs). Leave `req_id`
empty — the orchestrator will fill it after all domain workers return.

## Return summary
```
domain: {{DOMAIN}}
files_written:
  - <staging path> (type: functional | non-functional, complexity: <X>)
functional_count: <n>
non_functional_count: <n>
open_questions: <n>
contradictions_flagged: <n>
```
```

- [ ] **Step 6: Create `skills/ba-cr/phases/` and write `impact.md`**

```markdown
# Phase: impact

Dispatch prompt for `cr-impact-analyzer`.

## Read first
- `docs/implr/schemas/cr-schema.md`
- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/schemas/plan-schema.md`

## Your scope
```
cr_path: {{CR_PATH}}
requirements_dir: docs/implr/requirements/
plans_dir: docs/implr/plans/
```

## Task
Analyse impact of the CR across all requirements and plans. Read-only.

## Return summary
(impact report per agent system prompt)
```

- [ ] **Step 7: Write `skills/ba-cr/phases/apply.md`**

```markdown
# Phase: apply

Dispatch prompt for `cr-applier`. One dispatch per affected target.

## Read first
- `docs/implr/schemas/cr-schema.md`
- The schema for your target (`requirement-schema.md` or `plan-schema.md`)

## Your scope
```
cr_path: {{CR_PATH}}
target_path: {{TARGET_PATH}}
target_kind: {{TARGET_KIND}}      # requirement | plan
action: {{ACTION}}                # patch | replan
status_change: {{STATUS_CHANGE}}
```

## Task
Apply the CR change exactly as described in the CR's `before`/`after` fields. Update
`source_docs` and `status` per scope.

## Return summary
(applier report per agent system prompt)
```

- [ ] **Step 8: Create `skills/dev-planner/phases/` and write `plan-one.md`**

```markdown
# Phase: plan-one

Dispatch prompt for `plan-worker`.

## Read first
- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
requirement_path: {{REQUIREMENT_PATH}}
plan_path_out: {{PLAN_PATH_OUT}}
mode: {{MODE}}                                # create | replan
existing_plan_path: {{EXISTING_PLAN_PATH}}    # only when mode=replan
existing_reqs_index: docs/implr/requirements/requirements-index.md
existing_plans_index: docs/implr/plans/plans-index.md
brainstorm_decisions:
{{DECISIONS_BLOCK}}
```

## Task
Produce one plan file per agent system prompt. Surface blockers; do not stub missing
dependency plans.

## Return summary
(plan-worker report per agent system prompt)
```

- [ ] **Step 9: Create `skills/dev-executor/phases/` and write `execute-plan.md`**

```markdown
# Phase: execute-plan

Dispatch prompt for `executor-worker`. One dispatch per plan in scope.

## Read first
- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Your scope
```
plan_path: {{PLAN_PATH}}
resume_task: {{RESUME_TASK}}    # empty if starting from the first task
```

## Task
Implement the plan task-by-task in order. Enforce TDD for `tdd_required: true` tasks.
Apply SOLID. Flag any manual action you cannot perform.

## Return summary
(executor-worker report per agent system prompt)
```

- [ ] **Step 10: Create `skills/dev-code-review/phases/` and write `review-plan.md`**

```markdown
# Phase: review-plan

Dispatch prompt for `code-review-worker`. One dispatch per plan in scope.

## Read first
- `docs/implr/schemas/review-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- Plan and requirement (paths in scope)

## Your scope
```
plan_path: {{PLAN_PATH}}
requirement_path: {{REQUIREMENT_PATH}}
review_path_out: {{REVIEW_PATH_OUT}}
src_path: src
tests_path: tests
```

## Task
Verify each AC, check architecture/SOLID/security, audit tests. Issue verdict per schema.

## Return summary
(review report per agent system prompt)
```

- [ ] **Step 11: Commit**

```bash
git add skills/*/phases/
git commit -m "feat(phases): add per-skill phase prompt files"
```

---

## Task 3: Update `implr-init` to scaffold agents directory and config block

**Files:**
- Modify: `skills/implr-init/SKILL.md` (add agents/ scaffolding and config injection)
- Modify: `skills/implr-init/assets/implr.config.yaml` (add commented `agents:` block)

- [ ] **Step 1: Inspect current implr-init assets**

```bash
ls skills/implr-init/assets/
```

Expected: at least `implr.config.yaml` and possibly schema/template subfolders. The agents are NOT shipped via implr-init — they live at the repo root in `.claude/agents/` and the installer copies them. implr-init only seeds config and project structure.

- [ ] **Step 2: Update `skills/implr-init/assets/implr.config.yaml` to include the agents section**

Append to the bottom of the existing seed file (preserve existing content):

```yaml

# Per-agent model selection for the orchestrator-subagent execution model (v2.0+).
# Values: haiku | sonnet | opus.
# Uncomment and edit any line to override an agent's default model.
# agents:
#   doc-ingest-extractor: haiku       # mechanical text extraction
#   doc-ingest-digester: sonnet       # per-doc digest
#   doc-ingest-synthesizer: sonnet    # per-domain synthesis
#   arch-drafter: sonnet              # architecture draft
#   requirements-domain-worker: sonnet
#   cr-impact-analyzer: sonnet
#   cr-applier: sonnet
#   plan-worker: sonnet
#   executor-worker: opus             # TDD + SOLID enforcement
#   code-review-worker: sonnet
```

- [ ] **Step 3: Update `skills/implr-init/SKILL.md` description to mention v2.0 agents**

Read the current file. Find the `description:` frontmatter field and tighten it. Replace with content along the lines of:

```
description: >
  Scaffolds the implr workspace under docs/implr/ in the current project. Seeds
  implr.config.yaml (incl. v2.0 agents: block, commented), DEV-STANDARDS.md (with SOLID
  baseline), schemas, templates, CLAUDE.md, and the change-requests folder. Idempotent.
  Note: .claude/agents/ is shipped by the installer, not by this skill.
```

(Aim for ≤ 4 lines in the description; the field is parsed every invocation.)

- [ ] **Step 4: Confirm the SKILL.md still treats `implr.config.yaml` as a write-only-if-absent file**

Skim the SKILL.md to verify it has the "do not overwrite if exists" guard for `implr.config.yaml`. If absent, add it explicitly with a one-line check.

- [ ] **Step 5: Commit**

```bash
git add skills/implr-init/
git commit -m "feat(implr-init): seed agents: config block for v2.0 (commented defaults)"
```

---

## Task 4: Update the three installer scripts to copy `.claude/agents/`

**Files:**
- Modify: `install.sh`
- Modify: `install.ps1`
- Modify: `install.bat`

- [ ] **Step 1: Read all three installer scripts to understand current copy logic**

```bash
cat install.sh install.ps1 install.bat
```

Identify the section that copies `skills/` → `.claude/skills/`. The agents copy follows the same pattern.

- [ ] **Step 2: Update `install.sh`**

After the block that copies `.claude/skills/`, add a block that copies `.claude/agents/`. The block should:
- Determine target dir: `.claude/agents/` (or `~/.claude/agents/` if `--global` was passed)
- `mkdir -p` the target
- `cp -r` the repo's `.claude/agents/*` to the target
- Always overwrite (agents are plugin-owned, like skills)
- Echo a line confirming the count of agents installed

Exact pattern: locate the `cp -r skills/ ...` style block and add a sibling block after it for agents. Reuse the same `--global` flag handling.

- [ ] **Step 3: Update `install.ps1`**

Add an equivalent PowerShell block after the skills copy. Use `Copy-Item -Recurse -Force` to overwrite. Echo confirmation.

- [ ] **Step 4: Update `install.bat`**

Add an equivalent CMD block. Use `xcopy /E /Y` (or `robocopy` if already used) to overwrite. Echo confirmation.

- [ ] **Step 5: Update the installer's printed help/option table** (any of the three that print options) to mention `.claude/agents/` is also installed.

- [ ] **Step 6: Verify installer copies don't touch `implr.config.yaml`** — re-skim each installer to confirm the config seed guard is intact (only seeds when missing). Should be unchanged from current; just verify.

- [ ] **Step 7: Smoke-test the installer locally**

```bash
# In a scratch directory:
mkdir /tmp/implr-smoke && cd /tmp/implr-smoke
/path/to/implr/install.sh
ls .claude/skills/ .claude/agents/
```

Expected: both directories populated; `.claude/agents/` contains the 10 agent files.

- [ ] **Step 8: Commit**

```bash
git add install.sh install.ps1 install.bat
git commit -m "feat(install): copy .claude/agents/ alongside .claude/skills/"
```

---

## Task 5: Rewrite `doc-ingest/SKILL.md` as orchestrator

**Files:**
- Modify: `skills/doc-ingest/SKILL.md` (full rewrite)

- [ ] **Step 1: Read the current `skills/doc-ingest/SKILL.md`**

Note the existing description, phases, parameter table, and post-report prompts. The orchestrator rewrite preserves the same external contract — phases 1, 2, 7, 8, 9 stay in skill; phases 3, 4, 5 dispatch.

- [ ] **Step 2: Replace `skills/doc-ingest/SKILL.md` with the orchestrator version**

Full file content:

```markdown
---
name: doc-ingest
description: >
  Indexes and digests the knowledge base under docs/kb/. Use when adding/updating docs,
  refreshing the KB index, or asking to ingest/scan/digest. Default in v2.0 is REGISTRY
  ONLY (fast). Pass --digest for full pipeline (digests + syntheses + master). Dispatches
  parallel subagents for extract, digest, and per-domain synthesis. Detects contradictions.
  Incremental — only reprocesses changed files.
---

# doc-ingest Skill (v2.0 orchestrator)

You orchestrate the knowledge-base ingest pipeline. Heavy work runs in dedicated subagents
(`doc-ingest-extractor`, `doc-ingest-digester`, `doc-ingest-synthesizer`). You decide scope,
dispatch in parallel, aggregate summaries, and write the index, master synthesis, and log.

## Read first (cache-friendly)

- `docs/implr/schemas/kb-index-schema.md`
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/doc-ingest` — registry only: scan, classify, write `index.md`. No digests, no syntheses.
- `/doc-ingest --digest` — full pipeline (extract + digest + syntheses + master).
- `/doc-ingest --file <path>` — process one file (registry only unless `--digest` also passed).
- `/doc-ingest --rebuild` — implies `--digest`; reprocesses everything from scratch.
- `/doc-ingest --dry-run` — report what would change; write nothing; log unchanged.

Removed in v2.0: `--no-digest` (now the default; flag is redundant).

## Model resolution

For each dispatch, resolve model from `agents.<agent-name>` in `implr.config.yaml`; fall
back to the agent's `default_model`.

## Execution

### Phase 1 — Scan

Recursively list `docs/kb/`. Capture path, format, domain (first subfolder or `root`),
mtime, md5. Use `find` + `md5sum` (POSIX) or equivalent.

### Phase 2 — Classify against `docs/implr/kb-index/index.md`

NEW / CHANGED / UNCHANGED / REMOVED / UNSUPPORTED per current schema. `--rebuild` forces
all supported to CHANGED. `--file` forces the named file to CHANGED.

### Phase 3 — Extract text (parallel `doc-ingest-extractor` dispatches)

For each NEW or CHANGED supported file, dispatch `doc-ingest-extractor` with scope
`{file_path, slug}`. Cap parallel dispatches at 5 per wave; sequence remainder into waves.

Read each return summary. If `status: extraction_failed`, log a warning and continue. If
`status: unsupported`, mark `format_supported: false` in the index entry.

### Phase 4 — Per-doc digest (parallel `doc-ingest-digester` dispatches)

**Skip entirely if `--digest` was not passed.**

For each successfully extracted file, dispatch `doc-ingest-digester` with scope
`{slug, cache_path, source_path, domain}`. Cap parallelism at 5.

Collect digest paths, checksums, `arch_relevant` flags.

### Phase 5 — Domain syntheses (parallel `doc-ingest-synthesizer` dispatches)

**Skip if `--digest` was not passed.**

Determine affected domains: any domain containing a NEW, CHANGED, or REMOVED file.

For each affected domain, dispatch `doc-ingest-synthesizer` with scope
`{domain, digests_glob}`. Cap parallelism at 5.

### Phase 6 — Master synthesis (orchestrator, integrative)

**Skip if `--digest` was not passed.**

If any domain synthesis changed (new `synthesis_checksum` differs from what
`master-synthesis.md` recorded), rebuild `docs/implr/kb-index/master-synthesis.md`
in-skill:
- System overview narrative
- Domain map table
- Cross-domain contradiction detection
- Global NFR candidates with frequency
- Complete arch-relevant file list
- Open ambiguities

### Phase 7 — Update `index.md`

Rewrite with current entries; preserve UNCHANGED entries; update CHANGED; add NEW;
remove REMOVED.

### Phase 8 — Update `digest-log.md` (skip if `--dry-run`)

Create with the documented header if absent. Prepend a run entry: timestamp, trigger,
mode, files processed with checksums/actions, domains rebuilt, master rebuild flag,
contradictions, warnings.

### Phase 9 — Report

```
📚 doc-ingest complete  (v2.0)
Scanned: {n}   New: {n}   Changed: {n}   Unchanged: {n}   Removed: {n}   Unsupported: {n}
Mode: registry-only | full
Digests: {n}   Domains rebuilt: {list}   Master: rebuilt | unchanged
Contradictions: {n} {one-line list}
Warnings: {any}
```

If invoked by another skill as a chained step, suppress the trailing guidance line and
keep the summary compact.

### Post-report prompts

Fire only for NEW files.

- New CR files (`docs/kb/change-requests/`): emit `⚠️ New change request: <file>. Run /ba-cr --file <path>`.
- New KB docs (outside change-requests) AND `requirements-index.md` exists non-empty:
  emit `💡 New KB document: <file>. If it changes existing requirements: /ba-cr --ingest-file <path>`.

## Incremental guarantees

- A file whose checksum matches the index is never re-extracted, re-digested, or re-read.
- A domain synthesis is rebuilt only when one of its source digests changed.
- The master synthesis is rebuilt only when a domain synthesis changed.
- `--dry-run` writes nothing and does not advance log state.

## Failure handling

- Missing extraction tool → register file, `format_supported: false`, warn, continue.
- Subagent dispatch returns `extraction_failed` → warn, continue, do not write index entry
  as supported.
- `index.md` unparseable → treat all files as NEW and rebuild, warn the user.
- Never leave index/digests/syntheses/log inconsistent. On partial write, report exactly
  what was and was not written.
```

- [ ] **Step 3: Commit**

```bash
git add skills/doc-ingest/SKILL.md
git commit -m "refactor(doc-ingest): rewrite as orchestrator dispatching extract/digest/synthesize subagents"
```

---

## Task 6: Rewrite `arch-gen/SKILL.md` as orchestrator

**Files:**
- Modify: `skills/arch-gen/SKILL.md` (full rewrite)

- [ ] **Step 1: Read current `skills/arch-gen/SKILL.md`** to preserve external contract.

- [ ] **Step 2: Replace with the orchestrator version**

```markdown
---
name: arch-gen
description: >
  Generates docs/ARCHITECTURE.md from the master synthesis. Interactive — confirms each
  inferred architectural decision with the user before dispatching the draft to the
  arch-drafter subagent. Use when asked to generate architecture, draft architecture,
  produce arch doc, refresh architecture.
---

# arch-gen Skill (v2.0 orchestrator)

You orchestrate ARCHITECTURE.md generation. You handle decision confirmation in the main
conversation, then dispatch the actual drafting to `arch-drafter`.

## Read first

- `docs/implr/kb-index/master-synthesis.md`  (stop if missing — tell user to run /doc-ingest --digest)
- `docs/implr/config/implr.config.yaml`
- `docs/implr/config/DEV-STANDARDS.md`

## Parameters

- `/arch-gen` — create (or, if `docs/ARCHITECTURE.md` exists, propose a diff for confirmation).
- `/arch-gen --update` — explicitly refresh existing ARCHITECTURE.md.
- `/arch-gen --dry-run` — show what would be produced; write nothing.

## Execution

### Phase 1 — Detect mode

If `docs/ARCHITECTURE.md` exists OR `--update` passed → `mode: update`. Else `mode: create`.

### Phase 2 — Identify inferred decisions

Read master synthesis and arch-relevant digests. Build a list of architectural decisions
where the synthesis is ambiguous or the user has not yet chosen. Examples:
- Service topology (monolith vs services)
- Data store choice (when synthesis mentions several)
- Authn/authz approach
- Event vs request-response patterns

### Phase 3 — Confirm decisions with the user (main context)

For each inferred decision, present it as:
```
Decision D{n}: <summary>
Options: <A>, <B>, ...
Inferred from: <source docs>
Your choice?
```

Collect all confirmations. If `--dry-run`, do not dispatch — list the decisions and stop.

### Phase 4 — Dispatch `arch-drafter`

Resolve model. Dispatch with scope:
```
mode: create | update
existing_path: docs/ARCHITECTURE.md     (only for update)
confirmed_decisions:
  - id: D1, summary: ..., choice: ...
  - id: D2, summary: ..., choice: ...
```

### Phase 5 — Optional human review

For `mode: update`: show the diff between existing and new before final write. Get
go-ahead.

### Phase 6 — Report

```
🏛  arch-gen complete  (v2.0)
Mode: create | update
Decisions confirmed: {n}
Sections written: {n}
Traceability entries: {n}
ARCHITECTURE.md at docs/ARCHITECTURE.md
```

## Failure handling

- No master synthesis → stop, tell user to run `/doc-ingest --digest`.
- Arch-drafter dispatch fails → report failure, leave existing file untouched.
```

- [ ] **Step 3: Commit**

```bash
git add skills/arch-gen/SKILL.md
git commit -m "refactor(arch-gen): rewrite as orchestrator dispatching arch-drafter"
```

---

## Task 7: Rewrite `ba-requirements-gen/SKILL.md` as orchestrator (with --ingest removal + post-hoc ID assignment)

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md` (full rewrite)

- [ ] **Step 1: Read current `skills/ba-requirements-gen/SKILL.md`** to preserve all non-flag behaviour.

- [ ] **Step 2: Replace with orchestrator version**

```markdown
---
name: ba-requirements-gen
description: >
  Generates functional and non-functional requirements from the digested knowledge base.
  Reads syntheses, dispatches one requirements-domain-worker subagent per in-scope domain
  in parallel, assigns sequential IDs after workers return, surfaces contradictions, writes
  REQ-F-* and REQ-N-* files. Removed in v2.0: --ingest and --ingest-file flags (run
  /doc-ingest --digest first). Triggers on: generate requirements, create requirements,
  ba requirements, analyse kb, requirements gen.
---

# ba-requirements-gen Skill (v2.0 orchestrator)

You orchestrate requirements generation. Per-domain analysis runs in parallel
`requirements-domain-worker` subagents writing slug-only files to a staging dir; you assign
sequential IDs and finalise after all workers return.

## Read first

- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/kb-index/master-synthesis.md`  (stop if missing — tell user to run /doc-ingest --digest)
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/ba-requirements-gen` — use existing syntheses; no ingest.
- `/ba-requirements-gen --domain <name>` — restrict to one domain.
- `/ba-requirements-gen --reprocess <doc>` — re-derive from a specific source doc (CR file
  supported).
- `/ba-requirements-gen --dry-run` — preview; write nothing; do not advance log state.

**Removed in v2.0** — produce this exact error and stop:

- `--ingest` →
  ```
  ❌ --ingest removed in v2.0.0. Run /doc-ingest --digest first, then /ba-requirements-gen.
  ```
- `--ingest-file <path>` →
  ```
  ❌ --ingest-file removed in v2.0.0. Run /doc-ingest --file <path> --digest first, then /ba-requirements-gen.
  ```

## Execution

### Phase 1 — Load state and determine scope

Read `requirements-log.md` (create with header if absent). Determine scope:
- `--domain <name>` → one domain
- `--reprocess <doc>` → infer domain from doc path; mode=reprocess
- Otherwise → domains whose synthesis checksum changed since last run, or all domains on
  first run

Read `requirements-index.md` for existing IDs and the highest REQ-F / REQ-N numbers.

### Phase 2 — Create staging area

```
docs/implr/requirements/.staging/
```

Clear any leftover staging from a previous failed run.

### Phase 3 — Dispatch `requirements-domain-worker` per domain (parallel)

For each in-scope domain, dispatch with scope `{domain, synthesis_path, master_synthesis_path,
cache_dir, staging_dir, existing_reqs_index, mode, reprocess_target}`. Cap parallelism at 5.

Each worker writes to `staging/<domain>/<slug>.md` (functional) or `staging/<domain>/n-<slug>.md`
(non-functional) with empty `req_id` fields.

### Phase 4 — Aggregate returns; collect contradictions and open questions

Sum functional_count, non_functional_count, open_questions, contradictions across all
worker returns.

If `contradictions_block: true` in config AND any contradictions present, halt and report
to user before any rename/move.

### Phase 5 — Post-hoc ID assignment

For each staged file:
- Read its frontmatter (type: functional or non-functional)
- Allocate next sequential `REQ-F-NNN` or `REQ-N-NNN` continuing from existing highest
- Rewrite `req_id:` field in the staged file
- Move to final path: `docs/implr/requirements/functional/REQ-F-NNN-<slug>.md` or
  `non-functional/REQ-N-NNN-<slug>.md`

All requirements are created with `status: draft`.

### Phase 6 — Updates to existing requirements

If a worker produced a file for a slug that already exists in the final tree (replan path,
or reprocess mode): merge per the existing rules:
- Additive (new AC, new field) or contradictory → drop status from approved to under-review
- Minor clarification → leave status approved
- If a plan exists for the requirement, append the post-implementation warning to
  `requirements-log.md`

### Phase 7 — Update `requirements-index.md`

Recount statistics, update tables, list requirements with unresolved open questions under
"Needs Human Review", maintain traceability matrix mapping each source doc to derived REQ
IDs.

### Phase 8 — Update `requirements-log.md` (skip if `--dry-run`)

Prepend a run entry per schema.

### Phase 9 — Optional coherence sweep

Dispatch the built-in `Explore` subagent (read-only) with scope:
"Cross-check the requirements at <paths> for unresolved cross-references, duplicated AC
sets, or dependency cycles. Report any issues; do not modify files."

Include findings in the report.

### Phase 10 — Report

```
✅ Requirements generation complete  (v2.0)
Domains processed: {list}
Requirements created: {n} ({f} functional, {nfr} non-functional)
Requirements updated: {n}
Open questions: {n} (incl. {c} contradictions)
Needs your review: {list of REQ ids}
Post-implementation updates: {list, if any}

Next steps:
  1. Review docs/implr/requirements/requirements-index.md
  2. Resolve open questions; set status: approved on ready requirements
  3. Run /dev-planner --all  (or /dev-planner REQ-F-NNN)
```

## Quality gate (enforced by each domain worker)

- Testable Desired Outcome
- ≥ 2 independently verifiable ACs
- ≥ 1 subtask
- ≥ 1 source doc referenced
- NFRs have a quantified Measurable Target
- Known contradictions captured as open questions
- ≥ 1 Out of Scope entry
- complexity and tdd_required set; dependencies populated with reasons

## Incremental guarantees

- A domain whose synthesis checksum is unchanged is not reprocessed (unless `--reprocess`).
- `--dry-run` writes nothing and does not advance log state.
- Existing requirements are updated in place (preserve req_id, created_at, jira, status).

## Tone

BA briefing a dev team: active voice, specific, testable, neutral on implementation, always
traceable.
```

- [ ] **Step 3: Commit**

```bash
git add skills/ba-requirements-gen/SKILL.md
git commit -m "refactor(ba-requirements-gen): orchestrator with parallel domain workers + post-hoc ID assignment; remove --ingest"
```

---

## Task 8: Rewrite `ba-cr/SKILL.md` as orchestrator

**Files:**
- Modify: `skills/ba-cr/SKILL.md` (full rewrite)

- [ ] **Step 1: Read current `skills/ba-cr/SKILL.md`** — note three trigger paths (CLI / --file / --ingest-file).

- [ ] **Step 2: Replace with orchestrator version**

```markdown
---
name: ba-cr
description: >
  Creates and applies Change Requests to amend requirements and plans. Interactive CLI
  interview to author a CR (or --file to apply an existing one, or --ingest-file to derive
  one from a new KB doc). Dispatches cr-impact-analyzer for read-only impact analysis,
  then parallel cr-applier subagents to apply diffs to affected requirements and plans
  after user approval.
---

# ba-cr Skill (v2.0 orchestrator)

You orchestrate the Change Request lifecycle. Interview happens in main; impact analysis
runs in `cr-impact-analyzer`; per-target application runs in parallel `cr-applier`s.

## Read first

- `docs/implr/schemas/cr-schema.md`
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/ba-cr` — interactive CLI interview; create a CR, analyse impact, chain updates on approval.
- `/ba-cr --file <path>` — apply a manually-authored CR file.
- `/ba-cr --ingest-file <path>` — ingest a new/updated KB document, auto-generate a CR from
  its digest, apply.
- `/ba-cr --impact-only <path>` — run impact analysis only; do not apply.
- `/ba-cr --dry-run` — preview impact + downstream changes; write nothing.

## Execution

### Phase 1 — Acquire the CR

Branch on the parameter:

**Interactive (no flag):** Run the CLI interview in the main context:
- What is the change? (one-line)
- Which requirements does it touch? (or "I'm not sure" → impact-analyzer will find out)
- Why is the change needed? (business / regulatory / technical)
- Before/after for each rule changed
- Acceptance criteria affected
- Risks / out of scope

Compose a CR file at `docs/kb/change-requests/CR-NNN-<slug>.md` per the schema. Allocate
the next sequential CR ID.

**`--file <path>`:** Read the file. Validate against schema. If invalid, report the
fields missing and stop.

**`--ingest-file <path>`:** Ensure the KB document has been ingested with `--digest`
(check `index.md`). If not, prompt the user to run `/doc-ingest --file <path> --digest`
first. Once ingested, read the digest, auto-generate a draft CR from its rule changes,
present to the user for review before continuing.

### Phase 2 — Dispatch `cr-impact-analyzer`

Resolve model. Dispatch with scope `{cr_path, requirements_dir, plans_dir}`.

Read the return summary. If `--impact-only`, print and stop.

### Phase 3 — Present impact and get approval

```
📋 CR-NNN impact:
Affected requirements: {list with change_kind, current_status → proposed_status}
Affected plans: {list with action: none/patch/replan}
New requirements proposed: {n}
Contradictions with existing: {n}
Risks: {n}

Approve and apply? (yes / no / impact-only)
```

If `--dry-run`, print and stop without dispatching appliers.

On `no`, stop. On `impact-only`, save the impact report to the CR file and stop.

### Phase 4 — Dispatch `cr-applier` per affected target (parallel)

For each affected requirement and each affected plan:
- Resolve model
- Dispatch `cr-applier` with scope `{cr_path, target_path, target_kind, action, status_change}`
- Cap parallelism at 5

### Phase 5 — Handle replan markers

For plans where the applier set `replan_required: true`, queue them. After all appliers
return, present the user with:
```
The following plans need replanning: {list}
Run /dev-planner --replan {list} now? (yes / no)
```

If yes, invoke `/dev-planner --replan` for each.

### Phase 6 — Update `cr-index.md` and `requirements-log.md`

Add the CR entry to `cr-index.md`. Append entries to `requirements-log.md` for each
affected requirement and to `plans-log.md` for each affected plan.

### Phase 7 — Report

```
✅ CR-NNN applied  (v2.0)
Title: ...
Affected: {f} requirements, {p} plans
Status changes: {summary}
Replan needed: {list of plans}
Open questions added: {n}
```

## Failure handling

- CR file invalid → stop with field list.
- Impact analyzer returns empty (no affected targets) → warn user; still allow apply for
  documentation purposes.
- Applier fails on one target → report which, leave others applied, do not roll back.
```

- [ ] **Step 3: Commit**

```bash
git add skills/ba-cr/SKILL.md
git commit -m "refactor(ba-cr): orchestrator with cr-impact-analyzer + parallel cr-applier dispatches"
```

---

## Task 9: Rewrite `dev-planner/SKILL.md` as orchestrator

**Files:**
- Modify: `skills/dev-planner/SKILL.md` (full rewrite)

- [ ] **Step 1: Read current `skills/dev-planner/SKILL.md`**.

- [ ] **Step 2: Replace with orchestrator**

```markdown
---
name: dev-planner
description: >
  Creates implementation plans from approved requirements. Dispatches one plan-worker
  subagent per requirement in parallel (dependent reqs sequenced into waves). Optional
  interactive --brainstorm phase runs in main before dispatch. Cross-requirement coherence
  sweep via built-in Explore subagent. Use when planning approved requirements.
---

# dev-planner Skill (v2.0 orchestrator)

You orchestrate plan generation. `--brainstorm` runs in main; per-requirement planning runs
in parallel `plan-worker` subagents respecting dependency waves.

## Read first

- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/dev-planner REQ-F-001` — plan one requirement.
- `/dev-planner REQ-F-001 REQ-F-002 REQ-N-001` — plan several (deps respected).
- `/dev-planner --all` — plan all approved requirements without a current plan. **Skips
  requirements that already have a plan** (per v1.x fix).
- `/dev-planner --replan REQ-F-001` — regenerate an existing plan (preserve plan_id).
- `/dev-planner --brainstorm REQ-F-001` — interactive design exploration before planning.
- `/dev-planner --dry-run REQ-F-001` — preview; write nothing.

## Execution

### Phase 1 — Resolve scope and validate

Read each requirement; verify `status: approved` (unless `require_approved_status: false`).
For `--all`, read `requirements-index.md` and pick approved reqs without an existing plan.

For each in-scope req, check dependencies — every required REQ must have an existing plan.
If not, mark blocked. Surface blockers up front.

### Phase 2 — Brainstorm (if `--brainstorm`)

Run interactive design exploration in main:
- Present 2–3 design options per significant decision
- Trade-offs explicit
- User picks
- Capture decisions as a structured list

### Phase 3 — Open-question batching

For each requirement with unresolved open questions, batch-prompt the user:
```
REQ-F-NNN has {n} open questions:
1. ...
2. ...
Resolve, or mark requirement blocked? (resolve / blocked)
```

Update requirement status if user marks blocked.

### Phase 4 — Compute dispatch waves

Build the dependency graph among in-scope reqs. Topological sort into waves where each
wave contains reqs whose dependencies are already planned.

### Phase 5 — Dispatch `plan-worker` per requirement (parallel within wave)

For each wave, dispatch all reqs in parallel (cap 5):

Scope per dispatch: `{requirement_path, plan_path_out, mode, existing_plan_path,
existing_reqs_index, existing_plans_index, brainstorm_decisions}`.

Wait for the wave to complete before dispatching the next wave.

Aggregate returns. Collect blockers, AC coverage stats, tasks counts.

### Phase 6 — Cross-requirement coherence sweep

Dispatch the built-in `Explore` subagent (read-only) with scope:
"Check plans at <paths> for: duplicate task definitions across plans, missing AC coverage,
inconsistent task ordering vs requirement dependencies."

Include findings in the report; do not modify plans.

### Phase 7 — Update `plans-index.md` and `plans-log.md`

Recount, update tables, add entries.

### Phase 8 — Report

```
🧭 dev-planner complete  (v2.0)
Plans created: {n}    Plans replanned: {n}
Waves dispatched: {n}
Blockers: {list}
Average AC coverage: {pct}
Cross-plan findings: {n}

Next steps:
  1. Review docs/implr/plans/plans-index.md
  2. Run /dev-executor --all  (or /dev-executor PLAN-F-NNN)
```

## Failure handling

- Requirement not approved → skip with warning unless explicitly named on command line.
- Plan-worker reports blockers → do not mark plan as ready; surface to user.
- Dependent plan missing → block the dependent requirement; do not stub.
```

- [ ] **Step 3: Commit**

```bash
git add skills/dev-planner/SKILL.md
git commit -m "refactor(dev-planner): orchestrator with wave-based parallel plan-worker dispatch"
```

---

## Task 10: Rewrite `dev-executor/SKILL.md` as orchestrator

**Files:**
- Modify: `skills/dev-executor/SKILL.md` (full rewrite)

- [ ] **Step 1: Read current `skills/dev-executor/SKILL.md`**.

- [ ] **Step 2: Replace with orchestrator**

```markdown
---
name: dev-executor
description: >
  Implements ready plans. Dispatches one executor-worker subagent (Opus by default — TDD
  and SOLID need strong model) per plan. Independent plans dispatched in parallel waves;
  tasks within each plan stay sequential inside the subagent. Use when implementing plans.
---

# dev-executor Skill (v2.0 orchestrator)

You orchestrate plan execution. Per-plan implementation runs in `executor-worker`
subagents. Plan dependencies define the execution waves.

## Read first

- `docs/implr/schemas/plan-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`

## Parameters

- `/dev-executor PLAN-F-001` — execute one plan.
- `/dev-executor PLAN-F-001 PLAN-F-002` — execute several in the given order (deps validated).
- `/dev-executor --all` — execute all `ready` plans in dependency order from `plans-index.md`.
- `/dev-executor --task PLAN-F-001 TASK-003` — execute a single task (resume).
- `/dev-executor --dry-run PLAN-F-001` — list files that would be created/modified.

## Execution

### Phase 1 — Resolve scope

Identify plans to execute. For `--all`, read `plans-index.md` and pick `status: ready`.
For named plans, validate they exist and are `ready`. For `--task`, locate the named task
inside the named plan.

### Phase 2 — Validate dependencies

For each plan, every dependent PLAN must be `status: done`. Block plans whose deps are not
done; report.

### Phase 3 — Compute execution waves

Topologically sort by plan dependencies. Each wave contains plans whose deps are done.

### Phase 4 — Dispatch `executor-worker` per plan (parallel within wave)

For each wave, dispatch all in-wave plans (cap 5):

Scope: `{plan_path, resume_task}` (`resume_task` empty for fresh plan execution).

Wait for wave completion before next wave.

For `--task` mode: single dispatch with `resume_task` set to the named task; do not run
subsequent tasks.

For `--dry-run`: do not dispatch; instead, read each plan and list files it would touch.

### Phase 5 — Aggregate returns

Collect: tasks completed, blocked, manual actions, files created/modified, test
pass/fail, plan status updates.

Update `plans-index.md` with new statuses. Append entries to `plans-log.md`.

### Phase 6 — Report

```
🛠  dev-executor complete  (v2.0)
Plans executed: {n}    Waves: {n}
Tasks completed: {n}    Tasks blocked: {n}
Files: +{n} new, ~{n} modified
Tests: {n} added, status: pass | fail
Manual actions required:
  - {list}

Next steps:
  1. Review changes in src/ and tests/
  2. Run /dev-code-review --all (or specific plans)
```

## Failure handling

- Plan not ready → skip with warning unless explicitly named.
- Executor-worker reports `tests_pass: false` → mark plan status `in-progress` (not `done`),
  report failing tests.
- Manual actions required → leave plan `in-progress`, surface to user.
- Worker returns blocked task → mark plan `in-progress` with the blocking task highlighted.
```

- [ ] **Step 3: Commit**

```bash
git add skills/dev-executor/SKILL.md
git commit -m "refactor(dev-executor): orchestrator with wave-based parallel executor-worker dispatch"
```

---

## Task 11: Rewrite `dev-code-review/SKILL.md` as orchestrator

**Files:**
- Modify: `skills/dev-code-review/SKILL.md` (full rewrite)

- [ ] **Step 1: Read current `skills/dev-code-review/SKILL.md`**.

- [ ] **Step 2: Replace with orchestrator**

```markdown
---
name: dev-code-review
description: >
  Reviews produced code per plan. Dispatches one code-review-worker subagent per plan in
  parallel. Each verifies acceptance criteria, checks architecture/SOLID/security, audits
  tests, and writes a review file. Use when asked to review built code.
---

# dev-code-review Skill (v2.0 orchestrator)

You orchestrate code review. Per-plan review runs in parallel `code-review-worker`
subagents in a fresh context per plan.

## Read first

- `docs/implr/schemas/review-schema.md`
- `docs/ARCHITECTURE.md`
- `docs/implr/config/DEV-STANDARDS.md`

## Parameters

- `/dev-code-review PLAN-F-001` — review one plan's output.
- `/dev-code-review PLAN-F-001 PLAN-F-002` — review several.
- `/dev-code-review --all` — review all `done` plans without a current review.

## Execution

### Phase 1 — Resolve scope

For named plans: validate they exist and are `status: done`.
For `--all`: read `plans-index.md`, pick `done` plans without an existing review file.

### Phase 2 — Dispatch `code-review-worker` per plan (parallel)

Cap parallelism at 5.

Per dispatch scope: `{plan_path, requirement_path, review_path_out, src_path, tests_path}`.

The review paths follow: `docs/implr/reviews/REVIEW-F-NNN-<slug>.md` (numbering matches the
plan).

### Phase 3 — Aggregate verdicts

Collect verdicts and finding counts by severity.

### Phase 4 — Update `reviews-index.md`

Add entry per review with verdict and severity counts.

### Phase 5 — Report

```
🔍 dev-code-review complete  (v2.0)
Reviews written: {n}
Verdicts:
  ✅ approved: {n}
  ⚠️  approved-with-warnings: {n}
  ❌ changes-required: {n}
  🚫 rejected: {n}
Findings totals:
  Critical: {n}   High: {n}   Medium: {n}   Low: {n}   Info: {n}

Blocks merge: {list of plan ids with Critical or High findings}
```

## Verdict rules (enforced by worker)

- Critical present → `rejected` (no recoverable path) or `changes-required` (if fixable)
- High present (no Critical) → `changes-required`
- Only Medium/Low/Info → `approved-with-warnings`
- No findings → `approved`

Critical and High findings block merge.
```

- [ ] **Step 3: Commit**

```bash
git add skills/dev-code-review/SKILL.md
git commit -m "refactor(dev-code-review): orchestrator with parallel code-review-worker dispatch"
```

---

## Task 12: Tighten `implr-init/SKILL.md` (description audit only)

**Files:**
- Modify: `skills/implr-init/SKILL.md` (description tightening)

- [ ] **Step 1: Read the current `skills/implr-init/SKILL.md` description** (already partially updated in Task 3).

- [ ] **Step 2: Audit the body for unnecessary verbosity**

The implr-init body should be roughly 200 lines. If there is repeated prose (e.g., the
same scaffolding rule restated in multiple phases), consolidate. Do not remove any
substitution target or rule.

Specific items to check and trim if found:
- Prose preamble before phases
- Multi-paragraph explanations where a single bullet would suffice
- Repeated reminders that files are idempotent

Keep all substitution targets, all rules, all phases.

- [ ] **Step 3: Commit if changes made**

```bash
git add skills/implr-init/SKILL.md
git commit -m "refactor(implr-init): trim verbose prose; preserve all rules and substitution targets"
```

If no trimming was warranted, skip the commit.

---

## Task 13: README.md major restructure

**Files:**
- Modify: `README.md` (major restructure per spec §"Documentation Updates")

- [ ] **Step 1: Read the current `README.md` fully** to identify content to preserve, update, or replace.

- [ ] **Step 2: Apply edits in the order below**

The README final section order is locked in the spec (sections 1–22). Apply the changes
in passes: update existing sections first, then insert new ones.

**Pass 1 — Update existing sections in place:**

- `## The Skills` table: update the description column for v2.0 changes (mention
  "orchestrator with parallel subagent dispatch" briefly for the heavy skills).
- `## Installation`: add a line after the "Note on skill packaging" paragraph stating that
  v2.0 ships `.claude/agents/` alongside `.claude/skills/`; both are copied by the installer.
- `## Updating implr`: change the "What the update does" table so the `.claude/skills/` row
  reads `Skills and agents (.claude/skills/, .claude/agents/) | Always replaced`. Add a
  one-line note: "v2.0 introduces `.claude/agents/` — re-run the installer to pick it up."
- `## Required Folder Structure`: update the diagram to show `.claude/agents/` next to
  `.claude/skills/`.
- `## Quick Start`: change the inside-Claude-Code block to:

  ```
  /doc-ingest --digest        # index + digest the KB (full pipeline)
  /arch-gen                   # generate docs/ARCHITECTURE.md (confirms inferred decisions)
  /ba-requirements-gen        # generate requirements from the syntheses
  # review docs/implr/requirements/requirements-index.md
  # resolve open questions, set status: approved on ready requirements
  /dev-planner --all          # plan all approved requirements
  /dev-executor --all         # implement all ready plans in dependency order
  /dev-code-review --all      # review everything that was built
  ```

- `## The Full Pipeline`: in step 3 (INGEST), change to "`/doc-ingest --digest` for full
  digests + syntheses; `/doc-ingest` alone for registry-only fast scan". In step 5
  (REQUIREMENTS), change command to `/ba-requirements-gen` (no `--ingest` mention).
- `## Skills Reference / ba-requirements-gen`: remove `--ingest` and `--ingest-file`
  bullets; add a one-line note pointing to "two-step flow: /doc-ingest --digest first".
- `## Skills Reference / doc-ingest`: change parameter list to match the v2.0 flag set.
- `## Configuration`: under the existing yaml example, add a NEW subsection
  `### Per-agent model selection (v2.0)` with the agents: block from the spec, plus a
  paragraph on resolution order.

**Pass 2 — Insert NEW sections at the correct positions:**

Insert after `## The Full Pipeline` and before `## Skills Reference`:

```markdown
## How You Interact With implr

implr's skills fall into three interaction modes:

- **Non-interactive** — you run the command and wait for the report. The skill never
  pauses to ask you a question.
- **Interactive** — the skill asks you to confirm or choose during the run.
- **Semi-interactive** — the skill is non-interactive by default but becomes interactive
  when invoked with a specific flag.

| Skill | Mode | When the skill asks for input |
|---|---|---|
| `implr-init` | Interactive | Project name, paths, stack hint — once at scaffold |
| `doc-ingest` | Non-interactive | Never |
| `arch-gen` | Interactive | Confirms each inferred architectural decision |
| `ba-requirements-gen` | Non-interactive | Never (open questions surfaced in files) |
| `ba-cr` | Interactive (default) / non-interactive (`--file`) | CLI interview without `--file`/`--ingest-file` |
| `dev-planner` | Non-interactive (default) / interactive (`--brainstorm`) | Design exploration if `--brainstorm` |
| `dev-executor` | Non-interactive | Never (manual actions flagged in report) |
| `dev-code-review` | Non-interactive | Never |

Regardless of skill, three **human gates** block the pipeline:

1. **Approve requirements** before planning — set `status: approved` on each REQ file you
   want planned. `dev-planner` skips draft/under-review/blocked requirements unless you
   explicitly name them.
2. **Approve CR impact** before applying — `ba-cr` shows the impact report and waits for
   your `yes`/`no`/`impact-only`.
3. **Resolve Critical/High findings** before merge — `dev-code-review` blocks merge on any
   Critical or High finding; lower severities pass with warnings.

Full state diagrams and edge cases in [WORKFLOW.md](docs/WORKFLOW.md).
```

Insert next (still before `## Skills Reference`):

```markdown
## Status Flows

implr tracks status on three artefacts: requirements, plans, and change requests. Below is
the short summary. The authoritative diagrams (including blocked branches and edge cases)
live in [WORKFLOW.md](docs/WORKFLOW.md).

### Requirements

```
            ┌────────────────────────────────────────────────┐
            │                                                ▼
draft ──► approved ──► under-review ──► approved        (blocked)
              │                                            ▲
              └────────────────────────────────────────────┘
              (when open questions cannot be resolved)
```

| Transition | Triggered by | Who |
|---|---|---|
| `draft → approved` | Human reviews the REQ file, resolves open questions, sets `status: approved` | You |
| `approved → under-review` | CR or `--reprocess` changes the requirement post-approval (additive/contradictory) | ba-cr / ba-requirements-gen |
| `under-review → approved` | Human re-reviews and re-approves | You |
| `* → blocked` | Open questions cannot be resolved; user marks blocked during dev-planner prompt | You |

### Plans

```
ready ──► in-progress ──► done
  ▲           │              │
  │           ▼              ▼
  └─── replan_required ◄─────┘  (via ba-cr)
```

| Transition | Triggered by | Who |
|---|---|---|
| `(none) → ready` | dev-planner writes a new plan for an approved requirement | dev-planner |
| `ready → in-progress` | dev-executor begins implementing the plan | dev-executor |
| `in-progress → done` | All tasks complete and tests pass | dev-executor |
| `done → replan_required` | A CR mandates plan changes | ba-cr → cr-applier |
| `replan_required → ready` | dev-planner --replan regenerates the plan | dev-planner |

### Change Requests

```
draft ──► impact-analysed ──► approved ──► applied
                │                  │
                └─► rejected ◄─────┘
```

Three entry paths produce a CR:

- **CLI** — `/ba-cr` runs an interview and writes the CR file
- **Manual file** — you author the CR file under `docs/kb/change-requests/`, then run
  `/ba-cr --file <path>`
- **KB document** — a new/changed KB doc; `/ba-cr --ingest-file <path>` derives the CR

| Transition | Triggered by | Who |
|---|---|---|
| `(none) → draft` | CR file created by one of the three paths | ba-cr or you |
| `draft → impact-analysed` | cr-impact-analyzer dispatched and returns report | ba-cr |
| `impact-analysed → approved` | You answer `yes` to the impact prompt | You |
| `impact-analysed → rejected` | You answer `no` | You |
| `approved → applied` | cr-applier dispatches finish on all affected targets | ba-cr |

Full diagrams (including replan loops and approval edge cases) in
[WORKFLOW.md](docs/WORKFLOW.md).
```

Insert under Configuration, after the `agents:` block addition:

```markdown
### Customising model tiers

Each subagent has a built-in `default_model`. Override per agent in
`docs/implr/config/implr.config.yaml`:

```yaml
agents:
  doc-ingest-digester: haiku        # downgrade for cheaper runs on simple KBs
  executor-worker: sonnet           # downgrade if you don't need Opus for TDD work
  requirements-domain-worker: opus  # upgrade for complex domains
```

Valid values: `haiku`, `sonnet`, `opus`. Omit a line to use the agent's built-in default.
The installer never overwrites `implr.config.yaml`, so your overrides survive plugin
updates.

Resolution order at dispatch time:
1. `agents.<agent-name>` from `implr.config.yaml`
2. `default_model` in `.claude/agents/<agent-name>.md`
```

Insert as a new section after `## Configuration`:

```markdown
## Performance & Token Efficiency

implr v2.0 separates orchestration from heavy lifting:

- **Skills are orchestrators** — they run in the main conversation, handle interactive
  questions, and dispatch heavy phases to subagents.
- **Subagents are dedicated workers** — they run in isolated contexts, with focused tool
  allowlists and tier-appropriate models (Haiku for mechanical text extraction, Sonnet
  for analysis, Opus reserved for TDD-discipline tasks).
- **Phase prompts live in companion files** — under `skills/<skill>/phases/`, so the
  SKILL.md stays small and prompt-cache friendly.
- **Stable reads first** — every skill and phase reads schemas and config before dynamic
  inputs, so Anthropic's 5-minute prompt cache reuses the prefix across calls.

Two flag changes also cut waste:
- `/doc-ingest` now defaults to a fast registry-only scan; pass `--digest` for the full
  synthesis pipeline.
- `--ingest` and `--ingest-file` were removed from `ba-requirements-gen`. Run
  `/doc-ingest --digest` (or `/doc-ingest --file <path> --digest`) first instead.

Typical end-to-end runs cost 3–4× fewer tokens than v1.x.
```

Insert as a new section before `## Troubleshooting`:

```markdown
## Migrating from v1.x to v2.0

1. Pull the latest implr: `git pull` in your local implr checkout.
2. Re-run the installer from your project root. It will copy `.claude/agents/` alongside
   `.claude/skills/` and refresh schemas/templates.
3. Replace `/ba-requirements-gen --ingest` invocations with two steps:
   `/doc-ingest --digest` then `/ba-requirements-gen`.
4. Replace `/ba-requirements-gen --ingest-file <path>` with
   `/doc-ingest --file <path> --digest` then `/ba-requirements-gen`.
5. Add `--digest` to any `/doc-ingest` invocation where you actually want digests +
   syntheses. Without `--digest`, the command now only refreshes the registry.
6. **(Optional)** Edit `docs/implr/config/implr.config.yaml` and uncomment any line in
   the `agents:` block to override model tiers.

Removed flags emit clear error messages pointing to the replacement command.
```

- [ ] **Step 3: Add a Troubleshooting entry**

In `## Troubleshooting`, add:

```markdown
**Agent not found at dispatch time.** Re-run the installer; `.claude/agents/` was added in
v2.0 and existing v1.x installs do not have it. Confirm `.claude/agents/<name>.md` exists
where `<name>` matches the error.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): v2.0 restructure — interaction modes, status flows, model tiers, migration"
```

---

## Task 14: Update `docs/WORKFLOW.md`

**Files:**
- Modify: `docs/WORKFLOW.md` (add Subagent Dispatch Model section; touch up CR flow)

- [ ] **Step 1: Read the current `docs/WORKFLOW.md` fully.**

- [ ] **Step 2: Add a new top-level section "Subagent Dispatch Model"**

Place it near the start (after any existing intro), before the per-skill state diagrams,
because the dispatch model is foundational to understanding the v2.0 flows.

```markdown
## Subagent Dispatch Model (v2.0)

Every skill in v2.0 is an **orchestrator** that runs in the main conversation context. It
handles user interaction (questions, confirmations) and dispatches heavy phases to
dedicated subagents.

### Which phases dispatch

| Skill | Phase | Subagent | Default model | Parallel? |
|---|---|---|---|---|
| doc-ingest | Phase 3 (extract) | doc-ingest-extractor | haiku | Yes (cap 5) |
| doc-ingest | Phase 4 (digest) | doc-ingest-digester | sonnet | Yes (cap 5) |
| doc-ingest | Phase 5 (domain synthesis) | doc-ingest-synthesizer | sonnet | Yes (cap 5) |
| arch-gen | Phase 4 (draft) | arch-drafter | sonnet | No (single dispatch) |
| ba-requirements-gen | Phase 3 (per-domain) | requirements-domain-worker | sonnet | Yes (cap 5) |
| ba-requirements-gen | Phase 9 (coherence) | Explore (built-in) | n/a | No |
| ba-cr | Phase 2 (impact) | cr-impact-analyzer | sonnet | No |
| ba-cr | Phase 4 (apply) | cr-applier | sonnet | Yes (cap 5) |
| dev-planner | Phase 5 (plan-one) | plan-worker | sonnet | Yes per wave (cap 5) |
| dev-planner | Phase 6 (coherence) | Explore (built-in) | n/a | No |
| dev-executor | Phase 4 (execute) | executor-worker | **opus** | Yes per wave (cap 5) |
| dev-code-review | Phase 2 (review) | code-review-worker | sonnet | Yes (cap 5) |

### Model override

Users override per agent in `docs/implr/config/implr.config.yaml` under the `agents:`
key. Values: `haiku`, `sonnet`, `opus`. Resolution: config value wins; falls back to the
agent's `default_model`.

### Why this saves tokens

- Heavy reads (cache files, digests, requirements bodies) happen inside subagent contexts,
  not in the main conversation.
- Subagents have focused system prompts (1–3K tokens vs the main agent's ~10K).
- Subagents run on cheaper model tiers where strong reasoning isn't required.
- Independent units dispatch in parallel — same wall-clock, lower per-token spend on
  cheaper tiers.
- Stable inputs (schemas, config) are read first in every dispatch, so Anthropic's 5-minute
  prompt cache reuses the prefix across dispatches within a session.

Typical savings: 3–4× tokens vs v1.x end-to-end.
```

- [ ] **Step 3: Update existing state flow sections (Requirements / Plans / CRs)**

The state transitions did not change. Only the *executor* of some transitions changed
(now a subagent dispatches the work). In each existing state-diagram section:
- Add a one-line note after the diagram: "*In v2.0, this transition is performed by the
  `<agent-name>` subagent dispatched by the `<skill>` orchestrator.*"
- Do not change the diagrams themselves.

- [ ] **Step 4: Update the CR section**

In the CR state flow section, after the diagram, add:

```markdown
*In v2.0, impact analysis is performed by `cr-impact-analyzer` (read-only); applying the
CR is performed by parallel `cr-applier` dispatches, one per affected requirement or plan.
The `ba-cr` skill orchestrates both.*
```

- [ ] **Step 5: Commit**

```bash
git add docs/WORKFLOW.md
git commit -m "docs(workflow): add Subagent Dispatch Model section; annotate state flows for v2.0"
```

---

## Task 15: Add v2.0.0 CHANGELOG entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Read current `CHANGELOG.md`** to match the formatting of recent entries.

- [ ] **Step 2: Prepend the v2.0.0 entry**

```markdown
## v2.0.0 — 2026-05-30

### Breaking changes
- **Removed `/ba-requirements-gen --ingest`.** Run `/doc-ingest --digest` first, then
  `/ba-requirements-gen`. Passing `--ingest` now emits a clear error pointing to the
  replacement command.
- **Removed `/ba-requirements-gen --ingest-file <path>`.** Run
  `/doc-ingest --file <path> --digest` first, then `/ba-requirements-gen`. Same error
  handling.
- **Flipped `/doc-ingest` default.** `/doc-ingest` now performs a fast registry-only scan;
  the full pipeline (digests + per-domain syntheses + master synthesis) requires
  `/doc-ingest --digest`.
- **Removed `/doc-ingest --no-digest`.** The flag is now redundant with the new default.

### New
- **`.claude/agents/`** ships with ten dedicated subagent definitions: doc-ingest-extractor,
  doc-ingest-digester, doc-ingest-synthesizer, arch-drafter, requirements-domain-worker,
  cr-impact-analyzer, cr-applier, plan-worker, executor-worker, code-review-worker. The
  installer copies them alongside `.claude/skills/`.
- **`skills/<skill>/phases/`** ships per-skill phase prompt files used as dispatch payloads.
- **`agents:` section in `implr.config.yaml`** — per-agent model override.
  Values: `haiku`, `sonnet`, `opus`. Omit a line to use the agent's built-in default.

### Changed
- All eight skills rewritten as **orchestrators** that dispatch heavy phases to dedicated
  subagents. Same external command surface (minus the removed flags), same outputs.
- Per-domain processing in `ba-requirements-gen` now runs in parallel
  `requirements-domain-worker` dispatches with post-hoc ID assignment.
- Per-plan execution in `dev-executor` now runs in parallel `executor-worker` dispatches
  (one per plan; tasks stay sequential inside).
- Per-plan review in `dev-code-review` now runs in parallel `code-review-worker`
  dispatches.

### Performance
- Typical end-to-end pipeline runs cost **3–4× fewer tokens** than v1.x, with no measurable
  quality loss on the default model assignments.

### Migration
- Re-run the installer. See `Migrating from v1.x to v2.0` in README.md.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): v2.0.0 — orchestrator+subagent execution model"
```

---

## Task 16: Update CONTRIBUTING.md

**Files:**
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Read current `CONTRIBUTING.md`**.

- [ ] **Step 2: Append two new sections**

```markdown
## Authoring a dedicated subagent (v2.0+)

Dedicated subagents live at `.claude/agents/<agent-name>.md`. Each is a Markdown file with
YAML frontmatter (the contract) and a Markdown body (the agent's system prompt).

### Frontmatter contract

```yaml
---
name: <agent-name>                   # MUST match filename without .md extension
description: <one-line role>         # Used by the Agent tool catalogue
tools: [Read, Write, Bash, ...]      # Allowlist of tools the agent may call
default_model: haiku|sonnet|opus     # Used when implr.config.yaml does not override
---
```

### Authoring guidance

- **One job per agent.** If your agent has two unrelated phases, split it into two.
- **Restrict tools.** Workers that only read should not have Write. Workers that produce
  one file should not have Bash unless the format requires it.
- **Pick the right tier.** Haiku for mechanical extraction/formatting. Sonnet for analytic
  work (digest, synthesis, review). Opus only when judgement under discipline matters
  (TDD, SOLID enforcement).
- **Stable reads first.** The agent body must instruct the agent to read schemas, config,
  and standards BEFORE reading the dynamic input. This is what makes the 5-minute prompt
  cache work across dispatches.
- **Return structured summaries.** Use plain-text `key: value` lines, one per line, so the
  orchestrator can parse without regex gymnastics. List the exact keys in the agent body.

### How orchestrators dispatch

The skill's SKILL.md is the orchestrator. It reads `agents.<agent-name>` from
`implr.config.yaml`, falls back to the agent's `default_model`, and calls the `Agent` tool
with `subagent_type`, `model`, and a small scope payload (e.g. a file path or a requirement
id). The full phase instructions live in `skills/<skill>/phases/<phase>.md`.

## Prompt-cache-friendly ordering

Every SKILL.md and every `phases/*.md` must read stable inputs (schemas, config files)
before dynamic inputs (the file being processed, the requirement being planned, etc.).

This convention exists because Anthropic's 5-minute prompt cache reuses the conversation
prefix across calls. If a skill or phase reads dynamic content first, the cache key
diverges immediately and the prefix isn't reused. The hit is measurable on sessions with
many dispatches.

Pattern:

```markdown
## Read first (cache-friendly)
- docs/implr/schemas/<relevant-schema>.md
- docs/implr/config/implr.config.yaml
- docs/implr/config/DEV-STANDARDS.md  (if behavioural)

## Your scope (dynamic — from the orchestrator)
...

## Task
...
```

## Phase prompt files

Each heavy skill has a `phases/` subfolder. Each file is the dispatch prompt template the
orchestrator sends to a subagent.

- File path: `skills/<skill>/phases/<phase-name>.md`
- Naming: short verb or noun (`extract`, `digest`, `plan-one`, `apply`).
- Content: stable-reads-first block, scope block (with `{{PLACEHOLDERS}}` the orchestrator
  fills), task block, return summary block.

Phase files exist primarily to keep SKILL.md small and prompt-cache friendly. The
authoritative task instructions still live in the agent's system prompt body; the phase
file is the orchestration handle.
```

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs(contributing): add subagent authoring + prompt-cache + phase file conventions"
```

---

## Task 17: Smoke validation on a sample KB

**Files:** none modified — verification only.

- [ ] **Step 1: Verify the spec validation checklist**

Open `docs/superpowers/specs/2026-05-30-implr-token-optimization-design.md` § Validation /
Quality Gates. Walk through each checkbox manually:

- [ ] All ten agent files exist at `.claude/agents/<name>.md` with correct frontmatter.
- [ ] All ten phase files exist at `skills/<skill>/phases/<phase>.md`.
- [ ] Each rewritten SKILL.md is ≤ 100 lines of orchestrator content (frontmatter + body).
      Count with `wc -l skills/*/SKILL.md`.
- [ ] Each SKILL.md reads stable inputs (schema/config) before dynamic inputs. Scan each
      file's "Read first" block — it must precede any dispatch instructions.
- [ ] `--ingest`, `--ingest-file`, `--no-digest` produce the documented error strings —
      grep each removed flag and confirm an error string referencing v2.0.0 is present.

```bash
grep -n "v2.0.0" skills/ba-requirements-gen/SKILL.md skills/doc-ingest/SKILL.md
```

- [ ] **Step 2: Manually verify installer copies `.claude/agents/`**

```bash
mkdir -p /tmp/implr-v2-smoke && cd /tmp/implr-v2-smoke
/path/to/implr/install.sh
ls -la .claude/agents/
```

Expected: 10 files, each starting with the documented frontmatter (first three lines
include `---`, `name:`, `description:`).

- [ ] **Step 3: Verify implr.config.yaml seed contains agents block**

```bash
cd /tmp/implr-v2-smoke
grep -A 15 "^# agents:" docs/implr/config/implr.config.yaml || \
  grep -A 15 "^agents:" docs/implr/config/implr.config.yaml
```

Expected: the commented `agents:` block with all 10 default tiers shown.

- [ ] **Step 4: Documentation cross-references resolve**

Open README.md and check every `[link](docs/WORKFLOW.md)` and `[link](CHANGELOG.md)`
target. Each link must resolve. Run:

```bash
grep -n "](.*\.md" README.md
```

For each link, confirm the file exists at the path.

- [ ] **Step 5: Skill descriptions are ≤ 4 lines each (token efficiency)**

```bash
for f in skills/*/SKILL.md; do
  echo "=== $f ==="
  awk '/^description: >/,/^[a-z_]+:/' "$f" | head -10
done
```

Verify each description body is concise (3–4 lines of prose, not 8+).

- [ ] **Step 6: No reference to removed flags in user-facing docs (except CHANGELOG and migration)**

```bash
grep -rn -- "--ingest\b" README.md docs/WORKFLOW.md skills/ \
  | grep -v "removed in v2.0" \
  | grep -v "CHANGELOG"
```

Expected output: empty (no lingering documentation telling users to use `--ingest`).

Hits are acceptable only where the context is the migration/removal documentation itself.

- [ ] **Step 7: Commit any documentation fixes uncovered**

If smoke validation surfaces inconsistencies, fix them in their respective files and
commit:

```bash
git add <fixed-files>
git commit -m "docs: fix v2.0 reference inconsistencies surfaced in smoke validation"
```

---

## Task 18: Version bump and final integration commit

**Files:**
- Check: any `package.json`, `pyproject.toml`, or version file at repo root for version
  string.

- [ ] **Step 1: Search for a version string**

```bash
grep -rn "1\.2\.0" --include="*.json" --include="*.toml" --include="*.yaml" --include="*.md" .
```

implr v1.2.0 was the previous release. Identify any file declaring the version.

- [ ] **Step 2: Update version strings to `2.0.0`**

Wherever `1.2.0` appears as the implr version, replace with `2.0.0`. Use Edit per file.
Skip third-party version strings unrelated to implr.

- [ ] **Step 3: Final commit**

```bash
git add <version-files>
git commit -m "chore: bump version to 2.0.0"
```

- [ ] **Step 4: Tag**

```bash
git tag -a v2.0.0 -m "v2.0.0 — orchestrator + subagent execution model; 3–4× token reduction"
```

Do not push the tag automatically. Surface the tag to the user with the command they need
to push it (`git push origin v2.0.0`) so they remain in control of release timing.

---

## Self-Review Notes

Performed after writing the plan, before handoff.

**1. Spec coverage:** Every section of the spec maps to at least one task:
- Spec §"Architecture" → Tasks 1, 2, 5–11
- Spec §"Per-Skill Changes" → Tasks 5–12
- Spec §"Configuration" → Task 3 (config seed), Tasks 5–11 (resolution logic in each
  orchestrator)
- Spec §"Breaking Changes" → Tasks 5 (doc-ingest) and 7 (ba-requirements-gen)
- Spec §"Documentation Updates" → Tasks 13–16
- Spec §"Validation / Quality Gates" → Task 17
- Spec §"Risks" mitigations: parallelism cap (covered in dispatch convention at top of
  plan); fallback paths (covered in failure-handling blocks in each orchestrator)

**2. Placeholder scan:** No `TBD`, `TODO`, `implement later`, or `add appropriate error
handling` instances. Each step has concrete content.

**3. Type consistency:**
- Agent names match between frontmatter, phase files, dispatch calls, and orchestrator
  references.
- The `status_change` field used in `cr-applier` matches what the orchestrator computes
  from `cr-impact-analyzer` output (both refer to requirement/plan status transitions).
- The `staging_dir` path is consistent across `requirements-domain-worker` and
  `ba-requirements-gen` orchestrator (`docs/implr/requirements/.staging/<domain>/`).
- `plan_path_out` naming consistent between `plan-worker` agent body and the
  `plan-one.md` phase file.

No inconsistencies surfaced.
