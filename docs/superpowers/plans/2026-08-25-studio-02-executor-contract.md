# implr Studio — Plan 2: Executor Contract & FakeExecutor

> ## ⚠ SUPERSEDED — source material only
>
> This layer plan has been **replaced** by the phase breakdown in
> [`2026-08-25-studio-phases.md`](2026-08-25-studio-phases.md), which slices the same work
> vertically so every phase ends in something you can open in a browser.
>
> **Do not execute this document.** It is retained only as the source its content is being
> redistributed from. See *Where the old plans' content went* in the roadmap for the mapping.
> It will be deleted once phases 4-13 are written.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define the provider-neutral `StepExecutor` contract that every LLM provider adapter must satisfy, plus a scripted `FakeExecutor` that lets the entire orchestrator be tested with zero LLM calls and zero token spend.

**Architecture:** A `studio/backend/implr_studio/executors/` subpackage. `base.py` holds pure data types and a `typing.Protocol` — no I/O, no subprocess, no provider names. `fake.py` implements that Protocol by replaying a scripted list of events, including questions that block until answered. Nothing in this plan imports or references Claude.

**Tech Stack:** Python 3.11+, `asyncio`, `typing.Protocol`, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md`

**Runtime verification:** `docs/RUNTIME.md` — how to prove this plan actually runs, not just that its suite passes.

## Global Constraints

- Nothing in `executors/base.py` or `executors/fake.py` may mention Claude, Anthropic, subprocesses, or any provider. If a provider name appears in either file, the abstraction has failed.
- `StepEvent.kind` is exactly one of `"log"`, `"question"`, `"artifact"`, `"done"`. No other kinds.
- **Question arming rule.** An executor MUST record the pending question *before* it emits
  the `question` event, and MUST accept `answer()` while its event iterator is suspended or
  abandoned. The orchestrator stops consuming events the moment a question arrives and
  resumes only after the operator replies, so an executor that arms the question *after*
  the yield can never be answered. This is a contract on every implementation, not an
  implementation detail of any one of them.
- `artifact` events are **advisory only**. The orchestrator must never use them to decide whether a gate is open — gates read the filesystem. This is enforced by review, not by code.
- All executor methods are `async`. The orchestrator is an asyncio application.
- Python target: 3.11+.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/backend/implr_studio/executors/__init__.py` | Re-exports the public contract types. |
| `studio/backend/implr_studio/executors/base.py` | `StepRequest`, `StepEvent`, `StepHandle`, `StepExecutor` Protocol, `ExecutorError`. Pure data + interface. |
| `studio/backend/implr_studio/executors/fake.py` | `FakeExecutor` and its scripting types. Test double only — never imported by production code paths. |
| `studio/backend/tests/test_executor_base.py` | Event constructors and Protocol conformance. |
| `studio/backend/tests/test_fake_executor.py` | Scripted playback, question/answer handshake, failure, cancellation. |

---

### Task 1: The executor contract types

**Files:**
- Create: `studio/backend/implr_studio/executors/__init__.py`
- Create: `studio/backend/implr_studio/executors/base.py`
- Test: `studio/backend/tests/test_executor_base.py`

**Interfaces:**
- Consumes: nothing from earlier plans.
- Produces:
  - `StepRequest` — frozen dataclass: `node_id: str`, `skill: str`, `args: tuple[str, ...]`, `workspace: Path`, `timeout_seconds: int | None = None`, `models: dict[str, str]`.

`models` maps an agent name to a **tier** (`haiku` / `sonnet` / `opus`), never a provider
model ID. Tiers are a concept every provider has; `claude-opus-5` is not. The adapter
translates tier to whatever its own runtime calls that model, which is the same reason
`skill` and `args` cross this boundary as data rather than as a formatted command.
  - `StepHandle` — dataclass: `id: str`, `request: StepRequest`.
  - `StepEvent` — frozen dataclass: `kind: str`, `payload: dict`. Constructors: `StepEvent.log(text)`, `StepEvent.question(question_id, prompt_md, options=None)`, `StepEvent.artifact(path)`, `StepEvent.done(outcome, summary, error=None)`.
  - `StepEvent` accessors: `.text`, `.question_id`, `.prompt_md`, `.options`, `.outcome`, `.summary`, `.error`, and `.is_terminal` (True only for `kind == "done"`).
  - `StepExecutor` — `typing.Protocol` with `start`, `events`, `answer`, `cancel`.
  - `ExecutorError` — exception raised for contract misuse (e.g. answering an unknown question).
  - `OUTCOME_SUCCESS = "success"`, `OUTCOME_FAILURE = "failure"`.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_executor_base.py`:

```python
from pathlib import Path

import pytest

from implr_studio.executors import base


def _req() -> base.StepRequest:
    return base.StepRequest(
        node_id="ingest", skill="doc-ingest", args=("--digest",), workspace=Path("/tmp/ws")
    )


def test_step_request_is_frozen():
    req = _req()
    with pytest.raises(Exception):
        req.skill = "other"       # type: ignore[misc]


def test_step_request_carries_skill_and_args_as_data_not_a_command_string():
    """The adapter decides what skill+args mean. The contract must not pre-format them."""
    req = _req()
    assert req.skill == "doc-ingest"
    assert req.args == ("--digest",)
    assert not hasattr(req, "command")
    assert not hasattr(req, "command_line")


def test_log_event():
    e = base.StepEvent.log("hello")
    assert e.kind == "log"
    assert e.text == "hello"
    assert e.is_terminal is False


def test_question_event_defaults_to_no_options():
    e = base.StepEvent.question("q1", "Pick a database?")
    assert e.kind == "question"
    assert e.question_id == "q1"
    assert e.prompt_md == "Pick a database?"
    assert e.options is None
    assert e.is_terminal is False


def test_question_event_can_carry_options():
    """Unused in Phase 1, but reserved so structured questions need no contract change."""
    e = base.StepEvent.question("q1", "Pick one", options=["a", "b"])
    assert e.options == ["a", "b"]


def test_artifact_event():
    e = base.StepEvent.artifact("docs/ARCHITECTURE.md")
    assert e.kind == "artifact"
    assert e.payload["path"] == "docs/ARCHITECTURE.md"
    assert e.is_terminal is False


def test_done_success_event():
    e = base.StepEvent.done(base.OUTCOME_SUCCESS, "12 files digested")
    assert e.kind == "done"
    assert e.outcome == "success"
    assert e.summary == "12 files digested"
    assert e.error is None
    assert e.is_terminal is True


def test_done_failure_event_carries_error():
    e = base.StepEvent.done(base.OUTCOME_FAILURE, "step failed", error="exit code 1")
    assert e.outcome == "failure"
    assert e.error == "exit code 1"
    assert e.is_terminal is True


def test_done_rejects_unknown_outcome():
    with pytest.raises(ValueError, match="unknown outcome"):
        base.StepEvent.done("maybe", "hmm")


def test_accessors_on_wrong_kind_return_none():
    """Accessors are conveniences over payload; they must not explode on the wrong kind."""
    assert base.StepEvent.log("x").outcome is None
    assert base.StepEvent.done(base.OUTCOME_SUCCESS, "ok").text is None


def test_event_kinds_are_exactly_the_four():
    assert base.EVENT_KINDS == ("log", "question", "artifact", "done")


def test_base_module_names_no_provider():
    """The contract must stay provider-neutral - this is the whole point of the module."""
    source = Path(base.__file__).read_text(encoding="utf-8").lower()
    for banned in ("claude", "anthropic", "openai", "gpt", "subprocess", "gemini"):
        assert banned not in source, "provider/transport detail leaked into the contract: %s" % banned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_executor_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio.executors'`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/executors/base.py`:

```python
"""The provider-neutral step execution contract.

Every LLM provider adapter implements StepExecutor. Nothing provider-specific
belongs in this module: no transport, no vendor names, no command formatting.
A StepRequest carries `skill` and `args` as data, and each adapter decides what
they mean for its own runtime.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Protocol, runtime_checkable

EVENT_KINDS = ("log", "question", "artifact", "done")

OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"
OUTCOMES = (OUTCOME_SUCCESS, OUTCOME_FAILURE)


class ExecutorError(Exception):
    """Raised when the contract is misused (e.g. answering an unknown question)."""


@dataclass(frozen=True)
class StepRequest:
    node_id: str
    skill: str
    args: tuple[str, ...] = ()
    workspace: Path = Path(".")
    timeout_seconds: int | None = None
    # Agent name -> model tier ("haiku" | "sonnet" | "opus"). Sparse: an absent
    # agent inherits the project default. Deliberately generic - "tier" is a
    # concept every provider has, and no provider's model IDs appear here.
    models: dict[str, str] = field(default_factory=dict)


@dataclass
class StepHandle:
    """Opaque token identifying one in-flight step. Adapters may subclass it."""
    id: str
    request: StepRequest


@dataclass(frozen=True)
class StepEvent:
    kind: str
    payload: dict = field(default_factory=dict)

    # --- constructors ---

    @staticmethod
    def log(text: str) -> "StepEvent":
        return StepEvent("log", {"text": text})

    @staticmethod
    def question(question_id: str, prompt_md: str, options: list[str] | None = None) -> "StepEvent":
        return StepEvent(
            "question",
            {"question_id": question_id, "prompt_md": prompt_md, "options": options},
        )

    @staticmethod
    def artifact(path: str) -> "StepEvent":
        return StepEvent("artifact", {"path": path})

    @staticmethod
    def done(outcome: str, summary: str, error: str | None = None) -> "StepEvent":
        if outcome not in OUTCOMES:
            raise ValueError("unknown outcome %r (legal: %s)" % (outcome, list(OUTCOMES)))
        return StepEvent("done", {"outcome": outcome, "summary": summary, "error": error})

    # --- accessors (None when the kind does not carry the field) ---

    @property
    def is_terminal(self) -> bool:
        return self.kind == "done"

    @property
    def text(self) -> str | None:
        return self.payload.get("text")

    @property
    def question_id(self) -> str | None:
        return self.payload.get("question_id")

    @property
    def prompt_md(self) -> str | None:
        return self.payload.get("prompt_md")

    @property
    def options(self) -> list[str] | None:
        return self.payload.get("options")

    @property
    def outcome(self) -> str | None:
        return self.payload.get("outcome")

    @property
    def summary(self) -> str | None:
        return self.payload.get("summary")

    @property
    def error(self) -> str | None:
        return self.payload.get("error")


@runtime_checkable
class StepExecutor(Protocol):
    """Implemented once per LLM provider."""

    async def start(self, req: StepRequest) -> StepHandle:
        """Begin executing the step. Returns immediately with a handle."""
        ...

    def events(self, handle: StepHandle) -> AsyncIterator[StepEvent]:
        """Yield events until a terminal `done` event. Must be called at most once."""
        ...

    async def answer(self, handle: StepHandle, question_id: str, text: str) -> None:
        """Deliver the operator's reply to a pending question."""
        ...

    async def cancel(self, handle: StepHandle) -> None:
        """Abandon the step. Safe to call after completion."""
        ...
```

Create `studio/backend/implr_studio/executors/__init__.py`:

```python
from .base import (
    EVENT_KINDS,
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    ExecutorError,
    StepEvent,
    StepExecutor,
    StepHandle,
    StepRequest,
)

__all__ = [
    "EVENT_KINDS",
    "OUTCOME_FAILURE",
    "OUTCOME_SUCCESS",
    "ExecutorError",
    "StepEvent",
    "StepExecutor",
    "StepHandle",
    "StepRequest",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_executor_base.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/implr_studio/executors studio/backend/tests/test_executor_base.py
git commit -m "feat(studio): provider-neutral StepExecutor contract"
```

---

### Task 2: FakeExecutor — scripted playback

**Files:**
- Create: `studio/backend/implr_studio/executors/fake.py`
- Modify: `studio/backend/pyproject.toml` (add asyncio_mode config)
- Test: `studio/backend/tests/test_fake_executor.py`

**Interfaces:**
- Consumes: everything from Task 1.
- Produces:
  - `fake.FakeExecutor(scripts: dict[str, list[StepEvent]] | None = None, default: list[StepEvent] | None = None)` — keys are `skill` names.
  - `FakeExecutor.started: list[StepRequest]` — every request passed to `start`, in order.
  - `FakeExecutor.answers: list[tuple[str, str]]` — `(question_id, text)` in order.
  - `FakeExecutor.cancelled: list[str]` — handle ids cancelled.
  - `FakeExecutor.set_script(skill: str, events: list[StepEvent]) -> None`
  - Playback rule: a `question` event is yielded, then playback **blocks** until `answer()` is called for that `question_id`.
  - If a script has no terminal `done` event, `FakeExecutor` appends `done(success, "scripted end")` so `events()` always terminates.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_fake_executor.py`:

```python
import asyncio
from pathlib import Path

import pytest

from implr_studio.executors import base
from implr_studio.executors.fake import FakeExecutor

pytestmark = pytest.mark.asyncio


def _req(skill: str = "doc-ingest") -> base.StepRequest:
    return base.StepRequest(node_id="n1", skill=skill, args=(), workspace=Path("/tmp/ws"))


async def _drain(ex: FakeExecutor, handle) -> list[base.StepEvent]:
    return [e async for e in ex.events(handle)]


async def test_replays_scripted_events_in_order():
    ex = FakeExecutor({"doc-ingest": [
        base.StepEvent.log("scanning"),
        base.StepEvent.log("digesting"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "12 docs"),
    ]})
    handle = await ex.start(_req())

    events = await _drain(ex, handle)

    assert [e.kind for e in events] == ["log", "log", "done"]
    assert events[0].text == "scanning"
    assert events[-1].summary == "12 docs"


async def test_records_what_was_started():
    ex = FakeExecutor()
    await ex.start(base.StepRequest(node_id="n1", skill="dev-executor", args=("--all",), workspace=Path(".")))

    assert ex.started[0].skill == "dev-executor"
    assert ex.started[0].args == ("--all",)


async def test_script_without_done_is_terminated_automatically():
    """events() must always terminate, or the orchestrator hangs forever."""
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.log("only a log")]})
    handle = await ex.start(_req())

    events = await _drain(ex, handle)

    assert events[-1].kind == "done"
    assert events[-1].outcome == "success"


async def test_default_script_used_for_unknown_skill():
    ex = FakeExecutor(default=[base.StepEvent.done(base.OUTCOME_SUCCESS, "default")])
    handle = await ex.start(_req("never-scripted"))

    events = await _drain(ex, handle)

    assert events[-1].summary == "default"


async def test_failure_outcome_is_replayed():
    ex = FakeExecutor({"doc-ingest": [
        base.StepEvent.done(base.OUTCOME_FAILURE, "it broke", error="exit 1"),
    ]})
    handle = await ex.start(_req())

    events = await _drain(ex, handle)

    assert events[-1].outcome == "failure"
    assert events[-1].error == "exit 1"


async def test_question_blocks_until_answered():
    ex = FakeExecutor({"arch-gen": [
        base.StepEvent.log("thinking"),
        base.StepEvent.question("q1", "Postgres or MySQL?"),
        base.StepEvent.log("noted"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "done"),
    ]})
    handle = await ex.start(_req("arch-gen"))

    collected: list[base.StepEvent] = []

    async def consume():
        async for e in ex.events(handle):
            collected.append(e)

    task = asyncio.create_task(consume())

    # Let playback reach the question and stop there.
    await asyncio.sleep(0.05)
    assert [e.kind for e in collected] == ["log", "question"]
    assert not task.done(), "playback must block on an unanswered question"

    await ex.answer(handle, "q1", "Postgres")
    await asyncio.wait_for(task, timeout=2)

    assert [e.kind for e in collected] == ["log", "question", "log", "done"]
    assert ex.answers == [("q1", "Postgres")]


async def test_question_can_be_answered_after_the_iterator_is_abandoned():
    """THE contract test. This is exactly how the orchestrator behaves.

    It consumes events until a question arrives, then stops iterating entirely -
    the driver task returns and the async generator is left suspended at the
    yield. The answer arrives later, from an HTTP request, and only then does a
    new driver pass resume the same iterator.

    An executor that arms the pending question after the yield fails here even
    though it passes test_question_blocks_until_answered, because that test keeps
    consuming. Every executor must pass this one.
    """
    ex = FakeExecutor({"arch-gen": [
        base.StepEvent.log("thinking"),
        base.StepEvent.question("q1", "Postgres or MySQL?"),
        base.StepEvent.log("noted"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "done"),
    ]})
    handle = await ex.start(_req("arch-gen"))

    stream = ex.events(handle)
    seen: list[base.StepEvent] = []

    # Pass one: consume up to and including the question, then walk away.
    async for event in stream:
        seen.append(event)
        if event.kind == "question":
            break

    assert [e.kind for e in seen] == ["log", "question"]

    # The answer must be accepted with nothing iterating the stream.
    await ex.answer(handle, "q1", "Postgres")
    assert ex.answers == [("q1", "Postgres")]

    # Pass two: resume the SAME iterator and it must run to completion.
    async for event in stream:
        seen.append(event)

    assert [e.kind for e in seen] == ["log", "question", "log", "done"]
    assert seen[-1].outcome == base.OUTCOME_SUCCESS


async def test_answering_unknown_question_raises():
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")]})
    handle = await ex.start(_req())

    with pytest.raises(base.ExecutorError, match="no pending question"):
        await ex.answer(handle, "nope", "text")


async def test_two_questions_are_answered_in_sequence():
    ex = FakeExecutor({"arch-gen": [
        base.StepEvent.question("q1", "first?"),
        base.StepEvent.question("q2", "second?"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "done"),
    ]})
    handle = await ex.start(_req("arch-gen"))
    collected: list[base.StepEvent] = []

    async def consume():
        async for e in ex.events(handle):
            collected.append(e)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await ex.answer(handle, "q1", "a")
    await asyncio.sleep(0.05)
    await ex.answer(handle, "q2", "b")
    await asyncio.wait_for(task, timeout=2)

    assert ex.answers == [("q1", "a"), ("q2", "b")]
    assert collected[-1].kind == "done"


async def test_cancel_stops_playback_with_a_terminal_event():
    ex = FakeExecutor({"arch-gen": [
        base.StepEvent.question("q1", "waiting forever?"),
        base.StepEvent.done(base.OUTCOME_SUCCESS, "unreachable"),
    ]})
    handle = await ex.start(_req("arch-gen"))
    collected: list[base.StepEvent] = []

    async def consume():
        async for e in ex.events(handle):
            collected.append(e)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)

    await ex.cancel(handle)
    await asyncio.wait_for(task, timeout=2)

    assert handle.id in ex.cancelled
    assert collected[-1].kind == "done"
    assert collected[-1].outcome == "failure"
    assert "cancelled" in collected[-1].summary.lower()


async def test_cancel_after_completion_is_safe():
    ex = FakeExecutor({"doc-ingest": [base.StepEvent.done(base.OUTCOME_SUCCESS, "ok")]})
    handle = await ex.start(_req())
    await _drain(ex, handle)

    await ex.cancel(handle)      # must not raise


async def test_set_script_overrides_after_construction():
    ex = FakeExecutor()
    ex.set_script("doc-ingest", [base.StepEvent.done(base.OUTCOME_FAILURE, "nope")])
    handle = await ex.start(_req())

    events = await _drain(ex, handle)

    assert events[-1].outcome == "failure"


async def test_satisfies_the_step_executor_protocol():
    assert isinstance(FakeExecutor(), base.StepExecutor)


async def test_each_start_gets_a_distinct_handle():
    ex = FakeExecutor()
    h1 = await ex.start(_req())
    h2 = await ex.start(_req())

    assert h1.id != h2.id
```

- [ ] **Step 2: Add asyncio config to pyproject.toml**

In `studio/backend/pyproject.toml`, replace the `[tool.pytest.ini_options]` section with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_fake_executor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio.executors.fake'`

- [ ] **Step 4: Write the implementation**

Create `studio/backend/implr_studio/executors/fake.py`:

```python
"""A scripted StepExecutor for tests.

The orchestrator, gate evaluation, persistence, and streaming layers are all
tested through this class, so none of their tests cost a token. Any orchestrator
behaviour that cannot be exercised here is a design smell.
"""
import asyncio
import itertools
from typing import AsyncIterator

from .base import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    ExecutorError,
    StepEvent,
    StepHandle,
    StepRequest,
)

_CANCELLED = "step cancelled"


class _Session:
    def __init__(self, events: list[StepEvent]) -> None:
        self.events = events
        self.pending_question: str | None = None
        self.answered = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.finished = False


class FakeExecutor:
    """Replays scripted events. Questions block playback until answered."""

    def __init__(
        self,
        scripts: dict[str, list[StepEvent]] | None = None,
        default: list[StepEvent] | None = None,
    ) -> None:
        self._scripts: dict[str, list[StepEvent]] = dict(scripts or {})
        self._default = list(default) if default is not None else [
            StepEvent.done(OUTCOME_SUCCESS, "fake default")
        ]
        self._sessions: dict[str, _Session] = {}
        self._ids = itertools.count(1)

        self.started: list[StepRequest] = []
        self.answers: list[tuple[str, str]] = []
        self.cancelled: list[str] = []

    def set_script(self, skill: str, events: list[StepEvent]) -> None:
        self._scripts[skill] = list(events)

    async def start(self, req: StepRequest) -> StepHandle:
        self.started.append(req)
        handle = StepHandle(id="fake-%d" % next(self._ids), request=req)
        script = list(self._scripts.get(req.skill, self._default))
        if not script or not script[-1].is_terminal:
            script.append(StepEvent.done(OUTCOME_SUCCESS, "scripted end"))
        self._sessions[handle.id] = _Session(script)
        return handle

    async def events(self, handle: StepHandle) -> AsyncIterator[StepEvent]:
        session = self._session(handle)
        for event in session.events:
            if session.cancelled.is_set():
                break

            # Arm the question BEFORE yielding it. The consumer abandons this
            # iterator as soon as it sees a question event and only resumes after
            # answer() lands, so arming afterwards would make the question
            # unanswerable and clearing `answered` afterwards would discard a
            # reply that had already arrived. See the question arming rule.
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

    async def _wait_for_answer_or_cancel(self, session: _Session) -> None:
        answered = asyncio.create_task(session.answered.wait())
        cancelled = asyncio.create_task(session.cancelled.wait())
        done, pending = await asyncio.wait(
            {answered, cancelled}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()

    async def answer(self, handle: StepHandle, question_id: str, text: str) -> None:
        session = self._session(handle)
        if session.pending_question != question_id:
            raise ExecutorError(
                "no pending question %r for handle %s (pending: %r)"
                % (question_id, handle.id, session.pending_question)
            )
        self.answers.append((question_id, text))
        session.pending_question = None
        session.answered.set()

    async def cancel(self, handle: StepHandle) -> None:
        session = self._sessions.get(handle.id)
        if session is None or session.finished:
            return
        self.cancelled.append(handle.id)
        session.cancelled.set()

    def _session(self, handle: StepHandle) -> _Session:
        session = self._sessions.get(handle.id)
        if session is None:
            raise ExecutorError("unknown handle: %s" % handle.id)
        return session
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_fake_executor.py -v`
Expected: 13 passed

- [ ] **Step 6: Run the whole suite**

Run: `cd studio/backend && python -m pytest -v`
Expected: all tests from Plan 1 and Plan 2 pass

- [ ] **Step 7: Commit**

```bash
git add studio/backend/implr_studio/executors/fake.py studio/backend/tests/test_fake_executor.py studio/backend/pyproject.toml
git commit -m "feat(studio): scripted FakeExecutor for token-free orchestrator tests"
```

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes all Plan 1 + Plan 2 tests.
- [ ] `test_base_module_names_no_provider` passes — no vendor or transport word appears in `base.py`.
- [ ] `FakeExecutor` satisfies `isinstance(..., StepExecutor)` at runtime.
- [ ] A scripted question genuinely blocks playback until `answer()` is called, proven by the `not task.done()` assertion rather than by timing alone.
- [ ] `events()` always terminates with a `done` event — including for scripts that omit one, and for cancelled sessions.
- [ ] `test_question_can_be_answered_after_the_iterator_is_abandoned` passes — a question
      is answerable while nothing is consuming the stream, and resuming the same iterator
      runs the step to completion. This is the contract the orchestrator actually relies on.
