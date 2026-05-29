# implr Workflow — Deep Dive

This document explains how implr works internally: how data flows between skills, how
incremental processing works, and how the artefacts relate. Read the [README](../README.md)
first for installation and commands.

---

## The Artefact Graph

Every artefact implr produces traces back to source documentation:

```
docs/kb/**                      source documents (you own these)
   │
   ▼  doc-ingest
docs/implr/kb-index/
   ├── cache/{slug}.txt         normalised text per file
   ├── digests/per-doc/         one structured digest per file
   ├── domains/{domain}-synthesis.md   consolidated per domain + contradictions
   └── master-synthesis.md      system-wide view (bounded size)
   │
   ├──────────────▼  arch-gen
   │           docs/ARCHITECTURE.md
   │
   ▼  ba-requirements-gen
docs/implr/requirements/
   ├── functional/REQ-F-*.md
   └── non-functional/REQ-N-*.md
   │
   ▼  dev-planner   (reads ARCHITECTURE.md + DEV-STANDARDS.md)
docs/implr/plans/
   ├── functional/PLAN-F-*.md
   └── non-functional/PLAN-N-*.md
   │
   ▼  dev-executor  (reads ARCHITECTURE.md + DEV-STANDARDS.md)
src/**  tests/**
   │
   ▼  dev-code-review  (fresh context)
docs/implr/reviews/REVIEW-F-*.md
```

Traceability chain: `source doc → digest → domain synthesis → requirement → plan → code → review`.

---

## Incremental Processing — How It Stays Fast

The core idea: **checksums gate every stage**, so unchanged inputs are never reprocessed.

### Checksum propagation

```
file checksum (md5 of original bytes)
   │ change here ...
   ▼
per-doc digest (records source checksum)
   │ ... forces rebuild here ...
   ▼
domain synthesis (synthesis_checksum = hash of its source digest checksums)
   │ ... forces rebuild here ...
   ▼
master synthesis (master_checksum = hash of domain synthesis_checksums)
   │ ... brings the domain back into scope here ...
   ▼
requirements for that domain
```

If a file's checksum is unchanged, nothing downstream of it is touched. If one file in a
50-document KB changes, doc-ingest re-digests that one file, rebuilds that one domain synthesis,
rebuilds the master synthesis, and ba-requirements-gen reprocesses only that domain.

### Why digests exist

A large knowledge base cannot all fit usefully in one context window. Reading 50 raw documents
to generate requirements produces shallow output. So:

- **doc-ingest** reads raw documents once and distils each into a dense digest.
- **Domain syntheses** consolidate digests per domain and catch contradictions.
- **The master synthesis** is a bounded, system-wide briefing.
- **ba-requirements-gen** reads the master synthesis and domain syntheses — not every raw file —
  and only deep-dives into a specific raw document when a digest flags an ambiguity it must
  resolve.

This mirrors how a human BA works: read the briefing, then go to source only for the details
that matter.

### Why the text cache exists

- **Extract once, read many times.** Binary and structured formats (PDF, DOCX, XLSX, CSV)
  require external tool invocations (`pdftotext`, `python-docx`, `openpyxl`) — expensive to
  repeat on every skill run.
- **Checksum gate.** doc-ingest writes `cache/{slug}.txt` once per file and records the source
  checksum. On subsequent runs, if the checksum is unchanged, the cache is read directly —
  no tool invocation needed.
- **One consistent read path.** `.md` and `.txt` files are straight copies into cache, but
  having a single path (`cache/{slug}.txt`) means every downstream skill (ba-requirements-gen,
  arch-gen) never needs to know the original format or invoke extraction tools.
- **Never read the binary original downstream.** Skills always read from cache. If a cache
  entry is absent for a file that is needed, the skill flags it as an Open Question rather
  than attempting to read the raw binary.

---

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

---

## The Human Gates

implr deliberately stops for human judgement at three points:

1. **Requirement approval.** ba-requirements-gen creates requirements as `draft`. dev-planner
   only processes `approved` ones. A human reviews, resolves open questions, and promotes status.

2. **Architectural decisions.** arch-gen marks inferred decisions and asks for confirmation
   before writing ARCHITECTURE.md. On re-runs it proposes a diff rather than overwriting.

3. **Design decisions (optional).** `dev-planner --brainstorm` presents design options and
   records the human's choices before generating the plan.

Everything else is automated.

---

## Status Lifecycles

### Requirement

```
draft → under-review → approved → superseded
                     ↘ rejected
```

| Transition | Who | Condition |
|-----------|-----|-----------|
| `draft` → `under-review` | Human | Requirement needs discussion before approval |
| `draft` → `approved` | Human | Requirement is correct and complete |
| `under-review` → `approved` | Human | Open questions resolved |
| `under-review` → `rejected` | Human | Requirement is invalid or out of scope |
| `approved` → `under-review` | ba-requirements-gen or ba-cr | A source doc changed and the requirement may be affected |
| `approved` → `superseded` | Human | A new requirement replaces this one (`superseded_by` set) |

Claude only ever creates `draft`. Only humans promote to `approved`. ba-requirements-gen
and ba-cr can drop `approved` → `under-review` but never to `draft` (preserving review history).

---

### Plan

```
ready → in-progress → done
  ↑                     │
  └── changes-required ◄┘  (set by dev-code-review)
blocked → ready          (once the blocker is resolved)
```

| Transition | Who | Condition |
|-----------|-----|-----------|
| `ready` | dev-planner | Plan created; ready for a developer to start |
| `ready` → `in-progress` | dev-executor | Developer starts implementation |
| `in-progress` → `done` | dev-executor | All tasks complete; code submitted for review |
| `done` → `changes-required` | dev-code-review | Review finds blocking issues |
| `changes-required` → `in-progress` | dev-executor | Developer picks up the changes |
| `ready` → `blocked` | dev-planner | A required dependency has no plan yet |
| `blocked` → `ready` | Human or dev-planner | Blocker resolved |

A plan replanned by `dev-planner --replan` returns to `ready` regardless of prior status.

### Review verdict → plan effect
| Verdict | Plan effect |
|---------|------------|
| approved / approved-with-warnings | plan stays `done` |
| changes-required / rejected | plan set back to `in-progress`, blocking findings noted |

---

### Change Request (CR)

```
draft → approved → applied
      ↘ rejected
```

| Transition | Who | Condition |
|-----------|-----|-----------|
| `draft` | ba-cr | CR created from CLI interview, manual file, or auto-generated from KB doc |
| `draft` → `approved` | Human | Approved at the ba-cr approval gate |
| `draft` → `rejected` | Human | Rejected at the ba-cr approval gate |
| `approved` → `applied` | ba-cr | All downstream chains (ba-requirements-gen, dev-planner, arch-gen) completed |

`rejected` is a terminal state. Create a new CR to supersede a rejected one. A CR is never
edited after creation — it is a point-in-time record of intent.

---

## TDD Enforcement

Complexity drives TDD. Each requirement and each plan task carries a complexity rating; the
`default_tdd_threshold` in config (default `M`) decides where TDD becomes mandatory.

| Complexity | Meaning | TDD |
|------------|---------|-----|
| XS | Trivial | after |
| S | Simple | after |
| M | Moderate | tests first |
| L | Complex | tests first |
| XL | High risk | tests first |

For TDD tasks, dev-planner lists the exact tests to write first, and dev-executor writes them
before the implementation (red → green → refactor). dev-code-review checks that the produced
tests match the plan's "tests first" list.

---

## What Each Skill Reads and Writes

| Skill | Reads | Writes |
|-------|-------|--------|
| implr-init | bundled assets | docs/implr structure, config, CLAUDE.md |
| doc-ingest | docs/kb/**, config | kb-index/** (index, cache, digests, syntheses, log) |
| arch-gen | master-synthesis, arch docs, template | docs/ARCHITECTURE.md |
| ba-requirements-gen | syntheses, requirement schema, config | requirements/** |
| dev-planner | approved requirements, ARCHITECTURE.md, DEV-STANDARDS.md, plan schema | plans/** |
| dev-executor | plans, ARCHITECTURE.md, DEV-STANDARDS.md | src/**, tests/**, plan status |
| dev-code-review | plan, requirement, code, ARCHITECTURE.md, DEV-STANDARDS.md, review schema | reviews/** |

Note the clean separation: only doc-ingest writes kb-index; only ba-requirements-gen writes
requirements; only dev-planner writes plans; only dev-executor writes code; only dev-code-review
writes reviews. No skill edits another skill's artefacts except for status fields a downstream
skill is explicitly responsible for (dev-executor and dev-code-review update plan status).

---

## When a New Document Changes an Existing Requirement

The most important real-world scenario: a new document is added to `docs/kb/` after a
requirement has already been planned and possibly implemented.

```
1. /doc-ingest --file docs/kb/new-policy.md
   → detects new doc, rebuilds domain synthesis, flags any contradiction

2. /ba-requirements-gen
   → sees changed domain synthesis
   → updates REQ-F-007: new AC added + open question for contradiction
   → drops status from approved → under-review
   → appends warning to requirements-log.md
   → reports: "REQ-F-007 updated. PLAN-F-007 exists (done). Human review needed."

3. Human reviews REQ-F-007 and the warning
   Option A: new AC is additive, existing code handles it
             → set status: approved; no re-planning needed
   Option B: new policy changes described behaviour
             → set status: approved; run /dev-planner --replan REQ-F-007

4. /dev-planner --replan REQ-F-007    (only if Option B)
5. /dev-executor PLAN-F-007           (implements the delta)
6. /dev-code-review PLAN-F-007        (reviews)
```

Key rules:
- ba-requirements-gen never drops an `approved` requirement back to `draft` — only to
  `under-review`, preserving the review history
- dev-planner never automatically invalidates a plan — it adds a visible warning and leaves
  the decision to the human
- Only material changes (new ACs, changed behaviour) trigger `under-review`; minor
  clarifications leave `approved` untouched

---

## Log Files vs Index Files

Two files that sound similar but serve distinct purposes:

**`requirements-index.md`** — current-state register:
- What requirements exist right now: IDs, titles, statuses, dependencies, linked plans
- Traceability matrix (source document → requirement IDs)
- "Needs Human Review" section for open questions and unresolved contradictions
- Read by: dev-planner (to find approved requirements), humans tracking status

**`requirements-log.md`** — append-only history:
- Every ba-requirements-gen run, timestamped
- Which domain syntheses were processed and their checksums at processing time
- Which requirements were created or updated in each run
- Contradictions surfaced and post-implementation update warnings
- Read by: ba-requirements-gen as its incremental gate — without it, ba-requirements-gen
  cannot know which synthesis checksums it last processed and would reprocess everything

The same pattern applies to `digest-log.md` (owned by doc-ingest): it is the history record,
not the index. `index.md` is the current state of the KB file registry.

---

## Extending implr

To add a skill (for example the planned `ba-jira-populate`):

1. Create `skills/<name>/SKILL.md` with frontmatter (name, description with trigger phrases).
2. If it needs schemas or templates, add them under `skills/implr-init/assets/` so implr-init
   and the installer place them in `docs/implr/`.
3. Reference `docs/implr/` paths from the SKILL.md — never bundle data inside the skill.
4. Add the skill to the installer's skill list and to the README skills table.
5. Validate before release.

Keep skills thin (instructions only) and the schemas authoritative (data structures live in one
place that every skill references).

---

## Change Requests

A Change Request (CR) is the structured path for amending requirements after they have
already been generated — whether to correct a constraint, reduce scope, introduce a new rule,
or override a prior decision.

CRs live in `docs/kb/change-requests/` as first-class KB documents. They are ingested,
digested, and synthesised by `doc-ingest` exactly like any other source document. Every
requirement update triggered by a CR is traceable: the CR file is added to the requirement's
`source_docs` list.

### CLI path (most common)

```
1. Tell ba-cr what you want to change (free-form statement)
   /ba-cr  →  "I want to limit Azure costs to $20–50/month"

2. ba-cr interviews you for any missing required fields, then creates:
   docs/kb/change-requests/CR-NNN-slug.md

3. ba-cr chains /doc-ingest --file <CR-file> automatically

4. ba-cr runs impact analysis across all requirements
   → presents impact report with confirmed-affected requirements and their plans

5. You approve: all / selected / none

6. On approval, ba-cr chains in order:
   /ba-requirements-gen --reprocess <CR-file>   (for each approved requirement)
   /dev-planner --replan REQ-NNN                (for each with an existing plan)
   /arch-gen --update                           (only if architecture domain touched)
```

### Manual-file path

Use when you prefer to author the CR file yourself (e.g. drafting offline, team review).

```
1. Copy docs/implr/templates/cr-template.md → docs/kb/change-requests/CR-NNN-slug.md
2. Fill in the required fields (title, change_type, before, after, rationale)
3. /doc-ingest
   → doc-ingest detects the new CR file and prints:
     ⚠️  New change request detected: CR-NNN-slug.md
         Run /ba-cr --file docs/kb/change-requests/CR-NNN-slug.md to analyse impact and apply.
4. /ba-cr --file docs/kb/change-requests/CR-NNN-slug.md
   → skips the interview; continues from doc-ingest chain onward
```

**Important:** doc-ingest never auto-chains ba-cr. Step 4 is always an explicit user action.

### KB-document path (--ingest-file)

Use when you've added a new or updated document to the KB that logically changes existing
requirements — without writing a CR file yourself.

```
1. Add the new document to docs/kb/
   (e.g. a new version of a pricing policy, a revised architecture spec)

2. /ba-cr --ingest-file docs/kb/{your-new-doc}.md

   ba-cr automatically:
   a. Runs /doc-ingest --file on the new document
   b. Reads the domain synthesis diff to understand what changed
   c. Auto-generates CR-NNN with source: kb-document
   d. Runs /doc-ingest --file on the CR file itself
   e. Runs impact analysis → presents impact report
   f. Waits for your approval (same gate as CLI path)
   g. On approval: chains ba-requirements-gen --reprocess, dev-planner --replan,
      optionally arch-gen --update

Alternatively, run /doc-ingest first (to refresh the KB), then use the hint it prints:
   💡 New KB document ingested: {filename}
      If this document changes existing requirements, run:
      /ba-cr --ingest-file {original_path}
```

All three paths produce the same CR artefact and cr-log entry. The only difference is how
the CR content is captured: interview (cli-direct), manual file, or digest extraction
(kb-document).

### CR artefacts

| File | Purpose |
|------|---------|
| `docs/kb/change-requests/CR-NNN-slug.md` | The CR document (source of truth) |
| `docs/implr/requirements/cr-index.md` | Current-state register of all CRs |
| `docs/implr/requirements/cr-log.md` | Append-only history of ba-cr runs |
| `docs/implr/schemas/cr-schema.md` | Canonical CR, cr-index, cr-log structures |
| `docs/implr/templates/cr-template.md` | Blank template for manual CR authoring |
