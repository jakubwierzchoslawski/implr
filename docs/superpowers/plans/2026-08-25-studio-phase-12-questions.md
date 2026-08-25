# implr Studio — Phase 12: Questions

> **You are here for one assertion:** `len(ex.started) == 1` across a whole question round trip. If answering restarts the step instead of resuming it, everything below still *looks* right in the browser — and every interactive step silently costs double.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A step asks a question mid-run, it appears in the browser, and your answer reaches the step — which continues **in the same session**.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phases 9–11.

---

## Demo

Script `arch-gen` to ask which database. Run.

The node goes **`awaiting-input`** (violet). The rail shows a question card: the prompt as
markdown, the agent's own options as buttons, and a free-text box. Click **Postgres**. The step
continues and completes; the run proceeds.

Then the check that matters, which the browser cannot show you:

```bash
python -m pytest packages/implr_studio/tests/test_questions.py -k resumes -v
```

`ex.started` must list `arch-gen` **once**. Twice means answering restarted the step from the
top — and with a real adapter that means the agent lost its context, redid its reasoning, and
you paid for it twice.

---

## The two rules this phase turns on

### 1. Answering resumes the stream; it does not restart the step

When a question arrives, the driver **stops consuming events and returns** — the run is now
waiting on a human, possibly for hours. The executor's event iterator is left suspended
mid-stream.

Answering must **resume that same iterator**. So the orchestrator caches one live iterator per
`(run_id, node_id)` in `self._streams`, created when the step starts and resumed on a later
driver pass. Restarting is the obvious implementation and it is wrong: a real agent's session
holds the context that produced the question.

Contrast with Phase 13, deliberately: *request-changes* **discards** the stream, because the
point there is to start over with new information.

### 2. An executor must arm its pending question *before* emitting the event

This is the contract declared in Phase 9 and enforced here, and it is subtle enough to have
been a real defect in the first plan set.

The consumer abandons the iterator the moment it sees a `question` event. If the executor sets
its `pending_question` *after* the `yield`, that line never runs — so `answer()` arrives, finds
no pending question, and raises. And if it also clears its `answered` event after the yield, it
wipes a reply that had already landed and waits forever.

`FakeExecutor` must arm before the yield. Phase 9 asserted that structurally; this phase
asserts it behaviourally, with a test that abandons the iterator exactly as the driver does.

---

## Scope boundary — not in this phase

- **`options` render as buttons, and that is all they do.** No multi-select, no typed answers,
  no validation of the reply against the options — the operator may always type something the
  agent did not offer.
- **One pending question per node.** A second question from the same node before the first is
  answered is a protocol error.
- **No question history in the UI.** The card shows the current question; the log shows the rest.
- **No retry / skip / cancel.** Phase 14.
- **No node-level approval.** Phase 13.

---

## Global constraints

- The question is **persisted before** it is observable, so a service restart mid-question does
  not lose the prompt. (Recovering the *session* is Phase 14's problem, and its answer is that
  it cannot be — the node is reported failed.)
- `answer()` is idempotent-ish: answering an already-answered question is a `409`, not a
  double-delivery to the executor.
- `--st-input` is already a reserved token. No new colour.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/executors/fake.py` | **Modified** — arm before yield. |
| `packages/implr_studio/store.py` | **Modified** — the `questions` table. |
| `packages/implr_studio/orchestrator.py` | **Modified** — the question pause, the cached stream, `answer`. |
| `packages/implr_studio/api.py` | **Modified** — the answer route; the `question` refusal removed. |
| `web/src/panels/QuestionCard.tsx` | The affordance. |
| `web/src/store.ts` | **Modified** — `question`, set and cleared from the stream. |

---

### Task 1: The arming rule, enforced

**Files:**
- Modify: `packages/implr_studio/executors/fake.py`
- Test: `packages/implr_studio/tests/test_fake_executor.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
async def test_a_question_blocks_playback_until_answered():
    """The consumer keeps iterating. Passes even with the WRONG arming order."""
    ex = FakeExecutor({"arch-gen": [
        base.StepEvent.log("thinking"),
        base.StepEvent.question("q1", "Postgres or MySQL?"),
        base.StepEvent.log("noted"),
        base.StepEvent.done("success", "done")]})
    handle = await ex.start(_req("arch-gen"))
    collected = []

    task = asyncio.create_task(_consume(ex, handle, collected))
    await asyncio.sleep(0.05)

    assert [e.kind for e in collected] == ["log", "question"]
    assert not task.done(), "playback must block on an unanswered question"

    await ex.answer(handle, "q1", "Postgres")
    await asyncio.wait_for(task, timeout=2)

    assert [e.kind for e in collected] == ["log", "question", "log", "done"]


async def test_a_question_can_be_answered_after_the_iterator_is_abandoned():
    """THE contract test. Exactly what the orchestrator does.

    It consumes up to the question, then stops iterating entirely - the driver
    returns and the async generator is left suspended at the yield. The answer
    arrives later, from an HTTP request, and only then does a new driver pass
    resume the same iterator.

    An executor that arms the question AFTER the yield passes the test above and
    fails this one, because that test keeps consuming.
    """
    ex = FakeExecutor({"arch-gen": [
        base.StepEvent.log("thinking"),
        base.StepEvent.question("q1", "Postgres or MySQL?"),
        base.StepEvent.log("noted"),
        base.StepEvent.done("success", "done")]})
    handle = await ex.start(_req("arch-gen"))
    stream = ex.events(handle)
    seen = []

    # Pass one: consume up to and including the question, then walk away.
    async for event in stream:
        seen.append(event)
        if event.kind == "question":
            break
    assert [e.kind for e in seen] == ["log", "question"]

    # The answer must be accepted with NOTHING iterating the stream.
    await ex.answer(handle, "q1", "Postgres")
    assert ex.answers == [("q1", "Postgres")]

    # Pass two: resume the SAME iterator; it must run to completion.
    async for event in stream:
        seen.append(event)

    assert [e.kind for e in seen] == ["log", "question", "log", "done"]


async def test_answering_an_unknown_question_raises():
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.done("success", "ok")]})

    with pytest.raises(base.ExecutorError, match="no pending question"):
        await ex.answer(await ex.start(_req()), "nope", "text")


async def test_two_questions_are_answered_in_sequence():
    ...


async def test_cancel_releases_a_blocked_question():
    ...
```

- [ ] **Step 2: Fix the ordering**

```python
    async def events(self, handle: StepHandle) -> AsyncIterator[StepEvent]:
        session = self._session(handle)
        for event in session.events:
            if session.cancelled.is_set():
                break

            # Arm BEFORE yielding. The consumer abandons this iterator as soon as
            # it sees a question and only resumes after answer() lands, so arming
            # afterwards makes the question unanswerable - and clearing `answered`
            # afterwards would discard a reply that had already arrived.
            if event.kind == "question":
                session.pending_question = event.question_id
                session.answered.clear()

            yield event

            if event.is_terminal:
                session.finished = True
                return
            if event.kind == "question":
                await self._wait_for_answer_or_cancel(session)
                if session.cancelled.is_set():
                    break
        session.finished = True
        yield StepEvent.done(OUTCOME_FAILURE, _CANCELLED, error=_CANCELLED)
```

- [ ] **Step 3: Run, commit**

---

### Task 2: The `questions` table

**Files:**
- Modify: `packages/implr_studio/store.py`
- Test: `packages/implr_studio/tests/test_store_questions.py`

**Interfaces:**
- `create_question(question_id, run_id, node_id, prompt_md, options)`
- `get_question(question_id)`, `pending_question(run_id, node_id)`, `answer_question(question_id, text)`

- [ ] **Step 1: Write the failing test**

```python
def test_the_question_lifecycle(store):
    _make_run(store)
    store.create_question("q1", "r1", "a", "Postgres or MySQL?", None)

    pending = store.pending_question("r1", "a")
    assert pending["id"] == "q1"
    assert pending["answer"] is None

    store.answer_question("q1", "Postgres")

    assert store.pending_question("r1", "a") is None
    assert store.get_question("q1")["answer"] == "Postgres"
    assert store.get_question("q1")["answered_at"] is not None


def test_options_round_trip(store):
    _make_run(store)
    store.create_question("q1", "r1", "a", "Pick", ["Postgres", "MySQL"])

    assert store.get_question("q1")["options"] == ["Postgres", "MySQL"]


def test_no_options_is_null_not_an_empty_list(store):
    """The UI distinguishes 'free text only' from 'zero options offered'."""
    _make_run(store)
    store.create_question("q1", "r1", "a", "Anything?", None)

    assert store.get_question("q1")["options"] is None


def test_pending_returns_the_newest_unanswered(store):
    ...


def test_pending_is_scoped_to_the_node(store):
    """Two nodes, two questions. Neither must see the other's."""
    ...


def test_a_question_survives_reopening_the_database(tmp_path):
    """A restart mid-question must not lose the prompt."""
    ...


def test_answering_twice_keeps_the_first_answer(store):
    """The route returns 409; the store must not silently overwrite either."""
    ...
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 3: The orchestrator pause and resume

**Files:**
- Modify: `packages/implr_studio/orchestrator.py`
- Test: `packages/implr_studio/tests/test_questions.py`

**Interfaces:**
- `_run_node` caches `self._streams[(run_id, node_id)]`, creating it on first entry and resuming it on later passes.
- On a `question` event: persist, set `AWAITING_INPUT`, **return** — the driver stops.
- `await answer(run_id, question_id, text)` — record, deliver to the executor, set the node back to `RUNNING`, respawn the driver.

- [ ] **Step 1: Write the failing test**

```python
async def test_a_question_pauses_the_node_and_is_persisted(orch, store):
    orch.executor.set_script("arch-gen", [
        base.StepEvent.question("q1", "Postgres or MySQL?"),
        base.StepEvent.done("success", "ok")])

    run_id = await orch.start_run(_two_nodes())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_INPUT
    assert orch.run_status(run_id) == rs.RUN_PAUSED
    assert store.pending_question(run_id, "a")["prompt_md"] == "Postgres or MySQL?"


async def test_downstream_is_held_while_a_question_is_open(orch):
    """awaiting-input does not satisfy a dependency."""
    ...


async def test_answering_resumes_the_node_and_the_run(orch):
    orch.executor.set_script("arch-gen", [
        base.StepEvent.question("q1", "Which?"),
        base.StepEvent.log("thanks"),
        base.StepEvent.done("success", "ok")])
    run_id = await orch.start_run(_two_nodes())
    await orch.wait_quiescent(run_id)
    qid = orch.store.pending_question(run_id, "a")["id"]

    await orch.answer(run_id, qid, "Postgres")
    await orch.wait_quiescent(run_id)

    assert orch.executor.answers == [("q1", "Postgres")]
    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED
    assert orch.store.get_question(qid)["answer"] == "Postgres"


async def test_answering_RESUMES_the_step_rather_than_restarting_it(orch):
    """THE assertion of this phase.

    Two entries would mean the step was invoked twice: with a real adapter the
    agent loses the context that produced the question, redoes its reasoning, and
    the run costs double. The browser looks identical either way.
    """
    orch.executor.set_script("arch-gen", [
        base.StepEvent.question("q1", "Which?"),
        base.StepEvent.done("success", "ok")])
    run_id = await orch.start_run(_one_node(step="arch-gen"))
    await orch.wait_quiescent(run_id)
    qid = orch.store.pending_question(run_id, "a")["id"]

    await orch.answer(run_id, qid, "Postgres")
    await orch.wait_quiescent(run_id)

    assert len(orch.executor.started) == 1


async def test_two_questions_in_one_step_both_resume(orch):
    """The stream is resumed twice. A cache that is popped after the first answer
    passes the single-question test and fails here."""
    orch.executor.set_script("arch-gen", [
        base.StepEvent.question("q1", "first?"),
        base.StepEvent.question("q2", "second?"),
        base.StepEvent.done("success", "ok")])
    run_id = await orch.start_run(_one_node(step="arch-gen"))

    for _ in range(2):
        await orch.wait_quiescent(run_id)
        q = orch.store.pending_question(run_id, "a")
        await orch.answer(run_id, q["id"], "yes")
    await orch.wait_quiescent(run_id)

    assert len(orch.executor.started) == 1
    assert [a[0] for a in orch.executor.answers] == ["q1", "q2"]


async def test_the_options_the_agent_offered_are_persisted(orch, store):
    orch.executor.set_script("arch-gen", [
        base.StepEvent.question("q1", "Pick", options=["Postgres", "MySQL"]),
        base.StepEvent.done("success", "ok")])

    run_id = await orch.start_run(_one_node(step="arch-gen"))
    await orch.wait_quiescent(run_id)

    assert store.pending_question(run_id, "a")["options"] == ["Postgres", "MySQL"]


async def test_answering_an_unknown_question_raises(orch):
    ...


async def test_answering_a_question_from_another_run_raises(orch):
    """The question id is not an authorization either."""
    ...


async def test_a_free_text_answer_is_delivered_verbatim(orch):
    """The operator may say something the agent did not offer."""
    ...


async def test_the_question_event_is_in_the_stream_for_the_ui(orch, store):
    """The client learns about the question from the event stream, so a browser
    that connects after it was asked still renders the card."""
    ...
```

- [ ] **Step 2: Implement**

```python
    async def _run_node(self, run_id: str, node_id: str) -> None:
        """Run or resume one node.

        A question abandons the event iterator mid-stream, so the live iterator is
        cached here and RESUMED on a later driver pass. Restarting would re-invoke
        the step from the top and lose the agent's context.
        """
        key = (run_id, node_id)
        stream = self._streams.get(key)

        if stream is None:
            run = self.store.get_run(run_id)
            node = next(n for n in run["pipeline"].nodes if n.id == node_id)
            step = self.registry.get(node.step)
            handle = await self.executor.start(StepRequest(
                node_id=node_id, skill=step.skill,
                args=self.build_argv(node, step),
                workspace=self.workspace, models=dict(node.models)))
            self._handles[key] = handle
            stream = self.executor.events(handle)
            self._streams[key] = stream

        self.store.set_node_status(run_id, node_id, rs.RUNNING)
        self.store.append_event(run_id, node_id, "status", {"status": rs.RUNNING})

        async for event in stream:
            self.store.append_event(run_id, node_id, event.kind, dict(event.payload))

            if event.kind == "question":
                self.store.create_question(
                    event.question_id, run_id, node_id, event.prompt_md, event.options)
                self.store.set_node_status(run_id, node_id, rs.AWAITING_INPUT)
                self.store.append_event(run_id, node_id, "status",
                                        {"status": rs.AWAITING_INPUT})
                return          # the driver stops; answer() restarts it. The stream
                                # stays in self._streams, suspended at the yield.

            if event.is_terminal:
                status = rs.SUCCEEDED if event.outcome == OUTCOME_SUCCESS else rs.FAILED
                self.store.set_node_status(run_id, node_id, status,
                                           summary=event.summary, error=event.error)
                self.store.append_event(run_id, node_id, "status", {"status": status})
                self._handles.pop(key, None)
                self._streams.pop(key, None)      # only on a TERMINAL event
                return
```

The `_streams.pop` belongs **only** in the terminal branch. Popping it on the question branch
is the bug the two-question test catches.

`_next_ready` must skip a node in `AWAITING_INPUT`, or the driver will re-enter a stream that
is waiting on a human.

Remove Phase 9's `question`-event refusal.

- [ ] **Step 3: Run, commit**

---

### Task 4: The answer route and the question card

**Files:**
- Modify: `packages/implr_studio/api.py`, `web/src/api.ts`, `web/src/store.ts`, `web/src/panels/RunPanel.tsx`
- Create: `web/src/panels/QuestionCard.tsx`
- Test: `packages/implr_studio/tests/test_api_answer.py`, `web/src/panels/QuestionCard.test.tsx`

**Interfaces:**
- `POST /api/projects/{pid}/runs/{rid}/answer` — body `{question_id, text}`. `RUN_CONTROL`. `202`.
- `QuestionCard({ question, onAnswer })` — prompt, option buttons, free-text box.
- `store.question`, set from a `question` event and cleared on the node's `done`.

- [ ] **Step 1: Write the failing test**

```python
def test_answering_resumes_the_run(client, ctx):
    ...
    assert wait_for_run(client, PID, run_id)["status"] == rs.RUN_SUCCEEDED


def test_answering_an_already_answered_question_is_409(client):
    """Not a second delivery to the executor."""
    ...


def test_an_empty_answer_is_422(client):
    """A blank reply gives the agent nothing and is almost always a mis-click."""
    ...


def test_a_question_id_from_another_run_is_404(client):
    ...


def test_answer_requires_run_control(app):
    assert permission_for(app, "answer") is Permission.RUN_CONTROL
```

```tsx
it('renders the prompt as markdown');
it('renders the agent own options as buttons');
it('sends the option text when a button is clicked');
it('renders only a text box when options is null');
it('sends a typed answer');
it('disables Send until something is typed');
it('disables everything once an answer is submitted');   // double-send guard
it('clears when the node moves on');
```

`it('disables everything once an answer is submitted')` matters because the round trip is slow
enough for a second click to land, and a double answer is a `409` the operator did not cause.

- [ ] **Step 2: Implement, run, build, commit**

---

### Task 5: Run the demo

- [ ] **Step 1** — script the question. Run. The node goes violet, the card appears with two
      option buttons and a text box.
- [ ] **Step 2** — click an option. The step continues and completes.
- [ ] **Step 3** — re-run and answer with **free text** instead. Also accepted; the operator may
      say something the agent did not offer.
- [ ] **Step 4** — re-run, and while the question is open **refresh the browser**. The card is
      still there: the question came from the persisted event stream, not from session state.
- [ ] **Step 5** — the assertion the UI cannot show:
      `pytest -k resumes` → `len(ex.started) == 1`.
- [ ] **Step 6** — a two-question script. Both are answered, and `ex.started` is **still** 1.
- [ ] **Step 7** — restart the backend while a question is open. The prompt is still in the
      database; the node is still `awaiting-input`; answering now **fails**, because the
      executor session is gone. That is correct for Phase 12 and is exactly what Phase 14's
      recovery turns into an honest `failed`.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` / `npm run build` pass, with no model invoked.
- [ ] `FakeExecutor` arms its pending question **before** the yield, and
      `test_a_question_can_be_answered_after_the_iterator_is_abandoned` passes.
- [ ] **`len(ex.started) == 1`** across a one-question round trip *and* a two-question one.
- [ ] `_streams.pop` happens only on a terminal event.
- [ ] `_next_ready` skips a node in `awaiting-input`.
- [ ] A question, its options and its answer are all persisted; a restart does not lose the
      prompt.
- [ ] `options: None` and `options: []` are distinguishable.
- [ ] Answering twice is `409`; an empty answer is `422`; a question id from another run is `404`.
- [ ] The card renders options as buttons and still accepts free text.
- [ ] The card survives a browser refresh, because it is rebuilt from the event stream.
- [ ] Phase 9's `question`-event refusal is removed.

---

## What the next phase gets

The pause / act / resume plumbing that **Phase 13** reuses for review-and-send-back — with one
deliberate inversion: request-changes **discards** the stream where answering resumes it,
because starting over with new information is the point.
