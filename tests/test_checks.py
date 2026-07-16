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


# --- Task 7: workspace / cross-reference / index tests ---
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


if __name__ == "__main__":
    unittest.main()
