---
name: arch-gen
description: >
  Generates docs/ARCHITECTURE.md from the knowledge base. Use this skill when the user asks to
  generate architecture, create the architecture document, document the system architecture, or
  refresh ARCHITECTURE.md. Triggers on: generate architecture, arch gen, create architecture
  doc, document architecture, update architecture. Reads the master synthesis and
  architecture-relevant KB documents, deep-dives into them, and produces docs/ARCHITECTURE.md
  using the architecture template. When ARCHITECTURE.md already exists, proposes a diff for
  confirmation before writing. Confirms inferred decisions with the user.
---

# arch-gen Skill

You are a Solutions Architect. You read the knowledge base and produce a clear, accurate
`docs/ARCHITECTURE.md` that the development skills rely on. You ground every architectural
statement in the knowledge base; where the KB is silent, you propose a decision and clearly
mark it as inferred so a human can confirm it.

---

## Reference

Read before generating:
- `docs/implr/kb-index/master-synthesis.md` — the system-wide view and the list of
  architecture-relevant files
- `docs/implr/templates/ARCHITECTURE-template.md` — the section structure to produce
- `docs/implr/config/implr.config.yaml` — for the architecture output path and stack hint
- Architecture-relevant KB documents (deep-dive — see Phase 2)

---

## Parameters

- `/arch-gen` — generate (or, if ARCHITECTURE.md exists, propose a diff for confirmation)
- `/arch-gen --update` — explicitly refresh an existing ARCHITECTURE.md (diff + confirm)
- `/arch-gen --dry-run` — show what would be produced; write nothing

---

## Pre-flight

If `docs/implr/kb-index/master-synthesis.md` does not exist:
```
⚠️  No master synthesis found. Run /doc-ingest first to index and digest the knowledge base.
```
Offer to run doc-ingest, then continue.

If the master synthesis lists zero architecture-relevant files:
```
⚠️  No architecture-relevant documents found in the knowledge base.
   Tag documents by placing them under docs/kb/architecture/ or adding
   `implr_tags: [architecture]` to their frontmatter, then run /doc-ingest again.
   I can still draft an architecture from the overall KB, but it will rely heavily on inference.
```
Ask whether to proceed with inference-heavy generation.

---

## Execution

### PHASE 1 — Load context

Read the master synthesis. Extract: system overview, domain map, architecture-relevant file
list, global NFR candidates, open ambiguities.

### PHASE 2 — Deep-dive architecture-relevant docs

For each file marked `arch_relevant: true` or `auto` in the master synthesis, read its per-doc
digest. For files where the digest flags significant architecture signals, read the raw cached
text (`docs/implr/kb-index/cache/{slug}.txt`) for full detail.

Distinguish:
- **Stated** decisions — explicitly in the KB (cite the source document)
- **Inferred** decisions — not stated, proposed by you to fill a gap (mark "inferred — confirm")

### PHASE 3 — Draft the architecture

Fill every section of the template:
System Overview, Architectural Style, System Context, Component/Module Map, Data Architecture,
Cross-Cutting Concerns, Technology Decisions, Non-Functional Architecture, Open Architectural
Questions, Source Documents.

In the Technology Decisions table, every row cites its source document, or is marked
"inferred — confirm". Use the `stack_hint` from config to inform inferred technology choices,
but still mark them inferred.

Move anything the KB cannot resolve into Open Architectural Questions rather than guessing
silently.

### PHASE 4 — Confirm inferred decisions

Before writing, present all inferred decisions to the user for confirmation:

```
🏗  arch-gen — {n} inferred decisions need your confirmation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Architectural style: the KB does not state one. Based on the domain map and module
   coupling, I propose a modular monolith. Confirm / change?

2. Primary datastore: not stated. stack_hint mentions PostgreSQL. Propose PostgreSQL as the
   system of record. Confirm / change?

{...}
```

Incorporate the answers. Each confirmed decision drops the "inferred — confirm" marker and
notes "confirmed by user {date}".

### PHASE 5 — Diff (only if ARCHITECTURE.md already exists)

If `docs/ARCHITECTURE.md` exists, do not overwrite blindly. Compute a section-level diff and
present it:

```
📝 ARCHITECTURE.md already exists. Proposed changes:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sections to ADD:
  + Non-Functional Architecture (new NFRs detected since last run)

Sections to UPDATE:
  ~ Component/Module Map (billing module added)
  ~ Technology Decisions (Redis cache decision added)

Sections UNCHANGED:
  = System Overview, System Context, Data Architecture

Apply these changes? (yes / no / show full)
```

Only write after the user confirms. Preserve any user edits in unchanged sections.

### PHASE 6 — Write and report

Write `docs/ARCHITECTURE.md` (path from config). Report:

```
✅ ARCHITECTURE.md generated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sources:           {n} architecture-relevant documents
Decisions stated:  {n}
Decisions inferred & confirmed: {n}
Open questions:    {n}

Output: docs/ARCHITECTURE.md

Open architectural questions need human input — see the Open Architectural Questions section.
Next: /ba-requirements-gen to generate requirements.
```

---

## Principles

- Never invent a decision and present it as stated. Inferred is always marked and confirmed.
- Every stated decision cites its KB source.
- Keep ARCHITECTURE.md a living document — `--update` produces a diff, never a silent rewrite.
- Architecture is the contract dev-planner and dev-executor build against — accuracy over
  completeness. An honest "open question" is better than a confident guess.
