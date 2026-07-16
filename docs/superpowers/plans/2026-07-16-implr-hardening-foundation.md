# implr Hardening — Plan 1: Foundation (SSOT + Validation + Drift Fixes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one machine-readable source of truth for implr's four state machines, a dependency-free `implr-validate` that mechanically catches contract drift, a deterministic contradiction fingerprint, and fix the confirmed cache-path / format / status drift — so later plans build on enforced contracts.

**Architecture:** A small standard-library-only Python package (`scripts/implr_validate/`) owns: a restricted-frontmatter-subset parser, a versioned order-independent contradiction fingerprint, JSON contract loaders, the validation checks, and a CLI with `--repo` / `--workspace` / `--fingerprint` modes. The contracts themselves live in `scaffold/schemas/status-vocabulary.json` and `scaffold/schemas/frontmatter-rules.json`; prose schemas reference them and restate no enums. Drift fixes and doc updates follow once the validator can prove them clean.

**Tech Stack:** Python 3.8+ (standard library only — `json`, `re`, `hashlib`, `argparse`, `pathlib`, `sys`, `glob`). Tests use stdlib `unittest` (runnable with `python -m unittest`, zero install). Markdown/YAML-frontmatter artefacts. This plan corresponds to spec `docs/superpowers/specs/2026-07-16-implr-reliability-hardening-design.md`, workstreams **A**, **B**, **D**.

## Global Constraints

- **Zero third-party dependencies** in `scripts/implr_validate/` and its tests. Standard library only. No `pip install`.
- **Python 3.8+ compatible.** No `match` statements, no `tomllib`, no walrus-only constructs that break 3.8.
- Contract data files are **JSON** (stdlib-parseable), not YAML.
- The validator is invoked as `python scripts/implr_validate <mode>` (the directory has a `__main__.py`). The importable package name is `implr_validate` (underscore).
- Commit after every task. Commit messages end with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Work on a branch, not `main` (create `impl/hardening-foundation` before Task 1 if not already on a feature branch).
- Canonical enum values (copied verbatim from the spec — never restate them elsewhere in prose):
  - requirement: `draft | under-review | approved | rejected | superseded`
  - plan: `ready | in-progress | done | blocked | needs-rework`
  - review: `approved | approved-with-warnings | changes-required | rejected`
  - cr: `draft | approved | rejected | applied`

---

## File Structure

**Created:**
- `scaffold/schemas/status-vocabulary.json` — the four state machines (states, transitions).
- `scaffold/schemas/status-vocabulary.md` — thin human pointer to the JSON.
- `scaffold/schemas/frontmatter-rules.json` — required frontmatter fields per artefact type + `--repo` prose-check config.
- `scripts/implr_validate/__init__.py`
- `scripts/implr_validate/__main__.py` — entry point (`python scripts/implr_validate ...`).
- `scripts/implr_validate/frontmatter.py` — restricted-subset frontmatter parser.
- `scripts/implr_validate/fingerprint.py` — versioned contradiction fingerprint.
- `scripts/implr_validate/contracts.py` — load the two JSON contract files.
- `scripts/implr_validate/checks.py` — frontmatter/enum/status, cross-ref, index, and `--repo` prose checks.
- `scripts/implr_validate/cli.py` — argument parsing + mode dispatch + report + exit code.
- `tests/__init__.py`
- `tests/test_frontmatter.py`, `tests/test_fingerprint.py`, `tests/test_contracts.py`, `tests/test_checks.py`, `tests/test_cli.py`
- `tests/fixtures/sample-kb/` — B.4 minimal deterministic fixture + `expected-validate.txt`.

**Modified:**
- `scaffold/schemas/kb-index-schema.md` — cache path `.md`→`.txt`; `format` enum → 18 formats; add contradiction fingerprint algorithm + columns.
- `scaffold/config/implr.config.yaml:21` — `kb_supported_formats` → 18-format list.
- `scaffold/seeds/resolved-contradictions.md` — add `Fingerprint` / `FP-Ver` columns.
- `scaffold/schemas/{requirement,plan,review,cr}-schema.md` — reference `status-vocabulary.json`; keep enum comments consistent (they remain the human-facing display but must match the JSON).
- `skills/doc-ingest/SKILL.md`, `skills/doc-ingest/phases/synthesize-domain.md`, `.claude/agents/doc-ingest-synthesizer.md` — compute fingerprints via `--fingerprint`.
- `skills/ba-requirements-gen/SKILL.md` — Phase 0 keys on `(fingerprint_version, fingerprint)`.
- `README.md`, `docs/WORKFLOW.md` — status vocab, cache path, formats, fingerprint.

---

## Task 1: JSON single source of truth — `status-vocabulary.json` + thin `.md`

**Files:**
- Create: `scaffold/schemas/status-vocabulary.json`
- Create: `scaffold/schemas/status-vocabulary.md`

**Interfaces:**
- Produces: the canonical contract consumed by `contracts.py` (Task 5) and every check. Top-level shape: `{"machines": {"<name>": {"states": [...], "initial": <str|null>, "terminal": [...], "transitions": [{"from","to", ...}]}}}`.

- [ ] **Step 1: Write `status-vocabulary.json`**

```json
{
  "_comment": "SINGLE SOURCE OF TRUTH for implr artefact state machines. Do not restate these enums in any other file; reference this file by name. Validated and consumed by scripts/implr_validate. Human-readable overview: status-vocabulary.md.",
  "machines": {
    "requirement": {
      "states": ["draft", "under-review", "approved", "rejected", "superseded"],
      "initial": "draft",
      "terminal": ["rejected", "superseded"],
      "transitions": [
        {"from": "draft", "to": "under-review"},
        {"from": "under-review", "to": "approved"},
        {"from": "under-review", "to": "rejected"},
        {"from": "approved", "to": "under-review", "note": "reopened by contradictory/correction CR"},
        {"from": "approved", "to": "superseded", "note": "replaced via override CR; superseded_by set"}
      ]
    },
    "plan": {
      "states": ["ready", "in-progress", "done", "blocked", "needs-rework"],
      "initial": "ready",
      "terminal": [],
      "transitions": [
        {"from": "ready", "to": "in-progress"},
        {"from": "in-progress", "to": "done"},
        {"from": "ready", "to": "blocked"},
        {"from": "in-progress", "to": "blocked"},
        {"from": "blocked", "to": "ready"},
        {"from": "done", "to": "in-progress", "note": "review verdict changes-required/rejected"},
        {"from": "done", "to": "needs-rework", "by": "cr-applier", "note": "only cr-applier writes this"},
        {"from": "needs-rework", "to": "ready", "by": "dev-planner --replan", "note": "only exit from needs-rework"}
      ]
    },
    "review": {
      "states": ["approved", "approved-with-warnings", "changes-required", "rejected"],
      "initial": null,
      "terminal": [],
      "transitions": []
    },
    "cr": {
      "states": ["draft", "approved", "rejected", "applied"],
      "initial": "draft",
      "terminal": ["rejected", "applied"],
      "transitions": [
        {"from": "draft", "to": "approved"},
        {"from": "draft", "to": "rejected"},
        {"from": "approved", "to": "applied"}
      ]
    }
  }
}
```

- [ ] **Step 2: Verify the JSON parses**

Run: `python -c "import json; json.load(open('scaffold/schemas/status-vocabulary.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Write the thin human pointer `status-vocabulary.md`**

```markdown
# Status Vocabulary

**Machine-readable source of truth:** `status-vocabulary.json` (this directory).

This is the ONLY place implr defines legal states and transitions for its four artefact state
machines — `requirement`, `plan`, `review`, and `cr`. Every other file — prose schemas,
templates, README, WORKFLOW, agents, SKILLs — must reference this vocabulary by name and MUST
NOT restate an enum value inline. `implr-validate --repo` fails the build if any file hardcodes a
status value that diverges from the JSON.

To read the states and transitions, open `status-vocabulary.json`; each machine lists its
`states`, `initial`, `terminal`, and `transitions` (with the actor that performs each). This
document deliberately does NOT restate the state values — doing so would create exactly the
drift surface the JSON exists to prevent.
```

- [ ] **Step 4: Commit**

```bash
git add scaffold/schemas/status-vocabulary.json scaffold/schemas/status-vocabulary.md
git commit -m "feat(schemas): add machine-readable status-vocabulary as single source of truth"
```

---

## Task 2: `frontmatter-rules.json` — per-type field rules + prose-check config

**Files:**
- Create: `scaffold/schemas/frontmatter-rules.json`

**Interfaces:**
- Produces: `artefact_types` (map of type → `{id_field, id_pattern, status_machine, required[], index_file, path_globs[]}`), `schema_machine_map` (schema/template filename → machine), and `repo_prose_checks` (`banned_tokens[]`, `banned_token_surfaces[]`, `enum_comment_surfaces[]`, `exempt_paths[]`, `enum_check_exempt[]`, `cache_path_surfaces[]`, `canonical_formats[]`). Consumed by `contracts.py` (Task 5) and `checks.py` (Tasks 6–8).

- [ ] **Step 1: Write `frontmatter-rules.json`**

```json
{
  "_comment": "Required frontmatter fields per artefact type and configuration for implr-validate --repo prose checks. Enum values themselves live in status-vocabulary.json; this file only names which machine each artefact/schema uses.",
  "artefact_types": {
    "requirement": {
      "id_field": "req_id",
      "id_pattern": "^REQ-[FN]-[0-9]{3}$",
      "status_machine": "requirement",
      "required": ["req_id", "slug", "title", "type", "status", "complexity", "tdd_required", "source_docs", "created_at", "updated_at"],
      "index_file": "docs/implr/requirements/requirements-index.md",
      "path_globs": ["docs/implr/requirements/functional/*.md", "docs/implr/requirements/non-functional/*.md"]
    },
    "plan": {
      "id_field": "plan_id",
      "id_pattern": "^PLAN-[FN]-[0-9]{3}$",
      "status_machine": "plan",
      "required": ["plan_id", "slug", "title", "linked_requirement", "type", "status", "complexity", "tdd_required", "created_at", "updated_at"],
      "index_file": "docs/implr/plans/plans-index.md",
      "path_globs": ["docs/implr/plans/functional/*.md", "docs/implr/plans/non-functional/*.md"]
    },
    "cr": {
      "id_field": "cr_id",
      "id_pattern": "^CR-[0-9]{3}$",
      "status_machine": "cr",
      "required": ["cr_id", "slug", "title", "status", "change_type", "source", "created_at"],
      "index_file": "docs/implr/requirements/cr-index.md",
      "path_globs": ["docs/kb/change-requests/*.md"]
    },
    "review": {
      "id_field": "review_id",
      "id_pattern": "^REVIEW-[FN]-[0-9]{3}$",
      "status_machine": "review",
      "required": ["review_id", "status"],
      "index_file": "docs/implr/reviews/reviews-index.md",
      "path_globs": ["docs/implr/reviews/REVIEW-*.md"]
    }
  },
  "schema_machine_map": {
    "requirement-schema.md": "requirement",
    "requirement-template.md": "requirement",
    "plan-schema.md": "plan",
    "plan-template.md": "plan",
    "cr-schema.md": "cr",
    "cr-template.md": "cr",
    "review-schema.md": "review",
    "review-template.md": "review"
  },
  "repo_prose_checks": {
    "banned_tokens": [
      {"token": "replan_required", "reason": "retired plan-status marker; use needs-rework"},
      {"token": "impact-analysed", "reason": "never a real CR status; CR states are draft|approved|rejected|applied"}
    ],
    "banned_token_surfaces": ["scaffold/", "skills/", ".claude/agents/", "README.md", "docs/WORKFLOW.md"],
    "enum_comment_surfaces": ["scaffold/schemas/", "scaffold/templates/"],
    "exempt_paths": ["CHANGELOG.md", "docs/superpowers/"],
    "enum_check_exempt": ["scaffold/schemas/status-vocabulary.json", "scaffold/schemas/status-vocabulary.md"],
    "cache_path_surfaces": ["scaffold/schemas/", "skills/", ".claude/agents/", "README.md", "docs/WORKFLOW.md"],
    "canonical_formats": ["md", "pdf", "docx", "xlsx", "pptx", "odp", "odt", "ods", "csv", "txt", "vtt", "png", "jpg", "jpeg", "gif", "webp", "tiff", "bmp"],
    "format_presence_surfaces": ["scaffold/schemas/kb-index-schema.md", "README.md", "skills/doc-ingest/phases/extract.md"],
    "plan_status_misuse_tokens": ["changes-required"]
  }
}
```

Notes: `banned_token_surfaces` is deliberately broad (this is where the review found retired
tokens — README, WORKFLOW, skills, agents). `enum_comment_surfaces` is narrow because the
`status: x  # a | b | c` comment pattern only appears in schemas/templates. `cache_path_surfaces`
now includes README/WORKFLOW so the final "no `.md` cache path anywhere live" goal is a permanent
check, not a one-time grep. `canonical_formats` drives the format checks (exact-match on machine
arrays + presence on `format_presence_surfaces`). `plan_status_misuse_tokens` lists values that
are legal for another machine (e.g. `changes-required` is a review status) but must never appear
in a plan-lifecycle transition context on a doc surface.

- [ ] **Step 2: Verify the JSON parses**

Run: `python -c "import json; json.load(open('scaffold/schemas/frontmatter-rules.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add scaffold/schemas/frontmatter-rules.json
git commit -m "feat(schemas): add frontmatter-rules.json (field rules + repo prose-check config)"
```

---

## Task 3: Restricted-subset frontmatter parser

**Files:**
- Create: `scripts/implr_validate/__init__.py` (empty)
- Create: `scripts/implr_validate/frontmatter.py`
- Test: `tests/__init__.py` (empty), `tests/test_frontmatter.py`

**Interfaces:**
- Produces: `split_frontmatter(text: str) -> tuple[str | None, str]` (returns the raw frontmatter block and the body, or `(None, text)` if absent) and `parse_frontmatter(text: str) -> dict` (parses the restricted subset; raises `FrontmatterError` on out-of-subset content). `FrontmatterError(Exception)`.
- Subset supported: `key: scalar`, `key: "quoted"`, `key:` (empty → `""`), inline lists `key: [a, b]`, block lists (`- item` lines indented under a key), one level of nested mapping (indented `k: v` under a key), and inline objects `{ id: X, reason: "y" }` as block-list items.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_frontmatter.py
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.frontmatter import split_frontmatter, parse_frontmatter, FrontmatterError


class TestSplit(unittest.TestCase):
    def test_no_frontmatter_returns_none(self):
        fm, body = split_frontmatter("# Title\n\ntext\n")
        self.assertIsNone(fm)
        self.assertEqual(body, "# Title\n\ntext\n")

    def test_extracts_block(self):
        fm, body = split_frontmatter("---\na: 1\n---\n# Body\n")
        self.assertEqual(fm, "a: 1")
        self.assertEqual(body, "# Body\n")


class TestParse(unittest.TestCase):
    def test_scalar_and_quoted(self):
        d = parse_frontmatter("---\nreq_id: REQ-F-001\ntitle: \"A Title\"\n---\n")
        self.assertEqual(d["req_id"], "REQ-F-001")
        self.assertEqual(d["title"], "A Title")

    def test_empty_value(self):
        d = parse_frontmatter("---\napproved_at:\n---\n")
        self.assertEqual(d["approved_at"], "")

    def test_inline_list(self):
        d = parse_frontmatter("---\nlabels: [backend, auth]\n---\n")
        self.assertEqual(d["labels"], ["backend", "auth"])

    def test_block_list(self):
        d = parse_frontmatter("---\nsource_docs:\n  - auth-flow.md\n  - session.md\n---\n")
        self.assertEqual(d["source_docs"], ["auth-flow.md", "session.md"])

    def test_nested_mapping(self):
        d = parse_frontmatter("---\njira:\n  id: STOK-1\n  labels: [a, b]\n---\n")
        self.assertEqual(d["jira"], {"id": "STOK-1", "labels": ["a", "b"]})

    def test_inline_object_list(self):
        d = parse_frontmatter("---\ndependencies:\n  - { id: REQ-F-002, reason: \"needs user\" }\n---\n")
        self.assertEqual(d["dependencies"], [{"id": "REQ-F-002", "reason": "needs user"}])

    def test_out_of_subset_raises(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\na:\n  b:\n    c: 1\n---\n")  # two levels of nesting


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_frontmatter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_validate'` (package not created yet).

- [ ] **Step 3: Create the package marker and the parser**

Create empty `scripts/implr_validate/__init__.py` and empty `tests/__init__.py`, then write:

```python
# scripts/implr_validate/frontmatter.py
"""Parser for the restricted YAML-frontmatter subset implr templates produce.
Standard library only. Anything outside the subset is a validation error."""
import re


class FrontmatterError(Exception):
    pass


def split_frontmatter(text):
    """Return (frontmatter_block_or_None, body)."""
    if not text.startswith("---\n") and text != "---\n":
        return None, text
    rest = text[4:]
    end = rest.find("\n---")
    if end == -1:
        raise FrontmatterError("unterminated frontmatter block")
    block = rest[:end]
    after = rest[end + 4:]
    if after.startswith("\n"):
        after = after[1:]
    return block, after


def _scalar(raw):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith("[") and raw.endswith("]"):
        return _inline_list(raw)
    if raw.startswith("{") and raw.endswith("}"):
        return _inline_object(raw)
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    return raw


def _split_top(s):
    """Split on commas not inside quotes/brackets/braces."""
    parts, buf, depth, quote = [], [], 0, None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return [p.strip() for p in parts]


def _inline_list(raw):
    inner = raw[1:-1].strip()
    if inner == "":
        return []
    return [_scalar(p) for p in _split_top(inner)]


def _inline_object(raw):
    inner = raw[1:-1].strip()
    obj = {}
    for pair in _split_top(inner):
        if ":" not in pair:
            raise FrontmatterError("bad inline object: %r" % raw)
        k, v = pair.split(":", 1)
        obj[k.strip()] = _scalar(v)
    return obj


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def parse_frontmatter(text):
    block, _ = split_frontmatter(text)
    if block is None:
        raise FrontmatterError("no frontmatter block")
    lines = [ln for ln in block.split("\n") if ln.strip() != "" and not ln.lstrip().startswith("#")]
    result = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if _indent(line) != 0:
            raise FrontmatterError("unexpected indentation at top level: %r" % line)
        if ":" not in line:
            raise FrontmatterError("expected 'key:' at %r" % line)
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest != "":
            result[key] = _scalar(rest)
            i += 1
            continue
        # rest is empty: could be empty scalar, block list, or nested mapping
        j = i + 1
        children = []
        while j < len(lines) and _indent(lines[j]) >= 2:
            children.append(lines[j])
            j += 1
        if not children:
            result[key] = ""
        elif children[0].lstrip().startswith("- "):
            result[key] = _parse_block_list(children)
        else:
            result[key] = _parse_nested_mapping(children)
        i = j
    return result


def _parse_block_list(children):
    out = []
    for c in children:
        stripped = c.lstrip()
        if not stripped.startswith("- "):
            raise FrontmatterError("mixed block-list content: %r" % c)
        out.append(_scalar(stripped[2:]))
    return out


def _parse_nested_mapping(children):
    base = _indent(children[0])
    out = {}
    for c in children:
        if _indent(c) != base:
            raise FrontmatterError("only one level of nesting allowed: %r" % c)
        if ":" not in c:
            raise FrontmatterError("expected 'key:' in nested mapping: %r" % c)
        k, v = c.strip().split(":", 1)
        out[k.strip()] = _scalar(v)
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_frontmatter -v`
Expected: PASS (7 in `TestParse`, 2 in `TestSplit`).

- [ ] **Step 5: Commit**

```bash
git add scripts/implr_validate/__init__.py scripts/implr_validate/frontmatter.py tests/__init__.py tests/test_frontmatter.py
git commit -m "feat(validate): add restricted-subset frontmatter parser with tests"
```

---

## Task 4: Versioned, order-independent contradiction fingerprint

**Files:**
- Create: `scripts/implr_validate/fingerprint.py`
- Test: `tests/test_fingerprint.py`

**Interfaces:**
- Produces: `FINGERPRINT_VERSION: int = 1`; `contradiction_fingerprint(fields: dict) -> str` returning `"<version>:<16-hex>"`. `fields` must contain `source_a, statement_a, source_b, statement_b, type`. Swapping the A/B pair does not change the result.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fingerprint.py
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.fingerprint import contradiction_fingerprint, FINGERPRINT_VERSION

BASE = {
    "source_a": "spec-v1.md §3.2",
    "statement_a": "Token TTL must be 15 minutes.",
    "source_b": "spec-v2.md §1.4",
    "statement_b": "Token TTL must be 30 minutes",
    "type": "Hard conflict",
}


class TestFingerprint(unittest.TestCase):
    def test_has_version_prefix(self):
        fp = contradiction_fingerprint(BASE)
        self.assertTrue(fp.startswith("%d:" % FINGERPRINT_VERSION))

    def test_deterministic(self):
        self.assertEqual(contradiction_fingerprint(BASE), contradiction_fingerprint(dict(BASE)))

    def test_order_independent(self):
        swapped = {
            "source_a": BASE["source_b"], "statement_a": BASE["statement_b"],
            "source_b": BASE["source_a"], "statement_b": BASE["statement_a"],
            "type": BASE["type"],
        }
        self.assertEqual(contradiction_fingerprint(BASE), contradiction_fingerprint(swapped))

    def test_normalization_ignores_whitespace_case_trailing_punct(self):
        noisy = dict(BASE)
        noisy["statement_a"] = "  token  TTL must be 15 MINUTES  "
        self.assertEqual(contradiction_fingerprint(BASE), contradiction_fingerprint(noisy))

    def test_changed_statement_changes_fingerprint(self):
        changed = dict(BASE)
        changed["statement_a"] = "Token TTL must be 10 minutes."
        self.assertNotEqual(contradiction_fingerprint(BASE), contradiction_fingerprint(changed))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_fingerprint -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_validate.fingerprint'`.

- [ ] **Step 3: Write the implementation**

```python
# scripts/implr_validate/fingerprint.py
"""Deterministic, versioned, order-independent contradiction fingerprint.
An LLM cannot compute SHA-256 reliably; this is the canonical implementation that
doc-ingest invokes (via `python scripts/implr_validate --fingerprint`) and that
`--workspace` validation recomputes to verify stored fingerprints."""
import hashlib
import json
import re

FINGERPRINT_VERSION = 1


def _normalize(value):
    s = str(value).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:!?")
    return s


def contradiction_fingerprint(fields):
    for k in ("source_a", "statement_a", "source_b", "statement_b", "type"):
        if k not in fields:
            raise KeyError("missing fingerprint field: %s" % k)
    sides = sorted(
        [
            {"source": _normalize(fields["source_a"]), "statement": _normalize(fields["statement_a"])},
            {"source": _normalize(fields["source_b"]), "statement": _normalize(fields["statement_b"])},
        ],
        key=lambda d: (d["source"], d["statement"]),
    )
    payload = {"version": FINGERPRINT_VERSION, "type": _normalize(fields["type"]), "sides": sides}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return "%d:%s" % (FINGERPRINT_VERSION, digest[:16])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_fingerprint -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/implr_validate/fingerprint.py tests/test_fingerprint.py
git commit -m "feat(validate): add versioned order-independent contradiction fingerprint"
```

---

## Task 5: Contract loaders

**Files:**
- Create: `scripts/implr_validate/contracts.py`
- Test: `tests/test_contracts.py`

**Interfaces:**
- Consumes: `scaffold/schemas/status-vocabulary.json`, `scaffold/schemas/frontmatter-rules.json` (Tasks 1–2).
- Produces: `load_contracts(schema_dir: str) -> Contracts`. `Contracts` exposes `machines: dict`, `artefact_types: dict`, `schema_machine_map: dict`, `repo_prose_checks: dict`, and helper `states_for(machine: str) -> set[str]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_contracts.py
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.contracts import load_contracts

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "scaffold", "schemas")


class TestContracts(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def test_plan_states(self):
        self.assertEqual(
            self.c.states_for("plan"),
            {"ready", "in-progress", "done", "blocked", "needs-rework"},
        )

    def test_requirement_type_has_status_machine(self):
        self.assertEqual(self.c.artefact_types["requirement"]["status_machine"], "requirement")

    def test_banned_tokens_present(self):
        tokens = {b["token"] for b in self.c.repo_prose_checks["banned_tokens"]}
        self.assertIn("replan_required", tokens)
        self.assertIn("impact-analysed", tokens)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_contracts -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_validate.contracts'`.

- [ ] **Step 3: Write the implementation**

```python
# scripts/implr_validate/contracts.py
"""Load the JSON contract files (standard library only)."""
import json
import os


class Contracts(object):
    def __init__(self, vocab, rules):
        self.machines = vocab["machines"]
        self.artefact_types = rules["artefact_types"]
        self.schema_machine_map = rules["schema_machine_map"]
        self.repo_prose_checks = rules["repo_prose_checks"]

    def states_for(self, machine):
        return set(self.machines[machine]["states"])


def load_contracts(schema_dir):
    with open(os.path.join(schema_dir, "status-vocabulary.json"), encoding="utf-8") as f:
        vocab = json.load(f)
    with open(os.path.join(schema_dir, "frontmatter-rules.json"), encoding="utf-8") as f:
        rules = json.load(f)
    return Contracts(vocab, rules)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_contracts -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/implr_validate/contracts.py tests/test_contracts.py
git commit -m "feat(validate): add JSON contract loaders"
```

---

## Task 6: Workspace checks — frontmatter fields, enums, status legality

**Files:**
- Create: `scripts/implr_validate/checks.py`
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: `parse_frontmatter`/`FrontmatterError` (Task 3), `Contracts` (Task 5).
- Produces: `Finding(level: str, path: str, message: str)` (namedtuple-like: attributes `level`, `path`, `message`); `check_artefact_file(path: str, atype: str, contracts) -> list[Finding]`. `level` is `"error"`. An artefact is valid when its frontmatter parses, all `required` fields are present, its `id_field` matches `id_pattern`, and its `status` is in `states_for(status_machine)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_checks.py
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.contracts import load_contracts
from implr_validate.checks import check_artefact_file

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "scaffold", "schemas")

VALID_REQ = """---
req_id: REQ-F-001
slug: user-password-reset
title: "User Password Reset"
type: functional
status: approved
complexity: M
tdd_required: true
source_docs:
  - auth-flow.md
created_at: 2026-01-01T00:00:00Z
updated_at: 2026-01-01T00:00:00Z
---
# body
"""


def _write(tmp, text):
    p = os.path.join(tmp, "REQ-F-001-x.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


class TestCheckArtefact(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def test_valid_requirement_has_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            findings = check_artefact_file(_write(tmp, VALID_REQ), "requirement", self.c)
            self.assertEqual(findings, [])

    def test_illegal_status_flagged(self):
        bad = VALID_REQ.replace("status: approved", "status: replan_required")
        with tempfile.TemporaryDirectory() as tmp:
            findings = check_artefact_file(_write(tmp, bad), "requirement", self.c)
            self.assertTrue(any("status" in f.message and "replan_required" in f.message for f in findings))

    def test_missing_required_field_flagged(self):
        bad = VALID_REQ.replace("complexity: M\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            findings = check_artefact_file(_write(tmp, bad), "requirement", self.c)
            self.assertTrue(any("complexity" in f.message for f in findings))

    def test_bad_id_pattern_flagged(self):
        bad = VALID_REQ.replace("req_id: REQ-F-001", "req_id: REQ-F-1")
        with tempfile.TemporaryDirectory() as tmp:
            findings = check_artefact_file(_write(tmp, bad), "requirement", self.c)
            self.assertTrue(any("req_id" in f.message for f in findings))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_checks -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_validate.checks'`.

- [ ] **Step 3: Write the implementation**

```python
# scripts/implr_validate/checks.py
"""Validation checks. Standard library only."""
import os
import re

from .frontmatter import parse_frontmatter, FrontmatterError


class Finding(object):
    def __init__(self, level, path, message):
        self.level = level
        self.path = path
        self.message = message

    def __repr__(self):
        return "%s: %s: %s" % (self.level, self.path, self.message)

    def __eq__(self, other):
        return (self.level, self.path, self.message) == (other.level, other.path, other.message)


def check_artefact_file(path, atype, contracts):
    spec = contracts.artefact_types[atype]
    findings = []
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        fm = parse_frontmatter(text)
    except FrontmatterError as e:
        return [Finding("error", path, "frontmatter parse error: %s" % e)]
    for field in spec["required"]:
        if field not in fm or fm[field] == "":
            findings.append(Finding("error", path, "missing required field: %s" % field))
    idf = spec["id_field"]
    if idf in fm and not re.match(spec["id_pattern"], str(fm[idf])):
        findings.append(Finding("error", path, "%s %r does not match %s" % (idf, fm[idf], spec["id_pattern"])))
    if "status" in fm and fm["status"] != "":
        legal = contracts.states_for(spec["status_machine"])
        if fm["status"] not in legal:
            findings.append(Finding("error", path, "illegal status %r (legal: %s)" % (fm["status"], sorted(legal))))
    return findings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_checks -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/implr_validate/checks.py tests/test_checks.py
git commit -m "feat(validate): add artefact frontmatter/enum/status checks"
```

---

## Task 7: Workspace checks — cross-references & index agreement

**Files:**
- Modify: `scripts/implr_validate/checks.py`
- Modify: `tests/test_checks.py`

**Interfaces:**
- Consumes: `Contracts`, `Finding`, `check_artefact_file` (Task 6).
- Produces: `check_workspace(root: str, contracts) -> list[Finding]`. Discovers artefacts via each type's `path_globs`, runs `check_artefact_file` on each, then verifies: (a) plan `linked_requirement` resolves to an existing requirement; (b) `PLAN-x-NNN` number matches its linked requirement number; (c) requirement `superseded_by` (when set) resolves to an existing requirement; (d) **index agreement** — for each type with an `index_file`, the set of artefact ids referenced in the index equals the set of discovered artefact ids (both a missing-from-index and a phantom-in-index id are findings).

- [ ] **Step 1: Write the failing tests (append to `tests/test_checks.py`)**

```python
# append to tests/test_checks.py
from implr_validate.checks import check_workspace

VALID_PLAN = """---
plan_id: PLAN-F-001
slug: user-password-reset
title: "Impl"
linked_requirement: REQ-F-001
type: functional
status: ready
complexity: M
tdd_required: true
created_at: 2026-01-01T00:00:00Z
updated_at: 2026-01-01T00:00:00Z
---
# body
"""

REQ_INDEX = "# Requirements Index\n\n| ID | ... |\n| REQ-F-001 | ok |\n"
PLAN_INDEX = "# Plans Index\n\n| ID | ... |\n| PLAN-F-001 | ok |\n"


def _mk_workspace(root, req_index=REQ_INDEX, plan_index=PLAN_INDEX, with_plan=True):
    req_dir = os.path.join(root, "docs", "implr", "requirements", "functional")
    plan_dir = os.path.join(root, "docs", "implr", "plans", "functional")
    os.makedirs(req_dir)
    os.makedirs(plan_dir)
    with open(os.path.join(req_dir, "REQ-F-001-x.md"), "w", encoding="utf-8") as f:
        f.write(VALID_REQ)
    with open(os.path.join(root, "docs", "implr", "requirements", "requirements-index.md"), "w", encoding="utf-8") as f:
        f.write(req_index)
    if with_plan:
        with open(os.path.join(plan_dir, "PLAN-F-001-x.md"), "w", encoding="utf-8") as f:
            f.write(VALID_PLAN)
        with open(os.path.join(root, "docs", "implr", "plans", "plans-index.md"), "w", encoding="utf-8") as f:
            f.write(plan_index)
    return req_dir, plan_dir


class TestWorkspace(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def test_valid_workspace_clean(self):
        with tempfile.TemporaryDirectory() as root:
            _mk_workspace(root)
            self.assertEqual(check_workspace(root, self.c), [])

    def test_dangling_linked_requirement_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            _mk_workspace(root, with_plan=False)
            plan_dir = os.path.join(root, "docs", "implr", "plans", "functional")
            dangling = VALID_PLAN.replace("linked_requirement: REQ-F-001", "linked_requirement: REQ-F-099")
            with open(os.path.join(plan_dir, "PLAN-F-001-x.md"), "w", encoding="utf-8") as f:
                f.write(dangling)
            with open(os.path.join(root, "docs", "implr", "plans", "plans-index.md"), "w", encoding="utf-8") as f:
                f.write(PLAN_INDEX)
            findings = check_workspace(root, self.c)
            self.assertTrue(any("REQ-F-099" in f.message for f in findings))

    def test_dangling_superseded_by_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            _mk_workspace(root, with_plan=False)
            req = os.path.join(root, "docs", "implr", "requirements", "functional", "REQ-F-001-x.md")
            with open(req, encoding="utf-8") as f:
                text = f.read()
            with open(req, "w", encoding="utf-8") as f:
                f.write(text.replace("status: approved", "status: superseded\nsuperseded_by: REQ-F-777"))
            findings = check_workspace(root, self.c)
            self.assertTrue(any("REQ-F-777" in f.message for f in findings))

    def test_index_missing_id_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            # index omits REQ-F-001 that exists on disk
            _mk_workspace(root, req_index="# Requirements Index\n\n(empty)\n", with_plan=False)
            findings = check_workspace(root, self.c)
            self.assertTrue(any("REQ-F-001" in f.message and "index" in f.message.lower() for f in findings))

    def test_index_phantom_id_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            # index lists REQ-F-050 with no file
            _mk_workspace(root, req_index="# Requirements Index\n\n| REQ-F-001 | ok |\n| REQ-F-050 | phantom |\n", with_plan=False)
            findings = check_workspace(root, self.c)
            self.assertTrue(any("REQ-F-050" in f.message and "index" in f.message.lower() for f in findings))
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `python -m unittest tests.test_checks -v`
Expected: FAIL — `ImportError: cannot import name 'check_workspace'`.

- [ ] **Step 3: Add the implementation to `checks.py`**

```python
# append to scripts/implr_validate/checks.py
import glob


def _frontmatter_or_none(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return parse_frontmatter(text)
    except FrontmatterError:
        return None


def check_workspace(root, contracts):
    findings = []
    ids_by_type = {}          # atype -> set of ids found on disk
    plans = []                # (path, fm)
    requirements = []         # (path, fm)
    for atype, spec in contracts.artefact_types.items():
        found = set()
        for pattern in spec["path_globs"]:
            for path in glob.glob(os.path.join(root, pattern.replace("/", os.sep))):
                findings.extend(check_artefact_file(path, atype, contracts))
                fm = _frontmatter_or_none(path)
                if fm is None:
                    continue
                idv = fm.get(spec["id_field"], "")
                if idv:
                    found.add(idv)
                if atype == "plan":
                    plans.append((path, fm))
                if atype == "requirement":
                    requirements.append((path, fm))
        ids_by_type[atype] = found

    req_ids = ids_by_type.get("requirement", set())

    # (a)/(b) plan linkage + numbering
    for path, fm in plans:
        linked = fm.get("linked_requirement", "")
        if linked and linked not in req_ids:
            findings.append(Finding("error", path, "linked_requirement %s does not exist" % linked))
        pid = fm.get("plan_id", "")
        if linked and pid[-3:].isdigit() and linked[-3:].isdigit() and pid[-3:] != linked[-3:]:
            findings.append(Finding("error", path, "plan %s number does not match linked %s" % (pid, linked)))

    # (c) superseded_by resolution
    for path, fm in requirements:
        sb = fm.get("superseded_by", "")
        if sb and sb not in req_ids:
            findings.append(Finding("error", path, "superseded_by %s does not exist" % sb))

    # (d) index agreement
    for atype, spec in contracts.artefact_types.items():
        index_rel = spec.get("index_file")
        if not index_rel:
            continue
        index_path = os.path.join(root, index_rel.replace("/", os.sep))
        if not os.path.isfile(index_path):
            if ids_by_type.get(atype):
                findings.append(Finding("error", index_rel, "index file missing but %d %s artefact(s) exist" % (len(ids_by_type[atype]), atype)))
            continue
        with open(index_path, encoding="utf-8") as f:
            index_text = f.read()
        indexed = set(re.findall(spec["id_pattern"].strip("^$"), index_text))
        disk = ids_by_type.get(atype, set())
        for missing in sorted(disk - indexed):
            findings.append(Finding("error", index_rel, "%s exists on disk but is not in the index" % missing))
        for phantom in sorted(indexed - disk):
            findings.append(Finding("error", index_rel, "%s is in the index but has no file" % phantom))
    return findings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_checks -v`
Expected: PASS (10 tests now in the file — 4 from Task 6 plus 6 workspace tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/implr_validate/checks.py tests/test_checks.py
git commit -m "feat(validate): add cross-reference and workspace discovery checks"
```

---

## Task 8: Repo prose checks — banned tokens & divergent enums

**Files:**
- Modify: `scripts/implr_validate/checks.py`
- Modify: `tests/test_checks.py`

**Interfaces:**
- Consumes: `Contracts`, `Finding`.
- Produces: `check_repo_prose(root: str, contracts) -> list[Finding]`. (a) retired `banned_tokens` on any `banned_token_surfaces` path not under `exempt_paths`, PLUS `plan_status_misuse_tokens` (e.g. `changes-required`) used in an arrow/transition context; (b) divergent status enum comments in `schema_machine_map` files under `enum_comment_surfaces`; (c) retired `.md` cache-path references on `cache_path_surfaces` (now incl. README/WORKFLOW); (d) EVERY `kb_supported_formats: [...]` array repo-wide equals `canonical_formats`; (e) every canonical format token is present on each `format_presence_surfaces` file.

- [ ] **Step 1: Write the failing tests (append to `tests/test_checks.py`)**

```python
# append to tests/test_checks.py
from implr_validate.checks import check_repo_prose


class TestRepoProse(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def _repo(self, root, rel, text):
        p = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def test_banned_token_flagged_in_template(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "scaffold/templates/plan-template.md", "status: replan_required\n")
            self.assertTrue(any("replan_required" in f.message for f in check_repo_prose(root, self.c)))

    def test_banned_token_flagged_in_readme_and_workflow(self):
        # the drift class the original review found — must be caught on broad surfaces
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "README.md", "the plan can be replan_required after a CR\n")
            self._repo(root, "docs/WORKFLOW.md", "CR goes draft -> impact-analysed -> approved\n")
            findings = check_repo_prose(root, self.c)
            self.assertTrue(any("replan_required" in f.message for f in findings))
            self.assertTrue(any("impact-analysed" in f.message for f in findings))

    def test_banned_token_flagged_in_skill(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "skills/ba-cr/SKILL.md", "sets replan_required on the plan\n")
            self.assertTrue(any("replan_required" in f.message for f in check_repo_prose(root, self.c)))

    def test_banned_token_exempt_in_changelog(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "CHANGELOG.md", "removed replan_required in v3\n")
            self.assertEqual([f for f in check_repo_prose(root, self.c) if "replan_required" in f.message], [])

    def test_divergent_enum_comment_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "scaffold/schemas/plan-schema.md",
                       "status: ready   # ready | in-progress | done | changes-required\n")
            self.assertTrue(any("changes-required" in f.message for f in check_repo_prose(root, self.c)))

    def test_matching_enum_comment_clean(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "scaffold/schemas/plan-schema.md",
                       "status: ready   # ready | in-progress | done | blocked | needs-rework\n")
            self.assertEqual(check_repo_prose(root, self.c), [])

    def test_cache_md_extension_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "scaffold/schemas/kb-index-schema.md", "cache_path: docs/implr/kb-index/cache/x.md\n")
            self.assertTrue(any("cache" in f.message.lower() for f in check_repo_prose(root, self.c)))

    def test_format_list_mismatch_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "scaffold/config/implr.config.yaml", "  kb_supported_formats: [md, pdf, docx]\n")
            self.assertTrue(any("kb_supported_formats" in f.message for f in check_repo_prose(root, self.c)))

    def test_format_array_mismatch_in_readme_flagged(self):
        # (d) checks EVERY kb_supported_formats array anywhere, incl. README's config example
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "README.md", "example: `kb_supported_formats: [md, pdf]`\n")
            self.assertTrue(any("kb_supported_formats" in f.message for f in check_repo_prose(root, self.c)))

    def test_format_presence_missing_flagged(self):
        # (e) each canonical format must appear on a presence surface; omit 'bmp'
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "skills/doc-ingest/phases/extract.md",
                       "handles: md pdf docx xlsx pptx odp odt ods csv txt vtt png jpg jpeg gif webp tiff\n")
            findings = check_repo_prose(root, self.c)
            self.assertTrue(any("bmp" in f.message and "not mentioned" in f.message for f in findings))

    def test_changes_required_transition_misuse_flagged(self):
        # 'changes-required' used as a plan-lifecycle transition on a doc surface
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "docs/WORKFLOW.md", "plan flow: done -> changes-required -> in-progress\n")
            self.assertTrue(any("changes-required" in f.message and "transition" in f.message for f in check_repo_prose(root, self.c)))

    def test_changes_required_verdict_prose_clean(self):
        # legitimate review-verdict prose (no arrow) must NOT be flagged
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, "README.md", "If the verdict is changes-required, the plan returns to in-progress.\n")
            self.assertEqual([f for f in check_repo_prose(root, self.c) if "transition" in f.message], [])
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `python -m unittest tests.test_checks -v`
Expected: FAIL — `ImportError: cannot import name 'check_repo_prose'`.

- [ ] **Step 3: Add the implementation to `checks.py`**

```python
# append to scripts/implr_validate/checks.py
ENUM_COMMENT_RE = re.compile(r"status:\s*[\w-]+\s*#\s*([\w-]+(?:\s*\|\s*[\w-]+)+)")


def _is_exempt(rel, exempt_prefixes):
    rel = rel.replace(os.sep, "/")
    return any(rel == p or rel.startswith(p) for p in exempt_prefixes)


CACHE_MD_RE = re.compile(r"cache/\{slug\}\.md|cache/[\w-]+\.md|cache_path:\s*\S+\.md")
FORMATS_RE = re.compile(r"kb_supported_formats:\s*\[([^\]]*)\]")
# `changes-required` used as a plan lifecycle transition (misuse), not the review verdict noun
TRANSITION_MISUSE_RE_TMPL = r"(?:->|-->|→|—>)\s*%s|%s\s*(?:->|-->|→|—>)"


def _matches_surface(rel, surfaces):
    return any(rel == s or rel.startswith(s) for s in surfaces)


def check_repo_prose(root, contracts):
    cfg = contracts.repo_prose_checks
    findings = []
    banned = cfg["banned_tokens"]
    exempt = cfg["exempt_paths"]
    banned_surfaces = cfg["banned_token_surfaces"]
    enum_surfaces = cfg["enum_comment_surfaces"]
    enum_exempt = cfg["enum_check_exempt"]
    cache_surfaces = cfg["cache_path_surfaces"]
    misuse_tokens = cfg.get("plan_status_misuse_tokens", [])
    canonical = list(cfg["canonical_formats"])
    machine_map = contracts.schema_machine_map

    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(".md"):
                continue
            abspath = os.path.join(dirpath, name)
            rel = os.path.relpath(abspath, root).replace(os.sep, "/")
            with open(abspath, encoding="utf-8") as f:
                text = f.read()

            # (a) retired tokens — broad surface (README/WORKFLOW/skills/agents/scaffold)
            if _matches_surface(rel, banned_surfaces) and not _is_exempt(rel, exempt):
                for b in banned:
                    if b["token"] in text:
                        findings.append(Finding("error", rel, "banned token %r (%s)" % (b["token"], b["reason"])))
                # (a2) transition-context misuse of an otherwise-legal token
                for tok in misuse_tokens:
                    pat = TRANSITION_MISUSE_RE_TMPL % (re.escape(tok), re.escape(tok))
                    if re.search(pat, text):
                        findings.append(Finding("error", rel, "%r used as a plan-lifecycle transition; it is a review status, not a plan status" % tok))

            # (b) divergent enum comments — narrow surface (schemas/templates)
            if name in machine_map and _matches_surface(rel, enum_surfaces) and not _is_exempt(rel, enum_exempt):
                legal = contracts.states_for(machine_map[name])
                for m in ENUM_COMMENT_RE.finditer(text):
                    for v in [x.strip() for x in m.group(1).split("|")]:
                        if v not in legal:
                            findings.append(Finding("error", rel, "enum comment lists %r, illegal for %s machine" % (v, machine_map[name])))

            # (c) cache-path drift — the retired .md cache extension
            if _matches_surface(rel, cache_surfaces) and CACHE_MD_RE.search(text):
                findings.append(Finding("error", rel, "cache path uses retired .md extension; cache files are cache/{slug}.txt"))

    # (d) format-list drift — EVERY kb_supported_formats array anywhere must equal canonical
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not (name.endswith(".md") or name.endswith(".yaml") or name.endswith(".yml")):
                continue
            abspath = os.path.join(dirpath, name)
            rel = os.path.relpath(abspath, root).replace(os.sep, "/")
            if _is_exempt(rel, exempt):
                continue
            with open(abspath, encoding="utf-8") as f:
                for m in FORMATS_RE.finditer(f.read()):
                    listed = [x.strip() for x in m.group(1).split(",") if x.strip()]
                    if listed != canonical:
                        findings.append(Finding("error", rel, "kb_supported_formats %s != canonical %s" % (listed, canonical)))

    # (e) format presence — every canonical format must appear on each presence surface
    for rel in cfg.get("format_presence_surfaces", []):
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            text = f.read()
        for fmt in canonical:
            if not re.search(r"\b%s\b" % re.escape(fmt), text):
                findings.append(Finding("error", rel, "canonical format %r not mentioned on this surface" % fmt))
    return findings
```

Note on scope: (d) exact-matches machine-readable `kb_supported_formats: [...]` arrays (config and
README's config example). (e) is a presence check on the free-prose surfaces (schema enum comment,
README lists, extractor table) — it catches the realistic "added/removed a format but missed a
surface" drift without brittle exact-parsing of prose. Full bidirectional exact-match of prose
lists is intentionally not attempted; presence + machine-array exact-match is the robust
compromise.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_checks -v`
Expected: PASS (all TestRepoProse tests, including the new broad-surface, cache-path, and format tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/implr_validate/checks.py tests/test_checks.py
git commit -m "feat(validate): add repo prose checks (banned tokens, divergent enums)"
```

---

## Task 9: CLI — `--repo` / `--workspace` / `--fingerprint`

**Files:**
- Create: `scripts/implr_validate/cli.py`
- Create: `scripts/implr_validate/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_contracts`, `check_workspace`, `check_repo_prose`, `contradiction_fingerprint`.
- Produces: `main(argv: list[str]) -> int` (0 = clean, 1 = findings, 2 = usage error). `--repo` runs prose checks on cwd; `--workspace [PATH]` runs workspace checks (default cwd); `--fingerprint FILE.json` prints `<version>:<hash>` from a JSON fields file and returns 0. `--schema-dir` overrides the contract location (defaults to `scaffold/schemas` under cwd, falling back to `docs/implr/schemas`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.cli import main

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestCli(unittest.TestCase):
    def test_fingerprint_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath = os.path.join(tmp, "f.json")
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump({"source_a": "a", "statement_a": "x", "source_b": "b",
                           "statement_b": "y", "type": "Hard conflict"}, f)
            rc = main(["--fingerprint", fpath, "--schema-dir", os.path.join(REPO_ROOT, "scaffold", "schemas")])
            self.assertEqual(rc, 0)

    def test_repo_mode_clean_tree_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "scaffold", "schemas"))
            # copy the two contract files so load works, no offending prose present
            for fn in ("status-vocabulary.json", "frontmatter-rules.json"):
                src = os.path.join(REPO_ROOT, "scaffold", "schemas", fn)
                with open(src, encoding="utf-8") as a, open(os.path.join(tmp, "scaffold", "schemas", fn), "w", encoding="utf-8") as b:
                    b.write(a.read())
            rc = main(["--repo", "--root", tmp, "--schema-dir", os.path.join(tmp, "scaffold", "schemas")])
            self.assertEqual(rc, 0)

    def test_usage_error_returns_two(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify the tests fail**

Run: `python -m unittest tests.test_cli -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_validate.cli'`.

- [ ] **Step 3: Write `cli.py` and `__main__.py`**

```python
# scripts/implr_validate/cli.py
import argparse
import json
import os
import sys

from .contracts import load_contracts
from .checks import check_workspace, check_repo_prose
from .fingerprint import contradiction_fingerprint


def _resolve_schema_dir(root, override):
    if override:
        return override
    candidate = os.path.join(root, "scaffold", "schemas")
    if os.path.isdir(candidate):
        return candidate
    return os.path.join(root, "docs", "implr", "schemas")


def main(argv):
    parser = argparse.ArgumentParser(prog="implr_validate", add_help=True)
    parser.add_argument("--repo", action="store_true", help="validate the plugin source tree")
    parser.add_argument("--workspace", nargs="?", const=".", default=None,
                        help="validate an installed docs/implr workspace at PATH (default cwd)")
    parser.add_argument("--fingerprint", metavar="FILE", help="print fingerprint of a JSON fields file")
    parser.add_argument("--root", default=".", help="repo root for --repo (default cwd)")
    parser.add_argument("--schema-dir", default=None, help="override contract directory")
    args = parser.parse_args(argv)

    if not (args.repo or args.workspace is not None or args.fingerprint):
        sys.stderr.write("error: one of --repo, --workspace, --fingerprint is required\n")
        return 2

    if args.fingerprint:
        schema_dir = _resolve_schema_dir(args.root, args.schema_dir)
        _ = load_contracts(schema_dir)  # ensures contracts are loadable/consistent
        with open(args.fingerprint, encoding="utf-8") as f:
            fields = json.load(f)
        sys.stdout.write(contradiction_fingerprint(fields) + "\n")
        return 0

    findings = []
    if args.repo:
        schema_dir = _resolve_schema_dir(args.root, args.schema_dir)
        contracts = load_contracts(schema_dir)
        findings.extend(check_repo_prose(args.root, contracts))
    if args.workspace is not None:
        ws = args.workspace
        schema_dir = _resolve_schema_dir(ws, args.schema_dir)
        contracts = load_contracts(schema_dir)
        findings.extend(check_workspace(ws, contracts))

    if findings:
        for fnd in findings:
            sys.stderr.write("%s: %s: %s\n" % (fnd.level, fnd.path, fnd.message))
        sys.stderr.write("\n%d finding(s)\n" % len(findings))
        return 1
    sys.stdout.write("implr-validate: OK\n")
    return 0
```

```python
# scripts/implr_validate/__main__.py
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the CLI unit tests, then run the full suite**

Run: `python -m unittest tests.test_cli -v`
Expected: PASS (3 tests).

Run: `python -m unittest discover -s tests -v`
Expected: PASS (all tests across all files).

- [ ] **Step 5: Smoke-test the runnable directory form (portable)**

Run:
```
python -c "import json,tempfile,os; p=os.path.join(tempfile.gettempdir(),'f.json'); json.dump({'source_a':'a','statement_a':'x','source_b':'b','statement_b':'y','type':'t'}, open(p,'w')); print(p)"
```
Take the printed path and run:
`python scripts/implr_validate --fingerprint <printed-path> --schema-dir scaffold/schemas`
Expected: prints `1:` followed by 16 hex chars.

- [ ] **Step 6: Commit**

```bash
git add scripts/implr_validate/cli.py scripts/implr_validate/__main__.py tests/test_cli.py
git commit -m "feat(validate): add CLI with --repo/--workspace/--fingerprint modes"
```

---

## Task 10: B.4 minimal deterministic fixture

**Files:**
- Create: `tests/fixtures/sample-kb/docs/implr/requirements/functional/REQ-F-001-login.md`
- Create: `tests/fixtures/sample-kb/docs/kb/change-requests/CR-001-additive.md`
- Create: `tests/fixtures/sample-kb/docs/kb/change-requests/CR-002-correction.md`
- Create: `tests/fixtures/sample-kb/expected-validate.txt`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `main` (Task 9).
- Produces: a checked-in miniature workspace and an integration test asserting `main(["--workspace", <fixture>])` returns 0 and that a deliberately broken copy returns 1 with the expected finding substring.

- [ ] **Step 1: Create the fixture requirement**

`tests/fixtures/sample-kb/docs/implr/requirements/functional/REQ-F-001-login.md`:

```markdown
---
req_id: REQ-F-001
slug: login
title: "User Login"
type: functional
status: approved
complexity: M
tdd_required: true
source_docs:
  - login-spec.md
created_at: 2026-01-01T00:00:00Z
updated_at: 2026-01-01T00:00:00Z
---
# REQ-F-001 — User Login

## Acceptance Criteria
- [ ] AC-001: Given valid credentials — user is authenticated.
- [ ] AC-002: Given invalid credentials — access is denied.
```

- [ ] **Step 2: Create the two CR fixtures**

`tests/fixtures/sample-kb/docs/kb/change-requests/CR-001-additive.md`:

```markdown
---
cr_id: CR-001
slug: add-remember-me
title: "Add remember-me option to login"
status: draft
change_type: scope-expansion
source: cli-direct
created_at: 2026-01-02T00:00:00Z
---
# CR-001 — Add remember-me option to login

## Description of Change
Add an optional "remember me" checkbox that extends the session.
```

`tests/fixtures/sample-kb/docs/kb/change-requests/CR-002-correction.md`:

```markdown
---
cr_id: CR-002
slug: fix-lockout-threshold
title: "Correct lockout threshold from 3 to 5 attempts"
status: draft
change_type: correction
source: cli-direct
created_at: 2026-01-03T00:00:00Z
---
# CR-002 — Correct lockout threshold

## Description of Change
The spec said 3 failed attempts; the correct threshold is 5.
```

- [ ] **Step 2b: Create the index files (required by the index-agreement check)**

`tests/fixtures/sample-kb/docs/implr/requirements/requirements-index.md`:

```markdown
# Requirements Index

> Maintained by ba-requirements-gen. Do not edit manually.

## Functional
| ID | Title | Status |
|----|-------|--------|
| REQ-F-001 | User Login | approved |
```

`tests/fixtures/sample-kb/docs/implr/requirements/cr-index.md`:

```markdown
# CR Index

> Maintained by ba-cr. Do not edit manually.

## Change Requests
| CR ID | Title | Status | Change Type | Affected Reqs | Applied At |
|-------|-------|--------|-------------|---------------|------------|
| CR-001 | Add remember-me option to login | draft | scope-expansion | | |
| CR-002 | Correct lockout threshold from 3 to 5 attempts | draft | correction | | |
```

(No plans yet in this fixture, so no `plans-index.md` is required — Plan 2 adds a plan and its index. The CRs live under `docs/kb/change-requests/` and are indexed by `cr-index.md` under `docs/implr/requirements/`.)

- [ ] **Step 3: Create `expected-validate.txt`**

`tests/fixtures/sample-kb/expected-validate.txt`:

```
implr-validate: OK
```

- [ ] **Step 4: Write the failing integration tests (append to `tests/test_cli.py`)**

```python
# append to tests/test_cli.py
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample-kb")
SCHEMA_DIR = os.path.join(REPO_ROOT, "scaffold", "schemas")


class TestFixture(unittest.TestCase):
    def test_clean_fixture_passes(self):
        rc = main(["--workspace", FIXTURE, "--schema-dir", SCHEMA_DIR])
        self.assertEqual(rc, 0)

    def test_broken_status_fails(self):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "sample-kb")
            shutil.copytree(FIXTURE, dst)
            req = os.path.join(dst, "docs", "implr", "requirements", "functional", "REQ-F-001-login.md")
            with open(req, encoding="utf-8") as f:
                text = f.read()
            with open(req, "w", encoding="utf-8") as f:
                f.write(text.replace("status: approved", "status: replan_required"))
            rc = main(["--workspace", dst, "--schema-dir", SCHEMA_DIR])
            self.assertEqual(rc, 1)
```

- [ ] **Step 5: Run to verify the clean test passes and broken test fails as designed**

Run: `python -m unittest tests.test_cli.TestFixture -v`
Expected: PASS (both tests — the clean workspace returns 0; the mutated copy returns 1).

- [ ] **Step 6: Confirm the fixture matches `expected-validate.txt`**

Run: `python scripts/implr_validate --workspace tests/fixtures/sample-kb --schema-dir scaffold/schemas`
Expected: prints exactly `implr-validate: OK` (matching `expected-validate.txt`).

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/sample-kb tests/test_cli.py
git commit -m "test(validate): add minimal deterministic sample-kb fixture and integration tests"
```

---

## Task 11: Fix cache-path and format drift in scaffold

**Files:**
- Modify: `scaffold/schemas/kb-index-schema.md` (lines ~27, ~29, ~61, ~63, ~66-67)
- Modify: `scaffold/config/implr.config.yaml:21`

**Interfaces:**
- No code interface. Deliverable: `--repo` prose checks stay clean and the schema/config now agree with the extractor and README on `.txt` and the 18-format list.

- [ ] **Step 1: Fix the cache path in `kb-index-schema.md`**

Change line 27 from:
```
  cache_path: docs/implr/kb-index/cache/auth-flow.md
```
to:
```
  cache_path: docs/implr/kb-index/cache/auth-flow.txt
```

Change the section header (line 61) from `## 2. cache/{slug}.md — Normalised Text Cache` to `## 2. cache/{slug}.txt — Normalised Text Cache`, and line 63 from `Location: docs/implr/kb-index/cache/{slug}.md` to `Location: docs/implr/kb-index/cache/{slug}.txt`.

- [ ] **Step 2: Fix the `format` enum comment in `kb-index-schema.md` (line 29)**

Change:
```
  format: md                      # md | pdf | docx | xlsx | csv | txt | vtt | other
```
to:
```
  format: md                      # md | pdf | docx | xlsx | pptx | odp | odt | ods |
                                  # csv | txt | vtt | png | jpg | jpeg | gif | webp |
                                  # tiff | bmp | other
```

- [ ] **Step 3: Fix the default formats in `implr.config.yaml:21`**

Change:
```
  kb_supported_formats: [md, pdf, docx, xlsx, csv, txt, vtt]
```
to:
```
  kb_supported_formats: [md, pdf, docx, xlsx, pptx, odp, odt, ods, csv, txt, vtt, png, jpg, jpeg, gif, webp, tiff, bmp]
```

- [ ] **Step 4: Verify no stale `.md` cache references remain in the schema**

Run: `grep -n "cache/{slug}.md\|cache/auth-flow.md" scaffold/schemas/kb-index-schema.md || echo "none"`
Expected: `none`

- [ ] **Step 5: Targeted verification of the cache/format fixes**

A full `--repo` is NOT yet green here — README/WORKFLOW and the CR agents/skills still carry
retired status tokens that Task 13 clears. So verify only this task's surfaces:

Run: `grep -rn "cache/{slug}.md\|cache/auth-flow.md\|cache_path:.*\.md" scaffold/schemas/kb-index-schema.md || echo "none"`
Expected: `none`

Run: `python -c "import re,io; t=open('scaffold/config/implr.config.yaml',encoding='utf-8').read(); m=re.search(r'kb_supported_formats:\s*\[([^\]]*)\]',t); vals=[x.strip() for x in m.group(1).split(',')]; canon=['md','pdf','docx','xlsx','pptx','odp','odt','ods','csv','txt','vtt','png','jpg','jpeg','gif','webp','tiff','bmp']; print('OK' if vals==canon else ('MISMATCH: %s' % vals))"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add scaffold/schemas/kb-index-schema.md scaffold/config/implr.config.yaml
git commit -m "fix(scaffold): standardize cache path on .txt and default to full 18-format list"
```

---

## Task 12: Wire the contradiction fingerprint into schema, seed, and agents

**Files:**
- Modify: `scaffold/schemas/kb-index-schema.md` (contradiction table sections + a new "Contradiction Fingerprint" subsection)
- Modify: `scaffold/seeds/resolved-contradictions.md`
- Modify: `.claude/agents/doc-ingest-synthesizer.md`
- Modify: `skills/doc-ingest/SKILL.md`, `skills/doc-ingest/phases/synthesize-domain.md`
- Modify: `skills/ba-requirements-gen/SKILL.md`

**Interfaces:**
- Consumes: `python scripts/implr_validate --fingerprint FILE.json` (Task 9).
- No code test; deliverable is documented, consistent fingerprint handling with the orchestrator (which has Bash) computing hashes.

- [ ] **Step 1: Add the fingerprint algorithm subsection to `kb-index-schema.md`**

After the contradiction-table definitions, add:

```markdown
### Contradiction Fingerprint (stable identity)

Every contradiction row carries a `fingerprint` and `fingerprint_version`. The fingerprint is
the stable identity used to match against `resolved-contradictions.md` — `C-xxx` IDs are display
labels only and are NOT used for matching.

Algorithm (version 1), implemented canonically in `scripts/implr_validate/fingerprint.py`:

1. Normalize every field: trim, collapse internal whitespace, lowercase, strip trailing
   `.,;:!?`.
2. Build the two sides `{source, statement}` for A and B and **sort them** (so swapping A/B does
   not change the identity).
3. Serialize `{version, type, sides}` as canonical JSON (sorted keys, no insignificant
   whitespace).
4. `fingerprint = "1:" + sha256(canonical)[:16]`.

An LLM must NOT hand-compute this hash. The `doc-ingest` orchestrator computes it by writing the
five fields to a temp JSON file and calling
`python scripts/implr_validate --fingerprint <file>`. `implr-validate --workspace` recomputes
and verifies stored fingerprints. To change the algorithm, bump `fingerprint_version`.
```

- [ ] **Step 2: Add fingerprint columns to the contradiction tables in `kb-index-schema.md`**

In each "Contradictions Detected" / "Cross-Domain Contradictions" / resolved / deferred table
definition, add `Fingerprint` and `FP-Ver` columns after the `C-ID` column. Example resolved
header:

```markdown
| C-ID | Fingerprint | FP-Ver | Type | Source A | Source B | Problem | Decision | Resolved |
|------|-------------|--------|------|----------|----------|---------|----------|----------|
```

- [ ] **Step 3: Update the seed `resolved-contradictions.md`**

Replace the two table headers to include the new columns:

```markdown
## Resolved
| C-ID | Fingerprint | FP-Ver | Type | Source A | Source B | Problem | Decision | Resolved |
|------|-------------|--------|------|----------|----------|---------|----------|----------|

## Deferred
| C-ID | Fingerprint | FP-Ver | Type | Source A | Source B | Problem | Notes | Deferred |
|------|-------------|--------|------|----------|----------|---------|-------|----------|
```

- [ ] **Step 4: Update `.claude/agents/doc-ingest-synthesizer.md`**

Add to the contradiction-detection step: after classifying each contradiction, the synthesizer
records the five raw fields (`source_a, statement_a, source_b, statement_b, type`) per row and
emits them in its return summary as a `contradictions_for_fingerprinting` list. State
explicitly: "Do not compute the fingerprint hash yourself; the orchestrator computes it."

- [ ] **Step 5: Update `skills/doc-ingest/SKILL.md` and `phases/synthesize-domain.md`**

In the synthesize phase of the orchestrator, after a synthesizer subagent returns, for each
contradiction: write the five fields to a temp JSON file and run
`python scripts/implr_validate --fingerprint <tmp>`; capture the printed `<ver>:<hash>` and
write `fingerprint` + `fingerprint_version` into the synthesis contradiction table row. Document
the exact command and the temp-file cleanup.

- [ ] **Step 6: Update `skills/ba-requirements-gen/SKILL.md` Phase 0**

Change Step 2/Step 5 so `already_handled` and the resolved/deferred maps key on
`(fingerprint_version, fingerprint)` instead of `C-ID`. `C-ID` remains shown to the user in the
Step 3 prompt as a label. Add one line: "Matching is by fingerprint; a contradiction whose
fingerprint is absent from resolved-contradictions.md is treated as unresolved even if a similar
C-ID exists."

- [ ] **Step 7: Verify the fingerprint helper is reachable and deterministic (portable)**

Run:
```
python -c "import json,tempfile,os; p=os.path.join(tempfile.gettempdir(),'c.json'); json.dump({'source_a':'spec-v1 §3','statement_a':'TTL 15 min','source_b':'spec-v2 §1','statement_b':'TTL 30 min','type':'Hard conflict'}, open(p,'w',encoding='utf-8')); print(p)"
```
Take the printed path and run the validator against it twice:
`python scripts/implr_validate --fingerprint <printed-path> --schema-dir scaffold/schemas`
Expected: the same `1:<hash>` printed both times.

- [ ] **Step 8: Commit**

```bash
git add scaffold/schemas/kb-index-schema.md scaffold/seeds/resolved-contradictions.md .claude/agents/doc-ingest-synthesizer.md skills/doc-ingest/SKILL.md skills/doc-ingest/phases/synthesize-domain.md skills/ba-requirements-gen/SKILL.md
git commit -m "feat(doc-ingest): key contradictions on stable fingerprint via validate helper"
```

---

## Task 13: Align docs + clear retired tokens everywhere; final repo validation sweep

**Files:**
- Modify: `README.md` (status/lifecycle sections; formats line ~672; cache-path mentions)
- Modify: `docs/WORKFLOW.md` (plan lifecycle, CR lifecycle, contradiction section)
- Modify: `.claude/agents/cr-applier.md`, `skills/ba-cr/SKILL.md`, `skills/ba-cr/phases/apply.md` (token swap only)

**Interfaces:**
- No code interface. Deliverable: README/WORKFLOW cite `status-vocabulary.json`, use only legal statuses, describe fingerprint matching; ALL live surfaces are free of retired tokens; the full `--repo` check plus full test suite are green.

**Why this task touches CR agents/skills:** broadening `--repo` to skills/agents means the retired
`replan_required` token in `cr-applier.md`/`ba-cr` must go for `--repo` to pass. `needs-rework`
already exists in the vocabulary (Task 1), so this task does the minimal **token swap** to
`needs-rework` references. Plan 2 then layers the full `rework_cr`/`rework_reason` fields and
behavior on these same files — this is a deliberate, coherent hand-off, not duplication.

- [ ] **Step 1: Fix the plan lifecycle in `README.md`**

Locate the Plans lifecycle block (~lines 439–454) using the retired tokens and replace it so it
matches the plan machine, adding `needs-rework` and restoring `blocked`, and removing
`replan_required`:

```
ready ──► in-progress ──► done
  │                        │
  ├──► blocked ──► ready    ├──► needs-rework (via ba-cr) ──► ready (via dev-planner --replan)
  └───────────────────────►┘  (done → in-progress on review changes-required/rejected)
```

Add a sentence: "Legal plan states and transitions are defined once in
`docs/implr/schemas/status-vocabulary.json`; this diagram mirrors it."

- [ ] **Step 2: Fix the CR lifecycle in `README.md`**

Remove the `impact-analysed` state (~lines 459, 474–476). CR lifecycle must read
`draft → approved → applied` with `↘ rejected`, citing `status-vocabulary.json`.

- [ ] **Step 3: Fix the formats config example in `README.md` (~line 672)**

Ensure the shown `kb_supported_formats:` value equals the shipped config (the 18-format list
from Task 11 Step 3). If any prose lists cache files as `.md`, change to `.txt`.

- [ ] **Step 4: Fix `docs/WORKFLOW.md` plan and CR sections**

Plan transition table (~lines 244–269): remove `changes-required` as a plan *status*; represent
the review-failure transition as `done → in-progress`. Add `done → needs-rework` (by ba-cr) and
`needs-rework → ready` (by dev-planner --replan). CR section: keep `draft → approved → applied`.
Contradiction section (~lines 172–195): state that matching is by `(fingerprint_version,
fingerprint)`, with `C-xxx` as a display label.

- [ ] **Step 4b: Token-swap retired `replan_required` in the CR agents/skills**

These files use the retired marker; swap to `needs-rework` language (full fields/behavior land
in Plan 2):
- `.claude/agents/cr-applier.md`: change "write a stub `replan_required: true` marker" to "set the
  plan `status: needs-rework` (see `status-vocabulary.json`); the orchestrator invokes
  `dev-planner --replan` separately"; change the return-summary `status: applied | replan_required`
  to `status: applied | needs-rework`.
- `skills/ba-cr/SKILL.md`: change "plans where the applier set `replan_required: true`" to "plans
  the applier set to `needs-rework`".
- `skills/ba-cr/phases/apply.md`: change any `replan_required` return value to `needs-rework`.

Do NOT introduce `rework_cr`/`rework_reason` here (that is Plan 2 Task 2/9) — this step only
removes the retired token.

- [ ] **Step 5: Grep sweep for retired tokens outside history**

Run:
```
grep -rn "replan_required\|impact-analysed" README.md docs/WORKFLOW.md scaffold/ skills/ .claude/ || echo "none"
```
Expected: `none` (all live surfaces clean; CHANGELOG and docs/superpowers are exempt and not searched here).

- [ ] **Step 6: Run the full repo validation and test suite**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

Run: `python -m unittest discover -s tests -v`
Expected: PASS (all tests, all files).

- [ ] **Step 7: Commit**

```bash
git add README.md docs/WORKFLOW.md .claude/agents/cr-applier.md skills/ba-cr/SKILL.md skills/ba-cr/phases/apply.md
git commit -m "docs: align README/WORKFLOW with status-vocabulary; clear retired tokens on all live surfaces"
```

---

## Self-Review Notes

- **Spec coverage (A):** status-vocabulary.json (T1), thin .md (T1), drift fixes cache/formats (T11), README/WORKFLOW status sync (T13). ✓
- **Spec coverage (B):** JSON contracts not per-schema companions (T1, T2), frontmatter subset parser (T3), `--repo`/`--workspace` (T9), B.4 fixture (T10). `--repo` prose checks (T8): retired tokens on broad surfaces (README/WORKFLOW/skills/agents/scaffold), `changes-required` transition misuse, divergent enum comments, `.md` cache-path drift (incl. README/WORKFLOW), format-array exact-match repo-wide + canonical-format presence. Cross-ref/index checks (T7): linked_requirement, PLAN/REQ pairing, superseded_by, index agreement. ✓
- **Spec coverage (D):** versioned order-independent SHA-256 fingerprint (T4), algorithm defined once in kb-index-schema.md (T12), columns in seed/schema (T12), synthesizer emits fields / orchestrator computes hash (T12), ba-requirements-gen keys on fingerprint (T12), WORKFLOW updated (T13). ✓
- **LLM-can't-hash gap:** resolved — the fingerprint function is code (T4), invoked via `--fingerprint` by the orchestrator that has Bash (T12), and recomputed by `--workspace` for verification.
- **Type consistency:** `Finding(level, path, message)` used consistently T6–T9; `contradiction_fingerprint(fields)`/`FINGERPRINT_VERSION` T4/T9/T12; `check_workspace`/`check_repo_prose`/`load_contracts`/`states_for` names stable across T5–T9.
- **Out of scope (correct):** the `needs-rework` write path, CR audit trail, idempotent executor, and review changes are Plans 2 and 3. This plan only *defines* `needs-rework` in the vocabulary and validates it; nothing sets it yet.
- **Sequencing (broadened `--repo`):** because the banned-token scan now covers skills/agents, `--repo` cannot be green while `replan_required` lingers in `cr-applier.md`/`ba-cr`. T13 does the minimal token-swap to `needs-rework` on those surfaces (the state exists as of T1); Plan 2 layers `rework_cr`/behavior on top. Mid-plan T11 uses targeted grep/format checks, not full `--repo`; full `--repo: OK` is a genuine end-of-Plan-1 gate after T13.
