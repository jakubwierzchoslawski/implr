# implr Studio — Phase 2: Draw a pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drag two steps from the palette onto a canvas, connect them, press Save — and `docs/implr/config/pipeline.yaml` appears in the target project. Reload the page and the graph is still there.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phases 0–1.

---

## Demo

Both processes up. Drag **Document Ingestion** onto the canvas — a node card appears where
you dropped it. Drag **Architecture Brief** to its right. Drag from the first node's right
port to the second's left port — an edge appears. Press **Save**.

```bash
cat /tmp/studio-probe/docs/implr/config/pipeline.yaml
```

```yaml
version: 1
nodes:
- id: doc-ingest
  step: doc-ingest
  args: []
  position:
    x: 142.0
    y: 88.0
- id: arch-gen
  step: arch-gen
  args: []
  position:
    x: 411.0
    y: 96.0
edges:
- from: doc-ingest
  to: arch-gen
  gate:
    type: none
```

Reload the browser: the two nodes and the edge are back, at the same positions. Drag a third
copy of Document Ingestion on: it becomes `doc-ingest-2`.

---

## Scope boundary — not in this phase

**No graph validation.** You can save a cycle, an island, a graph with no root. Phase 3 adds
all of that. What this phase *does* reject is a malformed **document** — an unsupported
`version`, a node with no `step`, an unknown gate type — because `pipeline_from_dict` cannot
construct an object from it. The line is: *well-formed* here, *valid graph* in Phase 3.

No configurator, no gate editor, no args UI, no runs. Gates parse and round-trip but the only
one you can create is `{type: none}`, and edges render as plain lines with no label. Node
cards show label, id and phase — no args, no agents, no status.

---

## Tech Stack

Python 3.11+, PyYAML, FastAPI. React + TypeScript, `@xyflow/react` v12, Zustand, Vitest.
All already installed by Phase 0.

## Global Constraints

- The package is **`@xyflow/react`**, not `reactflow`. Any snippet importing from
  `'reactflow'` is v11 and wrong for this codebase.
- Use **`screenToFlowPosition`** from `useReactFlow()`. `project()` was **removed** in v12.
- `nodeTypes` and `edgeTypes` must be **module-scope constants**. Recreating them per render
  remounts every node and destroys DOM state.
- Never mutate a node or edge object — React Flow's change detection is reference-based.
- Measured dimensions live at `node.measured.width/height` in v12, not `node.width/height`.
- `fromFlow` must never emit React Flow's transient fields (`selected`, `dragging`,
  `measured`, `width`, `height`) into the DTO.
- The on-disk format keeps `from`/`to` keys. `source`/`target` is a React Flow concept and
  stays on the TypeScript side.
- Colours from tokens only.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/backend/implr_studio/pipeline.py` | Dataclasses, dict conversion, YAML load/save. **No validation.** |
| `studio/backend/implr_studio/context.py` | **Modified** — gains `pipeline_path`. |
| `studio/backend/implr_studio/api.py` | **Modified** — `GET`/`PUT /api/pipeline`. |
| `studio/frontend/src/graph.ts` | **Pure** mapping between the DTO and React Flow. Carries the round-trip guarantee. |
| `studio/frontend/src/flowTypes.ts` | Module-scope `nodeTypes` / `edgeTypes`. |
| `studio/frontend/src/nodes/StepNode.tsx` | The node card. |
| `studio/frontend/src/store.ts` | Zustand: graph state and actions. |
| `studio/frontend/src/App.tsx` | **Modified** — canvas, drag-and-drop, Save. |

---

### Task 1: Pipeline config load and save

**Files:**
- Create: `studio/backend/implr_studio/pipeline.py`
- Test: `studio/backend/tests/test_pipeline.py`

**Interfaces:**
- Produces:
  - `pipeline.Gate` — frozen: `type: str = "none"`, `artefact: str | None`, `quantifier: str | None`, `require: dict | None`.
  - `pipeline.Node` — frozen: `id`, `step`, `args: tuple[str, ...]`, `position: dict`.
  - `pipeline.Edge` — frozen: `source`, `target`, `gate: Gate`.
  - `pipeline.Pipeline` — frozen: `version: int`, `nodes: tuple[Node, ...]`, `edges: tuple[Edge, ...]`.
  - `pipeline.pipeline_from_dict(data) -> Pipeline`, `pipeline_to_dict(p) -> dict`
  - `pipeline.load_pipeline(path) -> Pipeline`, `save_pipeline(path, p) -> None`
  - `pipeline.PipelineError`
  - `pipeline.SUPPORTED_VERSION = 1`, `GATE_TYPES`, `QUANTIFIERS`

`Edge` uses `source`/`target` because `from` is a Python keyword. The YAML keys stay
`from`/`to`; conversion happens in the dict functions and nowhere else.

`Gate` carries `artefact`, `quantifier` and `require` from this phase even though only
`{type: none}` is reachable through the UI — the shape has to round-trip so that a
hand-written or Phase-6-authored gate survives a load/save cycle in Phase 2 unchanged.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_pipeline.py`:

```python
from pathlib import Path

import pytest
import yaml

from implr_studio import pipeline

VALID = """\
version: 1
nodes:
  - id: ingest
    step: doc-ingest
    args: []
    position: {x: 80, y: 120}
  - id: arch
    step: arch-gen
    args: []
    position: {x: 320, y: 120}
edges:
  - from: ingest
    to: arch
    gate:
      type: artifact
      artefact: requirement
      quantifier: all
      require: {status: approved}
"""


def test_load_parses_nodes_and_edges(tmp_path: Path):
    path = tmp_path / "pipeline.yaml"
    path.write_text(VALID, encoding="utf-8")

    p = pipeline.load_pipeline(path)

    assert p.version == 1
    assert [n.id for n in p.nodes] == ["ingest", "arch"]
    assert p.nodes[0].step == "doc-ingest"
    assert p.nodes[0].position == {"x": 80, "y": 120}
    assert p.edges[0].source == "ingest"
    assert p.edges[0].target == "arch"
    assert p.edges[0].gate.type == "artifact"
    assert p.edges[0].gate.require == {"status": "approved"}


def test_gate_defaults_to_none_when_omitted(tmp_path: Path):
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        "version: 1\n"
        "nodes:\n"
        "  - {id: a, step: doc-ingest, args: [], position: {x: 0, y: 0}}\n"
        "  - {id: b, step: arch-gen, args: [], position: {x: 1, y: 0}}\n"
        "edges:\n"
        "  - {from: a, to: b}\n",
        encoding="utf-8",
    )

    p = pipeline.load_pipeline(path)

    assert p.edges[0].gate.type == "none"
    assert p.edges[0].gate.artefact is None


def test_round_trip_preserves_structure(tmp_path: Path):
    src = tmp_path / "in.yaml"
    src.write_text(VALID, encoding="utf-8")
    loaded = pipeline.load_pipeline(src)

    out = tmp_path / "out.yaml"
    pipeline.save_pipeline(out, loaded)

    assert pipeline.load_pipeline(out) == loaded


def test_saved_yaml_uses_from_and_to_keys(tmp_path: Path):
    """The on-disk format stays human-editable; source/target is Python-side only."""
    src = tmp_path / "in.yaml"
    src.write_text(VALID, encoding="utf-8")
    out = tmp_path / "out.yaml"

    pipeline.save_pipeline(out, pipeline.load_pipeline(src))

    raw = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert raw["edges"][0]["from"] == "ingest"
    assert raw["edges"][0]["to"] == "arch"
    assert "source" not in raw["edges"][0]


def test_save_creates_the_parent_directory(tmp_path: Path):
    """A fresh workspace has no docs/implr/config yet."""
    out = tmp_path / "docs" / "implr" / "config" / "pipeline.yaml"

    pipeline.save_pipeline(out, pipeline.pipeline_from_dict(
        {"version": 1, "nodes": [], "edges": []}))

    assert out.is_file()


def test_empty_pipeline_round_trips(tmp_path: Path):
    """An empty canvas is a legal thing to save while designing."""
    out = tmp_path / "pipeline.yaml"
    empty = pipeline.pipeline_from_dict({"version": 1, "nodes": [], "edges": []})

    pipeline.save_pipeline(out, empty)

    assert pipeline.load_pipeline(out) == empty


def test_unsupported_version_rejected(tmp_path: Path):
    path = tmp_path / "pipeline.yaml"
    path.write_text("version: 99\nnodes: []\nedges: []\n", encoding="utf-8")

    with pytest.raises(pipeline.PipelineError, match="unsupported pipeline version: 99"):
        pipeline.load_pipeline(path)


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(pipeline.PipelineError, match="pipeline config not found"):
        pipeline.load_pipeline(tmp_path / "nope.yaml")


def test_node_without_a_step_rejected():
    with pytest.raises(pipeline.PipelineError, match="node missing required field: step"):
        pipeline.pipeline_from_dict({"version": 1, "nodes": [{"id": "a"}], "edges": []})


def test_edge_without_a_target_rejected():
    with pytest.raises(pipeline.PipelineError, match="edge missing required field: to"):
        pipeline.pipeline_from_dict(
            {"version": 1, "nodes": [], "edges": [{"from": "a"}]})


def test_unknown_gate_type_rejected():
    with pytest.raises(pipeline.PipelineError, match="unknown gate type 'wibble'"):
        pipeline.pipeline_from_dict({
            "version": 1, "nodes": [],
            "edges": [{"from": "a", "to": "b", "gate": {"type": "wibble"}}]})


def test_unknown_quantifier_rejected():
    with pytest.raises(pipeline.PipelineError, match="unknown quantifier 'most'"):
        pipeline.pipeline_from_dict({
            "version": 1, "nodes": [],
            "edges": [{"from": "a", "to": "b",
                       "gate": {"type": "artifact", "quantifier": "most"}}]})


def test_malformed_yaml_is_a_pipeline_error_not_a_yaml_error(tmp_path: Path):
    """Callers handle PipelineError; a raw YAMLError would escape as a 500."""
    path = tmp_path / "pipeline.yaml"
    path.write_text("version: 1\nnodes: [unclosed\n", encoding="utf-8")

    with pytest.raises(pipeline.PipelineError, match="could not be parsed"):
        pipeline.load_pipeline(path)


def test_a_cycle_loads_without_complaint():
    """Graph validation arrives in Phase 3. This phase only reads the document."""
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    })

    assert len(p.edges) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'pipeline'`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/pipeline.py`:

```python
"""Load, convert, and save docs/implr/config/pipeline.yaml.

This module reads and writes the document. It does not judge the graph - no
cycle detection, no reachability, no step existence. Phase 3 adds
validate_pipeline alongside these functions.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SUPPORTED_VERSION = 1
GATE_TYPES = ("none", "manual", "artifact", "artifact+manual")
QUANTIFIERS = ("all", "any")


class PipelineError(Exception):
    pass


@dataclass(frozen=True)
class Gate:
    type: str = "none"
    artefact: str | None = None
    quantifier: str | None = None
    require: dict | None = None


@dataclass(frozen=True)
class Node:
    id: str
    step: str
    args: tuple[str, ...] = ()
    position: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    gate: Gate = Gate()


@dataclass(frozen=True)
class Pipeline:
    version: int
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


def _gate_from_dict(data: dict | None) -> Gate:
    if not data:
        return Gate()
    gate_type = data.get("type", "none")
    if gate_type not in GATE_TYPES:
        raise PipelineError(
            "unknown gate type %r (legal: %s)" % (gate_type, list(GATE_TYPES)))
    quantifier = data.get("quantifier")
    if quantifier is not None and quantifier not in QUANTIFIERS:
        raise PipelineError(
            "unknown quantifier %r (legal: %s)" % (quantifier, list(QUANTIFIERS)))
    return Gate(
        type=gate_type,
        artefact=data.get("artefact"),
        quantifier=quantifier,
        require=dict(data["require"]) if data.get("require") else None,
    )


def _gate_to_dict(gate: Gate) -> dict:
    # Sparse: only what was set. A `none` gate serialises as one key, which keeps
    # the common case readable on disk.
    out: dict = {"type": gate.type}
    if gate.artefact is not None:
        out["artefact"] = gate.artefact
    if gate.quantifier is not None:
        out["quantifier"] = gate.quantifier
    if gate.require is not None:
        out["require"] = dict(gate.require)
    return out


def pipeline_from_dict(data: dict) -> Pipeline:
    version = data.get("version", SUPPORTED_VERSION)
    if version != SUPPORTED_VERSION:
        raise PipelineError("unsupported pipeline version: %s" % version)

    nodes = []
    for entry in data.get("nodes") or []:
        for required in ("id", "step"):
            if required not in entry:
                raise PipelineError("node missing required field: %s" % required)
        nodes.append(Node(
            id=entry["id"],
            step=entry["step"],
            args=tuple(entry.get("args") or ()),
            position=dict(entry.get("position") or {}),
        ))

    edges = []
    for entry in data.get("edges") or []:
        for required in ("from", "to"):
            if required not in entry:
                raise PipelineError("edge missing required field: %s" % required)
        edges.append(Edge(
            source=entry["from"],
            target=entry["to"],
            gate=_gate_from_dict(entry.get("gate")),
        ))

    return Pipeline(version=version, nodes=tuple(nodes), edges=tuple(edges))


def _node_to_dict(n: Node) -> dict:
    return {
        "id": n.id,
        "step": n.step,
        "args": list(n.args),
        "position": dict(n.position),
    }


def pipeline_to_dict(p: Pipeline) -> dict:
    return {
        "version": p.version,
        "nodes": [_node_to_dict(n) for n in p.nodes],
        "edges": [
            {"from": e.source, "to": e.target, "gate": _gate_to_dict(e.gate)}
            for e in p.edges
        ],
    }


def load_pipeline(path: Path) -> Pipeline:
    path = Path(path)
    if not path.is_file():
        raise PipelineError("pipeline config not found: %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        # Callers handle PipelineError; a raw YAMLError would escape as a 500.
        raise PipelineError("%s could not be parsed as YAML: %s" % (path, e))
    return pipeline_from_dict(data)


def save_pipeline(path: Path, p: Pipeline) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(pipeline_to_dict(p), f, sort_keys=False, default_flow_style=False)
```

- [ ] **Step 4: Run and commit**

Run: `cd studio/backend && python -m pytest tests/test_pipeline.py -v`

```bash
git add studio/backend/implr_studio/pipeline.py studio/backend/tests/test_pipeline.py
git commit -m "feat(studio): pipeline.yaml load, save, and round-trip"
```

---

### Task 2: The pipeline routes

**Files:**
- Modify: `studio/backend/implr_studio/context.py`, `api.py`
- Test: `studio/backend/tests/test_api_pipeline.py`

**Interfaces:**
- Produces:
  - `AppContext.pipeline_path: Path` — `<workspace>/docs/implr/config/pipeline.yaml`.
  - `GET /api/pipeline` → `{"pipeline": {...}, "exists": bool}`. A missing file returns
    `exists: false` with an **empty pipeline**, not a 404 — a fresh project has no pipeline
    and the builder must still open.
  - `PUT /api/pipeline` — body is a pipeline dict. `200` on success, `422` with
    `{"findings": [...]}` when the document cannot be parsed.

The 422 shape is introduced here, with a single `parse-error` finding, so Phase 3 can add
graph findings to the same envelope rather than changing it.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_api_pipeline.py`:

```python
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from implr_studio import context as ctx_mod
from implr_studio.api import create_app


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    from implr_studio import implr_bridge

    src = implr_bridge.repo_root() / "scaffold" / "schemas"
    dst = tmp_path / "docs" / "implr" / "schemas"
    dst.mkdir(parents=True)
    for f in src.glob("*.json"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(workspace: Path):
    with TestClient(create_app(ctx_mod.build_context(workspace))) as c:
        yield c


VALID = {
    "version": 1,
    "nodes": [
        {"id": "ingest", "step": "doc-ingest", "args": [], "position": {"x": 0, "y": 0}},
        {"id": "arch", "step": "arch-gen", "args": [], "position": {"x": 240, "y": 0}},
    ],
    "edges": [{"from": "ingest", "to": "arch", "gate": {"type": "none"}}],
}


def test_get_on_a_fresh_project_returns_empty_not_404(client):
    """A new project has no pipeline.yaml. The builder must still open."""
    r = client.get("/api/pipeline")

    assert r.status_code == 200
    assert r.json()["exists"] is False
    assert r.json()["pipeline"]["nodes"] == []
    assert r.json()["pipeline"]["edges"] == []
    assert r.json()["pipeline"]["version"] == 1


def test_put_then_get_round_trips(client):
    assert client.put("/api/pipeline", json=VALID).status_code == 200

    body = client.get("/api/pipeline").json()

    assert body["exists"] is True
    assert [n["id"] for n in body["pipeline"]["nodes"]] == ["ingest", "arch"]
    assert body["pipeline"]["edges"][0]["from"] == "ingest"


def test_put_writes_the_file_to_the_expected_path(client, workspace):
    client.put("/api/pipeline", json=VALID)

    written = workspace / "docs" / "implr" / "config" / "pipeline.yaml"
    assert written.is_file()
    raw = yaml.safe_load(written.read_text(encoding="utf-8"))
    assert raw["edges"][0]["from"] == "ingest"
    assert raw["nodes"][0]["position"] == {"x": 0, "y": 0}


def test_put_preserves_positions(client):
    positioned = dict(VALID, nodes=[
        {"id": "a", "step": "doc-ingest", "args": [], "position": {"x": 142.5, "y": 88.0}}],
        edges=[])

    client.put("/api/pipeline", json=positioned)

    got = client.get("/api/pipeline").json()["pipeline"]["nodes"][0]["position"]
    assert got == {"x": 142.5, "y": 88.0}


def test_put_rejects_an_unsupported_version_with_findings(client):
    r = client.put("/api/pipeline", json={"version": 99, "nodes": [], "edges": []})

    assert r.status_code == 422
    assert [f["code"] for f in r.json()["findings"]] == ["parse-error"]
    assert "99" in r.json()["findings"][0]["message"]


def test_put_rejects_an_unknown_gate_type(client):
    bad = dict(VALID, edges=[{"from": "ingest", "to": "arch", "gate": {"type": "wibble"}}])

    r = client.put("/api/pipeline", json=bad)

    assert r.status_code == 422
    assert r.json()["findings"][0]["code"] == "parse-error"


def test_rejected_put_does_not_write_the_file(client, workspace):
    client.put("/api/pipeline", json={"version": 99, "nodes": [], "edges": []})

    assert not (workspace / "docs" / "implr" / "config" / "pipeline.yaml").exists()


def test_put_accepts_a_cycle_in_this_phase(client):
    """Graph validation is Phase 3. Saving a work-in-progress graph must not be blocked."""
    cyclic = dict(VALID, edges=[
        {"from": "ingest", "to": "arch"}, {"from": "arch", "to": "ingest"}])

    assert client.put("/api/pipeline", json=cyclic).status_code == 200


def test_put_accepts_an_empty_canvas(client):
    assert client.put("/api/pipeline", json={"version": 1, "nodes": [], "edges": []}).status_code == 200


def test_get_surfaces_a_corrupt_file_as_findings_not_a_500(client, workspace):
    """A hand-edited broken file must not take the builder down."""
    path = workspace / "docs" / "implr" / "config" / "pipeline.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("version: 1\nnodes: [unclosed\n", encoding="utf-8")

    r = client.get("/api/pipeline")

    assert r.status_code == 422
    assert r.json()["findings"][0]["code"] == "parse-error"


def test_no_route_accepts_a_filesystem_path(client):
    """Security constraint: the workspace is fixed at startup."""
    blob = str(client.get("/openapi.json").json()).lower()

    for banned in ("workspace_path", "cwd", "directory", "file_path"):
        assert banned not in blob
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_api_pipeline.py -v`
Expected: FAIL — 404s from the missing routes.

- [ ] **Step 3: Add `pipeline_path` to the context**

```python
PIPELINE_RELPATH = Path("docs") / "implr" / "config" / "pipeline.yaml"


@dataclass
class AppContext:
    workspace: Path
    registry: object
    pipeline_path: Path


def build_context(workspace: Path) -> AppContext:
    workspace = Path(workspace).resolve()
    reg = load_registry(resolve_schema_dir(workspace), repo_root() / "skills")
    return AppContext(
        workspace=workspace,
        registry=reg,
        pipeline_path=workspace / PIPELINE_RELPATH,
    )
```

- [ ] **Step 4: Add the routes to `api.py`**

Add imports:

```python
from fastapi import Body, FastAPI, HTTPException
from fastapi.exceptions import HTTPException as _HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .pipeline import (
    PipelineError, load_pipeline, pipeline_from_dict, pipeline_to_dict, save_pipeline,
)

EMPTY_PIPELINE = {"version": 1, "nodes": [], "edges": []}
```

Inside `create_app`, before the root page:

```python
    def _findings(code: str, message: str) -> dict:
        return {"findings": [{"code": code, "message": message, "node_id": None}]}

    @app.get("/api/pipeline")
    def get_pipeline() -> dict:
        if not context.pipeline_path.is_file():
            # Not a 404: a fresh project has no pipeline and the builder must open.
            return {"pipeline": EMPTY_PIPELINE, "exists": False}
        try:
            p = load_pipeline(context.pipeline_path)
        except PipelineError as e:
            # A hand-edited broken file is the operator's problem to see, not a 500.
            raise HTTPException(422, detail=_findings("parse-error", str(e)))
        return {"pipeline": pipeline_to_dict(p), "exists": True}

    @app.put("/api/pipeline")
    def put_pipeline(body: dict = Body(...)) -> dict:
        try:
            p = pipeline_from_dict(body)
        except PipelineError as e:
            raise HTTPException(422, detail=_findings("parse-error", str(e)))

        # Phase 3 inserts graph validation here, before the write.
        save_pipeline(context.pipeline_path, p)
        return {"pipeline": pipeline_to_dict(p), "exists": True}
```

And register the handler that unwraps the findings envelope, immediately before
`return app`:

```python
    @app.exception_handler(_HTTPException)
    async def _unwrap_findings(request, exc: _HTTPException):
        # FastAPI wraps detail in {"detail": ...}; a findings payload is returned
        # at the top level so the client has one shape to parse.
        if isinstance(exc.detail, dict) and "findings" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

- [ ] **Step 5: Run the whole backend suite and commit**

Run: `cd studio/backend && python -m pytest -v`

```bash
git add studio/backend
git commit -m "feat(studio): pipeline config routes with a findings envelope"
```

---

### Task 3: Pure DTO mapping

**Files:**
- Create: `studio/frontend/src/graph.ts`
- Modify: `studio/frontend/src/types.ts`
- Test: `studio/frontend/src/graph.test.ts`

This module carries the round-trip guarantee, so it gets the heaviest tests in the phase and
contains no React import.

**Interfaces:**
- Produces:
  - `types.Gate`, `NodeDTO`, `EdgeDTO`, `PipelineDTO`, `StepNodeData`, `GateEdgeData`.
  - `graph.FlowNode`, `graph.FlowEdge` type aliases.
  - `graph.toFlow(dto, steps) -> { nodes, edges }`
  - `graph.fromFlow(nodes, edges) -> PipelineDTO`
  - `graph.makeNode(step, position, existingIds) -> FlowNode`
  - `graph.edgeId(from, to) -> string`
  - `graph.DEFAULT_GATE`

- [ ] **Step 1: Write the failing test**

Create `studio/frontend/src/graph.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import * as graph from './graph';
import type { PipelineDTO, StepDef } from './types';

const base = {
  args_allowed: [], args_default: [], interactive: false,
  agents: [], consumes: [], produces: [], produces_artefact: null,
};

const STEPS: Record<string, StepDef> = {
  'doc-ingest': { ...base, id: 'doc-ingest', label: 'Document Ingestion',
    phase: 'discovery', skill: 'doc-ingest', description: 'd', available: true },
  'dev-planner': { ...base, id: 'dev-planner', label: 'Planning', phase: 'planning',
    skill: 'dev-planner', args_default: ['--all'], interactive: true,
    description: 'p', available: true },
};

const DTO: PipelineDTO = {
  version: 1,
  nodes: [
    { id: 'ingest', step: 'doc-ingest', args: [], position: { x: 10, y: 20 } },
    { id: 'plan', step: 'dev-planner', args: ['--all'], position: { x: 200, y: 20 } },
  ],
  edges: [{ from: 'ingest', to: 'plan', gate: { type: 'none' } }],
};

describe('toFlow', () => {
  it('maps a node with its step definition into data', () => {
    const { nodes } = graph.toFlow(DTO, STEPS);

    expect(nodes[0].id).toBe('ingest');
    expect(nodes[0].type).toBe('step');
    expect(nodes[0].position).toEqual({ x: 10, y: 20 });
    expect(nodes[0].data.label).toBe('Document Ingestion');
    expect(nodes[0].data.phase).toBe('discovery');
    expect(nodes[0].data.args).toEqual([]);
    expect(nodes[0].data.available).toBe(true);
  });

  it('marks a node whose step is missing from the registry as unavailable', () => {
    const orphan: PipelineDTO = {
      version: 1,
      nodes: [{ id: 'x', step: 'sec-review', args: [], position: { x: 0, y: 0 } }],
      edges: [],
    };

    const { nodes } = graph.toFlow(orphan, STEPS);

    // A pipeline referencing a step this build does not know must still render,
    // labelled by its raw step id, rather than crashing the canvas.
    expect(nodes[0].data.available).toBe(false);
    expect(nodes[0].data.label).toBe('sec-review');
    expect(nodes[0].data.phase).toBe('unknown');
  });

  it('maps from/to onto source/target and keeps the gate in edge data', () => {
    const { edges } = graph.toFlow(DTO, STEPS);

    expect(edges[0].source).toBe('ingest');
    expect(edges[0].target).toBe('plan');
    expect(edges[0].type).toBe('gate');
    expect(edges[0].data!.gate.type).toBe('none');
  });

  it('gives every edge a stable deterministic id', () => {
    expect(graph.toFlow(DTO, STEPS).edges[0].id)
      .toBe(graph.toFlow(DTO, STEPS).edges[0].id);
    expect(graph.edgeId('a', 'b')).toBe('a__b');
  });
});

describe('fromFlow', () => {
  it('round-trips a pipeline unchanged', () => {
    const { nodes, edges } = graph.toFlow(DTO, STEPS);

    expect(graph.fromFlow(nodes, edges)).toEqual(DTO);
  });

  it('strips React Flow transient fields from the DTO', () => {
    const { nodes, edges } = graph.toFlow(DTO, STEPS);
    const dirty = nodes.map((n) => ({
      ...n, selected: true, dragging: true,
      measured: { width: 100, height: 40 }, width: 100, height: 40,
    }));

    const serialized = JSON.stringify(graph.fromFlow(dirty as typeof nodes, edges));

    for (const field of ['selected', 'dragging', 'measured', 'label', 'available']) {
      expect(serialized).not.toContain(field);
    }
  });

  it('rounds nothing and preserves fractional positions', () => {
    const { nodes, edges } = graph.toFlow(DTO, STEPS);
    const moved = [{ ...nodes[0], position: { x: 142.5, y: 88.25 } }, nodes[1]];

    expect(graph.fromFlow(moved, edges).nodes[0].position).toEqual({ x: 142.5, y: 88.25 });
  });

  it('emits an empty pipeline for an empty canvas', () => {
    expect(graph.fromFlow([], [])).toEqual({ version: 1, nodes: [], edges: [] });
  });
});

describe('makeNode', () => {
  it('seeds args from args_default', () => {
    const node = graph.makeNode(STEPS['dev-planner'], { x: 0, y: 0 }, []);

    expect(node.data.args).toEqual(['--all']);
    expect(node.data.interactive).toBe(true);
  });

  it('generates a unique id from the step id', () => {
    const first = graph.makeNode(STEPS['doc-ingest'], { x: 0, y: 0 }, []);
    const second = graph.makeNode(STEPS['doc-ingest'], { x: 0, y: 0 }, [first.id]);
    const third = graph.makeNode(STEPS['doc-ingest'], { x: 0, y: 0 }, [first.id, second.id]);

    expect([first.id, second.id, third.id])
      .toEqual(['doc-ingest', 'doc-ingest-2', 'doc-ingest-3']);
  });

  it('copies the drop position rather than aliasing it', () => {
    const position = { x: 5, y: 6 };
    const node = graph.makeNode(STEPS['doc-ingest'], position, []);

    position.x = 999;

    expect(node.position.x).toBe(5);
  });
});
```

- [ ] **Step 2: Extend `types.ts`**

```ts
export type GateType = 'none' | 'manual' | 'artifact' | 'artifact+manual';
export type Quantifier = 'all' | 'any';

export interface Gate {
  type: GateType;
  artefact?: string | null;
  quantifier?: Quantifier | null;
  require?: Record<string, string> | null;
}

export interface NodeDTO {
  id: string;
  step: string;
  args: string[];
  position: { x: number; y: number };
}

export interface EdgeDTO { from: string; to: string; gate: Gate }
export interface PipelineDTO { version: number; nodes: NodeDTO[]; edges: EdgeDTO[] }

export interface StepNodeData {
  label: string;
  step: string;
  phase: string;
  args: string[];
  interactive: boolean;
  available: boolean;
}

export interface GateEdgeData { gate: Gate }
```

- [ ] **Step 3: Write `graph.ts`**

```ts
/** Pure mapping between the backend's pipeline.yaml shape and React Flow's.
 *  No React import belongs here - this module carries the round-trip guarantee. */
import type { Edge, Node } from '@xyflow/react';
import type {
  EdgeDTO, Gate, GateEdgeData, NodeDTO, PipelineDTO, StepDef, StepNodeData,
} from './types';

export type FlowNode = Node<StepNodeData>;
export type FlowEdge = Edge<GateEdgeData>;

export const DEFAULT_GATE: Gate = { type: 'none' };

export const edgeId = (from: string, to: string): string => `${from}__${to}`;

export function toFlow(
  dto: PipelineDTO,
  steps: Record<string, StepDef>,
): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const nodes: FlowNode[] = dto.nodes.map((n) => {
    const def = steps[n.step];
    return {
      id: n.id,
      type: 'step',
      position: { ...n.position },
      data: {
        // A pipeline may name a step this build does not know - render it by its
        // raw id rather than crashing the canvas.
        label: def ? def.label : n.step,
        step: n.step,
        phase: def ? def.phase : 'unknown',
        args: [...n.args],
        interactive: def ? def.interactive : false,
        available: def ? def.available : false,
      },
    };
  });

  const edges: FlowEdge[] = dto.edges.map((e) => ({
    id: edgeId(e.from, e.to),
    source: e.from,
    target: e.to,
    type: 'gate',
    data: { gate: e.gate ?? DEFAULT_GATE },
  }));

  return { nodes, edges };
}

export function fromFlow(nodes: FlowNode[], edges: FlowEdge[]): PipelineDTO {
  return {
    version: 1,
    // Only these four keys. React Flow decorates its nodes with `selected`,
    // `dragging` and `measured`; none of that belongs in a config file.
    nodes: nodes.map((n): NodeDTO => ({
      id: n.id,
      step: n.data.step,
      args: [...n.data.args],
      position: { x: n.position.x, y: n.position.y },
    })),
    edges: edges.map((e): EdgeDTO => ({
      from: e.source,
      to: e.target,
      gate: e.data?.gate ?? DEFAULT_GATE,
    })),
  };
}

export function makeNode(
  step: StepDef,
  position: { x: number; y: number },
  existingIds: string[],
): FlowNode {
  const taken = new Set(existingIds);
  let id = step.id;
  let n = 2;
  while (taken.has(id)) {
    id = `${step.id}-${n}`;
    n += 1;
  }
  return {
    id,
    type: 'step',
    position: { ...position },
    data: {
      label: step.label,
      step: step.id,
      phase: step.phase,
      args: [...step.args_default],
      interactive: step.interactive,
      available: step.available,
    },
  };
}
```

The DTO key order — `id`, `step`, `args`, `position` — matches the backend's
`_node_to_dict`, which keeps the round-trip test honest and `pipeline.yaml` diffs stable.

- [ ] **Step 4: Run and commit**

```bash
cd studio/frontend && npm test
git add studio/frontend/src/graph.ts studio/frontend/src/graph.test.ts studio/frontend/src/types.ts
git commit -m "feat(studio): pure DTO mapping between pipeline.yaml and React Flow"
```

---

### Task 4: The node card and the store

**Files:**
- Create: `studio/frontend/src/nodes/StepNode.tsx`, `src/edges/GateEdge.tsx`, `src/flowTypes.ts`, `src/store.ts`
- Modify: `studio/frontend/src/app.css`
- Test: `src/nodes/StepNode.test.tsx`, `src/store.test.ts`

**Interfaces:**
- Produces:
  - `StepNode` — card with label, node id, phase, an `?` badge for interactive steps and a `!` badge for unimplemented ones. Target handle left, source handle right.
  - `GateEdge` — a smooth-step path. **No label yet**; Phase 6 adds the chip.
  - `flowTypes.nodeTypes` / `edgeTypes` — module-scope constants.
  - `store.usePipelineStore` — `nodes`, `edges`, `steps`, `phases`; actions `onNodesChange`, `onEdgesChange`, `onConnect`, `addStepNode`, `loadFrom`, `toDTO`, `setCatalogue`.

Zustand rather than `useNodesState` because the save action — and, from Phase 9, the
WebSocket — must reach graph state from outside the React tree.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/nodes/StepNode.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { ReactFlow, ReactFlowProvider } from '@xyflow/react';
import { describe, expect, it } from 'vitest';
import { nodeTypes } from '../flowTypes';
import type { FlowNode } from '../graph';

function renderNode(data: Partial<FlowNode['data']>, id = 'ingest') {
  const nodes: FlowNode[] = [{
    id, type: 'step', position: { x: 0, y: 0 },
    data: {
      label: 'Document Ingestion', step: 'doc-ingest', phase: 'discovery',
      args: [], interactive: false, available: true, ...data,
    },
  }];
  return render(
    <div style={{ width: 800, height: 600 }}>
      <ReactFlowProvider>
        <ReactFlow nodes={nodes} edges={[]} nodeTypes={nodeTypes}
                   nodesDraggable={false} panOnDrag={false} />
      </ReactFlowProvider>
    </div>,
  );
}

describe('StepNode', () => {
  it('shows the label, the node id, and the phase', () => {
    renderNode({});

    expect(screen.getByText('Document Ingestion')).toBeInTheDocument();
    expect(screen.getByText('ingest')).toBeInTheDocument();
    expect(screen.getByText('discovery')).toBeInTheDocument();
  });

  it('distinguishes the node id from the step id when they differ', () => {
    renderNode({}, 'doc-ingest-2');

    expect(screen.getByText('doc-ingest-2')).toBeInTheDocument();
  });

  it('badges an interactive step', () => {
    renderNode({ interactive: true });

    expect(screen.getByTitle(/asks questions/i)).toBeInTheDocument();
  });

  it('badges an unimplemented step', () => {
    renderNode({ available: false });

    expect(screen.getByTitle(/not implemented/i)).toBeInTheDocument();
  });

  it('marks an unimplemented node visually', () => {
    const { container } = renderNode({ available: false });

    expect(container.querySelector('.step-node--planned')).toBeTruthy();
  });

  it('nodeTypes and edgeTypes are stable module-scope objects', () => {
    // Recreating them per render remounts every node and destroys DOM state.
    expect(nodeTypes).toBe(nodeTypes);
  });
});
```

Create `studio/frontend/src/store.test.ts`:

```ts
import { beforeEach, describe, expect, it } from 'vitest';
import { usePipelineStore } from './store';
import type { PipelineDTO, StepDef } from './types';

const base = {
  args_allowed: [], args_default: [], interactive: false,
  agents: [], consumes: [], produces: [], produces_artefact: null,
};

const STEP: StepDef = { ...base, id: 'doc-ingest', label: 'Document Ingestion',
  phase: 'discovery', skill: 'doc-ingest', description: 'd', available: true };

const DTO: PipelineDTO = {
  version: 1,
  nodes: [
    { id: 'a', step: 'doc-ingest', args: [], position: { x: 0, y: 0 } },
    { id: 'b', step: 'doc-ingest', args: [], position: { x: 200, y: 0 } },
  ],
  edges: [{ from: 'a', to: 'b', gate: { type: 'none' } }],
};

const reset = () =>
  usePipelineStore.setState({ nodes: [], edges: [], steps: {}, phases: [] });

const load = () => usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });

describe('pipeline store', () => {
  beforeEach(reset);

  it('loads a pipeline into flow state', () => {
    load();

    expect(usePipelineStore.getState().nodes).toHaveLength(2);
    expect(usePipelineStore.getState().edges).toHaveLength(1);
  });

  it('round-trips back to a DTO', () => {
    load();

    expect(usePipelineStore.getState().toDTO()).toEqual(DTO);
  });

  it('adds a palette step at the drop position', () => {
    usePipelineStore.getState().setCatalogue([STEP], ['discovery']);

    usePipelineStore.getState().addStepNode(STEP, { x: 50, y: 60 });

    const node = usePipelineStore.getState().nodes[0];
    expect(node.position).toEqual({ x: 50, y: 60 });
    expect(node.data.label).toBe('Document Ingestion');
  });

  it('gives a second copy of the same step a distinct id', () => {
    usePipelineStore.getState().addStepNode(STEP, { x: 0, y: 0 });
    usePipelineStore.getState().addStepNode(STEP, { x: 20, y: 20 });

    const ids = usePipelineStore.getState().nodes.map((n) => n.id);
    expect(ids).toEqual(['doc-ingest', 'doc-ingest-2']);
    expect(new Set(ids).size).toBe(2);
  });

  it('onConnect adds an edge with the default gate', () => {
    load();
    usePipelineStore.setState({ edges: [] });

    usePipelineStore.getState().onConnect({
      source: 'a', target: 'b', sourceHandle: null, targetHandle: null,
    });

    const edge = usePipelineStore.getState().edges[0];
    expect(edge.id).toBe('a__b');
    expect(edge.data?.gate).toEqual({ type: 'none' });
    expect(edge.type).toBe('gate');
  });

  it('onNodesChange replaces objects rather than mutating them', () => {
    // React Flow's change detection is reference-based.
    load();
    const before = usePipelineStore.getState().nodes[0];

    usePipelineStore.getState().onNodesChange([
      { id: 'a', type: 'position', position: { x: 99, y: 99 } },
    ]);

    const after = usePipelineStore.getState().nodes[0];
    expect(after).not.toBe(before);
    expect(after.position).toEqual({ x: 99, y: 99 });
    expect(before.position).toEqual({ x: 0, y: 0 });
  });

  it('onEdgesChange can remove an edge', () => {
    load();

    usePipelineStore.getState().onEdgesChange([{ id: 'a__b', type: 'remove' }]);

    expect(usePipelineStore.getState().edges).toHaveLength(0);
  });

  it('setCatalogue stores the steps the palette and canvas share', () => {
    usePipelineStore.getState().setCatalogue([STEP], ['discovery', 'design']);

    expect(usePipelineStore.getState().steps['doc-ingest'].label).toBe('Document Ingestion');
    expect(usePipelineStore.getState().phases).toEqual(['discovery', 'design']);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `../flowTypes`, `./store`

- [ ] **Step 3: Write the components**

`src/nodes/StepNode.tsx`:

```tsx
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import type { FlowNode } from '../graph';

export default function StepNode({ id, data, selected }: NodeProps<FlowNode>) {
  return (
    <div
      className={`step-node${data.available ? '' : ' step-node--planned'}`}
      data-selected={selected || undefined}
    >
      <Handle type="target" position={Position.Left} className="port" />

      {/* The stripe is inert in this phase; Phase 8 tints it by run state. */}
      <div className="step-node__stripe" />

      <div className="step-node__body">
        <div className="step-node__top">
          <span className="step-node__name">{data.label}</span>
          {data.interactive && (
            <span className="step-node__badge"
                  title="Interactive - asks questions during the run">?</span>
          )}
          {!data.available && (
            <span className="step-node__badge"
                  title="Planned - this skill is not implemented yet">!</span>
          )}
          <span className="step-node__id">{id}</span>
        </div>
        <div className="step-node__phase">{data.phase}</div>
      </div>

      <Handle type="source" position={Position.Right} className="port" />
    </div>
  );
}
```

`src/edges/GateEdge.tsx` — a path only. The chip arrives in Phase 6:

```tsx
import { BaseEdge, getSmoothStepPath } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';
import type { FlowEdge } from '../graph';

export default function GateEdge({ id, ...props }: EdgeProps<FlowEdge>) {
  const [edgePath] = getSmoothStepPath(props);
  return <BaseEdge id={id} path={edgePath} />;
}
```

`src/flowTypes.ts`:

```ts
/**
 * Module scope is load-bearing. Building these objects inside a component
 * remounts every node on each render, destroying focus and DOM state, and
 * triggers React Flow's "you have created a new nodeTypes object" warning.
 */
import GateEdge from './edges/GateEdge';
import StepNode from './nodes/StepNode';

export const nodeTypes = { step: StepNode };
export const edgeTypes = { gate: GateEdge };
```

- [ ] **Step 4: Write `store.ts`**

```ts
/**
 * Zustand store for graph state.
 *
 * Zustand rather than useNodesState because the save action - and, from Phase 9,
 * the WebSocket - must reach graph state from outside the React tree. Every
 * update returns new objects: React Flow's change detection is reference-based.
 */
import { addEdge, applyEdgeChanges, applyNodeChanges } from '@xyflow/react';
import type { Connection, EdgeChange, NodeChange } from '@xyflow/react';
import { create } from 'zustand';
import { DEFAULT_GATE, edgeId, fromFlow, makeNode, toFlow } from './graph';
import type { FlowEdge, FlowNode } from './graph';
import type { PipelineDTO, StepDef } from './types';

interface PipelineState {
  nodes: FlowNode[];
  edges: FlowEdge[];
  steps: Record<string, StepDef>;
  phases: string[];

  onNodesChange: (changes: NodeChange<FlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<FlowEdge>[]) => void;
  onConnect: (connection: Connection) => void;
  addStepNode: (step: StepDef, position: { x: number; y: number }) => void;
  setCatalogue: (steps: StepDef[], phases: string[]) => void;
  loadFrom: (dto: PipelineDTO, steps: Record<string, StepDef>) => void;
  toDTO: () => PipelineDTO;
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  nodes: [],
  edges: [],
  steps: {},
  phases: [],

  onNodesChange: (changes) => set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) => set({ edges: applyEdgeChanges(changes, get().edges) }),

  onConnect: (connection) =>
    set({
      edges: addEdge(
        {
          ...connection,
          id: edgeId(connection.source!, connection.target!),
          type: 'gate',
          data: { gate: DEFAULT_GATE },
        },
        get().edges,
      ),
    }),

  addStepNode: (step, position) =>
    set({ nodes: [...get().nodes, makeNode(step, position, get().nodes.map((n) => n.id))] }),

  setCatalogue: (steps, phases) =>
    set({ steps: Object.fromEntries(steps.map((s) => [s.id, s])), phases }),

  loadFrom: (dto, steps) => {
    const { nodes, edges } = toFlow(dto, steps);
    set({ nodes, edges, steps });
  },

  toDTO: () => fromFlow(get().nodes, get().edges),
}));
```

- [ ] **Step 5: Add the styles**

Append to `app.css` — tokens only:

```css
.step-node {
  width: 196px; background: var(--raised); color: var(--text);
  border: 1px solid var(--hair); border-radius: var(--r-md);
  box-shadow: var(--shadow-1); overflow: hidden; cursor: pointer;
  transition: border-color var(--t), box-shadow var(--t);
}
.step-node:hover { border-color: var(--text-faint); box-shadow: var(--shadow-2); }
.step-node[data-selected] { border-color: var(--cyan); box-shadow: 0 0 0 3px var(--cyan-sunk); }
.step-node--planned { border-style: dashed; }

.step-node__stripe { height: 3px; background: var(--st-pending); }
.step-node__body { padding: .5rem .625rem .55rem; display: flex; flex-direction: column; gap: .25rem; }
.step-node__top { display: flex; align-items: flex-start; gap: .4rem; }
.step-node__name { font-size: 12.5px; font-weight: 700; letter-spacing: -.01em; line-height: 1.25; }
.step-node__id {
  font-family: var(--mono); font-size: 9.5px; color: var(--text-faint);
  margin-left: auto; flex: none; padding-top: 1px;
}
.step-node__badge {
  font-family: var(--mono); font-size: 9px;
  border: 1px solid currentColor; border-radius: 999px;
  width: 14px; height: 14px; display: grid; place-items: center;
  opacity: .7; flex: none;
}
.step-node__phase {
  font-family: var(--mono); font-size: 9px; text-transform: uppercase;
  letter-spacing: .08em; color: var(--text-faint);
}

.port {
  width: 8px; height: 8px; border-radius: 999px;
  background: var(--edge); border: 2px solid var(--surface);
}

.stagebar {
  position: sticky; top: 0; z-index: 6;
  display: flex; align-items: center; gap: .4rem; flex-wrap: wrap;
  padding: .55rem .625rem;
  background: color-mix(in srgb, var(--sunk) 88%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--hair-soft);
}
.btn {
  border: 1px solid var(--hair); background: var(--raised);
  cursor: pointer; font-size: 12.5px; font-weight: 600;
  padding: .44rem .75rem; border-radius: var(--r-sm);
  transition: border-color var(--t), background var(--t);
  white-space: nowrap;
}
.btn:hover { border-color: var(--text-faint); }
.btn--primary { background: var(--bone); color: var(--bone-ink); border-color: var(--bone); }
.btn--ghost { background: none; color: var(--text-soft); }
.btn[disabled] { opacity: .4; cursor: not-allowed; }

.hint {
  font-size: 11.5px; color: var(--text-faint);
  margin-left: auto; display: flex; align-items: center; gap: .35rem;
}
.flowwrap { position: absolute; inset: 0; padding-top: 42px; }
```

- [ ] **Step 6: Run and commit**

```bash
cd studio/frontend && npm test
git add studio/frontend/src
git commit -m "feat(studio): node card, gate edge, and the graph store"
```

---

### Task 5: Canvas, drag-and-drop, and Save

**Files:**
- Modify: `studio/frontend/src/App.tsx`, `src/api.ts`, `src/panels/Palette.tsx`
- Test: `src/App.test.tsx` (extend), `src/panels/Palette.test.tsx` (extend)

**Interfaces:**
- Produces:
  - `api.getPipeline()`, `api.putPipeline(dto)`.
  - `Palette` gains `draggable` on available steps and an `onDragStart` prop.
  - `App` renders `<ReactFlow>` inside `ReactFlowProvider`, handles drop, and wires Save.

- [ ] **Step 1: Extend the tests**

Add to `src/panels/Palette.test.tsx`:

```tsx
  it('makes an available step draggable', () => {
    render(<Palette steps={steps} phases={phases} onDragStart={vi.fn()} />);

    expect(screen.getByText('Document Ingestion').closest('[draggable]'))
      .toHaveAttribute('draggable', 'true');
  });

  it('does not make an unimplemented step draggable', () => {
    render(<Palette steps={steps} phases={phases} onDragStart={vi.fn()} />);

    expect(screen.getByText('Security Checks').closest('.chip-step'))
      .toHaveAttribute('draggable', 'false');
  });

  it('reports the step id on drag start', () => {
    const onDragStart = vi.fn();
    render(<Palette steps={steps} phases={phases} onDragStart={onDragStart} />);

    const item = screen.getByText('Document Ingestion').closest('.chip-step')!;
    // jsdom has no dataTransfer, so pass a stub - the handler must tolerate it.
    fireEvent.dragStart(item, { dataTransfer: { setData: vi.fn(), effectAllowed: '' } });

    expect(onDragStart).toHaveBeenCalledWith(expect.anything(), 'doc-ingest');
  });
```

Add to `src/App.test.tsx`:

```tsx
  it('loads the saved pipeline onto the canvas', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url === '/api/health') return Promise.resolve({ ok: true, json: () => Promise.resolve(ok) });
      if (url === '/api/registry') return Promise.resolve({
        ok: true, json: () => Promise.resolve({ steps: [STEP], phases: ['discovery'], tiers: [] }),
      });
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          exists: true,
          pipeline: { version: 1, nodes: [
            { id: 'a', step: 'doc-ingest', args: [], position: { x: 0, y: 0 } }], edges: [] },
        }),
      });
    });

    render(<App />);

    await waitFor(() => expect(usePipelineStore.getState().nodes).toHaveLength(1));
  });

  it('Save PUTs the current graph', async () => {
    /* ...same fetch router, then: */
    render(<App />);
    await waitFor(() => expect(usePipelineStore.getState().nodes).toHaveLength(1));

    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    const put = (fetch as ReturnType<typeof vi.fn>).mock.calls
      .find(([, init]) => (init as RequestInit)?.method === 'PUT');
    expect(put).toBeTruthy();
    expect(JSON.parse((put![1] as RequestInit).body as string).nodes[0].id).toBe('a');
  });

  it('disables Save while a save is in flight', async () => {
    /* assert the button is disabled between click and resolution */
  });
```

- [ ] **Step 2: Add the pipeline calls to `api.ts`**

```ts
import type { PipelineDTO } from './types';

export const getPipeline = () =>
  request<{ pipeline: PipelineDTO; exists: boolean }>('/pipeline');

export const putPipeline = (dto: PipelineDTO) =>
  request<{ pipeline: PipelineDTO; exists: boolean }>(
    '/pipeline', { method: 'PUT', body: JSON.stringify(dto) });
```

- [ ] **Step 3: Make the palette draggable**

Add the `onDragStart` prop and, on each available item:

```tsx
                draggable={step.available}
                onDragStart={(e) => step.available && onDragStart(e, step.id)}
```

- [ ] **Step 4: Wire the canvas into `App.tsx`**

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Background, Controls, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow,
} from '@xyflow/react';
import * as api from './api';
import { edgeTypes, nodeTypes } from './flowTypes';
import Palette from './panels/Palette';
import { usePipelineStore } from './store';
import { checkHealth } from './health';
import type { HealthState } from './health';

function Studio() {
  const store = usePipelineStore();
  const { screenToFlowPosition } = useReactFlow();
  const [health, setHealth] = useState<HealthState | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const dragged = useRef<string | null>(null);

  /* health poll - unchanged from Phase 0 */

  useEffect(() => {
    void (async () => {
      try {
        const registry = await api.getRegistry();
        usePipelineStore.getState().setCatalogue(registry.steps, registry.phases);
        const byId = Object.fromEntries(registry.steps.map((s) => [s.id, s]));
        const { pipeline } = await api.getPipeline();
        usePipelineStore.getState().loadFrom(pipeline, byId);
      } catch (e) {
        setMessage(String(e));
      }
    })();
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      // dataTransfer is unimplemented in jsdom, so a ref carries the id too.
      const stepId = dragged.current ?? event.dataTransfer.getData('text/plain');
      const step = usePipelineStore.getState().steps[stepId ?? ''];
      if (!step) return;
      usePipelineStore.getState().addStepNode(
        step, screenToFlowPosition({ x: event.clientX, y: event.clientY }));
      dragged.current = null;
    },
    [screenToFlowPosition],
  );

  const onSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await api.putPipeline(usePipelineStore.getState().toDTO());
      setMessage('Saved.');
    } catch (e) {
      setMessage(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="layout">
      {/* app bar - unchanged, plus nothing new */}

      <Palette
        steps={Object.values(store.steps)}
        phases={store.phases}
        onDragStart={(event, stepId) => {
          dragged.current = stepId;
          event.dataTransfer?.setData('text/plain', stepId);
          if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
        }}
      />

      <div
        className="stage"
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}
      >
        <div className="stagebar">
          <button className="btn btn--primary" onClick={onSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
          {message && <span className="hint">{message}</span>}
          <span className="hint">drag a step from the left</span>
        </div>

        <div className="flowwrap">
          <ReactFlow
            nodes={store.nodes}
            edges={store.edges}
            onNodesChange={store.onNodesChange}
            onEdgesChange={store.onEdgesChange}
            onConnect={store.onConnect}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            colorMode="dark"
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
      </div>

      <aside className="aside">
        <p className="placeholder">Pipeline health arrives in Phase 3.</p>
      </aside>
    </div>
  );
}

export default function App() {
  // useReactFlow (for screenToFlowPosition) must be called below the provider.
  return (
    <ReactFlowProvider>
      <Studio />
    </ReactFlowProvider>
  );
}
```

`colorMode="dark"` is explicit rather than `"system"`: dark is the product default, and
React Flow's own controls must match the console rather than the OS.

- [ ] **Step 5: Run, build, commit**

```bash
cd studio/frontend && npm test && npm run build
git add studio/frontend/src
git commit -m "feat(studio): canvas, drag-and-drop, and save"
```

---

### Task 6: Run the demo

- [ ] **Step 1: Both processes up**

```bash
cd studio/backend && implr-studio --workspace /tmp/studio-probe    # terminal 1
cd studio/frontend && npm run dev                                   # terminal 2
```

- [ ] **Step 2: Drag, connect, save**

1. Drag **Document Ingestion** onto the canvas. A card appears **where you dropped it** —
   if it lands at the top-left corner instead, `screenToFlowPosition` is missing.
2. Drag **Architecture Brief** to its right. It carries an `?` badge.
3. Drag from the first card's **right** port to the second's **left** port. An edge appears.
4. Press **Save**. The hint reads *Saved.*

```bash
cat /tmp/studio-probe/docs/implr/config/pipeline.yaml
```

Expected: `from:`/`to:` keys, real positions, `gate: {type: none}`.

- [ ] **Step 3: Confirm persistence**

Reload the browser. Both nodes and the edge return at the same positions. Drag them
somewhere new, Save, reload — the new positions persist.

- [ ] **Step 4: Confirm the id generator**

Drag a **third** Document Ingestion on. Its id badge reads `doc-ingest-2`. A fourth reads
`doc-ingest-3`.

- [ ] **Step 5: Confirm an unimplemented step cannot be dragged**

Try to drag **Security Checks**. Nothing happens — it is `draggable={false}`.

- [ ] **Step 6: Confirm a corrupt file is survivable**

```bash
echo "version: 1
nodes: [unclosed" > /tmp/studio-probe/docs/implr/config/pipeline.yaml
```

Reload the browser. The right rail shows a parse error rather than a blank page or a spinner
that never ends. Restore a good file by pressing Save.

- [ ] **Step 7: Confirm validation is genuinely absent**

Build a cycle: connect A→B and B→A. Press Save. It **succeeds** — that is correct for this
phase. Phase 3 is what refuses it, and this is the before-state its demo contrasts with.

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes.
- [ ] `npm test` and `npm run build` pass.
- [ ] `python -m pytest tests/` at the repo root still passes.
- [ ] `PYTHONPATH=scripts python -m implr_validate --repo --root .` exits `0`.
- [ ] `graph.fromFlow` emits exactly `id`, `step`, `args`, `position` per node — no
      `selected`, `dragging`, `measured`, `width`, `height` or `label` — proven by test.
- [ ] `toFlow` → `fromFlow` round-trips a pipeline unchanged, positions included.
- [ ] `nodeTypes` and `edgeTypes` are module-scope constants.
- [ ] A missing `pipeline.yaml` returns `exists: false` with an empty pipeline, never a 404.
- [ ] A rejected `PUT` leaves no file on disk.
- [ ] A corrupt `pipeline.yaml` surfaces as a `parse-error` finding, not a 500.
- [ ] **The demo:** drag two steps, connect them, Save, `pipeline.yaml` on disk with
      `from`/`to` keys and real positions; reload restores the graph; a third copy of a step
      becomes `-2`.

---

## What the next phase gets

A canvas that saves anything. Phase 3 adds `validate_pipeline`, merges its findings into the
422 envelope this phase built, and turns the right rail into a health panel — so its demo is
*"make a cycle, Save, and see it named and refused"*.
