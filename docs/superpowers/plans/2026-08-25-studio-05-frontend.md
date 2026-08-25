# implr Studio — Plan 5: Frontend (Design Mode & Run Mode)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One canvas, two modes. *Design mode*: drag steps from a palette, connect them, configure args and gates, save to the backend. *Run mode*: the same graph tinted by live run state, with per-node logs, a question box, and approve/retry/skip actions.

**Architecture:** Vite + React + TypeScript. Graph state lives in a Zustand store (not `useNodesState`) because both the WebSocket and the save action must touch graph state from outside the React tree. The pure logic — DTO mapping between the backend's `pipeline.yaml` shape and React Flow's node/edge shape — lives in plain modules with no React import, and carries the bulk of the test coverage. React Flow rendering is smoke-tested only; real drag-and-drop is out of scope for jsdom.

**Tech Stack:** Vite 5+, React 18+, TypeScript, `@xyflow/react@^12.11.3` (MIT), Zustand 4, Vitest + React Testing Library + jsdom.

**Spec:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md`

## Global Constraints

- The package is **`@xyflow/react`**, not `reactflow`. Version `^12.11.3`. Any snippet importing from `'reactflow'` is v11 and wrong for this codebase.
- Use **`screenToFlowPosition`** from `useReactFlow()`. `project()` was **removed** in v12, not merely deprecated.
- `nodeTypes` and `edgeTypes` must be defined at **module scope** (or `useMemo`'d). Recreating them per render remounts every node and destroys DOM state.
- Never mutate a node or edge object. React Flow's change detection is reference-based — always spread into a new object.
- Measured node dimensions live at `node.measured.width/height` in v12, **not** `node.width/height`.
- Interactive elements inside a custom node need `className="nodrag"`; edge labels need `nodrag nopan`.
- The backend is reached at a relative `/api` path through Vite's dev proxy. Never hardcode a host or port in frontend source.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/frontend/package.json`, `vite.config.ts`, `tsconfig.json` | Project setup and the `/api` dev proxy. |
| `studio/frontend/test/mockReactFlow.ts`, `test/setup.ts` | jsdom shims React Flow needs (ResizeObserver, DOMMatrixReadOnly, offset dimensions). |
| `studio/frontend/src/types.ts` | Shared TypeScript types mirroring the backend DTOs. |
| `studio/frontend/src/api.ts` | Typed `fetch` wrappers for every backend route. No React. |
| `studio/frontend/src/graph.ts` | **Pure** mapping between pipeline DTO and React Flow nodes/edges. No React. Carries most of the test coverage. |
| `studio/frontend/src/store.ts` | Zustand store: graph state, run state, actions. |
| `studio/frontend/src/nodes/StepNode.tsx` | Custom node: label, phase, args summary, status tint, handles. |
| `studio/frontend/src/edges/GateEdge.tsx` | Custom edge rendering the gate label. |
| `studio/frontend/src/panels/Palette.tsx` | Draggable step list grouped by phase; unavailable steps greyed. |
| `studio/frontend/src/panels/Inspector.tsx` | Selected node/edge configuration (args, gate). |
| `studio/frontend/src/panels/RunPanel.tsx` | Log stream, question box, operator actions. |
| `studio/frontend/src/App.tsx` | Layout, mode switch, providers. |

---

### Task 1: Project scaffolding and the jsdom shim

**Files:**
- Create: `studio/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`
- Create: `studio/frontend/test/mockReactFlow.ts`, `studio/frontend/test/setup.ts`
- Test: `studio/frontend/src/smoke.test.tsx`

**Interfaces:**
- Produces: a working `npm test` and `npm run dev`; `mockReactFlow()` callable from the Vitest setup file.

- [ ] **Step 1: Write the failing test**

Create `studio/frontend/src/smoke.test.tsx`:

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
    const edges = [{ id: 'a-b', source: 'a', target: 'b' }];

    const { container } = render(
      <div style={{ width: 800, height: 600 }}>
        <ReactFlow nodes={nodes} edges={edges} nodesDraggable={false} panOnDrag={false} />
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

Create `studio/frontend/package.json`:

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

Create `studio/frontend/vite.config.ts`:

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

Create `studio/frontend/tsconfig.json`:

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
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "test"]
}
```

Create `studio/frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>implr Studio</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `studio/frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '@xyflow/react/dist/style.css';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

Create `studio/frontend/src/index.css`:

```css
:root { color-scheme: light dark; font-family: system-ui, sans-serif; }
body { margin: 0; }
#root, .layout { height: 100vh; }
.layout { display: grid; grid-template-columns: 220px 1fr 320px; }
.canvas-wrap { position: relative; }
```

Create `studio/frontend/test/mockReactFlow.ts` (React Flow cannot measure nodes in jsdom without these; adapted from the official testing guide):

```ts
class ResizeObserverMock {
  callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }
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
    offsetHeight: {
      get() {
        return parseFloat(this.style.height) || 1;
      },
    },
    offsetWidth: {
      get() {
        return parseFloat(this.style.width) || 1;
      },
    },
  });

  (global.SVGElement as unknown as { prototype: { getBBox: () => object } }).prototype.getBBox =
    () => ({ x: 0, y: 0, width: 0, height: 0 });
};
```

Create `studio/frontend/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
import { mockReactFlow } from './mockReactFlow';

mockReactFlow();
```

- [ ] **Step 3: Install and run the test**

Run: `cd studio/frontend && npm install && npm test`
Expected: 1 passed. If it fails with "parent container needs a width and a height", the wrapper `<div style={{ width: 800, height: 600 }}>` is missing — React Flow needs explicit dimensions in jsdom.

- [ ] **Step 4: Commit**

```bash
git add studio/frontend
git commit -m "feat(studio): frontend scaffolding with React Flow jsdom shims"
```

---

### Task 2: Pure DTO mapping between pipeline.yaml and React Flow

**Files:**
- Create: `studio/frontend/src/types.ts`
- Create: `studio/frontend/src/graph.ts`
- Test: `studio/frontend/src/graph.test.ts`

**Interfaces:**
- Produces (all pure, no React import):
  - `types.StepDef`, `types.Gate`, `types.PipelineDTO`, `types.NodeDTO`, `types.EdgeDTO`, `types.RunDetail`, `types.NodeRunState`, `types.Finding`.
  - `graph.toFlow(dto: PipelineDTO, steps: Record<string, StepDef>) -> { nodes: FlowNode[]; edges: FlowEdge[] }`
  - `graph.fromFlow(nodes: FlowNode[], edges: FlowEdge[]) -> PipelineDTO`
  - `graph.makeNode(step: StepDef, position: {x,y}, existingIds: string[]) -> FlowNode` — generates a unique id from the step id (`ingest`, `ingest-2`, …).
  - `graph.gateLabel(gate: Gate) -> string` — the human-readable edge label.
  - `graph.DEFAULT_GATE: Gate` = `{ type: 'none' }`.

This module is where the round-trip correctness lives, so it gets the heaviest tests. It must never emit React Flow's transient fields (`selected`, `dragging`, `measured`, `width`, `height`) into the DTO.

- [ ] **Step 1: Write the failing test**

Create `studio/frontend/src/graph.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import * as graph from './graph';
import type { PipelineDTO, StepDef } from './types';

const STEPS: Record<string, StepDef> = {
  'doc-ingest': {
    id: 'doc-ingest', label: 'Document Ingestion', phase: 'discovery', skill: 'doc-ingest',
    args_allowed: ['--dry-run', '--rebuild'], args_default: [], interactive: false,
    produces: ['digests'], description: 'd', available: true,
  },
  'arch-gen': {
    id: 'arch-gen', label: 'Architecture Brief', phase: 'design', skill: 'arch-gen',
    args_allowed: ['--update'], args_default: [], interactive: true,
    produces: [], description: 'a', available: true,
  },
};

const DTO: PipelineDTO = {
  version: 1,
  nodes: [
    { id: 'ingest', step: 'doc-ingest', args: ['--rebuild'], position: { x: 10, y: 20 } },
    { id: 'arch', step: 'arch-gen', args: [], position: { x: 200, y: 20 } },
  ],
  edges: [
    {
      from: 'ingest', to: 'arch',
      gate: { type: 'artifact', artefact: 'requirement', quantifier: 'all', require: { status: 'approved' } },
    },
  ],
};

describe('toFlow', () => {
  it('maps nodes with their step definition into data', () => {
    const { nodes } = graph.toFlow(DTO, STEPS);

    expect(nodes).toHaveLength(2);
    expect(nodes[0].id).toBe('ingest');
    expect(nodes[0].type).toBe('step');
    expect(nodes[0].position).toEqual({ x: 10, y: 20 });
    expect(nodes[0].data.label).toBe('Document Ingestion');
    expect(nodes[0].data.args).toEqual(['--rebuild']);
    expect(nodes[0].data.available).toBe(true);
  });

  it('marks a node whose step is missing from the registry as unavailable', () => {
    const orphan: PipelineDTO = {
      version: 1,
      nodes: [{ id: 'x', step: 'sec-review', args: [], position: { x: 0, y: 0 } }],
      edges: [],
    };

    const { nodes } = graph.toFlow(orphan, STEPS);

    expect(nodes[0].data.available).toBe(false);
    expect(nodes[0].data.label).toBe('sec-review');
  });

  it('maps from/to onto source/target and keeps the gate in edge data', () => {
    const { edges } = graph.toFlow(DTO, STEPS);

    expect(edges[0].source).toBe('ingest');
    expect(edges[0].target).toBe('arch');
    expect(edges[0].type).toBe('gate');
    expect(edges[0].data.gate.type).toBe('artifact');
  });

  it('gives every edge a stable deterministic id', () => {
    const first = graph.toFlow(DTO, STEPS).edges[0].id;
    const second = graph.toFlow(DTO, STEPS).edges[0].id;

    expect(first).toBe(second);
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

    const dto = graph.fromFlow(dirty as typeof nodes, edges);

    const serialized = JSON.stringify(dto);
    for (const field of ['selected', 'dragging', 'measured', 'width', 'height', 'label']) {
      expect(serialized).not.toContain(field);
    }
  });

  it('emits a none gate for an edge created by dragging a connection', () => {
    const { nodes } = graph.toFlow(DTO, STEPS);
    const bare = [{ id: 'e1', source: 'ingest', target: 'arch', type: 'gate', data: {} }];

    const dto = graph.fromFlow(nodes, bare as never);

    expect(dto.edges[0].gate).toEqual({ type: 'none' });
  });

  it('preserves node positions after a drag', () => {
    const { nodes, edges } = graph.toFlow(DTO, STEPS);
    const moved = nodes.map((n) =>
      n.id === 'ingest' ? { ...n, position: { x: 999, y: 888 } } : n);

    const dto = graph.fromFlow(moved, edges);

    expect(dto.nodes[0].position).toEqual({ x: 999, y: 888 });
  });
});

describe('makeNode', () => {
  it('uses the step id when it is free', () => {
    const node = graph.makeNode(STEPS['doc-ingest'], { x: 5, y: 5 }, []);

    expect(node.id).toBe('doc-ingest');
    expect(node.data.args).toEqual([]);
  });

  it('suffixes a duplicate rather than colliding', () => {
    const node = graph.makeNode(STEPS['doc-ingest'], { x: 5, y: 5 }, ['doc-ingest']);

    expect(node.id).toBe('doc-ingest-2');
  });

  it('keeps suffixing past the second duplicate', () => {
    const ids = ['doc-ingest', 'doc-ingest-2'];

    expect(graph.makeNode(STEPS['doc-ingest'], { x: 0, y: 0 }, ids).id).toBe('doc-ingest-3');
  });

  it('applies the step default args', () => {
    const withDefaults = { ...STEPS['doc-ingest'], args_default: ['--rebuild'] };

    expect(graph.makeNode(withDefaults, { x: 0, y: 0 }, []).data.args).toEqual(['--rebuild']);
  });
});

describe('gateLabel', () => {
  it('renders nothing for an open gate', () => {
    expect(graph.gateLabel({ type: 'none' })).toBe('');
  });

  it('names a manual gate', () => {
    expect(graph.gateLabel({ type: 'manual' })).toBe('approval');
  });

  it('summarises an artefact gate', () => {
    const label = graph.gateLabel({
      type: 'artifact', artefact: 'requirement', quantifier: 'all',
      require: { status: 'approved' },
    });

    expect(label).toBe('all requirement status=approved');
  });

  it('marks a combined gate as also needing approval', () => {
    const label = graph.gateLabel({
      type: 'artifact+manual', artefact: 'plan', quantifier: 'any',
      require: { status: 'ready' },
    });

    expect(label).toBe('any plan status=ready + approval');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `./graph`

- [ ] **Step 3: Write the implementations**

Create `studio/frontend/src/types.ts`:

```ts
export interface StepDef {
  id: string;
  label: string;
  phase: string;
  skill: string;
  args_allowed: string[];
  args_default: string[];
  interactive: boolean;
  produces: string[];
  description: string;
  available: boolean;
}

export type GateType = 'none' | 'manual' | 'artifact' | 'artifact+manual';

export interface Gate {
  type: GateType;
  artefact?: string | null;
  quantifier?: 'all' | 'any' | null;
  require?: Record<string, string> | null;
}

export interface NodeDTO {
  id: string;
  step: string;
  args: string[];
  position: { x: number; y: number };
}

export interface EdgeDTO {
  from: string;
  to: string;
  gate: Gate;
}

export interface PipelineDTO {
  version: number;
  nodes: NodeDTO[];
  edges: EdgeDTO[];
}

export interface Finding {
  code: string;
  message: string;
  node_id: string | null;
}

export type NodeStatus =
  | 'pending' | 'blocked' | 'running' | 'awaiting-input' | 'awaiting-approval'
  | 'succeeded' | 'failed' | 'skipped' | 'cancelled';

export interface NodeRunState {
  node_id: string;
  status: NodeStatus;
  summary: string | null;
  error: string | null;
  manual_approved: boolean;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunDetail {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  nodes: Record<string, NodeRunState>;
  pipeline: PipelineDTO;
}

export interface RunEvent {
  seq: number;
  node_id: string | null;
  kind: 'log' | 'question' | 'artifact' | 'done' | 'status';
  payload: Record<string, unknown>;
  created_at: string;
}

export interface StepNodeData {
  label: string;
  step: string;
  phase: string;
  args: string[];
  interactive: boolean;
  available: boolean;
  status?: NodeStatus;
  [key: string]: unknown;
}

export interface GateEdgeData {
  gate: Gate;
  [key: string]: unknown;
}
```

Create `studio/frontend/src/graph.ts`:

```ts
/**
 * Pure mapping between the backend pipeline DTO and React Flow's node/edge shape.
 *
 * No React import belongs here. The DTO must never carry React Flow's transient
 * fields (selected, dragging, measured, width, height) - the backend rejects
 * unknown keys and, worse, they would be committed to pipeline.yaml.
 */
import type { Edge, Node } from '@xyflow/react';
import type { EdgeDTO, Gate, GateEdgeData, PipelineDTO, StepDef, StepNodeData } from './types';

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
    nodes: nodes.map((n) => ({
      id: n.id,
      step: n.data.step,
      args: [...n.data.args],
      position: { x: n.position.x, y: n.position.y },
    })),
    edges: edges.map(
      (e): EdgeDTO => ({
        from: e.source,
        to: e.target,
        gate: e.data?.gate ?? DEFAULT_GATE,
      }),
    ),
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

export function gateLabel(gate: Gate): string {
  if (gate.type === 'none') return '';
  if (gate.type === 'manual') return 'approval';

  const requirements = Object.entries(gate.require ?? {})
    .map(([field, value]) => `${field}=${value}`)
    .join(' ');
  const base = `${gate.quantifier ?? 'all'} ${gate.artefact ?? '?'} ${requirements}`.trim();

  return gate.type === 'artifact+manual' ? `${base} + approval` : base;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/frontend && npm test`
Expected: all `graph.test.ts` tests pass (18) plus the smoke test

- [ ] **Step 5: Commit**

```bash
git add studio/frontend/src/types.ts studio/frontend/src/graph.ts studio/frontend/src/graph.test.ts
git commit -m "feat(studio): pure pipeline<->React Flow DTO mapping"
```

---

### Task 3: API client and Zustand store

**Files:**
- Create: `studio/frontend/src/api.ts`
- Create: `studio/frontend/src/store.ts`
- Test: `studio/frontend/src/api.test.ts`, `studio/frontend/src/store.test.ts`

**Interfaces:**
- Produces:
  - `api.getRegistry()`, `api.getPipeline()`, `api.putPipeline(dto)`, `api.startRun()`, `api.getRun(id)`, `api.answer(runId, questionId, text)`, `api.approve(runId, nodeId)`, `api.retry(runId, nodeId)`, `api.skip(runId, nodeId)`, `api.cancel(runId)`, `api.openStream(runId, cursor, handlers)`.
  - `api.ValidationError` — thrown on 422, carrying `findings: Finding[]`.
  - `store.usePipelineStore` — Zustand store with `nodes`, `edges`, `steps`, `findings`, `runId`, `runStatus`, `nodeStates`, `logs`, `question`, and the actions `onNodesChange`, `onEdgesChange`, `onConnect`, `addStepNode`, `setNodeArgs`, `setEdgeGate`, `loadFrom`, `applyRunDetail`, `applyEvents`.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/api.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from './api';

const okJson = (body: unknown) =>
  Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses relative /api paths so no host is hardcoded', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(okJson({ steps: [], phases: [] }));

    await api.getRegistry();

    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url.startsWith('/api/')).toBe(true);
    expect(url).not.toContain('http');
  });

  it('throws ValidationError with findings on 422', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      Promise.resolve({
        ok: false, status: 422,
        json: () => Promise.resolve({ findings: [{ code: 'cycle', message: 'bad', node_id: null }] }),
      } as Response),
    );

    await expect(
      api.putPipeline({ version: 1, nodes: [], edges: [] }),
    ).rejects.toThrowError(api.ValidationError);

    try {
      await api.putPipeline({ version: 1, nodes: [], edges: [] });
    } catch (e) {
      expect((e as api.ValidationError).findings[0].code).toBe('cycle');
    }
  });

  it('throws a plain error on other failures', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      Promise.resolve({
        ok: false, status: 409,
        json: () => Promise.resolve({ detail: 'no pipeline saved' }),
      } as Response),
    );

    await expect(api.startRun()).rejects.toThrowError(/no pipeline saved/);
  });

  it('posts the answer body the backend expects', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(okJson({ ok: true }));

    await api.answer('r1', 'q1', 'Postgres');

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      question_id: 'q1', text: 'Postgres',
    });
  });
});
```

Create `studio/frontend/src/store.test.ts`:

```ts
import { beforeEach, describe, expect, it } from 'vitest';
import { usePipelineStore } from './store';
import type { PipelineDTO, RunDetail, StepDef } from './types';

const STEP: StepDef = {
  id: 'doc-ingest', label: 'Document Ingestion', phase: 'discovery', skill: 'doc-ingest',
  args_allowed: ['--dry-run'], args_default: [], interactive: false,
  produces: [], description: '', available: true,
};

const DTO: PipelineDTO = {
  version: 1,
  nodes: [
    { id: 'a', step: 'doc-ingest', args: [], position: { x: 0, y: 0 } },
    { id: 'b', step: 'doc-ingest', args: [], position: { x: 200, y: 0 } },
  ],
  edges: [{ from: 'a', to: 'b', gate: { type: 'none' } }],
};

const reset = () =>
  usePipelineStore.setState({
    nodes: [], edges: [], steps: {}, findings: [],
    runId: null, runStatus: null, nodeStates: {}, logs: {}, question: null, cursor: 0,
  });

describe('pipeline store', () => {
  beforeEach(reset);

  it('loads a pipeline into flow state', () => {
    usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });

    expect(usePipelineStore.getState().nodes).toHaveLength(2);
    expect(usePipelineStore.getState().edges).toHaveLength(1);
  });

  it('adds a palette step at the drop position with a unique id', () => {
    usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });

    usePipelineStore.getState().addStepNode(STEP, { x: 50, y: 60 });

    const ids = usePipelineStore.getState().nodes.map((n) => n.id);
    expect(ids).toContain('doc-ingest');
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('setNodeArgs replaces the object rather than mutating it', () => {
    usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });
    const before = usePipelineStore.getState().nodes[0];

    usePipelineStore.getState().setNodeArgs('a', ['--dry-run']);

    const after = usePipelineStore.getState().nodes[0];
    expect(after).not.toBe(before);
    expect(after.data.args).toEqual(['--dry-run']);
    expect(before.data.args).toEqual([]);
  });

  it('setEdgeGate updates the gate in edge data', () => {
    usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });
    const id = usePipelineStore.getState().edges[0].id;

    usePipelineStore.getState().setEdgeGate(id, { type: 'manual' });

    expect(usePipelineStore.getState().edges[0].data?.gate.type).toBe('manual');
  });

  it('applyRunDetail tints nodes with their run status', () => {
    usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });
    const detail = {
      id: 'r1', status: 'paused', created_at: '', updated_at: '', pipeline: DTO,
      nodes: {
        a: { node_id: 'a', status: 'succeeded', summary: null, error: null,
             manual_approved: false, started_at: null, finished_at: null },
        b: { node_id: 'b', status: 'failed', summary: null, error: 'exit 1',
             manual_approved: false, started_at: null, finished_at: null },
      },
    } as RunDetail;

    usePipelineStore.getState().applyRunDetail(detail);

    const nodes = usePipelineStore.getState().nodes;
    expect(nodes.find((n) => n.id === 'a')!.data.status).toBe('succeeded');
    expect(nodes.find((n) => n.id === 'b')!.data.status).toBe('failed');
    expect(usePipelineStore.getState().runStatus).toBe('paused');
  });

  it('applyEvents appends logs per node and advances the cursor', () => {
    usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });

    usePipelineStore.getState().applyEvents([
      { seq: 1, node_id: 'a', kind: 'log', payload: { text: 'one' }, created_at: '' },
      { seq: 2, node_id: 'a', kind: 'log', payload: { text: 'two' }, created_at: '' },
      { seq: 3, node_id: 'b', kind: 'log', payload: { text: 'other' }, created_at: '' },
    ]);

    const state = usePipelineStore.getState();
    expect(state.logs.a).toEqual(['one', 'two']);
    expect(state.logs.b).toEqual(['other']);
    expect(state.cursor).toBe(3);
  });

  it('applyEvents surfaces a question and clears it when the node moves on', () => {
    usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP });

    usePipelineStore.getState().applyEvents([
      { seq: 1, node_id: 'a', kind: 'question',
        payload: { question_id: 'q1', prompt_md: 'Which db?', options: null }, created_at: '' },
    ]);
    expect(usePipelineStore.getState().question?.question_id).toBe('q1');

    usePipelineStore.getState().applyEvents([
      { seq: 2, node_id: 'a', kind: 'done',
        payload: { outcome: 'success', summary: 'ok', error: null }, created_at: '' },
    ]);
    expect(usePipelineStore.getState().question).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `./api` and `./store`

- [ ] **Step 3: Write `api.ts`**

```ts
/**
 * Typed fetch wrappers. Paths are relative so the dev proxy (and the built
 * bundle served by the backend) resolve them - never hardcode a host or port.
 */
import type { Finding, PipelineDTO, RunDetail, RunEvent, StepDef } from './types';

export class ValidationError extends Error {
  findings: Finding[];
  constructor(findings: Finding[]) {
    super(findings.map((f) => f.message).join('; ') || 'pipeline is invalid');
    this.name = 'ValidationError';
    this.findings = findings;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 422 && Array.isArray((body as { findings?: Finding[] }).findings)) {
      throw new ValidationError((body as { findings: Finding[] }).findings);
    }
    throw new Error((body as { detail?: string }).detail ?? `request failed: ${response.status}`);
  }
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

export const getRegistry = () =>
  request<{ steps: StepDef[]; phases: string[] }>('/registry');

export const getPipeline = () =>
  request<{ pipeline: PipelineDTO; exists: boolean }>('/pipeline');

export const putPipeline = (dto: PipelineDTO) =>
  request<{ pipeline: PipelineDTO }>('/pipeline', { method: 'PUT', body: JSON.stringify(dto) });

export const startRun = () => post<{ run_id: string }>('/runs');
export const getRun = (runId: string) => request<RunDetail>(`/runs/${runId}`);
export const answer = (runId: string, questionId: string, text: string) =>
  post<{ ok: boolean }>(`/runs/${runId}/answer`, { question_id: questionId, text });
export const approve = (runId: string, nodeId: string) =>
  post<{ ok: boolean }>(`/runs/${runId}/approve`, { node_id: nodeId });
export const retry = (runId: string, nodeId: string) =>
  post<{ ok: boolean }>(`/runs/${runId}/nodes/${nodeId}/retry`);
export const skip = (runId: string, nodeId: string) =>
  post<{ ok: boolean }>(`/runs/${runId}/nodes/${nodeId}/skip`);
export const cancel = (runId: string) => post<{ ok: boolean }>(`/runs/${runId}/cancel`);

export interface StreamHandlers {
  onEvents: (events: RunEvent[], cursor: number) => void;
  onRunStatus: (status: string) => void;
  onClose?: () => void;
}

export function openStream(runId: string, cursor: number, handlers: StreamHandlers): WebSocket {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(
    `${scheme}://${window.location.host}/api/runs/${runId}/stream?cursor=${cursor}`,
  );

  socket.onmessage = (message) => {
    const frame = JSON.parse(message.data as string);
    if (frame.type === 'events') handlers.onEvents(frame.events, frame.cursor);
    else if (frame.type === 'run-status') handlers.onRunStatus(frame.status);
  };
  socket.onclose = () => handlers.onClose?.();

  return socket;
}
```

- [ ] **Step 4: Write `store.ts`**

```ts
/**
 * Zustand store for graph and run state.
 *
 * Zustand rather than useNodesState because both the WebSocket and the save
 * action must reach graph state from outside the React tree. Every update
 * returns new objects - React Flow's change detection is reference-based.
 */
import { addEdge, applyEdgeChanges, applyNodeChanges } from '@xyflow/react';
import type { Connection, EdgeChange, NodeChange } from '@xyflow/react';
import { create } from 'zustand';
import { DEFAULT_GATE, edgeId, fromFlow, makeNode, toFlow } from './graph';
import type { FlowEdge, FlowNode } from './graph';
import type { Finding, Gate, PipelineDTO, RunDetail, RunEvent, StepDef } from './types';

interface PendingQuestion {
  question_id: string;
  prompt_md: string;
  options: string[] | null;
  node_id: string | null;
}

interface PipelineState {
  nodes: FlowNode[];
  edges: FlowEdge[];
  steps: Record<string, StepDef>;
  findings: Finding[];
  runId: string | null;
  runStatus: string | null;
  nodeStates: RunDetail['nodes'];
  logs: Record<string, string[]>;
  question: PendingQuestion | null;
  cursor: number;

  onNodesChange: (changes: NodeChange<FlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<FlowEdge>[]) => void;
  onConnect: (connection: Connection) => void;
  addStepNode: (step: StepDef, position: { x: number; y: number }) => void;
  setNodeArgs: (nodeId: string, args: string[]) => void;
  setEdgeGate: (id: string, gate: Gate) => void;
  loadFrom: (dto: PipelineDTO, steps: Record<string, StepDef>) => void;
  toDTO: () => PipelineDTO;
  setFindings: (findings: Finding[]) => void;
  applyRunDetail: (detail: RunDetail) => void;
  applyEvents: (events: RunEvent[], cursor?: number) => void;
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  nodes: [],
  edges: [],
  steps: {},
  findings: [],
  runId: null,
  runStatus: null,
  nodeStates: {},
  logs: {},
  question: null,
  cursor: 0,

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

  setNodeArgs: (nodeId, args) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, args: [...args] } } : n,
      ),
    }),

  setEdgeGate: (id, gate) =>
    set({
      edges: get().edges.map((e) => (e.id === id ? { ...e, data: { ...e.data, gate } } : e)),
    }),

  loadFrom: (dto, steps) => {
    const { nodes, edges } = toFlow(dto, steps);
    set({ nodes, edges, steps, findings: [] });
  },

  toDTO: () => fromFlow(get().nodes, get().edges),

  setFindings: (findings) => set({ findings }),

  applyRunDetail: (detail) =>
    set({
      runId: detail.id,
      runStatus: detail.status,
      nodeStates: detail.nodes,
      nodes: get().nodes.map((n) => {
        const state = detail.nodes[n.id];
        return state ? { ...n, data: { ...n.data, status: state.status } } : n;
      }),
    }),

  applyEvents: (events, cursor) => {
    const logs = { ...get().logs };
    let question = get().question;

    for (const event of events) {
      const nodeId = event.node_id ?? '_run';
      if (event.kind === 'log') {
        logs[nodeId] = [...(logs[nodeId] ?? []), String(event.payload.text ?? '')];
      } else if (event.kind === 'question') {
        question = {
          question_id: String(event.payload.question_id),
          prompt_md: String(event.payload.prompt_md),
          options: (event.payload.options as string[] | null) ?? null,
          node_id: event.node_id,
        };
      } else if (event.kind === 'done' && question?.node_id === event.node_id) {
        question = null;
      }
    }

    const last = events.length ? events[events.length - 1].seq : get().cursor;
    set({ logs, question, cursor: cursor ?? last });
  },
}));
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd studio/frontend && npm test`
Expected: all api and store tests pass

- [ ] **Step 6: Commit**

```bash
git add studio/frontend/src/api.ts studio/frontend/src/store.ts studio/frontend/src/api.test.ts studio/frontend/src/store.test.ts
git commit -m "feat(studio): API client and Zustand graph/run store"
```

---

### Task 4: Custom node, custom edge, and the palette

**Files:**
- Create: `studio/frontend/src/nodes/StepNode.tsx`
- Create: `studio/frontend/src/edges/GateEdge.tsx`
- Create: `studio/frontend/src/panels/Palette.tsx`
- Create: `studio/frontend/src/flowTypes.ts`
- Test: `studio/frontend/src/nodes/StepNode.test.tsx`, `studio/frontend/src/panels/Palette.test.tsx`

**Interfaces:**
- Produces:
  - `StepNode` — renders label, phase, args, an "interactive" badge, an "unavailable" badge, and a `status-<status>` class. Target handle left, source handle right.
  - `GateEdge` — smooth-step path with the gate label in an `EdgeLabelRenderer`.
  - `flowTypes.nodeTypes` / `flowTypes.edgeTypes` — **module-scope constants**, the fix for React Flow's "you have created a new nodeTypes object" warning.
  - `Palette` — steps grouped by phase; unavailable steps are `draggable={false}` and greyed; `onDragStart` sets `text/plain` to the step id.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/nodes/StepNode.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { ReactFlow, ReactFlowProvider } from '@xyflow/react';
import { describe, expect, it } from 'vitest';
import { nodeTypes } from '../flowTypes';
import type { FlowNode } from '../graph';

function renderNode(data: Partial<FlowNode['data']>) {
  const nodes: FlowNode[] = [
    {
      id: 'a',
      type: 'step',
      position: { x: 0, y: 0 },
      data: {
        label: 'Document Ingestion', step: 'doc-ingest', phase: 'discovery',
        args: [], interactive: false, available: true, ...data,
      },
    },
  ];
  return render(
    <div style={{ width: 800, height: 600 }}>
      <ReactFlowProvider>
        <ReactFlow nodes={nodes} edges={[]} nodeTypes={nodeTypes} nodesDraggable={false} panOnDrag={false} />
      </ReactFlowProvider>
    </div>,
  );
}

describe('StepNode', () => {
  it('shows the label and phase', () => {
    renderNode({});

    expect(screen.getByText('Document Ingestion')).toBeInTheDocument();
    expect(screen.getByText('discovery')).toBeInTheDocument();
  });

  it('shows args when present', () => {
    renderNode({ args: ['--all'] });

    expect(screen.getByText('--all')).toBeInTheDocument();
  });

  it('badges an interactive step', () => {
    renderNode({ interactive: true });

    expect(screen.getByTitle(/asks questions/i)).toBeInTheDocument();
  });

  it('badges an unavailable step', () => {
    renderNode({ available: false });

    expect(screen.getByTitle(/not implemented/i)).toBeInTheDocument();
  });

  it('applies a status class so run state is visible', () => {
    const { container } = renderNode({ status: 'failed' });

    expect(container.querySelector('.step-node--failed')).toBeTruthy();
  });

  it('nodeTypes is a stable module-scope object', () => {
    const first = nodeTypes;
    const second = nodeTypes;

    expect(first).toBe(second);
  });
});
```

Create `studio/frontend/src/panels/Palette.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Palette from './Palette';
import type { StepDef } from '../types';

const steps: StepDef[] = [
  { id: 'doc-ingest', label: 'Document Ingestion', phase: 'discovery', skill: 'doc-ingest',
    args_allowed: [], args_default: [], interactive: false, produces: [],
    description: 'd', available: true },
  { id: 'sec-review', label: 'Security Checks', phase: 'verify', skill: 'sec-review',
    args_allowed: [], args_default: [], interactive: false, produces: [],
    description: 'planned', available: false },
];

describe('Palette', () => {
  it('groups steps under their phase heading', () => {
    render(<Palette steps={steps} phases={['discovery', 'verify']} onDragStart={vi.fn()} />);

    expect(screen.getByText('discovery')).toBeInTheDocument();
    expect(screen.getByText('verify')).toBeInTheDocument();
  });

  it('makes an available step draggable', () => {
    render(<Palette steps={steps} phases={['discovery', 'verify']} onDragStart={vi.fn()} />);

    expect(screen.getByText('Document Ingestion').closest('[draggable]'))
      .toHaveAttribute('draggable', 'true');
  });

  it('does not make an unavailable step draggable', () => {
    render(<Palette steps={steps} phases={['discovery', 'verify']} onDragStart={vi.fn()} />);

    const planned = screen.getByText('Security Checks').closest('.palette-item')!;
    expect(planned).toHaveAttribute('draggable', 'false');
    expect(planned.className).toContain('palette-item--unavailable');
  });

  it('explains why an unavailable step cannot be used', () => {
    render(<Palette steps={steps} phases={['discovery', 'verify']} onDragStart={vi.fn()} />);

    expect(screen.getByText('Security Checks').closest('.palette-item'))
      .toHaveAttribute('title', expect.stringMatching(/not implemented/i));
  });

  it('omits a phase heading with no steps', () => {
    render(<Palette steps={steps} phases={['discovery', 'verify', 'build']} onDragStart={vi.fn()} />);

    expect(screen.queryByText('build')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `../flowTypes` and `./Palette`

- [ ] **Step 3: Write the components**

Create `studio/frontend/src/nodes/StepNode.tsx`:

```tsx
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import type { FlowNode } from '../graph';

export default function StepNode({ data, selected }: NodeProps<FlowNode>) {
  const status = data.status ?? 'idle';

  return (
    <div
      className={`step-node step-node--${status}${data.available ? '' : ' step-node--planned'}`}
      data-selected={selected || undefined}
    >
      <Handle type="target" position={Position.Left} />

      <div className="step-node__header">
        <span className="step-node__label">{data.label}</span>
        {data.interactive && (
          <span className="step-node__badge" title="Interactive - asks questions during the run">?</span>
        )}
        {!data.available && (
          <span className="step-node__badge" title="Planned - this skill is not implemented yet">!</span>
        )}
      </div>

      <div className="step-node__phase">{data.phase}</div>

      {data.args.length > 0 && (
        <div className="step-node__args">
          {data.args.map((arg) => (
            <code key={arg}>{arg}</code>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Right} />
    </div>
  );
}
```

Create `studio/frontend/src/edges/GateEdge.tsx`:

```tsx
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';
import { gateLabel } from '../graph';
import type { FlowEdge } from '../graph';

export default function GateEdge({ id, data, ...props }: EdgeProps<FlowEdge>) {
  const [edgePath, labelX, labelY] = getSmoothStepPath(props);
  const label = data?.gate ? gateLabel(data.gate) : '';

  return (
    <>
      <BaseEdge id={id} path={edgePath} />
      {label && (
        <EdgeLabelRenderer>
          <div
            className="gate-label nodrag nopan"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
```

Create `studio/frontend/src/flowTypes.ts`:

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

Create `studio/frontend/src/panels/Palette.tsx`:

```tsx
import type { StepDef } from '../types';

interface Props {
  steps: StepDef[];
  phases: string[];
  onDragStart: (event: React.DragEvent, stepId: string) => void;
}

export default function Palette({ steps, phases, onDragStart }: Props) {
  return (
    <aside className="palette">
      {phases.map((phase) => {
        const inPhase = steps.filter((s) => s.phase === phase);
        if (inPhase.length === 0) return null;

        return (
          <section key={phase}>
            <h3 className="palette__phase">{phase}</h3>
            {inPhase.map((step) => (
              <div
                key={step.id}
                className={`palette-item${step.available ? '' : ' palette-item--unavailable'}`}
                draggable={step.available}
                onDragStart={(e) => step.available && onDragStart(e, step.id)}
                title={
                  step.available
                    ? step.description
                    : `${step.description} (not implemented yet - the skill does not exist)`
                }
              >
                {step.label}
              </div>
            ))}
          </section>
        );
      })}
    </aside>
  );
}
```

Add to `studio/frontend/src/index.css`:

```css
.palette { overflow-y: auto; padding: 8px; border-right: 1px solid #8883; }
.palette__phase { font-size: 11px; text-transform: uppercase; opacity: .6; margin: 12px 0 4px; }
.palette-item { padding: 6px 8px; margin-bottom: 4px; border: 1px solid #8886;
                border-radius: 6px; cursor: grab; font-size: 13px; }
.palette-item--unavailable { opacity: .45; cursor: not-allowed; border-style: dashed; }

.step-node { padding: 8px 12px; border: 2px solid #8886; border-radius: 8px;
             background: Canvas; min-width: 150px; font-size: 13px; }
.step-node[data-selected] { outline: 2px solid #3b82f6; }
.step-node--planned { border-style: dashed; }
.step-node__header { display: flex; gap: 6px; align-items: center; font-weight: 600; }
.step-node__badge { font-size: 10px; border: 1px solid currentColor; border-radius: 50%;
                    width: 14px; height: 14px; display: grid; place-items: center; opacity: .7; }
.step-node__phase { font-size: 10px; text-transform: uppercase; opacity: .55; }
.step-node__args code { font-size: 10px; margin-right: 4px; opacity: .8; }

.step-node--running          { border-color: #f59e0b; }
.step-node--succeeded        { border-color: #16a34a; }
.step-node--failed           { border-color: #dc2626; }
.step-node--blocked          { border-color: #6b7280; }
.step-node--awaiting-input   { border-color: #8b5cf6; }
.step-node--awaiting-approval{ border-color: #0ea5e9; }
.step-node--skipped          { border-color: #9ca3af; opacity: .6; }

.gate-label { background: #fde68a; color: #111; padding: 2px 6px;
              border-radius: 4px; font-size: 10px; font-weight: 600; }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd studio/frontend && npm test`
Expected: all StepNode and Palette tests pass

- [ ] **Step 5: Commit**

```bash
git add studio/frontend/src/nodes studio/frontend/src/edges studio/frontend/src/panels/Palette.tsx studio/frontend/src/flowTypes.ts studio/frontend/src/index.css studio/frontend/src/nodes/StepNode.test.tsx studio/frontend/src/panels/Palette.test.tsx
git commit -m "feat(studio): step node, gate edge, and palette"
```

---

### Task 5: Inspector, run panel, and the App shell

**Files:**
- Create: `studio/frontend/src/panels/Inspector.tsx`
- Create: `studio/frontend/src/panels/RunPanel.tsx`
- Create: `studio/frontend/src/App.tsx`
- Test: `studio/frontend/src/panels/Inspector.test.tsx`, `studio/frontend/src/panels/RunPanel.test.tsx`

**Interfaces:**
- Produces:
  - `Inspector` — args checkboxes drawn from the selected node's `args_allowed`; gate editor for a selected edge with artefact/quantifier/status dropdowns.
  - `RunPanel` — run status, per-node log pane, question box, and Approve / Retry / Skip / Cancel buttons shown only for the statuses that accept them.
  - `App` — the layout, `ReactFlowProvider`, drop handling via `screenToFlowPosition`, Save, Run, and mode switching.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/panels/Inspector.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Inspector from './Inspector';
import type { StepDef } from '../types';

const STEP: StepDef = {
  id: 'dev-executor', label: 'Implementation', phase: 'build', skill: 'dev-executor',
  args_allowed: ['--all', '--dry-run', '--commit'], args_default: ['--all'],
  interactive: false, produces: [], description: '', available: true,
};

const nodeSelection = {
  kind: 'node' as const,
  node: {
    id: 'build', type: 'step', position: { x: 0, y: 0 },
    data: { label: 'Implementation', step: 'dev-executor', phase: 'build',
            args: ['--all'], interactive: false, available: true },
  },
};

describe('Inspector - node', () => {
  it('offers exactly the args the registry allows', () => {
    render(<Inspector selection={nodeSelection} steps={{ 'dev-executor': STEP }}
                      onArgsChange={vi.fn()} onGateChange={vi.fn()} contracts={{}} />);

    for (const arg of STEP.args_allowed) {
      expect(screen.getByLabelText(arg)).toBeInTheDocument();
    }
    expect(screen.queryByLabelText('--wat')).not.toBeInTheDocument();
  });

  it('reflects the currently selected args', () => {
    render(<Inspector selection={nodeSelection} steps={{ 'dev-executor': STEP }}
                      onArgsChange={vi.fn()} onGateChange={vi.fn()} contracts={{}} />);

    expect(screen.getByLabelText('--all')).toBeChecked();
    expect(screen.getByLabelText('--dry-run')).not.toBeChecked();
  });

  it('reports an arg being enabled', async () => {
    const onArgsChange = vi.fn();
    render(<Inspector selection={nodeSelection} steps={{ 'dev-executor': STEP }}
                      onArgsChange={onArgsChange} onGateChange={vi.fn()} contracts={{}} />);

    await userEvent.click(screen.getByLabelText('--dry-run'));

    expect(onArgsChange).toHaveBeenCalledWith('build', ['--all', '--dry-run']);
  });

  it('reports an arg being disabled', async () => {
    const onArgsChange = vi.fn();
    render(<Inspector selection={nodeSelection} steps={{ 'dev-executor': STEP }}
                      onArgsChange={onArgsChange} onGateChange={vi.fn()} contracts={{}} />);

    await userEvent.click(screen.getByLabelText('--all'));

    expect(onArgsChange).toHaveBeenCalledWith('build', []);
  });
});

const edgeSelection = {
  kind: 'edge' as const,
  edge: { id: 'a__b', source: 'a', target: 'b', type: 'gate',
          data: { gate: { type: 'none' as const } } },
};

const CONTRACTS = {
  requirement: { states: ['draft', 'under-review', 'approved'] },
  plan: { states: ['ready', 'in-progress', 'done'] },
};

describe('Inspector - edge gate', () => {
  it('offers every gate type', () => {
    render(<Inspector selection={edgeSelection} steps={{}}
                      onArgsChange={vi.fn()} onGateChange={vi.fn()} contracts={CONTRACTS} />);

    const select = screen.getByLabelText(/gate type/i);
    expect(select).toHaveValue('none');
    for (const type of ['none', 'manual', 'artifact', 'artifact+manual']) {
      expect(screen.getByRole('option', { name: type })).toBeInTheDocument();
    }
  });

  it('hides artefact fields for a non-artefact gate', () => {
    render(<Inspector selection={edgeSelection} steps={{}}
                      onArgsChange={vi.fn()} onGateChange={vi.fn()} contracts={CONTRACTS} />);

    expect(screen.queryByLabelText(/artefact/i)).not.toBeInTheDocument();
  });

  it('offers only statuses legal for the chosen artefact', () => {
    const artefactGate = {
      kind: 'edge' as const,
      edge: { ...edgeSelection.edge, data: { gate: {
        type: 'artifact' as const, artefact: 'plan', quantifier: 'all' as const,
        require: { status: 'ready' } } } },
    };

    render(<Inspector selection={artefactGate} steps={{}}
                      onArgsChange={vi.fn()} onGateChange={vi.fn()} contracts={CONTRACTS} />);

    expect(screen.getByRole('option', { name: 'ready' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'approved' })).not.toBeInTheDocument();
  });
});
```

Create `studio/frontend/src/panels/RunPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import RunPanel from './RunPanel';
import type { NodeRunState } from '../types';

const node = (status: NodeRunState['status'], extra: Partial<NodeRunState> = {}): NodeRunState => ({
  node_id: 'a', status, summary: null, error: null,
  manual_approved: false, started_at: null, finished_at: null, ...extra,
});

const noop = {
  onAnswer: vi.fn(), onApprove: vi.fn(), onRetry: vi.fn(),
  onSkip: vi.fn(), onCancel: vi.fn(),
};

describe('RunPanel', () => {
  it('shows the log lines for the selected node', () => {
    render(<RunPanel runId="r1" runStatus="running" selectedNodeId="a"
                     nodeStates={{ a: node('running') }} logs={{ a: ['one', 'two'] }}
                     question={null} {...noop} />);

    expect(screen.getByText('one')).toBeInTheDocument();
    expect(screen.getByText('two')).toBeInTheDocument();
  });

  it('shows an approve button only when awaiting approval', () => {
    const { rerender } = render(
      <RunPanel runId="r1" runStatus="paused" selectedNodeId="a"
                nodeStates={{ a: node('running') }} logs={{}} question={null} {...noop} />);
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument();

    rerender(
      <RunPanel runId="r1" runStatus="paused" selectedNodeId="a"
                nodeStates={{ a: node('awaiting-approval') }} logs={{}} question={null} {...noop} />);
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument();
  });

  it('offers retry and skip only for a failed node, and shows the error', () => {
    render(<RunPanel runId="r1" runStatus="paused" selectedNodeId="a"
                     nodeStates={{ a: node('failed', { error: 'exit code 1' }) }}
                     logs={{}} question={null} {...noop} />);

    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /skip/i })).toBeInTheDocument();
    expect(screen.getByText(/exit code 1/)).toBeInTheDocument();
  });

  it('renders a pending question and submits the typed answer', async () => {
    const onAnswer = vi.fn();
    render(<RunPanel runId="r1" runStatus="running" selectedNodeId="a"
                     nodeStates={{ a: node('awaiting-input') }} logs={{}}
                     question={{ question_id: 'q1', prompt_md: 'Postgres or MySQL?',
                                 options: null, node_id: 'a' }}
                     {...noop} onAnswer={onAnswer} />);

    expect(screen.getByText('Postgres or MySQL?')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/your answer/i), 'Postgres');
    await userEvent.click(screen.getByRole('button', { name: /send/i }));

    expect(onAnswer).toHaveBeenCalledWith('q1', 'Postgres');
  });

  it('does not submit an empty answer', async () => {
    const onAnswer = vi.fn();
    render(<RunPanel runId="r1" runStatus="running" selectedNodeId="a"
                     nodeStates={{ a: node('awaiting-input') }} logs={{}}
                     question={{ question_id: 'q1', prompt_md: 'Which?', options: null, node_id: 'a' }}
                     {...noop} onAnswer={onAnswer} />);

    await userEvent.click(screen.getByRole('button', { name: /send/i }));

    expect(onAnswer).not.toHaveBeenCalled();
  });

  it('tells the operator when no run has started', () => {
    render(<RunPanel runId={null} runStatus={null} selectedNodeId={null}
                     nodeStates={{}} logs={{}} question={null} {...noop} />);

    expect(screen.getByText(/no run/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `./Inspector` and `./RunPanel`

- [ ] **Step 3: Write `Inspector.tsx`**

```tsx
import type { FlowEdge, FlowNode } from '../graph';
import type { Gate, GateType, StepDef } from '../types';

const GATE_TYPES: GateType[] = ['none', 'manual', 'artifact', 'artifact+manual'];

export type Selection =
  | { kind: 'node'; node: FlowNode }
  | { kind: 'edge'; edge: FlowEdge }
  | null;

interface Props {
  selection: Selection;
  steps: Record<string, StepDef>;
  contracts: Record<string, { states: string[] }>;
  onArgsChange: (nodeId: string, args: string[]) => void;
  onGateChange: (edgeId: string, gate: Gate) => void;
}

export default function Inspector({ selection, steps, contracts, onArgsChange, onGateChange }: Props) {
  if (!selection) {
    return <aside className="inspector">Select a step or a connection.</aside>;
  }

  if (selection.kind === 'node') {
    const { node } = selection;
    const def = steps[node.data.step];

    return (
      <aside className="inspector">
        <h3>{node.data.label}</h3>
        <p className="inspector__hint">{def?.description}</p>
        <h4>Arguments</h4>
        {(def?.args_allowed ?? []).map((arg) => (
          <label key={arg} className="inspector__row">
            <input
              type="checkbox"
              checked={node.data.args.includes(arg)}
              onChange={(e) =>
                onArgsChange(
                  node.id,
                  e.target.checked
                    ? [...node.data.args, arg]
                    : node.data.args.filter((a) => a !== arg),
                )
              }
            />
            {arg}
          </label>
        ))}
      </aside>
    );
  }

  const { edge } = selection;
  const gate: Gate = edge.data?.gate ?? { type: 'none' };
  const isArtefact = gate.type === 'artifact' || gate.type === 'artifact+manual';
  const artefactNames = Object.keys(contracts);
  const legalStates = gate.artefact ? (contracts[gate.artefact]?.states ?? []) : [];

  const update = (patch: Partial<Gate>) => onGateChange(edge.id, { ...gate, ...patch });

  return (
    <aside className="inspector">
      <h3>
        {edge.source} → {edge.target}
      </h3>

      <label className="inspector__row" htmlFor="gate-type">
        Gate type
      </label>
      <select
        id="gate-type"
        value={gate.type}
        onChange={(e) => {
          const type = e.target.value as GateType;
          update(
            type === 'artifact' || type === 'artifact+manual'
              ? {
                  type,
                  artefact: gate.artefact ?? artefactNames[0],
                  quantifier: gate.quantifier ?? 'all',
                  require: gate.require ?? {},
                }
              : { type, artefact: null, quantifier: null, require: null },
          );
        }}
      >
        {GATE_TYPES.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>

      {isArtefact && (
        <>
          <label className="inspector__row" htmlFor="gate-artefact">
            Artefact
          </label>
          <select
            id="gate-artefact"
            value={gate.artefact ?? ''}
            onChange={(e) => update({ artefact: e.target.value, require: {} })}
          >
            {artefactNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>

          <label className="inspector__row" htmlFor="gate-quantifier">
            Quantifier
          </label>
          <select
            id="gate-quantifier"
            value={gate.quantifier ?? 'all'}
            onChange={(e) => update({ quantifier: e.target.value as 'all' | 'any' })}
          >
            <option value="all">all</option>
            <option value="any">any</option>
          </select>

          <label className="inspector__row" htmlFor="gate-status">
            Required status
          </label>
          <select
            id="gate-status"
            value={gate.require?.status ?? ''}
            onChange={(e) => update({ require: { status: e.target.value } })}
          >
            <option value="">(any)</option>
            {legalStates.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </>
      )}
    </aside>
  );
}
```

- [ ] **Step 4: Write `RunPanel.tsx`**

```tsx
import { useState } from 'react';
import type { NodeRunState } from '../types';

interface PendingQuestion {
  question_id: string;
  prompt_md: string;
  options: string[] | null;
  node_id: string | null;
}

interface Props {
  runId: string | null;
  runStatus: string | null;
  selectedNodeId: string | null;
  nodeStates: Record<string, NodeRunState>;
  logs: Record<string, string[]>;
  question: PendingQuestion | null;
  onAnswer: (questionId: string, text: string) => void;
  onApprove: (nodeId: string) => void;
  onRetry: (nodeId: string) => void;
  onSkip: (nodeId: string) => void;
  onCancel: () => void;
}

export default function RunPanel(props: Props) {
  const { runId, runStatus, selectedNodeId, nodeStates, logs, question } = props;
  const [draft, setDraft] = useState('');

  if (!runId) {
    return <aside className="runpanel">No run yet. Press Run to start the saved pipeline.</aside>;
  }

  const state = selectedNodeId ? nodeStates[selectedNodeId] : undefined;
  const lines = selectedNodeId ? (logs[selectedNodeId] ?? []) : [];

  return (
    <aside className="runpanel">
      <h3>
        Run {runId} — {runStatus}
      </h3>
      <button onClick={props.onCancel}>Cancel run</button>

      {state && (
        <>
          <h4>
            {state.node_id} — {state.status}
          </h4>
          {state.error && <p className="runpanel__error">{state.error}</p>}

          {state.status === 'awaiting-approval' && (
            <button onClick={() => props.onApprove(state.node_id)}>Approve</button>
          )}
          {state.status === 'failed' && (
            <>
              <button onClick={() => props.onRetry(state.node_id)}>Retry</button>
              <button onClick={() => props.onSkip(state.node_id)}>Skip</button>
            </>
          )}
        </>
      )}

      {question && (
        <div className="runpanel__question">
          <p>{question.prompt_md}</p>
          <label htmlFor="answer">Your answer</label>
          <textarea id="answer" value={draft} onChange={(e) => setDraft(e.target.value)} />
          <button
            onClick={() => {
              if (!draft.trim()) return;
              props.onAnswer(question.question_id, draft);
              setDraft('');
            }}
          >
            Send
          </button>
        </div>
      )}

      <pre className="runpanel__log">
        {lines.map((line, i) => (
          <div key={i}>{line}</div>
        ))}
      </pre>
    </aside>
  );
}
```

- [ ] **Step 5: Write `App.tsx`**

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useOnSelectionChange,
  useReactFlow,
} from '@xyflow/react';
import * as api from './api';
import { edgeTypes, nodeTypes } from './flowTypes';
import Inspector from './panels/Inspector';
import type { Selection } from './panels/Inspector';
import Palette from './panels/Palette';
import RunPanel from './panels/RunPanel';
import { usePipelineStore } from './store';
import type { Finding, StepDef } from './types';

const CONTRACTS: Record<string, { states: string[] }> = {
  requirement: { states: ['draft', 'under-review', 'approved', 'rejected', 'superseded'] },
  plan: { states: ['ready', 'in-progress', 'done', 'blocked', 'needs-rework'] },
  cr: { states: ['draft', 'approved', 'rejected', 'applied'] },
  review: { states: ['approved', 'approved-with-warnings', 'changes-required', 'rejected'] },
};

function Studio() {
  const store = usePipelineStore();
  const { screenToFlowPosition } = useReactFlow();
  const [steps, setSteps] = useState<StepDef[]>([]);
  const [phases, setPhases] = useState<string[]>([]);
  const [mode, setMode] = useState<'design' | 'run'>('design');
  const [selection, setSelection] = useState<Selection>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const socket = useRef<WebSocket | null>(null);
  const dragged = useRef<string | null>(null);

  useEffect(() => {
    void (async () => {
      const registry = await api.getRegistry();
      setSteps(registry.steps);
      setPhases(registry.phases);
      const byId = Object.fromEntries(registry.steps.map((s) => [s.id, s]));
      const { pipeline } = await api.getPipeline();
      usePipelineStore.getState().loadFrom(pipeline, byId);
    })();
  }, []);

  const onChange = useCallback(({ nodes, edges }: { nodes: unknown[]; edges: unknown[] }) => {
    if (nodes.length === 1) setSelection({ kind: 'node', node: nodes[0] as never });
    else if (edges.length === 1) setSelection({ kind: 'edge', edge: edges[0] as never });
    else setSelection(null);
  }, []);
  useOnSelectionChange({ onChange });

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const stepId = dragged.current ?? event.dataTransfer.getData('text/plain');
      const step = steps.find((s) => s.id === stepId);
      if (!step) return;
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      usePipelineStore.getState().addStepNode(step, position);
      dragged.current = null;
    },
    [steps, screenToFlowPosition],
  );

  const onSave = async () => {
    try {
      await api.putPipeline(usePipelineStore.getState().toDTO());
      setFindings([]);
    } catch (e) {
      setFindings(e instanceof api.ValidationError ? e.findings : [
        { code: 'error', message: String(e), node_id: null },
      ]);
    }
  };

  const refresh = async (runId: string) => {
    usePipelineStore.getState().applyRunDetail(await api.getRun(runId));
  };

  const onRun = async () => {
    await onSave();
    const { run_id } = await api.startRun();
    setMode('run');
    await refresh(run_id);
    socket.current?.close();
    socket.current = api.openStream(run_id, usePipelineStore.getState().cursor, {
      onEvents: (events, cursor) => usePipelineStore.getState().applyEvents(events, cursor),
      onRunStatus: () => void refresh(run_id),
    });
  };

  const act = (fn: (runId: string, nodeId: string) => Promise<unknown>) => async (nodeId: string) => {
    const runId = usePipelineStore.getState().runId;
    if (!runId) return;
    await fn(runId, nodeId);
    await refresh(runId);
  };

  return (
    <div className="layout">
      <Palette
        steps={steps}
        phases={phases}
        onDragStart={(event, stepId) => {
          dragged.current = stepId;
          event.dataTransfer.setData('text/plain', stepId);
          event.dataTransfer.effectAllowed = 'move';
        }}
      />

      <div className="canvas-wrap" onDrop={onDrop} onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
      }}>
        <div className="toolbar">
          <button onClick={() => setMode(mode === 'design' ? 'run' : 'design')}>
            {mode === 'design' ? 'Run mode' : 'Design mode'}
          </button>
          <button onClick={onSave}>Save</button>
          <button onClick={onRun}>Run</button>
          {findings.map((f) => (
            <span key={f.code + f.message} className="finding">
              {f.message}
            </span>
          ))}
        </div>

        <ReactFlow
          nodes={store.nodes}
          edges={store.edges}
          onNodesChange={store.onNodesChange}
          onEdgesChange={store.onEdgesChange}
          onConnect={store.onConnect}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          colorMode="system"
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>

      {mode === 'design' ? (
        <Inspector
          selection={selection}
          steps={Object.fromEntries(steps.map((s) => [s.id, s]))}
          contracts={CONTRACTS}
          onArgsChange={store.setNodeArgs}
          onGateChange={store.setEdgeGate}
        />
      ) : (
        <RunPanel
          runId={store.runId}
          runStatus={store.runStatus}
          selectedNodeId={selection?.kind === 'node' ? selection.node.id : null}
          nodeStates={store.nodeStates}
          logs={store.logs}
          question={store.question}
          onAnswer={async (questionId, text) => {
            const runId = usePipelineStore.getState().runId;
            if (!runId) return;
            await api.answer(runId, questionId, text);
            await refresh(runId);
          }}
          onApprove={act(api.approve)}
          onRetry={act(api.retry)}
          onSkip={act(api.skip)}
          onCancel={async () => {
            const runId = usePipelineStore.getState().runId;
            if (runId) {
              await api.cancel(runId);
              await refresh(runId);
            }
          }}
        />
      )}
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

Add to `studio/frontend/src/index.css`:

```css
.toolbar { position: absolute; z-index: 5; top: 8px; left: 8px; display: flex;
           gap: 6px; align-items: center; }
.finding { background: #fee2e2; color: #991b1b; padding: 2px 6px;
           border-radius: 4px; font-size: 11px; }
.inspector, .runpanel { padding: 12px; border-left: 1px solid #8883;
                        overflow-y: auto; font-size: 13px; }
.inspector__row { display: block; margin: 4px 0; }
.inspector__hint { opacity: .7; font-size: 12px; }
.runpanel__error { color: #dc2626; font-size: 12px; }
.runpanel__question textarea { width: 100%; min-height: 60px; }
.runpanel__log { background: #0001; padding: 6px; font-size: 11px;
                 max-height: 40vh; overflow: auto; white-space: pre-wrap; }
```

- [ ] **Step 6: Run the whole frontend suite**

Run: `cd studio/frontend && npm test`
Expected: every test passes

- [ ] **Step 7: Typecheck and build**

Run: `cd studio/frontend && npm run build`
Expected: builds with no TypeScript errors

- [ ] **Step 8: Commit**

```bash
git add studio/frontend/src
git commit -m "feat(studio): inspector, run panel, and app shell"
```

---

## Definition of Done

- [ ] `npm test` in `studio/frontend/` passes.
- [ ] `npm run build` typechecks and builds.
- [ ] `graph.fromFlow` never emits `selected`, `dragging`, `measured`, `width`, or `height` into the DTO — proven by test.
- [ ] `toFlow` → `fromFlow` round-trips a pipeline unchanged.
- [ ] `nodeTypes` and `edgeTypes` are module-scope constants.
- [ ] The Inspector offers only the args in that step's `args_allowed`, and only the statuses legal for the chosen artefact.
- [ ] An unavailable step is visible in the palette but not draggable.
- [ ] No frontend source file contains a hardcoded host or port.

## Manual verification (not automatable in jsdom)

HTML5 drag-and-drop cannot be meaningfully simulated in jsdom — `dataTransfer` is not implemented. Verify by hand, with the backend running as `implr-studio --fake --workspace <a test project>`:

1. Drag "Document Ingestion" from the palette onto the canvas; a node appears where dropped.
2. Drag from its right handle to a second node's left handle; an edge appears.
3. Select the edge, set the gate to `artifact` / `requirement` / `all` / `approved`; the edge label updates.
4. Press Save; `docs/implr/config/pipeline.yaml` appears in the target project.
5. Set the gate status to a value from the wrong state machine; Save is rejected with a message naming the legal states.
6. Press Run; nodes tint as they execute and the log pane fills.
