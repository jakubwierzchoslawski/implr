"""The single point of coupling between implr Studio and implr_validate.

No other studio module may import from implr_validate directly. Keeping the
coupling in one file means a change to implr_validate's layout is a one-file fix.

There is deliberately no sys.path manipulation here. Phase -1 made implr_validate
an installed package and declared it as this package's dependency, so a plain
import is enough -- and a path hack would reintroduce precisely what that phase
removed.
"""
from pathlib import Path

# Re-exported so the rest of the studio package never imports implr_validate itself.
from implr_validate.contracts import load_contracts
from implr_validate.frontmatter import FrontmatterError, parse_frontmatter

__all__ = [
    "repo_root",
    "resolve_schema_dir",
    "load_contracts",
    "parse_frontmatter",
    "FrontmatterError",
]


def repo_root() -> Path:
    """The implr repository root.

    implr_bridge.py lives at
    <root>/packages/implr_studio/implr_studio/implr_bridge.py, so the root is
    three parents up from its directory.
    """
    return Path(__file__).resolve().parents[3]


def resolve_schema_dir(root: Path) -> Path:
    """Mirror implr_validate.cli._resolve_schema_dir.

    A plugin-source checkout has plugin/schemas; an installed workspace has
    docs/implr/schemas.
    """
    candidate = Path(root) / "plugin" / "schemas"
    if candidate.is_dir():
        return candidate
    return Path(root) / "docs" / "implr" / "schemas"
