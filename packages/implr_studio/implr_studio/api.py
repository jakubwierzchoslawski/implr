"""FastAPI routes.

Security: the workspace is fixed by server.main at startup. No route accepts or
returns a filesystem path, so no request can redirect the service elsewhere.
Phase 0 has one real route; later phases add to create_app.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

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


def create_app(workspace_name: str) -> FastAPI:
    app = FastAPI(title="implr Studio", version=VERSION)

    @app.get("/api/health")
    def health() -> dict:
        # The workspace NAME, never its path: the frontend shows it in the app
        # bar, and a path here would be the first step toward accepting one.
        #
        # This is the ONE route that is never authenticated - it is the container
        # liveness probe, and a probe that needs a token cannot report that the
        # token service is down. It therefore returns nothing tenant-specific.
        return {"status": "ok", "workspace": workspace_name, "version": VERSION}

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return _NOT_BUILT

    return app


def mount_frontend(app: FastAPI, dist_dir) -> bool:
    """Serve the built SPA at / when it exists. Returns whether it was mounted.

    A missing dist/ is normal during development, when Vite serves the UI and
    proxies /api here - so it is reported, not raised. Called after every /api
    route is registered, because a route registered before a mount wins.
    """
    dist_dir = Path(dist_dir)
    if not (dist_dir / "index.html").is_file():
        return False
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
    return True
