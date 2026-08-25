# implr Studio — Phase 0: Skeleton

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `implr-studio` starts, binds loopback, and serves a dark application shell in the browser with a live health indicator. Nothing else works yet — and that is the point.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Hosted:** `../specs/2026-08-25-implr-studio-hosted-design.md` · **Runtime:** `../../RUNTIME.md`

> **Two rules that hold from here to Phase 17.** Routes are **project-scoped** —
> `/api/projects/{pid}/…`, with local mode as the degenerate one-tenant, one-user,
> one-project case. And **every route calls `authorize()`**, even where the policy always
> says yes. Both exist from the start because retrofitting either means auditing every
> handler. See *Two things that cut across every phase* in the roadmap.

---

**Depends on:** Phase −1 (the restructure). Paths below assume `packages/implr_studio`
and `web/`; if you are running Phase 0 before the restructure, they are
`studio/backend/implr_studio` and `studio/frontend`.

---

## Demo

```bash
cd studio/backend && implr-studio --workspace /tmp/studio-probe
cd studio/frontend && npm run dev        # second terminal
```

Open the address Vite prints. You should see: a dark app bar reading **implr Studio**, the
workspace name, and a **green health dot** that turns red if you stop the backend. Three
empty panes in a `246px / 1fr / 316px` grid.

That is the whole demo. It proves the two processes talk to each other over the `/api`
proxy, the design system loads, and the shell is the right shape — which is everything the
next thirteen phases build on.

---

## Scope boundary — not in this phase

No registry, no pipeline, no canvas, no configurator, no runs, no executor. `GET /api/health`
is the only route besides the root page. The panes are empty divs with borders.

The backend must **start without `step-registry.json`**, because Phase 1 is what ships it.
No `AppContext`, no `Store`, no `Orchestrator` — those arrive when something needs them.

---

## Tech Stack

Python 3.11+, FastAPI, Uvicorn, pytest. Vite 5+, React 18+, TypeScript, Vitest + jsdom.
`@xyflow/react` is installed now (Phase 2 needs it, and installing once avoids a second
`npm install` churn) but nothing imports it yet except the smoke test.

## Global Constraints

- The server binds `127.0.0.1` **only**. There is no `--host` flag, now or ever.
- `scripts/implr_validate` stays **standard library only**.
- Dark is the default in every theme state. No `prefers-color-scheme` query.
- Colour is data: every saturated hue belongs to a reserved token group. No component
  stylesheet may introduce one. Task 4 ships the test that enforces this.
- No frontend file contains a host or a port. The dev proxy handles it.

---

## File Structure

| File | Responsibility |
|---|---|
| `.gitignore` | **Modified** — ignore the artefacts these phases create. |
| `scaffold/schemas/frontmatter-rules.json` | **Modified** — exempt `node_modules/` from prose checks. |
| `studio/backend/pyproject.toml` | Package metadata, deps, the `implr-studio` console script. |
| `studio/backend/implr_studio/__init__.py` | Package marker. |
| `studio/backend/implr_studio/implr_bridge.py` | The **only** module that knows where `scripts/implr_validate` lives. |
| `studio/backend/implr_studio/api.py` | `create_app` — health route, root page, `mount_frontend`. |
| `studio/backend/implr_studio/server.py` | `main()` — argument parsing, loopback bind. |
| `studio/frontend/src/tokens.css` | **The design system.** |
| `studio/frontend/src/app.css` | Component styles, tokens only. |
| `studio/frontend/src/App.tsx` | The shell: app bar, health dot, three panes. |
| `studio/frontend/src/health.ts` | Pure health polling logic. No React. |

---

### Task 1: Ignore the build artefacts these phases create

**Files:**
- Modify: `.gitignore`
- Modify: `scaffold/schemas/frontmatter-rules.json`

Do this first. Task 5 runs `npm install`, and Task 6 runs `git add studio/frontend`. Without
this task that commits `node_modules`.

- [ ] **Step 1: Extend `.gitignore`**

Append:

```gitignore
# python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
# node
node_modules/
studio/frontend/dist/
# studio run state (per-workspace, never committed)
docs/implr/.studio/
```

- [ ] **Step 2: Exempt node_modules from the prose checks**

`check_repo_prose` walks every `.md`, `.yaml` and `.yml` under the repo root looking for
`kb_supported_formats` drift. After `npm install` that means crawling tens of thousands of
files on every `implr-validate --repo`. Add two entries to
`repo_prose_checks.exempt_paths` in `scaffold/schemas/frontmatter-rules.json`, alongside the
existing `"docs/superpowers/"`:

```text
    "studio/frontend/node_modules/",
    "studio/frontend/dist/",
```

- [ ] **Step 3: Verify and commit**

```bash
git status --porcelain | grep -E "__pycache__|node_modules|\.egg-info" && echo FAIL || echo OK
PYTHONPATH=scripts python -m implr_validate --repo --root .
git add .gitignore scaffold/schemas/frontmatter-rules.json
git commit -m "chore(studio): ignore build artefacts introduced by implr Studio"
```

Expected: `OK`, then `implr-validate: OK`.

---

### Task 2: Backend package and the implr_validate bridge

**Files:**
- Create: `studio/backend/pyproject.toml`
- Create: `studio/backend/implr_studio/__init__.py`
- Create: `studio/backend/implr_studio/implr_bridge.py`
- Test: `studio/backend/tests/test_bridge.py`

**Interfaces:**
- Produces:
  - `implr_bridge.repo_root() -> Path` — the implr repo root.
  - `implr_bridge.resolve_schema_dir(root: Path) -> Path` — prefers `<root>/scaffold/schemas`, falls back to `<root>/docs/implr/schemas`.
  - `implr_bridge.parse_frontmatter(text) -> dict`, `implr_bridge.load_contracts(schema_dir) -> Contracts`, `implr_bridge.FrontmatterError` — re-exported.

The bridge exists so that exactly one file knows `implr_validate`'s location. Later phases
import frontmatter parsing and the state machines through it and never reach past it.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_bridge.py`:

```python
from pathlib import Path

from implr_studio import implr_bridge


def test_repo_root_contains_scripts_implr_validate():
    root = implr_bridge.repo_root()
    assert (root / "scripts" / "implr_validate" / "__init__.py").is_file()


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


def test_resolve_schema_dir_prefers_scaffold(tmp_path: Path):
    (tmp_path / "scaffold" / "schemas").mkdir(parents=True)
    (tmp_path / "docs" / "implr" / "schemas").mkdir(parents=True)
    assert implr_bridge.resolve_schema_dir(tmp_path) == tmp_path / "scaffold" / "schemas"


def test_resolve_schema_dir_falls_back_to_installed_workspace(tmp_path: Path):
    (tmp_path / "docs" / "implr" / "schemas").mkdir(parents=True)
    assert implr_bridge.resolve_schema_dir(tmp_path) == tmp_path / "docs" / "implr" / "schemas"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio'`

- [ ] **Step 3: Write the package**

Create `studio/backend/pyproject.toml`:

```toml
[project]
name = "implr-studio"
version = "0.1.0"
description = "Visual SDLC pipeline builder and orchestrator for implr"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[project.scripts]
implr-studio = "implr_studio.server:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["implr_studio*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

`asyncio_mode` and `pytest-asyncio` are set now even though nothing is async until Phase 9 —
configuring them once avoids a confusing "async test skipped silently" failure later.

Create `studio/backend/implr_studio/__init__.py` (empty).

Create `studio/backend/implr_studio/implr_bridge.py`:

```python
"""The single point of coupling between implr Studio and scripts/implr_validate.

No other studio module may import from implr_validate directly. Keeping the
coupling in one file means a change to implr_validate's layout is a one-file fix.
"""
import sys
from pathlib import Path


def repo_root() -> Path:
    """The implr repository root.

    implr_bridge.py lives at <root>/studio/backend/implr_studio/implr_bridge.py,
    so the root is three parents up from its directory.
    """
    return Path(__file__).resolve().parents[3]


def _ensure_scripts_on_path() -> None:
    scripts = str(repo_root() / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


_ensure_scripts_on_path()

# Re-exported so the rest of the studio package never imports implr_validate itself.
from implr_validate.contracts import load_contracts          # noqa: E402
from implr_validate.frontmatter import (                     # noqa: E402
    FrontmatterError,
    parse_frontmatter,
)

__all__ = [
    "repo_root",
    "resolve_schema_dir",
    "load_contracts",
    "parse_frontmatter",
    "FrontmatterError",
]


def resolve_schema_dir(root: Path) -> Path:
    """Mirror implr_validate.cli._resolve_schema_dir.

    A plugin-source checkout has scaffold/schemas; an installed workspace has
    docs/implr/schemas.
    """
    candidate = Path(root) / "scaffold" / "schemas"
    if candidate.is_dir():
        return candidate
    return Path(root) / "docs" / "implr" / "schemas"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pip install -e ".[dev]" && python -m pytest tests/test_bridge.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/pyproject.toml studio/backend/implr_studio studio/backend/tests
git commit -m "feat(studio): backend package and implr_validate bridge"
```

---

### Task 3: Health route, root page, and the loopback server

**Files:**
- Create: `studio/backend/implr_studio/api.py`
- Create: `studio/backend/implr_studio/server.py`
- Test: `studio/backend/tests/test_api_health.py`

**Interfaces:**
- Produces:
  - `api.create_app() -> FastAPI` — takes no context yet; Phase 1 introduces one.
  - `GET /api/health` → `{"status": "ok", "workspace": "<name>", "version": "0.1.0"}`
  - `GET /` → the SPA when built, otherwise a plain-text page explaining how to build it. **Never** a 404.
  - `api.mount_frontend(app, dist_dir) -> bool` — mounts the built bundle at `/`, returning whether it did.
  - `server.main(argv=None) -> int` — parses `--workspace` (default `.`) and `--port` (default 8765), binds `127.0.0.1`.

`create_app` takes the workspace **name** only, not a path, and no route returns a path.
The workspace is fixed at startup; no request may redirect the service at another directory.
That constraint starts here and holds for every later phase.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_api_health.py`:

```python
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
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>studio</body></html>", encoding="utf-8")
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

    app = create_app(workspace_name="ws")
    assert api_mod.mount_frontend(app, dist) is True

    with TestClient(app) as client:
        assert "studio" in client.get("/").text
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

    pyproject = implr_bridge.repo_root() / "studio" / "backend" / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert data["project"]["scripts"]["implr-studio"] == "implr_studio.server:main"


def test_server_refuses_a_directory_that_is_not_an_implr_workspace(tmp_path, capsys):
    from implr_studio import server

    code = server.main(["--workspace", str(tmp_path)])

    assert code == 2
    assert "not an implr workspace" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_api_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio.api'`

- [ ] **Step 3: Write `api.py`**

```python
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
<pre>cd studio/frontend
npm install
npm run dev</pre>
<p>Then open the address Vite prints (it proxies <code>/api</code> here).</p>
<h2>Single-process use</h2>
<pre>cd studio/frontend
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
```

- [ ] **Step 4: Write `server.py`**

```python
"""CLI entry point.

Binds 127.0.0.1 only. There is deliberately no --host flag: later phases run an
agent that writes files and executes shell commands in the target repository, and
this service must never be reachable by anyone but the local operator.
"""
import argparse
import sys
from pathlib import Path

import uvicorn

from .api import create_app, mount_frontend

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

    app = create_app(workspace_name=workspace.name)

    dist = Path(__file__).resolve().parents[3] / "studio" / "frontend" / "dist"
    served = mount_frontend(app, dist)

    sys.stderr.write("implr Studio on http://%s:%d (workspace: %s)\n"
                     % (LOOPBACK, args.port, workspace))
    sys.stderr.write("  ui: %s\n" % ("built bundle" if served else "not built - see the page at /"))
    uvicorn.run(app, host=LOOPBACK, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`main` resolves the workspace and passes only its **name** into `create_app`. From Phase 1
the path goes into an `AppContext` instead — still never into a route signature.

- [ ] **Step 5: Run tests and commit**

Run: `cd studio/backend && python -m pip install -e ".[dev]" && python -m pytest -v`
Expected: all bridge and health tests pass.

```bash
git add studio/backend
git commit -m "feat(studio): health route, self-explaining root page, loopback server"
```

---

### Task 4: The design system

**Files:**
- Create: `studio/frontend/src/tokens.css`
- Create: `studio/frontend/src/app.css`
- Test: `studio/frontend/src/tokens.test.ts`

This ships before any component, so no component can be written against an invented colour.

**Interfaces:**
- Produces: `tokens.css` as the single source of every colour, face, radius and shadow;
  `app.css` as component styles built only from those tokens.

- [ ] **Step 1: Write the failing test**

Create `studio/frontend/src/tokens.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const read = (f: string) => readFileSync(join(__dirname, f), 'utf8');

/** Any hex colour with real saturation. Greys are allowed anywhere. */
function saturatedHexes(css: string): string[] {
  const found: string[] = [];
  for (const match of css.matchAll(/#([0-9a-fA-F]{6})\b/g)) {
    const hex = match[1];
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    if (Math.max(r, g, b) - Math.min(r, g, b) > 24) found.push('#' + hex);
  }
  return found;
}

describe('tokens.css is the only source of colour', () => {
  it('defines the reserved semantic groups', () => {
    const css = read('tokens.css');

    for (const state of [
      'running', 'succeeded', 'failed', 'blocked',
      'input', 'approval', 'skipped', 'pending',
    ]) {
      expect(css).toContain(`--st-${state}:`);
    }
    for (const tier of ['haiku', 'sonnet', 'opus']) {
      expect(css).toContain(`--tier-${tier}:`);
    }
    expect(css).toContain('--gate:');
    expect(css).toContain('--bone:');
    expect(css).toContain('--cyan:');
  });

  it('is dark by default with no prefers-color-scheme query', () => {
    const css = read('tokens.css');

    // Dark is the commitment: a light OS must not flip the console.
    expect(css).not.toContain('prefers-color-scheme');
    expect(css).toContain('[data-theme="light"]');
  });

  it('paints the body background from a token', () => {
    // A transparent body silently borrows the host page's ground.
    expect(read('tokens.css')).toMatch(/body\s*\{[^}]*background:\s*var\(--ground\)/);
  });

  it('component styles introduce no saturated colour of their own', () => {
    // THE design rule. Every hue in the app is a reserved token, so a brand
    // colour can never compete with the run-state palette the operator reads.
    expect(saturatedHexes(read('app.css'))).toEqual([]);
  });

  it('every font-family declares a fallback stack', () => {
    const css = read('tokens.css');
    const families = [...css.matchAll(/--(?:sans|display|mono):([^;]+);/g)].map((m) => m[1]);

    expect(families.length).toBeGreaterThanOrEqual(3);
    for (const stack of families) {
      expect(stack.split(',').length).toBeGreaterThan(1);
    }
  });

  it('respects prefers-reduced-motion', () => {
    expect(read('tokens.css')).toContain('prefers-reduced-motion');
  });
});
```

- [ ] **Step 2: Write `tokens.css`**

The full token set. Later phases consume these and add none:

```css
/* ============================================================
   implr Studio design system.

   Dark is the commitment: :root carries the complete dark palette
   and there is deliberately NO prefers-color-scheme query, so a
   viewer on a light OS still gets the console. Light appears only
   under an explicit data-theme="light".

   Colour is data. The accent is achromatic (bone) with one cyan
   for focus and selection. Every saturated hue belongs to a
   reserved group: --st-* is run state, --tier-* is model tier,
   --gate is an edge condition. No component may add another.
   ============================================================ */
:root {
  --ground:      #0b0e14;
  --surface:     #131822;
  --raised:      #1a2130;
  --raised-2:    #212a3b;
  --sunk:        #0e131b;
  --hair:        #232b3a;
  --hair-soft:   #1b222e;

  --text:        #e8ecf3;
  --text-soft:   #9aa5b8;
  --text-faint:  #656f80;

  --bone:        #eceae4;
  --bone-ink:    #0b0e14;
  --cyan:        #3ed8c9;
  --cyan-sunk:   #10322f;

  --st-running:   #e8a33d;
  --st-succeeded: #43c08a;
  --st-failed:    #f2685c;
  --st-blocked:   #7a8494;
  --st-input:     #a78bfa;
  --st-approval:  #56b6e8;
  --st-skipped:   #5a6270;
  --st-pending:   #3b4453;

  --gate:        #d9b25c;
  --gate-sunk:   #2c2413;
  --edge:        #333d4e;

  --tier-haiku:  #56b6e8;
  --tier-sonnet: #43c08a;
  --tier-opus:   #e8a33d;

  --r-sm: 6px;
  --r-md: 10px;
  --r-lg: 14px;
  --r-xl: 20px;

  --shadow-1: 0 1px 2px rgb(0 0 0 / .5);
  --shadow-2: 0 4px 12px -2px rgb(0 0 0 / .55);
  --shadow-3: 0 24px 60px -12px rgb(0 0 0 / .8), 0 2px 8px rgb(0 0 0 / .5);

  --sans:    "Manrope", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --display: "Sora", "Manrope", ui-sans-serif, system-ui, sans-serif;
  --mono:    "JetBrains Mono", ui-monospace, "SF Mono", "Cascadia Mono", Menlo, monospace;

  --t: 160ms cubic-bezier(.2, .7, .3, 1);
}

:root[data-theme="light"] {
  --ground:      #f4f5f8;
  --surface:     #ffffff;
  --raised:      #ffffff;
  --raised-2:    #f0f2f6;
  --sunk:        #eaecf1;
  --hair:        #dde1e9;
  --hair-soft:   #e8ebf1;

  --text:        #141a24;
  --text-soft:   #545e6f;
  --text-faint:  #7f8898;

  --bone:        #141a24;
  --bone-ink:    #ffffff;
  --cyan:        #0f8b80;
  --cyan-sunk:   #dff3f1;

  --st-running:   #b4740f;
  --st-succeeded: #1d8055;
  --st-failed:    #c8382c;
  --st-blocked:   #6b7383;
  --st-input:     #6d4bd0;
  --st-approval:  #1a7fb5;
  --st-skipped:   #949bab;
  --st-pending:   #c8cdd7;

  --gate:        #8a6a12;
  --gate-sunk:   #faf0d3;
  --edge:        #bcc3ce;

  --tier-haiku:  #1a7fb5;
  --tier-sonnet: #1d8055;
  --tier-opus:   #b4740f;

  --shadow-1: 0 1px 2px rgb(20 26 36 / .06);
  --shadow-2: 0 4px 12px -2px rgb(20 26 36 / .1);
  --shadow-3: 0 24px 60px -12px rgb(20 26 36 / .22), 0 2px 8px rgb(20 26 36 / .08);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  /* Explicit, from a token: a transparent body borrows the host's ground. */
  background: var(--ground);
  color: var(--text);
  font-family: var(--sans);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

button, input, select, textarea { font-family: inherit; color: inherit; }

:focus-visible { outline: 2px solid var(--cyan); outline-offset: 2px; border-radius: 4px; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition: none !important; animation: none !important; }
}
```

- [ ] **Step 3: Write `app.css`**

Phase 0 only needs the shell. Every value is a token:

```css
/* Component styles. Colours come from tokens.css only -
   src/tokens.test.ts fails the build if a saturated hex appears here. */
.layout {
  display: grid;
  grid-template-columns: 246px minmax(0, 1fr) 316px;
  grid-template-rows: auto 1fr;
  height: 100vh;
}
@media (max-width: 1040px) {
  .layout { grid-template-columns: 1fr; grid-template-rows: auto repeat(3, minmax(0, 1fr)); }
}

.appbar {
  grid-column: 1 / -1;
  display: flex; align-items: center; gap: .875rem; flex-wrap: wrap;
  padding: .625rem .875rem;
  border-bottom: 1px solid var(--hair);
  background: linear-gradient(var(--raised), var(--surface));
}
.mark {
  display: flex; align-items: center; gap: .5rem;
  font-family: var(--display); font-weight: 600; font-size: .9375rem;
  letter-spacing: -.01em;
}
.mark i {
  width: 22px; height: 22px; border-radius: 7px;
  background: var(--cyan); color: var(--bone-ink);
  display: grid; place-items: center;
  font-family: var(--mono); font-size: 12px; font-weight: 600; font-style: normal;
}
.ws {
  display: flex; align-items: center; gap: .4rem; min-width: 0;
  font-family: var(--mono); font-size: 11.5px; color: var(--text-soft);
  background: var(--sunk); border: 1px solid var(--hair);
  padding: .3rem .5rem; border-radius: var(--r-sm);
}
.ws span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.spacer { flex: 1 1 1rem; }

.dot { width: 8px; height: 8px; border-radius: 999px; flex: none; }
.dot--ok   { background: var(--st-succeeded); }
.dot--down { background: var(--st-failed); }
.dot--wait { background: var(--st-pending); }

.rail   { border-right: 1px solid var(--hair); background: var(--surface); overflow-y: auto; }
.stage  { position: relative; overflow: auto; min-width: 0;
          background: radial-gradient(circle at 1px 1px, var(--hair) 1px, transparent 0)
                      0 0 / 18px 18px, var(--sunk); }
.aside  { border-left: 1px solid var(--hair); background: var(--surface);
          padding: .875rem; overflow-y: auto;
          display: flex; flex-direction: column; gap: .75rem; }

.placeholder {
  padding: .875rem; font-size: 12.5px; color: var(--text-faint);
  font-family: var(--mono);
}
```

- [ ] **Step 4: Commit after Task 5 installs the toolchain**

`npm test` cannot run until Task 5. Write these files now, verify them in Task 5 Step 4.

---

### Task 5: Frontend scaffolding, the shell, and the health dot

**Files:**
- Create: `studio/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`
- Create: `studio/frontend/src/main.tsx`, `src/App.tsx`, `src/health.ts`
- Create: `studio/frontend/test/mockReactFlow.ts`, `test/setup.ts`
- Test: `studio/frontend/src/health.test.ts`, `src/App.test.tsx`, `src/smoke.test.tsx`

**Interfaces:**
- Produces:
  - `health.checkHealth() -> Promise<HealthState>` — pure, `fetch`-based, never throws.
  - `App` — the shell: app bar with mark, workspace name, health dot; three empty panes.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/health.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { checkHealth } from './health';

describe('checkHealth', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('uses a relative /api path so no host is hardcoded', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true, json: () => Promise.resolve({ status: 'ok', workspace: 'w', version: '0.1.0' }),
    });

    await checkHealth();

    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toBe('/api/health');
  });

  it('reports the workspace name on success', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'ok', workspace: 'acme', version: '0.1.0' }),
    });

    await expect(checkHealth()).resolves.toEqual({
      up: true, workspace: 'acme', version: '0.1.0',
    });
  });

  it('reports down rather than throwing when the backend is unreachable', async () => {
    // The dot must go red, not blow up the app.
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('ECONNREFUSED'));

    await expect(checkHealth()).resolves.toEqual({ up: false, workspace: null, version: null });
  });

  it('reports down on a non-ok response', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, json: () => Promise.resolve({}) });

    await expect(checkHealth()).resolves.toMatchObject({ up: false });
  });
});
```

Create `studio/frontend/src/App.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const ok = { status: 'ok', workspace: 'acme-platform', version: '0.1.0' };

describe('App shell', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(ok) }));
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('renders the product mark', async () => {
    render(<App />);

    expect(screen.getByText(/implr studio/i)).toBeInTheDocument();
  });

  it('shows the workspace name reported by the backend', async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText('acme-platform')).toBeInTheDocument());
  });

  it('shows a healthy indicator when the backend answers', async () => {
    const { container } = render(<App />);

    await waitFor(() => expect(container.querySelector('.dot--ok')).toBeTruthy());
  });

  it('shows a down indicator when the backend does not answer', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('refused'));

    const { container } = render(<App />);

    await waitFor(() => expect(container.querySelector('.dot--down')).toBeTruthy());
  });

  it('lays out three panes', () => {
    const { container } = render(<App />);

    expect(container.querySelector('.rail')).toBeTruthy();
    expect(container.querySelector('.stage')).toBeTruthy();
    expect(container.querySelector('.aside')).toBeTruthy();
  });
});
```

Create `studio/frontend/src/smoke.test.tsx` — React Flow is not used until Phase 2, but the
jsdom shims are fiddly and proving them now saves debugging them later:

```tsx
import { render, waitFor } from '@testing-library/react';
import { ReactFlow } from '@xyflow/react';
import { describe, expect, it } from 'vitest';

describe('react flow renders in jsdom', () => {
  it('renders nodes and edges once measured', async () => {
    const nodes = [
      { id: 'a', position: { x: 0, y: 0 }, data: { label: 'A' } },
      { id: 'b', position: { x: 200, y: 0 }, data: { label: 'B' } },
    ];

    const { container } = render(
      <div style={{ width: 800, height: 600 }}>
        <ReactFlow nodes={nodes} edges={[{ id: 'a-b', source: 'a', target: 'b' }]}
                   nodesDraggable={false} panOnDrag={false} />
      </div>,
    );

    await waitFor(() => {
      expect(container.querySelectorAll('.react-flow__node')).toHaveLength(2);
      expect(container.querySelectorAll('.react-flow__edge').length).toBeGreaterThan(0);
    });
  });
});
```

- [ ] **Step 2: Create the project files**

`studio/frontend/package.json`:

```json
{
  "name": "implr-studio-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@xyflow/react": "^12.11.3",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "zustand": "^4.5.5"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/node": "^22.7.4",
    "@types/react": "^18.3.10",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "jsdom": "^25.0.1",
    "typescript": "^5.6.2",
    "vite": "^5.4.8",
    "vitest": "^2.1.2"
  }
}
```

`vite.config.ts`:

```ts
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    // The backend binds 127.0.0.1 only; the proxy keeps the frontend
    // free of any hardcoded host or port.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8765', ws: true, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.ts'],
  },
});
```

`tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "skipLibCheck": true,
    "types": ["vitest/globals", "@testing-library/jest-dom", "node"]
  },
  "include": ["src", "test"]
}
```

`index.html` — Google Fonts is the one external host; every face has a fallback stack in
`tokens.css` so a blocked request degrades rather than reflows:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>implr Studio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=Manrope:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '@xyflow/react/dist/style.css';
import './tokens.css';
import './app.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`test/mockReactFlow.ts` (React Flow cannot measure nodes in jsdom without these; adapted
from the official testing guide):

```ts
class ResizeObserverMock {
  callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) { this.callback = callback; }
  observe(target: Element) {
    setTimeout(() => {
      this.callback([{ target } as ResizeObserverEntry], this as unknown as ResizeObserver);
    }, 0);
  }
  unobserve() {}
  disconnect() {}
}

class DOMMatrixReadOnlyMock {
  m22: number;
  constructor(transform: string) {
    const scale = transform?.match(/scale\(([1-9.])\)/)?.[1];
    this.m22 = scale !== undefined ? +scale : 1;
  }
}

let initialised = false;

export const mockReactFlow = () => {
  if (initialised) return;
  initialised = true;

  global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
  global.DOMMatrixReadOnly = DOMMatrixReadOnlyMock as unknown as typeof DOMMatrixReadOnly;

  Object.defineProperties(global.HTMLElement.prototype, {
    offsetHeight: { get() { return parseFloat(this.style.height) || 1; } },
    offsetWidth: { get() { return parseFloat(this.style.width) || 1; } },
  });

  (global.SVGElement as unknown as { prototype: { getBBox: () => object } }).prototype.getBBox =
    () => ({ x: 0, y: 0, width: 0, height: 0 });
};
```

`test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
import { mockReactFlow } from './mockReactFlow';

mockReactFlow();
```

- [ ] **Step 3: Write `health.ts` and `App.tsx`**

`src/health.ts`:

```ts
/** Backend liveness. Pure and never-throwing: a dead backend turns the dot red,
 *  it does not take the application down. */
export interface HealthState {
  up: boolean;
  workspace: string | null;
  version: string | null;
}

export const DOWN: HealthState = { up: false, workspace: null, version: null };

export async function checkHealth(): Promise<HealthState> {
  try {
    const response = await fetch('/api/health');
    if (!response.ok) return DOWN;
    const body = await response.json();
    if (body?.status !== 'ok') return DOWN;
    return { up: true, workspace: body.workspace ?? null, version: body.version ?? null };
  } catch {
    return DOWN;
  }
}
```

`src/App.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { checkHealth, DOWN } from './health';
import type { HealthState } from './health';

const POLL_MS = 5000;

export default function App() {
  const [health, setHealth] = useState<HealthState | null>(null);

  useEffect(() => {
    let live = true;
    const tick = async () => {
      const next = await checkHealth();
      if (live) setHealth(next);
    };
    void tick();
    const timer = setInterval(tick, POLL_MS);
    return () => { live = false; clearInterval(timer); };
  }, []);

  const state = health ?? null;
  const dot = state === null ? 'dot--wait' : state.up ? 'dot--ok' : 'dot--down';
  const label = state === null ? 'connecting…' : state.up ? 'connected' : 'backend unreachable';

  return (
    <div className="layout">
      <header className="appbar">
        <div className="mark"><i>iS</i> implr Studio</div>
        <div className="ws">
          <span className={`dot ${dot}`} role="img" aria-label={label} title={label} />
          <span>{state?.workspace ?? (state === null ? 'connecting…' : 'no backend')}</span>
        </div>
        <div className="spacer" />
        {state?.version && <span className="placeholder">v{state.version}</span>}
      </header>

      <aside className="rail">
        <p className="placeholder">Steps arrive in Phase 1.</p>
      </aside>

      <div className="stage">
        <p className="placeholder">The canvas arrives in Phase 2.</p>
      </div>

      <aside className="aside">
        <p className="placeholder">Pipeline health arrives in Phase 3.</p>
      </aside>
    </div>
  );
}
```

The placeholders are deliberate. An empty pane looks broken; a pane that names the phase it
is waiting for looks intentional, and it makes progress legible when you hand this to
someone.

- [ ] **Step 4: Install, test, build**

```bash
cd studio/frontend
npm install
npm test
npm run build
```

Expected: the token tests, health tests, App tests and the React Flow smoke test all pass;
the build typechecks. If the smoke test fails with "parent container needs a width and a
height", the wrapper `<div style={{ width: 800, height: 600 }}>` is missing.

- [ ] **Step 5: Commit**

```bash
git status --porcelain | grep node_modules && echo "STOP: Task 1 was skipped"
git add studio/frontend
git commit -m "feat(studio): frontend scaffolding, design system, and the app shell"
```

---

### Task 6: Run the demo

Not a code task. This is the phase gate.

- [ ] **Step 1: Both processes up**

```bash
# terminal 1
cd studio/backend && implr-studio --workspace /tmp/studio-probe

# terminal 2
cd studio/frontend && npm run dev
```

If you have no `/tmp/studio-probe`, build one — see *Prerequisites* in
`docs/RUNTIME.md`. The server exits `2` on a directory with no `docs/implr`, which is
the check you should see working if you point it somewhere wrong.

- [ ] **Step 2: Confirm in the browser**

- Dark shell, even if your OS is in light mode.
- App bar reads **implr Studio**, then `studio-probe`, then a **green** dot.
- Three panes naming the phases that will fill them.

- [ ] **Step 3: Confirm the dot is real**

Stop the backend. Within five seconds the dot turns **red** and the workspace name becomes
`no backend`. Restart it; the dot goes green again without reloading the page.

This is the whole reason the health route exists: it proves the proxy path end to end, so
when Phase 1 adds a real endpoint you already know the plumbing works.

- [ ] **Step 4: Confirm loopback only**

```bash
curl -s -o /dev/null -w "loopback: %{http_code}\n" http://127.0.0.1:8765/api/health
curl -s -m 3 -o /dev/null -w "external: %{http_code}\n" "http://$(hostname):8765/api/health" \
  || echo "external: refused (correct)"
```

Expected: `loopback: 200`, and the second refused or timing out.

- [ ] **Step 5: Confirm the single-process path**

```bash
cd studio/frontend && npm run build
# restart implr-studio, then:
curl -s http://127.0.0.1:8765/ | head -3                     # the SPA
curl -s http://127.0.0.1:8765/api/health                      # still reachable
```

Expected: SPA HTML rather than the "not built" page, and the health route still answering —
the catch-all mount must not shadow `/api`.

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes.
- [ ] `npm test` and `npm run build` pass in `studio/frontend/`.
- [ ] `python -m pytest tests/` at the repo root still passes — 68 pre-existing tests.
- [ ] `PYTHONPATH=scripts python -m implr_validate --repo --root .` exits `0`, and is fast
      even with `node_modules/` present.
- [ ] `git status --porcelain` shows no `__pycache__`, `node_modules`, `dist` or `.egg-info`.
- [ ] `implr-studio --workspace <dir with no docs/implr>` exits `2` with an actionable message.
- [ ] `server.py` contains no `0.0.0.0` and no `--host`.
- [ ] `GET /` returns instructions when the UI is not built, never a 404.
- [ ] `tokens.test.ts` passes: reserved groups present, no `prefers-color-scheme`, no
      saturated colour in `app.css`, every font stack has a fallback.
- [ ] **The demo:** two processes up, dark shell, green dot that goes red when the backend
      stops and green again when it returns.

---

## What the next phase gets

A running shell with a proven `/api` path and a design system nothing can drift from.
Phase 1 adds `step-registry.json`, its loader, `GET /api/projects/{pid}/registry`, and turns the left rail
into a real palette — so its demo is *"nine steps appear, two of them dashed"*.
