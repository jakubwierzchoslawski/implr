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
draft → under-review → approved
                     ↘ rejected
approved → superseded (superseded_by points to the replacement)
```
Claude only ever creates `draft`. Humans promote.

### Plan
```
ready → in-progress → done
  ↑                     │
  └── changes-required ◄┘  (set by dev-code-review)
blocked → ready          (once the blocker is resolved)
```

### Review verdict → plan effect
| Verdict | Plan effect |
|---------|------------|
| approved / approved-with-warnings | plan stays `done` |
| changes-required / rejected | plan set back to `in-progress`, blocking findings noted |

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
