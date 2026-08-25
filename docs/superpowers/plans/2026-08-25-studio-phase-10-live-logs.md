# implr Studio — Phase 10: Live logs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Log lines appear *while* the step is running, not in one burst at the end — and a browser refresh mid-run loses nothing and duplicates nothing.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 9.

---

## Demo

Script a step with several log lines and a delay between them. Press **Run**.

Lines appear **progressively**. Then, mid-run, hit browser refresh: the log is complete, in
order, with nothing repeated.

**This is the demo that proves Phase 9's 202 was right.** If the lines arrive all at once when
the run finishes, a route is waiting for quiescence somewhere — and no amount of WebSocket
work will fix it.

```bash
# The cursor contract, checked directly.
RUN=$(curl -s -X POST "http://127.0.0.1:8000/api/projects/local/runs" \
      -H "Authorization: Bearer $TOKEN" | python -c "import json,sys;print(json.load(sys.stdin)['run_id'])")
python packages/implr_studio/tests/probe_stream.py "$RUN"
# ... events stream in ...
# cursor replay clean: no seq <= the last one already seen
```

---

## Scope boundary — not in this phase

- **Still one node.** Multi-node scheduling is Phase 11.
- **No questions.** A `question` event is still a hard error. Phase 12.
- **No log archive.** Every event lives in the table. Phase 16 moves the tail beyond N to Blob
  Storage; here the volume is a fake executor's script.
- **No log search or filtering.** A `<pre>` that scrolls.
- **No ANSI colour parsing.** The adapter emits plain text; Phase 15 decides whether that
  changes.

---

## Global constraints

- **Persist before broadcast.** Every event is written to the store *before* it can be
  observed. The persisted record is never behind what a client has seen, which is what makes
  refresh-safe replay possible at all.
- `events.seq` is one **monotonic** sequence, and the cursor is a **position, never an
  authorization**. A client supplying a cursor gets events for *its* run, filtered
  server-side — Phase 17's tenancy depends on that being true from the start.
- The socket **closes** once the run is terminal and the backlog is drained. A finished run
  must not hold a connection open forever.
- The WebSocket route reads the store and nothing else. It does not touch the orchestrator.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/store.py` | **Modified** — the `events` table, `append_event`, `events_since`. |
| `packages/implr_studio/orchestrator.py` | **Modified** — persist every event and every transition. |
| `packages/implr_studio/serialize.py` | **Modified** — `event_to_dict`. |
| `packages/implr_studio/api.py` | **Modified** — the WebSocket route. |
| `packages/implr_studio/tests/probe_stream.py` | A manual probe for the demo. |
| `web/src/api.ts` | **Modified** — `openStream`. |
| `web/src/store.ts` | **Modified** — `logs`, `cursor`, `applyEvents`. |
| `web/src/panels/RunPanel.tsx` | **Modified** — the log pane. |

---

### Task 1: The `events` table

**Files:**
- Modify: `packages/implr_studio/store.py`
- Test: `packages/implr_studio/tests/test_store_events.py`

**Interfaces:**
- `append_event(run_id, node_id | None, kind, payload: dict) -> int` — returns the `seq`.
- `events_since(run_id, cursor=0, limit=1000) -> list[dict]` — keys `seq`, `node_id`, `kind`, `payload`, `created_at`.

- [ ] **Step 1: Write the failing test**

```python
def test_seq_is_monotonic(store):
    _make_run(store)

    a = store.append_event("r1", "n", "log", {"text": "one"})
    b = store.append_event("r1", "n", "log", {"text": "two"})

    assert b > a


def test_events_since_returns_only_newer(store):
    _make_run(store)
    store.append_event("r1", "n", "log", {"text": "one"})
    cursor = store.append_event("r1", "n", "log", {"text": "two"})
    store.append_event("r1", "n", "log", {"text": "three"})

    assert [e["payload"]["text"] for e in store.events_since("r1", cursor)] == ["three"]


def test_cursor_zero_returns_everything(store):
    ...


def test_events_are_scoped_to_their_run(store):
    """The cursor is a position, not an authorization. A cursor from one run must
    never surface another run's events - Phase 17's tenancy depends on it."""
    _make_run(store, "r1")
    _make_run(store, "r2")
    store.append_event("r1", "n", "log", {"text": "mine"})
    store.append_event("r2", "n", "log", {"text": "theirs"})

    assert [e["payload"]["text"] for e in store.events_since("r1", 0)] == ["mine"]


def test_a_cursor_from_another_run_does_not_leak(store):
    """Explicitly: pass r2's seq as r1's cursor. r1 must still see only its own."""
    _make_run(store, "r1")
    _make_run(store, "r2")
    store.append_event("r1", "n", "log", {"text": "mine"})
    other = store.append_event("r2", "n", "log", {"text": "theirs"})

    assert store.events_since("r1", other) == []          # nothing of r1's is newer
    assert [e["payload"]["text"] for e in store.events_since("r1", 0)] == ["mine"]


def test_limit_is_respected(store):
    ...


def test_a_run_level_event_has_a_null_node(store):
    """Cancellation and run-status transitions belong to the run, not a node."""
    _make_run(store)

    store.append_event("r1", None, "status", {"status": "cancelled"})

    assert store.events_since("r1", 0)[0]["node_id"] is None


def test_the_payload_round_trips_as_json(store):
    _make_run(store)

    store.append_event("r1", "n", "question", {"options": ["a", "b"], "n": 1, "x": None})

    assert store.events_since("r1", 0)[0]["payload"] == {
        "options": ["a", "b"], "n": 1, "x": None}


def test_events_survive_reopening_the_database(tmp_path):
    ...


def test_append_event_holds_the_lock():
    import inspect
    assert "self._lock" in inspect.getsource(Store.append_event)
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 2: The orchestrator persists everything

**Files:**
- Modify: `packages/implr_studio/orchestrator.py`
- Test: `packages/implr_studio/tests/test_orchestrator_events.py`

Every `StepEvent` is appended, and every status transition is appended as a `status` event —
**before** it becomes observable.

- [ ] **Step 1: Write the failing test**

```python
async def test_log_events_are_persisted_in_order(orch, store):
    orch.executor.set_script("doc-ingest", [
        base.StepEvent.log("one"), base.StepEvent.log("two"),
        base.StepEvent.done("success", "ok")])

    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    logs = [e for e in store.events_since(run_id, 0) if e["kind"] == "log"]
    assert [e["payload"]["text"] for e in logs] == ["one", "two"]
    assert logs[0]["seq"] < logs[1]["seq"]


async def test_status_transitions_are_persisted_too(orch, store):
    """The client rebuilds node state from the stream, so a transition it never
    saw is a node stuck on the wrong colour after a refresh."""
    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    statuses = [e["payload"]["status"] for e in store.events_since(run_id, 0)
                if e["kind"] == "status"]
    assert statuses == [rs.RUNNING, rs.SUCCEEDED]


async def test_a_status_event_is_persisted_before_the_node_row_is_observable(orch, store):
    """Persist before broadcast. If the row changes first, a client polling between
    the two sees a state with no event explaining it."""
    ...


async def test_the_terminal_event_is_persisted(orch, store):
    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    kinds = [e["kind"] for e in store.events_since(run_id, 0)]
    assert kinds[-1] in ("status", "done")
    assert "done" in kinds


async def test_a_failure_persists_its_error(orch, store):
    ...


async def test_an_artifact_event_is_persisted_but_changes_no_state(orch, store):
    """Advisory only: gates read the filesystem, never this event."""
    orch.executor.set_script("doc-ingest", [
        base.StepEvent.artifact("docs/ARCHITECTURE.md"),
        base.StepEvent.done("success", "ok")])

    run_id = await orch.start_run(_one_node())
    await orch.wait_quiescent(run_id)

    assert any(e["kind"] == "artifact" for e in store.events_since(run_id, 0))
    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 3: The WebSocket

**Files:**
- Modify: `packages/implr_studio/api.py`, `serialize.py`
- Create: `packages/implr_studio/tests/probe_stream.py`
- Test: `packages/implr_studio/tests/test_api_stream.py`

**Interfaces:**
- `WS /api/projects/{pid}/runs/{rid}/stream?cursor=N`
- Frames: `{"type": "events", events: [...], cursor: N}`, `{"type": "run-status", status}`, `{"type": "error", message}`.
- On connect: replay everything after `cursor`, then poll the store every 250 ms.
- Close when the run is terminal **and** the backlog is empty.

The poll loop is deliberately simple. SQLite is local, and a poll has no cross-process
coordination to get wrong — a notification mechanism would be a second thing to keep correct
for no benefit at this scale.

- [ ] **Step 1: Write the failing test**

```python
def test_replays_history_for_a_finished_run(client):
    run_id = _run_to_completion(client)

    with client.websocket_connect(_stream(run_id, cursor=0)) as ws:
        frames = _drain(ws)

    texts = [e["payload"]["text"] for f in frames if f["type"] == "events"
             for e in f["events"] if e["kind"] == "log"]
    assert texts == ["one", "two"]


def test_a_cursor_skips_what_was_already_seen(client, ctx):
    """A reconnecting browser must not re-render the whole log."""
    run_id = _run_to_completion(client)
    wait_for(lambda: len(ctx.store.events_since(run_id, 0)) >= 2)
    midpoint = ctx.store.events_since(run_id, 0)[0]["seq"]

    with client.websocket_connect(_stream(run_id, cursor=midpoint)) as ws:
        frames = _drain(ws)

    seqs = [e["seq"] for f in frames if f["type"] == "events" for e in f["events"]]
    assert all(s > midpoint for s in seqs)


def test_no_event_is_delivered_twice_across_a_reconnect(client, ctx):
    """The refresh-safety guarantee, asserted rather than assumed."""
    run_id = _run_to_completion(client)

    with client.websocket_connect(_stream(run_id, 0)) as ws:
        first = _seqs(_drain(ws))
    with client.websocket_connect(_stream(run_id, max(first))) as ws:
        second = _seqs(_drain(ws))

    assert set(first) & set(second) == set()


def test_the_final_run_status_is_sent(client):
    ...


def test_the_socket_closes_on_a_terminal_run(client):
    """A finished run must not hold a connection open forever."""
    run_id = _run_to_completion(client)

    with client.websocket_connect(_stream(run_id, 0)) as ws:
        frames = _drain(ws)          # _drain returns when the server closes

    assert frames


def test_the_backlog_is_drained_before_closing(client):
    """A fast run finishes before the first poll. Closing on 'terminal' alone would
    drop its entire log."""
    run_id = _run_to_completion(client)

    with client.websocket_connect(_stream(run_id, 0)) as ws:
        frames = _drain(ws)

    assert any(e["kind"] == "done" for f in frames if f["type"] == "events"
               for e in f["events"])


def test_an_unknown_run_gets_an_error_frame_then_a_close(client):
    with client.websocket_connect(_stream("nope", 0)) as ws:
        frames = _drain(ws)

    assert frames[0]["type"] == "error"


def test_a_run_from_another_project_gets_an_error_not_its_events(client, other_pid):
    """The path carries the project. The run must belong to it."""
    ...


def test_events_stream_while_the_run_is_still_going(client):
    """THE test. A slow script, and a frame arrives before the run is terminal."""
    ex = FakeExecutor({"doc-ingest": _slow_script()})
    client, ctx = _client(workspace, ex)
    client.put(_url("/pipeline"), json=ONE_NODE)
    run_id = client.post(_url("/runs")).json()["run_id"]

    with client.websocket_connect(_stream(run_id, 0)) as ws:
        first = ws.receive_json()
        status = client.get(_url("/runs/%s" % run_id)).json()["status"]

    assert first["type"] in ("events", "run-status")
    assert status == rs.RUN_RUNNING          # still going when the first frame arrived
```

- [ ] **Step 2: Implement**

```python
    @app.websocket("/api/projects/{pid}/runs/{rid}/stream")
    async def stream(websocket: WebSocket, pid: str, rid: str, cursor: int = 0) -> None:
        import asyncio

        await websocket.accept()
        run = store.get_run(rid)
        # The path carries the project; the run must belong to it. An unguessable
        # id is not authorization.
        if run is None or run["project_id"] != pid:
            await websocket.send_json({"type": "error", "message": "unknown run: %s" % rid})
            await websocket.close()
            return

        last_status = None
        try:
            while True:
                events = store.events_since(rid, cursor)
                if events:
                    cursor = events[-1]["seq"]
                    await websocket.send_json({
                        "type": "events",
                        "events": [serialize.event_to_dict(e) for e in events],
                        "cursor": cursor,
                    })

                current = store.get_run(rid)
                status = current["status"] if current else None
                if status != last_status:
                    last_status = status
                    await websocket.send_json({"type": "run-status", "status": status})

                # Drain the backlog BEFORE closing. A fast run finishes before the
                # first poll, and closing on `terminal` alone drops its whole log.
                if status in rs.RUN_TERMINAL and not store.events_since(rid, cursor):
                    await websocket.close()
                    return

                await asyncio.sleep(0.25)
        except WebSocketDisconnect:
            return
```

Also write `packages/implr_studio/tests/probe_stream.py` — a small `websockets` client that
streams a run and asserts no stale sequence numbers on reconnect. It is used by the demo and by
`docs/RUNTIME.md`, and `websockets` ships with `uvicorn[standard]`, so it adds no dependency.

- [ ] **Step 3: Run, commit**

---

### Task 4: The log pane

**Files:**
- Modify: `web/src/api.ts`, `store.ts`, `panels/RunPanel.tsx`, `App.tsx`, `app.css`
- Test: `web/src/store.test.ts` (extend), `panels/RunPanel.test.tsx` (extend)

**Interfaces:**
- `api.openStream(projectId, runId, cursor, handlers) -> WebSocket`
- `store.logs: Record<string, string[]>`, `store.cursor`, `store.applyEvents(events, cursor?)`
- `RunPanel` renders the selected node's log.

`App.onRun` opens the socket **immediately after the 202**, and the Phase 9 poll is removed.

- [ ] **Step 1: Write the failing test**

```ts
it('appends logs per node', () => { ... });

it('advances the cursor to the last seq', () => { ... });

it('prefers the frame cursor over the last seq when given one', () => {
  // The server is authoritative about position.
  ...
});

it('applies status events to node state', () => {
  // The client rebuilds node colour from the stream, so a status event must land.
  ...
});

it('is idempotent for a replayed event', () => {
  // Belt and braces: the cursor should prevent this, but a duplicated line in a
  // log is a visible bug and cheap to rule out.
  const events = [{ seq: 1, node_id: 'a', kind: 'log', payload: { text: 'one' }, created_at: '' }];
  usePipelineStore.getState().applyEvents(events);
  usePipelineStore.getState().applyEvents(events);

  expect(usePipelineStore.getState().logs.a).toEqual(['one']);
});

it('keeps logs separate per node', () => { ... });

it('handles an event with a null node_id', () => { ... });
```

```tsx
it('shows the selected node log');
it('shows an empty state for a node with no output yet');
it('closes the socket on unmount');            // or the tab leaks a connection
it('reopens the stream from the stored cursor after a remount');
```

- [ ] **Step 2: Implement, run, build, commit**

---

### Task 5: Run the demo

- [ ] **Step 1** — a slow script. Lines appear **progressively**. If they arrive in one burst,
      stop and find the route that is awaiting quiescence.
- [ ] **Step 2** — refresh mid-run. The log is complete, ordered, and nothing is duplicated.
- [ ] **Step 3** — `python packages/implr_studio/tests/probe_stream.py $RUN`. It reports
      `cursor replay clean`.
- [ ] **Step 4** — open the same run in two browser tabs. Both stream; neither interferes.
- [ ] **Step 5** — let the run finish and watch the socket **close**. Check devtools: the
      connection is not left open.
- [ ] **Step 6** — a very fast run (a script with a single `done`). Its log is still complete —
      that is the backlog-drain path.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` / `npm run build` pass, with no model invoked.
- [ ] Log lines arrive **while the run is going**, asserted by a test that checks the run is
      still `running` when the first frame lands.
- [ ] A cursor returns only newer events; reconnecting delivers **no** event twice.
- [ ] A cursor from another run leaks nothing.
- [ ] A run from another project gets an `error` frame, not its events.
- [ ] The socket closes on a terminal run, **after** draining the backlog — a single-event run
      still delivers its log.
- [ ] Status transitions are persisted as events, so a refreshed client rebuilds node colour.
- [ ] `artifact` events are persisted and change no state.
- [ ] `applyEvents` is idempotent for a replayed event.
- [ ] The client closes its socket on unmount.
- [ ] Phase 9's polling is **removed** — the socket is the only mechanism.

---

## What the next phase gets

Live output. **Phase 11** lifts the one-node restriction: runtime gate evaluation, scheduling,
and the `blocked` state — whose demo is a gate that opens because you edited a file on disk,
with no click at all.
