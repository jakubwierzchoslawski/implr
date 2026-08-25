# implr Studio — Plan 5: Frontend (Console, Step Configurator, Run Mode)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dark-first operations console. *Design mode*: a searchable palette, a graph canvas, and a **step configurator modal** that selects arguments (including values), the model tier for each subagent the step dispatches, and shows the step's input sources and output artefact contract. *Run mode*: the same graph tinted by live run state, with per-node logs and the state's affordance.

**Architecture:** Vite + React + TypeScript. The design system is a **shipped file** (`src/tokens.css`), not a description, so it cannot drift from this plan. Graph state lives in a Zustand store because both the WebSocket and the save action must reach it from outside the React tree. The pure logic — DTO mapping, gate phrasing, model-mix aggregation — lives in plain modules with no React import and carries the bulk of the coverage. React Flow rendering is smoke-tested; real drag-and-drop is out of scope for jsdom.

**Tech Stack:** Vite 5+, React 18+, TypeScript, `@xyflow/react@^12.11.3` (MIT), Zustand 4, Vitest + React Testing Library + jsdom.

**Spec:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md`

**Runtime verification:** `docs/RUNTIME.md` — how to prove this plan actually runs, not just that its suite passes.

## Global Constraints

- The package is **`@xyflow/react`**, not `reactflow`. Version `^12.11.3`. Any snippet importing from `'reactflow'` is v11 and wrong for this codebase.
- Use **`screenToFlowPosition`** from `useReactFlow()`. `project()` was **removed** in v12, not merely deprecated.
- `nodeTypes` and `edgeTypes` must be defined at **module scope** (or `useMemo`'d). Recreating them per render remounts every node and destroys DOM state.
- Never mutate a node or edge object. React Flow's change detection is reference-based — always spread into a new object.
- Measured node dimensions live at `node.measured.width/height` in v12, **not** `node.width/height`.
- Interactive elements inside a custom node need `className="nodrag"`; edge labels need `nodrag nopan`.
- The backend is reached at a relative `/api` path through Vite's dev proxy. Never hardcode a host or port in frontend source.
- **Colour is data.** Every saturated colour comes from a `--st-*` (run state), `--tier-*` (model tier) or `--gate` token. No component may introduce a saturated colour outside those groups — a brand hue competing with `--st-failed` makes a failing node harder to spot, which is the one thing this UI exists to show. Task 1 ships a test that enforces this.
- **Dark is the default in every theme state.** There is deliberately no `prefers-color-scheme` query; light appears only under an explicit `data-theme="light"`.
- Nothing in the frontend hardcodes an implr status, artefact type, model tier, agent name, or flag. All of it arrives from `GET /api/registry`.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/frontend/package.json`, `vite.config.ts`, `tsconfig.json` | Project setup and the `/api` dev proxy. |
| `studio/frontend/src/tokens.css` | **The design system.** Colour, type, radii, shadows, motion. Imported first. |
| `studio/frontend/src/app.css` | Component styles, built entirely from tokens. |
| `studio/frontend/test/mockReactFlow.ts`, `test/setup.ts` | jsdom shims React Flow needs. |
| `studio/frontend/src/types.ts` | Shared types mirroring the backend DTOs. |
| `studio/frontend/src/api.ts` | Typed `fetch` wrappers. No React. |
| `studio/frontend/src/graph.ts` | **Pure** mapping between pipeline DTO and React Flow nodes/edges. |
| `studio/frontend/src/gates.ts` | **Pure** gate label + plain-language phrasing. |
| `studio/frontend/src/models.ts` | **Pure** model-mix aggregation and tier resolution. |
| `studio/frontend/src/store.ts` | Zustand: graph state, run state, actions. |
| `studio/frontend/src/nodes/StepNode.tsx` | Node card: status stripe, label, args, agent tier dots. |
| `studio/frontend/src/edges/GateEdge.tsx` | Gate chip on the edge. |
| `studio/frontend/src/panels/Palette.tsx` | Searchable phase-grouped step list. |
| `studio/frontend/src/panels/HealthPanel.tsx` | Design-mode right rail: counts, findings, model mix. |
| `studio/frontend/src/panels/RunPanel.tsx` | Run-mode right rail: log, question, operator actions. |
| `studio/frontend/src/modal/Modal.tsx` | The dialog shell: scrim, head, tabs, footer, Escape, focus. |
| `studio/frontend/src/modal/StepConfig.tsx` | **The configurator.** Run / Agents / Input / Output. |
| `studio/frontend/src/modal/GateConfig.tsx` | The gate editor pane. |
| `studio/frontend/src/App.tsx` | Layout, mode switch, providers. |

---

### Task 1: Scaffolding, the design system, and the colour guard

**Files:**
- Create: `studio/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`
- Create: `studio/frontend/src/tokens.css`
- Create: `studio/frontend/test/mockReactFlow.ts`, `studio/frontend/test/setup.ts`
- Test: `studio/frontend/src/smoke.test.tsx`, `studio/frontend/src/tokens.test.ts`

**Interfaces:**
- Produces: a working `npm test` and `npm run dev`; `tokens.css` as the single source of every colour, type and spacing value.

**Do Task 0 of Plan 1 before this task.** It adds `node_modules/` to `.gitignore`. Step 2
below runs `npm install`, and Step 6 runs `git add studio/frontend`.

- [ ] **Step 1: Write the failing tests**

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

Create `studio/frontend/src/tokens.test.ts` — the design guard:

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
    const spread = Math.max(r, g, b) - Math.min(r, g, b);
    if (spread > 24) found.push('#' + hex);
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

  it('component styles introduce no saturated colour of their own', () => {
    // THE design rule. Every hue in the app must be a reserved token, so a brand
    // colour can never compete with the run-state palette the operator reads.
    const offenders = saturatedHexes(read('app.css'));

    expect(offenders).toEqual([]);
  });

  it('every font-family declares a fallback stack', () => {
    const css = read('tokens.css');
    const families = [...css.matchAll(/--(?:sans|display|mono):([^;]+);/g)].map((m) => m[1]);

    expect(families.length).toBeGreaterThanOrEqual(3);
    for (const stack of families) {
      expect(stack.split(',').length).toBeGreaterThan(1);
    }
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
    "types": ["vitest/globals", "@testing-library/jest-dom", "node"]
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

Create `studio/frontend/src/main.tsx`:

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

- [ ] **Step 3: Write the design system**

Create `studio/frontend/src/tokens.css`. This file is the design. Every colour, size and
face in the application resolves through it:

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

Create `studio/frontend/src/app.css` with the component styles. It must contain **no
saturated hex value** — every colour is `var(--…)`. Start it with:

```css
/* Component styles. Colours come from tokens.css only - src/tokens.test.ts
   fails the build if a saturated hex appears here. */
.layout { display: grid; grid-template-columns: 246px minmax(0, 1fr) 316px; height: 100vh; }
.rail   { border-right: 1px solid var(--hair); background: var(--surface); }
.stage  { position: relative; overflow: auto; background:
            radial-gradient(circle at 1px 1px, var(--hair) 1px, transparent 0) 0 0 / 18px 18px,
            var(--sunk); }
.aside  { border-left: 1px solid var(--hair); background: var(--surface); padding: .875rem;
          overflow-y: auto; display: flex; flex-direction: column; gap: .75rem; }
```

The remaining component rules are given alongside their components in Tasks 4–7.

- [ ] **Step 4: Create the jsdom shims**

Create `studio/frontend/test/mockReactFlow.ts` (React Flow cannot measure nodes in jsdom
without these; adapted from the official testing guide):

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
    offsetHeight: { get() { return parseFloat(this.style.height) || 1; } },
    offsetWidth: { get() { return parseFloat(this.style.width) || 1; } },
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

- [ ] **Step 5: Install and run the tests**

Run: `cd studio/frontend && npm install && npm test`
Expected: the smoke test and all four token tests pass. If the smoke test fails with
"parent container needs a width and a height", the wrapper `<div style={{ width: 800,
height: 600 }}>` is missing — React Flow needs explicit dimensions in jsdom.

- [ ] **Step 6: Commit**

```bash
git status --porcelain | grep node_modules && echo "STOP: fix .gitignore first"
git add studio/frontend
git commit -m "feat(studio): frontend scaffolding and the design system"
```

---

### Task 2: Pure modules — DTO mapping, gate phrasing, model mix

**Files:**
- Create: `studio/frontend/src/types.ts`
- Create: `studio/frontend/src/graph.ts`
- Create: `studio/frontend/src/gates.ts`
- Create: `studio/frontend/src/models.ts`
- Test: `studio/frontend/src/graph.test.ts`, `src/gates.test.ts`, `src/models.test.ts`

**Interfaces:**
- Produces (all pure, no React import):
  - `types.ArgSpec`, `types.AgentRef`, `types.IOPath`, `types.StepDef`, `types.ArtefactContract`, `types.Gate`, `types.PipelineDTO`, `types.NodeDTO`, `types.EdgeDTO`, `types.RunDetail`, `types.NodeRunState`, `types.Finding`, `types.Tier`.
  - `graph.toFlow(dto, steps) -> { nodes, edges }`, `graph.fromFlow(nodes, edges) -> PipelineDTO`, `graph.makeNode(step, position, existingIds)`, `graph.edgeId(from, to)`, `graph.DEFAULT_GATE`.
  - `gates.gateLabel(gate) -> string`, `gates.gateSentence(gate, targetLabel) -> string`.
  - `models.resolveTier(node, agent, defaults) -> Tier | null`, `models.isOverridden(node, agent, defaults) -> boolean`, `models.mixFor(nodes, steps, defaults) -> Record<Tier, number>`, `models.worstTier(step, node, defaults) -> Tier | null`.

`fromFlow` must never emit React Flow's transient fields (`selected`, `dragging`,
`measured`, `width`, `height`), and must omit `arg_values` / `models` when empty so a
pipeline with no overrides serialises exactly as it did before those fields existed.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/graph.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import * as graph from './graph';
import type { PipelineDTO, StepDef } from './types';

const STEPS: Record<string, StepDef> = {
  'doc-ingest': {
    id: 'doc-ingest', label: 'Document Ingestion', phase: 'discovery', skill: 'doc-ingest',
    args_allowed: [
      { flag: '--dry-run', takes_value: false, value_pattern: null, note: '' },
      { flag: '--file', takes_value: true, value_pattern: '^[A-Za-z0-9._/-]{1,200}$', note: '' },
    ],
    args_default: [], interactive: false,
    agents: [{ name: 'doc-ingest-digester', fan_out: '1 per doc' }],
    consumes: [{ path: 'docs/kb/**', note: '' }],
    produces: [{ path: 'docs/implr/kb-index/master-synthesis.md', note: '' }],
    produces_artefact: null, description: 'd', available: true,
  },
  'dev-planner': {
    id: 'dev-planner', label: 'Planning', phase: 'planning', skill: 'dev-planner',
    args_allowed: [{ flag: '--all', takes_value: false, value_pattern: null, note: '' }],
    args_default: ['--all'], interactive: true,
    agents: [{ name: 'plan-worker', fan_out: '1 per requirement' }],
    consumes: [], produces: [], produces_artefact: 'plan',
    description: 'p', available: true,
  },
};

const DTO: PipelineDTO = {
  version: 1,
  nodes: [
    {
      id: 'ingest', step: 'doc-ingest', args: ['--file'],
      arg_values: { '--file': 'docs/kb/a.md' },
      models: { 'doc-ingest-digester': 'haiku' },
      position: { x: 10, y: 20 },
    },
    { id: 'plan', step: 'dev-planner', args: ['--all'], position: { x: 200, y: 20 } },
  ],
  edges: [
    {
      from: 'ingest', to: 'plan',
      gate: { type: 'artifact', artefact: 'requirement', quantifier: 'all', require: { status: 'approved' } },
    },
  ],
};

describe('toFlow', () => {
  it('maps nodes with their step definition into data', () => {
    const { nodes } = graph.toFlow(DTO, STEPS);

    expect(nodes[0].id).toBe('ingest');
    expect(nodes[0].type).toBe('step');
    expect(nodes[0].data.label).toBe('Document Ingestion');
    expect(nodes[0].data.args).toEqual(['--file']);
    expect(nodes[0].data.argValues).toEqual({ '--file': 'docs/kb/a.md' });
    expect(nodes[0].data.models).toEqual({ 'doc-ingest-digester': 'haiku' });
    expect(nodes[0].data.available).toBe(true);
  });

  it('defaults arg_values and models to empty objects', () => {
    const { nodes } = graph.toFlow(DTO, STEPS);

    expect(nodes[1].data.argValues).toEqual({});
    expect(nodes[1].data.models).toEqual({});
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
    expect(edges[0].target).toBe('plan');
    expect(edges[0].type).toBe('gate');
    expect(edges[0].data!.gate.type).toBe('artifact');
  });

  it('gives every edge a stable deterministic id', () => {
    expect(graph.toFlow(DTO, STEPS).edges[0].id).toBe(graph.toFlow(DTO, STEPS).edges[0].id);
  });
});

describe('fromFlow', () => {
  it('round-trips a pipeline unchanged', () => {
    const { nodes, edges } = graph.toFlow(DTO, STEPS);

    expect(graph.fromFlow(nodes, edges)).toEqual(DTO);
  });

  it('omits arg_values and models when empty', () => {
    const { nodes, edges } = graph.toFlow(DTO, STEPS);

    const dto = graph.fromFlow(nodes, edges);

    expect('arg_values' in dto.nodes[1]).toBe(false);
    expect('models' in dto.nodes[1]).toBe(false);
    // ...but keeps them where they are set.
    expect(dto.nodes[0].arg_values).toEqual({ '--file': 'docs/kb/a.md' });
  });

  it('strips React Flow transient fields from the DTO', () => {
    const { nodes, edges } = graph.toFlow(DTO, STEPS);
    const dirty = nodes.map((n) => ({
      ...n, selected: true, dragging: true,
      measured: { width: 100, height: 40 }, width: 100, height: 40,
    }));

    const serialized = JSON.stringify(graph.fromFlow(dirty as typeof nodes, edges));

    for (const field of ['selected', 'dragging', 'measured', 'label']) {
      expect(serialized).not.toContain(field);
    }
  });
});

describe('makeNode', () => {
  it('seeds args from args_default and generates a unique id', () => {
    const first = graph.makeNode(STEPS['dev-planner'], { x: 0, y: 0 }, []);
    const second = graph.makeNode(STEPS['dev-planner'], { x: 0, y: 0 }, [first.id]);

    expect(first.id).toBe('dev-planner');
    expect(second.id).toBe('dev-planner-2');
    expect(first.data.args).toEqual(['--all']);
    expect(first.data.argValues).toEqual({});
    expect(first.data.models).toEqual({});
  });
});
```

Create `studio/frontend/src/gates.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { gateLabel, gateSentence } from './gates';

describe('gateLabel', () => {
  it('renders nothing for an unconditional edge', () => {
    expect(gateLabel({ type: 'none' })).toBe('');
  });

  it('names a manual gate', () => {
    expect(gateLabel({ type: 'manual' })).toBe('approval');
  });

  it('renders an artefact condition compactly', () => {
    expect(gateLabel({
      type: 'artifact', artefact: 'plan', quantifier: 'any', require: { status: 'ready' },
    })).toBe('any plan status=ready');
  });

  it('appends approval for a combined gate', () => {
    expect(gateLabel({
      type: 'artifact+manual', artefact: 'requirement', quantifier: 'all',
      require: { status: 'approved' },
    })).toBe('all requirement status=approved + approval');
  });
});

describe('gateSentence', () => {
  it('explains an unconditional edge', () => {
    expect(gateSentence({ type: 'none' }, 'Planning'))
      .toBe('Planning starts as soon as the previous step succeeds.');
  });

  it('explains a manual gate', () => {
    expect(gateSentence({ type: 'manual' }, 'Planning'))
      .toBe('Planning waits for you to approve.');
  });

  it('explains an any-quantifier artefact gate in plain words', () => {
    expect(gateSentence({
      type: 'artifact', artefact: 'plan', quantifier: 'any', require: { status: 'ready' },
    }, 'Implementation'))
      .toBe('Implementation starts once at least one plan is ready.');
  });

  it('explains an all-quantifier combined gate', () => {
    expect(gateSentence({
      type: 'artifact+manual', artefact: 'requirement', quantifier: 'all',
      require: { status: 'approved' },
    }, 'Planning'))
      .toBe('Planning starts once every requirement is approved, and you approve.');
  });

  it('handles a condition with no required status', () => {
    expect(gateSentence({
      type: 'artifact', artefact: 'review', quantifier: 'any', require: {},
    }, 'Release'))
      .toBe('Release starts once at least one review exists.');
  });
});
```

Create `studio/frontend/src/models.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import * as models from './models';
import type { StepDef } from './types';

const STEP: StepDef = {
  id: 'dev-executor', label: 'Implementation', phase: 'build', skill: 'dev-executor',
  args_allowed: [], args_default: [], interactive: false,
  agents: [
    { name: 'arch-excerpter', fan_out: '1 per plan' },
    { name: 'plan-runner', fan_out: '1 per plan' },
    { name: 'task-executor', fan_out: '1 per task' },
  ],
  consumes: [], produces: [], produces_artefact: null,
  description: '', available: true,
};

const DEFAULTS = {
  'arch-excerpter': 'sonnet' as const,
  'plan-runner': 'opus' as const,
  'task-executor': 'opus' as const,
};

const node = (m: Record<string, string> = {}) => ({ step: 'dev-executor', models: m });

describe('resolveTier', () => {
  it('falls back to the project default', () => {
    expect(models.resolveTier(node(), 'task-executor', DEFAULTS)).toBe('opus');
  });

  it('prefers a node override', () => {
    expect(models.resolveTier(node({ 'task-executor': 'sonnet' }), 'task-executor', DEFAULTS))
      .toBe('sonnet');
  });

  it('returns null when neither the node nor the project sets a tier', () => {
    // A fully commented-out agents: block is normal - every agent then runs on
    // its own built-in default and the UI must say so rather than invent one.
    expect(models.resolveTier(node(), 'task-executor', {})).toBeNull();
  });
});

describe('isOverridden', () => {
  it('is false when the node matches the default', () => {
    expect(models.isOverridden(node({ 'task-executor': 'opus' }), 'task-executor', DEFAULTS))
      .toBe(false);
  });

  it('is true when the node differs from the default', () => {
    expect(models.isOverridden(node({ 'task-executor': 'haiku' }), 'task-executor', DEFAULTS))
      .toBe(true);
  });
});

describe('mixFor', () => {
  it('counts every agent of every node by resolved tier', () => {
    const mix = models.mixFor([node(), node()], { 'dev-executor': STEP }, DEFAULTS);

    expect(mix).toEqual({ haiku: 0, sonnet: 2, opus: 4 });
  });

  it('reflects an override in the aggregate', () => {
    const mix = models.mixFor(
      [node({ 'task-executor': 'haiku' })], { 'dev-executor': STEP }, DEFAULTS,
    );

    expect(mix).toEqual({ haiku: 1, sonnet: 1, opus: 1 });
  });

  it('ignores nodes whose step is not in the registry', () => {
    expect(models.mixFor([{ step: 'ghost', models: {} }], {}, DEFAULTS))
      .toEqual({ haiku: 0, sonnet: 0, opus: 0 });
  });
});

describe('worstTier', () => {
  it('reports the most expensive tier a step will use', () => {
    expect(models.worstTier(STEP, node(), DEFAULTS)).toBe('opus');
  });

  it('drops when every agent is overridden downward', () => {
    const cheap = node({ 'plan-runner': 'haiku', 'task-executor': 'haiku' });

    expect(models.worstTier(STEP, cheap, DEFAULTS)).toBe('sonnet');
  });

  it('is null for a step that dispatches nothing', () => {
    const planned: StepDef = { ...STEP, agents: [] };

    expect(models.worstTier(planned, node(), DEFAULTS)).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `./graph`, `./gates`, `./models`

- [ ] **Step 3: Write `types.ts`**

```ts
export type Tier = 'haiku' | 'sonnet' | 'opus';
export type GateType = 'none' | 'manual' | 'artifact' | 'artifact+manual';
export type Quantifier = 'all' | 'any';

export interface ArgSpec {
  flag: string;
  takes_value: boolean;
  value_pattern: string | null;
  note: string;
}

export interface AgentRef { name: string; fan_out: string }
export interface IOPath { path: string; note: string }

export interface StepDef {
  id: string;
  label: string;
  phase: string;
  skill: string;
  args_allowed: ArgSpec[];
  args_default: string[];
  interactive: boolean;
  agents: AgentRef[];
  consumes: IOPath[];
  produces: IOPath[];
  produces_artefact: string | null;
  description: string;
  available: boolean;
}

/** Straight from frontmatter-rules.json + status-vocabulary.json. Never copied. */
export interface ArtefactContract {
  states: string[];
  fields: string[];
  required: string[];
  optional: string[];
  path_globs: string[];
  machine: string;
}

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
  arg_values?: Record<string, string>;
  models?: Record<string, string>;
  position: { x: number; y: number };
}

export interface EdgeDTO { from: string; to: string; gate: Gate }
export interface PipelineDTO { version: number; nodes: NodeDTO[]; edges: EdgeDTO[] }

export interface Finding { code: string; message: string; node_id: string | null }

export interface NodeRunState {
  node_id: string;
  status: string;
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
  kind: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface StepNodeData {
  label: string;
  step: string;
  phase: string;
  args: string[];
  argValues: Record<string, string>;
  models: Record<string, string>;
  interactive: boolean;
  available: boolean;
  status?: string;
}

export interface GateEdgeData { gate: Gate }
```

- [ ] **Step 4: Write `graph.ts`**

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
        label: def ? def.label : n.step,
        step: n.step,
        phase: def ? def.phase : 'unknown',
        args: [...n.args],
        argValues: { ...(n.arg_values ?? {}) },
        models: { ...(n.models ?? {}) },
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
    nodes: nodes.map((n): NodeDTO => {
      const dto: NodeDTO = {
        id: n.id,
        step: n.data.step,
        args: [...n.data.args],
        position: { x: n.position.x, y: n.position.y },
      };
      // Omitted when empty so a pipeline with no overrides serialises exactly
      // as it did before these fields existed, keeping diffs readable.
      if (Object.keys(n.data.argValues).length) dto.arg_values = { ...n.data.argValues };
      if (Object.keys(n.data.models).length) dto.models = { ...n.data.models };
      return dto;
    }),
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
      argValues: {},
      models: {},
      interactive: step.interactive,
      available: step.available,
    },
  };
}
```

Note the DTO ordering: `id`, `step`, `args`, then the optional keys, then `position`. The
backend's `_node_to_dict` emits the same order, which keeps the round-trip test honest and
`pipeline.yaml` diffs stable.

- [ ] **Step 5: Write `gates.ts`**

```ts
/** Gate rendering. Two forms: a compact label for the canvas, and a plain
 *  sentence for the editor - `any plan status=ready` is precise but not friendly,
 *  and the operator designing a pipeline deserves the friendly version too. */
import type { Gate } from './types';

export function gateLabel(gate: Gate): string {
  if (gate.type === 'none') return '';
  if (gate.type === 'manual') return 'approval';

  const requirements = Object.entries(gate.require ?? {})
    .map(([field, value]) => `${field}=${value}`)
    .join(' ');
  const base = `${gate.quantifier ?? 'all'} ${gate.artefact ?? '?'} ${requirements}`.trim();

  return gate.type === 'artifact+manual' ? `${base} + approval` : base;
}

export function gateSentence(gate: Gate, targetLabel: string): string {
  if (gate.type === 'none') {
    return `${targetLabel} starts as soon as the previous step succeeds.`;
  }
  if (gate.type === 'manual') {
    return `${targetLabel} waits for you to approve.`;
  }

  const many = gate.quantifier === 'any' ? 'at least one' : 'every';
  const status = gate.require?.status;
  const condition = status ? `is ${status}` : 'exists';
  const approval = gate.type === 'artifact+manual' ? ', and you approve' : '';

  return `${targetLabel} starts once ${many} ${gate.artefact ?? 'artefact'} ${condition}${approval}.`;
}
```

- [ ] **Step 6: Write `models.ts`**

```ts
/** Model tier resolution and aggregation.
 *
 *  Tier lives per agent, not per step, because implr.config.yaml already maps
 *  each subagent to haiku | sonnet | opus. A node override shadows that default;
 *  neither being set is legal and means "the agent's own built-in default", which
 *  the UI reports rather than guessing at. */
import type { StepDef, Tier } from './types';

export const TIERS: Tier[] = ['haiku', 'sonnet', 'opus'];

interface NodeLike { step: string; models: Record<string, string> }
type Defaults = Record<string, string>;

const isTier = (v: string | undefined): v is Tier =>
  v !== undefined && (TIERS as string[]).includes(v);

export function resolveTier(node: NodeLike, agent: string, defaults: Defaults): Tier | null {
  const override = node.models[agent];
  if (isTier(override)) return override;
  const fallback = defaults[agent];
  return isTier(fallback) ? fallback : null;
}

export function isOverridden(node: NodeLike, agent: string, defaults: Defaults): boolean {
  const override = node.models[agent];
  if (!isTier(override)) return false;
  return override !== defaults[agent];
}

export function mixFor(
  nodes: NodeLike[],
  steps: Record<string, StepDef>,
  defaults: Defaults,
): Record<Tier, number> {
  const mix: Record<Tier, number> = { haiku: 0, sonnet: 0, opus: 0 };
  for (const node of nodes) {
    const step = steps[node.step];
    if (!step) continue;
    for (const agent of step.agents) {
      const tier = resolveTier(node, agent.name, defaults);
      if (tier) mix[tier] += 1;
    }
  }
  return mix;
}

export function worstTier(step: StepDef, node: NodeLike, defaults: Defaults): Tier | null {
  let worst = -1;
  for (const agent of step.agents) {
    const tier = resolveTier(node, agent.name, defaults);
    if (tier) worst = Math.max(worst, TIERS.indexOf(tier));
  }
  return worst < 0 ? null : TIERS[worst];
}
```

- [ ] **Step 7: Run the tests and commit**

Run: `cd studio/frontend && npm test`
Expected: all graph, gates and models tests pass.

```bash
git add studio/frontend/src/types.ts studio/frontend/src/graph.ts studio/frontend/src/gates.ts studio/frontend/src/models.ts studio/frontend/src/*.test.ts
git commit -m "feat(studio): pure DTO mapping, gate phrasing, and model-mix logic"
```

---

### Task 3: API client and Zustand store

**Files:**
- Create: `studio/frontend/src/api.ts`, `studio/frontend/src/store.ts`
- Test: `studio/frontend/src/api.test.ts`, `studio/frontend/src/store.test.ts`

**Interfaces:**
- Produces:
  - `api.getRegistry()` → `{ steps, phases, tiers, contracts, agent_defaults }`, plus `getPipeline`, `putPipeline`, `startRun`, `getRun`, `answer`, `approve`, `retry`, `skip`, `cancel`, `openStream`.
  - `api.ValidationError` — thrown on 422, carrying `findings: Finding[]`.
  - `store.usePipelineStore` — `nodes`, `edges`, `steps`, `agentDefaults`, `contracts`, `findings`, `runId`, `runStatus`, `nodeStates`, `logs`, `question`, `cursor`; actions `onNodesChange`, `onEdgesChange`, `onConnect`, `addStepNode`, `setNodeArgs`, `setArgValue`, `setNodeModel`, `setEdgeGate`, `loadFrom`, `toDTO`, `setFindings`, `applyRunDetail`, `applyEvents`.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/api.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from './api';

const okJson = (body: unknown) =>
  Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);

describe('api client', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('uses relative /api paths so no host is hardcoded', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(okJson({ steps: [], phases: [] }));

    await api.getRegistry();

    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url.startsWith('/api/')).toBe(true);
    expect(url).not.toContain('http');
  });

  it('accepts 202 from startRun as success', async () => {
    // The backend returns 202 Accepted: the run has started, not finished.
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      Promise.resolve({
        ok: true, status: 202, json: () => Promise.resolve({ run_id: 'r1' }),
      } as Response),
    );

    await expect(api.startRun()).resolves.toEqual({ run_id: 'r1' });
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
  });

  it('throws a plain error on other failures', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      Promise.resolve({
        ok: false, status: 409, json: () => Promise.resolve({ detail: 'no pipeline saved' }),
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
  args_allowed: [
    { flag: '--dry-run', takes_value: false, value_pattern: null, note: '' },
    { flag: '--file', takes_value: true, value_pattern: '^[a-z./]+$', note: '' },
  ],
  args_default: [], interactive: false,
  agents: [{ name: 'doc-ingest-digester', fan_out: '1' }],
  consumes: [], produces: [], produces_artefact: null,
  description: '', available: true,
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
    nodes: [], edges: [], steps: {}, agentDefaults: {}, agentTools: {}, contracts: {},
    findings: [], runId: null, runStatus: null, nodeStates: {}, logs: {},
    question: null, cursor: 0,
  });

const load = () =>
  usePipelineStore.getState().loadFrom(DTO, { 'doc-ingest': STEP }, {}, {}, {});

describe('pipeline store', () => {
  beforeEach(reset);

  it('loads a pipeline into flow state', () => {
    load();

    expect(usePipelineStore.getState().nodes).toHaveLength(2);
    expect(usePipelineStore.getState().edges).toHaveLength(1);
  });

  it('adds a palette step at the drop position with a unique id', () => {
    load();

    usePipelineStore.getState().addStepNode(STEP, { x: 50, y: 60 });

    const ids = usePipelineStore.getState().nodes.map((n) => n.id);
    expect(ids).toContain('doc-ingest');
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('setNodeArgs replaces the object rather than mutating it', () => {
    load();
    const before = usePipelineStore.getState().nodes[0];

    usePipelineStore.getState().setNodeArgs('a', ['--dry-run']);

    const after = usePipelineStore.getState().nodes[0];
    expect(after).not.toBe(before);
    expect(after.data.args).toEqual(['--dry-run']);
    expect(before.data.args).toEqual([]);
  });

  it('setNodeArgs drops the value of a flag that was deselected', () => {
    // A stale arg_values entry fails backend validation with orphan-arg-value,
    // so unchecking a flag must clear its value here.
    load();
    usePipelineStore.getState().setNodeArgs('a', ['--file']);
    usePipelineStore.getState().setArgValue('a', '--file', 'docs/kb/a.md');
    expect(usePipelineStore.getState().nodes[0].data.argValues).toEqual({
      '--file': 'docs/kb/a.md',
    });

    usePipelineStore.getState().setNodeArgs('a', []);

    expect(usePipelineStore.getState().nodes[0].data.argValues).toEqual({});
  });

  it('setNodeModel records and clears a tier override', () => {
    load();

    usePipelineStore.getState().setNodeModel('a', 'doc-ingest-digester', 'haiku');
    expect(usePipelineStore.getState().nodes[0].data.models)
      .toEqual({ 'doc-ingest-digester': 'haiku' });

    usePipelineStore.getState().setNodeModel('a', 'doc-ingest-digester', null);
    expect(usePipelineStore.getState().nodes[0].data.models).toEqual({});
  });

  it('setEdgeGate updates the gate in edge data', () => {
    load();
    const id = usePipelineStore.getState().edges[0].id;

    usePipelineStore.getState().setEdgeGate(id, { type: 'manual' });

    expect(usePipelineStore.getState().edges[0].data?.gate.type).toBe('manual');
  });

  it('applyRunDetail tints nodes with their run status', () => {
    load();
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
    load();

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
    load();

    usePipelineStore.getState().applyEvents([
      { seq: 1, node_id: 'a', kind: 'question',
        payload: { question_id: 'q1', prompt_md: 'Which db?', options: ['Postgres'] },
        created_at: '' },
    ]);
    expect(usePipelineStore.getState().question?.question_id).toBe('q1');
    expect(usePipelineStore.getState().question?.options).toEqual(['Postgres']);

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
import type {
  ArtefactContract, Finding, PipelineDTO, RunDetail, RunEvent, StepDef, Tier,
} from './types';

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
    const detail = (body as { detail?: unknown }).detail;
    throw new Error(
      typeof detail === 'string' ? detail : `request failed: ${response.status}`,
    );
  }
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

export interface RegistryResponse {
  steps: StepDef[];
  phases: string[];
  tiers: Tier[];
  contracts: Record<string, ArtefactContract>;
  agent_defaults: Record<string, string>;
  agent_tools: Record<string, string[]>;
}

export const getRegistry = () => request<RegistryResponse>('/registry');

export const getPipeline = () =>
  request<{ pipeline: PipelineDTO; exists: boolean }>('/pipeline');

export const putPipeline = (dto: PipelineDTO) =>
  request<{ pipeline: PipelineDTO }>('/pipeline', { method: 'PUT', body: JSON.stringify(dto) });

/** Returns 202 as soon as the run starts - it does NOT wait for it to finish. */
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
import type {
  ArtefactContract, Finding, Gate, PipelineDTO, RunDetail, RunEvent, StepDef, Tier,
} from './types';

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
  agentDefaults: Record<string, string>;
  agentTools: Record<string, string[]>;
  contracts: Record<string, ArtefactContract>;
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
  setArgValue: (nodeId: string, flag: string, value: string) => void;
  setNodeModel: (nodeId: string, agent: string, tier: Tier | null) => void;
  setEdgeGate: (id: string, gate: Gate) => void;
  loadFrom: (
    dto: PipelineDTO,
    steps: Record<string, StepDef>,
    agentDefaults: Record<string, string>,
    agentTools: Record<string, string[]>,
    contracts: Record<string, ArtefactContract>,
  ) => void;
  toDTO: () => PipelineDTO;
  setFindings: (findings: Finding[]) => void;
  applyRunDetail: (detail: RunDetail) => void;
  applyEvents: (events: RunEvent[], cursor?: number) => void;
}

/** Replace one node's data, never mutate it. */
const patchNode = (
  nodes: FlowNode[],
  nodeId: string,
  patch: (data: FlowNode['data']) => FlowNode['data'],
): FlowNode[] =>
  nodes.map((n) => (n.id === nodeId ? { ...n, data: patch(n.data) } : n));

export const usePipelineStore = create<PipelineState>((set, get) => ({
  nodes: [],
  edges: [],
  steps: {},
  agentDefaults: {},
  agentTools: {},
  contracts: {},
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
      nodes: patchNode(get().nodes, nodeId, (data) => {
        const selected = new Set(args);
        // Drop values for flags that are no longer selected: a stale entry fails
        // backend validation with orphan-arg-value.
        const argValues = Object.fromEntries(
          Object.entries(data.argValues).filter(([flag]) => selected.has(flag)),
        );
        return { ...data, args: [...args], argValues };
      }),
    }),

  setArgValue: (nodeId, flag, value) =>
    set({
      nodes: patchNode(get().nodes, nodeId, (data) => ({
        ...data,
        argValues: { ...data.argValues, [flag]: value },
      })),
    }),

  setNodeModel: (nodeId, agent, tier) =>
    set({
      nodes: patchNode(get().nodes, nodeId, (data) => {
        const models = { ...data.models };
        // null clears the override, returning the agent to the project default
        // rather than pinning it to whatever that default happens to be today.
        if (tier === null) delete models[agent];
        else models[agent] = tier;
        return { ...data, models };
      }),
    }),

  setEdgeGate: (id, gate) =>
    set({
      edges: get().edges.map((e) => (e.id === id ? { ...e, data: { ...e.data, gate } } : e)),
    }),

  loadFrom: (dto, steps, agentDefaults, agentTools, contracts) => {
    const { nodes, edges } = toFlow(dto, steps);
    set({ nodes, edges, steps, agentDefaults, agentTools, contracts, findings: [] });
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

- [ ] **Step 5: Run the tests and commit**

Run: `cd studio/frontend && npm test`
Expected: all api and store tests pass.

```bash
git add studio/frontend/src/api.ts studio/frontend/src/store.ts studio/frontend/src/api.test.ts studio/frontend/src/store.test.ts
git commit -m "feat(studio): API client and Zustand graph/run store"
```

---

### Task 4: Node card, gate edge, and the searchable palette

**Files:**
- Create: `studio/frontend/src/nodes/StepNode.tsx`, `src/edges/GateEdge.tsx`, `src/panels/Palette.tsx`, `src/flowTypes.ts`
- Modify: `studio/frontend/src/app.css`
- Test: `src/nodes/StepNode.test.tsx`, `src/panels/Palette.test.tsx`

**Interfaces:**
- Produces:
  - `StepNode` — a card with a **status stripe**, label, node id, args (with values), and an **agent tier-dot row**. Class `step-node--<status>` carries run state.
  - `GateEdge` — smooth-step path with the gate chip in an `EdgeLabelRenderer`.
  - `flowTypes.nodeTypes` / `edgeTypes` — **module-scope constants**.
  - `Palette` — a search box plus phase-grouped steps; unimplemented steps `draggable={false}`, dashed and explained.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/nodes/StepNode.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { ReactFlow, ReactFlowProvider } from '@xyflow/react';
import { describe, expect, it } from 'vitest';
import { nodeTypes } from '../flowTypes';
import type { FlowNode } from '../graph';

function renderNode(data: Partial<FlowNode['data']>) {
  const nodes: FlowNode[] = [{
    id: 'ingest',
    type: 'step',
    position: { x: 0, y: 0 },
    data: {
      label: 'Document Ingestion', step: 'doc-ingest', phase: 'discovery',
      args: [], argValues: {}, models: {},
      interactive: false, available: true, ...data,
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

  it('shows a flag with its value so the canvas is readable at a glance', () => {
    renderNode({ args: ['--file'], argValues: { '--file': 'docs/kb/a.md' } });

    expect(screen.getByText('--file docs/kb/a.md')).toBeInTheDocument();
  });

  it('says so when no arguments are selected', () => {
    renderNode({ args: [] });

    expect(screen.getByText(/no arguments/i)).toBeInTheDocument();
  });

  it('badges an interactive step', () => {
    renderNode({ interactive: true });

    expect(screen.getByTitle(/asks questions/i)).toBeInTheDocument();
  });

  it('badges an unimplemented step', () => {
    renderNode({ available: false });

    expect(screen.getByTitle(/not implemented/i)).toBeInTheDocument();
  });

  it('applies a status class so run state is visible', () => {
    const { container } = renderNode({ status: 'failed' });

    expect(container.querySelector('.step-node--failed')).toBeTruthy();
  });

  it('exposes a configure affordance', () => {
    renderNode({});

    expect(screen.getByLabelText(/configure/i)).toBeInTheDocument();
  });

  it('nodeTypes is a stable module-scope object', () => {
    expect(nodeTypes).toBe(nodeTypes);
  });
});
```

Create `studio/frontend/src/panels/Palette.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Palette from './Palette';
import type { StepDef } from '../types';

const base = {
  args_allowed: [], args_default: [], interactive: false,
  agents: [], consumes: [], produces: [], produces_artefact: null,
};

const steps: StepDef[] = [
  { ...base, id: 'doc-ingest', label: 'Document Ingestion', phase: 'discovery',
    skill: 'doc-ingest', description: 'Indexes the knowledge base.', available: true },
  { ...base, id: 'sec-review', label: 'Security Checks', phase: 'verify',
    skill: 'sec-review', description: 'Security review.', available: false },
];

const props = { steps, phases: ['discovery', 'verify'], agentDefaults: {}, onDragStart: vi.fn() };

describe('Palette', () => {
  it('groups steps under their phase heading', () => {
    render(<Palette {...props} />);

    expect(screen.getByText('discovery')).toBeInTheDocument();
    expect(screen.getByText('verify')).toBeInTheDocument();
  });

  it('makes an available step draggable', () => {
    render(<Palette {...props} />);

    expect(screen.getByText('Document Ingestion').closest('[draggable]'))
      .toHaveAttribute('draggable', 'true');
  });

  it('does not make an unimplemented step draggable, and explains why', () => {
    render(<Palette {...props} />);

    const planned = screen.getByText('Security Checks').closest('.chip-step')!;
    expect(planned).toHaveAttribute('draggable', 'false');
    expect(planned.className).toContain('chip-step--off');
    expect(planned).toHaveAttribute('title', expect.stringMatching(/not implemented/i));
  });

  it('omits a phase heading with no steps', () => {
    render(<Palette {...props} phases={['discovery', 'verify', 'build']} />);

    expect(screen.queryByText('build')).not.toBeInTheDocument();
  });

  it('filters by label and by description', async () => {
    render(<Palette {...props} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'knowledge');

    expect(screen.getByText('Document Ingestion')).toBeInTheDocument();
    expect(screen.queryByText('Security Checks')).not.toBeInTheDocument();
  });

  it('says so when nothing matches', async () => {
    render(<Palette {...props} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'zzzz');

    expect(screen.getByText(/no step matches/i)).toBeInTheDocument();
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

/** Renders one flag, with its value when it has one, so the canvas stays
 *  readable without opening the configurator. */
const flagText = (flag: string, values: Record<string, string>) =>
  values[flag] ? `${flag} ${values[flag]}` : flag;

export default function StepNode({ id, data, selected }: NodeProps<FlowNode>) {
  const status = data.status ?? 'pending';

  return (
    <div
      className={`step-node step-node--${status}${data.available ? '' : ' step-node--planned'}`}
      data-selected={selected || undefined}
    >
      <Handle type="target" position={Position.Left} className="port" />

      <div className="step-node__stripe" />

      <div className="step-node__body">
        <div className="step-node__top">
          <span className="step-node__name">{data.label}</span>
          {data.interactive && (
            <span className="step-node__badge" title="Interactive - asks questions during the run">?</span>
          )}
          {!data.available && (
            <span className="step-node__badge" title="Planned - this skill is not implemented yet">!</span>
          )}
          <span className="step-node__id">{id}</span>
        </div>

        <div className="step-node__args">
          {data.args.length === 0 ? (
            <span className="step-node__empty">no arguments</span>
          ) : (
            data.args.map((arg) => (
              <code key={arg}>{flagText(arg, data.argValues)}</code>
            ))
          )}
        </div>

        <div className="step-node__agents">
          <span className="step-node__phase">{data.phase}</span>
          <span className="step-node__cog nodrag" aria-label="Configure step" role="img">⚙</span>
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="port" />
    </div>
  );
}
```

The agent tier dots need the registry, which a React Flow node does not receive. Read them
from the store instead — add to the imports and render them inside `step-node__agents`:

```tsx
import { usePipelineStore } from '../store';
import { resolveTier } from '../models';
// ...inside the component, above the return:
const steps = usePipelineStore((s) => s.steps);
const defaults = usePipelineStore((s) => s.agentDefaults);
const def = steps[data.step];
const dots = (def?.agents ?? []).map((agent) => ({
  name: agent.name,
  tier: resolveTier({ step: data.step, models: data.models }, agent.name, defaults),
}));
// ...and inside step-node__agents, before the phase span:
{dots.map((d) => (
  <span
    key={d.name}
    className="tierdot"
    style={{ background: d.tier ? `var(--tier-${d.tier})` : 'var(--edge)' }}
    title={`${d.name} · ${d.tier ?? 'project default'}`}
  />
))}
```

Create `studio/frontend/src/edges/GateEdge.tsx`:

```tsx
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';
import { gateLabel } from '../gates';
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
            className="gate-chip nodrag nopan"
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
import { useMemo, useState } from 'react';
import { worstTier } from '../models';
import type { StepDef } from '../types';

interface Props {
  steps: StepDef[];
  phases: string[];
  agentDefaults: Record<string, string>;
  onDragStart: (event: React.DragEvent, stepId: string) => void;
}

export default function Palette({ steps, phases, agentDefaults, onDragStart }: Props) {
  const [query, setQuery] = useState('');

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return steps;
    return steps.filter((s) =>
      `${s.label} ${s.id} ${s.description}`.toLowerCase().includes(q),
    );
  }, [steps, query]);

  const groups = phases
    .map((phase) => ({ phase, items: matches.filter((s) => s.phase === phase) }))
    .filter((g) => g.items.length > 0);

  return (
    <aside className="rail">
      <div className="rail__search">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search steps…"
          aria-label="Search steps"
        />
      </div>

      <div className="rail__list">
        {groups.length === 0 && (
          <p className="rail__empty">No step matches “{query}”.</p>
        )}

        {groups.map(({ phase, items }) => (
          <section key={phase}>
            <h3 className="phase">{phase}</h3>
            {items.map((step) => {
              const tier = worstTier(step, { step: step.id, models: {} }, agentDefaults);
              return (
                <div
                  key={step.id}
                  className={`chip-step${step.available ? '' : ' chip-step--off'}`}
                  draggable={step.available}
                  onDragStart={(e) => step.available && onDragStart(e, step.id)}
                  title={
                    step.available
                      ? step.description
                      : `${step.description} (not implemented yet - the skill does not exist)`
                  }
                >
                  <span
                    className="tierdot"
                    style={{ background: tier ? `var(--tier-${tier})` : 'var(--edge)' }}
                  />
                  <span>{step.label}</span>
                  <span className="chip-step__meta">
                    {!step.available && <span className="tag tag--soon">soon</span>}
                    {step.available && step.interactive && <span className="tag tag--ask">asks</span>}
                  </span>
                </div>
              );
            })}
          </section>
        ))}
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Add the component styles**

Append to `studio/frontend/src/app.css` the rules for `.rail__search`, `.rail__list`,
`.rail__empty`, `.phase`, `.chip-step`, `.chip-step--off`, `.chip-step__meta`, `.tag`,
`.tierdot`, `.step-node*`, `.port` and `.gate-chip`. Every colour must be a `var(--…)`;
`src/tokens.test.ts` fails the build otherwise. The status stripe reads its colour from the
node's status class:

```css
.step-node { width: 196px; background: var(--raised); color: var(--text);
             border: 1px solid var(--hair); border-radius: var(--r-md);
             box-shadow: var(--shadow-1); overflow: hidden; cursor: pointer;
             transition: border-color var(--t), box-shadow var(--t); }
.step-node:hover { border-color: var(--text-faint); box-shadow: var(--shadow-2); }
.step-node[data-selected] { border-color: var(--cyan); box-shadow: 0 0 0 3px var(--cyan-sunk); }
.step-node--planned { border-style: dashed; }
.step-node__stripe { height: 3px; background: var(--st-pending); }
.step-node--running          .step-node__stripe { background: var(--st-running); }
.step-node--succeeded        .step-node__stripe { background: var(--st-succeeded); }
.step-node--failed           .step-node__stripe { background: var(--st-failed); }
.step-node--blocked          .step-node__stripe { background: var(--st-blocked); }
.step-node--awaiting-input   .step-node__stripe { background: var(--st-input); }
.step-node--awaiting-approval .step-node__stripe { background: var(--st-approval); }
.step-node--skipped          .step-node__stripe { background: var(--st-skipped); }

.tierdot { width: 7px; height: 7px; border-radius: 999px; flex: none; display: inline-block; }
.gate-chip { background: var(--gate-sunk); color: var(--gate); font-family: var(--mono);
             font-size: 10px; font-weight: 600; padding: .16rem .45rem; border-radius: 999px;
             border: 1px solid var(--gate); cursor: pointer; white-space: nowrap; }
```

- [ ] **Step 5: Run the tests and commit**

Run: `cd studio/frontend && npm test`

```bash
git add studio/frontend/src/nodes studio/frontend/src/edges studio/frontend/src/panels/Palette.tsx studio/frontend/src/flowTypes.ts studio/frontend/src/app.css
git commit -m "feat(studio): node card, gate edge, and searchable palette"
```

---

### Task 5: The step configurator

**Files:**
- Create: `studio/frontend/src/modal/Modal.tsx`
- Create: `studio/frontend/src/modal/StepConfig.tsx`
- Test: `studio/frontend/src/modal/StepConfig.test.tsx`

This is the centrepiece of the design. Everything it renders comes from
`GET /api/registry` — no status, tier, agent name or flag is hardcoded.

**Interfaces:**
- Produces:
  - `Modal({ icon, title, subtitle, tabs, active, onTab, footer, onClose, children })` — the dialog shell. Renders a scrim, traps initial focus on the close button, closes on Escape and on scrim click.
  - `StepConfig({ nodeId, onClose, onEditGate })` — four tabs, reading and writing through the store.
  - `StepConfig` tab contents exactly as the spec's table describes.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/modal/StepConfig.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StepConfig from './StepConfig';
import { usePipelineStore } from '../store';
import type { ArtefactContract, PipelineDTO, StepDef } from '../types';

const EXECUTOR: StepDef = {
  id: 'dev-executor', label: 'Implementation', phase: 'build', skill: 'dev-executor',
  args_allowed: [
    { flag: '--all', takes_value: false, value_pattern: null, note: 'every ready plan' },
    { flag: '--task', takes_value: true, value_pattern: '^[A-Za-z0-9._#/-]{1,80}$',
      note: 'one task id only' },
  ],
  args_default: ['--all'],
  interactive: false,
  agents: [
    { name: 'plan-runner', fan_out: '1 per plan, cap 5' },
    { name: 'task-executor', fan_out: '1 per task' },
  ],
  consumes: [{ path: 'docs/implr/plans/**', note: 'status: ready' }],
  produces: [{ path: 'src/**', note: 'implementation' }],
  produces_artefact: null,
  description: 'Implements ready plans task by task.',
  available: true,
};

const PLANNER: StepDef = {
  ...EXECUTOR,
  id: 'dev-planner', label: 'Planning', phase: 'planning', skill: 'dev-planner',
  args_allowed: [{ flag: '--all', takes_value: false, value_pattern: null, note: '' }],
  agents: [{ name: 'plan-worker', fan_out: '1 per requirement' }],
  consumes: [], produces: [], produces_artefact: 'plan',
  interactive: true, description: 'Writes plans.',
};

const PLANNED: StepDef = {
  ...EXECUTOR, id: 'sec-review', label: 'Security Checks', phase: 'verify',
  skill: 'sec-review', agents: [], available: false, description: 'Security review.',
};

const PLAN_CONTRACT: ArtefactContract = {
  states: ['ready', 'in-progress', 'done', 'blocked', 'needs-rework'],
  fields: ['plan_id', 'status', 'title'],
  required: ['plan_id', 'status', 'title'],
  optional: ['rework_cr'],
  path_globs: ['docs/implr/plans/functional/*.md'],
  machine: 'plan',
};

const DTO: PipelineDTO = {
  version: 1,
  nodes: [
    { id: 'build', step: 'dev-executor', args: ['--all'], position: { x: 0, y: 0 } },
    { id: 'plan', step: 'dev-planner', args: [], position: { x: 200, y: 0 } },
    { id: 'sec', step: 'sec-review', args: [], position: { x: 400, y: 0 } },
  ],
  edges: [{ from: 'plan', to: 'build', gate: { type: 'artifact', artefact: 'plan',
            quantifier: 'any', require: { status: 'ready' } } }],
};

const DEFAULTS = { 'plan-runner': 'opus', 'task-executor': 'opus', 'plan-worker': 'sonnet' };

beforeEach(() => {
  usePipelineStore.setState({
    nodes: [], edges: [], steps: {}, agentDefaults: {}, agentTools: {}, contracts: {},
    findings: [], runId: null, runStatus: null, nodeStates: {}, logs: {},
    question: null, cursor: 0,
  });
  usePipelineStore.getState().loadFrom(
    DTO,
    { 'dev-executor': EXECUTOR, 'dev-planner': PLANNER, 'sec-review': PLANNED },
    DEFAULTS,
    { 'plan-runner': ['Read', 'Write', 'Edit', 'Bash', 'Agent'] },
    { plan: PLAN_CONTRACT },
  );
});

const open = (nodeId = 'build') =>
  render(<StepConfig nodeId={nodeId} onClose={vi.fn()} onEditGate={vi.fn()} />);

const node = (id: string) => usePipelineStore.getState().nodes.find((n) => n.id === id)!;

describe('StepConfig — Run tab', () => {
  it('leads with the step description', () => {
    open();

    expect(screen.getByText('Implements ready plans task by task.')).toBeInTheDocument();
  });

  it('offers only that step args_allowed', () => {
    open();

    expect(screen.getByLabelText('--all')).toBeInTheDocument();
    expect(screen.getByLabelText('--task')).toBeInTheDocument();
    expect(screen.queryByLabelText('--verbose')).not.toBeInTheDocument();
  });

  it('reflects the selected args', () => {
    open();

    expect(screen.getByLabelText('--all')).toBeChecked();
    expect(screen.getByLabelText('--task')).not.toBeChecked();
  });

  it('toggling a flag updates the node', async () => {
    open();

    await userEvent.click(screen.getByLabelText('--all'));

    expect(node('build').data.args).toEqual([]);
  });

  it('disables the value input until its flag is selected', async () => {
    open();
    const value = screen.getByLabelText(/value for --task/i);
    expect(value).toBeDisabled();

    await userEvent.click(screen.getByLabelText('--task'));

    expect(screen.getByLabelText(/value for --task/i)).toBeEnabled();
  });

  it('records a value against the flag', async () => {
    open();
    await userEvent.click(screen.getByLabelText('--task'));

    await userEvent.type(screen.getByLabelText(/value for --task/i), 'PLAN-F-004#3');

    expect(node('build').data.argValues).toEqual({ '--task': 'PLAN-F-004#3' });
  });

  it('warns when a selected value-taking flag has no value', async () => {
    open();

    await userEvent.click(screen.getByLabelText('--task'));

    expect(screen.getByText(/needs a value/i)).toBeInTheDocument();
  });

  it('warns when a value does not match its pattern', async () => {
    open();
    await userEvent.click(screen.getByLabelText('--task'));

    await userEvent.type(screen.getByLabelText(/value for --task/i), 'has space');

    expect(screen.getByText(/not a valid value/i)).toBeInTheDocument();
  });

  it('explains that an unimplemented step will not run', () => {
    open('sec');

    expect(screen.getByText(/not implemented/i)).toBeInTheDocument();
  });

  it('explains that an interactive step will ask questions', () => {
    open('plan');

    expect(screen.getByText(/asks questions/i)).toBeInTheDocument();
  });
});

describe('StepConfig — Agents tab', () => {
  const goAgents = async () => {
    await userEvent.click(screen.getByRole('tab', { name: /agents/i }));
  };

  it('lists the agents the step dispatches, with fan-out', async () => {
    open();
    await goAgents();

    expect(screen.getByText('plan-runner')).toBeInTheDocument();
    expect(screen.getByText('task-executor')).toBeInTheDocument();
    expect(screen.getByText('1 per plan, cap 5')).toBeInTheDocument();
  });

  it('defaults each tier to the project default', async () => {
    open();
    await goAgents();

    const card = screen.getByTestId('agent-task-executor');
    expect(within(card).getByRole('button', { name: /opus/i }))
      .toHaveAttribute('aria-pressed', 'true');
  });

  it('changing a tier records an override and marks it', async () => {
    open();
    await goAgents();

    const card = screen.getByTestId('agent-task-executor');
    await userEvent.click(within(card).getByRole('button', { name: /sonnet/i }));

    expect(node('build').data.models).toEqual({ 'task-executor': 'sonnet' });
    expect(within(screen.getByTestId('agent-task-executor')).getByText(/overridden/i))
      .toBeInTheDocument();
  });

  it('selecting the project default again clears the override', async () => {
    open();
    await goAgents();
    const card = () => screen.getByTestId('agent-task-executor');
    await userEvent.click(within(card()).getByRole('button', { name: /sonnet/i }));

    await userEvent.click(within(card()).getByRole('button', { name: /opus/i }));

    // Cleared, not pinned: the node inherits whatever the project default becomes.
    expect(node('build').data.models).toEqual({});
  });

  it('shows the declared tool grant and marks the mutating tools', async () => {
    open();
    await goAgents();

    const card = screen.getByTestId('agent-plan-runner');
    expect(within(card).getByTitle(/changes the repository/i)).toBeInTheDocument();
  });

  it('says so for a step that dispatches nothing', async () => {
    open('sec');
    await goAgents();

    expect(screen.getByText(/dispatches no subagents/i)).toBeInTheDocument();
  });
});

describe('StepConfig — Input and Output tabs', () => {
  it('lists what the step reads', async () => {
    open();
    await userEvent.click(screen.getByRole('tab', { name: /input/i }));

    expect(screen.getByText('docs/implr/plans/**')).toBeInTheDocument();
  });

  it('says plainly that the input tab is descriptive', async () => {
    open();
    await userEvent.click(screen.getByRole('tab', { name: /input/i }));

    expect(screen.getByText(/descriptive/i)).toBeInTheDocument();
  });

  it('shows the inbound gate and offers to edit it', async () => {
    const onEditGate = vi.fn();
    render(<StepConfig nodeId="build" onClose={vi.fn()} onEditGate={onEditGate} />);
    await userEvent.click(screen.getByRole('tab', { name: /input/i }));

    await userEvent.click(screen.getByRole('button', { name: /edit condition/i }));

    expect(onEditGate).toHaveBeenCalledWith('plan__build');
  });

  it('renders the artefact contract for a step that produces one', async () => {
    open('plan');
    await userEvent.click(screen.getByRole('tab', { name: /output/i }));

    expect(screen.getByText('plan_id')).toBeInTheDocument();
    expect(screen.getByText('needs-rework')).toBeInTheDocument();
    expect(screen.getByText('docs/implr/plans/functional/*.md')).toBeInTheDocument();
  });

  it('explains the absence of a contract for a step that only writes files', async () => {
    open();
    await userEvent.click(screen.getByRole('tab', { name: /output/i }));

    expect(screen.getByText('src/**')).toBeInTheDocument();
    expect(screen.getByText(/no frontmatter contract/i)).toBeInTheDocument();
  });
});

describe('StepConfig — footer', () => {
  it('names pipeline.yaml alone when nothing is overridden', () => {
    open();

    expect(screen.getByTestId('writes').textContent).toContain('pipeline.yaml');
    expect(screen.getByTestId('writes').textContent).not.toContain('implr.config.yaml');
  });

  it('adds implr.config.yaml once a tier is overridden', async () => {
    open();
    await userEvent.click(screen.getByRole('tab', { name: /agents/i }));
    const card = screen.getByTestId('agent-task-executor');

    await userEvent.click(within(card).getByRole('button', { name: /haiku/i }));

    expect(screen.getByTestId('writes').textContent).toContain('implr.config.yaml');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `./StepConfig`

- [ ] **Step 3: Write `Modal.tsx`**

```tsx
import { useEffect, useRef } from 'react';

interface Props {
  icon: string;
  title: string;
  subtitle?: React.ReactNode;
  tabs?: { id: string; label: string; count?: number }[];
  active?: string;
  onTab?: (id: string) => void;
  footer?: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
}

export default function Modal({
  icon, title, subtitle, tabs, active, onTab, footer, onClose, children,
}: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="scrim" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal__head">
          <div className="modal__icon" aria-hidden="true">{icon}</div>
          <div className="modal__title">
            <h2>{title}</h2>
            {subtitle && <p className="modal__sub">{subtitle}</p>}
          </div>
          <button ref={closeRef} className="x" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {tabs && tabs.length > 0 && (
          <div className="tabs" role="tablist">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={tab.id === active}
                onClick={() => onTab?.(tab.id)}
              >
                {tab.label}
                {tab.count !== undefined && <span className="count">{tab.count}</span>}
              </button>
            ))}
          </div>
        )}

        <div className="modal__body">{children}</div>

        {footer && <div className="modal__foot">{footer}</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write `StepConfig.tsx`**

```tsx
import { useMemo, useState } from 'react';
import Modal from './Modal';
import { gateLabel } from '../gates';
import { isOverridden, resolveTier, TIERS } from '../models';
import { usePipelineStore } from '../store';
import type { ArgSpec, Tier } from '../types';

/** Tools that can change the repository. Marked so the operator can see, at a
 *  glance, which agents write and which only read. */
const MUTATING = new Set(['Write', 'Edit', 'Bash', 'Agent', 'Task', 'NotebookEdit']);

const TABS = [
  { id: 'run', label: 'Run' },
  { id: 'agents', label: 'Agents' },
  { id: 'input', label: 'Input' },
  { id: 'output', label: 'Output' },
];

interface Props {
  nodeId: string;
  onClose: () => void;
  onEditGate: (edgeId: string) => void;
}

export default function StepConfig({ nodeId, onClose, onEditGate }: Props) {
  const [tab, setTab] = useState('run');

  const node = usePipelineStore((s) => s.nodes.find((n) => n.id === nodeId));
  const edges = usePipelineStore((s) => s.edges);
  const steps = usePipelineStore((s) => s.steps);
  const contracts = usePipelineStore((s) => s.contracts);
  const defaults = usePipelineStore((s) => s.agentDefaults);
  const agentTools = usePipelineStore((s) => s.agentTools);
  const setNodeArgs = usePipelineStore((s) => s.setNodeArgs);
  const setArgValue = usePipelineStore((s) => s.setArgValue);
  const setNodeModel = usePipelineStore((s) => s.setNodeModel);

  if (!node) return null;
  const step = steps[node.data.step];

  const overridden = useMemo(
    () => (step?.agents ?? []).some((a) =>
      isOverridden({ step: node.data.step, models: node.data.models }, a.name, defaults)),
    [step, node.data.step, node.data.models, defaults],
  );

  const initials = (step?.label ?? node.data.step)
    .split(' ').map((w) => w[0]).join('').slice(0, 2);

  const footer = (
    <>
      <div className="writes" data-testid="writes">
        <span>Applying writes to</span>
        <code>pipeline.yaml → nodes[{nodeId}]</code>
        {overridden && <code>implr.config.yaml → agents:</code>}
      </div>
      <div className="spacer" />
      <button className="btn btn--ghost" onClick={onClose}>Cancel</button>
      <button className="btn btn--primary" onClick={onClose}>Apply</button>
    </>
  );

  return (
    <Modal
      icon={initials}
      title={step?.label ?? node.data.step}
      subtitle={<>node <code>{nodeId}</code> · step <code>{node.data.step}</code> · phase <code>{node.data.phase}</code></>}
      tabs={TABS.map((t) => ({
        ...t,
        count: t.id === 'run' ? node.data.args.length
             : t.id === 'agents' ? (step?.agents.length ?? 0)
             : undefined,
      }))}
      active={tab}
      onTab={setTab}
      footer={footer}
      onClose={onClose}
    >
      {tab === 'run' && <RunPane />}
      {tab === 'agents' && <AgentsPane />}
      {tab === 'input' && <InputPane />}
      {tab === 'output' && <OutputPane />}
    </Modal>
  );

  // ---- panes -------------------------------------------------------------

  function RunPane() {
    const selected = new Set(node!.data.args);

    const toggle = (flag: string) => {
      const next = selected.has(flag)
        ? node!.data.args.filter((a) => a !== flag)
        : [...node!.data.args, flag];
      setNodeArgs(nodeId, next);
    };

    const problem = (spec: ArgSpec): string | null => {
      if (!spec.takes_value || !selected.has(spec.flag)) return null;
      const value = node!.data.argValues[spec.flag] ?? '';
      if (!value) return 'needs a value';
      if (spec.value_pattern && !new RegExp(`^(?:${spec.value_pattern})$`).test(value)) {
        return 'not a valid value';
      }
      return null;
    };

    return (
      <div className="pane">
        <p className="pane__lead">{step?.description}</p>

        {step && !step.available && (
          <div className="banner banner--warn">
            This step is declared but <b>not implemented</b> — no{' '}
            <code>skills/{step.skill}/SKILL.md</code> exists. You can draw it into the
            process now; a run will refuse to start it.
          </div>
        )}

        {step?.interactive && (
          <div className="banner banner--info">
            This step <b>asks questions</b> mid-run. They surface in Run mode and your
            answer goes back into the same session.
          </div>
        )}

        <div className="grp">
          <p className="lbl">Arguments</p>
          {(step?.args_allowed ?? []).map((spec) => {
            const on = selected.has(spec.flag);
            const issue = problem(spec);
            return (
              <div key={spec.flag} className="arg" data-on={on ? '1' : '0'}>
                <input
                  id={`arg-${spec.flag}`}
                  type="checkbox"
                  checked={on}
                  onChange={() => toggle(spec.flag)}
                />
                <label className="arg__flag" htmlFor={`arg-${spec.flag}`}>{spec.flag}</label>
                {spec.note && <span className="arg__note">{spec.note}</span>}

                {spec.takes_value && (
                  <>
                    <input
                      className="arg__val"
                      type="text"
                      aria-label={`Value for ${spec.flag}`}
                      disabled={!on}
                      value={node!.data.argValues[spec.flag] ?? ''}
                      onChange={(e) => setArgValue(nodeId, spec.flag, e.target.value)}
                      placeholder="value…"
                    />
                    {issue && <span className="arg__issue">{issue}</span>}
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function AgentsPane() {
    if (!step?.agents.length) {
      return (
        <div className="pane">
          <p className="pane__lead">
            This step <b>dispatches no subagents</b> yet — the skill does not exist. Once it
            does, its agents appear here with their own model tiers.
          </p>
        </div>
      );
    }

    return (
      <div className="pane">
        <p className="pane__lead">
          Model tier is chosen <b>per agent</b>, not per step, because that is how implr
          already works: <code>implr.config.yaml</code> maps each subagent to a tier.
          Defaults are shown; a change is written back to that block.
        </p>

        {step.agents.map((agent) => {
          const current = resolveTier(
            { step: node!.data.step, models: node!.data.models }, agent.name, defaults,
          );
          const isOver = isOverridden(
            { step: node!.data.step, models: node!.data.models }, agent.name, defaults,
          );
          const tools = agentTools[agent.name] ?? [];

          return (
            <div className="agent" key={agent.name} data-testid={`agent-${agent.name}`}>
              <div className="agent__top">
                <span
                  className="tierdot"
                  style={{ background: current ? `var(--tier-${current})` : 'var(--edge)' }}
                />
                <span className="agent__name">{agent.name}</span>
                <span className="agent__fan">{agent.fan_out}</span>
                {isOver && <span className="tag tag--over">overridden</span>}
              </div>

              <div className="field">
                <label>Model tier</label>
                <div className="tiers">
                  {TIERS.map((tier) => (
                    <button
                      key={tier}
                      type="button"
                      aria-pressed={current === tier}
                      onClick={() =>
                        // Selecting the project default clears the override rather
                        // than pinning it, so the node keeps inheriting.
                        setNodeModel(nodeId, agent.name,
                          defaults[agent.name] === tier ? null : (tier as Tier))
                      }
                    >
                      <span className="tierdot" style={{ background: `var(--tier-${tier})` }} />
                      {tier}
                      {defaults[agent.name] === tier && <span className="tiers__def">default</span>}
                    </button>
                  ))}
                </div>
              </div>

              {tools.length > 0 && (
                <div className="field">
                  <label>Tool grant · declared</label>
                  <div className="tools">
                    {tools.map((tool) => (
                      <span
                        key={tool}
                        className={`tool${MUTATING.has(tool) ? ' tool--w' : ''}`}
                        title={MUTATING.has(tool) ? `${tool} changes the repository` : tool}
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  function InputPane() {
    const inbound = edges.filter((e) => e.target === nodeId);

    return (
      <div className="pane">
        <p className="pane__lead">
          What this step reads before it does anything, and the condition that must hold for
          it to start.
        </p>

        <div className="grp">
          <p className="lbl">Reads</p>
          {(step?.consumes ?? []).length === 0 && (
            <div className="io__row"><span>nothing yet</span></div>
          )}
          {(step?.consumes ?? []).map((c) => (
            <div className="io__row" key={c.path}>
              <span className="arrow">→</span>
              <span className="p">{c.path}</span>
              {c.note && <span className="n">{c.note}</span>}
            </div>
          ))}
        </div>

        <div className="grp">
          <p className="lbl">Entry condition</p>
          {inbound.length === 0 ? (
            <div className="banner banner--info">
              No incoming connection — this is a starting step and runs immediately.
            </div>
          ) : (
            inbound.map((e) => (
              <div className="io__row" key={e.id}>
                <span className="p">{e.source}</span>
                <span className="arrow">⟶</span>
                <span>{gateLabel(e.data?.gate ?? { type: 'none' }) || 'no condition'}</span>
                <button
                  className="btn btn--ghost"
                  onClick={() => onEditGate(e.id)}
                >
                  Edit condition
                </button>
              </div>
            ))
          )}
        </div>

        <div className="banner banner--warn">
          <b>Descriptive only.</b> Nothing validates these inputs yet — a per-skill input
          contract does not exist today. Shown so the graph is legible, not to imply
          enforcement.
        </div>
      </div>
    );
  }

  function OutputPane() {
    const artefact = step?.produces_artefact ? contracts[step.produces_artefact] : null;
    const outbound = edges.filter((e) => e.source === nodeId);

    return (
      <div className="pane">
        <p className="pane__lead">
          {artefact
            ? `This step produces ${step!.produces_artefact} artefacts. The contract below is the real frontmatter rule — the same vocabulary a downstream condition reads, which is why an impossible condition is caught while you design.`
            : 'This step writes files rather than status-carrying artefacts, so there is no frontmatter contract to enforce.'}
        </p>

        {(step?.produces ?? []).length > 0 && (
          <div className="grp">
            <p className="lbl">Writes</p>
            {step!.produces.map((w) => (
              <div className="io__row" key={w.path}>
                <span className="arrow">←</span>
                <span className="p">{w.path}</span>
                {w.note && <span className="n">{w.note}</span>}
              </div>
            ))}
          </div>
        )}

        {artefact && (
          <div className="schema">
            <div className="schema__hd">
              <span>{step!.produces_artefact}</span>
              <span className="path">{artefact.path_globs.join(', ')}</span>
              <span className="machine">{artefact.machine} machine</span>
            </div>
            <div className="fields">
              {artefact.required.map((f) => <span key={f} className="f f--req">{f}</span>)}
              {artefact.optional.map((f) => <span key={f} className="f">{f}</span>)}
            </div>
            <div className="states">
              {artefact.states.map((s) => <span key={s} className="state">{s}</span>)}
            </div>
          </div>
        )}

        {outbound.length > 0 && (
          <div className="grp">
            <p className="lbl">Feeds</p>
            {outbound.map((e) => (
              <div className="io__row" key={e.id}>
                <span className="arrow">⟶</span>
                <span>{steps[
                  usePipelineStore.getState().nodes.find((n) => n.id === e.target)?.data.step ?? ''
                ]?.label ?? e.target}</span>
                <span className="n">
                  {gateLabel(e.data?.gate ?? { type: 'none' }) || 'no condition'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
}
```

Two notes on the above:

- `agentTools` is a store field of type `Record<string, string[]>`, populated from
  `GET /api/registry`'s `agent_tools` (Plan 4 Task 1). Add it to `PipelineState` alongside
  `agentDefaults`, default it to `{}`, and set it in `loadFrom`. Read it with
  `usePipelineStore((s) => s.agentTools)` at the top of `AgentsPane` rather than through
  `getState()` inside the map, so the pane re-renders if it arrives late. **Never** hardcode
  a tool list in the frontend — the whole point is that it is the agent's own declaration.
- The `problem()` regex wraps `value_pattern` in `^(?:…)$` rather than trusting the pattern
  to be anchored. The backend uses `re.fullmatch`, and this keeps the two in agreement.

- [ ] **Step 5: Add the modal styles**

Append `.scrim`, `.modal*`, `.tabs`, `.pane*`, `.grp`, `.arg*`, `.agent*`, `.tiers*`,
`.tool*`, `.schema*`, `.f*`, `.state*`, `.io__row`, `.banner*` and `.writes` rules to
`app.css`, all built from tokens. The modal animates in with `transform` and `opacity`
only, and `tokens.css` already disables that under `prefers-reduced-motion`.

- [ ] **Step 6: Run the tests and commit**

Run: `cd studio/frontend && npm test`
Expected: every StepConfig test passes, including the tool-grant assertion.

```bash
git add studio/frontend/src/modal
git commit -m "feat(studio): step configurator with per-agent model tiers"
```

---

### Task 6: The gate editor

**Files:**
- Create: `studio/frontend/src/modal/GateConfig.tsx`
- Test: `studio/frontend/src/modal/GateConfig.test.tsx`

**Interfaces:**
- Produces: `GateConfig({ edgeId, onClose })` — the same `Modal` shell with one pane. Dropdowns populated from `contracts`; renders `gateSentence` beneath them; warns about the empty-match-set rule and about per-node approval.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GateConfig from './GateConfig';
import { usePipelineStore } from '../store';

// ...same fixture setup as StepConfig.test.tsx...

describe('GateConfig', () => {
  it('offers only the states of the chosen artefact', async () => {
    render(<GateConfig edgeId="plan__build" onClose={vi.fn()} />);

    const status = screen.getByLabelText(/required status/i);
    expect([...status.querySelectorAll('option')].map((o) => o.textContent))
      .toEqual(['(any status)', 'ready', 'in-progress', 'done', 'blocked', 'needs-rework']);
  });

  it('restates the condition in plain words', () => {
    render(<GateConfig edgeId="plan__build" onClose={vi.fn()} />);

    expect(screen.getByText(/Implementation starts once at least one plan is ready\./))
      .toBeInTheDocument();
  });

  it('switching to a condition-free type hides the artefact controls', async () => {
    render(<GateConfig edgeId="plan__build" onClose={vi.fn()} />);

    await userEvent.selectOptions(screen.getByLabelText(/condition/i), 'none');

    expect(screen.queryByLabelText(/required status/i)).not.toBeInTheDocument();
    expect(usePipelineStore.getState().edges[0].data!.gate).toEqual({ type: 'none' });
  });

  it('states the empty-match-set rule for an artefact condition', () => {
    render(<GateConfig edgeId="plan__build" onClose={vi.fn()} />);

    expect(screen.getByText(/never vacuously true/i)).toBeInTheDocument();
  });

  it('warns that approval is recorded per step', async () => {
    render(<GateConfig edgeId="plan__build" onClose={vi.fn()} />);

    await userEvent.selectOptions(screen.getByLabelText(/condition/i), 'manual');

    expect(screen.getByText(/per step, not per connection/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement, run, commit**

`GateConfig` mirrors `StepConfig`'s structure: read the edge and `contracts` from the
store, render four `<select>`s (condition, artefact, how many, required status), write via
`setEdgeGate`, and render `gateSentence(gate, targetStepLabel)` in a `banner--info`. Guard
the artefact controls behind `type === 'artifact' || type === 'artifact+manual'`.

```bash
git add studio/frontend/src/modal/GateConfig.tsx studio/frontend/src/modal/GateConfig.test.tsx
git commit -m "feat(studio): gate editor with plain-language restatement"
```

---

### Task 7: Health panel, run panel, and the app shell

**Files:**
- Create: `studio/frontend/src/panels/HealthPanel.tsx`, `src/panels/RunPanel.tsx`, `src/App.tsx`
- Test: `src/panels/HealthPanel.test.tsx`, `src/panels/RunPanel.test.tsx`

**Interfaces:**
- Produces:
  - `HealthPanel` — design-mode rail: step / connection / gated counts, the validation findings, and the **model-mix meter** from `models.mixFor`.
  - `RunPanel` — run-mode rail: run id and status, the selected node's status, its log, and the state's affordance. A question renders its options as buttons **and** a free-text box.
  - `App` — the shell: app bar with mode switch, Save and Run; the three-pane layout; and modal routing (node click → `StepConfig`, edge click → `GateConfig`).

- [ ] **Step 1: Write the failing tests**

Key assertions to cover — write them out in full following the style above:

```tsx
// HealthPanel
it('counts steps, connections and gated connections');
it('renders the model mix from every node agent');
it('names the most expensive step so the operator knows where the cost is');
it('lists validation findings with their message');
it('shows an empty state before the first save');

// RunPanel
it('prompts to press Run when there is no run yet');
it('shows the selected node status and its log');
it('renders a question with the agent own options as buttons');
it('sends a typed answer');
it('offers Retry, Skip and Abort for a failed node');
it('offers Approve for a node awaiting approval');
it('explains that a blocked node advances on its own and offers no approve button');
```

That last one matters: `blocked` and `awaiting-approval` look similar and mean opposite
things — one needs the operator, the other explicitly does not. Conflating them is the
most likely usability bug in Run mode, so it gets a test.

- [ ] **Step 2: Write `HealthPanel.tsx`**

```tsx
import { mixFor, TIERS, worstTier } from '../models';
import { usePipelineStore } from '../store';

export default function HealthPanel({ onConfigure }: { onConfigure: (nodeId: string) => void }) {
  const nodes = usePipelineStore((s) => s.nodes);
  const edges = usePipelineStore((s) => s.edges);
  const steps = usePipelineStore((s) => s.steps);
  const defaults = usePipelineStore((s) => s.agentDefaults);
  const findings = usePipelineStore((s) => s.findings);

  const nodeLikes = nodes.map((n) => ({ step: n.data.step, models: n.data.models }));
  const mix = mixFor(nodeLikes, steps, defaults);
  const total = TIERS.reduce((sum, t) => sum + mix[t], 0) || 1;
  const gated = edges.filter((e) => (e.data?.gate.type ?? 'none') !== 'none').length;

  // Where the cost is. Model tier is the dominant cost driver, so surfacing the
  // most expensive step saves the operator opening every configurator.
  const priciest = nodes
    .map((n) => ({
      id: n.id,
      label: n.data.label,
      tier: steps[n.data.step]
        ? worstTier(steps[n.data.step], { step: n.data.step, models: n.data.models }, defaults)
        : null,
    }))
    .filter((n) => n.tier)
    .sort((a, b) => TIERS.indexOf(b.tier!) - TIERS.indexOf(a.tier!))[0];

  return (
    <aside className="aside">
      <h3>Pipeline</h3>

      <div className="card">
        <dl className="kv"><dt>Steps</dt><dd>{nodes.length}</dd></dl>
        <dl className="kv"><dt>Connections</dt><dd>{edges.length}</dd></dl>
        <dl className="kv"><dt>With a condition</dt><dd>{gated}</dd></dl>
      </div>

      <p className="lbl">Model mix</p>
      <div className="card">
        <div className="meter">
          {TIERS.filter((t) => mix[t] > 0).map((t) => (
            <i
              key={t}
              style={{ width: `${(mix[t] / total) * 100}%`, background: `var(--tier-${t})` }}
              title={`${t} × ${mix[t]}`}
            />
          ))}
        </div>
        <div className="meterkey">
          {TIERS.map((t) => (
            <span key={t}>
              <span className="tierdot" style={{ background: `var(--tier-${t})` }} />
              {t} ×{mix[t]}
            </span>
          ))}
        </div>
        {priciest && (
          <p className="hintline">
            Most expensive: <b>{priciest.label}</b> on {priciest.tier}.{' '}
            <button className="btn btn--ghost" onClick={() => onConfigure(priciest.id)}>
              Configure
            </button>
          </p>
        )}
      </div>

      {findings.length > 0 && (
        <>
          <p className="lbl">{findings.length} issue{findings.length === 1 ? '' : 's'}</p>
          <div className="card">
            {findings.map((f) => (
              <p key={f.code + f.message} className="finding">{f.message}</p>
            ))}
          </div>
        </>
      )}

      <div className="banner banner--info">
        Saving writes <code>docs/implr/config/pipeline.yaml</code>, and any tier overrides
        to <code>implr.config.yaml</code>.
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Write `RunPanel.tsx`**

Follow the structure of the first plan's RunPanel, with these changes:

- Render the question's `options` as buttons above the textarea; clicking one sends it
  immediately. The free-text box stays, because the operator may want to say something the
  agent did not offer.
- Distinguish `blocked` from `awaiting-approval` explicitly. `blocked` renders an
  explanation that it advances on its own and offers **no** Approve button; only
  `awaiting-approval` offers Approve.
- Show `state.error` in a `.err` block for a failed node, above Retry / Skip / Abort.

- [ ] **Step 4: Write `App.tsx`**

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Background, Controls, MiniMap, ReactFlow, ReactFlowProvider, useReactFlow,
} from '@xyflow/react';
import * as api from './api';
import { edgeTypes, nodeTypes } from './flowTypes';
import GateConfig from './modal/GateConfig';
import StepConfig from './modal/StepConfig';
import HealthPanel from './panels/HealthPanel';
import Palette from './panels/Palette';
import RunPanel from './panels/RunPanel';
import { usePipelineStore } from './store';
import type { StepDef, Tier } from './types';

type Dialog = { kind: 'step'; id: string } | { kind: 'gate'; id: string } | null;

function Studio() {
  const store = usePipelineStore();
  const { screenToFlowPosition } = useReactFlow();
  const [steps, setSteps] = useState<StepDef[]>([]);
  const [phases, setPhases] = useState<string[]>([]);
  const [mode, setMode] = useState<'design' | 'run'>('design');
  const [dialog, setDialog] = useState<Dialog>(null);
  const socket = useRef<WebSocket | null>(null);
  const dragged = useRef<string | null>(null);

  useEffect(() => {
    void (async () => {
      const registry = await api.getRegistry();
      setSteps(registry.steps);
      setPhases(registry.phases);
      const byId = Object.fromEntries(registry.steps.map((s) => [s.id, s]));
      const { pipeline } = await api.getPipeline();
      usePipelineStore.getState().loadFrom(
        pipeline, byId, registry.agent_defaults, registry.agent_tools, registry.contracts,
      );
    })();
    return () => socket.current?.close();
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const stepId = dragged.current ?? event.dataTransfer.getData('text/plain');
      const step = steps.find((s) => s.id === stepId);
      if (!step) return;
      usePipelineStore.getState().addStepNode(
        step, screenToFlowPosition({ x: event.clientX, y: event.clientY }),
      );
      dragged.current = null;
    },
    [steps, screenToFlowPosition],
  );

  const onSave = async (): Promise<boolean> => {
    try {
      await api.putPipeline(usePipelineStore.getState().toDTO());
      usePipelineStore.getState().setFindings([]);
      return true;
    } catch (e) {
      usePipelineStore.getState().setFindings(
        e instanceof api.ValidationError
          ? e.findings
          : [{ code: 'error', message: String(e), node_id: null }],
      );
      return false;
    }
  };

  const refresh = async (runId: string) => {
    usePipelineStore.getState().applyRunDetail(await api.getRun(runId));
  };

  const onRun = async () => {
    if (!(await onSave())) return;
    // startRun returns 202 immediately, so the socket opens while the first step
    // is still working - which is the entire point of Run mode.
    const { run_id } = await api.startRun();
    setMode('run');
    await refresh(run_id);
    socket.current?.close();
    socket.current = api.openStream(run_id, usePipelineStore.getState().cursor, {
      onEvents: (events, cursor) => usePipelineStore.getState().applyEvents(events, cursor),
      onRunStatus: () => void refresh(run_id),
    });
  };

  return (
    <div className="layout">
      <Palette
        steps={steps}
        phases={phases}
        agentDefaults={store.agentDefaults}
        onDragStart={(event, stepId) => {
          dragged.current = stepId;
          event.dataTransfer.setData('text/plain', stepId);
          event.dataTransfer.effectAllowed = 'move';
        }}
      />

      <div
        className="stage"
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }}
      >
        <div className="appbar">
          <div className="seg" role="group" aria-label="Mode">
            <button aria-pressed={mode === 'design'} onClick={() => setMode('design')}>Design</button>
            <button aria-pressed={mode === 'run'} onClick={() => setMode('run')}>Run</button>
          </div>
          <div className="spacer" />
          <button className="btn" onClick={onSave}>Save</button>
          <button className="btn btn--primary" onClick={onRun}>Run pipeline</button>
        </div>

        <ReactFlow
          nodes={store.nodes}
          edges={store.edges}
          onNodesChange={store.onNodesChange}
          onEdgesChange={store.onEdgesChange}
          onConnect={store.onConnect}
          onNodeClick={(_, node) => setDialog({ kind: 'step', id: node.id })}
          onEdgeClick={(_, edge) => setDialog({ kind: 'gate', id: edge.id })}
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

      {mode === 'design'
        ? <HealthPanel onConfigure={(id) => setDialog({ kind: 'step', id })} />
        : <RunPanel />}

      {dialog?.kind === 'step' && (
        <StepConfig
          nodeId={dialog.id}
          onClose={() => setDialog(null)}
          onEditGate={(edgeId) => setDialog({ kind: 'gate', id: edgeId })}
        />
      )}
      {dialog?.kind === 'gate' && (
        <GateConfig edgeId={dialog.id} onClose={() => setDialog(null)} />
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

`colorMode="dark"` is passed explicitly rather than `"system"`: dark is the product
default, and React Flow's own controls must match the console rather than the OS.

- [ ] **Step 5: Run the whole frontend suite**

Run: `cd studio/frontend && npm test`

- [ ] **Step 6: Typecheck and build**

Run: `cd studio/frontend && npm run build`
Expected: builds with no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add studio/frontend/src
git commit -m "feat(studio): health panel, run panel, and the console shell"
```

---

## Definition of Done

- [ ] `npm test` in `studio/frontend/` passes.
- [ ] `npm run build` typechecks and builds.
- [ ] `src/tokens.test.ts` passes: the reserved token groups all exist, `app.css` introduces
      **no** saturated hex of its own, there is no `prefers-color-scheme` query, and every
      font stack has a fallback.
- [ ] The console renders dark with no `data-theme` stamp; only `data-theme="light"`
      produces the light palette.
- [ ] `graph.fromFlow` never emits `selected`, `dragging`, `measured`, `width` or `height`,
      and omits `arg_values` / `models` when empty — both proven by test.
- [ ] `toFlow` → `fromFlow` round-trips a pipeline unchanged, including values and overrides.
- [ ] `nodeTypes` and `edgeTypes` are module-scope constants.
- [ ] Clicking a node opens the configurator; clicking an edge opens the gate editor;
      Escape and a scrim click close either.
- [ ] The Run tab offers only that step's `args_allowed`; a value input is **disabled** until
      its flag is selected; a selected value-taking flag with no value, and a value failing
      its `value_pattern`, are both flagged inline before save.
- [ ] Deselecting a flag clears its recorded value, so no `orphan-arg-value` can be saved.
- [ ] The Agents tab lists the step's real agents with fan-out, defaults each tier from
      `agent_defaults`, marks a change as *overridden*, and re-selecting the project default
      **clears** the override rather than pinning it.
- [ ] The Output tab renders the produced artefact's required fields, optional fields, legal
      statuses and path globs — all from `contracts`, none hardcoded.
- [ ] The Input tab states plainly that it is descriptive.
- [ ] The gate editor offers only the states of the chosen artefact and restates the
      condition as a plain sentence.
- [ ] The health panel's model-mix meter reflects every node's agents, and names the most
      expensive step.
- [ ] Run mode distinguishes `blocked` from `awaiting-approval`: only the latter offers
      Approve.
- [ ] `onRun` opens the WebSocket immediately after a `202`, so logs stream while the run is
      still going.
- [ ] No frontend source file contains a hardcoded host, port, implr status, artefact type,
      agent name, model tier, or flag.

## Manual verification (not automatable in jsdom)

HTML5 drag-and-drop cannot be meaningfully simulated in jsdom — `dataTransfer` is not
implemented. Verify by hand, with the backend running as
`implr-studio --fake --workspace <a test project>`:

1. Drag "Document Ingestion" from the palette onto the canvas; a node appears where dropped.
2. Search the palette for "security"; only Security Checks shows, dashed and undraggable.
3. Drag from a node's right port to another's left port; an edge appears.
4. Click the Implementation node → Agents tab → drop `task-executor` to Sonnet. The node's
   tier dots change, the health panel's mix meter shifts, and the footer gains
   `implr.config.yaml`.
5. Run tab → select `--task`, type `PLAN-F-004#3`. Save succeeds. Clear the value; Save is
   rejected with a message naming the flag.
6. Click the `plan → build` edge, set the status to a value from the wrong state machine —
   it is not offered. Hand-edit `pipeline.yaml` to `complete` and reload: Save is rejected
   with a message naming the legal plan states.
7. Press Run pipeline; nodes tint and the log pane fills **while the run is still going**,
   not all at once at the end.
8. Force light mode with `document.documentElement.dataset.theme = 'light'` in the console;
   every pane, modal and chip stays legible.
