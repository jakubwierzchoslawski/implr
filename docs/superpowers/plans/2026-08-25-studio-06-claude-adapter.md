# implr Studio — Plan 6: Claude Code Adapter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The one Phase 1 implementation of `StepExecutor` — drive Claude Code via the `claude-agent-sdk` Python package, translate its message stream into `StepEvent`s, and intercept `AskUserQuestion` so operator input flows back into the same session.

**Architecture:** `claude_code.py` implements the Plan 2 Protocol and is the **only** file in the codebase that names Claude. All SDK types are imported behind a thin seam (`_sdk.py`) so the translation logic can be unit-tested against fake message objects with the SDK absent. A background task pumps the SDK's message stream into an `asyncio.Queue`; `events()` drains that queue.

**Tech Stack:** Python 3.11+, `claude-agent-sdk`, `asyncio`, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md`

## Global Constraints

- This is the only module permitted to mention Claude or Anthropic. `executors/base.py` must stay clean — Plan 2's `test_base_module_names_no_provider` enforces it.
- **Question detection is a tool interception, never text parsing.** Do not add a heuristic that inspects assistant prose for question marks or turn boundaries. An earlier draft of the spec assumed turn-end signalling; it is undocumented and was removed for that reason.
- Permission posture is `acceptEdits` plus an explicit allowlist. **Never** use `bypassPermissions` or `--dangerously-skip-permissions` — this agent is driven by a web page.
- If the agent never calls `AskUserQuestion`, the step runs to completion. It must not hang waiting for a question that will not come.
- Every default-suite test runs with the SDK **stubbed**. Real-SDK tests are marked `@pytest.mark.live` and are skipped unless explicitly selected.
- `events()` must always terminate with a `done` event, on every path including SDK exceptions.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/backend/implr_studio/executors/_sdk.py` | Import seam for `claude_agent_sdk`. Isolates the dependency so tests can substitute fakes. |
| `studio/backend/implr_studio/executors/translate.py` | **Pure** functions turning SDK message objects into `StepEvent`s. No async, no SDK import. Heaviest test coverage. |
| `studio/backend/implr_studio/executors/claude_code.py` | `ClaudeCodeExecutor` — session lifecycle, the message pump, `can_use_tool`, answer routing. |
| `studio/backend/tests/test_translate.py` | Message → event mapping. |
| `studio/backend/tests/test_claude_executor.py` | Executor behaviour against a stub SDK client. |
| `studio/backend/tests/test_claude_live.py` | Opt-in real-SDK test, skipped by default. |

---

### Task 1: The SDK import seam and prompt construction

**Files:**
- Create: `studio/backend/implr_studio/executors/_sdk.py`
- Modify: `studio/backend/pyproject.toml` (add `claude-agent-sdk`)
- Test: `studio/backend/tests/test_sdk_seam.py`

**Interfaces:**
- Produces:
  - `_sdk.SDK_AVAILABLE: bool` — whether `claude_agent_sdk` imports.
  - `_sdk.require_sdk() -> None` — raises `ExecutorError` with an install hint if absent.
  - `_sdk.build_prompt(skill: str, args: tuple[str, ...]) -> str` — the slash command plus the question-routing instruction.
  - `_sdk.ALLOWED_TOOLS: tuple[str, ...]` — the allowlist implr skills need.
  - `_sdk.PERMISSION_MODE = "acceptEdits"`
  - `_sdk.QUESTION_INSTRUCTION: str` — the appended instruction text.

- [ ] **Step 1: Add the dependency**

In `studio/backend/pyproject.toml`, add to `dependencies`:

```toml
    "claude-agent-sdk>=0.1.0",
```

Then: `cd studio/backend && python -m pip install -e ".[dev]"`

If the package is unavailable in this environment, continue anyway — every test in Tasks 1–3 runs without it, by design.

- [ ] **Step 2: Write the failing test**

Create `studio/backend/tests/test_sdk_seam.py`:

```python
from pathlib import Path

import pytest

from implr_studio.executors import _sdk


def test_prompt_starts_with_the_slash_command():
    prompt = _sdk.build_prompt("dev-executor", ("--all",))

    assert prompt.startswith("/dev-executor --all")


def test_prompt_with_no_args_has_no_trailing_space_before_the_newline():
    prompt = _sdk.build_prompt("doc-ingest", ())

    assert prompt.splitlines()[0] == "/doc-ingest"


def test_prompt_preserves_argument_order():
    prompt = _sdk.build_prompt("dev-executor", ("--all", "--verbose"))

    assert prompt.splitlines()[0] == "/dev-executor --all --verbose"


def test_prompt_appends_the_question_routing_instruction():
    """This instruction is the entire question-detection mechanism."""
    prompt = _sdk.build_prompt("arch-gen", ())

    assert _sdk.QUESTION_INSTRUCTION in prompt
    assert "AskUserQuestion" in prompt


def test_permission_mode_is_accept_edits_not_bypass():
    assert _sdk.PERMISSION_MODE == "acceptEdits"


def test_allowlist_covers_what_implr_skills_need():
    for tool in ("Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task", "AskUserQuestion"):
        assert tool in _sdk.ALLOWED_TOOLS


def test_no_bypass_permission_anywhere_in_the_module():
    """Security constraint: this agent is driven by a web page."""
    source = Path(_sdk.__file__).read_text(encoding="utf-8")
    for banned in ("bypassPermissions", "dangerously-skip-permissions", "dangerouslySkipPermissions"):
        assert banned not in source


def test_require_sdk_explains_how_to_install_when_missing(monkeypatch):
    monkeypatch.setattr(_sdk, "SDK_AVAILABLE", False)

    with pytest.raises(Exception, match="claude-agent-sdk"):
        _sdk.require_sdk()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_sdk_seam.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio.executors._sdk'`

- [ ] **Step 4: Write the implementation**

Create `studio/backend/implr_studio/executors/_sdk.py`:

```python
"""Import seam for claude-agent-sdk, plus prompt and permission construction.

Isolating the SDK import here means the translation layer and the executor's
control flow can both be tested with the SDK absent.
"""
from .base import ExecutorError

try:  # pragma: no cover - environment dependent
    import claude_agent_sdk  # noqa: F401
    SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    SDK_AVAILABLE = False


# acceptEdits auto-approves file edits and common filesystem commands; everything
# else falls back to the allowlist below. bypassPermissions is deliberately absent:
# this agent is driven by a web page and must not get unrestricted shell access.
PERMISSION_MODE = "acceptEdits"

ALLOWED_TOOLS = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "Task",
    "TodoWrite",
    "AskUserQuestion",
)

QUESTION_INSTRUCTION = (
    "When you need a decision or clarification from the operator, you MUST ask via "
    "the AskUserQuestion tool rather than writing the question as prose. There is no "
    "human reading your text output directly; a prose question will not be seen and "
    "the run will proceed without an answer."
)


def require_sdk() -> None:
    if not SDK_AVAILABLE:
        raise ExecutorError(
            "claude-agent-sdk is not installed. Install it with "
            "`pip install claude-agent-sdk`, or run the server with --fake to use "
            "the scripted test executor."
        )


def build_prompt(skill: str, args: tuple[str, ...]) -> str:
    command = "/%s" % skill
    if args:
        command = "%s %s" % (command, " ".join(args))
    return "%s\n\n%s" % (command, QUESTION_INSTRUCTION)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_sdk_seam.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add studio/backend/implr_studio/executors/_sdk.py studio/backend/tests/test_sdk_seam.py studio/backend/pyproject.toml
git commit -m "feat(studio): SDK seam, prompt construction, and permission allowlist"
```

---

### Task 2: Pure message translation

**Files:**
- Create: `studio/backend/implr_studio/executors/translate.py`
- Test: `studio/backend/tests/test_translate.py`

**Interfaces:**
- Consumes: `StepEvent`, `OUTCOME_SUCCESS`, `OUTCOME_FAILURE` from Plan 2.
- Produces:
  - `translate.message_to_events(message) -> list[StepEvent]` — duck-typed on the SDK's message shapes, so it never imports the SDK.
  - `translate.summarise_tool_use(name: str, tool_input: dict) -> str` — the one-line log form of a tool call.
  - `translate.question_from_tool_input(tool_input: dict) -> tuple[str, list[str] | None]` — `(prompt_md, options)` extracted from an `AskUserQuestion` payload.

Duck-typing rules — a message contributes events when it has:
- `.content` (a list of blocks): each block with `.text` → one `log`; each block with `.name` and `.input` → one `log` summarising the tool call.
- `.subtype` and `.is_error` (a result message) → one `done`.

Anything unrecognised yields `[]`. Unknown message types must be ignored, never crash a run.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_translate.py`:

```python
from dataclasses import dataclass, field

from implr_studio.executors import base
from implr_studio.executors import translate


@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    name: str
    input: dict
    id: str = "tu_1"


@dataclass
class AssistantMessage:
    content: list = field(default_factory=list)


@dataclass
class ResultMessage:
    subtype: str = "success"
    is_error: bool = False
    result: str = ""
    session_id: str = "s1"


@dataclass
class UnknownMessage:
    whatever: str = "?"


def test_assistant_text_becomes_a_log_event():
    events = translate.message_to_events(AssistantMessage(content=[TextBlock("scanning docs")]))

    assert [e.kind for e in events] == ["log"]
    assert events[0].text == "scanning docs"


def test_multiple_text_blocks_become_multiple_logs():
    message = AssistantMessage(content=[TextBlock("one"), TextBlock("two")])

    assert [e.text for e in translate.message_to_events(message)] == ["one", "two"]


def test_tool_use_is_condensed_to_one_log_line():
    message = AssistantMessage(content=[
        ToolUseBlock(name="Read", input={"file_path": "/ws/docs/kb/a.md"}),
    ])

    events = translate.message_to_events(message)

    assert [e.kind for e in events] == ["log"]
    assert "Read" in events[0].text
    assert "a.md" in events[0].text


def test_bash_tool_use_shows_the_command():
    message = AssistantMessage(content=[
        ToolUseBlock(name="Bash", input={"command": "pytest -q", "description": "run tests"}),
    ])

    assert "pytest -q" in translate.message_to_events(message)[0].text


def test_long_tool_input_is_truncated():
    message = AssistantMessage(content=[
        ToolUseBlock(name="Write", input={"content": "x" * 5000, "file_path": "/ws/f.py"}),
    ])

    text = translate.message_to_events(message)[0].text
    assert len(text) < 300


def test_mixed_content_preserves_order():
    message = AssistantMessage(content=[
        TextBlock("about to read"),
        ToolUseBlock(name="Read", input={"file_path": "/ws/x.md"}),
        TextBlock("done reading"),
    ])

    events = translate.message_to_events(message)

    assert len(events) == 3
    assert events[0].text == "about to read"
    assert "Read" in events[1].text
    assert events[2].text == "done reading"


def test_successful_result_becomes_a_done_success():
    events = translate.message_to_events(ResultMessage(subtype="success", result="12 docs"))

    assert [e.kind for e in events] == ["done"]
    assert events[0].outcome == base.OUTCOME_SUCCESS
    assert events[0].summary == "12 docs"


def test_error_result_becomes_a_done_failure():
    events = translate.message_to_events(
        ResultMessage(subtype="error_during_execution", is_error=True, result="it broke")
    )

    assert events[0].outcome == base.OUTCOME_FAILURE
    assert events[0].error


def test_max_turns_result_is_a_failure_naming_the_subtype():
    events = translate.message_to_events(ResultMessage(subtype="error_max_turns", is_error=True))

    assert events[0].outcome == base.OUTCOME_FAILURE
    assert "error_max_turns" in (events[0].error or "")


def test_unknown_message_type_is_ignored_not_fatal():
    """A new SDK message type must never crash a run."""
    assert translate.message_to_events(UnknownMessage()) == []


def test_empty_assistant_message_yields_nothing():
    assert translate.message_to_events(AssistantMessage(content=[])) == []


def test_blank_text_block_is_dropped():
    assert translate.message_to_events(AssistantMessage(content=[TextBlock("   ")])) == []


def test_question_extraction_from_ask_user_question_input():
    tool_input = {
        "questions": [{
            "question": "Postgres or MySQL?",
            "header": "Database",
            "options": [
                {"label": "Postgres", "description": "relational, JSONB"},
                {"label": "MySQL", "description": "relational"},
            ],
        }]
    }

    prompt, options = translate.question_from_tool_input(tool_input)

    assert "Postgres or MySQL?" in prompt
    assert options == ["Postgres", "MySQL"]


def test_question_extraction_includes_option_descriptions_in_the_prompt():
    tool_input = {"questions": [{
        "question": "Pick one", "header": "H",
        "options": [{"label": "A", "description": "the first"},
                    {"label": "B", "description": "the second"}],
    }]}

    prompt, _ = translate.question_from_tool_input(tool_input)

    assert "the first" in prompt


def test_question_extraction_handles_multiple_questions():
    tool_input = {"questions": [
        {"question": "First?", "header": "A", "options": [{"label": "x", "description": ""}]},
        {"question": "Second?", "header": "B", "options": [{"label": "y", "description": ""}]},
    ]}

    prompt, options = translate.question_from_tool_input(tool_input)

    assert "First?" in prompt and "Second?" in prompt
    assert options == ["x", "y"]


def test_question_extraction_survives_a_malformed_payload():
    """Never crash the run because a tool payload was shaped unexpectedly."""
    prompt, options = translate.question_from_tool_input({})

    assert isinstance(prompt, str) and prompt
    assert options is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_translate.py -v`
Expected: FAIL — cannot import `translate`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/executors/translate.py`:

```python
"""Pure translation from SDK message objects to StepEvents.

Duck-typed on message shape rather than isinstance checks, so this module never
imports the SDK and its tests need no SDK installed. An unrecognised message
yields no events - a new SDK message type must never crash a run.
"""
from .base import OUTCOME_FAILURE, OUTCOME_SUCCESS, StepEvent

_MAX_TOOL_SUMMARY = 200

# The most informative field per tool, tried in order.
_TOOL_FIELDS = ("file_path", "command", "pattern", "path", "prompt", "description")


def summarise_tool_use(name: str, tool_input: dict) -> str:
    detail = ""
    for field in _TOOL_FIELDS:
        value = tool_input.get(field)
        if value:
            detail = str(value)
            break
    if not detail and tool_input:
        detail = str(next(iter(tool_input.values())))

    line = "· %s %s" % (name, detail) if detail else "· %s" % name
    if len(line) > _MAX_TOOL_SUMMARY:
        line = line[: _MAX_TOOL_SUMMARY - 1] + "…"
    return line


def question_from_tool_input(tool_input: dict) -> tuple[str, list[str] | None]:
    """Render an AskUserQuestion payload as markdown plus a flat option list."""
    questions = tool_input.get("questions") or []
    if not questions:
        return ("The step is asking for input, but its question could not be read.", None)

    parts: list[str] = []
    options: list[str] = []

    for question in questions:
        text = question.get("question") or question.get("header") or "?"
        parts.append("**%s**" % text)
        for option in question.get("options") or []:
            label = option.get("label")
            if not label:
                continue
            options.append(label)
            description = option.get("description")
            parts.append("- **%s** — %s" % (label, description) if description else "- **%s**" % label)
        parts.append("")

    return ("\n".join(parts).strip(), options or None)


def message_to_events(message) -> list[StepEvent]:
    events: list[StepEvent] = []

    content = getattr(message, "content", None)
    if isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                if text.strip():
                    events.append(StepEvent.log(text))
                continue

            name = getattr(block, "name", None)
            tool_input = getattr(block, "input", None)
            if isinstance(name, str) and isinstance(tool_input, dict):
                events.append(StepEvent.log(summarise_tool_use(name, tool_input)))
        return events

    subtype = getattr(message, "subtype", None)
    if subtype is not None and hasattr(message, "is_error"):
        summary = str(getattr(message, "result", "") or "")
        if getattr(message, "is_error", False):
            events.append(StepEvent.done(
                OUTCOME_FAILURE,
                summary or "step failed",
                error=summary or str(subtype),
            ))
        else:
            events.append(StepEvent.done(OUTCOME_SUCCESS, summary or "completed"))

    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_translate.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/implr_studio/executors/translate.py studio/backend/tests/test_translate.py
git commit -m "feat(studio): pure SDK message to StepEvent translation"
```

---

### Task 3: ClaudeCodeExecutor

**Files:**
- Create: `studio/backend/implr_studio/executors/claude_code.py`
- Test: `studio/backend/tests/test_claude_executor.py`

**Interfaces:**
- Consumes: Tasks 1–2; the Plan 2 Protocol.
- Produces:
  - `ClaudeCodeExecutor(client_factory=None)` — `client_factory(request) -> client` is injected in tests; in production it builds a real `ClaudeSDKClient`.
  - Satisfies `StepExecutor`: `start`, `events`, `answer`, `cancel`.
  - `ClaudeCodeExecutor.can_use_tool(tool_name, tool_input, context)` — the interception hook. For `AskUserQuestion` it emits a `question` event and blocks until answered, then returns an allow-decision carrying the operator's reply. Every other tool is allowed unchanged.

The stub client contract used by tests (and satisfied by a thin wrapper over the real SDK):

```python
class Client(Protocol):
    async def connect(self) -> None
    async def query(self, prompt: str) -> None
    def receive_messages(self) -> AsyncIterator[object]
    async def interrupt(self) -> None
    async def disconnect(self) -> None
```

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_claude_executor.py`:

```python
import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from implr_studio.executors import base
from implr_studio.executors.claude_code import ClaudeCodeExecutor

pytestmark = pytest.mark.asyncio


@dataclass
class TextBlock:
    text: str


@dataclass
class AssistantMessage:
    content: list = field(default_factory=list)


@dataclass
class ResultMessage:
    subtype: str = "success"
    is_error: bool = False
    result: str = "done"


class StubClient:
    """Stands in for ClaudeSDKClient. Yields a scripted message sequence."""

    def __init__(self, messages, on_query=None):
        self.messages = messages
        self.queries: list[str] = []
        self.connected = False
        self.interrupted = False
        self.disconnected = False
        self._on_query = on_query

    async def connect(self):
        self.connected = True

    async def query(self, prompt: str):
        self.queries.append(prompt)
        if self._on_query:
            await self._on_query(self)

    async def receive_messages(self):
        for message in self.messages:
            await asyncio.sleep(0)
            yield message

    async def interrupt(self):
        self.interrupted = True

    async def disconnect(self):
        self.disconnected = True


def _req(skill="doc-ingest", args=()):
    return base.StepRequest(node_id="n1", skill=skill, args=tuple(args), workspace=Path("/ws"))


def _executor(messages, on_query=None):
    client = StubClient(messages, on_query)
    # The factory signature is (request, can_use_tool, handle_id) everywhere - the
    # production factory needs the hook and the handle id to bind the callback.
    executor = ClaudeCodeExecutor(client_factory=lambda request, hook, handle_id: client)
    return executor, client


async def _drain(executor, handle):
    return [e async for e in executor.events(handle)]


async def test_streams_text_then_terminates():
    executor, client = _executor([
        AssistantMessage(content=[TextBlock("scanning")]),
        ResultMessage(result="12 docs"),
    ])
    handle = await executor.start(_req())

    events = await _drain(executor, handle)

    assert [e.kind for e in events] == ["log", "done"]
    assert events[0].text == "scanning"
    assert events[-1].outcome == base.OUTCOME_SUCCESS


async def test_sends_the_slash_command_with_the_question_instruction():
    executor, client = _executor([ResultMessage()])
    await executor.start(_req("dev-executor", ["--all"]))

    assert client.queries[0].startswith("/dev-executor --all")
    assert "AskUserQuestion" in client.queries[0]


async def test_connects_before_querying():
    executor, client = _executor([ResultMessage()])
    await executor.start(_req())

    assert client.connected is True


async def test_failure_result_becomes_a_failure_event():
    executor, _ = _executor([ResultMessage(subtype="error_during_execution",
                                           is_error=True, result="exploded")])
    handle = await executor.start(_req())

    events = await _drain(executor, handle)

    assert events[-1].outcome == base.OUTCOME_FAILURE


async def test_stream_ending_without_a_result_still_terminates():
    """A truncated stream must not hang the orchestrator forever."""
    executor, _ = _executor([AssistantMessage(content=[TextBlock("only text")])])
    handle = await executor.start(_req())

    events = await asyncio.wait_for(_drain(executor, handle), timeout=5)

    assert events[-1].kind == "done"
    assert events[-1].outcome == base.OUTCOME_FAILURE


async def test_an_sdk_exception_becomes_a_failure_event():
    class Exploding(StubClient):
        async def receive_messages(self):
            raise RuntimeError("transport died")
            yield  # pragma: no cover

    executor = ClaudeCodeExecutor(client_factory=lambda r, hook, handle_id: Exploding([]))
    handle = await executor.start(_req())

    events = await asyncio.wait_for(_drain(executor, handle), timeout=5)

    assert events[-1].kind == "done"
    assert events[-1].outcome == base.OUTCOME_FAILURE
    assert "transport died" in (events[-1].error or "")


async def test_ask_user_question_becomes_a_question_event_and_blocks():
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req("arch-gen"))

    collected: list[base.StepEvent] = []

    async def consume():
        async for event in executor.events(handle):
            collected.append(event)

    task = asyncio.create_task(consume())

    tool_input = {"questions": [{
        "question": "Postgres or MySQL?", "header": "DB",
        "options": [{"label": "Postgres", "description": "JSONB"},
                    {"label": "MySQL", "description": "simple"}],
    }]}
    intercept = asyncio.create_task(
        executor.can_use_tool("AskUserQuestion", tool_input, {"handle_id": handle.id})
    )

    await asyncio.sleep(0.05)
    question = next(e for e in collected if e.kind == "question")
    assert "Postgres or MySQL?" in question.prompt_md
    assert question.options == ["Postgres", "MySQL"]
    assert not intercept.done(), "the tool call must block until the operator answers"

    await executor.answer(handle, question.question_id, "Postgres")
    decision = await asyncio.wait_for(intercept, timeout=2)

    assert "Postgres" in str(decision)
    await asyncio.wait_for(task, timeout=5)


async def test_other_tools_are_not_intercepted():
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req())

    decision = await asyncio.wait_for(
        executor.can_use_tool("Bash", {"command": "ls"}, {"handle_id": handle.id}), timeout=2
    )

    assert decision is not None


async def test_step_without_a_question_runs_to_completion():
    """The instruction is not a guarantee. A step that never asks must not hang."""
    executor, _ = _executor([
        AssistantMessage(content=[TextBlock("Should I use Postgres or MySQL?")]),
        ResultMessage(result="finished anyway"),
    ])
    handle = await executor.start(_req("arch-gen"))

    events = await asyncio.wait_for(_drain(executor, handle), timeout=5)

    assert [e.kind for e in events] == ["log", "done"]
    assert not any(e.kind == "question" for e in events)


async def test_cancel_interrupts_and_terminates():
    executor, client = _executor([ResultMessage()])
    handle = await executor.start(_req())

    await executor.cancel(handle)

    assert client.interrupted is True
    events = await asyncio.wait_for(_drain(executor, handle), timeout=5)
    assert events[-1].kind == "done"


async def test_answering_an_unknown_question_raises():
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req())

    with pytest.raises(base.ExecutorError, match="no pending question"):
        await executor.answer(handle, "nope", "text")


async def test_satisfies_the_step_executor_protocol():
    assert isinstance(
        ClaudeCodeExecutor(client_factory=lambda r, hook, handle_id: None), base.StepExecutor
    )


async def test_module_is_the_only_place_naming_the_provider():
    from implr_studio.executors import base as base_module
    from implr_studio.executors import translate as translate_module

    for module in (base_module, translate_module):
        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        assert "claude" not in source
        assert "anthropic" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_claude_executor.py -v`
Expected: FAIL — cannot import `claude_code`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/executors/claude_code.py`:

```python
"""The Claude Code adapter - the only module in implr Studio that names a provider.

Question detection is a tool interception, never text parsing: the prompt instructs
the agent to ask via AskUserQuestion, and can_use_tool intercepts that call. Do not
add a prose-scanning heuristic here; an earlier design assumed turn-end signalling,
which is undocumented, and that assumption was removed deliberately.
"""
import asyncio
import itertools
from typing import AsyncIterator

from . import translate
from ._sdk import ALLOWED_TOOLS, PERMISSION_MODE, build_prompt, require_sdk
from .base import (
    OUTCOME_FAILURE,
    ExecutorError,
    StepEvent,
    StepHandle,
    StepRequest,
)

_ASK_TOOL = "AskUserQuestion"


class _Session:
    def __init__(self, client) -> None:
        self.client = client
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pending_question: str | None = None
        self.answer_text: str | None = None
        self.answered = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.finished = False
        self.pump: asyncio.Task | None = None


def _default_client_factory(request: StepRequest, can_use_tool, handle_id: str):  # pragma: no cover
    require_sdk()
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    async def _hook(tool_name, tool_input, context):
        # The SDK does not know which step this callback belongs to; bind it here.
        ctx = dict(context or {})
        ctx["handle_id"] = handle_id
        return await can_use_tool(tool_name, tool_input, ctx)

    options = ClaudeAgentOptions(
        cwd=str(request.workspace),
        permission_mode=PERMISSION_MODE,
        allowed_tools=list(ALLOWED_TOOLS),
        can_use_tool=_hook,
    )
    return ClaudeSDKClient(options=options)


class ClaudeCodeExecutor:
    def __init__(self, client_factory=None) -> None:
        self._client_factory = client_factory or _default_client_factory
        self._sessions: dict[str, _Session] = {}
        self._ids = itertools.count(1)

    # --- StepExecutor ---

    async def start(self, req: StepRequest) -> StepHandle:
        handle = StepHandle(id="claude-%d" % next(self._ids), request=req)
        client = self._client_factory(req, self.can_use_tool, handle.id)
        session = _Session(client)
        self._sessions[handle.id] = session

        await client.connect()
        await client.query(build_prompt(req.skill, req.args))
        session.pump = asyncio.create_task(self._pump(session))

        return handle

    async def events(self, handle: StepHandle) -> AsyncIterator[StepEvent]:
        session = self._session(handle)
        while True:
            event = await session.queue.get()
            yield event
            if event.is_terminal:
                session.finished = True
                await self._teardown(session)
                return

    async def answer(self, handle: StepHandle, question_id: str, text: str) -> None:
        session = self._session(handle)
        if session.pending_question != question_id:
            raise ExecutorError(
                "no pending question %r for handle %s (pending: %r)"
                % (question_id, handle.id, session.pending_question)
            )
        session.answer_text = text
        session.pending_question = None
        session.answered.set()

    async def cancel(self, handle: StepHandle) -> None:
        session = self._sessions.get(handle.id)
        if session is None or session.finished:
            return
        session.cancelled.set()
        session.answered.set()          # release any blocked tool interception
        try:
            await session.client.interrupt()
        except Exception:               # noqa: BLE001 - cancellation is best-effort
            pass
        await session.queue.put(
            StepEvent.done(OUTCOME_FAILURE, "step cancelled", error="cancelled by operator")
        )

    # --- tool interception ---

    async def can_use_tool(self, tool_name: str, tool_input: dict, context: dict):
        """Intercept AskUserQuestion; allow every other tool unchanged."""
        session = self._sessions.get(context.get("handle_id", ""))
        if tool_name != _ASK_TOOL or session is None:
            return {"behavior": "allow", "updatedInput": tool_input}

        question_id = "q-%d" % next(self._ids)
        prompt_md, options = translate.question_from_tool_input(tool_input)

        session.pending_question = question_id
        session.answered.clear()
        await session.queue.put(StepEvent.question(question_id, prompt_md, options))

        await session.answered.wait()
        if session.cancelled.is_set():
            return {"behavior": "deny", "message": "run cancelled by operator"}

        return {
            "behavior": "allow",
            "updatedInput": tool_input,
            "operator_answer": session.answer_text,
        }

    # --- internals ---

    async def _pump(self, session: _Session) -> None:
        """Drain the SDK message stream into the event queue."""
        try:
            async for message in session.client.receive_messages():
                if session.cancelled.is_set():
                    return
                for event in translate.message_to_events(message):
                    await session.queue.put(event)
                    if event.is_terminal:
                        return
            # The stream ended without a result message. Say so rather than hang.
            await session.queue.put(StepEvent.done(
                OUTCOME_FAILURE,
                "the session ended without reporting a result",
                error="message stream closed before a result message",
            ))
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception as e:  # noqa: BLE001 - any transport failure ends the step
            await session.queue.put(
                StepEvent.done(OUTCOME_FAILURE, "step failed", error=str(e))
            )

    async def _teardown(self, session: _Session) -> None:
        if session.pump is not None and not session.pump.done():
            session.pump.cancel()
        try:
            await session.client.disconnect()
        except Exception:               # noqa: BLE001 - teardown is best-effort
            pass

    def _session(self, handle: StepHandle) -> _Session:
        session = self._sessions.get(handle.id)
        if session is None:
            raise ExecutorError("unknown handle: %s" % handle.id)
        return session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_claude_executor.py -v`
Expected: 13 passed

- [ ] **Step 5: Run the whole backend suite**

Run: `cd studio/backend && python -m pytest -v`
Expected: every test from Plans 1–4 and 6 passes

- [ ] **Step 6: Commit**

```bash
git add studio/backend/implr_studio/executors/claude_code.py studio/backend/tests/test_claude_executor.py
git commit -m "feat(studio): Claude Code adapter with AskUserQuestion interception"
```

---

### Task 4: Opt-in live test and wiring verification

**Files:**
- Create: `studio/backend/tests/test_claude_live.py`
- Modify: `studio/backend/pyproject.toml` (register the `live` marker)
- Modify: `studio/backend/implr_studio/executors/claude_code.py` (register `can_use_tool` with the real client)

**Interfaces:**
- Consumes: everything above.
- Produces: a `@pytest.mark.live` test, skipped by default, that runs a trivial real step end to end.

- [ ] **Step 1: Register the marker**

In `studio/backend/pyproject.toml`, extend the pytest section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "live: hits a real LLM provider; skipped unless -m live is passed",
]
addopts = "-m 'not live'"
```

- [ ] **Step 2: Write the live test**

Create `studio/backend/tests/test_claude_live.py`:

```python
"""Opt-in verification against the real SDK.

Run with:  python -m pytest tests/test_claude_live.py -m live -v

Skipped by default. This is the only test in the suite that spends tokens, and it
exists to confirm the wiring the stubbed tests cannot: that the SDK accepts our
options, that a slash command reaches the skill, and that a result comes back.
"""
from pathlib import Path

import pytest

from implr_studio.executors import _sdk, base
from implr_studio.executors.claude_code import ClaudeCodeExecutor

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


@pytest.mark.skipif(not _sdk.SDK_AVAILABLE, reason="claude-agent-sdk is not installed")
async def test_trivial_step_runs_end_to_end(tmp_path: Path):
    executor = ClaudeCodeExecutor()
    request = base.StepRequest(
        node_id="live", skill="", args=(), workspace=tmp_path, timeout_seconds=120
    )

    handle = await executor.start(request)
    events = [e async for e in executor.events(handle)]

    assert events[-1].kind == "done"
    assert events[-1].outcome == base.OUTCOME_SUCCESS
    assert any(e.kind == "log" for e in events)
```

Note: `skill=""` makes `build_prompt` emit a bare `/` line, which is not a useful probe. Before running this test, change the request to a real read-only skill invocation available in your workspace — the point is to exercise transport, not to assert on a specific skill's output. If no implr skill is safe to run live, replace the prompt with a plain instruction by temporarily passing a `client_factory` that queries `"Reply with the word ready and nothing else."`

- [ ] **Step 3: Verify the marker actually excludes the live test**

Run: `cd studio/backend && python -m pytest -v`
Expected: the live test is **not** collected (deselected by `addopts`)

Run: `cd studio/backend && python -m pytest -m live --collect-only`
Expected: the live test **is** listed

- [ ] **Step 4: Verify the callback is bound, not merely defined**

`can_use_tool` is only reachable in production if the factory passes it into
`ClaudeAgentOptions`. Task 3 already wires this, so confirm rather than rewire:

Run: `cd studio/backend && python -c "import inspect; from implr_studio.executors import claude_code as c; src = inspect.getsource(c._default_client_factory); assert 'can_use_tool=_hook' in src; assert 'handle_id' in src; print('callback is bound')"`
Expected: `callback is bound`

Confirm the factory signature is uniform — the production factory and every test
factory take `(request, can_use_tool, handle_id)`. There is deliberately no
argument-count fallback in `start()`: catching `TypeError` around a factory call
would swallow genuine `TypeError`s raised inside the factory and turn a real bug
into a confusing "unknown handle" error later.

- [ ] **Step 5: Run the whole suite one final time**

Run: `cd studio/backend && python -m pytest -v`
Expected: every non-live test passes

- [ ] **Step 6: Commit**

```bash
git add studio/backend/tests/test_claude_live.py studio/backend/implr_studio/executors/claude_code.py studio/backend/pyproject.toml
git commit -m "feat(studio): opt-in live adapter test and can_use_tool wiring"
```

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes and collects **no** live test.
- [ ] `python -m pytest -m live --collect-only` lists the live test.
- [ ] `base.py` and `translate.py` contain no provider name — asserted by test.
- [ ] No file contains `bypassPermissions` or `dangerously-skip-permissions`.
- [ ] A step whose agent never calls `AskUserQuestion` completes rather than hanging.
- [ ] An SDK exception, and a stream that ends without a result, both produce a terminal `done` failure rather than a hang.
- [ ] `events()` terminates on every path.

## Phase 2 follow-ups this plan makes concrete

1. **Edit `arch-gen` and `dev-planner` to call `AskUserQuestion` directly**, removing the dependency on the appended instruction being honoured. Small, targeted, and it makes question detection a guarantee rather than a strong convention.
2. **A second adapter.** The seam is proven only once something other than `claude_code.py` implements the Protocol. Until then, treat provider-neutrality as designed-for, not demonstrated.
