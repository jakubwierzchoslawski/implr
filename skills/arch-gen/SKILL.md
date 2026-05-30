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
