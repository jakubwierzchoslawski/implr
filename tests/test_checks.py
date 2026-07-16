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


# --- Fingerprint verification in check_workspace ---
from implr_validate.fingerprint import contradiction_fingerprint

_FP_FIELDS = {
    "source_a": "login-spec.md §1", "statement_a": "Lockout after 3 failed attempts",
    "source_b": "login-spec.md §4", "statement_b": "Lockout after 5 failed attempts",
    "type": "Hard conflict",
}
_SYNTH = """---
domain: authentication
synthesis_checksum: abc
---
# Domain Synthesis: Authentication

## Contradictions Detected
| ID | Fingerprint | FP-Ver | Statement A | Source A | Statement B | Source B | Type |
|----|-------------|--------|------------|---------|------------|---------|------|
| C-001 | {fp} | {ver} | Lockout after 3 failed attempts | login-spec.md §1 | Lockout after 5 failed attempts | login-spec.md §4 | Hard conflict |
"""


def _write_synth(root, fp, ver):
    d = os.path.join(root, "docs", "implr", "kb-index", "domains")
    os.makedirs(d)
    with open(os.path.join(d, "authentication-synthesis.md"), "w", encoding="utf-8") as f:
        f.write(_SYNTH.format(fp=fp, ver=ver))


class TestFingerprintVerification(unittest.TestCase):
    def setUp(self):
        self.c = load_contracts(SCHEMA_DIR)

    def test_correct_fingerprint_clean(self):
        with tempfile.TemporaryDirectory() as root:
            _write_synth(root, contradiction_fingerprint(_FP_FIELDS), "1")
            fp_findings = [f for f in check_workspace(root, self.c) if "fingerprint" in f.message.lower()]
            self.assertEqual(fp_findings, [])

    def test_wrong_fingerprint_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            _write_synth(root, "1:0000000000000000", "1")
            findings = check_workspace(root, self.c)
            self.assertTrue(any("fingerprint" in f.message.lower() for f in findings))

    def test_wrong_fp_ver_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            good = contradiction_fingerprint(_FP_FIELDS)
            _write_synth(root, good, "2")  # correct hash, wrong version column
            findings = check_workspace(root, self.c)
            self.assertTrue(any("fp-ver" in f.message.lower() or "version" in f.message.lower() for f in findings))

    def test_master_cross_domain_fingerprint_verified(self):
        m_fields = {
            "source_a": "auth/policy.md", "statement_a": "Token TTL 15 min",
            "source_b": "billing/spec.md", "statement_b": "Token TTL 30 min",
            "type": "Version drift",
        }
        good = contradiction_fingerprint(m_fields)
        master_tmpl = (
            "---\ndomains_included: [authentication, billing]\n---\n"
            "# Master Synthesis\n\n## Cross-Domain Contradictions\n"
            "| ID | Fingerprint | FP-Ver | Domain A | Statement A | Source A | Domain B | Statement B | Source B | Type |\n"
            "|----|-------------|--------|---------|------------|---------|---------|------------|---------|------|\n"
            "| C-010 | {fp} | 1 | authentication | Token TTL 15 min | auth/policy.md | billing | Token TTL 30 min | billing/spec.md | Version drift |\n"
        )

        def _write_master(root, fp):
            kb = os.path.join(root, "docs", "implr", "kb-index")
            os.makedirs(kb)
            with open(os.path.join(kb, "master-synthesis.md"), "w", encoding="utf-8") as f:
                f.write(master_tmpl.format(fp=fp))

        with tempfile.TemporaryDirectory() as root:
            _write_master(root, good)
            self.assertEqual([f for f in check_workspace(root, self.c) if "fingerprint" in f.message.lower()], [])
        with tempfile.TemporaryDirectory() as root:
            _write_master(root, "1:0000000000000000")
            self.assertTrue(any("fingerprint" in f.message.lower() for f in check_workspace(root, self.c)))


# --- Task 8: repo prose checks ---
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


if __name__ == "__main__":
    unittest.main()
