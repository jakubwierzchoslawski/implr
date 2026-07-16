# implr Hardening — Plan 3: Test-Aware Review, Ordering Gates & Safe Commit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last enforcement gaps — code review that fails on failing or stale tests, skills that refuse to run out of order, the review→plan status write that the schema requires but the skill never did, and a commit default that is safe inside arbitrary repos.

**Architecture:** Adds a deterministic `--source-ref` helper to the Plan 1 validator (git HEAD + diff hash, with a documented non-git fallback), a `test-results` artefact schema, and prompt-contract edits across `dev-executor`, `plan-runner`, `dev-code-review`, `code-review-worker`, and every top-level skill (Preconditions blocks). No new runtime dependencies.

**Tech Stack:** Same as Plans 1–2 — Python 3.8+ stdlib validator with `unittest`; Markdown prompt/schema files. Corresponds to spec `docs/superpowers/specs/2026-07-16-implr-reliability-hardening-design.md`, workstreams **F**, **G**, **H**.

**Depends on:** Plans 1 and 2 merged (needs `implr_validate` CLI, `status-vocabulary.json`, `needs-rework`, and the executor/review prompt contracts from Plan 2).

## Global Constraints

- Zero third-party dependencies in `scripts/implr_validate/`; Python 3.8+; stdlib only.
- Hashes / refs computed by `scripts/implr_validate`, never hand-computed by an LLM.
- Commit after every task; trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Work on branch `impl/hardening-review-gates-commit`.
- Staleness rule (authoritative, from spec G): a review downgrades to at least `changes-required` when test results are missing, not tied to the reviewed `plan_id`, whose `source_ref` ≠ the review's `current_source_ref`, or whose `run_at` is earlier than the plan's `executed_at`.
- Commit default (spec H): `plan-runner` defaults to `commit_mode: defer` (no commit). Auto-commit only when `/dev-executor --commit` is passed.

---

## File Structure

**Created:**
- `scripts/implr_validate/sourceref.py` — `source_ref_fallback` + `source_ref` (git-or-fallback).
- `scaffold/schemas/test-results-schema.md` — structure of the per-plan `test-results` artefact.
- `tests/test_sourceref.py`

**Modified — validator/CLI:**
- `scripts/implr_validate/cli.py` — add `--source-ref`.
- `tests/test_cli.py`

**Modified — prompts:**
- `skills/dev-executor/SKILL.md`, `.claude/agents/plan-runner.md`, `.claude/agents/task-executor.md`
- `skills/dev-code-review/SKILL.md`, `.claude/agents/code-review-worker.md`
- `skills/doc-ingest/SKILL.md`, `skills/ba-requirements-gen/SKILL.md`, `skills/dev-planner/SKILL.md`, `skills/ba-cr/SKILL.md`

**Modified — docs:**
- `README.md`, `docs/WORKFLOW.md`

---

## Task 1: `--source-ref` helper (git-or-fallback)

**Files:**
- Create: `scripts/implr_validate/sourceref.py`
- Modify: `scripts/implr_validate/cli.py`
- Test: `tests/test_sourceref.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `source_ref_fallback(root: str, rel_paths: list[str]) -> str` = `"fb:" + sha256(sorted (relpath,size,mtime_ns) tuples)[:16]`; `source_ref(root: str, rel_paths: list[str]) -> str` tries `git rev-parse HEAD` + hash of (`git diff HEAD -- <paths>` **plus** the content hashes of untracked files from `git ls-files --others --exclude-standard -- <paths>`) — so staged AND untracked changes are captured — returning `"git:<12hex>:<8hex>"`, and falls back to `source_ref_fallback` when git is unavailable. CLI `--source-ref PATH [PATH ...]` prints the ref.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sourceref.py
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.sourceref import source_ref_fallback


class TestSourceRefFallback(unittest.TestCase):
    def test_stable_for_same_tree(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "src"))
            with open(os.path.join(root, "src", "a.py"), "w") as f:
                f.write("x = 1\n")
            a = source_ref_fallback(root, ["src"])
            b = source_ref_fallback(root, ["src"])
            self.assertEqual(a, b)
            self.assertTrue(a.startswith("fb:"))

    def test_changes_when_content_size_changes(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "src"))
            p = os.path.join(root, "src", "a.py")
            with open(p, "w") as f:
                f.write("x = 1\n")
            a = source_ref_fallback(root, ["src"])
            with open(p, "w") as f:
                f.write("x = 1  # longer content changes size\n")
            b = source_ref_fallback(root, ["src"])
            self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_sourceref -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_validate.sourceref'`.

- [ ] **Step 3: Implement `sourceref.py`**

```python
# scripts/implr_validate/sourceref.py
"""Deterministic source-reference for tying test evidence to a code state.
Prefers git; falls back to a filesystem hash. Standard library only."""
import hashlib
import os
import subprocess


def source_ref_fallback(root, rel_paths):
    entries = []
    for rel in rel_paths:
        base = os.path.join(root, rel)
        if os.path.isfile(base):
            walk_roots = [(os.path.dirname(base), [os.path.basename(base)])]
        else:
            walk_roots = None
        if walk_roots is None:
            for dirpath, _dirs, files in os.walk(base):
                for name in sorted(files):
                    p = os.path.join(dirpath, name)
                    st = os.stat(p)
                    entries.append((os.path.relpath(p, root).replace(os.sep, "/"), st.st_size, st.st_mtime_ns))
        else:
            for dirpath, names in walk_roots:
                for name in names:
                    p = os.path.join(dirpath, name)
                    st = os.stat(p)
                    entries.append((os.path.relpath(p, root).replace(os.sep, "/"), st.st_size, st.st_mtime_ns))
    entries.sort()
    payload = "\n".join("%s|%d|%d" % e for e in entries)
    return "fb:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _git(root, args):
    return subprocess.check_output(["git"] + args, cwd=root, stderr=subprocess.DEVNULL).decode("utf-8").strip()


def source_ref(root, rel_paths):
    try:
        head = _git(root, ["rev-parse", "HEAD"])
        # tracked changes vs HEAD — includes BOTH staged and unstaged
        diff = _git(root, ["diff", "HEAD", "--"] + list(rel_paths))
        # untracked files (respecting .gitignore) — hash their contents
        others = _git(root, ["ls-files", "--others", "--exclude-standard", "--"] + list(rel_paths))
        untracked = []
        for rel in others.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            p = os.path.join(root, rel)
            try:
                with open(p, "rb") as fh:
                    content = fh.read()
            except OSError:
                content = b""
            untracked.append(rel + "\0" + hashlib.sha256(content).hexdigest())
        combined = diff + "\n--untracked--\n" + "\n".join(sorted(untracked))
        state_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:8]
        return "git:%s:%s" % (head[:12], state_hash)
    except Exception:
        return source_ref_fallback(root, rel_paths)
```

- [ ] **Step 4: Add `--source-ref` to `cli.py`**

Add the argument:
```python
    parser.add_argument("--source-ref", nargs="+", metavar="PATH", help="print the source ref for the given paths")
```
Import: `from .sourceref import source_ref`.
Include in the required-mode guard, and add a handler before the findings section:
```python
    if args.source_ref:
        sys.stdout.write(source_ref(args.root, args.source_ref) + "\n")
        return 0
```

- [ ] **Step 5: Add a CLI test (append to `tests/test_cli.py`)**

```python
    def test_source_ref_mode(self):
        rc = main(["--source-ref", "scaffold", "--root", REPO_ROOT, "--schema-dir", os.path.join(REPO_ROOT, "scaffold", "schemas")])
        self.assertEqual(rc, 0)
```

- [ ] **Step 6: Run full suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add scripts/implr_validate/sourceref.py scripts/implr_validate/cli.py tests/test_sourceref.py tests/test_cli.py
git commit -m "feat(validate): add --source-ref (git-or-fallback) helper"
```

---

## Task 2: `test-results` artefact schema

**Files:**
- Create: `scaffold/schemas/test-results-schema.md`

**Interfaces:**
- Produces: the canonical structure of `docs/implr/plans/test-results/PLAN-F-NNN-results.md`, written by `plan-runner`, read by `code-review-worker`.

- [ ] **Step 1: Write the schema**

```markdown
# Test Results Schema

Per-plan record of test execution, written by `plan-runner` and consumed by
`code-review-worker` for the staleness rule. One file per plan.

Location: `docs/implr/plans/test-results/PLAN-F-NNN-results.md`

```markdown
---
plan_id: PLAN-F-001
run_at: {ISO timestamp}
source_ref: {output of implr_validate --source-ref src tests}
executed_at: {plan.executed_at at time of run}
---

# Test Results — PLAN-F-001

| Task | Command | Exit | Result | Output tail |
|------|---------|------|--------|-------------|
| TASK-001 | pytest tests/test_auth.py | 0 | pass | ...last lines... |
| TASK-002 | pytest tests/test_token.py | 1 | fail | ...last lines... |
```

## Staleness rule (enforced by code-review-worker)

A review downgrades to at least `changes-required` when this file is:
- missing for the reviewed plan, OR
- `plan_id` ≠ the reviewed plan, OR
- `source_ref` ≠ the review's `current_source_ref`, OR
- `run_at` earlier than the plan's `executed_at`.

Otherwise the review fails the plan on any covered test whose Result is not `pass`.
```

- [ ] **Step 2: Verify repo clean (schema is not in schema_machine_map, so no enum check)**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 3: Commit**

```bash
git add scaffold/schemas/test-results-schema.md
git commit -m "feat(schemas): add test-results artefact schema"
```

---

## Task 3: `plan-runner` / `task-executor` — persist attributable test-results

**Files:**
- Modify: `.claude/agents/task-executor.md` (Return summary ~lines 93-107)
- Modify: `.claude/agents/plan-runner.md` (Work ~lines 42-72; Return summary)

**Interfaces:**
- Consumes: `--source-ref` (Task 1). Produces: `task-executor` returns `test_command`, `test_exit_code`, `test_output_tail`; `plan-runner` writes `docs/implr/plans/test-results/PLAN-F-NNN-results.md` per the schema with `run_at` and `source_ref`.

- [ ] **Step 1: `task-executor` returns test evidence**

Add to the return summary YAML:
```
test_command: "<runner invocation, or empty>"
test_exit_code: <int or null>
test_output_tail: "<last ~15 lines, or empty>"
```

- [ ] **Step 2: `plan-runner` writes `test-results.md`**

In Work, add a step after status update:
"Ensure the directory `docs/implr/plans/test-results/` exists (create it if missing — e.g.
`mkdir -p`, or the Windows equivalent). Then write
`docs/implr/plans/test-results/<plan_id>-results.md` per `test-results-schema.md`. Compute
`source_ref` by running `python scripts/implr_validate --source-ref <src_path> <tests_path>` and
set `run_at` to now and `executed_at` to the plan's `executed_at`. One row per task from the
executor returns (`test_command`, `test_exit_code`, pass/fail, `test_output_tail`)."

- [ ] **Step 3: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/task-executor.md .claude/agents/plan-runner.md
git commit -m "feat(dev-executor): persist attributable per-plan test-results"
```

---

## Task 4: `dev-code-review` — compute source ref & write plan status back

**Files:**
- Modify: `skills/dev-code-review/SKILL.md` (Read first ~lines 14-22; Phase 2 ~lines 39-43; add Phase 4.5)

**Interfaces:**
- Consumes: `--source-ref` (Task 1). Produces: `current_source_ref` computed in the orchestrator and passed to each worker; on `changes-required`/`rejected`, the linked plan is set back to `in-progress` in both `plans-index.md` and the plan file.

- [ ] **Step 1: Compute `current_source_ref` and pass it to workers**

In Phase 2, add before dispatch:
"Compute `current_source_ref` by running `python scripts/implr_validate --source-ref <src_path>
<tests_path>` (read `src`/`tests` from `implr.config.yaml` paths). Add `current_source_ref` and
`test_results_path: docs/implr/plans/test-results/<plan_id>-results.md` to each worker's dispatch
scope."

- [ ] **Step 2: Add Phase 4.5 — write plan status back**

Insert after Phase 4:
```
### Phase 4.5 — Reflect verdict on plan status

For each review with verdict `changes-required` or `rejected`: set the linked plan's
`status: in-progress` in `plans-index.md` AND in the plan file, and record the blocking finding
ids in the plan file's `## Risks and Notes` (or a `review_blockers:` frontmatter note). This
implements review-schema.md's required review→plan status write.
```

- [ ] **Step 3: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 4: Commit**

```bash
git add skills/dev-code-review/SKILL.md
git commit -m "feat(dev-code-review): compute source ref; write review verdict back to plan status"
```

---

## Task 5: `code-review-worker` — consume test-results with staleness rule

**Files:**
- Modify: `.claude/agents/code-review-worker.md` (Inputs ~lines 24-33; Work ~lines 36-41; Verdict rules ~lines 43-54)

**Interfaces:**
- Consumes: `current_source_ref`, `test_results_path` (Task 4). Produces: a verdict that is test-aware and staleness-guarded.

- [ ] **Step 1: Add the new inputs**

In the Inputs block, add:
```
current_source_ref: <output of implr_validate --source-ref, passed by dev-code-review>
test_results_path: docs/implr/plans/test-results/PLAN-F-NNN-results.md
```

- [ ] **Step 2: Add the test-evidence step in Work**

Add after the AC read-through paragraph:
"Read `test_results_path`. Apply the staleness rule from `test-results-schema.md`: if the file is
missing, its `plan_id` mismatches, its `source_ref` ≠ `current_source_ref`, or its `run_at` is
earlier than the plan's `executed_at`, add a Critical finding `stale-or-missing-test-evidence`
and set the verdict no higher than `changes-required`. Otherwise, for every AC-covering test row
whose Result is not `pass`, add a Critical finding. You still do not run code."

- [ ] **Step 3: Note the interaction with verdict rules**

Add one line under the verdict rules: "A stale/missing/failed-test finding is Critical, so the
deterministic rules already force at least `changes-required`."

- [ ] **Step 4: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/agents/code-review-worker.md
git commit -m "feat(dev-code-review): worker consumes test-results with staleness rule"
```

---

## Task 6: Safe commit default (`defer`), opt-in `--commit`

**Files:**
- Modify: `.claude/agents/plan-runner.md` (frontmatter description line 3; Inputs ~line 30; Work step 3 ~lines 65-72)
- Modify: `skills/dev-executor/SKILL.md` (Parameters ~lines 26-34; Phase 5 dispatch ~lines 119-125)

**Interfaces:**
- Produces: `plan-runner` treats absent/`defer` commit_mode as **do-nothing-to-git** (no `git add`, no `git commit` — the worktree is left exactly as the executor left it); `dev-executor` passes `commit_mode: auto` only when `--commit` is present (otherwise `defer`).

- [ ] **Step 1: `plan-runner` default to defer, and defer touches nothing in git**

Change the description clause "commits if commit_mode=auto" to "commits only when
commit_mode=auto (default defer)". In Inputs, change `commit_mode: auto | defer` to
`commit_mode: auto | defer   # default defer if absent`. In Work step 3, replace the whole
commit block with: "If `commit_mode` is absent or `defer`: **do NOT run `git add` or
`git commit`; leave the worktree exactly as-is** (staging is itself a side effect in an
arbitrary repo). Only when `commit_mode: auto`: run `git add -A` then `git commit`."

- [ ] **Step 2: `dev-executor` opt-in `--commit`**

Add a parameter line: "`/dev-executor --commit ...` — commit each plan's changes after success
(default: no commit; the worktree is left exactly as-is, nothing staged)."
In Phase 5 dispatch, change `commit_mode (auto; defer for --dry-run)` to
`commit_mode (auto only when --commit passed; otherwise defer)`.

- [ ] **Step 3: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/plan-runner.md skills/dev-executor/SKILL.md
git commit -m "feat(dev-executor): default to no-commit; add opt-in --commit"
```

---

## Task 7: Precondition / ordering gates in every skill

**Files:**
- Modify: `skills/doc-ingest/SKILL.md`, `skills/ba-requirements-gen/SKILL.md`, `skills/dev-planner/SKILL.md`, `skills/dev-executor/SKILL.md`, `skills/ba-cr/SKILL.md`

**Interfaces:**
- Produces: each skill gains a `## Preconditions` block checked at start; may run `python scripts/implr_validate --workspace .` for structural checks.

- [ ] **Step 1: Add Preconditions to `doc-ingest/SKILL.md`**

Add after "Read first":
```
## Preconditions

- At least one KB source document exists under `docs/kb/`. If none: halt with
  `❌ No KB documents found under docs/kb/. Add source docs first.`
```

- [ ] **Step 2: Add Preconditions to `ba-requirements-gen/SKILL.md`**

```
## Preconditions

- `docs/implr/kb-index/master-synthesis.md` exists (else: `❌ Run /doc-ingest first.`).
- `docs/implr/config/requirements-card.md` exists (else the Phase 0 Step 6 error).
```

- [ ] **Step 3: Add Preconditions to `dev-planner/SKILL.md`**

```
## Preconditions

- `docs/ARCHITECTURE.md` exists (else: `❌ Run /arch-gen first.`).
- Each in-scope requirement is `status: approved` (unless named explicitly / require_approved_status:false).
```

- [ ] **Step 4: Add Preconditions to `dev-executor/SKILL.md`**

```
## Preconditions

- `docs/implr/config/standards-card.md` exists (else the existing halt).
- Every in-scope plan is `status: ready`. A `needs-rework` plan is rejected with
  `❌ PLAN-F-NNN is needs-rework — run /dev-planner --replan first.`
```

- [ ] **Step 5: Add Preconditions to `ba-cr/SKILL.md`**

```
## Preconditions

- A requirements set exists under `docs/implr/requirements/` (else warn: a CR with no
  requirements to target can only create new ones).
```

- [ ] **Step 6: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 7: Commit**

```bash
git add skills/doc-ingest/SKILL.md skills/ba-requirements-gen/SKILL.md skills/dev-planner/SKILL.md skills/dev-executor/SKILL.md skills/ba-cr/SKILL.md
git commit -m "feat(skills): add precondition/ordering gates to every skill"
```

---

## Task 8: README & WORKFLOW — review test-awareness, commit default, gates

**Files:**
- Modify: `README.md`
- Modify: `docs/WORKFLOW.md`

**Interfaces:**
- No code interface. Deliverable: docs describe test-aware review + staleness, the review→plan status write, the safe commit default (`--commit`), and the precondition gates.

- [ ] **Step 1: Update README**

In the review section, state that review consumes per-plan `test-results.md` and cannot approve
code with failing or stale tests; in the execution section, state commits are off by default and
`--commit` opts in; add a short "Ordering gates" note listing each skill's precondition.

- [ ] **Step 2: Update WORKFLOW**

In the review stage, add the test-results artefact + staleness rule + review→plan `in-progress`
write; in the execution stage, note the commit default; add the preconditions to each stage's
description.

- [ ] **Step 3: Final validation + full suite**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

Run: `python scripts/implr_validate --workspace tests/fixtures/sample-kb --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

Run: `python -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 4: Grep sweep for retired tokens on live surfaces**

Run:
```
grep -rn "commit_mode: auto\b" .claude/agents/plan-runner.md || echo "auto is opt-in only — check dev-executor gates it"
```
Confirm `plan-runner` no longer *defaults* to auto (the token may appear as an allowed value, not a default).

- [ ] **Step 5: Commit**

```bash
git add README.md docs/WORKFLOW.md
git commit -m "docs: document test-aware review, safe commit default, and ordering gates"
```

---

## Self-Review Notes

- **F preconditions:** every skill (T7). ✓
- **F review→plan write:** dev-code-review Phase 4.5 (T4) — implements review-schema.md:107-108 which the SKILL previously ignored. ✓
- **G test-aware review:** source-ref helper (T1), test-results schema (T2), plan-runner persists attributable results (T3), dev-code-review computes/passes current_source_ref (T4), worker staleness rule (T5). ✓
- **H safe commit:** plan-runner default defer + dev-executor --commit (T6). ✓
- **Placeholder scan:** code steps show full code; prompt-edit steps show exact text. ✓
- **Type consistency:** `source_ref`/`source_ref_fallback` (T1) consumed by plan-runner (T3) and dev-code-review (T4); `current_source_ref`/`test_results_path` produced T4, consumed T5.
- **Cross-plan:** relies on Plan 2's `executed_at` being present on done plans (set by plan-runner) and Plan 1's CLI. The `needs-rework` precondition in T7 restates Plan 2's dev-executor halt — intentional, as the Preconditions block is the single place a reader checks.
