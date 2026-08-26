---
name: doc-ingest
description: >
  Indexes and digests the knowledge base under docs/kb/. Use when adding/updating docs,
  refreshing the KB index, or asking to ingest/scan/digest. Default in v3.0 is FULL
  PIPELINE (extract + digest + syntheses + master). Pass --registry-only for fast
  registry-only scan without digesting. Dispatches parallel subagents for extract,
  digest, and per-domain synthesis. Detects contradictions. Incremental.
---

# doc-ingest Skill (v2.0 orchestrator)

You orchestrate the knowledge-base ingest pipeline. Phase 3 extraction runs inline via
`Bash`. Heavy digest and synthesis work runs in dedicated subagents (`doc-ingest-digester`,
`doc-ingest-synthesizer`). You decide scope, dispatch in parallel, aggregate summaries, and
write the index, master synthesis, and log.

## Read first (cache-friendly)

- `docs/implr/schemas/kb-index-schema.md`
- `docs/implr/config/implr.config.yaml`

## Preconditions

- At least one KB source document exists under `docs/kb/`. If none: halt with
  `❌ No KB documents found under docs/kb/. Add source docs first.`

## Parameters

- `/doc-ingest` — **full pipeline** (extract + digest + syntheses + master). New default in v3.0.
- `/doc-ingest --registry-only` — fast scan: updates registry only, no digests or syntheses.
- `/doc-ingest --file <path>` — process one file (full pipeline unless `--registry-only` also passed).
- `/doc-ingest --rebuild` — full pipeline, reprocess everything from scratch.
- `/doc-ingest --dry-run` — report what would change; write nothing.

**Removed in v3.0:** `--digest` is now the default behaviour. The flag is accepted for
backward compatibility (with a deprecation warning) for one minor version, then will error.
If both `--digest` and `--registry-only` are passed, `--registry-only` wins with a warning.

**Renamed from v2.0:** the v2.0 registry-only default now needs explicit `--registry-only`.

## Model resolution

For each dispatch, resolve model from `agents.<agent-name>` in `implr.config.yaml`; fall
back to the agent's `default_model`.

Phase 3 extraction is inline (no subagent), so no model is resolved for it. Phases 4–5
still dispatch `doc-ingest-digester` and `doc-ingest-synthesizer`.

## Execution

### Phase 1 — Scan

Recursively list `docs/kb/`. Capture path, format, domain (first subfolder or `root`),
mtime, md5. Use `find` + `md5sum` (POSIX) or equivalent.

### Phase 2 — Classify against `docs/implr/kb-index/index.md`

NEW / CHANGED / UNCHANGED / REMOVED / UNSUPPORTED per current schema. `--rebuild` forces
all supported to CHANGED. `--file` forces the named file to CHANGED.

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
| pptx | `python3 -c "from pptx import Presentation; prs=Presentation('<src>'); out=open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8'); [out.write('\n'.join(shape.text for shape in slide.shapes if hasattr(shape,'text')) + '\n') for slide in prs.slides]; out.close()"` | same with `python` |
| odp, odt, ods | `python3 -c "from odf.opendocument import load; from odf.text import P; fn=lambda e: ''.join(n.data if hasattr(n,'data') else fn(n) for n in e.childNodes); doc=load('<src>'); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write('\n'.join(fn(p) for p in doc.getElementsByType(P)))"` | same with `python` |
| png, jpg, jpeg, gif, webp, tiff, bmp | `python3 -c "import pytesseract; from PIL import Image; img=Image.open('<src>'); text=pytesseract.image_to_string(img); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write(text); print('sparse' if len(text.split())<30 else 'ok')"` | same; use `python` on Windows if `python3` is absent |
| anything else | Do not extract. Mark the index entry `format_supported: false`. Skip Phase 4 for this file. |

For image files, run the extraction command with **stdout capture**. The command prints
`sparse` or `ok`; record `ocr_sparse: true` in the index entry when `sparse` is printed,
`false` otherwise. No other format uses stdout.

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
- `python3 -c "import pptx"` — required only when pptx files are in scope
- `python3 -c "from odf.opendocument import load; from odf.text import P"` — required only when OpenDocument files (odp, odt, ods) are in scope
- `python3 -c "import pytesseract; from PIL import Image"` — required only when image files (png, jpg, jpeg, gif, webp, tiff, bmp) are in scope

If a probe fails, emit one warning per format and skip all files of that format with
`format_supported: false`. Do not re-probe per file.

### Phase 4 — Per-doc digest (parallel `doc-ingest-digester` dispatches)

**Skip entirely if `--registry-only` was passed.**

For each successfully extracted file, dispatch `doc-ingest-digester` with scope
`{slug, cache_path, source_path, domain, ocr_sparse}`. Cap parallelism at 5.

`ocr_sparse` is `true` when the image extraction command printed `sparse` (OCR word count
< 30); `false` for all other formats and for image files where OCR produced ≥ 30 words.
Always pass the field; use `false` for non-image files.

Collect digest paths, checksums, `arch_relevant` flags.

### Phase 5 — Domain syntheses (parallel `doc-ingest-synthesizer` dispatches)

**Skip entirely if `--registry-only` was passed.**

Determine affected domains: any domain containing a NEW, CHANGED, or REMOVED file.

For each affected domain, dispatch `doc-ingest-synthesizer` with scope
`{domain, digests_glob}`. **Pass the WIDE glob** `docs/implr/kb-index/digests/per-doc/*-digest.md`
— the synthesizer filters by reading each digest's `domain:` frontmatter field, which is
robust to slug collisions across domains. Cap parallelism at 5.

**Compute contradiction fingerprints (orchestrator, has Bash).** The synthesizer returns a
`contradictions_for_fingerprinting` list (five raw fields per contradiction). An LLM cannot
compute SHA-256 reliably, so for each contradiction:

1. Write the five fields (`source_a`, `statement_a`, `source_b`, `statement_b`, `type`) to a
   temp JSON file, e.g. `docs/implr/kb-index/.fp-tmp.json`.
2. Run `implr-validate --fingerprint <tmp>` and capture the printed
   `<ver>:<hash>`.
3. Write the full printed `<ver>:<hash>` into the row's `Fingerprint` column and the `<ver>`
   into `FP-Ver` of the domain synthesis `Contradictions Detected` table.
4. Delete the temp file after the batch (`rm -f`/`Remove-Item`).

Do not hand-compute or guess the hash. `implr-validate --workspace` recomputes each domain
synthesis contradiction fingerprint from its `Source A/Statement A/Source B/Statement B/Type`
cells and fails if a stored `Fingerprint`/`FP-Ver` does not match — so a hand-written hash is
caught.

### Phase 6 — Master synthesis (orchestrator, integrative)

**Skip entirely if `--registry-only` was passed.**

If any domain synthesis changed (new `synthesis_checksum` differs from what
`master-synthesis.md` recorded), rebuild `docs/implr/kb-index/master-synthesis.md`
in-skill:
- System overview narrative
- Domain map table
- Cross-domain contradiction detection
- Global NFR candidates with frequency
- Complete arch-relevant file list
- Open ambiguities

For each cross-domain contradiction, record its two conflicting statements (`Statement A`,
`Statement B`) and sources, then compute its `Fingerprint`/`FP-Ver` the **same way as Phase 5**:
write the five fields (`source_a`, `statement_a`, `source_b`, `statement_b`, `type`) to a temp
JSON file, run `implr-validate --fingerprint <tmp>`, and write the full printed
`<ver>:<hash>` into the `Fingerprint` column and `<ver>` into `FP-Ver`. Do not hand-compute the
hash; `implr-validate --workspace` recomputes and verifies these too.

### Phase 7 — Update `index.md`

Rewrite with current entries; preserve UNCHANGED entries; update CHANGED; add NEW;
remove REMOVED.

### Phase 8 — Update `digest-log.md` (skip if `--dry-run`)

If `docs/implr/kb-index/digest-log.md` does not exist, create it with this header:

```
# digest-log
# Append-only run history for doc-ingest. Newest entry first.
# Format: see kb-index-schema.md § digest-log entry.
```

Then prepend a run entry: timestamp, trigger, mode, files processed with
checksums/actions, domains rebuilt, master rebuild flag, contradictions, warnings.

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
- Extraction command exits non-zero → log `extract-failed: <file_path> — <error>`, delete
  any partial cache file, mark `format_supported: false`, continue with the next file.
- Corrupt/unreadable source file (Read fails before dispatch) → skip with warning, do not
  fail the run.
- `index.md` unparseable → treat all files as NEW and rebuild, warn the user.
- Never leave index/digests/syntheses/log inconsistent. On partial write, report exactly
  what was and was not written.
