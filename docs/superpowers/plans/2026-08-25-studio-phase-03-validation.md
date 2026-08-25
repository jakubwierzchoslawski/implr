# implr Studio — Phase 3: Refuse bad graphs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cycle, press Save, and see it refused with the cycle named — in the UI, with nothing written to disk. The right rail becomes a health panel showing what is wrong and where.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phases 0–2.

---

## Demo

Both processes up, a graph on the canvas. Connect A→B **and** B→A, then press **Save**.

The right rail turns red:

```
2 ISSUES
  pipeline contains a cycle involving: arch-gen, doc-ingest
  pipeline has no starting node (every node has a dependency)
```

Both offending nodes get a red outline on the canvas. The file on disk is **unchanged** —
`cat` it and the last good version is still there.

Delete one edge, Save again: the rail goes quiet and reads **No issues**. Now drag on a step
and leave it unconnected while the rest of the graph is a chain: the rail reports
`node X cannot be reached from any starting node` and outlines only that node.

---

## Scope boundary — not in this phase

**Structural validation only.** The rules are about the *graph*: does the step exist, is the
arg allowed, is there a cycle, is every node reachable, is there a root. Nothing about gate
semantics — an `artifact` gate naming a nonexistent artefact type still saves. That is
Phase 6, which adds `gates.validate_gate` and merges its findings into the same list.

No configurator, no gate editor, no runs. Arg validation here is only membership — is this
flag in `args_allowed` — because nothing can *select* a flag until Phase 4. Value rules
arrive with the value fields.

---

## Tech Stack

Python 3.11+. React + TypeScript, Zustand, Vitest. No new dependencies.

## Global Constraints

- Validation runs in the **backend**, not the frontend, so the same rules apply whether the
  file was written by the builder or edited by hand. The UI renders findings; it does not
  compute them.
- Step **availability is deliberately not checked**. A pipeline may reference a
  registered-but-unimplemented step at design time — that is the whole point of the dashed
  palette items. Run-start enforcement arrives in Phase 9.
- A rejected save writes nothing. Validate, then write, never the reverse.
- Findings carry a machine-readable `code` as well as a message, so the UI can outline the
  right node without parsing prose.
- Colours from tokens only. `--st-failed` is the finding colour; it is already reserved.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/backend/implr_studio/pipeline.py` | **Modified** — appends `Finding` and `validate_pipeline`. |
| `studio/backend/implr_studio/serialize.py` | **Modified** — `finding_to_dict`. |
| `studio/backend/implr_studio/api.py` | **Modified** — `PUT` validates before writing. |
| `studio/frontend/src/store.ts` | **Modified** — `findings`, `setFindings`. |
| `studio/frontend/src/panels/HealthPanel.tsx` | The right rail: counts and findings. |
| `studio/frontend/src/nodes/StepNode.tsx` | **Modified** — a `--invalid` outline. |
| `studio/frontend/src/App.tsx` | **Modified** — catch `ValidationError`, feed the store. |

---

### Task 1: Graph validation

**Files:**
- Modify: `studio/backend/implr_studio/pipeline.py`
- Test: `studio/backend/tests/test_pipeline_validation.py`

**Interfaces:**
- Produces:
  - `pipeline.Finding` — frozen: `code: str`, `message: str`, `node_id: str | None = None`.
  - `pipeline.validate_pipeline(p, reg) -> list[Finding]` — empty list means valid to save.

`reg` is a `registry.Registry`, left **unannotated** so `pipeline.py` needs no import of
`registry.py` purely for a type hint. It is duck-typed on `.get(step_id)`, which also makes
the validator trivial to test with a stub.

Finding codes, which later phases and the frontend both depend on: `unknown-step`,
`disallowed-arg`, `duplicate-node-id`, `unknown-edge-node`, `cycle`, `unreachable-node`,
`no-root`.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_pipeline_validation.py`:

```python
import json
from pathlib import Path

import pytest

from implr_studio import pipeline, registry


@pytest.fixture
def reg(tmp_path: Path) -> registry.Registry:
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    schema_dir.mkdir(parents=True)
    steps = [
        {"id": step_id, "kind": "skill", "label": step_id, "phase": "discovery",
         "skill": step_id,
         "args_allowed": [
             {"flag": "--dry-run", "takes_value": False, "note": ""},
             {"flag": "--all", "takes_value": False, "note": ""},
         ],
         "args_default": [], "interactive": False,
         "agents": [], "consumes": [], "produces": [], "produces_artefact": None,
         "description": ""}
        for step_id in ("doc-ingest", "arch-gen", "sec-review")
    ]
    (schema_dir / "step-registry.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    for skill in ("doc-ingest", "arch-gen"):        # sec-review intentionally missing
        (skills_dir / skill).mkdir(parents=True)
        (skills_dir / skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return registry.load_registry(schema_dir, skills_dir)


def _p(nodes, edges) -> pipeline.Pipeline:
    return pipeline.pipeline_from_dict({"version": 1, "nodes": nodes, "edges": edges})


def _codes(findings) -> list[str]:
    return [f.code for f in findings]


# --- valid shapes ----------------------------------------------------------

def test_valid_pipeline_has_no_findings(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
           [{"from": "a", "to": "b"}])

    assert pipeline.validate_pipeline(p, reg) == []


def test_single_node_pipeline_is_valid(reg):
    assert pipeline.validate_pipeline(_p([{"id": "a", "step": "doc-ingest"}], []), reg) == []


def test_empty_pipeline_is_valid(reg):
    """An empty canvas is a legal thing to save while designing."""
    assert pipeline.validate_pipeline(_p([], []), reg) == []


def test_a_diamond_is_valid(reg):
    """Branch and join: the graph is a DAG, not a chain."""
    p = _p(
        [{"id": n, "step": "arch-gen"} for n in ("a", "b", "c", "d")],
        [{"from": "a", "to": "b"}, {"from": "a", "to": "c"},
         {"from": "b", "to": "d"}, {"from": "c", "to": "d"}],
    )

    assert pipeline.validate_pipeline(p, reg) == []


def test_registered_but_unavailable_step_is_accepted(reg):
    """Designing ahead of implementation is allowed; run start enforces availability."""
    assert pipeline.validate_pipeline(_p([{"id": "a", "step": "sec-review"}], []), reg) == []


# --- node rules ------------------------------------------------------------

def test_unknown_step_rejected(reg):
    findings = pipeline.validate_pipeline(_p([{"id": "a", "step": "does-not-exist"}], []), reg)

    assert _codes(findings) == ["unknown-step"]
    assert "does-not-exist" in findings[0].message
    assert findings[0].node_id == "a"


def test_disallowed_arg_rejected(reg):
    findings = pipeline.validate_pipeline(
        _p([{"id": "a", "step": "doc-ingest", "args": ["--wat"]}], []), reg)

    assert _codes(findings) == ["disallowed-arg"]
    assert "--wat" in findings[0].message
    assert "--dry-run" in findings[0].message      # names what IS allowed


def test_allowed_arg_accepted(reg):
    p = _p([{"id": "a", "step": "doc-ingest", "args": ["--dry-run", "--all"]}], [])

    assert pipeline.validate_pipeline(p, reg) == []


def test_duplicate_node_id_rejected(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}, {"id": "a", "step": "arch-gen"}], [])

    assert "duplicate-node-id" in _codes(pipeline.validate_pipeline(p, reg))


def test_edge_referencing_unknown_node_rejected(reg):
    findings = pipeline.validate_pipeline(
        _p([{"id": "a", "step": "doc-ingest"}], [{"from": "a", "to": "ghost"}]), reg)

    assert "unknown-edge-node" in _codes(findings)
    assert any("ghost" in f.message for f in findings)


# --- graph rules -----------------------------------------------------------

def test_cycle_rejected(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
           [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}])

    findings = pipeline.validate_pipeline(p, reg)

    assert "cycle" in _codes(findings)
    cycle = next(f for f in findings if f.code == "cycle")
    assert "a" in cycle.message and "b" in cycle.message


def test_self_loop_is_a_cycle(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}], [{"from": "a", "to": "a"}])

    assert "cycle" in _codes(pipeline.validate_pipeline(p, reg))


def test_three_node_cycle_names_all_three(reg):
    p = _p([{"id": n, "step": "arch-gen"} for n in ("a", "b", "c")],
           [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "a"}])

    cycle = next(f for f in pipeline.validate_pipeline(p, reg) if f.code == "cycle")

    for name in ("a", "b", "c"):
        assert name in cycle.message


def test_no_root_reported(reg):
    """Every node having an inbound edge means nothing can start."""
    p = _p([{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
           [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}])

    assert "no-root" in _codes(pipeline.validate_pipeline(p, reg))


def test_unreachable_node_reported(reg):
    """An island with no path from any root can never run."""
    p = _p(
        [{"id": n, "step": "arch-gen"} for n in ("a", "b", "c", "d")],
        [{"from": "a", "to": "b"}, {"from": "c", "to": "d"}, {"from": "d", "to": "c"}],
    )

    unreachable = [f for f in pipeline.validate_pipeline(p, reg) if f.code == "unreachable-node"]

    assert {f.node_id for f in unreachable} == {"c", "d"}


def test_a_lone_disconnected_node_is_reachable(reg):
    """It is its own root. Only a node behind a cycle is unreachable."""
    p = _p([{"id": "a", "step": "doc-ingest"}, {"id": "island", "step": "arch-gen"}], [])

    assert pipeline.validate_pipeline(p, reg) == []


def test_findings_carry_the_node_they_belong_to(reg):
    """The UI outlines nodes by id rather than parsing the message."""
    p = _p([{"id": "bad", "step": "nope"}], [])

    assert pipeline.validate_pipeline(p, reg)[0].node_id == "bad"


def test_multiple_problems_all_reported(reg):
    """One save should surface every problem, not just the first."""
    p = _p([{"id": "a", "step": "nope"}, {"id": "b", "step": "doc-ingest", "args": ["--wat"]}],
           [{"from": "b", "to": "ghost"}])

    codes = set(_codes(pipeline.validate_pipeline(p, reg)))

    assert {"unknown-step", "disallowed-arg", "unknown-edge-node"} <= codes


def test_a_large_chain_does_not_blow_the_stack(reg):
    """Cycle detection is iterative, not recursive."""
    nodes = [{"id": "n%d" % i, "step": "arch-gen"} for i in range(2000)]
    edges = [{"from": "n%d" % i, "to": "n%d" % (i + 1)} for i in range(1999)]

    assert pipeline.validate_pipeline(_p(nodes, edges), reg) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_pipeline_validation.py -v`
Expected: FAIL — `AttributeError: module 'implr_studio.pipeline' has no attribute 'validate_pipeline'`

- [ ] **Step 3: Append to `pipeline.py`**

```python
@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    node_id: str | None = None


def _find_cycle_nodes(node_ids: set[str], edges) -> set[str]:
    """Return every node that participates in a cycle.

    Iterative DFS with three-colour marking. Iterative rather than recursive so a
    long chain cannot blow the stack - a pipeline is operator-authored data and
    its depth is not bounded by anything we control.
    """
    adjacency: dict[str, list[str]] = {n: [] for n in node_ids}
    for e in edges:
        if e.source in adjacency and e.target in node_ids:
            adjacency[e.source].append(e.target)

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in node_ids}
    in_cycle: set[str] = set()

    for start in sorted(node_ids):
        if colour[start] != WHITE:
            continue
        stack = [(start, iter(adjacency[start]))]
        path = [start]
        colour[start] = GREY
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                if colour[child] == GREY:
                    # Everything from `child` to the top of `path` is in the cycle.
                    in_cycle.update(path[path.index(child):])
                    continue
                if colour[child] == WHITE:
                    colour[child] = GREY
                    path.append(child)
                    stack.append((child, iter(adjacency[child])))
                    advanced = True
                    break
            if not advanced:
                colour[node] = BLACK
                stack.pop()
                path.pop()
    return in_cycle


def validate_pipeline(p: Pipeline, reg) -> list[Finding]:
    """Return findings; an empty list means the pipeline is valid to save.

    Step *availability* is deliberately not checked: designing ahead of a skill's
    implementation is permitted, and run start enforces availability instead.

    `reg` is duck-typed on .get(step_id) so this module needs no import of
    registry.py for a type hint - and so the validator is trivial to stub.
    """
    findings: list[Finding] = []

    seen: set[str] = set()
    for node in p.nodes:
        if node.id in seen:
            findings.append(Finding(
                "duplicate-node-id", "duplicate node id: %s" % node.id, node.id))
            continue
        seen.add(node.id)

        step = reg.get(node.step)
        if step is None:
            findings.append(Finding(
                "unknown-step", "node %s: unknown step %r" % (node.id, node.step), node.id))
            continue

        for arg in node.args:
            if arg not in step.flags:
                findings.append(Finding(
                    "disallowed-arg",
                    "node %s: arg %r not allowed for step %s (allowed: %s)"
                    % (node.id, arg, node.step, list(step.flags)),
                    node.id,
                ))

    node_ids = seen
    for e in p.edges:
        for end in (e.source, e.target):
            if end not in node_ids:
                findings.append(Finding(
                    "unknown-edge-node",
                    "edge %s -> %s references unknown node %r" % (e.source, e.target, end),
                    end,
                ))

    live_edges = [e for e in p.edges if e.source in node_ids and e.target in node_ids]

    cycle_nodes = _find_cycle_nodes(node_ids, live_edges)
    if cycle_nodes:
        findings.append(Finding(
            "cycle",
            "pipeline contains a cycle involving: %s" % ", ".join(sorted(cycle_nodes)),
        ))

    if node_ids:
        has_inbound = {e.target for e in live_edges}
        roots = node_ids - has_inbound
        if not roots:
            findings.append(Finding(
                "no-root", "pipeline has no starting node (every node has a dependency)"))
        else:
            adjacency: dict[str, list[str]] = {n: [] for n in node_ids}
            for e in live_edges:
                adjacency[e.source].append(e.target)
            reached: set[str] = set()
            queue = list(roots)
            while queue:
                current = queue.pop()
                if current in reached:
                    continue
                reached.add(current)
                queue.extend(adjacency[current])
            for orphan in sorted(node_ids - reached):
                findings.append(Finding(
                    "unreachable-node",
                    "node %s cannot be reached from any starting node" % orphan,
                    orphan,
                ))

    return findings
```

A cycle produces **two** findings — `cycle` and `no-root` — when it swallows the whole
graph. That is correct and worth keeping: they are different facts, and a graph can have a
cycle *and* a valid root elsewhere.

- [ ] **Step 4: Run and commit**

Run: `cd studio/backend && python -m pytest tests/test_pipeline_validation.py -v`

```bash
git add studio/backend/implr_studio/pipeline.py studio/backend/tests/test_pipeline_validation.py
git commit -m "feat(studio): DAG validation for pipeline configs"
```

---

### Task 2: Validate before writing

**Files:**
- Modify: `studio/backend/implr_studio/serialize.py`, `api.py`
- Test: `studio/backend/tests/test_api_pipeline.py` (extend)

**Interfaces:**
- Produces:
  - `serialize.finding_to_dict(f) -> dict` → `{"code", "message", "node_id"}`
  - `PUT /api/pipeline` returns `422` with `{"findings": [...]}` when validation fails, and
    writes nothing.

- [ ] **Step 1: Extend the test**

Add to `studio/backend/tests/test_api_pipeline.py`:

```python
def test_put_rejects_a_cycle_with_422_and_findings(client):
    bad = dict(VALID, edges=[
        {"from": "ingest", "to": "arch"}, {"from": "arch", "to": "ingest"}])

    r = client.put("/api/pipeline", json=bad)

    assert r.status_code == 422
    codes = [f["code"] for f in r.json()["findings"]]
    assert "cycle" in codes
    assert "no-root" in codes


def test_put_rejects_an_unknown_step(client):
    bad = dict(VALID, nodes=[{"id": "x", "step": "not-a-step", "args": [],
                              "position": {"x": 0, "y": 0}}], edges=[])

    r = client.put("/api/pipeline", json=bad)

    assert r.status_code == 422
    assert [f["code"] for f in r.json()["findings"]] == ["unknown-step"]


def test_put_rejects_a_disallowed_arg(client):
    bad = dict(VALID, nodes=[{"id": "x", "step": "doc-ingest", "args": ["--wat"],
                              "position": {"x": 0, "y": 0}}], edges=[])

    r = client.put("/api/pipeline", json=bad)

    assert r.status_code == 422
    assert [f["code"] for f in r.json()["findings"]] == ["disallowed-arg"]


def test_findings_carry_the_node_id(client):
    bad = dict(VALID, nodes=[{"id": "culprit", "step": "nope", "args": [],
                              "position": {"x": 0, "y": 0}}], edges=[])

    findings = client.put("/api/pipeline", json=bad).json()["findings"]

    assert findings[0]["node_id"] == "culprit"


def test_a_rejected_put_does_not_overwrite_a_good_file(client, workspace):
    """The previous save must survive a failed one."""
    client.put("/api/pipeline", json=VALID)
    path = workspace / "docs" / "implr" / "config" / "pipeline.yaml"
    before = path.read_text(encoding="utf-8")

    client.put("/api/pipeline", json=dict(VALID, nodes=[
        {"id": "x", "step": "nope", "args": [], "position": {"x": 0, "y": 0}}], edges=[]))

    assert path.read_text(encoding="utf-8") == before


def test_put_accepts_a_registered_but_unimplemented_step(client):
    """Designing ahead of implementation is allowed. Run start enforces availability."""
    ahead = dict(VALID, nodes=[{"id": "sec", "step": "sec-review", "args": [],
                                "position": {"x": 0, "y": 0}}], edges=[])

    assert client.put("/api/pipeline", json=ahead).status_code == 200


def test_put_still_accepts_an_unvalidated_gate(client):
    """Gate semantics are Phase 6. A structurally-valid gate saves for now."""
    gated = dict(VALID, edges=[{
        "from": "ingest", "to": "arch",
        "gate": {"type": "artifact", "artefact": "unicorn",
                 "quantifier": "all", "require": {"status": "approved"}}}])

    assert client.put("/api/pipeline", json=gated).status_code == 200
```

> The last test is a **scope marker**, not an endorsement. Phase 6 replaces it with one
> asserting `unknown-artefact-type`. Leaving it here makes the boundary explicit, so a future
> reader does not mistake the gap for an oversight.

- [ ] **Step 2: Add `finding_to_dict`**

In `serialize.py`:

```python
from .pipeline import Finding


def finding_to_dict(f: Finding) -> dict:
    return {"code": f.code, "message": f.message, "node_id": f.node_id}
```

- [ ] **Step 3: Validate in the route**

In `api.py`, import `validate_pipeline`, then replace the Phase 2 comment placeholder:

```python
    @app.put("/api/pipeline")
    def put_pipeline(body: dict = Body(...)) -> dict:
        try:
            p = pipeline_from_dict(body)
        except PipelineError as e:
            raise HTTPException(422, detail=_findings("parse-error", str(e)))

        findings = [serialize.finding_to_dict(f)
                    for f in validate_pipeline(p, context.registry)]
        # Phase 6 appends gate findings to this list before the check.
        if findings:
            # Validate, then write. Never the reverse: a rejected save must leave
            # the previous good file untouched.
            raise HTTPException(422, detail={"findings": findings})

        save_pipeline(context.pipeline_path, p)
        return {"pipeline": pipeline_to_dict(p), "exists": True}
```

- [ ] **Step 4: Run the whole backend suite and commit**

Run: `cd studio/backend && python -m pytest -v`

```bash
git add studio/backend
git commit -m "feat(studio): validate the pipeline before writing it"
```

---

### Task 3: The health panel

**Files:**
- Create: `studio/frontend/src/panels/HealthPanel.tsx`
- Modify: `studio/frontend/src/store.ts`, `src/nodes/StepNode.tsx`, `src/App.tsx`, `src/app.css`
- Test: `src/panels/HealthPanel.test.tsx`, `src/store.test.ts` (extend)

**Interfaces:**
- Produces:
  - `store.findings: Finding[]`, `store.setFindings(findings)`, and `store.invalidNodeIds: () => Set<string>` derived from them.
  - `HealthPanel` — step / connection counts, and the findings list.
  - `StepNode` gains `data.invalid` driving a `step-node--invalid` outline.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/panels/HealthPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import HealthPanel from './HealthPanel';
import { usePipelineStore } from '../store';
import type { PipelineDTO, StepDef } from '../types';

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

beforeEach(() => {
  usePipelineStore.setState({ nodes: [], edges: [], steps: {}, phases: [], findings: [] });
  usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });
});

describe('HealthPanel', () => {
  it('counts steps and connections', () => {
    render(<HealthPanel />);

    expect(screen.getByText('Steps').nextSibling).toHaveTextContent('2');
    expect(screen.getByText('Connections').nextSibling).toHaveTextContent('1');
  });

  it('reports no issues on a clean graph', () => {
    render(<HealthPanel />);

    expect(screen.getByText(/no issues/i)).toBeInTheDocument();
  });

  it('lists each finding message', () => {
    usePipelineStore.getState().setFindings([
      { code: 'cycle', message: 'pipeline contains a cycle involving: a, b', node_id: null },
      { code: 'no-root', message: 'pipeline has no starting node', node_id: null },
    ]);

    render(<HealthPanel />);

    expect(screen.getByText(/2 issues/i)).toBeInTheDocument();
    expect(screen.getByText(/cycle involving: a, b/)).toBeInTheDocument();
    expect(screen.getByText(/no starting node/)).toBeInTheDocument();
  });

  it('uses the singular for one finding', () => {
    usePipelineStore.getState().setFindings([
      { code: 'unknown-step', message: 'node a: unknown step', node_id: 'a' },
    ]);

    render(<HealthPanel />);

    expect(screen.getByText(/1 issue$/i)).toBeInTheDocument();
  });

  it('names the node a finding belongs to', () => {
    usePipelineStore.getState().setFindings([
      { code: 'unreachable-node', message: 'node island cannot be reached', node_id: 'island' },
    ]);

    render(<HealthPanel />);

    expect(screen.getByText('island')).toBeInTheDocument();
  });
});
```

Add to `src/store.test.ts`:

```ts
  it('setFindings marks the nodes they belong to as invalid', () => {
    load();

    usePipelineStore.getState().setFindings([
      { code: 'unknown-step', message: 'nope', node_id: 'a' },
    ]);

    const nodes = usePipelineStore.getState().nodes;
    expect(nodes.find((n) => n.id === 'a')!.data.invalid).toBe(true);
    expect(nodes.find((n) => n.id === 'b')!.data.invalid).toBeFalsy();
  });

  it('clearing findings clears the invalid marks', () => {
    load();
    usePipelineStore.getState().setFindings([
      { code: 'unknown-step', message: 'nope', node_id: 'a' },
    ]);

    usePipelineStore.getState().setFindings([]);

    expect(usePipelineStore.getState().nodes.every((n) => !n.data.invalid)).toBe(true);
  });

  it('ignores a finding with no node_id when marking', () => {
    load();

    usePipelineStore.getState().setFindings([
      { code: 'no-root', message: 'no starting node', node_id: null },
    ]);

    expect(usePipelineStore.getState().nodes.every((n) => !n.data.invalid)).toBe(true);
  });

  it('a successful save clears stale findings', () => {
    load();
    usePipelineStore.getState().setFindings([
      { code: 'cycle', message: 'c', node_id: null },
    ]);

    usePipelineStore.getState().setFindings([]);

    expect(usePipelineStore.getState().findings).toEqual([]);
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `./HealthPanel`; `setFindings` is not a function.

- [ ] **Step 3: Extend the store**

Add `invalid?: boolean` to `StepNodeData` in `types.ts`, then in `store.ts`:

```ts
  findings: Finding[];
  setFindings: (findings: Finding[]) => void;
```

```ts
  findings: [],

  setFindings: (findings) => {
    // Findings carry node_id so the canvas can outline the culprit without
    // parsing prose. Recompute every node's flag, so clearing works too.
    const bad = new Set(findings.map((f) => f.node_id).filter((id): id is string => !!id));
    set({
      findings,
      nodes: get().nodes.map((n) =>
        n.data.invalid === bad.has(n.id)
          ? n
          : { ...n, data: { ...n.data, invalid: bad.has(n.id) } }),
    });
  },
```

The `n.data.invalid === bad.has(n.id) ? n : {...}` guard keeps the node reference stable when
nothing changed — React Flow re-renders on reference change, and remounting every node on
each save would lose selection.

- [ ] **Step 4: Write `HealthPanel.tsx`**

```tsx
import { usePipelineStore } from '../store';

export default function HealthPanel() {
  const nodes = usePipelineStore((s) => s.nodes);
  const edges = usePipelineStore((s) => s.edges);
  const findings = usePipelineStore((s) => s.findings);

  return (
    <aside className="aside">
      <h3>Pipeline</h3>

      <div className="card">
        <dl className="kv"><dt>Steps</dt><dd>{nodes.length}</dd></dl>
        <dl className="kv"><dt>Connections</dt><dd>{edges.length}</dd></dl>
      </div>

      {findings.length === 0 ? (
        <p className="lbl">No issues</p>
      ) : (
        <>
          <p className="lbl lbl--bad">
            {findings.length} issue{findings.length === 1 ? '' : 's'}
          </p>
          <div className="card">
            {findings.map((f, i) => (
              <div className="finding" key={`${f.code}-${i}`}>
                <span className="finding__code">{f.code}</span>
                <span>{f.message}</span>
                {f.node_id && <span className="finding__node">{f.node_id}</span>}
              </div>
            ))}
          </div>
        </>
      )}

      <div className="banner banner--info">
        Saving writes <code>docs/implr/config/pipeline.yaml</code>. A rejected save changes
        nothing on disk.
      </div>
    </aside>
  );
}
```

- [ ] **Step 5: Outline invalid nodes**

In `StepNode.tsx`, extend the class expression:

```tsx
      className={
        'step-node'
        + (data.available ? '' : ' step-node--planned')
        + (data.invalid ? ' step-node--invalid' : '')
      }
```

- [ ] **Step 6: Feed findings from `App.tsx`**

```tsx
  const onSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await api.putPipeline(usePipelineStore.getState().toDTO());
      usePipelineStore.getState().setFindings([]);
      setMessage('Saved.');
    } catch (e) {
      if (e instanceof api.ValidationError) {
        usePipelineStore.getState().setFindings(e.findings);
        setMessage('Not saved — see the issues on the right.');
      } else {
        usePipelineStore.getState().setFindings(
          [{ code: 'error', message: String(e), node_id: null }]);
        setMessage('Save failed.');
      }
    } finally {
      setSaving(false);
    }
  };
```

Replace the right-hand placeholder with `<HealthPanel />`.

- [ ] **Step 7: Add the styles**

Append to `app.css`:

```css
.step-node--invalid { border-color: var(--st-failed); box-shadow: 0 0 0 2px
  color-mix(in srgb, var(--st-failed) 25%, transparent); }

.card {
  background: var(--raised); border: 1px solid var(--hair);
  border-radius: var(--r-md); padding: .625rem .7rem;
  display: flex; flex-direction: column; gap: .45rem;
}
.kv { display: flex; align-items: baseline; justify-content: space-between;
      gap: .5rem; font-size: 12.5px; margin: 0; }
.kv dt { color: var(--text-soft); }
.kv dd { margin: 0; font-family: var(--mono); font-size: 12px; font-weight: 600;
         font-variant-numeric: tabular-nums; }

.lbl {
  font-family: var(--mono); font-size: 10px; letter-spacing: .12em;
  text-transform: uppercase; color: var(--text-faint); margin: 0;
}
.lbl--bad { color: var(--st-failed); }

.finding {
  display: flex; flex-direction: column; gap: .15rem;
  font-size: 12px; line-height: 1.45;
  padding-left: .5rem; border-left: 2px solid var(--st-failed);
}
.finding__code {
  font-family: var(--mono); font-size: 9.5px; letter-spacing: .06em;
  text-transform: uppercase; color: var(--st-failed);
}
.finding__node {
  font-family: var(--mono); font-size: 10px; color: var(--text-faint);
  align-self: flex-start; border: 1px solid var(--hair);
  border-radius: 4px; padding: 0 .25rem;
}

.banner {
  display: flex; gap: .5rem; align-items: flex-start;
  border-radius: var(--r-md); padding: .55rem .65rem;
  font-size: 12px; line-height: 1.45;
  background: var(--raised); border: 1px solid var(--hair); color: var(--text-soft);
}
.banner code { font-family: var(--mono); font-size: 11px; color: var(--text); }
.aside h3 { margin: 0; font-family: var(--display); font-size: .9375rem;
            font-weight: 600; letter-spacing: -.015em; }
```

- [ ] **Step 8: Run, build, commit**

```bash
cd studio/frontend && npm test && npm run build
git add studio/frontend/src
git commit -m "feat(studio): health panel and invalid-node outlines"
```

---

### Task 4: Run the demo

- [ ] **Step 1: Both processes up, a clean graph saved**

Build the two-node chain from Phase 2 and Save. The rail reads **No issues**.

- [ ] **Step 2: Make a cycle**

Connect the second node back to the first. Press **Save**.

- The stagebar reads *Not saved — see the issues on the right.*
- The rail turns red: **2 issues** — a `cycle` naming both nodes, and `no-root`.
- Both node cards get a red outline.

```bash
cat /tmp/studio-probe/docs/implr/config/pipeline.yaml
```

Expected: still the **clean** two-node chain. A rejected save changed nothing.

- [ ] **Step 3: Fix it**

Delete the back edge (select it, press Delete). Save. The rail goes quiet, outlines clear,
the stagebar reads *Saved.*

- [ ] **Step 4: Make an island behind a cycle**

Add two more nodes, connect them to each other in both directions, and leave them
disconnected from the chain. Save. Expect `cycle` plus **two** `unreachable-node` findings,
each naming its node, with only those two outlined.

- [ ] **Step 5: Confirm a lone node is fine**

Delete one of the two, leaving a single disconnected node. Save. **No issues** — a lone node
is its own root. Only a node trapped behind a cycle is unreachable.

- [ ] **Step 6: Confirm hand-edits are validated too**

```bash
python - <<'EOF'
import io
p = "/tmp/studio-probe/docs/implr/config/pipeline.yaml"
s = io.open(p, encoding="utf-8").read().replace("step: doc-ingest", "step: not-a-step", 1)
io.open(p, "w", encoding="utf-8").write(s)
EOF
```

Reload the browser, press Save. Expect `unknown-step` naming `not-a-step`. Validation lives
in the backend precisely so a hand-edited file is judged by the same rules as a
builder-authored one.

- [ ] **Step 7: Confirm the scope boundary**

Hand-edit a gate to `artefact: unicorn` and Save. It **succeeds** — gate semantics are
Phase 6. This is the before-state Phase 6's demo contrasts with.

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes, including the 2000-node chain test that
      proves cycle detection is iterative.
- [ ] `npm test` and `npm run build` pass.
- [ ] `python -m pytest tests/` at the repo root still passes.
- [ ] `PYTHONPATH=scripts python -m implr_validate --repo --root .` exits `0`.
- [ ] Every finding code has a test asserting the specific code: `unknown-step`,
      `disallowed-arg`, `duplicate-node-id`, `unknown-edge-node`, `cycle`,
      `unreachable-node`, `no-root`.
- [ ] A registered-but-unimplemented step still saves — availability is not a save-time rule.
- [ ] A rejected `PUT` leaves the previous good file byte-identical.
- [ ] Findings carry `node_id`, and the store marks exactly those nodes invalid — with the
      node reference left stable when the flag did not change.
- [ ] A single disconnected node is valid; two nodes in a mutual cycle are not.
- [ ] **The demo:** a cycle is refused with both findings named, both nodes outlined, and
      the file on disk unchanged; deleting the back edge clears everything.

---

## What the next phase gets

A designer that refuses graphs it cannot run. **Phase 4** opens the first configurator tab —
`Modal.tsx` plus the Run pane, `arg_values` on the node, and the three value findings — so
its demo is *"tick `--task`, type a value, and a bad one is refused inline before you can
save"*.
