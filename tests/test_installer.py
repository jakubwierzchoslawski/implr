from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALLERS = ["install.sh", "install.ps1", "install.bat"]


def test_no_installer_copies_python_files():
    """Vendoring a package by shell script gives every project a divergent copy."""
    for name in INSTALLERS:
        text = (REPO / name).read_text(encoding="utf-8")
        assert "implr_validate" not in text or "pip install" in text, name


def test_every_installer_installs_the_package():
    for name in INSTALLERS:
        assert "implr-validate" in (REPO / name).read_text(encoding="utf-8"), name


def test_every_installer_reads_from_plugin():
    for name in INSTALLERS:
        text = (REPO / name).read_text(encoding="utf-8")
        assert "plugin" in text, name
        assert "scaffold" not in text, name


def test_the_installers_agree_on_the_skill_list():
    """Three files hand-synced is three chances to diverge. Assert they have not."""
    import re

    lists = []
    for name in INSTALLERS:
        text = (REPO / name).read_text(encoding="utf-8")
        lists.append(set(re.findall(r"\b(implr-init|doc-ingest|arch-gen|ba-requirements-gen"
                                    r"|ba-cr|dev-planner|dev-executor|dev-code-review)\b", text)))

    assert lists[0] == lists[1] == lists[2]
    assert len(lists[0]) == 8


def test_bootstrapping_implr_itself_installs_editable():
    """A plain install into this repo shadows the source tree with a snapshot copy,
    so a contributor's edits to packages/implr_validate stop taking effect."""
    for name in ("install.sh", "install.ps1"):
        assert "--editable" in (REPO / name).read_text(encoding="utf-8"), name


def test_the_bootstrap_step_is_documented():
    """A fresh clone cannot run an implr skill until .claude/agents exists."""
    assert "install.sh" in (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
