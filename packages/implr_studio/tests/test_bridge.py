import ast
from pathlib import Path

from implr_studio import implr_bridge


def test_repo_root_contains_the_implr_validate_package():
    root = implr_bridge.repo_root()
    assert (root / "packages" / "implr_validate" / "implr_validate" / "__init__.py").is_file()


def test_the_bridge_needs_no_path_manipulation():
    """Phase -1 made implr_validate an installed package. A path hack here would
    reintroduce exactly what that phase removed.

    Read as an AST rather than as text: the module's own docstring says it does
    no sys.path manipulation, and a substring check would match that sentence.
    """
    tree = ast.parse(Path(implr_bridge.__file__).read_text(encoding="utf-8"))

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert "sys" not in imported


def test_parse_frontmatter_is_the_implr_validate_parser():
    text = "---\nreq_id: REQ-F-001\nstatus: approved\n---\nbody\n"
    assert implr_bridge.parse_frontmatter(text) == {
        "req_id": "REQ-F-001",
        "status": "approved",
    }


def test_load_contracts_exposes_the_real_state_machines():
    schema_dir = implr_bridge.resolve_schema_dir(implr_bridge.repo_root())
    contracts = implr_bridge.load_contracts(str(schema_dir))
    assert contracts.states_for("requirement") == {
        "draft", "under-review", "approved", "rejected", "superseded",
    }


def test_resolve_schema_dir_prefers_the_plugin_payload(tmp_path: Path):
    (tmp_path / "plugin" / "schemas").mkdir(parents=True)
    (tmp_path / "docs" / "implr" / "schemas").mkdir(parents=True)
    assert implr_bridge.resolve_schema_dir(tmp_path) == tmp_path / "plugin" / "schemas"


def test_resolve_schema_dir_falls_back_to_installed_workspace(tmp_path: Path):
    (tmp_path / "docs" / "implr" / "schemas").mkdir(parents=True)
    assert implr_bridge.resolve_schema_dir(tmp_path) == tmp_path / "docs" / "implr" / "schemas"
