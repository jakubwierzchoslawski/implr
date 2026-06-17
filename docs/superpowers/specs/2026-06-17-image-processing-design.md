# Image Processing for doc-ingest — Design

**Date:** 2026-06-17
**Status:** approved

---

## Overview

Add image file support to the doc-ingest pipeline. Supported formats: `png`, `jpg`, `jpeg`,
`gif`, `webp`, `tiff`, `bmp`. Extraction uses OCR (pytesseract + Pillow) in Phase 3; when
OCR yields fewer than 30 words, the doc-ingest-digester uses Claude's native vision capability
to produce a richer digest. File content never enters an LLM during Phase 3.

---

## Architecture

Four files change. No new phases, no new agents.

| File | Change |
|---|---|
| `skills/doc-ingest/SKILL.md` | Add image formats to Phase 3 extraction table; add `ocr_sparse` to Phase 4 dispatch envelope; add image tool probe |
| `skills/doc-ingest/phases/extract.md` | Add image row to extraction table (also sync missing pptx row) |
| `.claude/agents/doc-ingest-digester.md` | Accept `ocr_sparse` in input envelope; Read source image when sparse |
| `README.md` | Add `Pillow` + `pytesseract` row to Python libraries table; note Tesseract binary requirement |

---

## Data Flow

```
image file (png/jpg/jpeg/gif/webp/tiff/bmp)
  │
  ▼ Phase 3 (inline Bash — no LLM)
  pytesseract OCR  →  slug.txt  (even if sparse / empty)
  word count check →  index entry: ocr_sparse: true | false
  │
  ▼ Phase 4 (doc-ingest-digester subagent)
  receives: {slug, cache_path, source_path, domain, ocr_sparse}
  │
  ├─ ocr_sparse: false  →  digest from cache .txt (unchanged path)
  └─ ocr_sparse: true   →  Read(source_path) for vision
                            + OCR text as supplementary context
                            →  richer digest
```

**Sparse threshold:** < 30 words in `.txt` after OCR.

---

## Phase 3 — Extraction

### Extraction table row (new)

| Ext | Command (POSIX) | Command (PowerShell) |
|---|---|---|
| `png, jpg, jpeg, gif, webp, tiff, bmp` | `python3 -c "import pytesseract; from PIL import Image; img=Image.open('<src>'); text=pytesseract.image_to_string(img); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write(text); print('sparse' if len(text.split())<30 else 'ok')"` | same with `python` on Windows if `python3` is absent |

The script prints `sparse` or `ok` to stdout. The orchestrator captures the output and sets
`ocr_sparse: true` in the index entry when `sparse` is printed.

### Tool probe (added once per run, only when image files are in scope)

```
python3 -c "import pytesseract; from PIL import Image"
```

If this probe fails, emit one warning and mark all image files `format_supported: false`. Do
not re-probe per file.

---

## Phase 4 — Digester changes

### Dispatch envelope

```
slug: <slug>
cache_path: docs/implr/kb-index/cache/<slug>.txt
source_path: docs/kb/<domain>/<name>.<ext>
domain: <domain>
ocr_sparse: true | false       ← new field
```

### Digester behaviour

When `ocr_sparse: false`: unchanged. Read `cache_path`, produce digest.

When `ocr_sparse: true`:
1. Read `cache_path` — OCR partial text (useful as a signal even if sparse).
2. `Read(source_path)` — Claude Code's Read tool supports images natively; the digester
   sees the image visually.
3. Produce the digest from both. Note in the digest `extraction_method: vision` so
   consumers know the content is vision-derived.

---

## Error Handling

| Failure | Behaviour |
|---|---|
| `pytesseract` / `Pillow` probe fails | One warning per run; all image files get `format_supported: false`; skipped for Phase 4 |
| OCR command exits non-zero | Log `extract-failed: <path> — <error>`; delete partial cache file; `format_supported: false`; continue |
| Digester's `Read(source_path)` fails on image | Digester proceeds with OCR-only text; logs warning in digest `ambiguities` section |

No new failure modes in Phase 5 or later — digester output is always text.

---

## README Changes

Add to the Python libraries table under "Python libraries for document extraction":

| Format | Library | Install |
|--------|---------|---------|
| Image (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`) | `Pillow` + `pytesseract` | `pip install Pillow pytesseract` (also requires [Tesseract](https://github.com/tesseract-ocr/tesseract) binary) |

Add note: Tesseract must be installed separately as a system binary and be on `PATH`.

---

## Supported Formats Summary (after this change)

`md, txt, csv, vtt, pdf, docx, xlsx, pptx, png, jpg, jpeg, gif, webp, tiff, bmp`

---

## Out of Scope

- Configurable sparse threshold (hardcoded at 30 words; can be a config option in a later iteration)
- PDF page images (PDFs with embedded images are handled by the existing pdftotext/pymupdf path)
- Video frames or animated GIF extraction beyond first-frame OCR
