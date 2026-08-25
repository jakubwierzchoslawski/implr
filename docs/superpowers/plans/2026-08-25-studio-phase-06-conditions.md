# implr Studio — Phase 6: Conditions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a condition on a connection, see it restated in plain English, and find that an illegal status is not even offered — and is refused if you hand-edit it in.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` (*Component: Gates*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 4 — the gate editor reuses `Modal.tsx`.

---

## Demo

Click the `plan → build` edge. The same modal shell, one pane, four dropdowns.

Set condition `artifact`, artefact `plan`, how many `any`, required status `ready`. The edge
grows a chip reading `any plan status=ready`, and beneath the dropdowns:

> **Implementation starts once at least one plan is ready.**

Now the payoff. Open the **Required status** dropdown: it offers exactly
`ready · in-progress · done · blocked · needs-rework`. There is no `approved` — that is a
*requirement* status, and this is a *plan* condition. Switch the artefact to `requirement` and
the list changes to the five requirement states.

Then prove the backend agrees:

```bash
python - <<'PY'
import io
p = "/tmp/studio-probe/docs/implr/config/pipeline.yaml"
s = io.open(p, encoding="utf-8").read().replace("status: ready", "status: complete", 1)
io.open(p, "w", encoding="utf-8").write(s)
PY
```

Reload, Save → `422`, `illegal-status`, and the message names the five legal plan states.

**This is the concrete payoff of choosing a Python backend.** The gate vocabulary comes from
`status-vocabulary.json` through the same loader `implr_validate` uses, so the operator learns
`complete` is not a plan status while designing, not three steps into a run.

---

## Scope boundary — not in this phase

- **Save-time validation only.** Nothing *evaluates* a condition yet — no filesystem globbing,
  no `blocked` state, no run. That is Phase 11, and it is deliberately later so an unrunnable
  condition cannot be saved in the first place.
- **No manual-gate UI beyond the dropdown.** `manual` and `artifact+manual` are selectable and
  validate, but nothing approves anything until Phase 11.
- **`require` constrains one field: `status`.** The gate language admits any declared field,
  and the backend validates any of them — but the editor offers only `status`, because it is
  the only one anyone has wanted and every extra control is a control to validate and explain.
- **No Input/Output tabs.** Phase 7, which renders the `contracts` payload this phase adds.

---

## Global constraints

- Artefact types, their fields and their legal statuses come from
  `frontmatter-rules.json` + `status-vocabulary.json`, served as `contracts`. **No vocabulary
  is hardcoded in TypeScript** — that is the whole reason this data crosses the wire.
- An **empty match set never satisfies a gate**, under any quantifier. Stated here because the
  rule is written in Phase 6's validation messages and enforced in Phase 11's evaluation, and
  the two must not drift.
- Gate findings merge into the **same** `422` envelope as DAG findings. One shape for the
  client.
- `--gate` is already a reserved token. No new colour.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/gates.py` | **NEW** — `validate_gate`. Save-time only. |
| `packages/implr_studio/serialize.py` | **Modified** — `contracts_to_dict`. |
| `packages/implr_studio/api.py` | **Modified** — registry grows `contracts`; PUT merges gate findings. |
| `web/src/gates.ts` | **Pure** — `gateLabel`, `gateSentence`. |
| `web/src/modal/GateConfig.tsx` | The editor. |
| `web/src/edges/GateEdge.tsx` | **Modified** — render the chip. |
| `web/src/App.tsx` | **Modified** — `onEdgeClick` opens it. |

---

### Task 1: `validate_gate`

**Files:**
- Create: `packages/implr_studio/gates.py`
- Test: `packages/implr_studio/tests/test_gates.py`

**Interfaces:**
- `gates.validate_gate(gate, contracts) -> list[Finding]`
- Findings: `missing-artefact`, `unknown-artefact-type`, `missing-quantifier`, `unknown-artefact-field`, `illegal-status`.

Everything comes from the contract files. `_artefact_fields` unions `required`, `optional` and
every `conditional_required` rule's fields — and must tolerate all three being **absent**,
because in the real `frontmatter-rules.json` only `cr` has `optional` and only `plan` has
`conditional_required`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import gates, implr_bridge, pipeline


@pytest.fixture
def contracts():
    root = implr_bridge.repo_root()
    return implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))


def _g(**kw):
    return pipeline.Gate(**kw)


def _codes(f):
    return [x.code for x in f]


# --- gate types that need no artefact -------------------------------------

def test_none_needs_no_artefact(contracts):
    assert gates.validate_gate(_g(type="none"), contracts) == []


def test_manual_needs_no_artefact(contracts):
    assert gates.validate_gate(_g(type="manual"), contracts) == []


# --- artefact gates -------------------------------------------------------

def test_a_valid_artifact_gate_passes(contracts):
    assert gates.validate_gate(_g(type="artifact", artefact="requirement",
                                  quantifier="all", require={"status": "approved"}),
                               contracts) == []


def test_a_missing_artefact_is_rejected(contracts):
    assert _codes(gates.validate_gate(
        _g(type="artifact", quantifier="all", require={"status": "approved"}),
        contracts)) == ["missing-artefact"]


def test_an_unknown_artefact_type_is_rejected(contracts):
    findings = gates.validate_gate(
        _g(type="artifact", artefact="unicorn", quantifier="all",
           require={"status": "approved"}), contracts)

    assert _codes(findings) == ["unknown-artefact-type"]
    assert "requirement" in findings[0].message      # names the legal types


def test_a_missing_quantifier_is_rejected(contracts):
    assert _codes(gates.validate_gate(
        _g(type="artifact", artefact="requirement", require={"status": "approved"}),
        contracts)) == ["missing-quantifier"]


def test_an_unknown_field_is_rejected(contracts):
    findings = gates.validate_gate(
        _g(type="artifact", artefact="requirement", quantifier="all",
           require={"colour": "blue"}), contracts)

    assert _codes(findings) == ["unknown-artefact-field"]


def test_a_declared_non_status_field_is_accepted(contracts):
    """The language admits any declared field even though the editor offers only status."""
    assert gates.validate_gate(
        _g(type="artifact", artefact="requirement", quantifier="all",
           require={"type": "functional"}), contracts) == []


def test_a_conditional_required_field_counts_as_declared(contracts):
    """plan declares rework_cr only under conditional_required. It is still a field."""
    assert gates.validate_gate(
        _g(type="artifact", artefact="plan", quantifier="any",
           require={"rework_cr": "CR-001"}), contracts) == []


def test_an_optional_field_counts_as_declared(contracts):
    """cr is the only artefact with an `optional` list. Do not skip it."""
    assert gates.validate_gate(
        _g(type="artifact", artefact="cr", quantifier="any",
           require={"rationale": "x"}), contracts) == []


# --- the headline check ---------------------------------------------------

def test_a_status_outside_the_state_machine_is_rejected(contracts):
    """'complete' is not a plan status. The plan machine is
    ready | in-progress | done | blocked | needs-rework."""
    findings = gates.validate_gate(
        _g(type="artifact", artefact="plan", quantifier="all",
           require={"status": "complete"}), contracts)

    assert _codes(findings) == ["illegal-status"]
    for legal in ("ready", "in-progress", "done", "blocked", "needs-rework"):
        assert legal in findings[0].message


def test_a_status_from_the_WRONG_machine_is_rejected(contracts):
    """'approved' is real - for a requirement. It is not a plan status, and this is
    the mistake the whole feature exists to catch."""
    findings = gates.validate_gate(
        _g(type="artifact", artefact="plan", quantifier="all",
           require={"status": "approved"}), contracts)

    assert _codes(findings) == ["illegal-status"]


def test_every_artefacts_own_statuses_are_accepted(contracts):
    """Guards against a machine-lookup bug that happens to pass for one artefact."""
    for artefact, spec in contracts.artefact_types.items():
        for status in contracts.states_for(spec["status_machine"]):
            assert gates.validate_gate(
                _g(type="artifact", artefact=artefact, quantifier="any",
                   require={"status": status}), contracts) == [], (artefact, status)


def test_artifact_plus_manual_is_validated_like_artifact(contracts):
    assert _codes(gates.validate_gate(
        _g(type="artifact+manual", artefact="unicorn", quantifier="all",
           require={"status": "approved"}), contracts)) == ["unknown-artefact-type"]


def test_an_empty_require_is_accepted(contracts):
    """'any plan exists' is a legal condition."""
    assert gates.validate_gate(
        _g(type="artifact", artefact="plan", quantifier="any", require={}), contracts) == []


def test_multiple_problems_are_all_reported(contracts):
    findings = gates.validate_gate(
        _g(type="artifact", artefact="plan", quantifier="all",
           require={"status": "complete", "colour": "blue"}), contracts)

    assert set(_codes(findings)) == {"illegal-status", "unknown-artefact-field"}
```

`test_every_artefacts_own_statuses_are_accepted` is the one that earns its keep: it catches a
machine lookup that happens to work for `requirement` (where the artefact and machine names
coincide) and is wrong for the other three.

- [ ] **Step 2: Implement, run, commit**

```python
def _artefact_fields(spec: dict) -> set[str]:
    # required is always present; optional exists only on `cr`; conditional_required
    # only on `plan`. All three must be optional here or this raises on real data.
    fields = set(spec.get("required") or [])
    fields |= set(spec.get("optional") or [])
    for rule in spec.get("conditional_required") or []:
        fields |= set(rule.get("require") or [])
    return fields
```

```bash
git commit -m "feat(studio): save-time gate validation against the real state machines"
```

---

### Task 2: Serving the contracts

**Files:**
- Modify: `packages/implr_studio/serialize.py`, `api.py`
- Test: `packages/implr_studio/tests/test_contracts_payload.py`

**Interfaces:**
- `serialize.contracts_to_dict(contracts) -> dict` — per artefact: `states`, `required`, `optional`, `fields`, `path_globs`, `machine`.
- `GET /api/projects/{pid}/registry` grows `contracts`.
- `PUT` merges gate findings into the existing envelope.

`states` comes from `contracts.machines[...]["states"]` — a **list**, order preserved — not
from `states_for()`, which returns a set. The dropdown must read
`ready, in-progress, done, blocked, needs-rework` in lifecycle order, and a set would scramble
it.

- [ ] **Step 1: Write the failing test**

```python
def test_states_are_in_lifecycle_order_not_alphabetical(contracts):
    """states_for() returns a SET. The dropdown must read in lifecycle order."""
    out = serialize.contracts_to_dict(contracts)

    assert out["plan"]["states"] == ["ready", "in-progress", "done", "blocked", "needs-rework"]


def test_states_match_the_status_vocabulary_for_every_artefact(contracts):
    """A drifting copy is exactly what this payload exists to prevent."""
    out = serialize.contracts_to_dict(contracts)

    for artefact, spec in contracts.artefact_types.items():
        assert set(out[artefact]["states"]) == contracts.states_for(spec["status_machine"])


def test_required_and_optional_are_reported_separately(contracts):
    """Phase 7's Output tab marks required fields distinctly."""
    out = serialize.contracts_to_dict(contracts)

    assert len(out["requirement"]["required"]) == 10
    assert out["requirement"]["optional"] == []
    assert "rationale" in out["cr"]["optional"]


def test_path_globs_are_reported(contracts):
    out = serialize.contracts_to_dict(contracts)

    assert "docs/implr/plans/functional/*.md" in out["plan"]["path_globs"]


def test_the_machine_name_is_reported(contracts):
    assert serialize.contracts_to_dict(contracts)["cr"]["machine"] == "cr"


def test_the_payload_is_json_serializable(contracts):
    json.dumps(serialize.contracts_to_dict(contracts))


def test_the_registry_response_carries_contracts(client):
    body = client.get(f"/api/projects/{PID}/registry").json()

    assert sorted(body["contracts"]) == ["cr", "plan", "requirement", "review"]
    assert body["contracts"]["plan"]["states"][0] == "ready"


def test_put_rejects_an_illegal_status_with_422(client):
    bad = dict(VALID, edges=[{
        "from": "ingest", "to": "arch",
        "gate": {"type": "artifact", "artefact": "plan",
                 "quantifier": "all", "require": {"status": "complete"}}}])

    r = client.put(f"/api/projects/{PID}/pipeline", json=bad)

    assert r.status_code == 422
    finding = next(f for f in r.json()["findings"] if f["code"] == "illegal-status")
    assert "ready" in finding["message"]


def test_gate_findings_and_dag_findings_share_one_envelope(client):
    """One shape for the client, whichever validator objected."""
    bad = dict(VALID,
               nodes=[{"id": "x", "step": "nope", "args": [], "position": {"x": 0, "y": 0}}],
               edges=[{"from": "x", "to": "x",
                       "gate": {"type": "artifact", "artefact": "unicorn",
                                "quantifier": "all", "require": {}}}])

    codes = [f["code"] for f in client.put(f"/api/projects/{PID}/pipeline", json=bad).json()["findings"]]

    assert "unknown-step" in codes
    assert "unknown-artefact-type" in codes


def test_a_rejected_gate_leaves_no_file(client, workspace):
    client.put(f"/api/projects/{PID}/pipeline", json=BAD_GATE)

    assert not (workspace / "docs" / "implr" / "config" / "pipeline.yaml").exists()
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 3: `gates.ts` — the label and the sentence

**Files:**
- Create: `web/src/gates.ts`
- Test: `web/src/gates.test.ts`

**Interfaces:**
- `gateLabel(gate) -> string` — the compact chip.
- `gateSentence(gate, targetLabel) -> string` — the plain restatement.

Two forms because `any plan status=ready` is precise and unfriendly. Someone composing a
pipeline for the first time should not have to parse it.

- [ ] **Step 1: Write the failing test**

```ts
describe('gateLabel', () => {
  it('renders nothing for an unconditional edge', () => {
    // A `none` gate draws no chip: only real conditions get ink.
    expect(gateLabel({ type: 'none' })).toBe('');
  });

  it('names a manual gate', () => {
    expect(gateLabel({ type: 'manual' })).toBe('approval');
  });

  it('renders an artefact condition compactly', () => {
    expect(gateLabel({ type: 'artifact', artefact: 'plan', quantifier: 'any',
                       require: { status: 'ready' } })).toBe('any plan status=ready');
  });

  it('appends approval for a combined gate', () => {
    expect(gateLabel({ type: 'artifact+manual', artefact: 'requirement', quantifier: 'all',
                       require: { status: 'approved' } }))
      .toBe('all requirement status=approved + approval');
  });

  it('handles an empty require', () => {
    expect(gateLabel({ type: 'artifact', artefact: 'plan', quantifier: 'any', require: {} }))
      .toBe('any plan');
  });

  it('defaults a missing quantifier to all', () => {
    expect(gateLabel({ type: 'artifact', artefact: 'plan', require: { status: 'ready' } }))
      .toBe('all plan status=ready');
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

  it('explains an any-quantifier condition', () => {
    expect(gateSentence({ type: 'artifact', artefact: 'plan', quantifier: 'any',
                          require: { status: 'ready' } }, 'Implementation'))
      .toBe('Implementation starts once at least one plan is ready.');
  });

  it('explains an all-quantifier condition', () => {
    expect(gateSentence({ type: 'artifact', artefact: 'requirement', quantifier: 'all',
                          require: { status: 'approved' } }, 'Planning'))
      .toBe('Planning starts once every requirement is approved.');
  });

  it('explains a combined gate', () => {
    expect(gateSentence({ type: 'artifact+manual', artefact: 'requirement', quantifier: 'all',
                          require: { status: 'approved' } }, 'Planning'))
      .toBe('Planning starts once every requirement is approved, and you approve.');
  });

  it('says "exists" when no status is required', () => {
    expect(gateSentence({ type: 'artifact', artefact: 'review', quantifier: 'any',
                          require: {} }, 'Release'))
      .toBe('Release starts once at least one review exists.');
  });
});
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 4: The gate editor and the chip

**Files:**
- Create: `web/src/modal/GateConfig.tsx`
- Modify: `web/src/edges/GateEdge.tsx`, `web/src/App.tsx`, `web/src/store.ts`, `web/src/app.css`
- Test: `web/src/modal/GateConfig.test.tsx`

**Interfaces:**
- `GateConfig({ edgeId, onClose })` — four dropdowns, the sentence, two banners.
- `store.contracts`, `store.setEdgeGate(id, gate)`.
- `GateEdge` renders the chip via `EdgeLabelRenderer`, `className="gate-chip nodrag nopan"`.

- [ ] **Step 1: Write the failing test**

```tsx
describe('GateConfig', () => {
  it('offers only the states of the chosen artefact', () => {
    open('plan__build');

    expect([...screen.getByLabelText(/required status/i)
              .querySelectorAll('option')].map((o) => o.textContent))
      .toEqual(['(any status)', 'ready', 'in-progress', 'done', 'blocked', 'needs-rework']);
  });

  it('does NOT offer a status from another machine', () => {
    // 'approved' is a requirement status. This is the mistake the feature prevents.
    open('plan__build');
    expect(screen.queryByRole('option', { name: 'approved' })).toBeNull();
  });

  it('changes the status list when the artefact changes', async () => {
    open('plan__build');
    await userEvent.selectOptions(screen.getByLabelText(/artefact/i), 'requirement');

    expect(screen.getByRole('option', { name: 'approved' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'needs-rework' })).toBeNull();
  });

  it('clears the required status when the artefact changes', async () => {
    // Otherwise you keep a status that is illegal for the new artefact.
    open('plan__build');
    await userEvent.selectOptions(screen.getByLabelText(/artefact/i), 'requirement');

    expect(edge('plan__build').data.gate.require).toEqual({});
  });

  it('restates the condition in plain words', () => {
    open('plan__build');
    expect(screen.getByText(/Implementation starts once at least one plan is ready\./))
      .toBeInTheDocument();
  });

  it('updates the sentence as you change the dropdowns', async () => {
    open('plan__build');
    await userEvent.selectOptions(screen.getByLabelText(/how many/i), 'all');

    expect(screen.getByText(/every plan is ready/)).toBeInTheDocument();
  });

  it('hides the artefact controls for a condition-free type', async () => {
    open('plan__build');
    await userEvent.selectOptions(screen.getByLabelText(/^condition$/i), 'none');

    expect(screen.queryByLabelText(/required status/i)).toBeNull();
    expect(edge('plan__build').data.gate).toEqual({ type: 'none' });
  });

  it('restores sensible defaults when switching back to artifact', async () => {
    open('plan__build');
    await userEvent.selectOptions(screen.getByLabelText(/^condition$/i), 'none');
    await userEvent.selectOptions(screen.getByLabelText(/^condition$/i), 'artifact');

    const gate = edge('plan__build').data.gate;
    expect(gate.artefact).toBeTruthy();
    expect(gate.quantifier).toBe('all');
  });

  it('states the empty-match-set rule', () => {
    // Easy to read backwards, so the UI says it.
    open('plan__build');
    expect(screen.getByText(/never vacuously true/i)).toBeInTheDocument();
  });

  it('warns that approval is recorded per step', async () => {
    open('plan__build');
    await userEvent.selectOptions(screen.getByLabelText(/^condition$/i), 'manual');

    expect(screen.getByText(/per step, not per connection/i)).toBeInTheDocument();
  });

  it('names the file a save will write', () => {
    open('plan__build');
    expect(screen.getByTestId('writes').textContent).toContain('pipeline.yaml');
  });
});
```

```tsx
// GateEdge
it('renders no chip for a none gate', () => { ... });
it('renders the compact label for an artefact gate', () => { ... });
it('marks the chip nodrag nopan so it does not pan the canvas', () => { ... });
```

- [ ] **Step 2: Implement**

The artefact-change rule is the one with a real bug behind it:

```tsx
          onChange={(e) => update({ artefact: e.target.value, require: {} })}
```

Clearing `require` is not tidiness. Keeping `status: ready` while switching the artefact to
`requirement` produces a gate the backend refuses, in a UI that showed you the value — the
worst kind of validation error.

- [ ] **Step 3: Run, build, commit**

---

### Task 5: Run the demo

- [ ] **Step 1** — the *Demo* flow: build the condition, read the chip, read the sentence.
- [ ] **Step 2** — open the status dropdown for `plan` and confirm `approved` is **absent**.
      Switch to `requirement`; confirm `needs-rework` is absent and `approved` is present.
- [ ] **Step 3** — the hand-edit: `status: complete`, reload, Save → `422`, `illegal-status`,
      five legal states named.
- [ ] **Step 4** — set the condition to `none` and confirm the chip disappears entirely rather
      than rendering an empty pill.
- [ ] **Step 5** — set it to `manual` and read the per-step approval warning. That is finding
      G3 surfaced where it matters rather than buried in a spec.
- [ ] **Step 6** — no regression: a pipeline whose every gate is `none` saves exactly as it did
      in Phase 5, and the YAML gains nothing.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` / `npm run build` pass.
- [ ] Every artefact type's own statuses validate; a status from another machine does not —
      asserted across **all four** artefact types, not just `requirement`.
- [ ] `_artefact_fields` tolerates absent `optional` and absent `conditional_required`, which
      is the shape of the real file.
- [ ] `contracts.states` are in **lifecycle order**, not set order.
- [ ] `required` and `optional` are reported separately, for Phase 7.
- [ ] Gate findings and DAG findings arrive in one `422` envelope.
- [ ] A rejected gate leaves no file on disk.
- [ ] The editor offers only the chosen artefact's states, and changing the artefact **clears**
      the required status.
- [ ] `gateSentence` covers all four gate types and the no-status case.
- [ ] A `none` gate renders **no** chip.
- [ ] The editor states the empty-match-set rule and the per-step approval limitation.
- [ ] No vocabulary is hardcoded in TypeScript.

---

## What the next phase gets

The `contracts` payload. **Phase 7** spends it: the Output tab renders the ten required `plan`
fields and its five legal statuses, with **no new backend at all** — which is why it is the
cheapest phase in the sequence and comes last of the four.
