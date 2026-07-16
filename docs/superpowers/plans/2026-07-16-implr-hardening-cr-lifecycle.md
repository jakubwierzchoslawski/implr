# implr Hardening — Plan 2: Delta-Safe CR Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Change Request flow into one coherent, auditable, delta-safe path — explicit CR targets, a real `needs-rework` plan state with enforced transitions, `ba-cr` creating new requirements, an idempotent executor that skips genuinely-current tasks via a task fingerprint, and a complete CR audit trail (CR stamping + `cr-log.md`).

**Architecture:** Builds on Plan 1's `status-vocabulary.json`, `implr_validate`, and fingerprint helper. Adds new frontmatter fields to the CR and plan schemas, a second deterministic fingerprint (`task_fingerprint`) in the validator, new workspace checks, and prompt-contract edits across `ba-cr`, `cr-impact-analyzer`, `cr-applier`, `dev-planner`, `dev-executor`, `plan-runner`, and `task-executor`. Hashing stays in code (the orchestrators call the validator), never hand-computed by an LLM.

**Tech Stack:** Same as Plan 1 — Python 3.8+ stdlib validator with `unittest`; Markdown prompt/schema/template files. Corresponds to spec `docs/superpowers/specs/2026-07-16-implr-reliability-hardening-design.md`, workstreams **C** and **E**.

**Depends on:** Plan 1 merged (needs `status-vocabulary.json` with `plan.needs-rework`, `implr_validate`, `fingerprint.py`, the CLI, and the sample-kb fixture).

## Global Constraints

- Zero third-party dependencies in `scripts/implr_validate/`; Python 3.8+; stdlib only.
- No enum value is restated in prose that diverges from `status-vocabulary.json` (Plan 1's `--repo` check enforces this).
- Hashes are computed by `scripts/implr_validate`, never by an LLM agent.
- Commit after every task; trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Work on branch `impl/hardening-cr-lifecycle`.
- Requirement/plan/CR transition rules (from the spec, authoritative):
  - CR change kind → requirement status: additive → stays `approved`; contradictory/correction → `under-review`; override-that-replaces → old `superseded` (+`superseded_by`), new REQ created.
  - `done → needs-rework` is written ONLY by `cr-applier`.
  - `needs-rework → ready` happens ONLY via `dev-planner --replan`.
  - `dev-executor` NEVER executes a `needs-rework` plan.

---

## File Structure

**Modified — schemas/templates:**
- `scaffold/schemas/cr-schema.md` — add `targets`; document `targets` vs `applied_targets`/`excluded_targets`; add `applied_targets`/`excluded_targets` to `cr-log.md`.
- `scaffold/templates/cr-template.md` — add `targets: []`.
- `scaffold/schemas/plan-schema.md` — add `rework_cr`, `rework_reason`, `implemented_files`, `task_fingerprints`.
- `scaffold/templates/plan-template.md` — mirror the new plan fields.
- `scaffold/schemas/frontmatter-rules.json` — register new optional fields; add a `conditional_required` rule for `needs-rework`.

**Modified — validator + tests:**
- `scripts/implr_validate/fingerprint.py` — add `task_fingerprint`.
- `scripts/implr_validate/cli.py` — add `--task-fingerprint`.
- `scripts/implr_validate/checks.py` — add the `needs-rework ⇒ rework_cr` check.
- `tests/test_fingerprint.py`, `tests/test_cli.py`, `tests/test_checks.py` — cover the above.
- `tests/fixtures/sample-kb/` — add a `needs-rework` plan + a CR with `targets`; update `expected-validate.txt` if needed.

**Modified — prompts:**
- `.claude/agents/cr-impact-analyzer.md`, `.claude/agents/cr-applier.md`, `.claude/agents/task-executor.md`, `.claude/agents/plan-runner.md`
- `skills/ba-cr/SKILL.md`, `skills/ba-cr/phases/apply.md`, `skills/ba-cr/phases/impact.md`
- `skills/dev-planner/SKILL.md`, `skills/dev-executor/SKILL.md`

**Modified — seeds/docs:**
- `scaffold/seeds/cr-log.md` (new seed), `scaffold/seeds/cr-index.md`
- `docs/WORKFLOW.md`, `README.md`

---

## Task 1: CR schema & template — `targets` and audit fields

**Files:**
- Modify: `scaffold/schemas/cr-schema.md` (frontmatter block ~lines 11-40; cr-log.md block ~lines 77-96)
- Modify: `scaffold/templates/cr-template.md` (frontmatter ~lines 1-26)
- Modify: `scaffold/schemas/frontmatter-rules.json` (cr artefact type)

**Interfaces:**
- Produces: CR frontmatter gains `targets: [REQ-F-NNN, ...]` (full confirmed impact set; may be empty). `cr-log.md` gains per-run `applied_targets` / `excluded_targets`.

- [ ] **Step 1: Add `targets` to the CR schema frontmatter**

In `scaffold/schemas/cr-schema.md`, after the `affected_domains: []` line, add:

```
targets: []             # all confirmed affected requirement IDs (full impact set).
                        # written by ba-cr after the approval gate from cr-impact-analyzer's
                        # returned set. NOT the applied subset — see cr-log.md for
                        # applied_targets / excluded_targets.
```

- [ ] **Step 2: Add the audit fields to the `cr-log.md` template in the schema**

In the `cr-log.md` template block, replace the single "Excluded from apply" line with:

```
- **Applied targets:** {list of req IDs applied this run, or none}
- **Excluded targets:** {list of req IDs the user declined this run, or none}
```

Add a sentence under the block: "`targets` on the CR frontmatter is the durable full impact set; `applied_targets`/`excluded_targets` here are per-run because a later run may apply a previously excluded target."

- [ ] **Step 3: Mirror `targets` in the CR template**

In `scaffold/templates/cr-template.md`, after `affected_domains: []` add `targets: []`.

- [ ] **Step 4: Register `targets` as an optional CR field (no required change)**

In `frontmatter-rules.json`, the `cr` artefact type keeps its `required` list unchanged (targets is optional). Add a top-level `optional_fields` note for documentation only — add under the `cr` type:

```json
"optional": ["targets", "affected_domains", "before", "after", "rationale", "approved_at", "applied_at"]
```

(The validator ignores unknown/optional fields; this documents intent and is available for future checks.)

- [ ] **Step 5: Validate repo still clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

Run: `python -c "import json; json.load(open('scaffold/schemas/frontmatter-rules.json')); print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add scaffold/schemas/cr-schema.md scaffold/templates/cr-template.md scaffold/schemas/frontmatter-rules.json
git commit -m "feat(cr): add CR targets and applied/excluded audit fields"
```

---

## Task 2: Plan schema & template — rework and provenance fields

**Files:**
- Modify: `scaffold/schemas/plan-schema.md` (frontmatter block ~lines 13-38)
- Modify: `scaffold/templates/plan-template.md`
- Modify: `scaffold/schemas/frontmatter-rules.json`

**Interfaces:**
- Produces: plan frontmatter gains `rework_cr` (CR id or blank), `rework_reason` (text or blank), `implemented_files` (list, filled by plan-runner), and `task_fingerprints` (map `TASK-NNN → "t1:<hash>"`, filled by plan-runner).

- [ ] **Step 1: Add the fields to `plan-schema.md`**

After the `blocked_reason:` line, add:

```
rework_cr:                       # CR id that put this plan in needs-rework, else blank
rework_reason:                   # short text when status is needs-rework, else blank
implemented_files: []            # files written for this plan; set by plan-runner on completion
task_fingerprints: {}            # { TASK-NNN: "t1:<hash>" } recorded by plan-runner per task
```

Add to the Status Lifecycle section a note: "`needs-rework` is set only by `cr-applier` (from `done`); the only exit is `dev-planner --replan`, which returns the plan to `ready`. See `status-vocabulary.json`."

- [ ] **Step 2: Mirror the fields in `plan-template.md`**

Add the same four frontmatter lines to the template's frontmatter.

- [ ] **Step 3: Add a conditional-required rule to `frontmatter-rules.json`**

Under the `plan` artefact type, add:

```json
"conditional_required": [
  {"when_status": "needs-rework", "require": ["rework_cr"]}
]
```

- [ ] **Step 4: Validate**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 5: Commit**

```bash
git add scaffold/schemas/plan-schema.md scaffold/templates/plan-template.md scaffold/schemas/frontmatter-rules.json
git commit -m "feat(plan): add rework_cr/rework_reason and provenance fields"
```

---

## Task 3: `task_fingerprint` helper + `--task-fingerprint` CLI

**Files:**
- Modify: `scripts/implr_validate/fingerprint.py`
- Modify: `scripts/implr_validate/cli.py`
- Modify: `tests/test_fingerprint.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `TASK_FINGERPRINT_VERSION: int = 1`; `task_fingerprint(fields: dict) -> str` returning `"t1:<16-hex>"`. Required keys: `task_body, ac_ids, ac_text, files, tests_first, requirement_updated_at, arch_excerpt_hash, interfaces_contracts, applied_nfrs, standards_card_hash, test_runner`. List fields are order-independent. CLI `--task-fingerprint FILE.json` prints the value.

- [ ] **Step 1: Write the failing tests (append to `tests/test_fingerprint.py`)**

```python
# append to tests/test_fingerprint.py
from implr_validate.fingerprint import task_fingerprint, TASK_FINGERPRINT_VERSION

TASK = {
    "task_body": "Add reset endpoint",
    "ac_ids": ["AC-001", "AC-002"],
    "ac_text": ["given valid token — reset", "given expired token — reject"],
    "files": ["src/auth.py", "tests/test_auth.py"],
    "tests_first": ["test reset ok", "test expired rejected"],
    "requirement_updated_at": "2026-01-01T00:00:00Z",
    "arch_excerpt_hash": "abc123",
    "interfaces_contracts": "IAuthRepo.reset()",
    "applied_nfrs": "p99<200ms",
    "standards_card_hash": "def456",
    "test_runner": "pytest",
}


class TestTaskFingerprint(unittest.TestCase):
    def test_prefix(self):
        self.assertTrue(task_fingerprint(TASK).startswith("t%d:" % TASK_FINGERPRINT_VERSION))

    def test_list_order_independent(self):
        t2 = dict(TASK)
        t2["ac_ids"] = ["AC-002", "AC-001"]
        t2["files"] = ["tests/test_auth.py", "src/auth.py"]
        self.assertEqual(task_fingerprint(TASK), task_fingerprint(t2))

    def test_standards_change_changes_fingerprint(self):
        t2 = dict(TASK)
        t2["standards_card_hash"] = "CHANGED"
        self.assertNotEqual(task_fingerprint(TASK), task_fingerprint(t2))

    def test_nfr_change_changes_fingerprint(self):
        t2 = dict(TASK)
        t2["applied_nfrs"] = "p99<100ms"
        self.assertNotEqual(task_fingerprint(TASK), task_fingerprint(t2))

    def test_missing_field_raises(self):
        t2 = dict(TASK)
        del t2["test_runner"]
        with self.assertRaises(KeyError):
            task_fingerprint(t2)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_fingerprint -v`
Expected: FAIL — `ImportError: cannot import name 'task_fingerprint'`.

- [ ] **Step 3: Implement in `fingerprint.py`**

Add below the existing code (do not change `contradiction_fingerprint`):

```python
# append to scripts/implr_validate/fingerprint.py
TASK_FINGERPRINT_VERSION = 1

_TASK_FIELDS = [
    "task_body", "ac_ids", "ac_text", "files", "tests_first",
    "requirement_updated_at", "arch_excerpt_hash", "interfaces_contracts",
    "applied_nfrs", "standards_card_hash", "test_runner",
]
_TASK_LIST_FIELDS = {"ac_ids", "ac_text", "files", "tests_first"}
_TASK_PASSTHROUGH = {"arch_excerpt_hash", "standards_card_hash"}


def task_fingerprint(fields):
    for k in _TASK_FIELDS:
        if k not in fields:
            raise KeyError("missing task fingerprint field: %s" % k)
    payload = {"version": TASK_FINGERPRINT_VERSION}
    for k in _TASK_FIELDS:
        v = fields[k]
        if k in _TASK_LIST_FIELDS:
            payload[k] = sorted(_normalize(item) for item in v)
        elif k in _TASK_PASSTHROUGH:
            payload[k] = str(v)
        else:
            payload[k] = _normalize(v)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return "t%d:%s" % (TASK_FINGERPRINT_VERSION, digest[:16])
```

- [ ] **Step 4: Add `--task-fingerprint` to `cli.py`**

Add the argument next to `--fingerprint`:

```python
    parser.add_argument("--task-fingerprint", metavar="FILE", help="print task fingerprint of a JSON fields file")
```

Import it: change the fingerprint import line to
`from .fingerprint import contradiction_fingerprint, task_fingerprint`.

In the required-mode guard, include it:
```python
    if not (args.repo or args.workspace is not None or args.fingerprint or args.task_fingerprint):
```

Add a handler block right after the `--fingerprint` handler:
```python
    if args.task_fingerprint:
        with open(args.task_fingerprint, encoding="utf-8") as f:
            fields = json.load(f)
        sys.stdout.write(task_fingerprint(fields) + "\n")
        return 0
```

- [ ] **Step 5: Add a CLI test (append to `tests/test_cli.py`)**

```python
# append to tests/test_cli.py (inside TestCli or as a new method)
    def test_task_fingerprint_mode(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "t.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({
                    "task_body": "b", "ac_ids": ["AC-001"], "ac_text": ["x"],
                    "files": ["a.py"], "tests_first": ["t"], "requirement_updated_at": "z",
                    "arch_excerpt_hash": "h", "interfaces_contracts": "i",
                    "applied_nfrs": "n", "standards_card_hash": "s", "test_runner": "pytest",
                }, f)
            rc = main(["--task-fingerprint", p, "--schema-dir", os.path.join(REPO_ROOT, "scaffold", "schemas")])
            self.assertEqual(rc, 0)
```

- [ ] **Step 6: Run full suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
git add scripts/implr_validate/fingerprint.py scripts/implr_validate/cli.py tests/test_fingerprint.py tests/test_cli.py
git commit -m "feat(validate): add task_fingerprint helper and --task-fingerprint mode"
```

---

## Task 4: Workspace check — `needs-rework` requires `rework_cr`

**Files:**
- Modify: `scripts/implr_validate/checks.py`
- Modify: `tests/test_checks.py`

**Interfaces:**
- Consumes: `Finding`, `contracts.artefact_types[...]["conditional_required"]`.
- Produces: `check_artefact_file` now enforces `conditional_required` rules — when a field named in `when_status` matches the artefact's `status`, every field in `require` must be present and non-empty.

- [ ] **Step 1: Write the failing test (append to `tests/test_checks.py`)**

```python
# append to tests/test_checks.py
VALID_PLAN_REWORK = """---
plan_id: PLAN-F-001
slug: x
title: "Impl"
linked_requirement: REQ-F-001
type: functional
status: needs-rework
complexity: M
tdd_required: true
rework_cr: CR-014
created_at: 2026-01-01T00:00:00Z
updated_at: 2026-01-01T00:00:00Z
---
# body
"""


class TestConditionalRequired(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def _write_plan(self, tmp, text):
        p = os.path.join(tmp, "PLAN-F-001-x.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_needs_rework_with_cr_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(check_artefact_file(self._write_plan(tmp, VALID_PLAN_REWORK), "plan", self.c), [])

    def test_needs_rework_without_cr_flagged(self):
        bad = VALID_PLAN_REWORK.replace("rework_cr: CR-014\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            findings = check_artefact_file(self._write_plan(tmp, bad), "plan", self.c)
            self.assertTrue(any("rework_cr" in f.message for f in findings))
```

- [ ] **Step 2: Run to verify the second test fails**

Run: `python -m unittest tests.test_checks.TestConditionalRequired -v`
Expected: `test_needs_rework_without_cr_flagged` FAILS (no such check yet).

- [ ] **Step 3: Add the conditional-required logic to `check_artefact_file`**

In `checks.py`, before the final `return findings` of `check_artefact_file`, add:

```python
    for rule in spec.get("conditional_required", []):
        if fm.get("status") == rule["when_status"]:
            for req_field in rule["require"]:
                if req_field not in fm or fm[req_field] == "":
                    findings.append(Finding("error", path, "status %s requires field %s" % (rule["when_status"], req_field)))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_checks -v`
Expected: PASS (all, including both TestConditionalRequired tests).

- [ ] **Step 4b: Add a CR-`targets` cross-reference test (append to `tests/test_checks.py`)**

This closes spec cross-ref item "CR targets" (deferred from Plan 1 because `targets` is a Plan 2
field). Extend the workspace helper to drop a CR under `docs/kb/change-requests/` and assert a
dangling target is flagged.

```python
# append to tests/test_checks.py
CR_WITH_TARGET = """---
cr_id: CR-001
slug: x
title: "A change"
status: draft
change_type: correction
source: cli-direct
targets: [REQ-F-001]
created_at: 2026-01-01T00:00:00Z
---
# CR-001
"""


class TestCrTargets(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def _ws_with_cr(self, root, cr_text):
        _mk_workspace(root, with_plan=False)
        cr_dir = os.path.join(root, "docs", "kb", "change-requests")
        os.makedirs(cr_dir)
        with open(os.path.join(cr_dir, "CR-001-x.md"), "w", encoding="utf-8") as f:
            f.write(cr_text)
        # index the CR so index-agreement stays clean
        with open(os.path.join(root, "docs", "implr", "requirements", "cr-index.md"), "w", encoding="utf-8") as f:
            f.write("# CR Index\n\n| CR-001 | ok |\n")

    def test_valid_target_clean(self):
        with tempfile.TemporaryDirectory() as root:
            self._ws_with_cr(root, CR_WITH_TARGET)
            self.assertEqual([f for f in check_workspace(root, self.c) if "target" in f.message.lower()], [])

    def test_dangling_target_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._ws_with_cr(root, CR_WITH_TARGET.replace("REQ-F-001", "REQ-F-404"))
            self.assertTrue(any("REQ-F-404" in f.message for f in check_workspace(root, self.c)))
```

- [ ] **Step 4c: Add the CR-targets check to `check_workspace`**

In `checks.py` `check_workspace`, collect CR frontmatter in the discovery loop
(`if atype == "cr": crs.append((path, fm))`, initialising `crs = []`), then after the
`superseded_by` block add:

```python
    # CR targets resolve to existing requirements
    for path, fm in crs:
        for tgt in fm.get("targets", []) or []:
            if tgt not in req_ids:
                findings.append(Finding("error", path, "CR target %s does not exist" % tgt))
```

Run: `python -m unittest tests.test_checks -v`
Expected: PASS (including `TestCrTargets`).

- [ ] **Step 5: Commit**

```bash
git add scripts/implr_validate/checks.py tests/test_checks.py
git commit -m "feat(validate): enforce needs-rework rework_cr and CR target resolution"
```

---

## Task 5: `cr-impact-analyzer` returns targets, stays read-only

**Files:**
- Modify: `.claude/agents/cr-impact-analyzer.md` (Work ~lines 27-37; Return summary ~lines 44-64)

**Interfaces:**
- Produces: return summary gains `confirmed_targets: [REQ-F-NNN, ...]` (author-supplied `targets` confirmed + any newly discovered). The agent writes nothing (already read-only; make it explicit).

- [ ] **Step 1: Add author-targets input and the confirmed-targets output**

In the Inputs block, note the CR may already carry `targets`. In Work, add:
"Start from the CR's `targets` (author-supplied, possibly empty). Confirm each still exists and is affected; add any additional affected requirement you discover via Grep. The union is `confirmed_targets`. **Write nothing** — you are read-only; `ba-cr` persists the set after the approval gate."

- [ ] **Step 2: Add `confirmed_targets` to the return summary**

Add to the return YAML, above `affected_requirements`:
```
confirmed_targets: [REQ-F-NNN, ...]   # full impact set; ba-cr writes this to CR frontmatter
```

- [ ] **Step 3: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/cr-impact-analyzer.md
git commit -m "feat(cr): impact-analyzer returns confirmed_targets (read-only)"
```

---

## Task 6: `ba-cr` — all/selected/none gate, write targets, single path

**Files:**
- Modify: `skills/ba-cr/SKILL.md` (Phase 3 ~lines 61-76; Phase 4 ~lines 78-84)
- Modify: `skills/ba-cr/phases/apply.md`

**Interfaces:**
- Consumes: `confirmed_targets` (Task 5). Produces: an approval gate offering `all / selected / none`; `ba-cr` writes CR `targets` from `confirmed_targets`; dispatches `cr-applier` only for the applied subset.

- [ ] **Step 1: Rewrite Phase 3 approval gate**

Replace the `Approve and apply? (yes / no / impact-only)` prompt block with:

```
Approve and apply?
  all      — apply to every affected requirement/plan
  selected — you pick which requirement IDs to apply; the rest are excluded this run
  none     — do not apply (optionally save impact report)
  impact-only — save the impact report to the CR and stop
```

Add: "On `selected`, prompt for the requirement IDs to apply. Record `applied_targets` (chosen) and `excluded_targets` (the rest of `confirmed_targets`). On `none`/`impact-only`, stop without applying."

- [ ] **Step 2: Persist `targets` after the gate**

Add a step at the end of Phase 3 (after approval, before dispatch):
"Write the full `confirmed_targets` set to the CR file's `targets:` frontmatter. Set the CR `status: approved` and stamp `approved_at: <ISO timestamp>`."

- [ ] **Step 3: Restrict Phase 4 dispatch to the applied subset**

In Phase 4, change "For each affected requirement and each affected plan" to "For each requirement in `applied_targets` and each plan linked to those requirements". Keep the parallelism cap at 5.

- [ ] **Step 4: Note the single apply path**

Add a line under Phase 1: "`ba-cr` is the only path that applies a CR. `/ba-requirements-gen --reprocess` is for re-deriving from changed KB source documents, not for CRs."

- [ ] **Step 5: Update `phases/apply.md` scope**

Ensure the dispatch scope documents that only `applied_targets` requirements (and their plans) are dispatched.

- [ ] **Step 6: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 7: Commit**

```bash
git add skills/ba-cr/SKILL.md skills/ba-cr/phases/apply.md
git commit -m "feat(ba-cr): all/selected/none gate; write CR targets; single apply path"
```

---

## Task 7: `ba-cr` — stamp the CR file & write `cr-log.md`

**Files:**
- Modify: `skills/ba-cr/SKILL.md` (Phase 6 ~lines 96-99; Phase 7 ~lines 101-110; Failure handling ~lines 112-117)
- Create: `scaffold/seeds/cr-log.md`

**Interfaces:**
- Produces: on full success `status: applied` + `applied_at`; `cr-log.md` gets an appended entry per run with `applied_targets`/`excluded_targets`; partial failure leaves CR `approved`.

- [ ] **Step 1: Create the `cr-log.md` seed**

`scaffold/seeds/cr-log.md`:

```markdown
# cr-log
# Append-only run history for ba-cr. Newest entry first.
```

- [ ] **Step 2: Rewrite Phase 6 to include CR stamping and cr-log**

Replace Phase 6 body with:

```
### Phase 6 — Stamp CR, write logs and indices

1. If every dispatched applier succeeded: set the CR file `status: applied` and stamp
   `applied_at: <ISO timestamp>`. If any applier failed: leave `status: approved` and do not
   stamp applied_at.
2. Prepend an entry to `docs/implr/requirements/cr-log.md` per cr-schema.md, including
   `Applied targets` and `Excluded targets` for this run, and any failures.
3. Add/update the CR row in `cr-index.md`.
4. Append entries to `requirements-log.md` for each applied requirement and to `plans-log.md`
   for each affected plan.
```

- [ ] **Step 3: Strengthen the partial-failure rule**

In Failure handling, replace the applier-fail line with:
"Applier fails on one target → report which; leave successfully-applied targets applied; do NOT roll back; do NOT stamp the CR `applied`. Record the failure in `cr-log.md`. The CR stays `approved` so a re-run can complete it."

- [ ] **Step 4: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 5: Commit**

```bash
git add skills/ba-cr/SKILL.md scaffold/seeds/cr-log.md
git commit -m "feat(ba-cr): stamp CR lifecycle and write append-only cr-log.md"
```

---

## Task 8: `ba-cr` — create new requirements from a CR

**Files:**
- Modify: `skills/ba-cr/SKILL.md` (add Phase 4.5)

**Interfaces:**
- Consumes: `cr-impact-analyzer`'s `new_requirements_proposed` count and descriptions; `requirements-domain-worker` + `.staging/` machinery (from ba-requirements-gen).
- Produces: new REQ files created at `status: draft` (needing human approval), with sequential IDs.

- [ ] **Step 1: Add Phase 4.5 to `ba-cr/SKILL.md`**

Insert after Phase 4:

```
### Phase 4.5 — Create genuinely-new requirements (if any)

If impact analysis reported new requirements are needed (not just amendments):

1. Determine the target domain for each new requirement (from the CR's affected_domains).
2. Create the staging dir `docs/implr/requirements/.staging/<domain>/` (delete first if present,
   per the ba-requirements-gen Windows/Unix rules).
3. Dispatch `requirements-domain-worker` with a `domain_envelope` whose `mode: create`, passing
   the CR description as the source material and the requirements-card inline (same envelope
   shape ba-requirements-gen uses).
4. After the worker returns, assign the next sequential `REQ-F-NNN`/`REQ-N-NNN` (continue from
   `requirements-index.md`), move the staged file into `functional/` or `non-functional/`, set
   `status: draft`, and add the CR filename to `source_docs`.
5. Report the new REQ IDs and that they require human approval before planning.
```

Add to the Phase 7 report: `New requirements created: {list of REQ ids (draft — need approval)}`.

- [ ] **Step 2: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 3: Commit**

```bash
git add skills/ba-cr/SKILL.md
git commit -m "feat(ba-cr): create new requirements from a CR via requirements-domain-worker"
```

---

## Task 9: `cr-applier` — needs-rework transition & requirement status table

**Files:**
- Modify: `.claude/agents/cr-applier.md` (Work ~lines 30-42; Return summary ~lines 44-55)

**Interfaces:**
- Consumes: `status_change` in scope. Produces: plans go `done → needs-rework` with `rework_cr`/`rework_reason`; requirement status follows the C.5 table.

- [ ] **Step 1: Replace the plan-replan behavior**

Replace the `action: replan` bullet with:
"For `action: replan`: set the plan `status: needs-rework`, `rework_cr: <cr_id>`,
`rework_reason: <one line>`. Do NOT regenerate the plan body and do NOT write a
`replan_required` marker (that token is retired). Only `dev-planner --replan` returns the plan
to `ready`."

- [ ] **Step 2: Add the requirement status-transition table**

Replace the requirement bullets with:

```
For requirements, set status per the change kind (the orchestrator passes change_kind in scope):
- additive (new AC): keep status `approved`; append the new AC(s); do not rewrite existing ACs.
- contradictory or correction: set status `under-review`; replace the rule; add an Open Question
  citing the CR. (dev-planner will not replan until a human re-approves.)
- override that replaces the requirement: set the old requirement `status: superseded` and
  `superseded_by: <new REQ id>`. (ba-cr creates the replacement; the applier does not.)
Always add the CR filename to `source_docs`.
```

- [ ] **Step 3: Update the return summary**

Change `action_applied` values to `patch | needs-rework-set | requirement-updated` and
`status` to `applied | needs-rework`. Remove `replan_marker_set`.

- [ ] **Step 4: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 5: Commit**

```bash
git add .claude/agents/cr-applier.md
git commit -m "feat(cr): applier sets needs-rework and applies requirement status transitions"
```

---

## Task 10: `dev-planner` — `--replan` is the only exit from `needs-rework`

**Files:**
- Modify: `skills/dev-planner/SKILL.md` (Parameters ~line 28; Phase 1 ~lines 35-42)

**Interfaces:**
- Produces: `--replan` accepts `needs-rework` (and `ready`) plans and returns them to `ready`, preserving `plan_id`; a precondition documents that this is the sole `needs-rework → ready` transition.

- [ ] **Step 1: Clarify `--replan` semantics**

Change the `--replan` parameter line to:
"`/dev-planner --replan REQ-F-001` — regenerate an existing plan (preserve plan_id). Valid when
the plan is `ready`, `done`, or `needs-rework`. Regeneration sets the plan back to `ready` and
clears `rework_cr`/`rework_reason`. This is the ONLY transition out of `needs-rework`."

- [ ] **Step 2: Add a precondition note in Phase 1**

Add: "When replanning a `needs-rework` plan, read its `rework_cr`/`rework_reason` and incorporate
the CR-driven changes; after writing, set `status: ready` and blank the rework fields."

- [ ] **Step 3: Verify repo clean**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

- [ ] **Step 4: Commit**

```bash
git add skills/dev-planner/SKILL.md
git commit -m "feat(dev-planner): --replan is the sole exit from needs-rework"
```

---

## Task 11: `dev-executor` + `plan-runner` — halt on needs-rework; record provenance

**Files:**
- Modify: `skills/dev-executor/SKILL.md` (Phase 1 ~lines 38-42; Failure handling)
- Modify: `.claude/agents/plan-runner.md` (Inputs ~lines 26-35; Work step 2 ~lines 58-63)
- Modify: `.claude/agents/task-executor.md` (Inputs; Work; Return summary)

**Interfaces:**
- Consumes: `--task-fingerprint` (Task 3). Produces: `dev-executor` refuses `needs-rework`; `plan-runner` computes and stores `task_fingerprints` and `implemented_files` on completion and passes each task's `prior_fingerprint` into the executor envelope.

- [ ] **Step 1: `dev-executor` refuses `needs-rework`**

In Phase 1, after the status validation, add:
"If a named or `--all`-selected plan has `status: needs-rework`, do NOT execute it. Emit:
`❌ PLAN-F-NNN is needs-rework (CR {rework_cr}). Run /dev-planner --replan {plan} first.` and
skip it."

- [ ] **Step 2: `plan-runner` computes and stores fingerprints + implemented_files**

In `plan-runner.md` Work step 2 (Update plan status), add:
"On `status: done`: set `implemented_files:` to the union of all task `files_created`/
`files_modified`. For each task, compute its fingerprint by writing the task's fingerprint
fields to a temp JSON file and running
`python scripts/implr_validate --task-fingerprint <tmp>`; store the printed value in
`task_fingerprints[TASK-NNN]`."

Add to Inputs a note that each envelope may carry `prior_fingerprint` (from
`plan.task_fingerprints[TASK-NNN]`), passed through to task-executor.

- [ ] **Step 3: `task-executor` idempotent skip**

In `task-executor.md` Inputs, add to the envelope:
```
  prior_fingerprint: "t1:<hash> or empty"   # from plan.task_fingerprints, if any
```

Add a new Work step 0 before step 1:
"0. **Idempotent skip check.** If `prior_fingerprint` is non-empty, recompute this task's
fingerprint from the envelope fields (the orchestrator supplies the same fields; if you cannot
recompute, treat as non-matching). If it matches `prior_fingerprint` AND the task's tests
currently pass when run, do NOT re-implement: return `task_status: done` with a note
`already-satisfied` and no file changes. Otherwise proceed with the normal flow. (Note: the skip
relies on a live test run, not a stored pass flag — there is no `prior_tests_pass` in Plan 2.
Plan 3's `test-results.md` is for review evidence, a separate concern.)"

Add `already_satisfied: true | false` to the return summary.

- [ ] **Step 4: Verify repo clean and suite green**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

Run: `python -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/dev-executor/SKILL.md .claude/agents/plan-runner.md .claude/agents/task-executor.md
git commit -m "feat(dev-executor): halt on needs-rework; record fingerprints; idempotent task skip"
```

---

## Task 12: Fixtures — needs-rework plan and CR with targets

**Files:**
- Create: `tests/fixtures/sample-kb/docs/implr/plans/functional/PLAN-F-001-login.md`
- Create: `tests/fixtures/sample-kb/docs/implr/plans/plans-index.md`
- Modify: `tests/fixtures/sample-kb/docs/kb/change-requests/CR-001-additive.md`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: fixture coverage that a valid `needs-rework` plan (with `rework_cr`) and a CR with `targets` both pass `--workspace`, and that a `needs-rework` plan missing `rework_cr` fails.

- [ ] **Step 1: Add a valid plan to the fixture (status ready, links REQ-F-001)**

`tests/fixtures/sample-kb/docs/implr/plans/functional/PLAN-F-001-login.md`:

```markdown
---
plan_id: PLAN-F-001
slug: login
title: "User Login Implementation"
linked_requirement: REQ-F-001
type: functional
status: ready
complexity: M
tdd_required: true
rework_cr:
rework_reason:
implemented_files: []
task_fingerprints: {}
created_at: 2026-01-01T00:00:00Z
updated_at: 2026-01-01T00:00:00Z
---
# PLAN-F-001 — User Login Implementation

## Acceptance Criteria Coverage
- AC-001: → TASK-001
- AC-002: → TASK-001
```

- [ ] **Step 1b: Add the plans index (required by the index-agreement check)**

`tests/fixtures/sample-kb/docs/implr/plans/plans-index.md`:

```markdown
# Plans Index

> Maintained by dev-planner. Do not edit manually.

## Functional Plans
| ID | Title | Requirement | Complexity | TDD | Status | File |
|----|-------|-------------|-----------|-----|--------|------|
| PLAN-F-001 | User Login Implementation | REQ-F-001 | M | true | ready | functional/PLAN-F-001-login.md |
```

- [ ] **Step 2: Add `targets` to the CR fixture**

In `CR-001-additive.md`, add `targets: [REQ-F-001]` after `source: cli-direct`.

- [ ] **Step 3: Add fixture tests (append to `tests/test_cli.py` `TestFixture`)**

```python
    def test_needs_rework_missing_cr_fails(self):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "sample-kb")
            shutil.copytree(FIXTURE, dst)
            plan = os.path.join(dst, "docs", "implr", "plans", "functional", "PLAN-F-001-login.md")
            with open(plan, encoding="utf-8") as f:
                text = f.read()
            with open(plan, "w", encoding="utf-8") as f:
                f.write(text.replace("status: ready", "status: needs-rework"))  # no rework_cr
            rc = main(["--workspace", dst, "--schema-dir", SCHEMA_DIR])
            self.assertEqual(rc, 1)
```

- [ ] **Step 4: Confirm the clean fixture still passes**

Run: `python scripts/implr_validate --workspace tests/fixtures/sample-kb --schema-dir scaffold/schemas`
Expected: `implr-validate: OK` (matches `expected-validate.txt`).

Run: `python -m unittest tests.test_cli -v`
Expected: PASS (including the new test).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/sample-kb tests/test_cli.py
git commit -m "test(validate): fixture coverage for needs-rework plan and CR targets"
```

---

## Task 13: WORKFLOW & README — CR lifecycle, transitions; final sweep

**Files:**
- Modify: `docs/WORKFLOW.md` (CR section ~lines 277-289, 437-442, 489-499; Plan section ~lines 244-269)
- Modify: `README.md` (CR + Plans sections)

**Interfaces:**
- No code interface. Deliverable: docs describe the single delta-safe path, `needs-rework`, the requirement transition table, targets vs applied/excluded, the CR audit artefacts — and the repo validates clean.

- [ ] **Step 1: Rewrite the WORKFLOW CR section**

Describe: author (optional) `targets` → read-only impact analysis returns `confirmed_targets` →
all/selected/none gate → ba-cr writes `targets`, applies to `applied_targets`, creates new
requirements as needed → cr-applier sets requirement transitions (table) and `done → needs-rework`
on plans → `dev-planner --replan` returns plans to `ready` → CR stamped `applied`, `cr-log.md`
entry with applied/excluded. Include the requirement transition table verbatim from Global
Constraints.

- [ ] **Step 2: Update the WORKFLOW plan transition table**

Add `done → needs-rework (cr-applier)` and `needs-rework → ready (dev-planner --replan)`; keep
review-failure as `done → in-progress`. Cite `status-vocabulary.json`.

- [ ] **Step 3: Update README CR and Plans sections**

Reflect `needs-rework`, the single apply path, all/selected/none, CR stamping + cr-log, and
new-requirement creation. Remove any lingering `replan_required` phrasing.

- [ ] **Step 4: Grep sweep for retired token on live surfaces**

Run:
```
grep -rn "replan_required\|replan_marker_set\|impact-analysed" README.md docs/WORKFLOW.md scaffold/ skills/ .claude/ || echo "none"
```
Expected: `none`

- [ ] **Step 5: Final validation + full suite**

Run: `python scripts/implr_validate --repo --root . --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

Run: `python scripts/implr_validate --workspace tests/fixtures/sample-kb --schema-dir scaffold/schemas`
Expected: `implr-validate: OK`

Run: `python -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/WORKFLOW.md
git commit -m "docs: document delta-safe CR lifecycle, needs-rework, and requirement transitions"
```

---

## Self-Review Notes

- **C.1 targets:** CR field (T1), impact-analyzer returns confirmed_targets read-only (T5), ba-cr writes after gate (T6). ✓
- **C.2 single path:** ba-cr owns apply; reprocess reserved for KB docs (T6). ✓
- **C.3 new reqs:** ba-cr Phase 4.5 via requirements-domain-worker (T8). ✓
- **C.4 needs-rework:** fields (T2), conditional-required check (T4), cr-applier sets it (T9), dev-planner sole exit (T10), dev-executor halts (T11). ✓
- **C.5 requirement transitions:** table in cr-applier (T9) and WORKFLOW (T13). ✓
- **C.6/C.7 idempotent executor + provenance:** task_fingerprint helper (T3), plan-runner records fingerprints+implemented_files (T11), task-executor skip on fingerprint-match + live test pass — **no `prior_tests_pass` dependency** (T11); test-results persistence stays a Plan 3 concern. ✓
- **C.8 traceability + E audit trail:** CR stamping, cr-log with applied/excluded (T7), cr-log seed (T7). ✓
- **E all/selected/none:** T6. ✓
- **CR-targets cross-ref (spec §B):** deferred from Plan 1 (field introduced here); validated in T4 (Steps 4b/4c). ✓
- **Fixture index files:** Plan 1's index-agreement check requires the fixture to ship indices — cr-index in Plan 1, plans-index added in T12. ✓
- **Placeholder scan:** prompt-edit steps show exact text to add; code steps show full code. ✓
- **Type consistency:** `task_fingerprint`/`TASK_FINGERPRINT_VERSION` (T3) used by CLI (T3) and plan-runner (T11); `conditional_required` shape defined in T2, consumed in T4; `confirmed_targets` produced T5, consumed T6.
- **Deferred to Plan 3 (correct):** review test-awareness, preconditions in every skill, commit default. This plan leaves `commit_mode: auto` as-is (Plan 3 flips it).
