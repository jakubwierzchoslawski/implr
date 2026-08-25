# implr Studio — Phase 14: Failure & recovery

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A step fails, the run pauses instead of collapsing, and you retry it — or skip it, or abort. Then kill the server mid-run and watch it come back honest.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 13 — retry and skip clear the approval stamps that phase introduced, and
`awaiting-review` is one of the states recovery must leave alone.

---

## Demo

Script a step to fail. Run.

The node goes **red** with the error text visible. The run goes **paused** — not `failed`.
Downstream nodes stay **`pending`**, not `failed`: they never ran, and saying they failed would
be a lie you then have to explain.

Fix the script and press **Retry**. It succeeds and the run continues.

Then **Skip** a different failure and watch the run proceed *past* it — but with any `artifact`
gate downstream still holding, because skipping a step does not conjure its artefacts.

Then the one that matters in production:

```bash
# start a run, kill the process mid-step, restart, reopen the browser
implr-studio --workspace $PROBE --fake &
# ... press Run, then:
kill -9 %1
implr-studio --workspace $PROBE --fake
```

Completed nodes are still completed. The interrupted node reports **`failed`**, with an error
naming the restart. It is **not** silently retried, and the run is **paused**, waiting for you.

---

## Why this phase exists

Phase 9 gave the driver an exception guard, so a raising step leaves a `failed` node rather than a
node stuck at `running`. That is the *floor*. It is not recovery:

| Gap after Phase 13 | Consequence |
|---|---|
| A failure is terminal for the whole run | One flaky step throws away twenty minutes of completed work |
| No retry | The fix is to re-run the pipeline from the top |
| No skip | A step that is genuinely optional today blocks a run permanently |
| No cancel | The only way to stop a run is to kill the server |
| A crash leaves nodes at `running` forever | The console shows a spinner for a process that no longer exists |

The last one is the one that decides whether this is a product. A restart is not exotic — it is a
deploy, an OOM kill, a laptop lid. What the operator needs after one is a screen that tells the
truth.

---

## Scope boundary — not in this phase

- **No automatic retry.** Not on failure, not on restart. See *Global constraints*.
- **No partial retry within a step.** Same limitation Phase 13 documented: retry re-runs the whole
  step.
- **No resume of an interrupted step.** A crash loses the agent's session; the node fails and you
  retry it from the start. Session resumption is an adapter capability (`ClaudeAgentOptions.resume`)
  and belongs with Phase 15, if at all.
- **No run deletion or purge.** Run history grows. Retention arrives with Postgres in Phase 16.
- **No cross-run rollback.** Studio does not revert files a step wrote. Git is the undo, and the
  error block says so.

---

## Global constraints

**No automatic retry, ever.** Three reasons, and each has cost a real team a bad afternoon: a
step that failed because it half-wrote a file will half-write it again; a retry loop on a
crash-inducing step is an infinite loop that bills; and an agent run is expensive, so spending
money without a human pressing something is not a default anyone should ship. Retry is a button.

**A node failure pauses the run; it does not fail it.** `RUN_PAUSED` is the actionable state, and
the whole point of the phase is that completed work survives. A run reaches `RUN_FAILED` only
when nothing further can happen and the operator has taken no action — see Task 3.

**Downstream nodes of a failure stay `pending`.** They are not `failed`, not `blocked`, not
`skipped`. `pending` is true: they have not run.

**`skipped` satisfies a dependency; it does not satisfy a gate.** This is the honest half of
skip. The edge is traversable, and any `artifact` condition on it is still evaluated against the
filesystem — so skipping `dev-planner` lets the graph move on and the `plan` artefact gate still
refuses, because the plans do not exist. Skip cannot fabricate work.

**Recovery is idempotent and runs before the server accepts a request.** Two recoveries in a row
change nothing the second time, and no route can observe a node in the pre-recovery state.

**Cancel is bounded.** If an executor ignores the close, the node is forced to `cancelled` after a
grace period rather than sitting at `running` while the UI claims a cancel succeeded.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/runstate.py` | **Modified** — `SKIPPED`, `CANCELLED`, `RUN_FAILED`, `RUN_CANCELLED`, the terminal sets. |
| `packages/implr_studio/orchestrator.py` | **Modified** — `retry`, `skip`, `cancel`, `recover`, the failure path. |
| `packages/implr_studio/store.py` | **Modified** — `list_runs`, `stale_running_nodes`, error columns. |
| `packages/implr_studio/executors/base.py` | **Modified** — the cancellation contract. |
| `packages/implr_studio/executors/fake.py` | **Modified** — record cancellation; a script that hangs. |
| `packages/implr_studio/api.py` | **Modified** — retry / skip / cancel routes, run list. |
| `web/src/panels/RunPanel.tsx` | **Modified** — Retry / Skip / Abort, the error block. |
| `web/src/panels/RunHistory.tsx` | Past runs, newest first. |

---

### Task 1: The three new statuses

**Files:**
- Modify: `packages/implr_studio/runstate.py`
- Test: `packages/implr_studio/tests/test_runstate_terminal.py`

**Interfaces:**
- `SKIPPED = "skipped"`, `CANCELLED = "cancelled"`.
- `RUN_FAILED = "failed"`, `RUN_CANCELLED = "cancelled"`.
- `NODE_TERMINAL = {SUCCEEDED, FAILED, SKIPPED, CANCELLED}`.
- `NODE_SATISFIES_DEPENDENCY = {SUCCEEDED, SKIPPED}`.
- `RUN_TERMINAL = {RUN_SUCCEEDED, RUN_FAILED, RUN_CANCELLED}`.
- `is_retryable(status) -> bool` — `FAILED`, `SKIPPED`, `SUCCEEDED`; not `CANCELLED`, not any
  in-flight or awaiting state.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import runstate as rs


def test_the_terminal_set_is_exactly_four():
    assert rs.NODE_TERMINAL == {rs.SUCCEEDED, rs.FAILED, rs.SKIPPED, rs.CANCELLED}


def test_skipped_satisfies_a_dependency():
    """Skip means 'proceed without it'. If it did not satisfy the dependency,
    skip would be indistinguishable from failure."""
    assert rs.satisfies_dependency(rs.SKIPPED) is True


@pytest.mark.parametrize("status", [rs.FAILED, rs.CANCELLED, rs.BLOCKED,
                                    rs.AWAITING_APPROVAL, rs.AWAITING_REVIEW,
                                    rs.AWAITING_INPUT, rs.RUNNING, rs.PENDING])
def test_nothing_else_satisfies_a_dependency(status):
    assert rs.satisfies_dependency(status) is False


@pytest.mark.parametrize("status,ok", [
    (rs.FAILED, True),
    (rs.SKIPPED, True),
    (rs.SUCCEEDED, True),          # re-run a good step; Phase 13 re-asks for approval
    (rs.CANCELLED, False),         # the run is over; start a new one
    (rs.RUNNING, False),
    (rs.PENDING, False),
    (rs.AWAITING_REVIEW, False),   # that is accept / request-changes, not retry
    (rs.AWAITING_INPUT, False),    # that is answer
])
def test_is_retryable(status, ok):
    assert rs.is_retryable(status) is ok


def test_every_status_is_declared():
    """A status that exists in the orchestrator and not in NODE_STATUSES gets
    a grey stripe and no affordance - a bug nobody reports because it looks
    like a loading state."""
    assert rs.NODE_TERMINAL <= set(rs.NODE_STATUSES)
    assert rs.RUN_TERMINAL <= set(rs.RUN_STATUSES)
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(runstate): skipped, cancelled, and the retryable predicate"
```

---

### Task 2: Failure pauses the run and holds the downstream

**Files:**
- Modify: `packages/implr_studio/orchestrator.py`
- Test: `packages/implr_studio/tests/test_failure.py`

**Interfaces:**
- `_run_node` records `error` and the failing node's last log tail alongside the status.
- `_finalise_run_status` returns `RUN_PAUSED` when any node is `failed` and any action remains.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import orchestrator, pipeline
from implr_studio import runstate as rs
from implr_studio.executors import base

pytestmark = pytest.mark.asyncio


def _chain():
    return pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest"},
                  {"id": "b", "step": "arch-gen"},
                  {"id": "c", "step": "requirements"}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]})


async def test_a_failure_leaves_downstream_pending(orch):
    """Not failed, not blocked, not skipped. They did not run."""
    orch.executor.set_script("arch-gen", [base.StepEvent.done(base.OUTCOME_FAILURE, "boom")])

    run_id = await orch.start_run(_chain())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {
        "a": rs.SUCCEEDED, "b": rs.FAILED, "c": rs.PENDING}


async def test_a_failure_pauses_the_run_rather_than_failing_it(orch):
    """The completed work is the asset. A run that fails on first error
    throws away everything upstream of the error."""
    orch.executor.set_script("arch-gen", [base.StepEvent.done(base.OUTCOME_FAILURE, "boom")])

    run_id = await orch.start_run(_chain())
    await orch.wait_quiescent(run_id)

    assert orch.run_status(run_id) == rs.RUN_PAUSED


async def test_the_error_text_is_recorded(orch, store):
    orch.executor.set_script(
        "arch-gen", [base.StepEvent.log("about to fail"),
                     base.StepEvent.done(base.OUTCOME_FAILURE, "no ARCHITECTURE.md written")])

    run_id = await orch.start_run(_chain())
    await orch.wait_quiescent(run_id)

    node = store.get_node(run_id, "b")
    assert "no ARCHITECTURE.md written" in node["error"]


async def test_a_raising_step_is_a_failure_with_the_exception_text(orch):
    """Phase 9 guaranteed the driver survives. This guarantees the operator
    learns *what* happened rather than seeing a bare 'failed'."""
    orch.executor.set_raise("arch-gen", RuntimeError("adapter exploded"))

    run_id = await orch.start_run(_chain())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["b"] == rs.FAILED
    assert "adapter exploded" in store_error(orch, run_id, "b")


async def test_a_parallel_branch_unaffected_by_the_failure_still_completes(orch):
    """The reason pausing beats failing: independent work should finish."""
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "root", "step": "doc-ingest"},
                  {"id": "left", "step": "arch-gen"},
                  {"id": "right", "step": "requirements"}],
        "edges": [{"from": "root", "to": "left"}, {"from": "root", "to": "right"}]})
    orch.executor.set_script("arch-gen", [base.StepEvent.done(base.OUTCOME_FAILURE, "boom")])

    run_id = await orch.start_run(p)
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["right"] == rs.SUCCEEDED
    assert orch.node_statuses(run_id)["left"] == rs.FAILED
```

That last test is the argument for the whole design in one assertion. If a failure failed the run,
the right-hand branch would be abandoned for a reason unrelated to it.

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(orchestrator): a failure pauses the run"
```

---

### Task 3: Retry, skip, cancel

**Files:**
- Modify: `packages/implr_studio/orchestrator.py`, `store.py`, `executors/base.py`, `executors/fake.py`
- Test: `packages/implr_studio/tests/test_operator_actions.py`

**Interfaces:**
- `await Orchestrator.retry(run_id, node_id)` — clears error, approvals and the cached stream;
  increments `attempt`; re-drives.
- `await Orchestrator.skip(run_id, node_id, reason)` — `SKIPPED`; requires a reason.
- `await Orchestrator.cancel(run_id)` — closes in-flight streams, marks `running` →
  `CANCELLED`, `pending` and awaiting → `CANCELLED`, run → `RUN_CANCELLED`.
- `orchestrator.CANCEL_GRACE_SECONDS = 10.0`
- `base.StepEvent.CANCELLED` is **not** added — cancellation is orchestrator bookkeeping, not
  something a step reports about itself.

- [ ] **Step 1: Write the failing test**

```python
# --- retry -----------------------------------------------------------------

async def test_retry_reruns_and_the_run_continues(orch):
    orch.executor.set_script("arch-gen", [base.StepEvent.done(base.OUTCOME_FAILURE, "boom")])
    run_id = await orch.start_run(_chain())
    await orch.wait_quiescent(run_id)
    orch.executor.clear_script("arch-gen")          # "fix the bug"

    await orch.retry(run_id, "b")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {
        "a": rs.SUCCEEDED, "b": rs.SUCCEEDED, "c": rs.SUCCEEDED}
    assert orch.run_status(run_id) == rs.RUN_SUCCEEDED


async def test_retry_does_not_rerun_the_upstream(orch):
    """The completed work is the asset. Re-running `a` would be the expensive
    kind of wrong: it costs money and may rewrite files `b` was reading."""
    orch.executor.set_script("arch-gen", [base.StepEvent.done(base.OUTCOME_FAILURE, "boom")])
    run_id = await orch.start_run(_chain())
    await orch.wait_quiescent(run_id)
    orch.executor.clear_script("arch-gen")

    await orch.retry(run_id, "b")
    await orch.wait_quiescent(run_id)

    assert [r.node_id for r in orch.executor.started].count("a") == 1


async def test_retry_clears_the_error(orch, store):
    ...
    assert store.get_node(run_id, "b")["error"] is None


async def test_retry_increments_attempt(orch, store):
    ...
    assert store.get_node(run_id, "b")["attempt"] == 2


async def test_retrying_a_running_node_is_refused(orch):
    with pytest.raises(orchestrator.OperatorActionError, match="running"):
        await orch.retry(run_id, "a")


async def test_retrying_a_cancelled_run_is_refused(orch):
    """A cancelled run is over. Reviving one node of it produces a run whose
    status says cancelled and whose nodes say otherwise."""
    run_id = await orch.start_run(_chain())
    await orch.cancel(run_id)

    with pytest.raises(orchestrator.OperatorActionError, match="cancelled"):
        await orch.retry(run_id, "b")


# --- skip ------------------------------------------------------------------

async def test_skip_lets_the_run_proceed(orch):
    orch.executor.set_script("arch-gen", [base.StepEvent.done(base.OUTCOME_FAILURE, "boom")])
    run_id = await orch.start_run(_chain())
    await orch.wait_quiescent(run_id)

    await orch.skip(run_id, "b", "the brief was written by hand")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["b"] == rs.SKIPPED
    assert orch.node_statuses(run_id)["c"] == rs.SUCCEEDED


async def test_skip_requires_a_reason(orch):
    """A skipped step in a pipeline someone reads in three weeks needs to say
    why. Without a reason this is a silent hole in the audit trail."""
    with pytest.raises(orchestrator.OperatorActionError, match="reason"):
        await orch.skip(run_id, "b", "  ")


async def test_skip_does_not_satisfy_an_artifact_gate(orch, workspace):
    """THE honest half of skip. Skipping dev-planner makes the edge
    traversable and the `plan` artefact still does not exist, so an artifact
    gate downstream must still refuse. Skip cannot fabricate work."""
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "plan", "step": "dev-planner"},
                  {"id": "build", "step": "dev-executor"}],
        "edges": [{"from": "plan", "to": "build",
                   "gate": {"kind": "artifact", "artefact": "plan",
                            "states": ["approved"], "quantifier": "all"}}]})
    orch.executor.set_script("dev-planner", [base.StepEvent.done(base.OUTCOME_FAILURE, "boom")])
    run_id = await orch.start_run(p)
    await orch.wait_quiescent(run_id)

    await orch.skip(run_id, "plan", "plans came from the ticket")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["build"] == rs.BLOCKED


async def test_a_skipped_node_can_be_retried(orch):
    """Skip is a decision, not a verdict. Changing your mind must be possible."""
    ...
    assert orch.node_statuses(run_id)["b"] == rs.SUCCEEDED


# --- cancel ----------------------------------------------------------------

async def test_cancel_stops_a_running_node(orch):
    orch.executor.set_hang("doc-ingest")
    run_id = await orch.start_run(_chain())
    await orch.wait_running(run_id, "a")

    await orch.cancel(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.CANCELLED
    assert orch.run_status(run_id) == rs.RUN_CANCELLED
    assert orch.executor.cancelled == ["a"]


async def test_cancel_marks_pending_nodes_cancelled_not_pending(orch):
    """A pending node in a cancelled run will never run. Leaving it `pending`
    shows a queue that is not a queue."""
    ...
    assert orch.node_statuses(run_id)["c"] == rs.CANCELLED


async def test_cancel_leaves_completed_nodes_alone(orch):
    ...
    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED


async def test_cancel_is_idempotent(orch):
    run_id = await orch.start_run(_chain())
    await orch.cancel(run_id)
    before = orch.node_statuses(run_id)

    await orch.cancel(run_id)

    assert orch.node_statuses(run_id) == before


async def test_cancel_forces_a_node_whose_executor_ignores_the_close(orch, monkeypatch):
    """Bounded, not best-effort. An adapter that swallows aclose() must not
    leave the UI claiming a cancel that never happened."""
    monkeypatch.setattr(orchestrator, "CANCEL_GRACE_SECONDS", 0.05)
    orch.executor.set_uncloseable("doc-ingest")
    run_id = await orch.start_run(_chain())
    await orch.wait_running(run_id, "a")

    await orch.cancel(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.CANCELLED


async def test_a_cancelled_run_starts_no_further_nodes(orch):
    """The regression that matters: a driver task still in flight when cancel
    lands must not schedule the next node afterwards."""
    ...
    assert len(orch.executor.started) == 1
```

The last one is the race worth writing the test for. `cancel` sets state; a driver coroutine that
already passed its readiness check will happily start the next node unless it re-checks the run
status after every await point.

- [ ] **Step 2: Implement**

The cancellation contract, added to `executors/base.py`:

```python
class StepExecutor(Protocol):
    def start(self, request: StepRequest) -> AsyncIterator[StepEvent]:
        """Begin the step. Cancellation is `aclose()` on the returned iterator.

        An implementation must make `aclose()` release its resources and must
        not yield afterwards. It may take time; the orchestrator bounds the
        wait and proceeds regardless.
        """
```

Nothing is *added* to the Protocol — `aclose()` is already part of the async-generator contract.
Saying so in the docstring is the change, because "how do I stop this" was otherwise unspecified
and an adapter author would have had to guess.

And in the orchestrator:

```python
    async def cancel(self, run_id: str) -> None:
        if self.store.get_run(run_id)["status"] in rs.RUN_TERMINAL:
            return                                     # idempotent

        # Status first, streams second: a driver coroutine between awaits must
        # observe the cancellation before it can schedule another node.
        self.store.set_run_status(run_id, rs.RUN_CANCELLED)
        self.store.cancel_unfinished_nodes(run_id)

        for (rid, node_id), stream in list(self._streams.items()):
            if rid != run_id:
                continue
            self._streams.pop((rid, node_id), None)
            try:
                await asyncio.wait_for(stream.aclose(), CANCEL_GRACE_SECONDS)
            except (asyncio.TimeoutError, Exception):
                # Bounded, not best-effort. The node is already CANCELLED in
                # the store; an adapter that will not close does not get to
                # keep the UI spinning.
                pass
```

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(orchestrator): retry, skip and cancel"
```

---

### Task 4: Recovery after a restart

**Files:**
- Modify: `packages/implr_studio/orchestrator.py`, `store.py`, `api.py`
- Test: `packages/implr_studio/tests/test_recovery.py`

**Interfaces:**
- `Orchestrator.recover() -> int` — returns how many nodes it reconciled. Called once at startup,
  **before** the server accepts a request.
- `store.unfinished_nodes() -> list[tuple[run_id, node_id, status]]`
- `orchestrator.RESTART_ERROR = "the service restarted while this step was running; it was not retried automatically"`

- [ ] **Step 1: Write the failing test**

```python
async def test_a_running_node_becomes_failed_on_recovery(tmp_path):
    """Not `pending` - that would look like it is about to run and it is not.
    Not retried - see the module docstring for why automatic retry is wrong."""
    store = make_store(tmp_path)
    run_id = seed_run(store, {"a": rs.SUCCEEDED, "b": rs.RUNNING, "c": rs.PENDING})

    orch = make_orchestrator(store)
    n = await orch.recover()

    assert n == 1
    assert orch.node_statuses(run_id) == {
        "a": rs.SUCCEEDED, "b": rs.FAILED, "c": rs.PENDING}


async def test_the_error_names_the_restart(tmp_path):
    """The operator must be able to tell 'the step failed' from 'the service
    died'. They lead to different next actions."""
    ...
    assert "restart" in store.get_node(run_id, "b")["error"].lower()


async def test_the_run_is_paused_not_failed(tmp_path):
    ...
    assert orch.run_status(run_id) == rs.RUN_PAUSED


async def test_recovery_does_not_start_anything(tmp_path):
    """A restart must not spend money. If recovery re-drove the run, a crash
    loop becomes a billing loop."""
    orch = make_orchestrator(store)

    await orch.recover()

    assert orch.executor.started == []


async def test_recovery_leaves_awaiting_states_alone(tmp_path):
    """A question, an approval and a review are durable decisions waiting for
    a human. A restart is not an answer."""
    run_id = seed_run(store, {"a": rs.AWAITING_INPUT, "b": rs.AWAITING_APPROVAL,
                              "c": rs.AWAITING_REVIEW})

    await make_orchestrator(store).recover()

    assert store.node_statuses(run_id) == {
        "a": rs.AWAITING_INPUT, "b": rs.AWAITING_APPROVAL, "c": rs.AWAITING_REVIEW}


async def test_recovery_leaves_terminal_runs_alone(tmp_path):
    run_id = seed_run(store, {"a": rs.SUCCEEDED}, run_status=rs.RUN_SUCCEEDED)

    await make_orchestrator(store).recover()

    assert store.get_run(run_id)["status"] == rs.RUN_SUCCEEDED


async def test_recovery_is_idempotent(tmp_path):
    orch = make_orchestrator(store)
    assert await orch.recover() == 1

    assert await orch.recover() == 0


async def test_recovery_spans_every_run(tmp_path):
    """Two runs interrupted by one kill. Recovering only the newest leaves a
    permanent spinner on the older one."""
    first = seed_run(store, {"a": rs.RUNNING})
    second = seed_run(store, {"a": rs.RUNNING})

    assert await make_orchestrator(store).recover() == 2


async def test_a_recovered_node_can_be_retried(tmp_path):
    """The recovery path and the ordinary failure path must converge, or
    'Retry' works on one kind of red node and not the other."""
    ...
    assert orch.node_statuses(run_id)["b"] == rs.SUCCEEDED


def test_the_server_recovers_before_serving(client_factory, tmp_path):
    """Asserted at the HTTP boundary: no request may observe a stale
    `running`. A recovery in a background task loses this race."""
    store = make_store(tmp_path)
    run_id = seed_run(store, {"a": rs.RUNNING})

    client = client_factory(tmp_path)              # constructs and starts the app

    body = client.get(url("/runs/%s" % run_id)).json()
    assert body["nodes"]["a"]["status"] == rs.FAILED


def test_recovery_emits_an_event_so_the_log_shows_it(tmp_path):
    """A node that changed status while nobody was watching should say so in
    its own log, not only in its status field."""
    ...
    assert any("restart" in e["payload"].get("error", "") for e in events)
```

- [ ] **Step 2: Implement**

```python
RESTART_ERROR = ("the service restarted while this step was running; "
                 "it was not retried automatically")


async def recover(self) -> int:
    """Reconcile nodes left mid-flight by a crash. Idempotent. Starts nothing.

    Automatic retry is deliberately absent: a step that failed by half-writing
    a file would half-write it again, and a step that crashed the process
    would crash it again - on boot, in a loop, while billing.
    """
    reconciled = 0
    for run_id, node_id, status in self.store.unfinished_nodes():
        if status != rs.RUNNING:
            continue                       # awaiting-* is a durable human wait
        self.store.set_node_status(run_id, node_id, rs.FAILED, error=RESTART_ERROR)
        self.store.append_event(run_id, node_id, "status",
                                {"status": rs.FAILED, "error": RESTART_ERROR})
        reconciled += 1

    for run_id in self.store.non_terminal_run_ids():
        self.store.set_run_status(run_id, self._finalise_run_status(run_id))
    return reconciled
```

Wire it into the app's lifespan **before** the router is reachable, not as a background task.

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(orchestrator): honest recovery after a restart"
```

---

### Task 5: The routes and run history

**Files:**
- Modify: `packages/implr_studio/api.py`, `store.py`
- Test: `packages/implr_studio/tests/test_api_recovery.py`

**Interfaces:**
- `POST /api/projects/{pid}/runs/{rid}/nodes/{node}/retry` → **202**
- `POST /api/projects/{pid}/runs/{rid}/nodes/{node}/skip` → **202**, body `{reason: str}`
- `POST /api/projects/{pid}/runs/{rid}/cancel` → **202**
- `GET /api/projects/{pid}/runs?limit=&before=` → newest first, keyset paginated.
- All three actions require `Permission.RUN_CONTROL`.

- [ ] **Step 1: Write the failing test**

```python
def test_retry_returns_202(client): ...
def test_skip_with_no_reason_is_422(client): ...
def test_cancel_returns_202_and_the_run_reports_cancelled(client): ...
def test_retrying_a_running_node_is_409(client): ...
def test_an_unknown_node_is_404(client): ...


def test_no_route_awaits_quiescence(api_source):
    """Phase 9's contract, still holding. `cancel` is the tempting one: it
    feels synchronous, and awaiting an uncooperative adapter would hold the
    request open for the full grace period."""
    assert "wait_quiescent" not in api_source


def test_run_history_is_newest_first(client):
    ids = [r["id"] for r in client.get(url("/runs")).json()["runs"]]

    assert ids == list(reversed(created_order))


def test_run_history_paginates_by_keyset_not_offset(client):
    """Offset pagination over a table that grows at the head shows duplicates.
    Runs are created while somebody is reading page two."""
    page1 = client.get(url("/runs?limit=2")).json()
    page2 = client.get(url("/runs?limit=2&before=%s" % page1["next"])).json()

    assert not ({r["id"] for r in page1["runs"]} & {r["id"] for r in page2["runs"]})


def test_all_three_actions_require_run_control(app):
    for path in ("retry", "skip", "cancel"):
        assert permission_for(app, path) is Permission.RUN_CONTROL
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 6: The UI

**Files:**
- Modify: `web/src/panels/RunPanel.tsx`, `web/src/api.ts`, `web/src/app.css`, `web/src/tokens.css`
- Create: `web/src/panels/RunHistory.tsx`
- Test: `web/src/panels/RunPanel.test.tsx`, `web/src/panels/RunHistory.test.tsx`

**Interfaces:**
- Error block: the message, the failing node, the log tail, and one line saying Studio did not
  revert anything.
- **Retry** and **Skip** on a failed node; **Abort** at run level.
- Skip is behind a confirm that requires the reason — the reason *is* the confirmation.
- `--st-skipped` and `--st-cancelled` in both palettes.

- [ ] **Step 1: Write the failing test**

```tsx
it('shows the error text, not just a red stripe');
it('shows the log tail from the failing node');
it('offers Retry and Skip on a failed node');
it('offers neither on a running node');
it('requires a reason before Skip is enabled');
it('shows the skip reason afterwards, on the node');
it('renders skipped and cancelled distinctly from failed');
it('says Studio did not revert any files');
it('shows the restart error differently from a step error');
it('disables every action on a cancelled run');
it('lists past runs newest first with their outcome');
```

Two are worth the argument:

- **"says Studio did not revert any files"** — the operator's first instinct after a failed
  `dev-executor` is to wonder what state the repo is in. Answer it in the error block, where they
  are already looking, rather than in documentation they will not read.
- **"shows the restart error differently from a step error"** — same status, different cause,
  different next action. A step error means read the log; a restart means just press Retry.

- [ ] **Step 2: Implement, run, build, commit**

```bash
git commit -m "feat(ui): failure, recovery and run history"
```

---

### Task 7: Run the demo

- [ ] **Step 1: Failure**

Script `arch-gen` to fail. Run. Node red with the error visible; run **paused**; downstream
**pending**; a parallel branch **finishes**.

- [ ] **Step 2: Retry**

Fix the script. Retry. It succeeds, the run continues, and upstream nodes were **not** re-run —
check `ex.started`.

- [ ] **Step 3: Skip**

Fail it again and Skip with a reason. The run proceeds. Then skip `dev-planner` on a pipeline with
an `artifact` gate downstream and watch the downstream node go **blocked**, not succeeded.

- [ ] **Step 4: Cancel**

Start a long fake run. Abort. Running node → `cancelled`, pending nodes → `cancelled`, completed
nodes untouched, and no further node starts.

- [ ] **Step 5: Restart recovery**

Start a run, `kill -9` the server mid-step, restart, reopen the browser.

- Completed nodes: still completed.
- The interrupted node: **`failed`**, error naming the restart, rendered differently from a step
  error.
- The run: **paused**.
- Nothing was retried — `ex.started` after restart is empty until you press Retry.
- Press Retry: it works, exactly like an ordinary failed node.

- [ ] **Step 6: History**

Open run history. Every run above, newest first, with its outcome. Page through it while starting
a new run and confirm no duplicates.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` pass; `npm run build` passes. Still no tokens spent.
- [ ] `NODE_TERMINAL` is exactly four states; only `succeeded` and `skipped` satisfy a dependency.
- [ ] A failure leaves downstream nodes **`pending`** and the run **`paused`**.
- [ ] An unrelated parallel branch still completes after a failure.
- [ ] A raising step produces a `failed` node whose error contains the exception text.
- [ ] Retry does not re-run the upstream, and clears error + approvals + cached stream.
- [ ] Retry is refused on a `running` node and on a `cancelled` run.
- [ ] Skip requires a reason, and the reason is visible on the node afterwards.
- [ ] **`skipped` satisfies a dependency and does not satisfy an artifact gate**, asserted by test.
- [ ] A skipped node can be retried.
- [ ] Cancel is idempotent, leaves completed nodes alone, marks pending nodes `cancelled`, starts
      nothing further, and is **bounded** when the executor ignores `aclose()`.
- [ ] `recover()` turns `running` → `failed` with an error naming the restart, leaves every
      `awaiting-*` state untouched, starts nothing, is idempotent, and spans every run.
- [ ] **Recovery completes before the server accepts a request**, asserted at the HTTP boundary.
- [ ] Recovery appends an event, so the change appears in the node's own log.
- [ ] No route awaits quiescence — still asserted by source test.
- [ ] Run history is newest-first and keyset-paginated.
- [ ] `--st-skipped` and `--st-cancelled` exist in both palettes; `tokens.test.ts` passes.
- [ ] The error block says Studio reverted nothing.

---

## Known limitations, kept

**An interrupted step's work is not resumed.** The agent's session dies with the process. The
node fails and a retry starts it over, which for `dev-executor` over twenty plans is expensive.
`ClaudeAgentOptions` has `resume` and `session_id`, so this is *possible* — it needs the session id
persisted per node-run and a resumption path in the adapter, which is Phase 15's territory and a
deliberate follow-up rather than a gap in this phase.

**Studio never reverts files.** A failed step may have left half-written artefacts. Git is the
undo, and the error block says so. Automatic rollback would mean Studio taking ownership of the
working tree, which is a much larger promise than it can keep — the agent also runs `git` itself.

**Run history grows forever.** No retention, no purge. SQLite handles years of local use; the
hosted answer is a retention policy alongside the Blob log archive in Phase 16.

---

## What the next phase gets

A run loop that survives contact with reality: failure, operator correction, cancellation and
restart. **Phase 15** replaces `FakeExecutor` with a real model — and needs every one of these
paths, because a real adapter fails in ways a scripted one never does. Notably, the recovery path
is what makes a mid-run rate-limit or a killed container an incident you can see rather than a
spinner.
