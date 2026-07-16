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
