# scripts/implr_validate/finalize.py
"""Deterministic end-of-plan bookkeeping for plan-runner: plan frontmatter, optional
commit, source_ref, test-results.md, work-dir cleanup. Standard library only."""
import datetime
import glob
import json
import os
import re
import shutil
import subprocess

from .fingerprint import task_fingerprint
from .frontmatter import parse_frontmatter, split_frontmatter
from .sourceref import source_ref


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _quote(value):
    return '"%s"' % str(value).replace("\\", "\\\\").replace('"', '\\"')


def _render(key, value):
    if isinstance(value, dict):
        if not value:
            return ["%s: {}" % key]
        return ["%s:" % key] + ["  %s: %s" % (k, _quote(v)) for k, v in value.items()]
    if isinstance(value, list):
        if not value:
            return ["%s: []" % key]
        return ["%s:" % key] + ["  - %s" % item for item in value]
    if value == "":
        return ["%s:" % key]
    return ["%s: %s" % (key, value)]


def _set_fields(text, updates):
    """Replace (or append) top-level frontmatter keys, leaving everything else byte-identical."""
    block, body = split_frontmatter(text)
    lines = block.split("\n")
    for key, value in updates.items():
        new = _render(key, value)
        for i, line in enumerate(lines):
            if line.startswith(key + ":"):
                j = i + 1
                while j < len(lines) and lines[j].startswith(" "):
                    j += 1
                lines[i:j] = new
                break
        else:
            lines.extend(new)
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def _git(root, args):
    return subprocess.run(["git"] + args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _commit(root, plan_id):
    _git(root, ["add", "-A"])
    if _git(root, ["diff", "--cached", "--quiet"]).returncode == 0:
        return
    _git(root, ["commit", "-m", "feat(%s): implement plan tasks" % plan_id])


def _cell(value):
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _results_markdown(plan_id, run_at, ref, executed_at, rows):
    out = ["---", "plan_id: %s" % plan_id, "run_at: %s" % run_at, "source_ref: %s" % ref,
           "executed_at:%s" % ((" " + executed_at) if executed_at else ""), "---", "",
           "# Test Results — %s" % plan_id, "",
           "| Task | Command | Exit | Result | Output tail |",
           "|------|---------|------|--------|-------------|"]
    for r in rows:
        code = r.get("test_exit_code")
        if code is None:
            exit_cell, verdict = "", "skip"
        else:
            exit_cell, verdict = str(code), ("pass" if code == 0 else "fail")
        out.append("| %s | %s | %s | %s | %s |" % (
            r["task_id"], _cell(r.get("test_command", "")), exit_cell, verdict,
            _cell(r.get("test_output_tail", ""))))
    return "\n".join(out) + "\n"


def finalize_plan(workdir, root="."):
    """Finalize one plan from its work dir; returns the summary dict plan-runner reports."""
    meta = _load_json(os.path.join(workdir, "meta.json"))
    plan_id = meta["plan_id"]
    task_ids = meta["task_ids"]
    plan_path = os.path.join(root, meta["plan_path"])

    results = {}
    for tid in task_ids:
        p = os.path.join(workdir, tid + ".result.json")
        if os.path.exists(p):
            results[tid] = _load_json(p)
    dispatched = [results[t] for t in task_ids if t in results]

    stopping_task, stopping_reason = "", ""
    for tid in task_ids:
        r = results.get(tid)
        if r is None:
            stopping_task, stopping_reason = tid, "not dispatched (run stopped before this task)"
        elif r["task_status"] != "done" or not r["tests_pass"]:
            stopping_task = tid
            stopping_reason = "task_status=%s tests_pass=%s" % (r["task_status"], r["tests_pass"])
        else:
            continue
        break
    done = stopping_task == ""

    with open(plan_path, encoding="utf-8") as f:
        text = f.read()
    fm = parse_frontmatter(text)
    updates = {}
    if done:
        files = list(fm.get("implemented_files") or [])
        for r in dispatched:
            for p in r.get("files_created", []) + r.get("files_modified", []):
                if p not in files:
                    files.append(p)
        fps = dict(fm.get("task_fingerprints") or {})
        for tid in task_ids:
            fps[tid] = task_fingerprint(_load_json(os.path.join(workdir, tid + ".fp.json")))
        executed_at = _now()
        updates = {"status": "done", "blocked_reason": "", "executed_at": executed_at,
                   "implemented_files": files, "task_fingerprints": fps}
    else:
        executed_at = fm.get("executed_at", "")
        blocked = [r for r in dispatched if r["task_status"] == "blocked"]
        updates = {"status": "in-progress"}
        if blocked:
            updates["blocked_reason"] = _quote("%s blocked: %s" % (
                blocked[0]["task_id"], "; ".join(blocked[0].get("manual_actions") or ["see task result"])))
    with open(plan_path, "w", encoding="utf-8", newline="") as f:
        f.write(_set_fields(text, updates))

    if meta.get("commit_mode") == "auto":
        _commit(root, plan_id)

    ref = source_ref(root, [meta["src_path"], meta["tests_path"]])
    results_dir = os.path.join(root, "docs", "implr", "plans", "test-results")
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, plan_id + "-results.md"), "w", encoding="utf-8", newline="") as f:
        f.write(_results_markdown(plan_id, _now(), ref, executed_at, dispatched))

    summary = {
        "plan_id": plan_id,
        "plan_status": "done" if done else "in-progress",
        "tasks_completed": sum(1 for r in dispatched if r["task_status"] == "done"),
        "tasks_blocked": sum(1 for r in dispatched if r["task_status"] == "blocked"),
        "manual_actions": [a for r in dispatched for a in r.get("manual_actions") or []],
        "files_created": len({p for r in dispatched for p in r.get("files_created", [])}),
        "files_modified": len({p for r in dispatched for p in r.get("files_modified", [])}),
        "tests_added": sum(r.get("tests_added", 0) for r in dispatched),
        "tests_pass": all(r["tests_pass"] for r in dispatched) and done,
        "stopping_task": stopping_task,
        "stopping_reason": stopping_reason,
    }
    if done:
        shutil.rmtree(workdir, ignore_errors=True)
    return summary
