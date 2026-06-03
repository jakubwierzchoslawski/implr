# doc-ingest Inline Extraction + ba-requirements-gen Envelope Pattern — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate two distinct token-waste patterns that survived v3.0: (1) `doc-ingest-extractor` dispatches a full LLM subagent to mechanically copy file bytes into the cache; (2) every `requirements-domain-worker` cold-starts by re-reading the schema, config, and DEV-STANDARDS — paying the v2-style stable-context tax that `task-executor` already escaped via inline envelopes.

**Architecture:** Two parallel fixes sharing one v3 pattern. (1) Move all KB extraction inline into the `doc-ingest` skill orchestrator using direct shell commands; delete the extractor agent. (2) Introduce a `requirements-card.md` (analog of the existing `standards-card.md`), build a per-domain envelope in `ba-requirements-gen` containing all stable + per-domain content inline, and strip the worker's "Read first" block — mirroring the `task-executor` envelope contract introduced in v3.0.

**Tech Stack:** Markdown skill/agent prompts; PowerShell/Bash/Batch installer scripts; YAML config. No application code — the plugin IS prompts.

**Verification model:** This plugin has no unit tests. Each task's verification is one of (a) re-read the modified file and confirm structural assertions; (b) run installer end-to-end against a scratch directory; (c) end-of-plan smoke run of `/doc-ingest` and `/ba-requirements-gen` on a representative input.

---

## File Structure

### New files
| Path | Purpose |
|---|---|
| `scaffold/templates/requirements-card-template.md` | Skeleton for the auto-generated requirements card |

### Modified files
| Path | Change |
|---|---|
| `skills/doc-ingest/SKILL.md` | Phase 3 rewritten to do extraction inline; extractor dispatch removed; phase numbering preserved |
| `.claude/agents/doc-ingest-digester.md` | Input schema clarified: cache path is `.txt` (was `.md`); no behavioural change |
| `skills/implr-init/SKILL.md` | Step 5 generates `requirements-card.md`; `--refresh-card` regenerates both cards |
| `.claude/agents/requirements-domain-worker.md` | Drop "Read first"; accept inline envelope; same output contract |
| `skills/ba-requirements-gen/SKILL.md` | Phase 3 builds inline envelope (read stable files once); pass to workers |
| `install.ps1` | Workspace install ensures `requirements-card-template.md` reaches `docs/implr/templates/` |
| `install.sh` | Same |
| `install.bat` | Same |
| `README.md` | Document the two changes under "What's new in this minor version" |
| `docs/WORKFLOW.md` | Update dispatch chart: extractor agent removed; envelope flow extends to requirements |

### Deleted files
| Path | Reason |
|---|---|
| `.claude/agents/doc-ingest-extractor.md` | Replaced by inline extraction in `doc-ingest` skill |

---

## Task 1: Inline extraction in `doc-ingest` skill (Phase 3 rewrite)

**Files:**
- Modify: `skills/doc-ingest/SKILL.md`

- [ ] **Step 1: Re-read current Phase 3 block**

Read `skills/doc-ingest/SKILL.md` lines 53–62 (Phase 3) to confirm the exact current wording before editing.

- [ ] **Step 2: Replace Phase 3 with inline extraction logic**

Find the Phase 3 block exactly as it stands:

```
### Phase 3 — Extract text (parallel `doc-ingest-extractor` dispatches)

For each NEW or CHANGED supported file, compute the slug (kebab-cased filename without
extension; if two files share a filename across domains, append a 6-char hex hash of the
relative path for disambiguation). Then dispatch `doc-ingest-extractor` with scope
`{file_path, slug}`. Cap parallel dispatches at 5 per wave; sequence remainder into waves.

Read each return summary. If `status: extraction_failed`, log a warning and continue. If
`status: unsupported`, mark `format_supported: false` in the index entry.
```

Replace with:

````
### Phase 3 — Extract text (inline in the orchestrator)

For each NEW or CHANGED file, compute the slug (kebab-cased filename without extension; if
two files share a filename across different domains, append a 6-char hex hash of the
relative path for disambiguation).

Then write `docs/implr/kb-index/cache/<slug>.txt` by running the appropriate command for
the file's extension. The orchestrator runs these inline via `Bash`; no subagent is
dispatched. File content never enters an LLM context window during extraction.

| Ext | Command (POSIX) | Command (PowerShell) |
|---|---|---|
| md, txt, csv, vtt | `cp "<src>" "docs/implr/kb-index/cache/<slug>.txt"` | `Copy-Item -LiteralPath "<src>" -Destination "docs\implr\kb-index\cache\<slug>.txt" -Force` |
| pdf | `pdftotext "<src>" "docs/implr/kb-index/cache/<slug>.txt"` (fallback: `python3 -c "import pymupdf; doc=pymupdf.open('<src>'); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write('\n'.join(p.get_text() for p in doc))"`) | same; use `python` on Windows if `python3` is absent |
| docx | `python3 -c "from docx import Document; d=Document('<src>'); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write('\n'.join(p.text for p in d.paragraphs))"` | same with `python` |
| xlsx | `python3 -c "from openpyxl import load_workbook; wb=load_workbook('<src>', data_only=True); out=open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8'); [out.write(f'## {s.title}\n' + '\n'.join('\t'.join('' if c is None else str(c) for c in r) for r in s.iter_rows(values_only=True)) + '\n') for s in wb.worksheets]; out.close()"` | same with `python` |
| anything else | Do not extract. Mark the index entry `format_supported: false`. Skip Phase 4 for this file. |

Cap parallel `Bash` calls at 5 (one wave at a time per file batch). Sequence the remainder
into subsequent waves.

If a command exits non-zero OR the required tool is missing, log a warning of the form
`extract-failed: <file_path> — <error one-liner>` and continue with the next file. Do not
write a partial cache file (delete it if a partial was produced). Do not write an index
entry as `format_supported: true` for that file.

Detect missing tools BEFORE the first invocation by probing once per run:
- `pdftotext -v` (or `python3 -c "import pymupdf"` as fallback) — required only when pdf files are in scope
- `python3 -c "import docx"` — required only when docx files are in scope
- `python3 -c "import openpyxl"` — required only when xlsx files are in scope

If a probe fails, emit one warning per format and skip all files of that format with
`format_supported: false`. Do not re-probe per file.
````

- [ ] **Step 3: Drop the model-resolution line for extractor in this skill**

Find the `## Model resolution` section. It currently says:

```
For each dispatch, resolve model from `agents.<agent-name>` in `implr.config.yaml`; fall
back to the agent's `default_model`.
```

Leave the section but append:

```

Phase 3 extraction is inline (no subagent), so no model is resolved for it. Phases 4–5
still dispatch `doc-ingest-digester` and `doc-ingest-synthesizer`.
```

- [ ] **Step 4: Verify the skill file**

Re-read `skills/doc-ingest/SKILL.md`. Confirm:
- No occurrence of the string `doc-ingest-extractor` anywhere in the file.
- The string `Phase 3 — Extract text (inline in the orchestrator)` appears once.
- Phase numbering 1, 2, 3, 4, 5, 6, 7, 8, 9 is intact.

Run (PowerShell):
```powershell
Select-String -Path skills\doc-ingest\SKILL.md -Pattern "doc-ingest-extractor"
```
Expected: no matches.

Run (PowerShell):
```powershell
Select-String -Path skills\doc-ingest\SKILL.md -Pattern "Phase \d "
```
Expected: nine matches, in order Phase 1 through Phase 9.

- [ ] **Step 5: Commit**

```bash
git add skills/doc-ingest/SKILL.md
git commit -m "feat(doc-ingest): inline KB extraction; remove extractor subagent dispatch"
```

---

## Task 2: Delete the `doc-ingest-extractor` agent file

**Files:**
- Delete: `.claude/agents/doc-ingest-extractor.md`

- [ ] **Step 1: Confirm no remaining references**

Run (PowerShell):
```powershell
Select-String -Path .\skills,.claude\agents -Pattern "doc-ingest-extractor" -Recurse
```
Expected: no matches (Task 1 already removed them from the SKILL).

If matches appear, fix the referring file before deleting the agent.

- [ ] **Step 2: Delete the agent file**

```powershell
Remove-Item -LiteralPath .claude\agents\doc-ingest-extractor.md -Force
```

POSIX equivalent: `rm -f .claude/agents/doc-ingest-extractor.md`.

- [ ] **Step 3: Verify**

Run (PowerShell):
```powershell
Test-Path .claude\agents\doc-ingest-extractor.md
```
Expected: `False`.

- [ ] **Step 4: Commit**

```bash
git add -A .claude/agents/
git commit -m "chore(agents): remove doc-ingest-extractor (replaced by inline extraction)"
```

---

## Task 3: Clean digester input-schema doc-bug (cache extension)

**Files:**
- Modify: `.claude/agents/doc-ingest-digester.md`

- [ ] **Step 1: Fix the cache path extension in Inputs**

Open `.claude/agents/doc-ingest-digester.md`. Find:

```
cache_path: docs/implr/kb-index/cache/<slug>.md
```

Replace with:

```
cache_path: docs/implr/kb-index/cache/<slug>.txt
```

Rationale: the cache writer (formerly extractor, now inline) has always written `.txt`. The digester schema string is the only place still saying `.md`. No behavioural change — the orchestrator passes the actual path on dispatch.

- [ ] **Step 2: Verify**

Run (PowerShell):
```powershell
Select-String -Path .claude\agents\doc-ingest-digester.md -Pattern "cache/<slug>\.md"
```
Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/doc-ingest-digester.md
git commit -m "docs(digester): align cache_path extension to .txt (matches extraction output)"
```

---

## Task 4: Create `requirements-card-template.md`

**Files:**
- Create: `scaffold/templates/requirements-card-template.md`

- [ ] **Step 1: Write the template**

Create `scaffold/templates/requirements-card-template.md` with this exact content:

```markdown
# Requirements Card

> AUTO-GENERATED from docs/implr/schemas/requirement-schema.md + docs/implr/config/DEV-STANDARDS.md by /implr-init.
> Do not edit by hand — run `/implr-init --refresh-card` to regenerate.
> Read by: requirements-domain-worker.
> Full schema (with examples) lives in requirement-schema.md.
> Full standards live in DEV-STANDARDS.md.

## Frontmatter — required fields (orchestrator fills `req_id`)
slug · title · type (functional | non-functional)
status: draft · complexity: XS|S|M|L|XL · tdd_required (derived)
source_docs[] · dependencies[{id, reason}] · created_at · updated_at

## Complexity → tdd_required
XS, S → false   |   M, L, XL → true (overridable per-requirement)
Effective threshold per project: {{TDD_THRESHOLD}} (everything at or above is TDD)

## Non-functional additions (when type = non-functional)
nfr_category: Performance | Security | Scalability | Reliability | Maintainability | Usability | Compliance | Observability
Body MUST include: `### Measurable Target` (quantified), `### Verification Method`, `### Category Rationale`

## Section order (canonical)
Frontmatter → `# {req_id} — {Title}` → `## Domain Context` → `## Summary` →
`## Detailed Description` → `## Desired Outcome` → `## Acceptance Criteria` →
`[## Acceptance Notes]` → `## Out of Scope` → `[## Open Questions]` →
`## Data Models` → `## Process Sequence` → `## Subtasks` →
`[## NFR-Specific Fields]` (only when type=non-functional) →
`## Source Document References`

## Optional sections — OMIT entirely when empty
`## Acceptance Notes` · `## Open Questions`
`## Data Models` — emit `N/A` OR omit
`## Process Sequence` — emit `N/A` OR omit

## Quality gate (fail the requirement if any miss)
- Testable Desired Outcome
- ≥ 2 independently verifiable ACs
- ≥ 1 subtask
- ≥ 1 source doc referenced
- NFRs: quantified Measurable Target with metric + value + conditions
- ≥ 1 Out of Scope entry
- complexity + tdd_required set; dependencies populated with reasons
- Deferred contradictions → Open Questions; resolved contradictions → authoritative content (never Open Questions)

## NFR baselines (apply when deriving NFRs from synthesis)
Security: validate at boundary; never log secrets / tokens / PII / payment data; parameterised queries only; auth required by default on endpoints; rate-limit public mutation endpoints; bcrypt/argon2 cost ≥ 10; no stack traces to clients; verify resource ownership (IDOR).
Performance: state quantified p50/p95/p99 targets when present in source; otherwise mark for human input as an Open Question.
Testing: TDD enforced when tdd_required=true. Unit tests for services/validators/transformers; integration tests for repos/endpoints; E2E only on critical journeys.

## Tone
BA briefing a dev team: active voice, specific, testable, neutral on implementation,
always traceable to a source document.
```

- [ ] **Step 2: Verify**

Run (PowerShell):
```powershell
Test-Path scaffold\templates\requirements-card-template.md
(Get-Content scaffold\templates\requirements-card-template.md | Measure-Object -Line).Lines
```
Expected: `True`, and line count in the 45–60 range.

Run (PowerShell):
```powershell
Select-String -Path scaffold\templates\requirements-card-template.md -Pattern "\{\{TDD_THRESHOLD\}\}"
```
Expected: exactly one match.

- [ ] **Step 3: Commit**

```bash
git add scaffold/templates/requirements-card-template.md
git commit -m "feat(templates): add requirements-card-template for envelope dispatch"
```

---

## Task 5: Update `implr-init` to generate `requirements-card.md`

**Files:**
- Modify: `skills/implr-init/SKILL.md`

- [ ] **Step 1: Update the `--refresh-card` description**

In the parameters table near the top of `skills/implr-init/SKILL.md`, find the row:

```
| `/implr-init --refresh-card` | Regenerate `docs/implr/config/standards-card.md` ONLY from current `docs/implr/config/DEV-STANDARDS.md` — no questions re-asked |
```

Replace with:

```
| `/implr-init --refresh-card` | Regenerate `docs/implr/config/standards-card.md` AND `docs/implr/config/requirements-card.md` from current `docs/implr/config/DEV-STANDARDS.md` and `docs/implr/config/implr.config.yaml` — no questions re-asked |
```

- [ ] **Step 2: Update the "Refresh-card-only mode" block**

Find the "Refresh-card-only mode" section. Locate the numbered list step `2`:

```
2. Run Step 5 only (generate `docs/implr/config/standards-card.md`) using these extracted values.
```

Replace with:

```
2. Additionally read `docs/implr/config/implr.config.yaml` and extract
   `behaviour.default_tdd_threshold` (treat the literal token after the colon, stripping
   inline comments and whitespace).

3. Run Step 4 (generate `docs/implr/config/standards-card.md`) and Step 5 (generate
   `docs/implr/config/requirements-card.md`) using these extracted values. Skip Step 1
   (no questions) and Step 2 (no source subdirectories).
```

And update the existing step `3` "Print" line to step `4`, and step `4` "Stop" to step `5`. Final section should read:

```
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
```

- [ ] **Step 3: Renumber Step 4 → Step 4 (standards-card), and insert new Step 5 (requirements-card)**

Find the section currently titled `## Step 4 — Generate standards-card` and leave it AS IS (already correct). Then find `## Step 5 — Report` and INSERT a new section before it:

```
## Step 5 — Generate requirements-card

1. Read `docs/implr/templates/requirements-card-template.md`.

2. Substitute placeholders:

   | Placeholder | Value |
   |-------------|-------|
   | `{{TDD_THRESHOLD}}` | answer 5 (or `default_tdd_threshold` extracted in refresh-card mode) |

3. Write the result to `docs/implr/config/requirements-card.md`. ALWAYS overwrite — this
   file is auto-managed and must never be hand-edited.

---
```

- [ ] **Step 4: Renumber `## Step 5 — Report` to `## Step 6 — Report` and extend the Report block**

Find:

```
## Step 5 — Report
```

Replace with:

```
## Step 6 — Report
```

Inside that report block, find:

```
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  CLAUDE.md
  docs/implr/config/standards-card.md   (auto-generated; do not hand-edit)
```

Replace with:

```
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  CLAUDE.md
  docs/implr/config/standards-card.md       (auto-generated; do not hand-edit)
  docs/implr/config/requirements-card.md    (auto-generated; do not hand-edit)
```

- [ ] **Step 5: Verify**

Run (PowerShell):
```powershell
Select-String -Path skills\implr-init\SKILL.md -Pattern "## Step \d "
```
Expected: six matches in order — Step 1, Step 2, Step 3, Step 4, Step 5, Step 6.

Run (PowerShell):
```powershell
Select-String -Path skills\implr-init\SKILL.md -Pattern "requirements-card"
```
Expected: at least five matches (param row, refresh-card list, Step 5 header + body, Step 6 report).

- [ ] **Step 6: Commit**

```bash
git add skills/implr-init/SKILL.md
git commit -m "feat(implr-init): generate requirements-card.md; --refresh-card covers both cards"
```

---

## Task 6: Update installer scripts to copy the new template

**Files:**
- Modify: `install.ps1`
- Modify: `install.sh`
- Modify: `install.bat`

- [ ] **Step 1: Confirm `install.ps1` already wildcards the templates dir**

Run (PowerShell):
```powershell
Select-String -Path install.ps1 -Pattern "scaffold.*templates"
```
Expected: at least one match (a wildcarded `Copy-Item` over `scaffold\templates`). If the script already copies `*.md` from the templates folder, no edit is required for `install.ps1`. Verify by reading the relevant block and continue.

If `install.ps1` enumerates templates by name, add `requirements-card-template.md` to the list. Otherwise leave as-is.

- [ ] **Step 2: Same check for `install.sh`**

Run (Bash):
```bash
grep -n "scaffold/templates" install.sh
```
Expected: a wildcarded copy of `scaffold/templates/*.md` into `docs/implr/templates/`. If enumerated, add `requirements-card-template.md`; otherwise leave as-is.

- [ ] **Step 3: Same check for `install.bat`**

Run (PowerShell):
```powershell
Select-String -Path install.bat -Pattern "scaffold.templates"
```
Expected: a wildcarded copy. If enumerated, add the new template; otherwise leave as-is.

- [ ] **Step 4: Run the installer against a scratch directory to verify the template arrives**

```powershell
$scratch = New-Item -ItemType Directory -Force -Path "$env:TEMP\implr-install-test-$(Get-Date -Format yyyyMMddHHmmss)"
Push-Location $scratch
try {
  & "$PSScriptRoot\..\install.ps1"  # adjust path if running from plan
  Test-Path "docs\implr\templates\requirements-card-template.md"
} finally {
  Pop-Location
  Remove-Item -Recurse -Force $scratch
}
```

Expected final output: `True`.

POSIX equivalent: `bash install.sh && test -f docs/implr/templates/requirements-card-template.md && echo OK` inside a scratch dir.

- [ ] **Step 5: Commit (only if installer changes were needed)**

If any installer file changed:
```bash
git add install.ps1 install.sh install.bat
git commit -m "chore(install): ensure requirements-card-template.md ships to docs/implr/templates"
```

If none changed, skip the commit — the wildcard already handles it.

---

## Task 7: Rewrite `requirements-domain-worker` to consume an inline envelope

**Files:**
- Modify: `.claude/agents/requirements-domain-worker.md`

- [ ] **Step 1: Replace the file end-to-end with the envelope version**

Overwrite `.claude/agents/requirements-domain-worker.md` with this exact content:

````markdown
---
name: requirements-domain-worker
description: Generates functional and non-functional requirements for one domain from an inline envelope (requirements-card, domain synthesis, NFR-relevant master synthesis excerpt, contradiction maps). Does NOT read requirement-schema, implr.config.yaml, or DEV-STANDARDS — all stable context arrives inline. Writes REQ files to a staging directory with slug-only filenames.
tools: [Read, Write, Glob]
default_model: sonnet
---

# requirements-domain-worker

You generate requirements for exactly one domain. You write REQ files with slug-only
filenames to the staging directory the orchestrator gives you. The orchestrator renames
them with sequential IDs after all workers return.

## You do NOT read

- `docs/implr/schemas/requirement-schema.md` — the executable subset arrives as
  `requirements_card` in the envelope.
- `docs/implr/config/implr.config.yaml` — `default_tdd_threshold` arrives in the envelope.
- `docs/implr/config/DEV-STANDARDS.md` — NFR baselines arrive inside `requirements_card`.
- `docs/implr/kb-index/master-synthesis.md` — only the NFR + cross-domain-contradiction
  excerpt is provided as `master_synthesis_nfr`.
- `docs/implr/kb-index/domains/<domain>-synthesis.md` — its full content is provided
  inline as `domain_synthesis`.

Reading any of these wastes tokens. The envelope is authoritative. You MAY read a
per-doc digest from `digests_dir` only when the domain synthesis flags an ambiguity for
that doc, when field-level data models are needed, when a specific numeric NFR target
the synthesis paraphrased is required, or when a requirement cannot meet the quality
gate from the synthesis alone.

You NEVER read `docs/implr/kb-index/cache/<slug>.txt`. The digest is the complete
structured extraction of the source.

## Inputs (from the orchestrator)

```yaml
domain_envelope:
  domain: <domain>
  mode: create | reprocess
  reprocess_target: <doc-or-cr-path>   # only when mode=reprocess

  staging_dir: docs/implr/requirements/.staging/<domain>/
  digests_dir: docs/implr/kb-index/digests/per-doc/

  requirements_card: |
    <full inline content of docs/implr/config/requirements-card.md>

  domain_synthesis: |
    <full inline content of docs/implr/kb-index/domains/<domain>-synthesis.md>

  master_synthesis_nfr: |
    <inline excerpt: "Global NFR Candidates" + "Cross-Domain Contradictions" sections only>

  default_tdd_threshold: M     # M | L | XL (from implr.config.yaml)

  existing_reqs_summary:
    req_ids: [REQ-F-001, REQ-F-002, ...]
    slugs_in_domain: [...]

  # From ba-requirements-gen Phase 0
  resolved_contradictions: {C-001: {problem: "...", decision: "..."}, ...}
  deferred_contradictions: ["C-003", "C-004"]
```

## Work

Use `requirements_card` as the authoritative spec for frontmatter, section order, quality
gate, optional-section rules, NFR additions, and tone.

Read `domain_synthesis`. For each item in its "Ambiguities Detected" section, either
resolve from a per-doc digest (read `digests_dir/<slug>-digest.md` when needed) or surface
it as an Open Question citing the source document.

For C-IDs referenced in the synthesis "Contradictions Detected" table, normalise to
uppercase with no surrounding whitespace before lookup, then apply:

| C-ID state | Action |
|------------|--------|
| In `resolved_contradictions` | Use the `decision` value as authoritative content. Do NOT create an Open Question. |
| In `deferred_contradictions` | Create an Open Question: `Source: <C-ID> (deferred)`, question text = problem summary. |
| Not referenced (regular ambiguity) | Existing behaviour — create an Open Question citing the source document. |

Generate one REQ per: distinct user-facing behaviour, business rule, data lifecycle
event, external integration. Generate one NFR per distinct cross-cutting quality
constraint (use `master_synthesis_nfr` as the source of global NFR candidates).

Apply requirement inference per `requirements_card`. Set `complexity` from subtask
aggregation; derive `tdd_required` from complexity vs `default_tdd_threshold`.

For `mode: reprocess`: re-derive requirements for the named source document from the
current (already up-to-date) `domain_synthesis`. **You do not apply CR diffs** — that is
`cr-applier`'s job. The orchestrator dispatches `cr-applier` separately before invoking
you.

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
contradictions_resolved_via_map: <n>
contradictions_flagged: <n>
```
````

- [ ] **Step 2: Verify**

Run (PowerShell):
```powershell
Select-String -Path .claude\agents\requirements-domain-worker.md -Pattern "## You do NOT read"
```
Expected: exactly one match.

Run (PowerShell):
```powershell
Select-String -Path .claude\agents\requirements-domain-worker.md -Pattern "requirements_card|domain_synthesis|master_synthesis_nfr"
```
Expected: at least eight matches across the file.

Run (PowerShell):
```powershell
Select-String -Path .claude\agents\requirements-domain-worker.md -Pattern "## Read first"
```
Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add .claude/agents/requirements-domain-worker.md
git commit -m "feat(reqs-worker): consume inline envelope; drop stable reads (schema/config/standards)"
```

---

## Task 8: Update `ba-requirements-gen` Phase 3 to build inline envelopes

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md`

- [ ] **Step 1: Add `requirements-card.md` to the "Read first" list**

Find the `## Read first` block:

```
- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/kb-index/master-synthesis.md`  (stop if missing — tell user to run /doc-ingest --digest)
- `docs/implr/config/implr.config.yaml`
```

Replace with:

```
- `docs/implr/config/requirements-card.md`  (stop if missing — tell user to run /implr-init or /implr-init --refresh-card)
- `docs/implr/schemas/requirement-schema.md`  (orchestrator only — workers no longer read this)
- `docs/implr/kb-index/master-synthesis.md`  (stop if missing — tell user to run /doc-ingest)
- `docs/implr/config/implr.config.yaml`  (orchestrator only — for default_tdd_threshold and contradictions_block)
```

- [ ] **Step 2: Replace Phase 3 with the envelope-building version**

Find the current Phase 3 block:

```
### Phase 3 — Dispatch `requirements-domain-worker` per domain (parallel)

For each in-scope domain, dispatch with scope `{domain, synthesis_path, master_synthesis_path,
digests_dir, staging_dir, existing_reqs_index, mode, reprocess_target,
resolved_contradictions, deferred_contradictions}`. Cap parallelism at 5.

Where `resolved_contradictions` is `resolved_map` and `deferred_contradictions` is
`deferred_list` built in Phase 0 Step 5.

Each worker writes to `staging/<domain>/<slug>.md` (functional) or `staging/<domain>/n-<slug>.md`
(non-functional) with empty `req_id` fields.
```

Replace with:

````
### Phase 3 — Dispatch `requirements-domain-worker` per domain (parallel, inline envelope)

**Build once per run (before dispatching any worker):**

1. `requirements_card_inline` = full contents of `docs/implr/config/requirements-card.md`
   read once (stop with the error in Phase 1 if absent).

2. `master_synthesis_nfr_inline` = the substring of `docs/implr/kb-index/master-synthesis.md`
   containing ONLY the "Global NFR Candidates" section AND the "Cross-Domain Contradictions"
   section (heading inclusive, ending at the next `## ` heading or EOF). If either section
   is absent in the master synthesis, substitute the literal string `N/A` for that section
   inside the inline excerpt with a one-line header so the worker can still parse it.

3. `default_tdd_threshold` = value of `behaviour.default_tdd_threshold` from
   `implr.config.yaml`.

4. `existing_reqs_summary` = `{req_ids: [...], slugs_in_domain: {<domain>: [...], ...}}`
   built from `requirements-index.md` (or empty lists on first run).

**Per-domain (parallel, cap 5):**

For each in-scope domain, read its synthesis file ONCE in the orchestrator and pass the
content inline. Dispatch `requirements-domain-worker` with `domain_envelope`:

```yaml
domain_envelope:
  domain: <domain>
  mode: <create|reprocess>
  reprocess_target: <path or null>

  staging_dir: docs/implr/requirements/.staging/<domain>/
  digests_dir: docs/implr/kb-index/digests/per-doc/

  requirements_card: |
    <requirements_card_inline>

  domain_synthesis: |
    <full content of docs/implr/kb-index/domains/<domain>-synthesis.md, read here>

  master_synthesis_nfr: |
    <master_synthesis_nfr_inline>

  default_tdd_threshold: <value>

  existing_reqs_summary:
    req_ids: <existing_reqs_summary.req_ids>
    slugs_in_domain: <existing_reqs_summary.slugs_in_domain[<domain>] or []>

  resolved_contradictions: <resolved_map>
  deferred_contradictions: <deferred_list>
```

Each worker writes to `staging/<domain>/<slug>.md` (functional) or
`staging/<domain>/n-<slug>.md` (non-functional) with empty `req_id` fields.

**Token-budget note:** workers no longer cold-read `requirement-schema.md`, `DEV-STANDARDS.md`,
`implr.config.yaml`, or `master-synthesis.md`. Stable context arrives inline (~50 lines of
`requirements_card` + the NFR-only master excerpt) instead of ~400+ lines read per worker.
````

- [ ] **Step 3: Add a Phase 1 stop-condition for the missing card**

Find the start of `### Phase 1 — Load state and determine scope`. Just before it, append a new check to the Phase 0 block (after Step 5):

```

**Step 6 — Verify requirements-card present**

If `docs/implr/config/requirements-card.md` does not exist, halt with:

```
❌ requirements-card.md missing. Run /implr-init (first-time setup) or
   /implr-init --refresh-card (to regenerate from DEV-STANDARDS.md + config).
```

Do not advance to Phase 1.
```

- [ ] **Step 4: Verify**

Run (PowerShell):
```powershell
Select-String -Path skills\ba-requirements-gen\SKILL.md -Pattern "requirements-card"
```
Expected: at least three matches (Read first, Phase 0 Step 6, Phase 3 build).

Run (PowerShell):
```powershell
Select-String -Path skills\ba-requirements-gen\SKILL.md -Pattern "domain_envelope"
```
Expected: at least two matches.

Run (PowerShell):
```powershell
Select-String -Path skills\ba-requirements-gen\SKILL.md -Pattern "synthesis_path"
```
Expected: no matches (replaced by inline `domain_synthesis`).

- [ ] **Step 5: Commit**

```bash
git add skills/ba-requirements-gen/SKILL.md
git commit -m "feat(reqs-gen): inline envelope dispatch; read stable files once per run"
```

---

## Task 9: Update `WORKFLOW.md` to reflect both changes

**Files:**
- Modify: `docs/WORKFLOW.md`

- [ ] **Step 1: Find the doc-ingest dispatch block**

Read `docs/WORKFLOW.md` and locate the section describing doc-ingest agents/dispatch
(search for `doc-ingest-extractor` or the doc-ingest phase chart).

- [ ] **Step 2: Replace extractor references**

Remove every mention of `doc-ingest-extractor`. In the dispatch chart, replace the
"extract" row to indicate inline extraction in the skill. Example replacement (apply to
matching prose; exact wording depends on existing content):

```
| Phase | Runner | Notes |
|---|---|---|
| Extract (text from KB files) | `doc-ingest` skill (inline) | shell-only: cp / pdftotext / python one-liners; no LLM token cost |
| Digest (per doc) | `doc-ingest-digester` | sonnet; 1 per NEW/CHANGED file |
| Synthesise (per domain) | `doc-ingest-synthesizer` | sonnet; 1 per affected domain |
```

If no such chart exists, add a one-paragraph note under the doc-ingest section:

```
**v3.1:** Text extraction is now inline in the `doc-ingest` skill (direct shell calls).
The `doc-ingest-extractor` subagent has been removed — file content no longer enters an
LLM context window during extraction.
```

- [ ] **Step 3: Add the requirements-card / envelope note**

Find the section describing `ba-requirements-gen` or `requirements-domain-worker`. Add:

```
**v3.1:** `ba-requirements-gen` builds an inline `domain_envelope` per dispatch.
`requirements-domain-worker` no longer reads `requirement-schema.md`,
`implr.config.yaml`, `DEV-STANDARDS.md`, or `master-synthesis.md` — the orchestrator
reads them once, packages the executable subset as `requirements_card` (auto-generated
by `/implr-init`), and embeds them inline. Mirrors the v3.0 `task-executor` envelope
contract.
```

- [ ] **Step 4: Verify**

Run (PowerShell):
```powershell
Select-String -Path docs\WORKFLOW.md -Pattern "doc-ingest-extractor"
```
Expected: no matches.

Run (PowerShell):
```powershell
Select-String -Path docs\WORKFLOW.md -Pattern "requirements_card|domain_envelope"
```
Expected: at least one match.

- [ ] **Step 5: Commit**

```bash
git add docs/WORKFLOW.md
git commit -m "docs(workflow): reflect inline extraction and requirements envelope dispatch"
```

---

## Task 10: Update `README.md` with the v3.1 changes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find or create a "What's new" section**

Read `README.md` top-to-bottom and locate the version notes section (likely titled
`What's new`, `Changelog`, or `Release notes`). If none exists, add one immediately
after the top-of-file project description.

- [ ] **Step 2: Add a v3.1 entry**

Insert at the TOP of the version notes block:

```markdown
### v3.1 — Cost reduction Wave 2

- **doc-ingest: inline extraction.** KB text extraction no longer dispatches a subagent.
  The skill runs `cp`, `pdftotext`, or a python one-liner directly. File content never
  enters an LLM window during extraction. Savings: ~1 subagent dispatch + N file-content
  reads per ingest. The `doc-ingest-extractor` agent has been removed.
- **ba-requirements-gen: inline envelope.** Mirrors the v3.0 task-executor envelope
  pattern. `requirements-domain-worker` no longer reads `requirement-schema.md`,
  `DEV-STANDARDS.md`, `implr.config.yaml`, or `master-synthesis.md` on cold start.
  Orchestrator builds a `requirements_card` (auto-generated by `/implr-init`) plus a
  domain envelope; worker receives everything inline. Savings: ~30–40k tokens × N
  domains per run.
- **`/implr-init` change.** Step 5 generates `docs/implr/config/requirements-card.md`.
  `/implr-init --refresh-card` now regenerates both standards-card and requirements-card.
```

- [ ] **Step 3: Verify**

Run (PowerShell):
```powershell
Select-String -Path README.md -Pattern "v3\.1"
```
Expected: at least one match.

Run (PowerShell):
```powershell
Select-String -Path README.md -Pattern "requirements-card|inline envelope|inline extraction"
```
Expected: at least three matches.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): v3.1 release notes — inline extraction + requirements envelope"
```

---

## Task 11: End-to-end smoke verification

**Files:** none modified — verification only.

- [ ] **Step 1: Set up a scratch workspace**

```powershell
$scratch = New-Item -ItemType Directory -Force -Path "$env:TEMP\implr-smoke-$(Get-Date -Format yyyyMMddHHmmss)"
Push-Location $scratch
& "B:\development\python_space\implr\install.ps1"
```

Expected: installer reports success and creates `docs/implr/` plus `.claude/`.

- [ ] **Step 2: Verify removed and new artefacts**

```powershell
Test-Path .claude\agents\doc-ingest-extractor.md     # → False
Test-Path docs\implr\templates\requirements-card-template.md   # → True
```

- [ ] **Step 3: Run `/implr-init` in Claude Code on the scratch workspace**

Open the scratch directory in Claude Code. Run `/implr-init`. Provide minimal answers
(project name `smoke`, accept all defaults).

Verify:
```powershell
Test-Path docs\implr\config\standards-card.md         # → True
Test-Path docs\implr\config\requirements-card.md      # → True
Select-String -Path docs\implr\config\requirements-card.md -Pattern "\{\{TDD_THRESHOLD\}\}"
# Expected: no matches (placeholder substituted)
Select-String -Path docs\implr\config\requirements-card.md -Pattern "Effective threshold per project: M"
# Expected: one match (or whatever threshold was chosen)
```

- [ ] **Step 4: Run `/implr-init --refresh-card` and confirm both cards regenerate**

```powershell
Remove-Item docs\implr\config\standards-card.md
Remove-Item docs\implr\config\requirements-card.md
```

In Claude Code: `/implr-init --refresh-card`.

```powershell
Test-Path docs\implr\config\standards-card.md         # → True
Test-Path docs\implr\config\requirements-card.md      # → True
```

- [ ] **Step 5: Drop a tiny KB doc and run `/doc-ingest`**

```powershell
New-Item -ItemType Directory -Force -Path "docs\kb\smoke" | Out-Null
Set-Content -Encoding utf8 -Path "docs\kb\smoke\hello.md" -Value @"
# Smoke Test Doc

Users can reset their password by requesting a reset link. The link expires after 15 minutes.
"@
```

In Claude Code: `/doc-ingest`.

Verify the extracted cache:
```powershell
Test-Path docs\implr\kb-index\cache\hello.txt    # → True
(Get-Content docs\implr\kb-index\cache\hello.txt -Raw) -match "reset their password"   # → True
```

Confirm the agent transcript shows ZERO dispatches of `doc-ingest-extractor` (only
inline Bash + parallel digester/synthesizer dispatches).

- [ ] **Step 6: Run `/ba-requirements-gen` and inspect the worker dispatch**

In Claude Code: `/ba-requirements-gen`.

Verify the transcript shows the orchestrator reading `requirements-card.md`,
`master-synthesis.md`, `implr.config.yaml`, and each domain synthesis file ONCE — then
dispatching `requirements-domain-worker` with an inline `domain_envelope`.

Verify the worker transcript shows NO reads of:
- `docs/implr/schemas/requirement-schema.md`
- `docs/implr/config/DEV-STANDARDS.md`
- `docs/implr/config/implr.config.yaml`
- `docs/implr/kb-index/master-synthesis.md`
- `docs/implr/kb-index/domains/*-synthesis.md`

Verify the worker DID produce at least one REQ file in
`docs/implr/requirements/functional/` or `non-functional/`.

- [ ] **Step 7: Clean up**

```powershell
Pop-Location
Remove-Item -Recurse -Force $scratch
```

- [ ] **Step 8: Commit the verification record**

Append a short entry to `docs/superpowers/plans/2026-06-03-doc-ingest-and-reqs-cost-reduction.md`
under a new `## Verification Results` section at the bottom: timestamp, scratch dir,
the four `Test-Path` outcomes, the two transcript audits, and the produced REQ filename.

```bash
git add docs/superpowers/plans/2026-06-03-doc-ingest-and-reqs-cost-reduction.md
git commit -m "test(v3.1): smoke verification — inline extraction + envelope dispatch confirmed"
```

---

## Self-review checklist (already applied during authoring)

- Spec coverage: both stated problems (inline extraction, requirements envelope) have implementation tasks (Tasks 1–3 and Tasks 4–8 respectively); docs + install + smoke covered (Tasks 6, 9, 10, 11).
- No placeholders: every code/command/markdown block is concrete; no "TBD" or "implement later".
- Type consistency: `domain_envelope` shape declared identically in the agent (Task 7) and the orchestrator (Task 8). `requirements_card` placeholder `{{TDD_THRESHOLD}}` declared in template (Task 4) and substituted in skill (Task 5). Cache extension `.txt` consistent across Tasks 1 and 3.
- Order: leaves first (skill rewrite, agent deletion, schema fix, template, init, installer), inward (worker contract, orchestrator dispatch), outward (docs, smoke).
