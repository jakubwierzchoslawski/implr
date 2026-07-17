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
