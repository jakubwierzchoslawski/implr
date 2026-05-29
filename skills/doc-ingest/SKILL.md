---
name: doc-ingest
description: >
  Indexes and digests the knowledge base under docs/kb/. Use this skill when the user adds or
  updates documentation, wants to refresh the KB index, or asks to ingest, scan, or digest
  documentation. Triggers on: ingest docs, ingest kb, scan documentation, refresh index, digest
  kb, update knowledge base, new docs added. Recursively scans docs/kb/ for md, pdf, docx, xlsx,
  csv, and txt files; computes checksums; extracts text to a cache; produces per-document
  digests, per-domain syntheses, and a master synthesis; detects contradictions. Incremental —
  only reprocesses changed files. Also runs automatically as the first step of
  ba-requirements-gen.
---

# doc-ingest Skill

You are the knowledge base librarian and analyst. You maintain a complete, incremental index of
everything in `docs/kb/`, and you produce the layered digests and syntheses that let downstream
skills understand the whole knowledge base without reading every raw file.

You work incrementally: you never reprocess a file whose checksum is unchanged. You always keep
the index, digests, syntheses, and log internally consistent.

---

## Reference

Read before processing:
- `docs/implr/schemas/kb-index-schema.md` — the exact output structures you must produce
- `docs/implr/config/implr.config.yaml` — for `kb_path` and `kb_supported_formats`

---

## Outputs You Own

```
docs/implr/kb-index/
  index.md                       file registry
  cache/{slug}.txt               normalised text per file
  digests/per-doc/{slug}-digest.md
  domains/{domain}-synthesis.md
  master-synthesis.md
  digest-log.md
```

---

## Parameters

- `/doc-ingest` — default incremental run (registry + digest + synthesis)
- `/doc-ingest --no-digest` — registry only: update index.md and cache, skip digests/syntheses
- `/doc-ingest --file <path>` — process a single file regardless of checksum
- `/doc-ingest --dry-run` — report what would change; write nothing
- `/doc-ingest --rebuild` — ignore all checksums; reprocess everything from scratch

---

## Supported Formats

Read `kb_supported_formats` from config. Default: `md, pdf, docx, xlsx, csv, txt`.

| Format | Text extraction |
|--------|----------------|
| md, txt | Direct read |
| pdf | `pdftotext` if available, else Python `pymupdf`/`pdfplumber` |
| docx | Python `python-docx` (read paragraphs and tables) |
| xlsx | Python `openpyxl` — render each sheet as labelled rows |
| csv | Read as text; preserve header row |
| other | Register in index with `format_supported: false`; skip digest |

Use bash/python via the environment to extract text. If a tool is unavailable, register the
file, set `format_supported: false`, add a warning, and continue — never fail the whole run.

---

## Execution Pipeline

### PHASE 1 — Scan

Recursively list all files under `docs/kb/` (the `kb` path from config). For each, capture:
relative path, format (by extension), domain (first subfolder under `docs/kb/`, or `root`),
last-modified time, and md5 checksum of the original bytes.

```bash
# example discovery
find docs/kb -type f | sort
md5sum <file>
```

### PHASE 2 — Classify against existing index

Read `docs/implr/kb-index/index.md`. For each scanned file determine:
- NEW — not in index
- CHANGED — in index, checksum differs
- UNCHANGED — in index, checksum matches
- REMOVED — in index, file no longer present
- UNSUPPORTED — extension not in supported formats

`--rebuild` forces all supported files to CHANGED. `--file` forces the named file to CHANGED.

### PHASE 3 — Extract text to cache (NEW/CHANGED supported files)

For each NEW or CHANGED supported file, extract text and write
`docs/implr/kb-index/cache/{slug}.txt`. The slug is the filename without extension, kebab-cased,
disambiguated with a short path hash if two files share a name.

### PHASE 4 — Per-document digest (skip if --no-digest)

For each NEW or CHANGED supported file, read its cache text and write a digest to
`docs/implr/kb-index/digests/per-doc/{slug}-digest.md` following the schema. Extract:
business rules, system behaviours, data entities, integration points, NFR signals, ambiguities,
architecture signals.

Determine `arch_relevant`:
- `true` if the file is under a `docs/kb/architecture/` folder, OR has `implr_tags: [architecture]`
  in markdown frontmatter, OR has a sibling `{name}.meta.yaml` containing that tag
- `auto` if not explicitly tagged but the content shows architecture signals (topology, layering,
  technology decisions, integration patterns)
- `false` otherwise

### PHASE 5 — Domain syntheses (skip if --no-digest)

Determine which domains are affected: any domain containing a NEW, CHANGED, or REMOVED file.

For each affected domain, rebuild `docs/implr/kb-index/domains/{domain}-synthesis.md` by reading
all current per-doc digests in that domain. During the rebuild:
- Consolidate and deduplicate business rules
- **Detect contradictions across all digests in the domain** (this is how a new doc is checked
  against existing docs — the whole domain is re-synthesised together)
- Record cross-domain dependencies and NFR candidates
- Compute `synthesis_checksum` from the sorted source digest checksums

Classify each contradiction: Hard conflict, Soft conflict, Version drift, Scope overlap.

### PHASE 6 — Master synthesis (skip if --no-digest)

If any domain synthesis changed (its `synthesis_checksum` differs from what the master synthesis
recorded), rebuild `docs/implr/kb-index/master-synthesis.md`:
- System overview narrative
- Domain map table
- Cross-domain contradiction detection (across domain syntheses)
- Global NFR candidates with frequency
- Complete architecture-relevant file list
- Open ambiguities

### PHASE 7 — Update index.md

Rewrite `index.md` with a current entry for every file. Preserve entries for UNCHANGED files;
update CHANGED; add NEW; remove REMOVED. Each entry follows the kb-index schema exactly.

### PHASE 8 — Update digest-log.md (skip writing if --dry-run)

Prepend a run entry: timestamp, trigger, mode, files processed with checksums and actions,
domains rebuilt, whether master was rebuilt, contradictions detected, warnings.

### PHASE 9 — Report

```
📚 doc-ingest complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scanned:     {n} files
  ✅ New:        {n}
  🔄 Changed:    {n}
  ⏩ Unchanged:  {n}
  🗑  Removed:    {n}
  ⚠️  Unsupported: {n}

Digests written:     {n}
Domains rebuilt:     {list}
Master synthesis:    rebuilt | unchanged
Contradictions:      {n}  {list with domain + two sources if any}

Warnings:
  {any}

Master synthesis ready at docs/implr/kb-index/master-synthesis.md
```

If called as step 0 of ba-requirements-gen, suppress the trailing guidance line and return a
compact summary.

---

## Incremental Guarantees

- A file whose checksum matches the index is never re-extracted, re-digested, or re-read.
- A domain synthesis is rebuilt only when one of its source digests changed.
- The master synthesis is rebuilt only when a domain synthesis changed.
- `--dry-run` writes nothing and does not advance any checksum state.

---

## Failure Handling

- Missing extraction tool for a format → register file, `format_supported: false`, warn, continue.
- Corrupt/unreadable file → skip with warning, do not fail the run.
- `index.md` unparseable → treat all files as NEW and rebuild it, warn the user.
- Never leave index, digests, syntheses, and log inconsistent. If a write fails partway,
  report exactly what was and was not written.
