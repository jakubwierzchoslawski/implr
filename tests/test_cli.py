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

    def test_source_ref_mode(self):
        rc = main(["--source-ref", "scaffold", "--root", REPO_ROOT, "--schema-dir", os.path.join(REPO_ROOT, "scaffold", "schemas")])
        self.assertEqual(rc, 0)


# --- Task 10: sample-kb fixture integration tests ---
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

    def test_broken_fingerprint_fails(self):
        import shutil, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "sample-kb")
            shutil.copytree(FIXTURE, dst)
            synth = os.path.join(dst, "docs", "implr", "kb-index", "domains", "authentication-synthesis.md")
            with open(synth, encoding="utf-8") as f:
                text = f.read()
            with open(synth, "w", encoding="utf-8") as f:
                f.write(text.replace("1:d5fe836f0aa838fd", "1:0000000000000000"))
            rc = main(["--workspace", dst, "--schema-dir", SCHEMA_DIR])
            self.assertEqual(rc, 1)

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


if __name__ == "__main__":
    unittest.main()
