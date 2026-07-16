# tests/test_frontmatter.py
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.frontmatter import split_frontmatter, parse_frontmatter, FrontmatterError


class TestSplit(unittest.TestCase):
    def test_no_frontmatter_returns_none(self):
        fm, body = split_frontmatter("# Title\n\ntext\n")
        self.assertIsNone(fm)
        self.assertEqual(body, "# Title\n\ntext\n")

    def test_extracts_block(self):
        fm, body = split_frontmatter("---\na: 1\n---\n# Body\n")
        self.assertEqual(fm, "a: 1")
        self.assertEqual(body, "# Body\n")


class TestParse(unittest.TestCase):
    def test_scalar_and_quoted(self):
        d = parse_frontmatter("---\nreq_id: REQ-F-001\ntitle: \"A Title\"\n---\n")
        self.assertEqual(d["req_id"], "REQ-F-001")
        self.assertEqual(d["title"], "A Title")

    def test_empty_value(self):
        d = parse_frontmatter("---\napproved_at:\n---\n")
        self.assertEqual(d["approved_at"], "")

    def test_inline_list(self):
        d = parse_frontmatter("---\nlabels: [backend, auth]\n---\n")
        self.assertEqual(d["labels"], ["backend", "auth"])

    def test_block_list(self):
        d = parse_frontmatter("---\nsource_docs:\n  - auth-flow.md\n  - session.md\n---\n")
        self.assertEqual(d["source_docs"], ["auth-flow.md", "session.md"])

    def test_nested_mapping(self):
        d = parse_frontmatter("---\njira:\n  id: STOK-1\n  labels: [a, b]\n---\n")
        self.assertEqual(d["jira"], {"id": "STOK-1", "labels": ["a", "b"]})

    def test_inline_object_list(self):
        d = parse_frontmatter("---\ndependencies:\n  - { id: REQ-F-002, reason: \"needs user\" }\n---\n")
        self.assertEqual(d["dependencies"], [{"id": "REQ-F-002", "reason": "needs user"}])

    def test_out_of_subset_raises(self):
        with self.assertRaises(FrontmatterError):
            parse_frontmatter("---\na:\n  b:\n    c: 1\n---\n")  # two levels of nesting


if __name__ == "__main__":
    unittest.main()
