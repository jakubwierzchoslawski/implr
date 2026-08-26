"""The packaging contract. These are the tests that make the path hacks unnecessary."""
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_implr_validate_imports_without_path_manipulation():
    """The whole point. If this fails, nothing else in the phase matters."""
    import implr_validate
    from implr_validate.contracts import load_contracts          # noqa: F401
    from implr_validate.checks import check_repo_prose            # noqa: F401

    assert implr_validate.__file__


def test_no_test_file_manipulates_sys_path():
    # This file is excluded: it holds the literal needle above, so it would
    # otherwise report itself and the check could never pass.
    this_file = Path(__file__).name
    offenders = [
        p.name for p in (REPO / "tests").glob("*.py")
        if p.name != this_file and "sys.path.insert" in p.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_the_console_script_is_declared():
    data = tomllib.loads(
        (REPO / "packages" / "implr_validate" / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["scripts"]["implr-validate"] == "implr_validate.cli:main"


def test_implr_validate_declares_no_dependencies():
    """A target project installs this. It must not drag FastAPI in with it."""
    data = tomllib.loads(
        (REPO / "packages" / "implr_validate" / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"].get("dependencies", []) == []


def test_module_invocation_works_from_any_directory(tmp_path):
    """`python -m implr_validate` from /tmp is what breaks under a path hack."""
    result = subprocess.run(
        [sys.executable, "-m", "implr_validate", "--repo", "--root", str(REPO)],
        cwd=tmp_path, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "implr-validate: OK" in result.stdout


def test_the_root_workspace_declares_every_package():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    members = data["tool"]["uv"]["workspace"]["members"]

    assert "packages/implr_validate" in members
    assert "packages/implr_studio" in members


def test_scripts_and_scaffold_are_gone():
    """Left in place they become a second, stale source of truth."""
    assert not (REPO / "scripts").exists()
    assert not (REPO / "scaffold").exists()
