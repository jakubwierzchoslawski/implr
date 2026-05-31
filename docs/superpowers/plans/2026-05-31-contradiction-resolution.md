# Contradiction Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Phase 0 to `ba-requirements-gen` that resolves C-xxx contradictions before any requirement is generated, persisting decisions in `resolved-contradictions.md` so workers produce correct requirements from the start.

**Architecture:** A new seed file mirrors `cr-index.md`'s pattern. `ba-requirements-gen` gains Phase 0 which reads all C-xxx IDs from syntheses, presents unresolved ones to the user, and writes decisions to `resolved-contradictions.md`. Workers receive the resolved/deferred maps in their dispatch scope and apply a simple lookup rule before creating Open Questions.

**Tech Stack:** Markdown skill files, YAML frontmatter, bash/PowerShell/bat install scripts.

---

## Files

| Action | Path |
|--------|------|
| Create | `scaffold/seeds/resolved-contradictions.md` |
| Modify | `scaffold/schemas/kb-index-schema.md` |
| Modify | `install.sh` |
| Modify | `install.ps1` |
| Modify | `install.bat` |
| Modify | `skills/ba-requirements-gen/SKILL.md` |
| Modify | `.claude/agents/requirements-domain-worker.md` |
| Modify | `docs/WORKFLOW.md` |
| Modify | `README.md` |

---

## Task 1: Seed file and schema

**Files:**
- Create: `scaffold/seeds/resolved-contradictions.md`
- Modify: `scaffold/schemas/kb-index-schema.md`

- [ ] **Step 1: Create the seed file**

Create `scaffold/seeds/resolved-contradictions.md` with this exact content:

```markdown
# Resolved Contradictions
> Maintained by ba-requirements-gen. To change a decision, edit this file and re-run `/ba-requirements-gen`.

## Resolved
| C-ID | Type | Source A | Source B | Problem | Decision | Resolved |
|------|------|----------|----------|---------|----------|----------|

## Deferred
| C-ID | Type | Source A | Source B | Problem | Notes | Deferred |
|------|------|----------|----------|---------|-------|----------|
```

- [ ] **Step 2: Verify the seed file**

Read `scaffold/seeds/resolved-contradictions.md`. Confirm:
- Header says `# Resolved Contradictions`
- The `> Maintained by...` line mentions editing the file and re-running `/ba-requirements-gen`
- Resolved table has 7 columns: C-ID, Type, Source A, Source B, Problem, Decision, Resolved
- Deferred table has 7 columns: C-ID, Type, Source A, Source B, Problem, Notes, Deferred
- Both tables have only the header+separator rows (empty data)

- [ ] **Step 3: Add schema section to kb-index-schema.md**

Read `scaffold/schemas/kb-index-schema.md`. The file currently ends after section 6 (digest-log.md). Append this new section at the end:

```markdown

---

## 7. requirements/resolved-contradictions.md — Contradiction Resolution Log

Location: `docs/implr/requirements/resolved-contradictions.md`

Records human decisions on every C-xxx contradiction detected during synthesis. Consumed by
`ba-requirements-gen` Phase 0 and passed to `requirements-domain-worker` subagents. The file
is append-only — re-running `ba-requirements-gen` adds new rows but never overwrites existing
ones. To change a decision, edit the file manually and re-run `/ba-requirements-gen`.

```markdown
# Resolved Contradictions
> Maintained by ba-requirements-gen. To change a decision, edit this file and re-run `/ba-requirements-gen`.

## Resolved
| C-ID  | Type          | Source A                | Source B                | Problem                          | Decision                      | Resolved   |
|-------|---------------|-------------------------|-------------------------|----------------------------------|-------------------------------|------------|
| C-001 | Hard conflict | docs/kb/spec-v1.md §3.2 | docs/kb/spec-v2.md §1.4 | Auth token TTL: 15 min vs 30 min | Use 30-minute auth token TTL  | 2026-05-31 |

## Deferred
| C-ID  | Type          | Source A            | Source B            | Problem                         | Notes                     | Deferred   |
|-------|---------------|---------------------|---------------------|---------------------------------|---------------------------|------------|
| C-003 | Scope overlap | docs/kb/roadmap.md  | docs/kb/mvp.md      | Feature X: in MVP scope or not? | Needs product owner input | 2026-05-31 |
```

### Column definitions

**Resolved table**

| Column | Source | Notes |
|--------|--------|-------|
| C-ID | domain/master synthesis | Assigned at synthesis time |
| Type | synthesis Contradictions Detected | Hard conflict / Soft conflict / Version drift / Scope overlap |
| Source A | synthesis | File path + section if available |
| Source B | synthesis | File path + section if available |
| Problem | synthesis contradiction description | Short summary copied verbatim |
| Decision | user input during Phase 0 | Authoritative; passed to workers |
| Resolved | ISO date Phase 0 ran | |

**Deferred table**

Same columns except `Decision` → `Notes` (user's deferral reason) and `Resolved` → `Deferred`.

### Idempotency

`ba-requirements-gen` Phase 0 skips any C-ID already present in either table. Only new
C-IDs trigger prompts. File is never truncated or overwritten — only appended.
```

- [ ] **Step 4: Verify the schema section**

Read `scaffold/schemas/kb-index-schema.md`. Confirm:
- Section `## 7. requirements/resolved-contradictions.md` exists after section 6
- The example tables match the seed file structure (same column names, same order)
- Column definitions table is present for both Resolved and Deferred tables
- Idempotency rule is documented

- [ ] **Step 5: Commit**

```bash
git add scaffold/seeds/resolved-contradictions.md scaffold/schemas/kb-index-schema.md
git commit -m "feat: add resolved-contradictions.md seed and schema"
```

---

## Task 2: Update install scripts

**Files:**
- Modify: `install.sh` (after line ~79, in `scaffold_workspace` function, before `echo "  workspace scaffolded"`)
- Modify: `install.ps1` (after line ~81, in `Scaffold-Workspace` function, before `Write-Host "  workspace scaffolded"`)
- Modify: `install.bat` (after line ~122, in `:scaffold_workspace` subroutine, before `echo   workspace scaffolded`)

- [ ] **Step 1: Update install.sh**

Read `install.sh`. Find the cr-index.md block (around line 74–79):

```bash
  # Skip if exists: cr-index.md seed
  if [ ! -f "docs/implr/requirements/cr-index.md" ]; then
    cp "$SCAFFOLD_SRC/seeds/cr-index.md" "docs/implr/requirements/cr-index.md"
    echo "  created docs/implr/requirements/cr-index.md"
  else
    echo "  kept existing docs/implr/requirements/cr-index.md"
  fi

  echo "  workspace scaffolded"
```

Insert this block between the cr-index.md block and `echo "  workspace scaffolded"`:

```bash
  # Skip if exists: resolved-contradictions.md seed
  if [ ! -f "docs/implr/requirements/resolved-contradictions.md" ]; then
    cp "$SCAFFOLD_SRC/seeds/resolved-contradictions.md" "docs/implr/requirements/resolved-contradictions.md"
    echo "  created docs/implr/requirements/resolved-contradictions.md"
  else
    echo "  kept existing docs/implr/requirements/resolved-contradictions.md"
  fi
```

- [ ] **Step 2: Update install.ps1**

Read `install.ps1`. Find the cr-index.md block (around line 76–81):

```powershell
    # Skip if exists: cr-index.md seed
    if (-not (Test-Path "docs\implr\requirements\cr-index.md")) {
        Copy-Item (Join-Path $ScaffoldSrc "seeds\cr-index.md") "docs\implr\requirements\cr-index.md"
        Write-Host "  created docs\implr\requirements\cr-index.md"
    } else {
        Write-Host "  kept existing docs\implr\requirements\cr-index.md"
    }

    Write-Host "  workspace scaffolded"
```

Insert this block between the cr-index.md block and `Write-Host "  workspace scaffolded"`:

```powershell
    # Skip if exists: resolved-contradictions.md seed
    if (-not (Test-Path "docs\implr\requirements\resolved-contradictions.md")) {
        Copy-Item (Join-Path $ScaffoldSrc "seeds\resolved-contradictions.md") "docs\implr\requirements\resolved-contradictions.md"
        Write-Host "  created docs\implr\requirements\resolved-contradictions.md"
    } else {
        Write-Host "  kept existing docs\implr\requirements\resolved-contradictions.md"
    }
```

- [ ] **Step 3: Update install.bat**

Read `install.bat`. Find the cr-index.md block (around line 118–123):

```bat
if not exist "docs\implr\requirements\cr-index.md" (
    copy /y "%SCAFFOLD_SRC%\seeds\cr-index.md" "docs\implr\requirements\cr-index.md" >nul
    echo   created docs\implr\requirements\cr-index.md
) else (
    echo   kept existing docs\implr\requirements\cr-index.md
)

echo   workspace scaffolded
```

Insert this block between the cr-index.md block and `echo   workspace scaffolded`:

```bat
if not exist "docs\implr\requirements\resolved-contradictions.md" (
    copy /y "%SCAFFOLD_SRC%\seeds\resolved-contradictions.md" "docs\implr\requirements\resolved-contradictions.md" >nul
    echo   created docs\implr\requirements\resolved-contradictions.md
) else (
    echo   kept existing docs\implr\requirements\resolved-contradictions.md
)
```

- [ ] **Step 4: Verify all three scripts**

Read install.sh, install.ps1, install.bat and confirm:
- All three have the resolved-contradictions.md block immediately before the "workspace scaffolded" message
- All three use "Skip if exists" logic (not force-copy)
- The source path in all three uses `seeds/resolved-contradictions.md` (not `config/` or `templates/`)
- The destination path in all three is `docs/implr/requirements/resolved-contradictions.md`

- [ ] **Step 5: Commit**

```bash
git add install.sh install.ps1 install.bat
git commit -m "feat(install): seed resolved-contradictions.md on workspace scaffold"
```

---

## Task 3: Update ba-requirements-gen SKILL.md

**Files:**
- Modify: `skills/ba-requirements-gen/SKILL.md`

The current skill has phases numbered 1–10. This task inserts Phase 0 before Phase 1 and
updates Phase 3 (dispatch scope) and Phase 10 (report).

- [ ] **Step 1: Insert Phase 0 before Phase 1**

Read `skills/ba-requirements-gen/SKILL.md`. Find the `## Execution` heading and the line
`### Phase 1 — Load state and determine scope`. Insert Phase 0 immediately before Phase 1:

```markdown
### Phase 0 — Contradiction Resolution

Run before Phase 1. Resolves outstanding C-xxx contradictions so workers generate
requirements with correct data — resolved contradictions never become Open Questions.

**Step 1 — Collect C-IDs**

Read every `docs/implr/kb-index/domains/*-synthesis.md` and gather all rows from their
`Contradictions Detected` tables. Read `docs/implr/kb-index/master-synthesis.md` and gather
rows from `Cross-Domain Contradictions`. De-duplicate by C-ID.

**Step 2 — Load existing resolutions**

Read `docs/implr/requirements/resolved-contradictions.md` (skip if absent).
Build `already_handled = resolved_ids ∪ deferred_ids`.

**Step 3 — Prompt for unresolved**

For each C-ID not in `already_handled`, present to user:

```
C-001 [Hard conflict]
Source A: docs/kb/spec-v1.md §3.2 — "Token TTL must be 15 minutes"
Source B: docs/kb/spec-v2.md §1.4 — "Token TTL must be 30 minutes"
Problem:  Auth token TTL: 15 min vs 30 min

Decision (or type 'defer' + reason):
```

**Step 4 — Write resolutions**

After collecting all answers, append new rows to `docs/implr/requirements/resolved-contradictions.md`
in a single pass. Resolved decisions go to the `## Resolved` table; deferred items go to
the `## Deferred` table. If the file does not yet exist, create it from the seed structure.

If all C-IDs are already in `already_handled`: log
`No unresolved contradictions. Skipping Phase 0.` and proceed immediately to Phase 1.

**Step 5 — Build dispatch maps**

After writing, read `resolved-contradictions.md` and build:
- `resolved_map`: `{C-001: {problem: "...", decision: "..."}, ...}` — one entry per Resolved row
- `deferred_list`: `["C-003", "C-004"]` — C-IDs from the Deferred table

These are passed to every worker dispatch in Phase 3.

```

- [ ] **Step 2: Update Phase 3 dispatch scope**

Find the Phase 3 dispatch scope line:

```
For each in-scope domain, dispatch with scope `{domain, synthesis_path, master_synthesis_path,
digests_dir, staging_dir, existing_reqs_index, mode, reprocess_target}`. Cap parallelism at 5.
```

Replace with:

```
For each in-scope domain, dispatch with scope `{domain, synthesis_path, master_synthesis_path,
digests_dir, staging_dir, existing_reqs_index, mode, reprocess_target,
resolved_contradictions, deferred_contradictions}`. Cap parallelism at 5.
```

Where `resolved_contradictions` is `resolved_map` and `deferred_contradictions` is
`deferred_list` built in Phase 0 Step 5.

- [ ] **Step 3: Update Phase 10 report**

Find the Phase 10 report block:

```
✅ Requirements generation complete  (v2.0)
Domains processed: {list}
Requirements created: {n} ({f} functional, {nfr} non-functional)
Requirements updated: {n}
Open questions: {n} (incl. {c} contradictions)
Needs your review: {list of REQ ids}
Post-implementation updates: {list, if any}
```

Replace the `Open questions` line with two lines:

```
Contradictions: {r} resolved, {d} deferred in Phase 0
Open questions: {n} (from deferred contradictions and synthesis ambiguities)
```

- [ ] **Step 4: Verify the SKILL.md changes**

Read `skills/ba-requirements-gen/SKILL.md`. Confirm:
- Phase 0 section exists before Phase 1 with all 5 steps
- Phase 3 dispatch scope includes `resolved_contradictions` and `deferred_contradictions`
- Phase 10 report has both contradiction and open questions lines
- No existing phases were accidentally deleted or renumbered

- [ ] **Step 5: Commit**

```bash
git add skills/ba-requirements-gen/SKILL.md
git commit -m "feat(ba-requirements-gen): add Phase 0 contradiction resolution"
```

---

## Task 4: Update requirements-domain-worker.md

**Files:**
- Modify: `.claude/agents/requirements-domain-worker.md`

- [ ] **Step 1: Add new inputs to the Inputs section**

Read `.claude/agents/requirements-domain-worker.md`. Find the `## Inputs` block:

```
mode: create | reprocess
reprocess_target: <doc-or-cr-path>   (only when mode=reprocess)
```

Add two new lines immediately after `reprocess_target`:

```
resolved_contradictions: {C-001: {problem: "...", decision: "..."}, ...}   (empty map if none)
deferred_contradictions: ["C-003", "C-004"]                                 (empty list if none)
```

- [ ] **Step 2: Add contradiction resolution rule to Work section**

Find the Work section. It currently starts:

```
Read the domain synthesis. Check its "Ambiguities Detected" section. For each ambiguity
either resolve it from `docs/implr/kb-index/digests/per-doc/<slug>-digest.md` (if the
digest is unambiguous) or surface it as an Open Question citing the source document.
```

After that opening paragraph, insert:

```
When the domain synthesis `Contradictions Detected` table references a C-ID, apply this rule
before deciding whether to create an Open Question:

| C-ID state | Action |
|------------|--------|
| In `resolved_contradictions` | Use the `decision` value as authoritative content. Do NOT create an Open Question. |
| In `deferred_contradictions` | Create an Open Question: `Source: <C-ID> (deferred)`, question text = problem summary. |
| Not referenced (regular ambiguity) | Existing behaviour — create an Open Question citing the source document. |
```

- [ ] **Step 3: Update return summary**

Find the `## Return summary` block. Find the line:

```
contradictions_flagged: <n>
```

Replace with:

```
contradictions_resolved_via_map: <n>
contradictions_flagged: <n>
```

Where `contradictions_resolved_via_map` counts how many C-IDs were found in
`resolved_contradictions` (and therefore did NOT become Open Questions), and
`contradictions_flagged` counts deferred + unresolved items that became Open Questions.

- [ ] **Step 4: Verify worker changes**

Read `.claude/agents/requirements-domain-worker.md`. Confirm:
- Inputs section has `resolved_contradictions` and `deferred_contradictions` after `reprocess_target`
- Work section has the contradiction rule table immediately after the first paragraph
- Return summary has `contradictions_resolved_via_map` before `contradictions_flagged`
- The Inputs types match what ba-requirements-gen Phase 0 Step 5 builds (`resolved_map` and `deferred_list`)

- [ ] **Step 5: Commit**

```bash
git add .claude/agents/requirements-domain-worker.md
git commit -m "feat(requirements-domain-worker): apply resolved contradictions map"
```

---

## Task 5: Update WORKFLOW.md and README.md

**Files:**
- Modify: `docs/WORKFLOW.md`
- Modify: `README.md`

- [ ] **Step 1: Update the Contradiction Detection section in WORKFLOW.md**

Read `docs/WORKFLOW.md`. Find the `## Contradiction Detection` section (around line 160):

```markdown
## Contradiction Detection

Contradictions are found at synthesis time, not requirement time.

1. When a document changes, its digest is rebuilt.
2. The domain synthesis is rebuilt by reading **all** digests in that domain together — so a new
   document is automatically compared against every existing document in its domain.
3. Contradictions are classified: Hard conflict, Soft conflict, Version drift, Scope overlap.
4. Cross-domain contradictions are caught when the master synthesis is rebuilt from domain
   syntheses.
5. ba-requirements-gen reads these pre-detected contradictions and writes them into the
   affected requirement's Open Questions, citing both source documents — it does not need to
   re-read both raw files.

By default contradictions do not block requirement generation (`contradictions_block: false`);
the requirement is created with the most defensible interpretation plus an open question. Set
the flag to `true` to halt and ask instead.
```

Replace the entire section with:

```markdown
## Contradiction Detection

Contradictions are found at synthesis time, resolved before requirement generation.

1. When a document changes, its digest is rebuilt.
2. The domain synthesis is rebuilt by reading **all** digests in that domain together — so a new
   document is automatically compared against every existing document in its domain.
3. Contradictions are classified: Hard conflict, Soft conflict, Version drift, Scope overlap,
   and assigned a C-xxx ID.
4. Cross-domain contradictions are caught when the master synthesis is rebuilt from domain
   syntheses.
5. When you run `/ba-requirements-gen`, **Phase 0** reads all C-xxx IDs from the domain and
   master syntheses, presents each unresolved one to you with both conflicting sources, and
   records your decision in `docs/implr/requirements/resolved-contradictions.md`.
6. Workers receive the resolved decisions map. Resolved contradictions are used as authoritative
   content — they do not become Open Questions. Deferred contradictions become Open Questions
   with the C-ID preserved in the Source column (`Source: C-003 (deferred)`).

`resolved-contradictions.md` is append-only. Re-running `/ba-requirements-gen` only prompts
for contradictions not already in the file. To change a decision, edit the file manually and
re-run.

To halt on any deferred contradictions that become Open Questions, set
`contradictions_block: true` in `docs/implr/config/implr.config.yaml`.
```

- [ ] **Step 2: Update README.md requirements directory tree**

Read `README.md`. Find the requirements directory entry (around line 230–233):

```
│       ├── requirements/
│       │   ├── functional/             REQ-F-* files (ba-requirements-gen)
│       │   ├── non-functional/         REQ-N-* files (ba-requirements-gen)
│       │   └── cr-index.md            change-request index (ba-cr)
```

Replace with:

```
│       ├── requirements/
│       │   ├── functional/             REQ-F-* files (ba-requirements-gen)
│       │   ├── non-functional/         REQ-N-* files (ba-requirements-gen)
│       │   ├── cr-index.md            change-request index (ba-cr)
│       │   └── resolved-contradictions.md  contradiction decisions (ba-requirements-gen)
```

- [ ] **Step 3: Update README.md step 5 description**

Find the step 5 description (around line 316–319):

```
5. REQUIREMENTS      /ba-requirements-gen
   Reads syntheses (not every raw doc), dispatches one requirements-domain-worker per
   in-scope domain in parallel, assigns sequential IDs after workers return, writes REQ-F-*
   and REQ-N-* files. Flags contradictions as open questions.
```

Replace the last sentence:

```
5. REQUIREMENTS      /ba-requirements-gen
   Reads syntheses (not every raw doc). Phase 0: resolves C-xxx contradictions interactively,
   persists decisions in resolved-contradictions.md. Then dispatches one requirements-domain-worker
   per in-scope domain in parallel, assigns sequential IDs after workers return, writes REQ-F-*
   and REQ-N-* files. Resolved contradictions never become open questions.
```

- [ ] **Step 4: Update interaction table for ba-requirements-gen**

Find the interaction table row (around line 357):

```
| `ba-requirements-gen` | Non-interactive | Never (open questions surfaced in files) |
```

Replace with:

```
| `ba-requirements-gen` | Interactive (Phase 0 only) | Resolves each unresolved contradiction once before generating requirements |
```

- [ ] **Step 5: Verify WORKFLOW.md and README.md**

Read both files and confirm:
- WORKFLOW.md contradiction section now has 6 numbered steps including Phase 0 and resolved-contradictions.md
- WORKFLOW.md no longer mentions `contradictions_block` as the only option (the old paragraph at the bottom of the section is replaced)
- README.md tree has `resolved-contradictions.md` entry
- README.md step 5 mentions Phase 0 and resolved-contradictions.md
- README.md interaction table shows ba-requirements-gen as interactive

- [ ] **Step 6: Commit**

```bash
git add docs/WORKFLOW.md README.md
git commit -m "docs: update contradiction detection workflow and README for Phase 0"
```
