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
