"""The authorization seam.

The roadmap requires this from Phase 1: every route calls authorize(), even in
local mode where the policy always says yes. Naming the permission verbs later
would mean revisiting every call site to decide which verb it meant -- which is
exactly the audit this seam exists to prevent.
"""
import inspect
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from implr_studio import authz, context as ctx_mod
from implr_studio.api import create_app

# /api/health is the container liveness probe. A probe that needs a token cannot
# report that the token service is down, so it is deliberately unauthenticated
# and returns nothing tenant-specific.
UNAUTHENTICATED = {"/api/health"}


@pytest.fixture
def app(tmp_path: Path):
    from implr_studio import implr_bridge

    src = implr_bridge.repo_root() / "plugin" / "schemas"
    dst = tmp_path / "docs" / "implr" / "schemas"
    dst.mkdir(parents=True)
    for f in src.glob("*.json"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    return create_app(ctx_mod.build_context(tmp_path))


def test_every_api_route_calls_authorize(app):
    """Walks the route table. Kept green from Phase 1 onward."""
    offenders = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        if route.path in UNAUTHENTICATED:
            continue
        if "authorize" not in inspect.getsource(route.endpoint):
            offenders.append(route.path)

    assert offenders == [], "these /api routes never call authorize(): %s" % offenders


def test_every_permission_verb_is_named_from_the_start():
    """Phase 17 swaps the policy; it must not have to invent verbs."""
    verbs = {p.value for p in authz.Permission}

    assert verbs == {
        "project.read", "project.write", "run.start", "run.control",
        "step.author", "skill.author", "tenant.admin",
    }


def test_local_policy_allows_everything():
    principal = authz.local_principal()

    for permission in authz.Permission:
        assert authz.LocalPolicy().allows(principal, permission, None) is True


def test_authorize_raises_forbidden_when_the_policy_refuses():
    class DenyAll:
        def allows(self, principal, permission, project=None):
            return False

    with pytest.raises(authz.Forbidden):
        authz.authorize(authz.local_principal(), authz.Permission.PROJECT_READ,
                        policy=DenyAll())


def test_forbidden_becomes_403_not_500(app):
    """A policy refusal is an answer, not a crash."""

    @app.get("/api/_probe_forbidden")
    def probe():
        raise authz.Forbidden("nope")

    with TestClient(app) as client:
        assert client.get("/api/_probe_forbidden").status_code == 403
