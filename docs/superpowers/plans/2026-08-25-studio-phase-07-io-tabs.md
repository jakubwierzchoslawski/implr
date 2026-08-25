# implr Studio — Phase 7: Input / Output tabs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The configurator's last two tabs. The Output tab shows the ten required `plan` fields and its five legal statuses — read from the contract files, not typed into a component.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 6 — the Output tab renders the `contracts` payload it added.

---

## Demo

Click **Specification / Planning** → **Output**:

```
plan        docs/implr/plans/{functional,non-functional}/*.md      plan machine

plan_id*  slug*  title*  linked_requirement*  type*  status*
complexity*  tdd_required*  created_at*  updated_at*     rework_cr

ready   in-progress   done   blocked   needs-rework

* required · the rest optional · pills are the only legal values of status
```

Then **Implementation** → **Output**: `src/**`, `tests/**`, and a line saying there is **no
frontmatter contract** — it writes code, not status-carrying artefacts.

Then **Implementation** → **Input**: the plans glob with `status: ready`, `ARCHITECTURE.md`,
`DEV-STANDARDS.md`, the inbound condition with an **Edit** button that opens Phase 6's editor
— and a banner saying the tab is **descriptive**.

---

## Why this phase is cheap, and why it is last

**It adds no backend at all.** `consumes`, `produces` and `produces_artefact` shipped with the
registry in Phase 1; `contracts` shipped in Phase 6. This phase spends data that already
exists.

That is also why it comes fourth of the four: it is the only one of 4–7 with no server-side
slice, so ordering it earlier would have meant either shipping the payload before anything
rendered it, or rendering a tab against data that was not there yet.

**The value is that it closes the loop.** Phase 6 lets you demand `plan status=ready` on a
connection. Phase 7 shows you, on the step that *produces* plans, that `ready` is one of
exactly five legal values. Same vocabulary, both ends, visibly — which is the argument for the
Python backend made visual.

---

## Scope boundary — not in this phase

- **The Input tab is descriptive and says so.** Nothing validates that a step reads what
  `consumes` claims. A per-skill input contract does not exist, and inventing one here would
  mean asserting a schema the skills do not honour.
- **No authoring.** Phase 8 makes these fields editable for `kind: "agent"` steps. Here they
  are read-only for every step, including authored ones.
- **No artefact preview.** The Output tab shows the *contract*, not the files. Reading actual
  artefacts is a different feature and needs the workspace, which the configurator does not
  have.
- **No `--dry-run` awareness.** The Output tab says what the step writes when it runs for real.
  Phase 18's first-run flow is what explains that a dry run writes nothing.

---

## Global constraints

- Every field, status, glob and path comes from `GET /api/projects/{pid}/registry`. **Nothing
  in these two components contains an implr vocabulary word.** A test greps for that.
- A step with `produces_artefact: null` must render a *reason*, not an empty panel.
- Colours from tokens. Required-field marking uses `--st-failed` for the asterisk, which is
  already reserved.

---

## File Structure

| File | Responsibility |
|---|---|
| `web/src/modal/StepConfig.tsx` | **Modified** — the Input and Output panes; two more tabs. |
| `web/src/app.css` | **Modified** — `.schema`, `.fields`, `.f`, `.state`, `.io__row`. |

That is the whole file list. No Python.

---

### Task 1: The Input pane

**Files:**
- Modify: `web/src/modal/StepConfig.tsx`
- Test: `web/src/modal/StepConfig.test.tsx` (extend)

**Interfaces:**
- The Input pane: `consumes` paths with notes; inbound edges with their condition and an Edit
  button; the descriptive banner.
- `StepConfig` gains an `onEditGate(edgeId)` prop, so the modal can hand off to Phase 6's
  editor rather than nesting a second dialog.

- [ ] **Step 1: Write the failing test**

```tsx
const goInput = () => userEvent.click(screen.getByRole('tab', { name: /input/i }));

describe('StepConfig — Input tab', () => {
  it('lists what the step reads', async () => {
    open(); await goInput();

    expect(screen.getByText('docs/implr/plans/**')).toBeInTheDocument();
    expect(screen.getByText('docs/ARCHITECTURE.md')).toBeInTheDocument();
  });

  it('shows the note beside a path', async () => {
    open(); await goInput();

    expect(screen.getByText('status: ready')).toBeInTheDocument();
  });

  it('says so for a step that reads nothing', async () => {
    open('sec'); await goInput();

    expect(screen.getByText(/nothing yet/i)).toBeInTheDocument();
  });

  it('shows the inbound condition', async () => {
    open(); await goInput();

    expect(screen.getByText('any plan status=ready')).toBeInTheDocument();
  });

  it('names the upstream step, not the node id', async () => {
    // 'plan' means nothing to a reader; 'Planning' does.
    open(); await goInput();

    expect(screen.getByText(/Planning/)).toBeInTheDocument();
  });

  it('offers to edit the condition, handing off rather than nesting a dialog', async () => {
    const onEditGate = vi.fn();
    openWith({ onEditGate }); await goInput();

    await userEvent.click(screen.getByRole('button', { name: /edit condition/i }));

    expect(onEditGate).toHaveBeenCalledWith('plan__build');
  });

  it('says a starting step has no incoming connection', async () => {
    open('ingest'); await goInput();

    expect(screen.getByText(/starting step/i)).toBeInTheDocument();
  });

  it('lists every inbound condition when a node has several', async () => {
    openWith({ nodeId: 'join' }); await goInput();

    expect(screen.getAllByRole('button', { name: /edit condition/i })).toHaveLength(2);
  });

  it('states plainly that the tab is descriptive', async () => {
    // Nothing validates these paths. Implying otherwise would be a lie the UI tells.
    open(); await goInput();

    expect(screen.getByText(/descriptive only/i)).toBeInTheDocument();
  });
});
```

`it('lists every inbound condition when a node has several')` matters because the six-step
template is a chain, so a single-inbound assumption would pass every other test and break on
the first branching pipeline anyone draws.

- [ ] **Step 2: Implement**

```tsx
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
          ) : inbound.map((e) => (
            <div className="io__row" key={e.id}>
              {/* The step's LABEL, not the node id: 'plan' means nothing to a reader. */}
              <span className="p">{labelOf(e.source)}</span>
              <span className="arrow">⟶</span>
              <span>{gateLabel(e.data?.gate ?? { type: 'none' }) || 'no condition'}</span>
              <button className="btn btn--ghost" onClick={() => onEditGate(e.id)}>
                Edit condition
              </button>
            </div>
          ))}
        </div>

        <div className="banner banner--warn">
          <b>Descriptive only.</b> Nothing validates these inputs — a per-skill input contract
          does not exist today. Shown so the graph is legible, not to imply enforcement.
        </div>
      </div>
    );
  }
```

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(studio): configurator Input tab"
```

---

### Task 2: The Output pane

**Files:**
- Modify: `web/src/modal/StepConfig.tsx`, `web/src/app.css`
- Test: `web/src/modal/StepConfig.test.tsx` (extend)

**Interfaces:**
- The Output pane: `produces` paths; the artefact contract when `produces_artefact` is set;
  the outbound edges it feeds.

- [ ] **Step 1: Write the failing test**

```tsx
const goOutput = () => userEvent.click(screen.getByRole('tab', { name: /output/i }));

describe('StepConfig — Output tab', () => {
  it('renders the artefact contract for a step that produces one', async () => {
    open('plan'); await goOutput();

    expect(screen.getByText('plan_id')).toBeInTheDocument();
    expect(screen.getByText('linked_requirement')).toBeInTheDocument();
    expect(screen.getByText('needs-rework')).toBeInTheDocument();
    expect(screen.getByText(/docs\/implr\/plans/)).toBeInTheDocument();
  });

  it('shows all ten required plan fields', async () => {
    open('plan'); await goOutput();

    const required = screen.getAllByTestId('field-required');
    expect(required).toHaveLength(10);
  });

  it('distinguishes required from optional', async () => {
    open('plan'); await goOutput();

    expect(screen.getByText('rework_cr').closest('.f')!.className).not.toContain('f--req');
    expect(screen.getByText('plan_id').closest('.f')!.className).toContain('f--req');
  });

  it('shows the states in lifecycle order', async () => {
    // Not alphabetical. A reader scans this as a lifecycle.
    open('plan'); await goOutput();

    expect(screen.getAllByTestId('state').map((n) => n.textContent))
      .toEqual(['ready', 'in-progress', 'done', 'blocked', 'needs-rework']);
  });

  it('names the state machine', async () => {
    open('plan'); await goOutput();

    expect(screen.getByText(/plan machine/i)).toBeInTheDocument();
  });

  it('explains the absence of a contract for a step that writes files', async () => {
    open(); await goOutput();

    expect(screen.getByText('src/**')).toBeInTheDocument();
    expect(screen.getByText(/no frontmatter contract/i)).toBeInTheDocument();
  });

  it('does not render an empty schema panel when there is no artefact', async () => {
    open(); await goOutput();

    expect(screen.queryByTestId('schema')).toBeNull();
  });

  it('shows the note beside a written path', async () => {
    open(); await goOutput();

    expect(screen.getByText(/tests first/i)).toBeInTheDocument();
  });

  it('lists the steps it feeds, with their conditions', async () => {
    open('plan'); await goOutput();

    expect(screen.getByText('Implementation')).toBeInTheDocument();
    expect(screen.getByText('any plan status=ready')).toBeInTheDocument();
  });

  it('says so for a terminal step', async () => {
    open('review'); await goOutput();

    expect(screen.getByText(/nothing downstream/i)).toBeInTheDocument();
  });

  it('renders a contract for an artefact the registry names but contracts lacks', async () => {
    // Defensive: produces_artefact is validated server-side, but a stale client
    // payload must not blank the tab.
    openWith({ contracts: {} }, 'plan'); await goOutput();

    expect(screen.getByText(/contract unavailable/i)).toBeInTheDocument();
  });
});

describe('StepConfig — no hardcoded vocabulary', () => {
  it('contains no implr status, artefact type or field name', () => {
    // Everything comes from /api/registry. This test is the enforcement.
    const source = readFileSync(join(__dirname, 'StepConfig.tsx'), 'utf8');

    for (const word of ['approved', 'under-review', 'needs-rework', 'in-progress',
                        'req_id', 'plan_id', 'requirement', 'ARCHITECTURE']) {
      expect(source).not.toContain(word);
    }
  });
});
```

That last test is the one that keeps the phase honest. It is easy to "just render" a field list
by typing it, and the whole architecture of this project exists to prevent a second copy of
implr's vocabulary.

- [ ] **Step 2: Implement**

```tsx
  function OutputPane() {
    const artefactName = step?.produces_artefact ?? null;
    const artefact = artefactName ? contracts[artefactName] : null;
    const outbound = edges.filter((e) => e.source === nodeId);

    return (
      <div className="pane">
        <p className="pane__lead">
          {artefactName
            ? `This step produces ${artefactName} artefacts. The contract below is the real `
              + 'frontmatter rule — the same vocabulary a downstream condition reads, which is '
              + 'why an impossible condition is caught while you design.'
            : 'This step writes files rather than status-carrying artefacts, so there is no '
              + 'frontmatter contract to enforce.'}
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

        {artefactName && !artefact && (
          <div className="banner banner--warn">
            Contract unavailable for <code>{artefactName}</code> — reload to refresh the
            registry.
          </div>
        )}

        {artefact && (
          <div className="schema" data-testid="schema">
            <div className="schema__hd">
              <span>{artefactName}</span>
              <span className="path">{artefact.path_globs.join(', ')}</span>
              <span className="machine">{artefact.machine} machine</span>
            </div>
            <div className="fields">
              {artefact.required.map((f) => (
                <span key={f} className="f f--req" data-testid="field-required">{f}</span>
              ))}
              {artefact.optional.map((f) => (
                <span key={f} className="f" data-testid="field-optional">{f}</span>
              ))}
            </div>
            <div className="states">
              {artefact.states.map((s) => (
                <span key={s} className="state" data-testid="state">{s}</span>
              ))}
            </div>
          </div>
        )}
        {/* … Feeds … */}
      </div>
    );
  }
```

Add the `.schema` block to `app.css`. The required marker is a CSS `::after` asterisk in
`--st-failed`, not a character in the label, so the field name stays copy-pasteable.

- [ ] **Step 3: Run, build, commit**

---

### Task 3: Run the demo

- [ ] **Step 1** — the three panes in *Demo*, in order.
- [ ] **Step 2** — close the loop deliberately. On **Planning → Output**, note the five plan
      states. Open the `plan → build` edge and confirm the status dropdown offers **exactly**
      those five. Same source, both ends.
- [ ] **Step 3** — **Implementation → Input → Edit condition** hands off to the gate editor
      rather than opening a dialog inside a dialog.
- [ ] **Step 4** — open **Code Review → Output**: the `review` contract has only two required
      fields (`review_id`, `status`) and four states. A component with a hardcoded ten-field
      assumption fails here.
- [ ] **Step 5** — open **Testing** (the unimplemented step): every tab renders, nothing
      crashes, and each says what is missing rather than showing a blank panel.

Step 4 is the cheap check that the tab is really data-driven. `requirement` and `plan` both
have ten required fields, so a hardcoded implementation passes both; `review` has two.

---

## Definition of Done

- [ ] `npm test` and `npm run build` pass. **No Python changed** — `python -m pytest` is
      unaffected, and that is the point.
- [ ] The Output tab renders required fields, optional fields, statuses, path globs and the
      machine name, all from `contracts`.
- [ ] Required and optional fields are visually distinct, with the marker in CSS so the field
      name stays copy-pasteable.
- [ ] States render in **lifecycle order**.
- [ ] A step with `produces_artefact: null` explains why, and renders **no** schema panel.
- [ ] A step that reads nothing, and a terminal step, both say so rather than showing an empty
      list.
- [ ] A node with two inbound edges lists **both** conditions.
- [ ] Upstream and downstream steps are named by **label**, not node id.
- [ ] Edit-condition hands off to the gate editor rather than nesting a dialog.
- [ ] The Input tab states that it is descriptive.
- [ ] `StepConfig.tsx` contains **no** implr status, artefact type or field name — asserted by
      a source grep.
- [ ] Every tab renders for an unimplemented step without crashing.
- [ ] **The demo:** the five plan states on the Output tab are the same five the gate editor
      offers, and `review` shows two required fields rather than ten.

---

## What the next phase gets

A complete configurator, and **Phase 7 is a milestone**: a pipeline *designer* for the nine
steps implr ships, fully working, with no execution and no hosting. It is shippable on its own.

**Phase 8** makes it open-ended — authoring your own step — and **Phase 9** is where anything
first runs.
