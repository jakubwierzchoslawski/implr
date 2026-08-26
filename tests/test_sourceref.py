import os, shutil, subprocess, tempfile, unittest
from implr_validate.sourceref import source_ref, source_ref_fallback

GIT = shutil.which("git")


def _git(root, *args):
    subprocess.check_call(["git"] + list(args), cwd=root,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _init_repo(root):
    """Create a minimal, isolated git repo with one committed file under src/."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "config", "core.autocrlf", "false")
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    with open(os.path.join(root, "src", "a.py"), "w", newline="\n") as f:
        f.write("x = 1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")


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


@unittest.skipUnless(GIT, "git not available on PATH")
class TestSourceRef(unittest.TestCase):
    """Exercises the real, git-backed source_ref() against an actual temporary git repo —
    no mocking. Each test builds its own repo via subprocess so it stays deterministic and
    self-contained, matching the TestSourceRefFallback style above."""

    def test_git_mode_returns_git_prefixed_ref(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            ref = source_ref(root, ["src"])
            self.assertTrue(ref.startswith("git:"), ref)

    def test_stable_for_same_clean_committed_state(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            a = source_ref(root, ["src"])
            b = source_ref(root, ["src"])
            self.assertEqual(a, b)

    def test_changes_when_tracked_file_edited_unstaged(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            baseline = source_ref(root, ["src"])
            with open(os.path.join(root, "src", "a.py"), "w", newline="\n") as f:
                f.write("x = 2  # unstaged edit\n")
            edited = source_ref(root, ["src"])
            self.assertNotEqual(baseline, edited)

    def test_changes_when_tracked_file_edit_is_staged(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            baseline = source_ref(root, ["src"])
            with open(os.path.join(root, "src", "a.py"), "w", newline="\n") as f:
                f.write("x = 2  # staged edit\n")
            unstaged = source_ref(root, ["src"])
            _git(root, "add", "-A")
            staged = source_ref(root, ["src"])
            # Staging must not make the change invisible: still different from the clean
            # baseline (the point of the fix this test guards: staged changes are captured,
            # not silently ignored by `git diff HEAD`).
            self.assertNotEqual(baseline, staged)
            # `git diff HEAD` reports both staged and unstaged changes identically here,
            # so the ref for the same edit is the same whether or not it has been staged —
            # this is expected (both are captured), not a bug.
            self.assertEqual(unstaged, staged)

    def test_changes_when_untracked_file_added(self):
        with tempfile.TemporaryDirectory() as root:
            _init_repo(root)
            baseline = source_ref(root, ["src"])
            with open(os.path.join(root, "src", "b.py"), "w", newline="\n") as f:
                f.write("y = 1\n")
            with_untracked = source_ref(root, ["src"])
            self.assertNotEqual(baseline, with_untracked)

    def test_falls_back_when_not_a_git_repo(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "src"))
            with open(os.path.join(root, "src", "a.py"), "w") as f:
                f.write("x = 1\n")
            ref = source_ref(root, ["src"])
            self.assertTrue(ref.startswith("fb:"), ref)


if __name__ == "__main__":
    unittest.main()
