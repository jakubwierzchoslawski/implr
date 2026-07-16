# Image Processing for doc-ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add image format support (`png`, `jpg`, `jpeg`, `gif`, `webp`, `tiff`, `bmp`) to the doc-ingest pipeline using OCR in Phase 3 with a vision-fallback in Phase 4 when OCR yields sparse text.

**Architecture:** Phase 3 runs `pytesseract` OCR inline, writes `.txt`, and records `ocr_sparse: true` in the index entry when the extracted word count is below 30. Phase 4 passes `ocr_sparse` in the digester dispatch envelope; the digester reads the original image via the Read tool (multimodal) when the flag is set. No new agents or phases are introduced.

**Tech Stack:** Python (`pytesseract`, `Pillow`), Tesseract binary, Claude Code native image Read.

---

## File Map

| File | Change |
|---|---|
| `skills/doc-ingest/SKILL.md` | Add image row to Phase 3 extraction table; add stdout-capture note; add image probe; add `ocr_sparse` to Phase 4 envelope |
| `skills/doc-ingest/phases/extract.md` | Add missing `pptx` row; add `image` row with stdout note |
| `.claude/agents/doc-ingest-digester.md` | Add `ocr_sparse` to inputs; add vision-fallback logic to Work section |
| `README.md` | Add `Pillow`+`pytesseract` to Python deps table; update supported-formats string in four places |

---

## Task 1: Update SKILL.md — Phase 3 extraction table and tool probe

**Files:**
- Modify: `skills/doc-ingest/SKILL.md`

- [ ] **Step 1: Add the image row and stdout-capture note to the extraction table**

Find this exact text (the last two rows of the table + the cap note):

```
| anything else | Do not extract. Mark the index entry `format_supported: false`. Skip Phase 4 for this file. |

Cap parallel `Bash` calls at 5 (one wave at a time per file batch). Sequence the remainder
into subsequent waves.
```

Replace with:

```
| png, jpg, jpeg, gif, webp, tiff, bmp | `python3 -c "import pytesseract; from PIL import Image; img=Image.open('<src>'); text=pytesseract.image_to_string(img); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write(text); print('sparse' if len(text.split())<30 else 'ok')"` | same; use `python` on Windows if `python3` is absent |
| anything else | Do not extract. Mark the index entry `format_supported: false`. Skip Phase 4 for this file. |

For image files, run the extraction command with **stdout capture**. The command prints
`sparse` or `ok`; record `ocr_sparse: true` in the index entry when `sparse` is printed,
`false` otherwise. No other format uses stdout.

Cap parallel `Bash` calls at 5 (one wave at a time per file batch). Sequence the remainder
into subsequent waves.
```

- [ ] **Step 2: Add the image tool probe**

Find this exact text (last bullet of the probes list):

```
- `python3 -c "import pptx"` — required only when pptx files are in scope
```

Replace with:

```
- `python3 -c "import pptx"` — required only when pptx files are in scope
- `python3 -c "import pytesseract; from PIL import Image"` — required only when image files (png, jpg, jpeg, gif, webp, tiff, bmp) are in scope
```

- [ ] **Step 3: Verify the file reads correctly**

Open `skills/doc-ingest/SKILL.md` and confirm:
- The image row appears between `pptx` and `anything else` in the Phase 3 table.
- The stdout-capture note appears between the table and the "Cap parallel" line.
- The image probe is the last bullet in the probes list.

- [ ] **Step 4: Commit**

```bash
git add skills/doc-ingest/SKILL.md
git commit -m "feat(doc-ingest): add image format support to Phase 3 extraction table and probe"
```

---

## Task 2: Update SKILL.md — Phase 4 dispatch envelope

**Files:**
- Modify: `skills/doc-ingest/SKILL.md`

- [ ] **Step 1: Add `ocr_sparse` to the Phase 4 scope**

Find this exact text:

```
For each successfully extracted file, dispatch `doc-ingest-digester` with scope
`{slug, cache_path, source_path, domain}`. Cap parallelism at 5.
```

Replace with:

```
For each successfully extracted file, dispatch `doc-ingest-digester` with scope
`{slug, cache_path, source_path, domain, ocr_sparse}`. Cap parallelism at 5.

`ocr_sparse` is `true` when the image extraction command printed `sparse` (OCR word count
< 30); `false` for all other formats and for image files where OCR produced ≥ 30 words.
Always pass the field; use `false` for non-image files.
```

- [ ] **Step 2: Verify**

Open `skills/doc-ingest/SKILL.md` and confirm `ocr_sparse` appears in the Phase 4 scope
block with its definition.

- [ ] **Step 3: Commit**

```bash
git add skills/doc-ingest/SKILL.md
git commit -m "feat(doc-ingest): add ocr_sparse to Phase 4 digester dispatch envelope"
```

---

## Task 3: Update phases/extract.md

**Files:**
- Modify: `skills/doc-ingest/phases/extract.md`

- [ ] **Step 1: Add the missing `pptx` row and the new image row**

The current table ends with this (find exactly):

```
| xlsx | `python3 -c "from openpyxl import load_workbook; ..."` | same with `python` |
| anything else | Mark `format_supported: false`. Skip Phase 4 for this file. |
```

Replace with:

```
| xlsx | `python3 -c "from openpyxl import load_workbook; ..."` | same with `python` |
| pptx | `python3 -c "from pptx import Presentation; ..."` | same with `python` |
| png, jpg, jpeg, gif, webp, tiff, bmp | `python3 -c "import pytesseract; from PIL import Image; ..."` (stdout: `sparse`/`ok`) | same with `python` |
| anything else | Mark `format_supported: false`. Skip Phase 4 for this file. |

For image files, capture stdout — the command prints `sparse` (OCR word count < 30) or
`ok`. Record `ocr_sparse: true` in the index entry when `sparse` is printed.
```

- [ ] **Step 2: Verify**

Open `skills/doc-ingest/phases/extract.md` and confirm:
- `pptx` row appears between `xlsx` and `png/jpg/...`.
- Image row appears between `pptx` and `anything else`.
- The stdout note appears after the table.

- [ ] **Step 3: Commit**

```bash
git add skills/doc-ingest/phases/extract.md
git commit -m "feat(doc-ingest): sync extract.md — add pptx row and image row with stdout note"
```

---

## Task 4: Update doc-ingest-digester.md

**Files:**
- Modify: `.claude/agents/doc-ingest-digester.md`

- [ ] **Step 1: Add `ocr_sparse` to the Inputs block**

Find this exact text:

```
```
slug: <slug>
cache_path: docs/implr/kb-index/cache/<slug>.txt
source_path: docs/kb/<domain>/<name>.<ext>
domain: <domain>
```
```

Replace with:

```
```
slug: <slug>
cache_path: docs/implr/kb-index/cache/<slug>.txt
source_path: docs/kb/<domain>/<name>.<ext>
domain: <domain>
ocr_sparse: true | false
```
```

- [ ] **Step 2: Add vision-fallback logic to the Work section**

Find this exact text (the opening of the Work section):

```
Read the cache file. Produce a digest with all schema-required sections: business rules,
system behaviours, data entities, integration points, NFR signals, ambiguities,
architecture signals.
```

Replace with:

```
Read the cache file. Produce a digest with all schema-required sections: business rules,
system behaviours, data entities, integration points, NFR signals, ambiguities,
architecture signals.

**If `ocr_sparse` is `true`:** the source is an image whose OCR text was sparse (< 30
words). After reading `cache_path`, also `Read(source_path)` — the Read tool renders
images natively. Produce the digest from the combined OCR text and visual content. Add an
`<!-- extraction: vision-assisted -->` comment on the line after the frontmatter closing
`---` so consumers can identify vision-derived digests. If `ocr_sparse` is `false` or
absent, proceed with cache text only.
```

- [ ] **Step 3: Verify**

Open `.claude/agents/doc-ingest-digester.md` and confirm:
- `ocr_sparse: true | false` is the last line of the Inputs code block.
- The `ocr_sparse: true` vision-fallback paragraph follows immediately after the first
  paragraph of the Work section.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/doc-ingest-digester.md
git commit -m "feat(doc-ingest-digester): accept ocr_sparse; Read source image when OCR is sparse"
```

---

## Task 5: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add image row to the Python libraries table**

Find this exact text:

```
| Word (`.docx`) | `python-docx` | `pip install python-docx` |

Plain-text formats (`.md`, `.txt`, `.csv`, `.vtt`) need no extra libraries. For PDF,
`pdftotext` (from poppler) is tried first; `pymupdf` is the fallback.
```

Replace with:

```
| Word (`.docx`) | `python-docx` | `pip install python-docx` |
| Images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`) | `Pillow` + `pytesseract` | `pip install Pillow pytesseract` — also requires [Tesseract](https://github.com/tesseract-ocr/tesseract) binary on `PATH` |

Plain-text formats (`.md`, `.txt`, `.csv`, `.vtt`) need no extra libraries. For PDF,
`pdftotext` (from poppler) is tried first; `pymupdf` is the fallback. For images, OCR
(pytesseract) runs first; when OCR yields fewer than 30 words the digester uses Claude's
native vision capability on the original file as a fallback.
```

- [ ] **Step 2: Update the supported formats string in the doc-ingest Skills Reference section**

Find:

```
Supported formats: `md, pdf, docx, xlsx, csv, txt, vtt` (configurable). Unsupported files are
registered but not digested.
```

Replace with:

```
Supported formats: `md, pdf, docx, xlsx, pptx, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff, bmp` (configurable). Unsupported files are
registered but not digested.
```

- [ ] **Step 3: Update the "Mix formats freely" line in the KB Guide section**

Find:

```
- Mix formats freely: `.md`, `.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt`, `.vtt`.
```

Replace with:

```
- Mix formats freely: `.md`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.txt`, `.vtt`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`.
```

- [ ] **Step 4: Update the DOCUMENT step in The Full Pipeline section**

Find:

```
   You add .md/.pdf/.docx/.xlsx/.pptx/.csv/.txt/.vtt files to docs/kb/
```

Replace with:

```
   You add .md/.pdf/.docx/.xlsx/.pptx/.csv/.txt/.vtt/.png/.jpg/.jpeg/.gif/.webp/.tiff/.bmp files to docs/kb/
```

- [ ] **Step 5: Update `kb_supported_formats` in the Configuration example**

Find:

```
  kb_supported_formats: [md, pdf, docx, xlsx, csv, txt, vtt]
```

Replace with:

```
  kb_supported_formats: [md, pdf, docx, xlsx, pptx, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff, bmp]
```

- [ ] **Step 6: Verify**

Open `README.md` and confirm all six changes are present:
1. Python libraries table has the image row.
2. Plain-text note paragraph mentions OCR + vision fallback.
3. doc-ingest Skills Reference supported formats string includes image extensions.
4. KB Guide "Mix formats freely" line includes image extensions.
5. Full Pipeline DOCUMENT step includes image extensions.
6. `kb_supported_formats` config example includes image extensions.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs(readme): add image format support — Pillow/pytesseract dep, updated format lists"
```
