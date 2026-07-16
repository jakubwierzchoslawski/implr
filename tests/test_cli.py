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
