"""CLI entry point.

Binds 127.0.0.1 only. There is deliberately no flag to change that: later phases
run an agent that writes files and executes shell commands in the target
repository, and this service must never be reachable by anyone but the local
operator. Hosted mode is a separate image with its own entry point.
"""
import argparse
import sys
from pathlib import Path

import uvicorn

from .api import create_app, mount_frontend
from .context import build_context
from .implr_bridge import repo_root

LOOPBACK = "127.0.0.1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="implr-studio")
    parser.add_argument("--workspace", default=".", help="target project directory")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve()
    if not (workspace / "docs" / "implr").is_dir():
        sys.stderr.write(
            "error: %s is not an implr workspace (no docs/implr). Run the installer first.\n"
            % workspace
        )
        return 2

    try:
        context = build_context(workspace)
    except Exception as e:
        sys.stderr.write("error: could not load the step registry: %s\n" % e)
        sys.stderr.write(
            "hint: re-run the implr installer so docs/implr/schemas is current.\n")
        return 2

    app = create_app(context)

    dist = repo_root() / "web" / "dist"
    served = mount_frontend(app, dist)

    sys.stderr.write("implr Studio on http://%s:%d (workspace: %s)\n"
                     % (LOOPBACK, args.port, workspace))
    sys.stderr.write("  ui: %s\n" % ("built bundle" if served else "not built - see the page at /"))
    uvicorn.run(app, host=LOOPBACK, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
