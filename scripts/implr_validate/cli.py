# scripts/implr_validate/cli.py
import argparse
import json
import os
import sys

from .contracts import load_contracts
from .checks import check_workspace, check_repo_prose
from .fingerprint import contradiction_fingerprint


def _resolve_schema_dir(root, override):
    if override:
        return override
    candidate = os.path.join(root, "scaffold", "schemas")
    if os.path.isdir(candidate):
        return candidate
    return os.path.join(root, "docs", "implr", "schemas")


def main(argv):
    parser = argparse.ArgumentParser(prog="implr_validate", add_help=True)
    parser.add_argument("--repo", action="store_true", help="validate the plugin source tree")
    parser.add_argument("--workspace", nargs="?", const=".", default=None,
                        help="validate an installed docs/implr workspace at PATH (default cwd)")
    parser.add_argument("--fingerprint", metavar="FILE", help="print fingerprint of a JSON fields file")
    parser.add_argument("--root", default=".", help="repo root for --repo (default cwd)")
    parser.add_argument("--schema-dir", default=None, help="override contract directory")
    args = parser.parse_args(argv)

    if not (args.repo or args.workspace is not None or args.fingerprint):
        sys.stderr.write("error: one of --repo, --workspace, --fingerprint is required\n")
        return 2

    if args.fingerprint:
        schema_dir = _resolve_schema_dir(args.root, args.schema_dir)
        _ = load_contracts(schema_dir)  # ensures contracts are loadable/consistent
        with open(args.fingerprint, encoding="utf-8") as f:
            fields = json.load(f)
        sys.stdout.write(contradiction_fingerprint(fields) + "\n")
        return 0

    findings = []
    if args.repo:
        schema_dir = _resolve_schema_dir(args.root, args.schema_dir)
        contracts = load_contracts(schema_dir)
        findings.extend(check_repo_prose(args.root, contracts))
    if args.workspace is not None:
        ws = args.workspace
        schema_dir = _resolve_schema_dir(ws, args.schema_dir)
        contracts = load_contracts(schema_dir)
        findings.extend(check_workspace(ws, contracts))

    if findings:
        for fnd in findings:
            sys.stderr.write("%s: %s: %s\n" % (fnd.level, fnd.path, fnd.message))
        sys.stderr.write("\n%d finding(s)\n" % len(findings))
        return 1
    sys.stdout.write("implr-validate: OK\n")
    return 0
