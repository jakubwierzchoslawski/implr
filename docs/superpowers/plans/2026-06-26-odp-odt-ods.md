# OpenDocument Format Support (ODP, ODT, ODS) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `odp`, `odt`, and `ods` to the doc-ingest pipeline using the `odfpy` library for text extraction.

**Architecture:** All three OpenDocument formats share a single extraction command that walks paragraph (`P`) elements via a recursive lambda. One shared probe fires when any of the three extensions are in scope. No digester changes — these are text-based formats and `ocr_sparse` does not apply.

**Tech Stack:** Python (`odfpy`), Markdown file edits only — no code files created.

---

## File Map

| File | Change |
|---|---|
| `skills/doc-ingest/SKILL.md` | Add `odp, odt, ods` row to Phase 3 table; add probe bullet |
| `skills/doc-ingest/phases/extract.md` | Add `odp, odt, ods` row |
| `README.md` | Add `odfpy` row to Python libraries table; update 4 supported-format strings |

---

## Task 1: Update SKILL.md — extraction table row

**Files:**
- Modify: `skills/doc-ingest/SKILL.md`

- [ ] **Step 1: Add the `odp, odt, ods` extraction row**

Find this exact text in the Phase 3 extraction table:

```
| pptx | `python3 -c "from pptx import Presentation; prs=Presentation('<src>'); out=open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8'); [out.write('\n'.join(shape.text for shape in slide.shapes if hasattr(shape,'text')) + '\n') for slide in prs.slides]; out.close()"` | same with `python` |
| png, jpg, jpeg, gif, webp, tiff, bmp |
```

Replace with:

```
| pptx | `python3 -c "from pptx import Presentation; prs=Presentation('<src>'); out=open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8'); [out.write('\n'.join(shape.text for shape in slide.shapes if hasattr(shape,'text')) + '\n') for slide in prs.slides]; out.close()"` | same with `python` |
| odp, odt, ods | `python3 -c "from odf.opendocument import load; from odf.text import P; fn=lambda e: ''.join(n.data if hasattr(n,'data') else fn(n) for n in e.childNodes); doc=load('<src>'); open('docs/implr/kb-index/cache/<slug>.txt','w',encoding='utf-8').write('\n'.join(fn(p) for p in doc.getElementsByType(P)))"` | same with `python` |
| png, jpg, jpeg, gif, webp, tiff, bmp |
```

- [ ] **Step 2: Add the probe bullet**

Find this exact text in the probes list:

```
- `python3 -c "import pptx"` — required only when pptx files are in scope
- `python3 -c "import pytesseract; from PIL import Image"` — required only when image files (png, jpg, jpeg, gif, webp, tiff, bmp) are in scope
```

Replace with:

```
- `python3 -c "import pptx"` — required only when pptx files are in scope
- `python3 -c "from odf.opendocument import load; from odf.text import P"` — required only when OpenDocument files (odp, odt, ods) are in scope
- `python3 -c "import pytesseract; from PIL import Image"` — required only when image files (png, jpg, jpeg, gif, webp, tiff, bmp) are in scope
```

- [ ] **Step 3: Verify**

Open `skills/doc-ingest/SKILL.md` and confirm:
- The `odp, odt, ods` row appears between `pptx` and `png, jpg, jpeg, ...` in the Phase 3 table.
- The OpenDocument probe bullet appears between the pptx and pytesseract probes.

- [ ] **Step 4: Commit**

```bash
git add skills/doc-ingest/SKILL.md
git commit -m "feat(doc-ingest): add odp/odt/ods to Phase 3 extraction table and probe"
```

---

## Task 2: Update phases/extract.md — extraction row

**Files:**
- Modify: `skills/doc-ingest/phases/extract.md`

- [ ] **Step 1: Add the `odp, odt, ods` row**

Find this exact text:

```
| pptx | `python3 -c "from pptx import Presentation; ..."` | same with `python` |
| png, jpg, jpeg, gif, webp, tiff, bmp | `python3 -c "import pytesseract; from PIL import Image; ..."` (stdout: `sparse`/`ok`) | same with `python` |
```

Replace with:

```
| pptx | `python3 -c "from pptx import Presentation; ..."` | same with `python` |
| odp, odt, ods | `python3 -c "from odf.opendocument import load; from odf.text import P; ..."` | same with `python` |
| png, jpg, jpeg, gif, webp, tiff, bmp | `python3 -c "import pytesseract; from PIL import Image; ..."` (stdout: `sparse`/`ok`) | same with `python` |
```

- [ ] **Step 2: Verify**

Open `skills/doc-ingest/phases/extract.md` and confirm the `odp, odt, ods` row appears between `pptx` and `png, jpg, jpeg, ...`.

- [ ] **Step 3: Commit**

```bash
git add skills/doc-ingest/phases/extract.md
git commit -m "feat(doc-ingest): add odp/odt/ods row to extract.md"
```

---

## Task 3: Update README.md — library table and format strings

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the `odfpy` row to the Python libraries table**

Find this exact text:

```
| Word (`.docx`) | `python-docx` | `pip install python-docx` |
| Images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`) | `Pillow` + `pytesseract` | `pip install Pillow pytesseract` — also requires [Tesseract](https://github.com/tesseract-ocr/tesseract) binary on `PATH` |
```

Replace with:

```
| Word (`.docx`) | `python-docx` | `pip install python-docx` |
| OpenDocument (`.odp`, `.odt`, `.ods`) | `odfpy` | `pip install odfpy` |
| Images (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`) | `Pillow` + `pytesseract` | `pip install Pillow pytesseract` — also requires [Tesseract](https://github.com/tesseract-ocr/tesseract) binary on `PATH` |
```

- [ ] **Step 2: Update the doc-ingest Skills Reference supported formats line**

Find:

```
Supported formats: `md, pdf, docx, xlsx, pptx, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff, bmp` (configurable). Unsupported files are
```

Replace with:

```
Supported formats: `md, pdf, docx, xlsx, pptx, odp, odt, ods, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff, bmp` (configurable). Unsupported files are
```

- [ ] **Step 3: Update the KB Guide "Mix formats freely" line**

Find:

```
- Mix formats freely: `.md`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.txt`, `.vtt`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`.
```

Replace with:

```
- Mix formats freely: `.md`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.odp`, `.odt`, `.ods`, `.csv`, `.txt`, `.vtt`, `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.tiff`, `.bmp`.
```

- [ ] **Step 4: Update the Full Pipeline DOCUMENT step**

Find:

```
   You add .md/.pdf/.docx/.xlsx/.pptx/.csv/.txt/.vtt/.png/.jpg/.jpeg/.gif/.webp/.tiff/.bmp files to docs/kb/
```

Replace with:

```
   You add .md/.pdf/.docx/.xlsx/.pptx/.odp/.odt/.ods/.csv/.txt/.vtt/.png/.jpg/.jpeg/.gif/.webp/.tiff/.bmp files to docs/kb/
```

- [ ] **Step 5: Update `kb_supported_formats` in the Configuration example**

Find:

```
  kb_supported_formats: [md, pdf, docx, xlsx, pptx, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff, bmp]
```

Replace with:

```
  kb_supported_formats: [md, pdf, docx, xlsx, pptx, odp, odt, ods, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff, bmp]
```

- [ ] **Step 6: Verify**

Open `README.md` and confirm all four changes are present:
1. Python libraries table has the `odfpy` row between `python-docx` and `Pillow`.
2. doc-ingest Skills Reference supported formats includes `odp, odt, ods`.
3. KB Guide "Mix formats freely" includes `.odp`, `.odt`, `.ods`.
4. Full Pipeline DOCUMENT step includes `.odp/.odt/.ods`.
5. `kb_supported_formats` config example includes `odp, odt, ods`.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs(readme): add odfpy dep and odp/odt/ods to supported format lists"
```
