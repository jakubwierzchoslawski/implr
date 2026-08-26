# packages/implr_validate/implr_validate/cli.py
import argparse
import json
import os
import sys

from .contracts import load_contracts
from .checks import check_workspace, check_repo_prose, check_step_registry
from .fingerprint import contradiction_fingerprint, task_fingerprint
from .sourceref import source_ref


def _resolve_schema_dir(root, override):
    if override:
        return override
    # A plugin-source checkout has plugin/schemas; an installed workspace has
    # docs/implr/schemas.
    candidate = os.path.join(root, "plugin", "schemas")
    if os.path.isdir(candidate):
        return candidate
    return os.path.join(root, "docs", "implr", "schemas")


def main(argv=None):
    # argv defaults to None so the `implr-validate` console script, which calls
    # main() with no arguments, works. argparse reads sys.argv[1:] for None.
    parser = argparse.ArgumentParser(prog="implr-validate", add_help=True)
    parser.add_argument("--repo", action="store_true", help="validate the plugin source tree")
    parser.add_argument("--workspace", nargs="?", const=".", default=None,
                        help="validate an installed docs/implr workspace at PATH (default cwd)")
    parser.add_argument("--fingerprint", metavar="FILE", help="print fingerprint of a JSON fields file")
    parser.add_argument("--task-fingerprint", metavar="FILE", help="print task fingerprint of a JSON fields file")
    parser.add_argument("--source-ref", nargs="+", metavar="PATH", help="print the source ref for the given paths")
    parser.add_argument("--root", default=".", help="repo root for --repo (default cwd)")
    parser.add_argument("--schema-dir", default=None, help="override contract directory")
    args = parser.parse_args(argv)

    if not (args.repo or args.workspace is not None or args.fingerprint or args.task_fingerprint or args.source_ref):
        sys.stderr.write("error: one of --repo, --workspace, --fingerprint is required\n")
        return 2

    if args.fingerprint:
        schema_dir = _resolve_schema_dir(args.root, args.schema_dir)
        _ = load_contracts(schema_dir)  # ensures contracts are loadable/consistent
        with open(args.fingerprint, encoding="utf-8") as f:
            fields = json.load(f)
        sys.stdout.write(contradiction_fingerprint(fields) + "\n")
        return 0

    if args.task_fingerprint:
        with open(args.task_fingerprint, encoding="utf-8") as f:
            fields = json.load(f)
        sys.stdout.write(task_fingerprint(fields) + "\n")
        return 0

    if args.source_ref:
        sys.stdout.write(source_ref(args.root, args.source_ref) + "\n")
        return 0

    findings = []
    if args.repo:
        schema_dir = _resolve_schema_dir(args.root, args.schema_dir)
        contracts = load_contracts(schema_dir)
        findings.extend(check_repo_prose(args.root, contracts))
        findings.extend(check_step_registry(args.root, contracts))
    if args.workspace is not None:
        ws = args.workspace
        schema_dir = _resolve_schema_dir(ws, args.schema_dir)
        contracts = load_contracts(schema_dir)
        findings.extend(check_workspace(ws, contracts))

    if findings:
        for fnd in findings:
            sys.stderr.write("%s: %s: %s\n" % (fnd.level, fnd.path, fnd.message))
        # Level-aware from Phase 1: an "info" finding prints without failing, so
        # declaring a step before its skill exists does not break the build.
        # Every finding that predates this change is level "error", so nothing
        # that used to fail starts passing.
        errors = [f for f in findings if f.level == "error"]
        sys.stderr.write("\n%d finding(s), %d error(s)\n" % (len(findings), len(errors)))
        if errors:
            return 1
    sys.stdout.write("implr-validate: OK\n")
    return 0
