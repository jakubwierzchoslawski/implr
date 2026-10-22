import json, os, subprocess, sys, tempfile, unittest, unittest.mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from implr_validate.finalize import finalize_plan
from implr_validate.fingerprint import task_fingerprint
from implr_validate.frontmatter import parse_frontmatter

PLAN_ID = "PLAN-F-001"
PLAN_REL = "docs/implr/plans/functional/PLAN-F-001-demo.md"

PLAN_TEXT = """---
plan_id: PLAN-F-001
slug: demo
title: Demo
linked_requirement: REQ-F-001
type: functional
status: ready
blocked_reason:
implemented_files: []
task_fingerprints: {}
complexity: M
tdd_required: true
executed_at:
created_at: 2026-01-01T00:00:00Z
updated_at: 2026-01-01T00:00:00Z
---

# PLAN-F-001
"""


def fp_fields(tid):
    return {
        "task_body": "body " + tid, "ac_ids": ["AC-001"], "ac_text": ["text"],
        "files": ["src/a.py"], "tests_first": [], "requirement_updated_at": "2026-01-01",
        "arch_excerpt_hash": "arch", "interfaces_contracts": "if", "applied_nfrs": "N/A",
        "standards_card_hash": "card", "test_runner": "pytest",
    }


def result(tid, status="done", tests_pass=True, exit_code=0, **kw):
    r = {"task_id": tid, "task_status": status, "files_created": ["src/%s.py" % tid.lower()],
         "files_modified": [], "interfaces_added": [], "decisions": [], "tests_added": 1,
         "tests_pass": tests_pass, "already_satisfied": False, "test_command": "pytest",
         "test_exit_code": exit_code, "test_output_tail": "1 passed", "manual_actions": []}
    r.update(kw)
    return r


class FinalizeBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)
        os.makedirs(os.path.join(self.root, "src"))
        os.makedirs(os.path.join(self.root, "tests"))
        os.makedirs(os.path.join(self.root, os.path.dirname(PLAN_REL)))
        self.plan_path = os.path.join(self.root, PLAN_REL)
        self.write(self.plan_path, PLAN_TEXT)
        self.work = os.path.join(self.root, "docs", "implr", ".work", PLAN_ID)
        os.makedirs(self.work)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def setup_run(self, task_ids, results, commit_mode="defer", prior=None):
        meta = {"plan_id": PLAN_ID, "plan_path": PLAN_REL, "src_path": "src", "tests_path": "tests",
                "test_runner": "pytest", "commit_mode": commit_mode, "task_ids": task_ids,
                "prior_fingerprints": prior or {}}
        self.write(os.path.join(self.work, "meta.json"), json.dumps(meta))
        for tid in task_ids:
            self.write(os.path.join(self.work, tid + ".fp.json"), json.dumps(fp_fields(tid)))
        for r in results:
            self.write(os.path.join(self.work, r["task_id"] + ".result.json"), json.dumps(r))

    def fm(self):
        with open(self.plan_path, encoding="utf-8") as f:
            return parse_frontmatter(f.read())

    def results_file(self):
        return os.path.join(self.root, "docs", "implr", "plans", "test-results", PLAN_ID + "-results.md")


class TestFinalizeOutcome(FinalizeBase):
    def test_all_done(self):
        self.setup_run(["TASK-001", "TASK-002"], [result("TASK-001"), result("TASK-002")])
        summary = finalize_plan(self.work, self.root)
        fm = self.fm()
        self.assertEqual(fm["status"], "done")
        self.assertNotEqual(fm["executed_at"], "")
        self.assertEqual(sorted(fm["implemented_files"]), ["src/task-001.py", "src/task-002.py"])
        self.assertEqual(fm["task_fingerprints"]["TASK-001"], task_fingerprint(fp_fields("TASK-001")))
        self.assertEqual(summary["plan_status"], "done")
        self.assertEqual(summary["tasks_completed"], 2)
        self.assertTrue(summary["tests_pass"])
        self.assertFalse(os.path.exists(self.work))

    def test_failed_task_stops_in_progress_and_keeps_workdir(self):
        self.setup_run(["TASK-001", "TASK-002"],
                       [result("TASK-001", status="failed", tests_pass=False, exit_code=1)])
        summary = finalize_plan(self.work, self.root)
        fm = self.fm()
        self.assertEqual(fm["status"], "in-progress")
        self.assertEqual(fm["executed_at"], "")
        self.assertEqual(fm["task_fingerprints"], {})
        self.assertEqual(summary["stopping_task"], "TASK-001")
        self.assertFalse(summary["tests_pass"])
        self.assertTrue(os.path.isdir(self.work))

    def test_tests_pass_false_with_done_status_is_not_done(self):
        self.setup_run(["TASK-001"], [result("TASK-001", tests_pass=False, exit_code=1)])
        finalize_plan(self.work, self.root)
        self.assertEqual(self.fm()["status"], "in-progress")

    def test_blocked_sets_blocked_reason(self):
        self.setup_run(["TASK-001"], [result("TASK-001", status="blocked", tests_pass=True,
                                             manual_actions=["need: API key"])])
        summary = finalize_plan(self.work, self.root)
        fm = self.fm()
        self.assertEqual(fm["status"], "in-progress")
        self.assertIn("TASK-001", fm["blocked_reason"])
        self.assertEqual(summary["tasks_blocked"], 1)
        self.assertEqual(summary["manual_actions"], ["need: API key"])

    def test_missing_result_means_early_stop(self):
        self.setup_run(["TASK-001", "TASK-002"], [result("TASK-001")])
        summary = finalize_plan(self.work, self.root)
        self.assertEqual(self.fm()["status"], "in-progress")
        self.assertEqual(summary["tasks_completed"], 1)
        self.assertEqual(summary["stopping_task"], "TASK-002")

    def test_resume_merges_existing_frontmatter(self):
        text = PLAN_TEXT.replace("implemented_files: []", "implemented_files:\n  - src/old.py") \
                        .replace("task_fingerprints: {}", "task_fingerprints:\n  TASK-001: \"t1:old\"")
        self.write(self.plan_path, text)
        self.setup_run(["TASK-002"], [result("TASK-002")])
        finalize_plan(self.work, self.root)
        fm = self.fm()
        self.assertEqual(sorted(fm["implemented_files"]), ["src/old.py", "src/task-002.py"])
        self.assertEqual(fm["task_fingerprints"]["TASK-001"], "t1:old")
        self.assertIn("TASK-002", fm["task_fingerprints"])

    def test_body_and_other_fields_preserved(self):
        self.setup_run(["TASK-001"], [result("TASK-001")])
        finalize_plan(self.work, self.root)
        with open(self.plan_path, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.endswith("# PLAN-F-001\n"))
        self.assertEqual(self.fm()["title"], "Demo")


class TestFinalizeTestResults(FinalizeBase):
    def test_results_file_rows_and_skip(self):
        self.setup_run(["TASK-001", "TASK-002", "TASK-003"], [
            result("TASK-001"),
            result("TASK-002", test_command="", test_exit_code=None, test_output_tail=""),
            result("TASK-003", tests_pass=False, exit_code=1, test_output_tail="a | b\nFAILED"),
        ])
        finalize_plan(self.work, self.root)
        with open(self.results_file(), encoding="utf-8") as f:
            text = f.read()
        fm = parse_frontmatter(text)
        self.assertEqual(fm["plan_id"], PLAN_ID)
        self.assertTrue(fm["source_ref"].startswith(("git:", "fb:")))
        self.assertIn("| TASK-001 | pytest | 0 | pass | 1 passed |", text)
        self.assertIn("| TASK-002 |  |  | skip |  |", text)
        self.assertIn("| TASK-003 | pytest | 1 | fail | a \\| b<br>FAILED |", text)

    def test_executed_at_copied_from_plan_when_not_done(self):
        text = PLAN_TEXT.replace("executed_at:", "executed_at: 2026-02-02T00:00:00Z")
        self.write(self.plan_path, text)
        self.setup_run(["TASK-001"], [result("TASK-001", status="failed", tests_pass=False, exit_code=1)])
        finalize_plan(self.work, self.root)
        self.assertEqual(parse_frontmatter(open(self.results_file(), encoding="utf-8").read())["executed_at"],
                         "2026-02-02T00:00:00Z")


def git(root, *args):
    return subprocess.check_output(
        ["git", "-c", "commit.gpgsign=false"] + list(args),
        cwd=root, stderr=subprocess.DEVNULL).decode("utf-8").strip()


class TestFinalizeCommit(FinalizeBase):
    def setUp(self):
        super().setUp()
        # temp dirs on some filesystems fail git's ownership check; identity is needed to commit
        env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*",
               "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        patcher = unittest.mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def init_repo(self):
        git(self.root, "init", "-q")
        with open(os.path.join(self.work, ".gitignore"), "w") as f:
            f.write("*\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "init")

    def test_defer_leaves_git_untouched(self):
        self.init_repo()
        head = git(self.root, "rev-parse", "HEAD")
        self.setup_run(["TASK-001"], [result("TASK-001")], commit_mode="defer")
        self.write(os.path.join(self.root, "src", "task-001.py"), "x = 1\n")
        finalize_plan(self.work, self.root)
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only"), "")

    def test_auto_commits_and_source_ref_is_post_commit(self):
        self.init_repo()
        head = git(self.root, "rev-parse", "HEAD")
        self.setup_run(["TASK-001"], [result("TASK-001")], commit_mode="auto")
        self.write(os.path.join(self.root, "src", "task-001.py"), "x = 1\n")
        finalize_plan(self.work, self.root)
        self.assertNotEqual(git(self.root, "rev-parse", "HEAD"), head)
        self.assertEqual(git(self.root, "log", "-1", "--format=%s"), "feat(PLAN-F-001): implement plan tasks")
        ref = parse_frontmatter(open(self.results_file(), encoding="utf-8").read())["source_ref"]
        self.assertIn(git(self.root, "rev-parse", "HEAD")[:12], ref)


class TestFinalizeInput(FinalizeBase):
    def test_missing_meta_raises(self):
        with self.assertRaises(FileNotFoundError):
            finalize_plan(self.work, self.root)


if __name__ == "__main__":
    unittest.main()
