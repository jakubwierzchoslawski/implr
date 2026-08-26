from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from implr_studio import api as api_mod
from implr_studio.api import create_app


@pytest.fixture
def client():
    with TestClient(create_app(workspace_name="acme-platform")) as c:
        yield c


def test_health_reports_ok_and_the_workspace_name(client):
    body = client.get("/api/health").json()

    assert body["status"] == "ok"
    assert body["workspace"] == "acme-platform"
    assert body["version"]


def test_root_explains_itself_when_the_ui_is_not_built(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.text.lower()
    assert "npm run dev" in body or "npm run build" in body


def test_root_serves_the_spa_when_built(tmp_path):
    # A marker that cannot appear in the not-built page. Asserting on "studio"
    # passes against that page too, because it says `restart implr-studio`.
    marker = "__SPA_MARKER__"
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>%s</body></html>" % marker, encoding="utf-8")
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

    app = create_app(workspace_name="ws")
    assert api_mod.mount_frontend(app, dist) is True

    with TestClient(app) as client:
        body = client.get("/").text
        assert marker in body
        assert "npm run build" not in body, "the not-built page is shadowing the SPA"
        assert client.get("/assets/app.js").status_code == 200


def test_mount_returns_false_for_a_missing_dist(tmp_path):
    assert api_mod.mount_frontend(create_app(workspace_name="ws"), tmp_path / "nope") is False


def test_api_routes_still_win_over_the_spa_mount(tmp_path):
    """A catch-all mount at / must not shadow /api."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")

    app = create_app(workspace_name="ws")
    api_mod.mount_frontend(app, dist)

    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"


def test_no_route_exposes_a_filesystem_path():
    """Security constraint: the workspace is fixed at startup."""
    with TestClient(create_app(workspace_name="ws")) as client:
        blob = str(client.get("/openapi.json").json()).lower()

    for banned in ("workspace_path", "cwd", "directory", "file_path"):
        assert banned not in blob, "an API parameter exposes a filesystem path: %s" % banned


def test_server_binds_localhost_only():
    """No configuration may expose this service."""
    from implr_studio import server

    source = Path(server.__file__).read_text(encoding="utf-8")
    assert "127.0.0.1" in source
    assert "0.0.0.0" not in source
    assert "--host" not in source, "the host must not be configurable"


def test_console_script_is_registered():
    """`implr-studio` is quoted throughout the phases; it must actually exist."""
    import tomllib

    from implr_studio import implr_bridge

    pyproject = implr_bridge.repo_root() / "packages" / "implr_studio" / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert data["project"]["scripts"]["implr-studio"] == "implr_studio.server:main"


def test_server_refuses_a_directory_that_is_not_an_implr_workspace(tmp_path, capsys):
    from implr_studio import server

    code = server.main(["--workspace", str(tmp_path)])

    assert code == 2
    assert "not an implr workspace" in capsys.readouterr().err
