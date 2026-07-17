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


if __name__ == "__main__":
    unittest.main()
