# OpenDocument Format Support (ODP, ODT, ODS) — Design

**Date:** 2026-06-26
**Status:** approved

---

## Overview

Add OpenDocument format support to the doc-ingest pipeline: `odp` (presentation), `odt`
(word document), `ods` (spreadsheet). All three formats are handled by the `odfpy` Python
library using a single shared extraction command. No new agents, phases, or flags are
introduced.

---

## Architecture

Three files change. No digester changes — these are text-based formats; `ocr_sparse` does
not apply.

| File | Change |
|---|---|
| `skills/doc-ingest/SKILL.md` | Add `odp, odt, ods` row to Phase 3 extraction table; add probe bullet |
| `skills/doc-ingest/phases/extract.md` | Add `odp, odt, ods` row |
| `README.md` | Add `odfpy` row to Python libraries table; add `odp, odt, ods` to supported-format strings |

---

## Library

`odfpy` (`pip install odfpy`). One library covers all three formats. The package exposes
`odf.opendocument.load` and `odf.text.P`.

---

## Extraction

All three formats share the same extraction command. Each format stores its human-readable
text content inside paragraph (`P`) elements:

- **ODT** — prose paragraphs map directly to `P`
- **ODP** — slide text boxes contain `P` elements
- **ODS** — spreadsheet cells contain `P` elements

**Command (POSIX and PowerShell — same; use `python` on Windows if `python3` is absent):**

```
python3 -c "from odf.opendocument import load; from odf.text import P; fn=lambda e: ''.join(n.data if hasattr(n,'data') else fn(n) for n in e.childNodes); doc=load('<src>'); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write('\n'.join(fn(p) for p in doc.getElementsByType(P)))"
```

The recursive lambda `fn` walks each `P` element's child nodes, collecting text nodes
(`hasattr(n, 'data')`) and recursing into element nodes (spans, links, etc.).

---

## Tool Probe

One probe covers all three formats. It is run once per pipeline run, only when at least
one `odp`, `odt`, or `ods` file is in scope:

```
python3 -c "from odf.opendocument import load; from odf.text import P"
```

If the probe fails, emit one warning and mark all `odp`/`odt`/`ods` files
`format_supported: false`. Do not re-probe per file.

---

## Phase 4 — No Changes

`ocr_sparse` is `false` for all three formats (pass the field as usual; it is already
always passed as `false` for non-image formats). The digester path is unchanged.

---

## Error Handling

Follows the existing pattern for all text-extraction formats:

| Failure | Behaviour |
|---|---|
| Probe fails | One warning; all odp/odt/ods files get `format_supported: false`; skipped for Phase 4 |
| Extraction command exits non-zero | Log `extract-failed: <path> — <error>`; delete partial cache file; `format_supported: false`; continue |

---

## README Changes

### Python libraries table — new row

| Format | Library | Install |
|--------|---------|---------|
| OpenDocument (`.odp`, `.odt`, `.ods`) | `odfpy` | `pip install odfpy` |

### Supported-format strings — updated in four places

Add `odp, odt, ods` to:
1. doc-ingest Skills Reference supported formats line
2. KB Guide "Mix formats freely" line
3. Full Pipeline DOCUMENT step
4. `kb_supported_formats` config example

---

## Supported Formats Summary (after this change)

`md, txt, csv, vtt, pdf, docx, xlsx, pptx, odp, odt, ods, png, jpg, jpeg, gif, webp, tiff, bmp`

---

## Out of Scope

- ODF formula files (`.odf`) — uncommon; can be added later
- Embedded images inside ODT/ODP — handled visually only if the file is re-ingested as an
  image; text extraction suffices for typical document content
- LibreOffice CLI conversion path — not needed; `odfpy` covers all three formats without a
  system binary
