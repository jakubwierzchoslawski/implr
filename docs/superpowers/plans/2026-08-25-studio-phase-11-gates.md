# implr Studio — Phase 11: Many nodes, real gates

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A gate holds. You edit a file on disk. It opens — with no click at all.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` (*Component: Gates*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phases 9–10 for execution and streaming; Phase 6 for save-time gate validation — so an unrunnable condition cannot reach this phase in the first place.

---

## Demo

A two-node pipeline, `ingest → reqs`, gated on `all requirement status=approved`.

Press **Run**. `ingest` goes green. `reqs` goes **grey** — `blocked` — and the rail explains
*4 of 7 requirements are still under-review*, with **no Approve button**, because there is
nothing for a human to do.

Now, in another termin:

```bash
cat > /tmp/studio-probe/docs/implr/requirements/functional/req-f-001.md <<'EOF'
---
req_id: REQ-F-001
status: approved
---
body
EOF
```

Within a poll interval, `reqs` starts. **You clicked nothing.** The gate opened because the
*filesystem* changed, which is the whole design: gates read artefact frontmatter, never events.

Then the rule that is easy to get backwards:

```bash
rm /tmp/studio-probe/docs/implr/requirements/functional/*.md
```

Re-run. The `all` gate does **not** open. An empty match set never satisfies a gate.

---

## Scope boundary — not in this phase

- **No node-level approval.** `awaiting-approval` here comes from a `manual` **edge** gate.
  Phase 13 adds `approval: before|after` on the node, and with it `awaiting-review`.
- **No retry / skip / cancel.** A failed node pauses the run and stays failed. Phase 14.
- **No questions.** Still a hard error. Phase 12.
- **Concurrency stays 1.** The scheduler selects every eligible node; the driver runs them one
  at a time. Concurrent implr steps writing to shared artefact directories is unproven, and
  raising the cap is a config change once it is not.

---

## Global constraints

- **Gates read the filesystem.** An `artifact` StepEvent is advisory and must never influence
  scheduling. Enforced by review, and by a test that runs a gate against a workspace where the
  event says one thing and the files say another.
- **An `all` gate over an empty match set is `False`**, never vacuously true. The natural
  reading is the wrong one, so it gets its own test at both the evaluation and the readiness
  layer.
- **A file whose frontmatter cannot be parsed cannot satisfy a gate.**
- `blocked` and `awaiting-approval` are opposite in meaning and must not be conflated in the
  UI: one advances on its own, the other needs the operator.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/gates.py` | **Modified** — `evaluate_gate`, `artefact_condition_holds`. |
| `packages/implr_studio/orchestrator.py` | **Modified** — `edge_gate_state`, `node_readiness`, multi-node driver, `approve`. |
| `packages/implr_studio/store.py` | **Modified** — `set_manual_approved`. |
| `packages/implr_studio/api.py` | **Modified** — the approve route; the one-node refusal removed. |
| `web/src/panels/RunPanel.tsx` | **Modified** — the blocked / awaiting-approval affordances. |
| `web/src/edges/GateEdge.tsx` | **Modified** — an open/held marker in run mode. |

---

### Task 1: Runtime gate evaluation

**Files:**
- Modify: `packages/implr_studio/gates.py`
- Test: `packages/implr_studio/tests/test_gate_evaluation.py`

**Interfaces:**
- `gates.artefact_condition_holds(gate, workspace, contracts) -> bool` — the artefact half only.
- `gates.evaluate_gate(gate, workspace, contracts) -> bool` — `True` only when the gate is open **without** operator action.

Two functions because a combined gate needs both answers: *are the artefacts satisfied* (so the
UI can say whether there is anything to approve) and *is the gate open* (which a manual
component always makes `False` until approved).

Path globs from `frontmatter-rules.json` use `/`; they must be converted with
`.replace("/", os.sep)` before globbing, matching what `implr_validate.checks.check_workspace`
does. Frontmatter is parsed only via `implr_bridge.parse_frontmatter` — no second parser.

- [ ] **Step 1: Write the failing test**

```python
def _write(workspace, kind, name, **fields):
    sub = {"requirement": "requirements/functional", "plan": "plans/functional"}[kind]
    d = workspace / "docs" / "implr" / sub
    d.mkdir(parents=True, exist_ok=True)
    body = "".join("%s: %s\n" % (k, v) for k, v in fields.items())
    (d / ("%s.md" % name)).write_text("---\n%s---\nbody\n" % body, encoding="utf-8")


# --- the empty-match-set rule, at both quantifiers ------------------------

def test_all_over_an_empty_match_set_is_false(tmp_path, contracts):
    """SPEC RULE. A gate must not open merely because nothing has been produced.
    The vacuous-truth reading is the natural one and it is wrong here."""
    g = _g(type="artifact", artefact="requirement", quantifier="all",
           require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_any_over_an_empty_match_set_is_false(tmp_path, contracts):
    ...


def test_all_becomes_true_only_when_every_file_matches(tmp_path, contracts):
    g = _g(type="artifact", artefact="requirement", quantifier="all",
           require={"status": "approved"})
    _write(tmp_path, "requirement", "r1", req_id="REQ-F-001", status="approved")
    _write(tmp_path, "requirement", "r2", req_id="REQ-F-002", status="draft")

    assert gates.evaluate_gate(g, tmp_path, contracts) is False

    _write(tmp_path, "requirement", "r2", req_id="REQ-F-002", status="approved")

    assert gates.evaluate_gate(g, tmp_path, contracts) is True


def test_any_is_true_with_one_match(tmp_path, contracts):
    ...


# --- both path globs ------------------------------------------------------

def test_both_path_globs_are_searched(tmp_path, contracts):
    """requirement declares functional AND non-functional. A gate that globbed only
    the first would open while half the requirements were still draft."""
    g = _g(type="artifact", artefact="requirement", quantifier="all",
           require={"status": "approved"})
    _write(tmp_path, "requirement", "r1", req_id="REQ-F-001", status="approved")
    d = tmp_path / "docs" / "implr" / "requirements" / "non-functional"
    d.mkdir(parents=True)
    (d / "r2.md").write_text("---\nreq_id: REQ-N-001\nstatus: draft\n---\nb\n", encoding="utf-8")

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


# --- unparseable and incomplete files ------------------------------------

@pytest.mark.parametrize("body,why", [
    ("---\nreq_id: REQ-F-002\nstatus: approved\n", "unterminated frontmatter"),
    ("no frontmatter at all\n", "no frontmatter block"),
])
def test_an_unparseable_file_cannot_satisfy_a_gate(tmp_path, contracts, body, why):
    """A file implr_validate cannot read must not be able to open a gate. Both
    inputs genuinely raise FrontmatterError - do not substitute a malformed VALUE,
    which the restricted parser accepts as a string and would pass for the wrong
    reason."""
    _write(tmp_path, "requirement", "r1", req_id="REQ-F-001", status="approved")
    d = tmp_path / "docs" / "implr" / "requirements" / "functional"
    (d / "broken.md").write_text(body, encoding="utf-8")
    g = _g(type="artifact", artefact="requirement", quantifier="all",
           require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_a_file_missing_the_required_field_does_not_match(tmp_path, contracts):
    """Distinct from unparseable: it parses cleanly and has no `status` at all."""
    ...


def test_a_multi_field_require_needs_every_field(tmp_path, contracts):
    ...


# --- the manual component ------------------------------------------------

def test_a_none_gate_is_always_open(tmp_path, contracts):
    assert gates.evaluate_gate(_g(type="none"), tmp_path, contracts) is True


def test_a_manual_gate_is_never_opened_by_evaluation(tmp_path, contracts):
    """The operator releases it; evaluation cannot."""
    assert gates.evaluate_gate(_g(type="manual"), tmp_path, contracts) is False


def test_a_combined_gate_does_not_auto_open_even_when_the_artefacts_hold(tmp_path, contracts):
    _write(tmp_path, "requirement", "r1", req_id="REQ-F-001", status="approved")
    g = _g(type="artifact+manual", artefact="requirement", quantifier="all",
           require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False
    assert gates.artefact_condition_holds(g, tmp_path, contracts) is True


def test_the_artefact_half_is_separately_queryable(tmp_path, contracts):
    """So the UI can distinguish 'nothing to approve yet' from 'waiting on you'."""
    ...


# --- the advisory-event rule ---------------------------------------------

def test_evaluation_ignores_what_an_artifact_event_claimed(tmp_path, contracts):
    """gates read the FILESYSTEM. An artifact event saying a file was written must
    not open a gate when the file is not there."""
    g = _g(type="artifact", artefact="requirement", quantifier="any",
           require={"status": "approved"})

    # No files on disk, whatever any event said.
    assert gates.evaluate_gate(g, tmp_path, contracts) is False
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 2: Readiness and the multi-node driver

**Files:**
- Modify: `packages/implr_studio/orchestrator.py`
- Test: `packages/implr_studio/tests/test_scheduling.py`, `test_multi_node.py`

**Interfaces:**
- `GateState` — frozen: `open: bool`, `needs_approval: bool`.
- `edge_gate_state(edge, node_row, workspace, contracts) -> GateState`
- `node_readiness(node_id, p, nodes, workspace, contracts) -> str` — `PENDING`, `BLOCKED`, `AWAITING_APPROVAL`, or the sentinel `READY`.
- `READY = "ready"` — a scheduling answer, **never** a node status. It is not in `NODE_STATUSES` and is never written to the store.
- `await approve(run_id, node_id)`

Readiness rules, in order — and the ordering is the interesting part:

1. Any inbound edge whose source is not `succeeded`/`skipped` → `PENDING`.
2. All upstream satisfied, but some gate's artefact condition is false → `BLOCKED`.
3. Artefact conditions hold, but a manual gate is unapproved → `AWAITING_APPROVAL`.
4. Otherwise → `READY`.

**Blocked outranks awaiting-approval.** If the artefacts do not hold there is nothing
meaningful to approve, and asking the operator to approve a condition that is not yet met
trains them to approve without looking.

- [ ] **Step 1: Write the failing test**

```python
def test_a_root_node_is_ready(tmp_path, contracts):
    assert node_readiness("a", _pipe(), _nodes(a=rs.PENDING), tmp_path, contracts) == READY


def test_downstream_is_pending_while_upstream_runs(tmp_path, contracts):
    assert node_readiness("b", _pipe(), _nodes(a=rs.RUNNING, b=rs.PENDING),
                          tmp_path, contracts) == rs.PENDING


def test_a_failed_upstream_leaves_downstream_pending(tmp_path, contracts):
    """Never releases its dependents, and never marks them failed either."""
    assert node_readiness("b", _pipe(), _nodes(a=rs.FAILED, b=rs.PENDING),
                          tmp_path, contracts) == rs.PENDING


def test_a_skipped_upstream_does_release_downstream(tmp_path, contracts):
    assert node_readiness("b", _pipe(), _nodes(a=rs.SKIPPED, b=rs.PENDING),
                          tmp_path, contracts) == READY


def test_a_node_with_two_upstreams_waits_for_both(tmp_path, contracts):
    ...


def test_an_artefact_gate_blocks_until_the_frontmatter_satisfies_it(tmp_path, contracts):
    p, nodes = _pipe(ARTEFACT_GATE), _nodes(a=rs.SUCCEEDED, b=rs.PENDING)
    _write(tmp_path, "requirement", "r1", req_id="REQ-F-001", status="draft")

    assert node_readiness("b", p, nodes, tmp_path, contracts) == rs.BLOCKED

    _write(tmp_path, "requirement", "r1", req_id="REQ-F-001", status="approved")

    assert node_readiness("b", p, nodes, tmp_path, contracts) == READY


def test_a_manual_gate_awaits_approval(tmp_path, contracts):
    assert node_readiness("b", _pipe(MANUAL_GATE), _nodes(a=rs.SUCCEEDED, b=rs.PENDING),
                          tmp_path, contracts) == rs.AWAITING_APPROVAL


def test_blocked_outranks_awaiting_approval(tmp_path, contracts):
    """If the artefacts do not hold there is nothing to approve, and asking anyway
    trains the operator to approve without looking."""
    p, nodes = _pipe(COMBINED_GATE), _nodes(a=rs.SUCCEEDED, b=rs.PENDING)
    _write(tmp_path, "requirement", "r1", req_id="REQ-F-001", status="draft")

    assert node_readiness("b", p, nodes, tmp_path, contracts) == rs.BLOCKED


def test_a_combined_gate_awaits_approval_once_the_artefacts_hold(tmp_path, contracts):
    ...


def test_ready_is_not_a_node_status():
    """READY is a scheduling answer. It must never reach the store."""
    assert READY not in rs.NODE_STATUSES
```

```python
# multi-node execution

async def test_a_chain_runs_in_dependency_order(orch):
    run_id = await orch.start_run(_chain_of_three())
    await orch.wait_quiescent(run_id)

    assert [r.skill for r in orch.executor.started] == [
        "doc-ingest", "arch-gen", "ba-requirements-gen"]


async def test_a_failing_node_leaves_downstream_pending_not_failed(orch):
    orch.executor.set_script("doc-ingest", [base.StepEvent.done("failure", "broke")])

    run_id = await orch.start_run(_chain_of_three())
    await orch.wait_quiescent(run_id)

    statuses = orch.node_statuses(run_id)
    assert statuses["a"] == rs.FAILED
    assert statuses["b"] == rs.PENDING and statuses["c"] == rs.PENDING
    assert orch.run_status(run_id) == rs.RUN_PAUSED


async def test_a_blocked_gate_holds_the_run_paused(orch):
    run_id = await orch.start_run(_two_with_artefact_gate())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED, "b": rs.BLOCKED}
    assert orch.run_status(run_id) == rs.RUN_PAUSED
    assert [r.skill for r in orch.executor.started] == ["doc-ingest"]


async def test_the_gate_opens_when_the_filesystem_changes(orch):
    """No operator action. The gate reads artefact frontmatter, not events."""
    run_id = await orch.start_run(_two_with_artefact_gate())
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["b"] == rs.BLOCKED

    _write(orch.workspace, "requirement", "r1", req_id="REQ-F-001", status="approved")
    orch.rescan(run_id)                    # what the periodic re-evaluation calls
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["b"] == rs.SUCCEEDED


async def test_approve_releases_a_manual_gate(orch):
    run_id = await orch.start_run(_two_with_manual_gate())
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["b"] == rs.AWAITING_APPROVAL

    await orch.approve(run_id, "b")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["b"] == rs.SUCCEEDED


async def test_approving_a_node_that_is_not_awaiting_approval_is_refused(orch):
    ...


async def test_parallel_branches_run_one_at_a_time(orch):
    """Concurrency 1: the graph may branch, execution does not."""
    run_id = await orch.start_run(_diamond())
    await orch.wait_quiescent(run_id)

    assert len(orch.executor.started) == 4
    assert orch.run_status(run_id) == rs.RUN_SUCCEEDED


async def test_a_diamond_join_waits_for_both_branches(orch):
    ...


async def test_blocked_states_are_recorded_for_the_ui(orch, store):
    """A node the UI shows as `pending` when it is really blocked on a gate gives
    the operator nothing to read."""
    run_id = await orch.start_run(_two_with_artefact_gate())
    await orch.wait_quiescent(run_id)

    assert store.get_node(run_id, "b")["status"] == rs.BLOCKED
```

- [ ] **Step 2: Implement**

Two things worth writing carefully. `_refresh_blocked_states` runs in the driver's `finally`
and records *why* each not-yet-run node cannot proceed, so the UI has something to show. And
`rescan(run_id)` re-evaluates and respawns the driver — called by a periodic job and by the
approve route, so a filesystem change is noticed without a click.

Remove Phase 9's `UnsupportedPipelineError` for multi-node and non-`none` gates. Keep it for
`question` events until Phase 12.

- [ ] **Step 3: Run, commit**

---

### Task 3: The approve route and the run-mode affordances

**Files:**
- Modify: `packages/implr_studio/api.py`, `web/src/panels/RunPanel.tsx`, `web/src/edges/GateEdge.tsx`, `web/src/api.ts`
- Test: `packages/implr_studio/tests/test_api_approve.py`, `web/src/panels/RunPanel.test.tsx` (extend)

**Interfaces:**
- `POST /api/projects/{pid}/runs/{rid}/approve` — body `{node_id}`. `RUN_CONTROL`. `409` when the node is not awaiting approval.
- `RunPanel`: `blocked` → an explanation and **no** Approve; `awaiting-approval` → Approve.
- `GateEdge` in run mode: `✓` when the gate is open, `⋯` when held.

- [ ] **Step 1: Write the failing test**

```tsx
it('offers Approve for a node awaiting approval', () => { ... });

it('does NOT offer Approve for a blocked node', () => {
  // blocked and awaiting-approval look similar and mean opposite things. This is
  // the most likely usability bug in run mode, so it gets a test.
  renderPanel({ status: 'blocked' });

  expect(screen.queryByRole('button', { name: /approve/i })).toBeNull();
});

it('explains that a blocked node advances on its own', () => {
  renderPanel({ status: 'blocked' });

  expect(screen.getByText(/no action needed/i)).toBeInTheDocument();
});

it('shows why it is blocked when the backend said', () => { ... });

it('distinguishes the two states visually', () => {
  // --st-blocked vs --st-approval, both already reserved.
  ...
});
```

```python
def test_approve_releases_the_gate(client):
    ...
    assert wait_for_run(client, PID, run_id)["status"] == rs.RUN_SUCCEEDED


def test_approving_a_blocked_node_is_409(client):
    """You cannot approve your way past an unmet artefact condition."""
    ...


def test_approve_requires_run_control(app):
    assert permission_for(app, "approve") is Permission.RUN_CONTROL
```

`test_approving_a_blocked_node_is_409` is the one that closes the loop on the ordering rule:
`blocked` outranks `awaiting-approval` in readiness, so the route must refuse rather than
record an approval that readiness will ignore.

- [ ] **Step 2: Implement, run, build, commit**

---

### Task 4: Run the demo

- [ ] **Step 1** — the *Demo* flow: run, watch `reqs` go blocked, read the rail.
- [ ] **Step 2** — write the approved requirement file. The gate opens with **no click**.
- [ ] **Step 3** — delete the requirement files and re-run. The `all` gate does **not** open.
      That is the empty-match-set rule, and it is the one people expect to behave the other way.
- [ ] **Step 4** — write a *malformed* requirement file (unterminated frontmatter) alongside a
      good one. The gate stays closed: a file implr cannot read cannot open a gate.
- [ ] **Step 5** — switch the gate to `manual`. The node goes `awaiting-approval` — a different
      colour and an Approve button. Confirm a `blocked` node has neither.
- [ ] **Step 6** — a diamond: `a → b`, `a → c`, `b → d`, `c → d`. All four run, one at a time,
      and `d` waits for both branches.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` / `npm run build` pass, with no model invoked.
- [ ] An `all` **and** an `any` gate over an empty match set both evaluate `False`.
- [ ] Both of `requirement`'s path globs are searched.
- [ ] An unparseable file, and a file missing the required field, both fail to satisfy a gate.
- [ ] `evaluate_gate` returns `False` for `manual` and `artifact+manual`;
      `artefact_condition_holds` answers the artefact half separately.
- [ ] Gate decisions read the filesystem; no `artifact` event influences scheduling.
- [ ] `blocked` outranks `awaiting-approval`, and approving a blocked node is `409`.
- [ ] A failed node leaves downstream nodes `pending`, never `failed`.
- [ ] `READY` is not in `NODE_STATUSES` and never reaches the store.
- [ ] A gate opens on a filesystem change with no operator action.
- [ ] A diamond runs all four nodes, one at a time, and the join waits for both branches.
- [ ] The UI never offers Approve on a `blocked` node, and explains that it needs no action.
- [ ] Phase 9's multi-node and gate refusals are removed; the `question` refusal remains.

---

## What the next phase gets

A real scheduler. **Phase 12** adds questions — and the assertion that makes it correct is
`ex.started == 1` across a whole question round trip, because answering must **resume** the
step's session rather than restart it.
