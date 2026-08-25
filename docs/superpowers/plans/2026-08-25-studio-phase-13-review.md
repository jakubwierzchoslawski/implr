# implr Studio — Phase 13: Review & send back

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject a step's output with a note and watch it re-run knowing why. Plus the three fixes that make *"every step can be human-in-the-loop"* true rather than nearly true.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-design.md` (*Component: Human-in-the-loop*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 12 (questions) — this reuses the pause / operator-action / resume plumbing.

---

## Demo

Set `approval: after` on Architecture Brief. Run.

The node reaches **`awaiting-review`**, not `succeeded`. The run stays paused; downstream
nodes stay `pending`. The review card shows what it wrote. Type *"the persistence decision is
unjustified — the synthesis says nothing about transaction volume"* and click **Request
changes**.

The node re-runs. `ex.started` shows **two** attempts, and the second `StepRequest` carries
the note. Accept the second attempt; the run proceeds.

Then the two fixes that are easiest to forget:

```bash
# A ROOT node with approval: before must wait. Before this phase it ran immediately.
# A TERMINAL node with approval: after must hold the run open.
python -m pytest packages/implr_studio/tests/test_hitl.py -k "root or terminal" -v
```

And the one that bites in production: **retry an already-approved node and confirm it asks
again.**

---

## Why this phase exists

Four gaps, found by checking rather than assuming:

| Gap | Evidence | Consequence |
|---|---|---|
| A root node cannot be gated | `node_readiness` opens with `if not inbound: return READY` | The first step of every pipeline always runs unsupervised |
| A terminal node's output cannot be reviewed | approval releases a *downstream* edge; a terminal node has none | Code Review — the step you most want to read — is the one you cannot |
| No review-and-send-back | Approve means proceed; Retry re-runs blind | The only correction available is to re-roll the dice |
| `manual_approved` is per node and never cleared | `set_manual_approved` sets a flag; `retry` does not clear it | A re-run of an approved step is unsupervised, and you find out when you were paying least attention |

**The root cause of the first two is that HITL was modelled on edges.** A reasonable first cut
— a gate *is* naturally about a connection — but *"should a human look at this step?"* is a
property of the **step**. It also reads backwards in the UI: to supervise one step you had to
find and edit its inbound edge.

---

## Scope boundary — not in this phase

- **Edge gates stay.** `manual` and `artifact+manual` keep working. They remain the right tool
  when approval is genuinely conditional on which path through a branch was taken. The
  configurator steers to node approval because that is the common case, not because gates were
  wrong.
- **No partial rejection.** Request-changes re-runs the **whole** step. See *Known limitation*.
- **No approval delegation, no multi-party sign-off, no time-boxed auto-approve.** One
  operator, one decision.
- **No notifications.** Phase 18's inbox makes them implementable.

---

## Global constraints

- `feedback` crosses the `StepExecutor` boundary as **prose**, not a formatted prompt. Same
  discipline as `skill` and `args`: the adapter decides what it means.
- **Both approval stamps clear on retry and on request-changes.** A supervised step re-runs
  supervised.
- A node in `awaiting-review` **blocks the run from reporting success**. Otherwise a terminal
  node's review is advisory, which is the gap this phase exists to close.
- `awaiting-review` gets its own reserved status token, `--st-review`. Borrowing
  `awaiting-input`'s violet would make two different "needs you" states look identical.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/pipeline.py` | **Modified** — `Node.approval`, its validation. |
| `packages/implr_studio/runstate.py` | **Modified** — `AWAITING_REVIEW`, terminal sets. |
| `packages/implr_studio/orchestrator.py` | **Modified** — readiness for root nodes, the review pause, `accept`, `request_changes`. |
| `packages/implr_studio/store.py` | **Modified** — approval columns, feedback, attempt. |
| `packages/implr_studio/executors/base.py` | **Modified** — `StepRequest.feedback`. |
| `packages/implr_studio/executors/claude_code.py` | **Modified** — render feedback into the prompt. |
| `packages/implr_studio/api.py` | **Modified** — accept / request-changes routes. |
| `web/src/panels/ReviewCard.tsx` | The review affordance. |
| `web/src/modal/StepConfig.tsx` | **Modified** — the `approval` control. |

---

### Task 1: `approval` on the node

**Files:**
- Modify: `packages/implr_studio/pipeline.py`
- Test: `packages/implr_studio/tests/test_approval_config.py`

**Interfaces:**
- `Node.approval: str = "none"` — `none | before | after | both`.
- `pipeline.APPROVALS = ("none", "before", "after", "both")`.
- `validate_pipeline` gains `illegal-approval`.
- Helpers: `Node.wants_approval_before`, `Node.wants_approval_after`.

The two boolean helpers exist so no call site parses the string. `both` is a real value rather
than two flags because it round-trips through YAML as one field, and a pipeline is read by
humans.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import pipeline


def _n(**kw):
    return pipeline.pipeline_from_dict(
        {"version": 1, "nodes": [dict({"id": "a", "step": "doc-ingest"}, **kw)], "edges": []}
    ).nodes[0]


def test_approval_defaults_to_none():
    """Every pipeline written before this phase keeps behaving identically."""
    assert _n().approval == "none"
    assert _n().wants_approval_before is False
    assert _n().wants_approval_after is False


@pytest.mark.parametrize("value,before,after", [
    ("none", False, False),
    ("before", True, False),
    ("after", False, True),
    ("both", True, True),
])
def test_the_four_values(value, before, after):
    node = _n(approval=value)

    assert node.wants_approval_before is before
    assert node.wants_approval_after is after


def test_an_illegal_approval_is_rejected(reg):
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest", "approval": "sometimes"}],
        "edges": []})

    findings = pipeline.validate_pipeline(p, reg)

    assert [f.code for f in findings] == ["illegal-approval"]
    assert "before" in findings[0].message      # names the legal values


def test_approval_none_is_omitted_from_the_yaml():
    """Sparse, like arg_values and models: a pipeline with no approvals must
    round-trip byte-identically to the pre-Phase-13 format."""
    p = pipeline.pipeline_from_dict(
        {"version": 1, "nodes": [{"id": "a", "step": "doc-ingest"}], "edges": []})

    assert "approval" not in pipeline.pipeline_to_dict(p)["nodes"][0]


def test_a_set_approval_survives_the_round_trip():
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "a", "step": "doc-ingest", "approval": "after"}],
        "edges": []})

    assert pipeline.pipeline_to_dict(p)["nodes"][0]["approval"] == "after"
    assert pipeline.pipeline_from_dict(pipeline.pipeline_to_dict(p)) == p
```

- [ ] **Step 2: Implement, run, commit**

Add `approval: str = "none"` to `Node`, the two properties, `APPROVALS`, the `illegal-approval`
finding in `_validate_args`'s sibling, and the sparse emit in `_node_to_dict`.

```bash
git commit -m "feat(hitl): node-level approval policy"
```

---

### Task 2: `awaiting-review`, and a root node that waits

**Files:**
- Modify: `packages/implr_studio/runstate.py`, `orchestrator.py`
- Test: `packages/implr_studio/tests/test_hitl.py`

**Interfaces:**
- `runstate.AWAITING_REVIEW = "awaiting-review"`, in `NODE_STATUSES`, **not** in `NODE_TERMINAL`, **not** in `NODE_SATISFIES_DEPENDENCY`.
- `node_readiness` returns `AWAITING_APPROVAL` for a node with `approval in (before, both)` that has not been approved — **regardless of inbound edges**.
- `_run_node` parks a node in `AWAITING_REVIEW` on success when `approval in (after, both)`.
- `_finalise_run_status` treats `awaiting-review` as paused, never succeeded.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import orchestrator, pipeline
from implr_studio import runstate as rs
from implr_studio.executors import base
from implr_studio.executors.fake import FakeExecutor

pytestmark = pytest.mark.asyncio


def _pipe(**node_kw):
    return pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [dict({"id": "a", "step": "doc-ingest"}, **node_kw),
                  {"id": "b", "step": "arch-gen"}],
        "edges": [{"from": "a", "to": "b"}]})


# --- the root-node fix -----------------------------------------------------

async def test_a_root_node_with_approval_before_waits(orch, store):
    """THE fix. Before this phase, node_readiness returned READY for any node with
    no inbound edge, so the first step of every pipeline ran unsupervised."""
    run_id = await orch.start_run(_pipe(approval="before"))
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_APPROVAL
    assert orch.run_status(run_id) == rs.RUN_PAUSED
    assert orch.executor.started == []           # it never started


async def test_approving_the_root_node_releases_it(orch):
    run_id = await orch.start_run(_pipe(approval="before"))
    await orch.wait_quiescent(run_id)

    await orch.approve(run_id, "a")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED


async def test_approval_none_on_a_root_node_still_runs_immediately(orch):
    """No regression for every pipeline that predates this field."""
    run_id = await orch.start_run(_pipe())
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED, "b": rs.SUCCEEDED}


# --- the terminal-node fix -------------------------------------------------

async def test_a_node_with_approval_after_parks_in_awaiting_review(orch):
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_REVIEW
    assert orch.node_statuses(run_id)["b"] == rs.PENDING      # downstream held
    assert orch.run_status(run_id) == rs.RUN_PAUSED


async def test_awaiting_review_does_not_satisfy_a_dependency(orch):
    """A reviewed-but-unaccepted node must not release its edges."""
    assert rs.satisfies_dependency(rs.AWAITING_REVIEW) is False


async def test_a_terminal_node_in_review_blocks_run_success(orch):
    """Otherwise the review is advisory - the gap this phase exists to close."""
    p = pipeline.pipeline_from_dict({
        "version": 1,
        "nodes": [{"id": "only", "step": "doc-ingest", "approval": "after"}],
        "edges": []})

    run_id = await orch.start_run(p)
    await orch.wait_quiescent(run_id)

    assert orch.run_status(run_id) == rs.RUN_PAUSED
    assert orch.run_status(run_id) != rs.RUN_SUCCEEDED


async def test_accept_advances_the_run(orch):
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    await orch.accept(run_id, "a")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id) == {"a": rs.SUCCEEDED, "b": rs.SUCCEEDED}
    assert orch.run_status(run_id) == rs.RUN_SUCCEEDED


async def test_both_waits_twice(orch):
    run_id = await orch.start_run(_pipe(approval="both"))
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_APPROVAL

    await orch.approve(run_id, "a")
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_REVIEW

    await orch.accept(run_id, "a")
    await orch.wait_quiescent(run_id)
    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED


async def test_a_failed_node_does_not_enter_review(orch):
    """Review is for output you can read. A failure goes to failed, with retry/skip."""
    orch.executor.set_script("doc-ingest", [base.StepEvent.done(base.OUTCOME_FAILURE, "broke")])

    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.FAILED
```

- [ ] **Step 2: Implement**

Two edits to `node_readiness`, and the first is the whole fix:

```python
def node_readiness(node_id, p, nodes, workspace, contracts) -> str:
    node = next((n for n in p.nodes if n.id == node_id), None)
    row = nodes.get(node_id, {})

    # BEFORE any edge reasoning: an unapproved `approval: before` node waits even
    # with no inbound edge. This is the line that makes a root node supervisable.
    if node is not None and node.wants_approval_before and not row.get("approved_before_at"):
        return rs.AWAITING_APPROVAL

    inbound = [e for e in p.edges if e.target == node_id]
    if not inbound:
        return READY
    ...
```

and in `_run_node`, on a terminal success:

```python
            if event.is_terminal:
                if event.outcome == OUTCOME_SUCCESS and node.wants_approval_after:
                    # Not succeeded: succeeded would release the edges and let the
                    # run report success, which makes the review advisory.
                    self.store.set_node_status(run_id, node_id, rs.AWAITING_REVIEW,
                                               summary=event.summary)
                    self.store.append_event(run_id, node_id, "status",
                                            {"status": rs.AWAITING_REVIEW})
                else:
                    status = rs.SUCCEEDED if event.outcome == OUTCOME_SUCCESS else rs.FAILED
                    ...
```

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(hitl): awaiting-review, and a root node that can be gated"
```

---

### Task 3: `feedback` on the request, and request-changes

**Files:**
- Modify: `packages/implr_studio/executors/base.py`, `orchestrator.py`, `store.py`
- Test: `packages/implr_studio/tests/test_feedback.py`

**Interfaces:**
- `StepRequest.feedback: tuple[str, ...] = ()` — accumulated rejection notes, oldest first.
- `await Orchestrator.accept(run_id, node_id, note=None)`
- `await Orchestrator.request_changes(run_id, node_id, text)` — appends, clears approvals, re-runs.
- `store` columns: `approved_before_at/by`, `approved_after_at/by`, `review_feedback` (jsonb), `attempt`.

**A tuple, not a string.** The second rejection must not erase the first: an agent that has
already been corrected once benefits from knowing both objections, and an operator reading
the history needs to see this was the third attempt.

- [ ] **Step 1: Write the failing test**

```python
async def test_request_changes_reruns_the_step(orch):
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    await orch.request_changes(run_id, "a", "the persistence decision is unjustified")
    await orch.wait_quiescent(run_id)

    assert len(orch.executor.started) == 2


async def test_the_second_attempt_carries_the_note(orch):
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    await orch.request_changes(run_id, "a", "no justification for Postgres")
    await orch.wait_quiescent(run_id)

    assert orch.executor.started[0].feedback == ()
    assert orch.executor.started[1].feedback == ("no justification for Postgres",)


async def test_a_second_rejection_accumulates_rather_than_replaces(orch):
    """An agent corrected twice needs both objections, not only the latest."""
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)
    await orch.request_changes(run_id, "a", "first objection")
    await orch.wait_quiescent(run_id)

    await orch.request_changes(run_id, "a", "second objection")
    await orch.wait_quiescent(run_id)

    assert orch.executor.started[2].feedback == ("first objection", "second objection")


async def test_attempt_is_incremented(orch, store):
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)
    assert store.get_node(run_id, "a")["attempt"] == 1

    await orch.request_changes(run_id, "a", "again")
    await orch.wait_quiescent(run_id)

    assert store.get_node(run_id, "a")["attempt"] == 2


async def test_request_changes_requires_a_non_empty_note(orch):
    """A rejection with no reason is a retry wearing a costume."""
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    with pytest.raises(orchestrator.OperatorActionError, match="reason"):
        await orch.request_changes(run_id, "a", "   ")


async def test_request_changes_rejects_a_node_not_in_review(orch):
    run_id = await orch.start_run(_pipe())
    await orch.wait_quiescent(run_id)

    with pytest.raises(orchestrator.OperatorActionError, match="succeeded"):
        await orch.request_changes(run_id, "a", "too late")


async def test_accept_with_a_note_records_it(orch, store):
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    await orch.accept(run_id, "a", note="good enough, but thin on NFRs")

    assert "thin on NFRs" in str(store.get_node(run_id, "a")["review_feedback"])
    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED


# --- the bookkeeping fix ---------------------------------------------------

async def test_retry_clears_the_approval(orch, store):
    """The production bug: a re-run of an approved step must be approved again.
    You notice the old behaviour when you were paying least attention."""
    run_id = await orch.start_run(_pipe(approval="both"))
    await orch.wait_quiescent(run_id)
    await orch.approve(run_id, "a")
    await orch.wait_quiescent(run_id)
    await orch.accept(run_id, "a")
    await orch.wait_quiescent(run_id)
    store.set_node_status(run_id, "a", rs.FAILED, error="something later broke")

    await orch.retry(run_id, "a")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_APPROVAL
    assert store.get_node(run_id, "a")["approved_before_at"] is None
    assert store.get_node(run_id, "a")["approved_after_at"] is None


async def test_request_changes_clears_the_after_approval(orch, store):
    run_id = await orch.start_run(_pipe(approval="after"))
    await orch.wait_quiescent(run_id)

    await orch.request_changes(run_id, "a", "again please")
    await orch.wait_quiescent(run_id)

    assert orch.node_statuses(run_id)["a"] == rs.AWAITING_REVIEW
    assert store.get_node(run_id, "a")["attempt"] == 2


async def test_feedback_survives_a_service_restart(tmp_path):
    """The note is durable: a rejection is a decision, not session state."""
    ...
```

- [ ] **Step 2: Implement**

`request_changes` is the interesting one, and its ordering matters:

```python
    async def request_changes(self, run_id: str, node_id: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            # A rejection with no reason is a retry wearing a costume, and it gives
            # the next attempt nothing to work with.
            raise OperatorActionError("request_changes needs a reason")

        node = self.store.get_node(run_id, node_id)
        if node is None:
            raise KeyError("unknown node: %s" % node_id)
        if node["status"] != rs.AWAITING_REVIEW:
            raise OperatorActionError(
                "node %s is %s, not awaiting review" % (node_id, node["status"]))

        # Persist the note BEFORE clearing the stream, so a crash between the two
        # loses the re-run rather than the reason for it.
        self.store.append_review_feedback(run_id, node_id, text)
        self.store.clear_approvals(run_id, node_id)
        self.store.increment_attempt(run_id, node_id)

        key = (run_id, node_id)
        self._handles.pop(key, None)
        self._streams.pop(key, None)          # a fresh step, not a resumed one

        self.store.set_node_status(run_id, node_id, rs.PENDING)
        self.store.set_run_status(run_id, rs.RUN_RUNNING)
        self._spawn_driver(run_id)
```

And `_run_node` reads the accumulated notes into the request:

```python
            request = StepRequest(
                node_id=node_id,
                skill=step.skill,
                args=self.build_argv(node, step),
                workspace=self.workspace,
                models=dict(node.models),
                feedback=tuple(self.store.get_review_feedback(run_id, node_id)),
            )
```

Note the contrast with Phase 12's question handling: answering a question **resumes** the
existing stream, because the agent's session still holds its context. Request-changes
**discards** it, because the point is to start the step over with new information.

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(hitl): request-changes with accumulated feedback"
```

---

### Task 4: The adapter renders feedback

**Files:**
- Modify: `packages/implr_studio/executors/_sdk.py`, `claude_code.py`
- Test: `packages/implr_studio/tests/test_sdk_seam.py` (extend)

**Interfaces:**
- `_sdk.build_prompt(skill, args, feedback=()) -> str`
- `_sdk.FEEDBACK_PREAMBLE: str`

- [ ] **Step 1: Write the failing test**

```python
def test_no_feedback_leaves_the_prompt_unchanged():
    """A first attempt must look exactly like it did before this phase."""
    assert _sdk.build_prompt("arch-gen", ()) == _sdk.build_prompt("arch-gen", (), feedback=())


def test_feedback_appears_after_the_command():
    prompt = _sdk.build_prompt("arch-gen", (), feedback=("justify the database choice",))

    assert prompt.splitlines()[0] == "/arch-gen"
    assert "justify the database choice" in prompt
    assert _sdk.FEEDBACK_PREAMBLE in prompt


def test_multiple_notes_are_numbered_in_order():
    prompt = _sdk.build_prompt("arch-gen", (), feedback=("first", "second"))

    assert prompt.index("first") < prompt.index("second")
    assert "1." in prompt and "2." in prompt


def test_the_preamble_says_this_is_a_rerun():
    """Without it the agent has no way to know it already tried and was rejected."""
    assert "previous attempt" in _sdk.FEEDBACK_PREAMBLE.lower()


def test_feedback_is_not_interpolated_into_the_slash_command():
    """A note is prose from an operator. It must never reach the command line."""
    prompt = _sdk.build_prompt("arch-gen", (), feedback=("--dangerous --flag",))

    assert prompt.splitlines()[0] == "/arch-gen"
```

That last test is the one worth having. Operator prose is untrusted input as far as the
command line is concerned, and the only safe place for it is the prompt body.

- [ ] **Step 2: Implement**

```python
FEEDBACK_PREAMBLE = (
    "A previous attempt at this step was reviewed and sent back. Address every point "
    "below. Do not repeat the work that was accepted; correct what was objected to."
)


def build_prompt(skill: str, args: tuple[str, ...], feedback: tuple[str, ...] = ()) -> str:
    command = "/%s" % skill
    if args:
        command = "%s %s" % (command, " ".join(args))

    parts = [command, QUESTION_INSTRUCTION]
    if feedback:
        # Operator prose, in the body, never on the command line.
        notes = "\n".join("%d. %s" % (i, t) for i, t in enumerate(feedback, 1))
        parts.append("%s\n\n%s" % (FEEDBACK_PREAMBLE, notes))
    return "\n\n".join(parts)
```

- [ ] **Step 3: Run, commit**

---

### Task 5: The routes

**Files:**
- Modify: `packages/implr_studio/api.py`
- Test: `packages/implr_studio/tests/test_api_review.py`

**Interfaces:**
- `POST /api/projects/{pid}/runs/{rid}/nodes/{node}/accept` — body `{note?: str}`
- `POST /api/projects/{pid}/runs/{rid}/nodes/{node}/request-changes` — body `{text: str}`
- Both authorized with `Permission.RUN_CONTROL`.

- [ ] **Step 1: Write the failing test**

```python
def test_accept_advances_the_run(client):
    ...
    assert wait_for_run(client, run_id)["status"] == rs.RUN_SUCCEEDED


def test_request_changes_reruns_and_returns_202(client):
    r = client.post(url("/runs/%s/nodes/a/request-changes" % run_id), json={"text": "no"})

    assert r.status_code == 202


def test_request_changes_with_no_text_is_422(client):
    r = client.post(url("/runs/%s/nodes/a/request-changes" % run_id), json={"text": ""})

    assert r.status_code == 422


def test_accepting_a_node_not_in_review_is_409(client):
    ...


def test_both_routes_require_run_control(app):
    """The permission split matters: someone who may trigger a run is not
    automatically someone who may sign off its output."""
    for path in ("accept", "request-changes"):
        assert permission_for(app, path) is Permission.RUN_CONTROL
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 6: The review card and the approval control

**Files:**
- Create: `web/src/panels/ReviewCard.tsx`
- Modify: `web/src/panels/RunPanel.tsx`, `web/src/modal/StepConfig.tsx`, `web/src/api.ts`, `web/src/app.css`, `web/src/tokens.css`
- Test: `web/src/panels/ReviewCard.test.tsx`

**Interfaces:**
- `ReviewCard({ node, onAccept, onRequestChanges })` — summary, written paths, log, three actions.
- `StepConfig`'s Run tab gains an `approval` segmented control.
- `tokens.css` gains `--st-review` (both palettes) and `app.css` a `.step-node--awaiting-review` stripe.

- [ ] **Step 1: Write the failing test**

```tsx
it('shows what the step wrote');
it('disables Request changes until a reason is typed');
it('sends the typed reason');
it('shows the attempt number when this is not the first');
it('shows previous rejection notes so you do not repeat one');
it('Accept with a note keeps the note but still accepts');
it('renders a review state distinctly from awaiting-input');
```

The fifth is the one that makes the feature usable rather than merely present: on attempt
three, the reviewer needs to see what attempts one and two were rejected for.

- [ ] **Step 2: Implement**

Add to both palettes in `tokens.css`:

```css
  --st-review:#f472b6;    /* :root            */
  --st-review:#b83280;    /* [data-theme=light] */
```

`awaiting-review` is a distinct "needs you" state from `awaiting-input`; sharing violet would
make them indistinguishable in the inbox, which is the one place both appear together.

- [ ] **Step 3: Run, build, commit**

---

### Task 7: Run the demo

- [ ] **Step 1: The main flow**

Local stack, `--fake`. Set Architecture Brief to `approval: after`, Save, Run.

- The node goes **`awaiting-review`**, pink stripe. Downstream `pending`. Run **paused**.
- The card shows the summary and the paths it wrote.
- **Request changes** is disabled until you type a reason.
- Type one, send. The node re-runs; the card shows *attempt 2* and your previous note.
- **Accept**. The run proceeds.

- [ ] **Step 2: The root-node fix**

Set the **first** node to `approval: before`. Run. It waits — before this phase it ran
immediately. Approve; it runs.

- [ ] **Step 3: The terminal-node fix**

Set the **last** node to `approval: after`. Run to the end. The run stays **paused**, not
succeeded, until you accept.

- [ ] **Step 4: The bookkeeping fix**

Approve and accept a `both` node. Force it to `failed`. **Retry.** It asks for approval
**again**.

- [ ] **Step 5: No regression**

Open a pipeline with no `approval` anywhere. Run. Identical to Phase 12 behaviour, and
`pipeline.yaml` gains no `approval` key.

---

## Definition of Done

- [ ] `python -m pytest` passes; every test uses `FakeExecutor`, so this phase costs nothing.
- [ ] `npm test` and `npm run build` pass.
- [ ] `approval` defaults to `none` and is **omitted from the YAML** when unset — a
      pre-Phase-13 pipeline round-trips byte-identically.
- [ ] A **root** node with `approval: before` waits, and the executor was never started.
- [ ] A **terminal** node with `approval: after` keeps the run `paused`, never `succeeded`.
- [ ] `awaiting-review` is not in `NODE_TERMINAL` and does not satisfy a dependency.
- [ ] A **failed** node goes to `failed`, not `awaiting-review`.
- [ ] `request_changes` refuses an empty reason.
- [ ] Feedback **accumulates**: the third attempt carries both earlier notes, in order.
- [ ] `attempt` increments per re-run and is durable across a restart.
- [ ] **Retry and request-changes both clear both approval stamps.**
- [ ] Feedback reaches the prompt **body** and never the slash command, asserted by test.
- [ ] A first attempt's prompt is byte-identical to the pre-Phase-13 prompt.
- [ ] `--st-review` is defined in both palettes; `tokens.test.ts` still passes.
- [ ] The review card shows previous rejection notes on attempt ≥ 2.
- [ ] Both routes require `RUN_CONTROL`.

---

## Known limitation, kept

**Request-changes re-runs the whole step.** There is no way to say *"keep requirements 1–6,
redo 7"*. implr steps are file-based and idempotent so a re-run is safe, but it is not cheap:
a rejected `dev-executor` node redoes every task in the plan, and on Opus that is the most
expensive button in the product.

Narrowing it needs per-artefact rejection, which needs a step to report which artefacts it
produced and to accept a subset on re-entry — a change to every skill, not just to the
orchestrator. Deferred deliberately, and worth doing.

**The interim mitigation is a UI one:** the review card shows the paths the step wrote and the
model tiers it used, so the cost of rejecting is visible before you click.

---

## What the next phase gets

HITL that means something. **Phase 14** adds failure and recovery — retry, skip, cancel and
restart recovery — on top of an approval model that now clears itself correctly, which is why
14 comes after 13 rather than before it.
