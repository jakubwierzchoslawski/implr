# Phase: extract

Extraction runs **inline** in the orchestrator via `Bash` — no subagent is dispatched.

Follow the extraction table and rules defined in `SKILL.md` Phase 3. Run commands directly
with the `Bash` tool. Cap parallel `Bash` calls at 5 per wave.

Write extracted text to `docs/implr/kb-index/cache/<slug>.txt`.

If a command exits non-zero or a required tool is missing, log
`extract-failed: <file_path> — <error>`, delete any partial cache file, and continue.

## Extraction command table

| Ext | Command (POSIX) | Command (PowerShell) |
|---|---|---|
| md, txt, csv, vtt | `cp "<src>" "docs/implr/kb-index/cache/<slug>.txt"` | `Copy-Item -LiteralPath "<src>" -Destination "docs\implr\kb-index\cache\<slug>.txt" -Force` |
| pdf | `pdftotext "<src>" "docs/implr/kb-index/cache/<slug>.txt"` (fallback: pymupdf) | same |
| docx | `python3 -c "from docx import Document; ..."` | same with `python` |
| xlsx | `python3 -c "from openpyxl import load_workbook; ..."` | same with `python` |
| pptx | `python3 -c "from pptx import Presentation; ..."` | same with `python` |
| odp, odt, ods | `python3 -c "from odf.opendocument import load; from odf.text import P; ..."` | same with `python` |
| png, jpg, jpeg, gif, webp, tiff, bmp | `python3 -c "import pytesseract; from PIL import Image; ..."` (stdout: `sparse`/`ok`) | same with `python` |
| anything else | Mark `format_supported: false`. Skip Phase 4 for this file. |

For image files, capture stdout — the command prints `sparse` (OCR word count < 30) or
`ok`. Record `ocr_sparse: true` in the index entry when `sparse` is printed.
