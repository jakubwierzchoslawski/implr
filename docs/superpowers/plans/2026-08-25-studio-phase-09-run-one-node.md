# implr Studio — Phase 9: Run one node

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Press Run. One node goes green. No model was called, and the HTTP request that started it returned before the node finished.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 3. **Not** on 4–8 — the run phases need the canvas and validation, not the configurator.

---

## Demo

Save a one-node pipeline. Press **Run**.

The node's stripe goes amber, then green. The right rail shows the run id and per-node status.
No model was called: `FakeExecutor` served a scripted `done`.

Then the two things that matter more than the green stripe:

```bash
# The start returns 202 BEFORE the run settles.
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
     "http://127.0.0.1:8000/api/projects/local/runs" -w "\nHTTP %{http_code}\n"
# {"run_id":"..."}
# HTTP 202
```

and, for a node with `--task PLAN-F-004#3`, that the value reached the executor as **two argv
elements** rather than one joined string. There is a test for it, because the difference is
invisible in the UI and is the whole point of Phase 4's validation.

---

## Why 202, and why it is a phase constraint rather than a detail

The obvious implementation awaits the run before responding: the response then reflects a
settled run, and every test is deterministic without polling.

It is the wrong trade, and it was a real defect in the first plan set. A `dev-executor` node
can run for twenty minutes. A blocking start holds one HTTP request open for the whole
pipeline, and the browser does not learn the `run_id` until there is nothing left to stream —
so **Phase 10 becomes impossible.**

So: every mutating route returns as soon as its state change is persisted. Tests get
determinism from a polling helper. That constraint starts here and holds through Phase 19.

---

## Scope boundary — not in this phase

Deliberately minimal. **One node, no gates, no logs, no questions, no failure handling.**

- **No `events` table.** Phase 10.
- **No gate evaluation.** A pipeline with a non-`none` gate is refused at run start with a
  clear message. Phase 11.
- **No multi-node scheduling.** A pipeline with more than one node is likewise refused. Phase 11.
- **No questions.** A `question` event from the executor is a hard error here. Phase 12.
- **No retry / skip / cancel.** Phase 14.
- **No `approval`.** Phase 13.

Refusing what is not yet supported, rather than half-doing it, is what keeps the phase
honest — and each refusal is a test that turns into a feature later.

---

## Global constraints

- The route returns **202** and never awaits quiescence.
- `Store` serialises every operation under a lock: sync FastAPI routes run in a threadpool
  while the driver task runs on the event loop, and they share one connection.
- A value-taking flag becomes **two** argv elements. Never interpolated into a string.
- The driver loop is exception-safe: a step that raises leaves a `failed` node, not a crashed
  service and not a node stuck at `running`.
- Nothing in `executors/base.py` or `executors/fake.py` names a provider.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/executors/base.py` | `StepRequest`, `StepEvent`, `StepHandle`, `StepExecutor` Protocol. Pure. |
| `packages/implr_studio/executors/fake.py` | `FakeExecutor`. Test double only. |
| `packages/implr_studio/runstate.py` | Status constants and the terminal sets. |
| `packages/implr_studio/store.py` | SQLite, `runs` + `node_runs` only. |
| `packages/implr_studio/orchestrator.py` | Single-node driver, `build_argv`. |
| `packages/implr_studio/api.py` | **Modified** — the run routes. |
| `web/src/panels/RunPanel.tsx` | Run-mode rail. |
| `web/src/App.tsx` | **Modified** — mode switch, Run button, polling. |

---

### Task 1: The executor contract and the fake

**Files:**
- Create: `packages/implr_studio/executors/{__init__,base,fake}.py`
- Test: `packages/implr_studio/tests/test_executor_base.py`, `test_fake_executor.py`

**Interfaces:**
- `StepRequest` — frozen: `node_id`, `skill`, `args: tuple[str, ...]`, `workspace: Path`, `timeout_seconds: int | None`, `models: dict[str, str]`, `feedback: tuple[str, ...]`.
- `StepEvent` — frozen: `kind`, `payload`. Constructors `log`, `question`, `artifact`, `done`. Accessors, and `is_terminal`.
- `StepExecutor` — Protocol: `start`, `events`, `answer`, `cancel`.
- `FakeExecutor(scripts=None, default=None)` with `.started`, `.answers`, `.cancelled`, `.set_script`.
- `EVENT_KINDS`, `OUTCOME_SUCCESS`, `OUTCOME_FAILURE`, `ExecutorError`.

`models` and `feedback` are on the request from the start even though Phase 9 uses neither —
Phase 5 writes the first and Phase 13 the second, and widening a frozen dataclass later means
touching every construction site.

**The question-arming rule is declared here and enforced in Phase 12.** An executor MUST record
its pending question *before* emitting the `question` event, and MUST accept `answer()` while
its iterator is suspended. Phase 9 does not exercise it; stating it now stops `fake.py` being
written the wrong way round and needing a fix later.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from implr_studio.executors import base


def _req(**kw):
    return base.StepRequest(node_id="a", skill="doc-ingest", workspace=Path("/ws"), **kw)


def test_step_request_is_frozen():
    with pytest.raises(Exception):
        _req().skill = "other"          # type: ignore[misc]


def test_skill_and_args_cross_as_data_not_a_command_string():
    """The adapter decides what they mean. The contract must not pre-format them."""
    req = _req(args=("--all", "--task", "PLAN-F-004#3"))

    assert req.args == ("--all", "--task", "PLAN-F-004#3")
    assert not hasattr(req, "command")
    assert not hasattr(req, "command_line")


def test_models_and_feedback_default_empty():
    """Present from Phase 9 so Phases 5 and 13 need not widen a frozen dataclass."""
    assert _req().models == {}
    assert _req().feedback == ()


def test_the_four_event_kinds():
    assert base.EVENT_KINDS == ("log", "question", "artifact", "done")


def test_done_rejects_an_unknown_outcome():
    with pytest.raises(ValueError, match="unknown outcome"):
        base.StepEvent.done("maybe", "hmm")


def test_only_done_is_terminal():
    assert base.StepEvent.done(base.OUTCOME_SUCCESS, "ok").is_terminal is True
    assert base.StepEvent.log("x").is_terminal is False
    assert base.StepEvent.question("q", "?").is_terminal is False


def test_accessors_on_the_wrong_kind_return_none():
    """Conveniences over payload; they must not explode."""
    assert base.StepEvent.log("x").outcome is None
    assert base.StepEvent.done(base.OUTCOME_SUCCESS, "ok").text is None


def test_base_names_no_provider():
    """The whole point of the module. If this fails, Phase 15's second adapter is dead."""
    source = Path(base.__file__).read_text(encoding="utf-8").lower()

    for banned in ("claude", "anthropic", "openai", "gpt", "gemini", "subprocess"):
        assert banned not in source, "leaked into the contract: %s" % banned
```

And for the fake:

```python
pytestmark = pytest.mark.asyncio


async def test_replays_scripted_events_in_order():
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.log("scanning"),
                                      base.StepEvent.done("success", "12 docs")]})
    handle = await ex.start(_req())

    events = [e async for e in ex.events(handle)]

    assert [e.kind for e in events] == ["log", "done"]


async def test_a_script_with_no_done_is_terminated_automatically():
    """events() must always terminate, or the orchestrator hangs forever."""
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.log("only a log")]})

    events = [e async for e in ex.events(await ex.start(_req()))]

    assert events[-1].kind == "done"


async def test_records_what_was_started():
    ex = FakeExecutor()
    await ex.start(_req(args=("--all",)))

    assert ex.started[0].args == ("--all",)


async def test_each_start_gets_a_distinct_handle():
    ex = FakeExecutor()

    assert (await ex.start(_req())).id != (await ex.start(_req())).id


async def test_satisfies_the_protocol():
    assert isinstance(FakeExecutor(), base.StepExecutor)


async def test_arms_a_pending_question_before_yielding_it():
    """The Phase 12 contract, asserted structurally now so fake.py is not written
    the wrong way round and fixed later."""
    import inspect

    body = inspect.getsource(FakeExecutor.events)

    assert body.index("pending_question") < body.index("yield event")
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(studio): provider-neutral executor contract and scripted fake"
```

---

### Task 2: `runstate` and the store

**Files:**
- Create: `packages/implr_studio/runstate.py`, `store.py`
- Test: `packages/implr_studio/tests/test_runstate.py`, `test_store.py`

**Interfaces:**
- `runstate`: `PENDING`, `BLOCKED`, `RUNNING`, `AWAITING_INPUT`, `AWAITING_APPROVAL`, `SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED`; run statuses; `NODE_TERMINAL`, `NODE_SATISFIES_DEPENDENCY`, `RUN_TERMINAL`; `is_terminal`, `satisfies_dependency`.
- `Store(db_path)` — `create_run`, `get_run`, `list_runs`, `set_run_status`, `get_node`, `get_nodes`, `set_node_status`, `close`.

Every status is declared now, including the ones Phases 11–14 use, because
`NODE_SATISFIES_DEPENDENCY` is the set Phase 11's scheduler reads and getting its membership
right is easier to reason about all at once.

**Every public `Store` method holds a lock.** Sync FastAPI routes run in a threadpool while the
driver task runs on the event loop; they share one `sqlite3` connection, and interleaved
`with self._conn:` transactions from two threads is a real race. The lock is non-reentrant, so
no public method may call another.

- [ ] **Step 1: Write the failing test**

```python
def test_only_succeeded_and_skipped_satisfy_a_dependency():
    """A failed upstream must never release a downstream node."""
    assert rs.satisfies_dependency(rs.SUCCEEDED) is True
    assert rs.satisfies_dependency(rs.SKIPPED) is True
    for status in (rs.FAILED, rs.CANCELLED, rs.RUNNING, rs.BLOCKED,
                   rs.AWAITING_INPUT, rs.AWAITING_APPROVAL, rs.PENDING):
        assert rs.satisfies_dependency(status) is False, status


def test_awaiting_states_are_not_terminal():
    for status in (rs.AWAITING_INPUT, rs.AWAITING_APPROVAL):
        assert rs.is_terminal(status) is False


def test_wire_values_are_hyphenated():
    assert rs.AWAITING_INPUT == "awaiting-input"
```

```python
def test_schema_is_created_idempotently(tmp_path):
    Store(tmp_path / "runs.db").close()
    Store(tmp_path / "runs.db").close()


def test_nodes_start_pending(store):
    _make_run(store)

    assert store.get_nodes("r1")["a"]["status"] == rs.PENDING


def test_started_at_is_stamped_on_running(store):
    _make_run(store)
    store.set_node_status("r1", "a", rs.RUNNING)

    node = store.get_node("r1", "a")
    assert node["started_at"] is not None
    assert node["finished_at"] is None


def test_started_at_is_not_overwritten_on_a_second_run(store):
    """Retry keeps the original start time, for run-duration reporting."""
    _make_run(store)
    store.set_node_status("r1", "a", rs.RUNNING)
    first = store.get_node("r1", "a")["started_at"]
    store.set_node_status("r1", "a", rs.FAILED, error="boom")

    store.set_node_status("r1", "a", rs.RUNNING)

    assert store.get_node("r1", "a")["started_at"] == first


def test_finished_at_is_stamped_on_any_terminal_status(store):
    ...


def test_a_run_survives_reopening_the_database(tmp_path):
    """The whole point of persistence."""
    ...


def test_list_runs_is_newest_first(store):
    ...


def test_every_public_method_takes_the_lock():
    """Sync routes run in a threadpool while the driver runs on the event loop, and
    they share one connection. A method that skips the lock is a race that shows up
    as an intermittent flake nobody can reproduce."""
    import inspect

    for name, fn in inspect.getmembers(Store, inspect.isfunction):
        if name.startswith("_"):
            continue
        assert "self._lock" in inspect.getsource(fn), name


def test_concurrent_writes_from_two_threads_do_not_corrupt(store):
    """The lock, exercised rather than inspected."""
    import threading

    _make_run(store)
    errors = []

    def hammer(status):
        try:
            for _ in range(200):
                store.set_node_status("r1", "a", status)
        except Exception as e:            # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=hammer, args=(s,))
               for s in (rs.RUNNING, rs.SUCCEEDED)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert errors == []
    assert store.get_node("r1", "a")["status"] in (rs.RUNNING, rs.SUCCEEDED)
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 3: The single-node orchestrator

**Files:**
- Create: `packages/implr_studio/orchestrator.py`
- Test: `packages/implr_studio/tests/test_orchestrator.py`

**Interfaces:**
- `Orchestrator(workspace, registry, contracts, executor, store, concurrency=1)`
- `await start_run(p, run_id=None) -> str` — validates, persists, spawns the driver, returns.
- `await wait_quiescent(run_id)` — **for tests only.** No route calls it.
- `run_status`, `node_statuses`
- `Orchestrator.build_argv(node, step) -> tuple[str, ...]` — static, pure.
- `UnavailableStepError`, `UnsupportedPipelineError`

- [ ] **Step 1: Write the failing test**

```python
# --- argv, the invisible correctness ---------------------------------------

def test_a_value_taking_flag_becomes_two_argv_elements(reg):
    """Never one interpolated string. The difference is invisible in the UI and is
    the entire point of Phase 4's value validation."""
    node = _node(args=["--task"], arg_values={"--task": "PLAN-F-004#3"})

    argv = Orchestrator.build_argv(node, reg.get("dev-executor"))

    assert argv == ("--task", "PLAN-F-004#3")
    assert "--task PLAN-F-004#3" not in " ".join(argv[:1])


def test_a_flag_without_a_value_contributes_one_element(reg):
    assert Orchestrator.build_argv(_node(args=["--all"]), reg.get("dev-executor")) == ("--all",)


def test_argv_preserves_selection_order(reg):
    node = _node(args=["--all", "--task"], arg_values={"--task": "X"})

    assert Orchestrator.build_argv(node, reg.get("dev-executor")) == ("--all", "--task", "X")


def test_a_value_with_shell_metacharacters_still_becomes_one_element(reg):
    """Save-time validation should have refused it; argv separation means even a
    value that got past that check cannot become shell syntax."""
    node = _node(args=["--task"], arg_values={"--task": "a; rm -rf /"})

    assert Orchestrator.build_argv(node, reg.get("dev-executor")) == ("--task", "a; rm -rf /")


# --- running one node ------------------------------------------------------

async def test_runs_the_node_and_reports_success(orch):
    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED}
    assert orch.run_status(run_id) == rs.RUN_SUCCEEDED
    assert [r.skill for r in orch.executor.started] == ["doc-ingest"]


async def test_the_request_carries_the_workspace_and_the_argv(orch):
    run_id = await orch.start_run(_one_node(args=["--dry-run"]))
    await orch.wait_quiescent(run_id)

    req = orch.executor.started[0]
    assert req.args == ("--dry-run",)
    assert req.workspace == orch.workspace


async def test_a_failing_node_pauses_the_run(orch):
    orch.executor.set_script("doc-ingest",
                             [base.StepEvent.done("failure", "broke", error="exit 1")])

    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.FAILED}
    assert orch.run_status(run_id) == rs.RUN_PAUSED
    assert orch.store.get_node(run_id, "a")["error"] == "exit 1"


async def test_start_returns_before_the_node_finishes(orch):
    """The 202 contract at the orchestrator level: start_run spawns and returns."""
    orch.executor.set_script("doc-ingest", [base.StepEvent.log("slow"),
                                            base.StepEvent.done("success", "ok")])

    run_id = await orch.start_run(_one_node())

    # Not yet settled - no await of quiescence happened.
    assert orch.node_statuses(run_id)["a"] in (rs.PENDING, rs.RUNNING)
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED


# --- refusing what is not built yet ----------------------------------------

async def test_an_unavailable_step_is_refused_at_run_start(orch):
    """Designing ahead is fine; executing a skill that does not exist is not."""
    with pytest.raises(orchestrator.UnavailableStepError, match="sec-review"):
        await orch.start_run(_one_node(step="sec-review"))

    assert orch.executor.started == []


async def test_more_than_one_node_is_refused_with_a_clear_message(orch):
    """Phase 11 lifts this. Refusing beats half-scheduling."""
    with pytest.raises(orchestrator.UnsupportedPipelineError, match="one node"):
        await orch.start_run(_two_nodes())


async def test_a_non_none_gate_is_refused_with_a_clear_message(orch):
    with pytest.raises(orchestrator.UnsupportedPipelineError, match="condition"):
        await orch.start_run(_one_node_with_gate())


async def test_a_question_event_is_a_hard_error_in_this_phase(orch):
    """Phase 12 handles it. Silently ignoring it would hang the run."""
    orch.executor.set_script("doc-ingest", [base.StepEvent.question("q1", "?")])

    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.FAILED
    assert "question" in orch.store.get_node(run_id, "a")["error"].lower()


# --- the driver must not crash the service ---------------------------------

async def test_an_executor_that_raises_leaves_a_failed_node(orch):
    """Not a node stuck at running, and not an exception escaping into a route as
    a 500 with the run in an unreadable state."""
    class Exploding:
        async def start(self, req): raise RuntimeError("transport died")

    orch.executor = Exploding()

    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.FAILED
    assert "transport died" in orch.store.get_node(run_id, "a")["error"]
    assert orch.run_status(run_id) == rs.RUN_PAUSED


async def test_two_orchestrators_share_no_state(tmp_path):
    """_handles and _streams must be instance attributes. A class-level dict leaks
    run state between instances and between tests."""
    a, b = _make_orch(tmp_path / "a"), _make_orch(tmp_path / "b")

    await a.start_run(_one_node())

    assert b._handles == {}
```

- [ ] **Step 2: Implement**

`_drive` with the exception guard, which is the part most easily left out:

```python
    async def _drive(self, run_id: str) -> None:
        try:
            while True:
                node_id = self._next_ready(run_id)
                if node_id is None:
                    break
                try:
                    await self._run_node(run_id, node_id)
                except asyncio.CancelledError:
                    raise
                except Exception as e:                      # noqa: BLE001
                    # A step that blew up is a failed step, not a crashed service.
                    self._handles.pop((run_id, node_id), None)
                    self._streams.pop((run_id, node_id), None)
                    self.store.set_node_status(
                        run_id, node_id, rs.FAILED,
                        summary="the step raised before reporting a result",
                        error="%s: %s" % (type(e).__name__, e))
                    break
        finally:
            self._finalise_run_status(run_id)
```

`_handles` and `_streams` are initialised in `__init__`, **not** as class attributes — a
class-level dict is shared by every instance and leaks state between tests.

- [ ] **Step 3: Run, commit**

---

### Task 4: The run routes

**Files:**
- Modify: `packages/implr_studio/api.py`, `context.py`
- Create: `packages/implr_studio/tests/conftest.py` — the polling helpers
- Test: `packages/implr_studio/tests/test_api_runs.py`

**Interfaces:**
- `POST /api/projects/{pid}/runs` → **202** `{run_id}`. `409` if no pipeline saved; `422` if a step is unavailable or the pipeline is unsupported. `RUN_START`.
- `GET /api/projects/{pid}/runs` → `{runs: [...]}`, newest first. `PROJECT_READ`.
- `GET /api/projects/{pid}/runs/{rid}` → detail. `404` if the run is not in this project.
- `context.build_context` gains `store` and `orchestrator`.

**No route calls `wait_quiescent`.** The helpers below are the only waiting logic in the
codebase, and they live in tests.

- [ ] **Step 1: Write the helpers**

```python
# packages/implr_studio/tests/conftest.py
import time


def wait_for(predicate, timeout: float = 5.0, interval: float = 0.02):
    """Poll until predicate() is truthy, then return it. Raises on timeout.

    The API deliberately does not block until a run settles, so tests poll. This is
    the ONLY place waiting logic lives: never add a sleep to a test, and never make
    a production route wait to make a test simpler.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    raise AssertionError("condition not met within %ss" % timeout)


def wait_for_run(client, pid, run_id, *, until=None):
    """Return the run detail once it is no longer `running`, or once `until` holds."""
    from implr_studio import runstate as rs

    def settled():
        detail = client.get("/api/projects/%s/runs/%s" % (pid, run_id)).json()
        if until is not None:
            return detail if until(detail) else None
        return detail if detail["status"] != rs.RUN_RUNNING else None

    return wait_for(settled)
```

- [ ] **Step 2: Write the failing test**

```python
def test_start_returns_202(client):
    client.put(f"/api/projects/{PID}/pipeline", json=ONE_NODE)

    r = client.post(f"/api/projects/{PID}/runs")

    assert r.status_code == 202
    assert r.json()["run_id"]


def test_start_returns_before_the_run_settles(client):
    """THE regression test. The step parks on an event that never terminates, so a
    blocking start would hang this test rather than pass it slowly."""
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.log("working")] * 500})
    client, ctx = _client(workspace, ex)
    client.put(f"/api/projects/{PID}/pipeline", json=ONE_NODE)

    r = client.post(f"/api/projects/{PID}/runs")

    assert r.status_code == 202          # returned, not waited


def test_the_run_completes_and_the_detail_reflects_it(client):
    client.put(f"/api/projects/{PID}/pipeline", json=ONE_NODE)
    run_id = client.post(f"/api/projects/{PID}/runs").json()["run_id"]

    detail = wait_for_run(client, PID, run_id)

    assert detail["status"] == rs.RUN_SUCCEEDED
    assert detail["nodes"]["a"]["status"] == rs.SUCCEEDED


def test_starting_without_a_saved_pipeline_is_409(client):
    assert client.post(f"/api/projects/{PID}/runs").status_code == 409


def test_the_body_cannot_smuggle_a_pipeline(client):
    """The run executes what was SAVED. A request must not supply a graph."""
    client.put(f"/api/projects/{PID}/pipeline", json=ONE_NODE)
    smuggled = {"pipeline": {"version": 1, "nodes": [
        {"id": "evil", "step": "dev-executor", "args": ["--commit"],
         "position": {"x": 0, "y": 0}}], "edges": []}}

    run_id = client.post(f"/api/projects/{PID}/runs", json=smuggled).json()["run_id"]
    wait_for_run(client, PID, run_id)

    assert set(client.get(f"/api/projects/{PID}/runs/{run_id}").json()["nodes"]) == {"a"}


def test_an_unavailable_step_is_422(client):
    client.put(f"/api/projects/{PID}/pipeline", json=PLANNED_STEP)

    r = client.post(f"/api/projects/{PID}/runs")

    assert r.status_code == 422
    assert "sec-review" in r.text


def test_an_unsupported_pipeline_is_422_with_a_readable_reason(client):
    client.put(f"/api/projects/{PID}/pipeline", json=TWO_NODES)

    r = client.post(f"/api/projects/{PID}/runs")

    assert r.status_code == 422
    assert "one node" in r.text.lower()


def test_a_run_id_from_another_project_is_404_not_403(client, other_pid):
    """A resource you may not see does not exist."""
    ...


def test_list_runs_is_newest_first(client):
    ...


def test_an_unknown_run_is_404(client):
    assert client.get(f"/api/projects/{PID}/runs/nope").status_code == 404


def test_no_route_awaits_quiescence():
    """The constraint, asserted rather than trusted."""
    import inspect
    from implr_studio import api

    assert "wait_quiescent" not in inspect.getsource(api)
```

- [ ] **Step 3: Implement, run, commit**

---

### Task 5: Run mode

**Files:**
- Create: `web/src/panels/RunPanel.tsx`
- Modify: `web/src/App.tsx`, `web/src/store.ts`, `web/src/api.ts`, `web/src/nodes/StepNode.tsx`, `web/src/app.css`
- Test: `web/src/panels/RunPanel.test.tsx`, `web/src/store.test.ts` (extend)

**Interfaces:**
- `api.startRun(projectId)`, `api.getRun(projectId, runId)`
- `store.runId`, `runStatus`, `nodeStates`, `applyRunDetail(detail)`
- A mode switch; `StepNode` tints its stripe by `data.status`; `RunPanel` shows the run and the selected node.

Phase 9 **polls** `GET …/runs/{rid}` every 1s while the run is not terminal. Phase 10 replaces
that with the WebSocket. Polling first is deliberate: it proves the 202 contract end to end
with a mechanism that cannot mask a blocking start.

- [ ] **Step 1: Write the failing tests**

```tsx
it('prompts to press Run when there is no run yet');
it('shows the run id and status');
it('shows the selected node status');
it('tints a node stripe by run state');
it('stops polling once the run is terminal');   // or it polls forever
it('shows a failed node error');
it('switches to run mode when Run is pressed');
```

`it('stops polling once the run is terminal')` matters: a poll loop with no exit condition is
the kind of thing that looks fine locally and shows up as a support ticket about battery life.

- [ ] **Step 2: Implement, run, build, commit**

---

### Task 6: Run the demo

- [ ] **Step 1** — one-node pipeline, press Run, watch amber → green. No tokens.
- [ ] **Step 2** — `curl -w "HTTP %{http_code}"` the start route: **202**.
- [ ] **Step 3** — script a failure (`implr-studio --fake` uses the default script; use the
      probe script in `docs/RUNTIME.md`). The node goes red, the run **paused**, the error shown.
- [ ] **Step 4** — save a two-node pipeline and press Run: **422**, *"this phase runs one node"*.
      A clear refusal, not a partial run.
- [ ] **Step 5** — kill the backend mid-run and restart it. The run is still there, the node
      still says `running`, and **nothing recovers it**. That is correct for Phase 9 and is the
      before-state Phase 14's demo contrasts with.

---

## Definition of Done

- [ ] `python -m pytest` passes with **no model invoked**.
- [ ] `npm test` and `npm run build` pass.
- [ ] `POST …/runs` returns **202** and no route contains `wait_quiescent` — asserted by a
      source test.
- [ ] A value-taking flag reaches the executor as **two** argv elements.
- [ ] `base.py` names no provider.
- [ ] `FakeExecutor.events` arms its pending question **before** the yield.
- [ ] `events()` always terminates, including for a script with no `done`.
- [ ] Every public `Store` method holds the lock, and a two-thread hammer test passes.
- [ ] `started_at` survives a second run of the same node; `finished_at` is stamped on any
      terminal status.
- [ ] An executor that raises leaves a `failed` node and a `paused` run — never a node stuck at
      `running`.
- [ ] `_handles` and `_streams` are instance attributes.
- [ ] Multi-node pipelines, non-`none` gates and `question` events are each refused with a
      readable reason rather than half-handled.
- [ ] A request body cannot smuggle a pipeline.
- [ ] A run id from another project returns **404**.
- [ ] **The demo:** amber to green, 202 from the start route, and a clear refusal for a
      two-node pipeline.

---

## What the next phase gets

A run that works and a UI that polls. **Phase 10** adds the `events` table and the WebSocket —
and its demo is the one that proves this phase's 202 was right: log lines appearing *while* the
step runs, not in one burst at the end.
