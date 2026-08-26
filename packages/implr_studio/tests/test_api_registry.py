from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from implr_studio import context as ctx_mod
from implr_studio.api import create_app

# The single project in local mode. Routes are project-scoped from Phase 1 so
# there is one API shape; a hosted tenant simply has more than one project id.
PID = "local"


def _install_schemas(workspace: Path) -> None:
    from implr_studio import implr_bridge

    src = implr_bridge.repo_root() / "plugin" / "schemas"
    dst = workspace / "docs" / "implr" / "schemas"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.json"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")


def _install_skills(workspace: Path) -> None:
    """Availability resolves against the WORKSPACE's installed skills, so a
    realistic fixture installs them the way install.sh does."""
    from implr_studio import implr_bridge

    for skill_dir in (implr_bridge.repo_root() / "plugin" / "skills").iterdir():
        if not (skill_dir / "SKILL.md").is_file():
            continue
        target = workspace / ".claude" / "skills" / skill_dir.name
        target.mkdir(parents=True, exist_ok=True)
        (target / "SKILL.md").write_text(
            (skill_dir / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A target project with the real schemas AND skills installed."""
    _install_schemas(tmp_path)
    _install_skills(tmp_path)
    return tmp_path


@pytest.fixture
def client(workspace: Path):
    with TestClient(create_app(ctx_mod.build_context(workspace))) as c:
        yield c


def test_registry_lists_every_step_with_availability(client):
    body = client.get(f"/api/projects/{PID}/registry").json()

    steps = {s["id"]: s for s in body["steps"]}
    assert len(steps) == 9
    assert steps["doc-ingest"]["available"] is True
    assert steps["sec-review"]["available"] is False


def test_registry_exposes_phase_and_tier_vocabularies(client):
    body = client.get(f"/api/projects/{PID}/registry").json()

    assert body["phases"] == [
        "discovery", "design", "requirements", "planning", "build", "verify"]
    assert body["tiers"] == ["haiku", "sonnet", "opus"]


def test_registry_serves_value_taking_flags(client):
    """The configurator needs this in Phase 4; serving it now costs nothing."""
    steps = {s["id"]: s for s in client.get(f"/api/projects/{PID}/registry").json()["steps"]}

    task = next(a for a in steps["dev-executor"]["args_allowed"] if a["flag"] == "--task")
    assert task["takes_value"] is True
    assert task["value_pattern"]


def test_registry_serves_the_agent_dispatch_map(client):
    steps = {s["id"]: s for s in client.get(f"/api/projects/{PID}/registry").json()["steps"]}

    assert [a["name"] for a in steps["dev-executor"]["agents"]] == [
        "arch-excerpter", "plan-runner", "task-executor"]


def test_registry_serves_the_step_kind(client):
    steps = {s["id"]: s for s in client.get(f"/api/projects/{PID}/registry").json()["steps"]}

    assert steps["doc-ingest"]["kind"] == "skill"


def test_availability_is_resolved_against_the_workspace_skills(tmp_path):
    """Not the implr repo's plugin/skills tree.

    The adapter runs with cwd=<workspace>, so that is where the CLI resolves a
    slash command from. A palette that consulted the plugin source instead could
    call a step usable while the agent cannot find it.
    """
    _install_schemas(tmp_path)

    # An empty workspace skills tree: every step reads unavailable, even though
    # the implr repo itself has all eight installed.
    (tmp_path / ".claude" / "skills").mkdir(parents=True)

    with TestClient(create_app(ctx_mod.build_context(tmp_path))) as c:
        steps = {s["id"]: s for s in c.get(f"/api/projects/{PID}/registry").json()["steps"]}
    assert all(s["available"] is False for s in steps.values())

    # Install one, and only that one becomes available.
    d = tmp_path / ".claude" / "skills" / "doc-ingest"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: doc-ingest\n---\n", encoding="utf-8")

    with TestClient(create_app(ctx_mod.build_context(tmp_path))) as c:
        steps = {s["id"]: s for s in c.get(f"/api/projects/{PID}/registry").json()["steps"]}
    assert steps["doc-ingest"]["available"] is True
    assert steps["arch-gen"]["available"] is False


def test_projects_lists_exactly_one_in_local_mode(client, workspace):
    body = client.get("/api/projects").json()

    assert len(body["projects"]) == 1
    assert body["projects"][0]["id"] == PID
    assert body["projects"][0]["name"] == workspace.name


def test_me_reports_the_principal_and_its_permissions(client):
    body = client.get("/api/me").json()

    assert body["tenant_id"]
    assert "project.read" in body["permissions"]


def test_an_unknown_project_is_404_never_403(client):
    """A resource you cannot see does not exist; a 403 would confirm that it does."""
    assert client.get("/api/projects/not-a-project/registry").status_code == 404


def test_health_still_reports_the_workspace_name(client, workspace):
    assert client.get("/api/health").json()["workspace"] == workspace.name


def test_no_route_exposes_a_filesystem_path(client):
    blob = str(client.get("/openapi.json").json()).lower()

    for banned in ("workspace_path", "cwd", "directory", "file_path"):
        assert banned not in blob
