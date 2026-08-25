# implr Studio — Phase 4: Configure arguments

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Click a step, tick `--task`, type a value — and a bad value is refused inline before you can save.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phases 0–3.

---

## Demo

Both processes up, the six-step pipeline on the canvas. Click **Implementation**.

A modal opens on its **Run** tab: the step's description, then its six flags as checkboxes.
Beside `--task` there is a text input, **disabled** until you tick the flag.

1. Tick `--task`. The input enables and an inline *needs a value* appears.
2. Type `has space` → *not a valid value*.
3. Type `PLAN-F-004#3` → the warning clears, and the node on the canvas reads
   `--task PLAN-F-004#3`.
4. **Save.** The YAML gains `arg_values`.
5. Clear the value and Save → `422`, `missing-arg-value`, naming the flag.

```bash
cat /tmp/studio-probe/docs/implr/config/pipeline.yaml
```

```yaml
- id: build
  step: dev-executor
  args:
  - --all
  - --task
  arg_values:
    --task: PLAN-F-004#3
  position: {x: 1040, y: 120}
```

---

## Why the value field is the whole phase

Four implr flags genuinely take an argument — `doc-ingest --file <path>`,
`dev-executor --task <id>`, `ba-requirements-gen --domain <name>`, `ba-cr --file <path>`.
Phase 1 shipped their arg specs with `takes_value: true` and a `value_pattern`; nothing has
consumed them yet.

Until it does, those flags are **selectable and inert** — which is worse than not offering
them, because the UI implies they work. That was finding G1 from the plan review, and this
phase is where it closes.

---

## Scope boundary — not in this phase

- **One tab: Run.** Agents is Phase 5, Input and Output are Phase 7.
- **No `approval` control.** That field arrives in Phase 13; adding a control for it now would
  render a setting nothing reads.
- **No gate editor.** Clicking an edge does nothing yet. Phase 6.
- **No authoring.** The modal edits an existing node; Phase 8 creates new steps.

The modal **shell** built here is reused by every later phase, so it is worth getting right:
scrim, head, tab strip, body, footer, Escape, focus.

---

## Global constraints

- Values are validated in the **backend**, against the arg spec's `value_pattern`, with
  `re.fullmatch`. The UI's inline check is a courtesy; the save is the gate.
- The frontend wraps the pattern as `^(?:…)$` rather than trusting it to be anchored, so the
  two agree.
- A deselected flag's value is **dropped**, or the save fails with `orphan-arg-value`.
- Colours from tokens. `--st-running` is the inline-warning colour; it is already reserved.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/pipeline.py` | **Modified** — `Node.arg_values`, three findings. |
| `packages/implr_studio/api.py` | **Modified** — nothing new; validation already runs on PUT. |
| `web/src/modal/Modal.tsx` | The dialog shell. Reused by phases 5–8. |
| `web/src/modal/StepConfig.tsx` | The configurator, Run pane only. |
| `web/src/store.ts` | **Modified** — `setArgValue`, and `setNodeArgs` drops orphans. |
| `web/src/nodes/StepNode.tsx` | **Modified** — render `flag value`. |
| `web/src/App.tsx` | **Modified** — `onNodeClick` opens the modal. |

---

### Task 1: `arg_values` and its three findings

**Files:**
- Modify: `packages/implr_studio/pipeline.py`
- Test: `packages/implr_studio/tests/test_arg_values.py`

**Interfaces:**
- `Node.arg_values: dict = {}` — flag → value. Sparse; omitted from the YAML when empty.
- `validate_pipeline` gains `missing-arg-value`, `bad-arg-value`, `orphan-arg-value`.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

import pytest

from implr_studio import pipeline, registry


@pytest.fixture
def reg(tmp_path: Path) -> registry.Registry:
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    schema_dir.mkdir(parents=True)
    (schema_dir / "step-registry.json").write_text(json.dumps({"steps": [{
        "id": "doc-ingest", "kind": "skill", "label": "d", "phase": "discovery",
        "skill": "doc-ingest",
        "args_allowed": [
            {"flag": "--dry-run", "takes_value": False, "note": ""},
            {"flag": "--file", "takes_value": True,
             "value_pattern": "^[A-Za-z0-9._/-]{1,200}$", "note": ""},
        ],
        "args_default": [], "interactive": False,
        "agents": [], "consumes": [], "produces": [], "produces_artefact": None,
        "description": "",
    }]}), encoding="utf-8")
    (skills_dir / "doc-ingest").mkdir(parents=True)
    (skills_dir / "doc-ingest" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return registry.load_registry(schema_dir, skills_dir)


def _p(node) -> pipeline.Pipeline:
    return pipeline.pipeline_from_dict({"version": 1, "nodes": [node], "edges": []})


def _codes(f):
    return [x.code for x in f]


def test_arg_values_defaults_to_empty():
    assert _p({"id": "a", "step": "doc-ingest"}).nodes[0].arg_values == {}


def test_a_value_taking_flag_with_no_value_is_rejected(reg):
    """The G1 gap: selectable and inert is worse than absent."""
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "doc-ingest", "args": ["--file"]}), reg)

    assert _codes(findings) == ["missing-arg-value"]
    assert "--file" in findings[0].message
    assert findings[0].node_id == "a"


def test_an_empty_string_counts_as_missing(reg):
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "doc-ingest", "args": ["--file"],
            "arg_values": {"--file": "   "}}), reg)

    assert _codes(findings) == ["missing-arg-value"]


def test_a_valid_value_is_accepted(reg):
    assert pipeline.validate_pipeline(
        _p({"id": "a", "step": "doc-ingest", "args": ["--file"],
            "arg_values": {"--file": "docs/kb/billing/rules.md"}}), reg) == []


@pytest.mark.parametrize("value", [
    "docs/kb/a.md; rm -rf /",
    "$(whoami)",
    "`id`",
    "docs/kb/has space.md",
    'docs/kb/"quoted".md',
    "docs/kb/a.md\nrm -rf /",
    "x" * 300,
])
def test_a_value_failing_the_pattern_is_rejected(reg, value):
    """Shell metacharacters never reach an argv vector - rejected on the way in.
    The newline case matters: a pattern anchored with ^...$ and matched with
    re.match would accept everything after the first line."""
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "doc-ingest", "args": ["--file"],
            "arg_values": {"--file": value}}), reg)

    assert _codes(findings) == ["bad-arg-value"]


def test_the_pattern_is_matched_in_full_not_prefixed(reg):
    """re.match would pass 'docs/kb/a.md\\nevil'. fullmatch is required."""
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "doc-ingest", "args": ["--file"],
            "arg_values": {"--file": "docs/kb/a.md\nevil"}}), reg)

    assert _codes(findings) == ["bad-arg-value"]


def test_a_value_for_an_unselected_flag_is_rejected(reg):
    """A stale value left behind after unticking the flag is a bug, not a nicety:
    it saves a configuration the UI is not showing."""
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "doc-ingest", "args": [],
            "arg_values": {"--file": "docs/kb/a.md"}}), reg)

    assert _codes(findings) == ["orphan-arg-value"]


def test_a_value_for_a_non_value_flag_is_rejected(reg):
    findings = pipeline.validate_pipeline(
        _p({"id": "a", "step": "doc-ingest", "args": ["--dry-run"],
            "arg_values": {"--dry-run": "yes"}}), reg)

    assert _codes(findings) == ["orphan-arg-value"]


def test_arg_values_is_omitted_from_the_yaml_when_empty():
    """A pipeline with no values round-trips byte-identically to Phase 3's format."""
    p = _p({"id": "a", "step": "doc-ingest"})

    assert "arg_values" not in pipeline.pipeline_to_dict(p)["nodes"][0]


def test_arg_values_survives_the_round_trip():
    p = _p({"id": "a", "step": "doc-ingest", "args": ["--file"],
            "arg_values": {"--file": "docs/kb/a.md"}})

    assert pipeline.pipeline_from_dict(pipeline.pipeline_to_dict(p)) == p
```

- [ ] **Step 2: Run to verify it fails, then implement**

`_validate_args` grows the three checks. Two details the tests pin down:

```python
        value = node.arg_values.get(arg)
        if value is None or not str(value).strip():
            findings.append(Finding("missing-arg-value", ..., node.id))
            continue
        # fullmatch, not match: an anchored pattern under re.match still accepts
        # everything after a newline.
        if not re.fullmatch(spec.value_pattern, str(value)):
            findings.append(Finding("bad-arg-value", ..., node.id))
```

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(studio): arg values with pattern validation"
```

---

### Task 2: The modal shell

**Files:**
- Create: `web/src/modal/Modal.tsx`
- Modify: `web/src/app.css`
- Test: `web/src/modal/Modal.test.tsx`

**Interfaces:**
- `Modal({ icon, title, subtitle, tabs, active, onTab, footer, onClose, children })`
- Escape closes. A scrim click closes. A click inside does not. Focus moves to Close on open.

Built as its own task because phases 5, 6 and 8 all reuse it, and a dialog that traps focus
badly or swallows Escape is the kind of thing nobody goes back to fix.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Modal from './Modal';

const open = (props = {}) =>
  render(<Modal icon="IM" title="Implementation" onClose={vi.fn()} {...props}>
    <p>body</p></Modal>);

describe('Modal', () => {
  it('renders the title and the body', () => {
    open();
    expect(screen.getByText('Implementation')).toBeInTheDocument();
    expect(screen.getByText('body')).toBeInTheDocument();
  });

  it('is a dialog with an accessible name', () => {
    open();
    expect(screen.getByRole('dialog', { name: 'Implementation' })).toBeInTheDocument();
  });

  it('moves focus to Close on open', () => {
    open();
    expect(screen.getByLabelText('Close')).toHaveFocus();
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    open({ onClose });
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('closes on a scrim click', async () => {
    const onClose = vi.fn();
    const { container } = open({ onClose });
    await userEvent.click(container.querySelector('.scrim')!);
    expect(onClose).toHaveBeenCalled();
  });

  it('does NOT close on a click inside the dialog', async () => {
    const onClose = vi.fn();
    open({ onClose });
    await userEvent.click(screen.getByText('body'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('renders tabs and reports a selection', async () => {
    const onTab = vi.fn();
    open({ tabs: [{ id: 'run', label: 'Run' }, { id: 'agents', label: 'Agents' }],
           active: 'run', onTab });

    expect(screen.getByRole('tab', { name: 'Run' })).toHaveAttribute('aria-selected', 'true');
    await userEvent.click(screen.getByRole('tab', { name: 'Agents' }));
    expect(onTab).toHaveBeenCalledWith('agents');
  });

  it('shows a count on a tab when given one', () => {
    open({ tabs: [{ id: 'run', label: 'Run', count: 2 }], active: 'run' });
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('removes its key listener on unmount', async () => {
    const onClose = vi.fn();
    const { unmount } = open({ onClose });
    unmount();
    await userEvent.keyboard('{Escape}');
    expect(onClose).not.toHaveBeenCalled();
  });
});
```

The last test exists because a modal that leaks its `keydown` handler makes Escape close a
dialog that is no longer open — and it only shows up after the third or fourth open.

- [ ] **Step 2: Implement**

```tsx
import { useEffect, useRef } from 'react';

interface Tab { id: string; label: string; count?: number }

interface Props {
  icon: string;
  title: string;
  subtitle?: React.ReactNode;
  tabs?: Tab[];
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
    // Removing this is not optional: a leaked handler closes a dialog that is
    // no longer open, and it only surfaces after several opens.
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
            {tabs.map((t) => (
              <button key={t.id} role="tab" aria-selected={t.id === active}
                      onClick={() => onTab?.(t.id)}>
                {t.label}
                {t.count !== undefined && <span className="count">{t.count}</span>}
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

Add `.scrim`, `.modal*`, `.tabs`, `.count`, `.x` to `app.css` — tokens only. The modal animates
with `transform` and `opacity`; `tokens.css` already disables that under
`prefers-reduced-motion`.

- [ ] **Step 3: Run, commit**

---

### Task 3: The Run pane

**Files:**
- Create: `web/src/modal/StepConfig.tsx`
- Modify: `web/src/store.ts`, `web/src/nodes/StepNode.tsx`, `web/src/App.tsx`
- Test: `web/src/modal/StepConfig.test.tsx`, `web/src/store.test.ts` (extend)

**Interfaces:**
- `StepConfig({ nodeId, onClose })` — one tab for now.
- `store.setArgValue(nodeId, flag, value)`
- `store.setNodeArgs` **drops values for deselected flags**.
- `StepNode` renders `flag value` when a value exists.

- [ ] **Step 1: Write the failing tests**

`store.test.ts`:

```ts
it('setArgValue records a value against a flag', () => {
  load();
  usePipelineStore.getState().setNodeArgs('a', ['--file']);

  usePipelineStore.getState().setArgValue('a', '--file', 'docs/kb/a.md');

  expect(usePipelineStore.getState().nodes[0].data.argValues).toEqual({ '--file': 'docs/kb/a.md' });
});

it('deselecting a flag drops its value', () => {
  // A stale arg_values entry fails the save with orphan-arg-value.
  load();
  usePipelineStore.getState().setNodeArgs('a', ['--file']);
  usePipelineStore.getState().setArgValue('a', '--file', 'docs/kb/a.md');

  usePipelineStore.getState().setNodeArgs('a', []);

  expect(usePipelineStore.getState().nodes[0].data.argValues).toEqual({});
});

it('deselecting one flag keeps another flag value', () => {
  load();
  usePipelineStore.getState().setNodeArgs('a', ['--file', '--other']);
  usePipelineStore.getState().setArgValue('a', '--file', 'x');
  usePipelineStore.getState().setArgValue('a', '--other', 'y');

  usePipelineStore.getState().setNodeArgs('a', ['--other']);

  expect(usePipelineStore.getState().nodes[0].data.argValues).toEqual({ '--other': 'y' });
});

it('setArgValue replaces the node object rather than mutating it', () => {
  load();
  const before = usePipelineStore.getState().nodes[0];

  usePipelineStore.getState().setArgValue('a', '--file', 'x');

  expect(usePipelineStore.getState().nodes[0]).not.toBe(before);
});
```

`StepConfig.test.tsx`:

```tsx
describe('StepConfig — Run tab', () => {
  it('leads with the step description', () => {
    open();
    expect(screen.getByText(/Implements ready plans/)).toBeInTheDocument();
  });

  it('offers only that step args_allowed', () => {
    open();
    expect(screen.getByLabelText('--all')).toBeInTheDocument();
    expect(screen.getByLabelText('--task')).toBeInTheDocument();
    expect(screen.queryByLabelText('--domain')).not.toBeInTheDocument();
  });

  it('reflects the currently selected args', () => {
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
    expect(screen.getByLabelText(/value for --task/i)).toBeDisabled();

    await userEvent.click(screen.getByLabelText('--task'));

    expect(screen.getByLabelText(/value for --task/i)).toBeEnabled();
  });

  it('renders no value input for a flag that takes none', () => {
    open();
    expect(screen.queryByLabelText(/value for --all/i)).not.toBeInTheDocument();
  });

  it('warns when a selected value-taking flag has no value', async () => {
    open();
    await userEvent.click(screen.getByLabelText('--task'));
    expect(screen.getByText(/needs a value/i)).toBeInTheDocument();
  });

  it('warns when a value fails its pattern', async () => {
    open();
    await userEvent.click(screen.getByLabelText('--task'));
    await userEvent.type(screen.getByLabelText(/value for --task/i), 'has space');
    expect(screen.getByText(/not a valid value/i)).toBeInTheDocument();
  });

  it('clears the warning once the value is valid', async () => {
    open();
    await userEvent.click(screen.getByLabelText('--task'));
    await userEvent.type(screen.getByLabelText(/value for --task/i), 'PLAN-F-004#3');
    expect(screen.queryByText(/not a valid value/i)).not.toBeInTheDocument();
    expect(node('build').data.argValues).toEqual({ '--task': 'PLAN-F-004#3' });
  });

  it('matches the pattern in full, like the backend', async () => {
    // The backend uses re.fullmatch. An unanchored client check would accept
    // this and then the save would fail, which is a confusing experience.
    open();
    await userEvent.click(screen.getByLabelText('--task'));
    await userEvent.type(screen.getByLabelText(/value for --task/i), 'PLAN-1 bad');
    expect(screen.getByText(/not a valid value/i)).toBeInTheDocument();
  });

  it('explains that an unimplemented step will not run', () => {
    open('sec');
    expect(screen.getByText(/not implemented/i)).toBeInTheDocument();
  });

  it('explains that an interactive step asks questions', () => {
    open('plan');
    expect(screen.getByText(/asks questions/i)).toBeInTheDocument();
  });

  it('names the file a save will write', () => {
    open();
    expect(screen.getByTestId('writes').textContent).toContain('pipeline.yaml');
  });
});
```

`StepNode.test.tsx`, one addition:

```tsx
it('shows a flag with its value so the canvas is readable without opening the modal', () => {
  renderNode({ args: ['--task'], argValues: { '--task': 'PLAN-F-004#3' } });
  expect(screen.getByText('--task PLAN-F-004#3')).toBeInTheDocument();
});
```

- [ ] **Step 2: Implement**

The inline check, wrapping the pattern so it agrees with `re.fullmatch`:

```tsx
    const problem = (spec: ArgSpec): string | null => {
      if (!spec.takes_value || !selected.has(spec.flag)) return null;
      const value = node.data.argValues[spec.flag] ?? '';
      if (!value.trim()) return 'needs a value';
      // ^(?:…)$ rather than trusting the pattern to be anchored - the backend
      // uses re.fullmatch, and a client that disagrees produces a save that
      // fails for a reason the UI said was fine.
      if (spec.value_pattern && !new RegExp(`^(?:${spec.value_pattern})$`).test(value)) {
        return 'not a valid value';
      }
      return null;
    };
```

In `App.tsx`, wire `onNodeClick` to open the modal. Leave `onEdgeClick` unwired — Phase 6.

- [ ] **Step 3: Run, build, commit**

---

### Task 4: Run the demo

- [ ] **Step 1** — the six steps in *Demo* above, in order.
- [ ] **Step 2** — Escape closes the modal; so does clicking the scrim; clicking inside does not.
- [ ] **Step 3** — open the modal four times in a row and press Escape each time. It closes
      once per open, not once per previous open: that is the leaked-listener bug.
- [ ] **Step 4** — hand-edit the YAML to `--task: "x; rm -rf /"`, reload, Save. `422`,
      `bad-arg-value`. Validation lives in the backend so a hand-edit is judged by the same rule.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` / `npm run build` pass.
- [ ] A selected value-taking flag with no value, an empty-ish value, a pattern failure and a
      newline-injection attempt are each rejected with the right code.
- [ ] The pattern is matched with `re.fullmatch`, and the client wraps it as `^(?:…)$`.
- [ ] A value for an unselected flag, or for a non-value flag, produces `orphan-arg-value`.
- [ ] `arg_values` is omitted from the YAML when empty — Phase 3 pipelines round-trip unchanged.
- [ ] Deselecting a flag drops its value and leaves other flags' values intact.
- [ ] The value input is disabled until its flag is ticked, and absent for flags that take none.
- [ ] `Modal` closes on Escape and on a scrim click, not on an inside click, and **removes its
      key listener on unmount**.
- [ ] The node card renders `flag value`.
- [ ] **The demo:** a bad value is refused inline, a good one reaches the YAML, and a
      hand-edited bad one is refused on save.

---

## What the next phase gets

A modal shell and one working tab. **Phase 5** adds the Agents tab, the tier selectors and the
model-mix meter — the first thing in the product that shows what a run will cost.
