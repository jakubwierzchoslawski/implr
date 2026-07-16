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
