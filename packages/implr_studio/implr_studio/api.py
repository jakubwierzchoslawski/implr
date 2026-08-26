"""FastAPI routes.

Two rules hold from here to Phase 17.

Routes are **project-scoped** - `/api/projects/{pid}/...` - with local mode as the
degenerate one-tenant, one-user, one-project case. One API shape, not two.

**Every route calls authorize()**, even where the policy always says yes. Both
exist from the start because retrofitting either means auditing every handler.

Security: the workspace is fixed by server.main at startup. No route accepts or
returns a filesystem path, so no request can redirect the service elsewhere.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import serialize
from .authz import Forbidden, Permission, Principal, authorize, local_principal
from .context import AppContext, ProjectRef

VERSION = "0.1.0"

_NOT_BUILT = """<!doctype html>
<meta charset="utf-8">
<title>implr Studio</title>
<h1>implr Studio backend is running</h1>
<p>The API is live at <code>/api/health</code>, but the user interface has not been built.</p>
<h2>Development</h2>
<pre>cd web
npm install
npm run dev</pre>
<p>Then open the address Vite prints (it proxies <code>/api</code> here).</p>
<h2>Single-process use</h2>
<pre>cd web
npm install
npm run build</pre>
<p>Then restart <code>implr-studio</code> and reload this page.</p>
"""


def create_app(context: AppContext) -> FastAPI:
    app = FastAPI(title="implr Studio", version=VERSION)
    app.state.ctx = context

    # Set by mount_frontend. The index route consults it rather than letting the
    # static mount answer "/": an explicitly registered route always wins over a
    # later mount, so without this the built SPA is never served.
    app.state.dist_index = None

    @app.exception_handler(Forbidden)
    def _forbidden(request: Request, exc: Forbidden) -> JSONResponse:
        # A policy refusal is an answer, not a crash.
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    def current_principal() -> Principal:
        # Local mode has one implicit operator. Phase 17 reads a validated Entra
        # token here instead; no route signature changes.
        return local_principal()

    def resolve_project(pid: str, principal: Principal) -> ProjectRef:
        """The ONLY way a route obtains a project.

        Raises 404 - never 403 - for a project this principal may not read. A
        resource you cannot see does not exist, and a 403 would confirm it does.
        """
        project = context.projects.get(pid)
        if project is None or not context.policy.allows(
                principal, Permission.PROJECT_READ, project):
            raise HTTPException(status_code=404, detail="no such project")
        return project

    @app.get("/api/health")
    def health() -> dict:
        # The workspace NAME, never its path: the frontend shows it in the app
        # bar, and a path here would be the first step toward accepting one.
        #
        # This is the ONE route that is never authenticated - it is the container
        # liveness probe, and a probe that needs a token cannot report that the
        # token service is down. It therefore returns nothing tenant-specific.
        return {"status": "ok", "workspace": context.workspace.name, "version": VERSION}

    @app.get("/api/me")
    def me() -> dict:
        principal = current_principal()
        authorize(principal, Permission.PROJECT_READ, policy=context.policy)
        return {
            "id": principal.id,
            "tenant_id": principal.tenant_id,
            "display_name": principal.display_name,
            "mode": context.mode,
            "permissions": [
                p.value for p in Permission
                if context.policy.allows(principal, p, None)
            ],
        }

    @app.get("/api/projects")
    def list_projects() -> dict:
        # One entry in local mode; the UI hides the picker when there is one.
        # Filtered by the policy, so a hosted tenant sees only what it may read.
        principal = current_principal()
        authorize(principal, Permission.PROJECT_READ, policy=context.policy)
        return {"projects": [
            serialize.project_to_dict(p)
            for p in context.projects.values()
            if context.policy.allows(principal, Permission.PROJECT_READ, p)
        ]}

    @app.get("/api/projects/{pid}/registry")
    def get_registry(pid: str) -> dict:
        principal = current_principal()
        project = resolve_project(pid, principal)
        authorize(principal, Permission.PROJECT_READ, project=project, policy=context.policy)
        return serialize.registry_to_dict(context.registry)

    @app.get("/", include_in_schema=False)
    def index() -> Response:
        dist_index = app.state.dist_index
        if dist_index is not None:
            return FileResponse(dist_index)
        return HTMLResponse(_NOT_BUILT)

    return app


def mount_frontend(app: FastAPI, dist_dir) -> bool:
    """Serve the built SPA at / when it exists. Returns whether it was mounted.

    A missing dist/ is normal during development, when Vite serves the UI and
    proxies /api here - so it is reported, not raised. Called after every /api
    route is registered, because a route registered before a mount wins.
    """
    dist_dir = Path(dist_dir)
    index = dist_dir / "index.html"
    if not index.is_file():
        return False
    # The mount serves /assets/*; "/" itself is answered by the index route,
    # which this hands the built document to.
    app.state.dist_index = index
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
    return True
