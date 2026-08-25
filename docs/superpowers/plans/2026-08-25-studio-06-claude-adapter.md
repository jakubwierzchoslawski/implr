# implr Studio — Plan 6: Claude Code Adapter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The one Phase 1 implementation of `StepExecutor` — drive Claude Code via the `claude-agent-sdk` Python package, translate its message stream into `StepEvent`s, and intercept `AskUserQuestion` so operator input flows back into the same session.

**Architecture:** `claude_code.py` implements the Plan 2 Protocol and is the **only** file in the codebase that names Claude. All SDK types are imported behind a thin seam (`_sdk.py`) so the translation logic can be unit-tested against fake message objects with the SDK absent. A background task pumps the SDK's message stream into an `asyncio.Queue`; `events()` drains that queue.

**Tech Stack:** Python 3.11+, `claude-agent-sdk`, `asyncio`, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md`

**Runtime verification:** `docs/RUNTIME.md` — how to prove this plan actually runs, not just that its suite passes.

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
  - `_sdk.allow(updated_input: dict | None = None)` → a `PermissionResultAllow`.
  - `_sdk.deny(message: str, interrupt: bool = False)` → a `PermissionResultDeny`.
  - `_sdk.ANSWER_TEMPLATE: str` — wraps the operator's reply for the return trip.

The `allow`/`deny` helpers exist because `can_use_tool` must return the SDK's
**dataclass** results, not dicts, and the field is `updated_input` (snake_case).
Routing construction through `_sdk` keeps `claude_code.py` testable with the SDK absent.

- [ ] **Step 1: Add the dependency**

In `studio/backend/pyproject.toml`, add to `dependencies`:

```toml
    "claude-agent-sdk>=0.2.144,<0.3",
```

The floor is verified against PyPI, not guessed: the 0.1.x series ends at 0.1.81 and
the current release is 0.2.144. `PermissionResultAllow` / `PermissionResultDeny` and
`ClaudeAgentOptions.can_use_tool` are 0.2-series API, so a 0.1 floor would resolve to
a release without them.

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
    for tool in ("Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task", "Agent"):
        assert tool in _sdk.ALLOWED_TOOLS


def test_ask_user_question_is_not_in_the_allowlist():
    """The load-bearing negative assertion.

    An allowed_tools entry naming a whole tool auto-approves it BEFORE
    can_use_tool is consulted. Allowlisting AskUserQuestion would silently
    disable every question the operator is supposed to see.
    """
    assert "AskUserQuestion" not in _sdk.ALLOWED_TOOLS
    assert "AskUserQuestion" not in _sdk.PERMITTED_ON_REQUEST


def test_skill_tool_is_enabled_through_the_skills_option():
    """The SDK gates the Skill tool behind `skills`; passing it in allowed_tools
    is deprecated and would not enable it."""
    assert _sdk.SKILLS == "all"
    assert "Skill" not in _sdk.ALLOWED_TOOLS


def test_agent_tool_is_allowed_because_implr_agents_declare_it():
    assert "Agent" in _sdk.ALLOWED_TOOLS


def test_tier_map_covers_every_legal_tier():
    from implr_studio.registry import TIERS

    for tier in TIERS:
        assert tier in _sdk.TIER_TO_MODEL


def test_agent_definitions_is_none_without_overrides(tmp_path):
    assert _sdk.agent_definitions(tmp_path, {}) is None


def test_read_agent_file_returns_none_when_absent(tmp_path):
    assert _sdk.read_agent_file(tmp_path, "nope") is None


def test_read_agent_file_parses_description_body_and_tools(tmp_path):
    d = tmp_path / ".claude" / "agents"
    d.mkdir(parents=True)
    (d / "plan-worker.md").write_text(
        "---\nname: plan-worker\ndescription: Produces one plan.\n"
        "tools: [Read, Write, Grep, Glob]\n---\nYou write plans.\n",
        encoding="utf-8",
    )

    description, body, tools = _sdk.read_agent_file(tmp_path, "plan-worker")

    assert description == "Produces one plan."
    assert "You write plans." in body
    assert tools == ["Read", "Write", "Grep", "Glob"]


def test_no_bypass_permission_anywhere_in_the_module():
    """Security constraint: this agent is driven by a web page."""
    source = Path(_sdk.__file__).read_text(encoding="utf-8")
    for banned in ("bypassPermissions", "dangerously-skip-permissions", "dangerouslySkipPermissions"):
        assert banned not in source


def test_require_sdk_explains_how_to_install_when_missing(monkeypatch):
    monkeypatch.setattr(_sdk, "SDK_AVAILABLE", False)

    with pytest.raises(Exception, match="claude-agent-sdk"):
        _sdk.require_sdk()


def test_allow_uses_snake_case_updated_input():
    """The SDK field is updated_input, not updatedInput. A dict would be rejected."""
    result = _sdk.allow({"command": "ls"})

    assert result.behavior == "allow"
    assert result.updated_input == {"command": "ls"}
    assert not isinstance(result, dict)


def test_deny_carries_a_message():
    result = _sdk.deny("nope")

    assert result.behavior == "deny"
    assert result.message == "nope"
    assert result.interrupt is False


def test_answer_template_frames_the_reply_as_a_decision_not_a_refusal():
    text = _sdk.ANSWER_TEMPLATE.format(answer="Postgres")

    assert "Postgres" in text
    assert "not a refusal" in text


@pytest.mark.skipif(not _sdk.SDK_AVAILABLE, reason="claude-agent-sdk is not installed")
def test_helpers_return_the_real_sdk_types_when_installed():
    """Guards against the stand-ins silently masking an SDK API change."""
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    assert isinstance(_sdk.allow(None), PermissionResultAllow)
    assert isinstance(_sdk.deny("x"), PermissionResultDeny)


@pytest.mark.skipif(not _sdk.SDK_AVAILABLE, reason="claude-agent-sdk is not installed")
def test_permission_mode_is_a_value_the_sdk_accepts():
    import dataclasses
    import typing

    from claude_agent_sdk import ClaudeAgentOptions

    field = {f.name: f for f in dataclasses.fields(ClaudeAgentOptions)}["permission_mode"]
    legal = typing.get_args(field.type)
    assert _sdk.PERMISSION_MODE in legal, "permission_mode %r is not accepted by the SDK" % _sdk.PERMISSION_MODE
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

# Auto-approved without prompting. AskUserQuestion is deliberately ABSENT: an
# allowed_tools entry naming a whole tool auto-approves it *before* can_use_tool
# is consulted (the SDK ships a warning helper saying exactly that), so
# allowlisting the one tool this adapter exists to intercept would silently
# disable question proxying. Leaving it out makes its calls fall through to the
# callback, which is the entire mechanism.
#
# Both "Task" and "Agent" appear because implr's own agent definitions declare
# `tools: [..., Agent]`, and doc-ingest, ba-requirements-gen, dev-planner,
# dev-executor and dev-code-review all depend on subagent dispatch.
ALLOWED_TOOLS = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "Task",
    "Agent",
    "TodoWrite",
)

# Tools that reach can_use_tool and are approved there. AskUserQuestion is
# intercepted rather than approved, so it is not in this set either.
PERMITTED_ON_REQUEST = ALLOWED_TOOLS + ("NotebookEdit", "BashOutput", "KillShell")

# Skills are enabled through this option, never through allowed_tools: the SDK
# gates the Skill tool behind it and "configures everything needed (including
# allowing the Skill tool)". Passing "Skill" in allowed_tools is deprecated.
# Without this, no implr step can be invoked at all.
SKILLS = "all"

# Tier -> the model alias the SDK accepts. Kept here so the tier vocabulary that
# crosses the StepExecutor boundary stays provider-neutral.
TIER_TO_MODEL = {
    "haiku": "haiku",
    "sonnet": "sonnet",
    "opus": "opus",
}

QUESTION_INSTRUCTION = (
    "When you need a decision or clarification from the operator, you MUST ask via "
    "the AskUserQuestion tool rather than writing the question as prose. There is no "
    "human reading your text output directly; a prose question will not be seen and "
    "the run will proceed without an answer."
)


# The operator's reply travels back to the agent through the permission-denial
# message, which is the only channel can_use_tool offers to the model. Allowing
# AskUserQuestion instead would let the tool execute, and in a headless session
# there is no human on the other end of it. The wording below matters: a bare
# denial reads as a refusal, so it states plainly that this is the answer.
ANSWER_TEMPLATE = (
    "The operator answered: {answer}\n\n"
    "This is their decision, not a refusal of your request. Proceed using it, and do "
    "not ask the same question again."
)

if SDK_AVAILABLE:  # pragma: no cover - environment dependent
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
else:  # pragma: no cover
    from dataclasses import dataclass

    @dataclass
    class PermissionResultAllow:  # type: ignore[no-redef]
        behavior: str = "allow"
        updated_input: dict | None = None

    @dataclass
    class PermissionResultDeny:  # type: ignore[no-redef]
        behavior: str = "deny"
        message: str = ""
        interrupt: bool = False


def allow(updated_input: dict | None = None):
    return PermissionResultAllow(updated_input=updated_input)


def deny(message: str, interrupt: bool = False):
    return PermissionResultDeny(message=message, interrupt=interrupt)


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


def read_agent_file(workspace, name: str) -> tuple[str, str, list[str] | None] | None:
    """Return (description, body, tools) from <workspace>/.claude/agents/<name>.md.

    Parsed with the same restricted frontmatter reader implr_validate uses, so
    there is no second parser. Returns None when the file is absent.
    """
    from pathlib import Path

    from ..implr_bridge import parse_frontmatter

    path = Path(workspace) / ".claude" / "agents" / ("%s.md" % name)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        fm = parse_frontmatter(text)
    except Exception:
        return None

    parts = text.split("---", 2)
    body = parts[2].strip() if len(parts) == 3 else ""

    raw_tools = fm.get("tools")
    tools = None
    if isinstance(raw_tools, str) and raw_tools.strip():
        tools = [t.strip() for t in raw_tools.strip("[] ").split(",") if t.strip()]

    return (str(fm.get("description", "")), body, tools)


def agent_definitions(workspace, models: dict[str, str]):
    """Turn a node's tier overrides into SDK AgentDefinition objects.

    ClaudeAgentOptions takes an `agents` dict of AgentDefinition, each carrying
    its own `model`, so a tier override lands on a real SDK field - nothing about
    the model goes into the prompt text.

    IMPORTANT: passing an entry here *defines* that agent for the session rather
    than patching the one on disk. So the definition is rebuilt from
    .claude/agents/<name>.md and only its model is changed. An agent whose file
    cannot be read is skipped rather than replaced by a stub - a wrong prompt is
    far worse than an un-overridden model tier.

    Agents the node did not override are omitted entirely, so they resolve
    normally from the filesystem with the project default tier.
    """
    if not models or not SDK_AVAILABLE:  # pragma: no cover - env dependent
        return None
    from claude_agent_sdk import AgentDefinition

    out = {}
    for agent, tier in models.items():
        model = TIER_TO_MODEL.get(tier)
        if model is None:
            continue
        found = read_agent_file(workspace, agent)
        if found is None:
            continue
        description, body, tools = found
        out[agent] = AgentDefinition(
            description=description,
            prompt=body,
            model=model,
            tools=tools,
        )
    return out or None
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
  - `ClaudeCodeExecutor.can_use_tool(handle_id, tool_name, tool_input)` — the interception hook. For `AskUserQuestion` it emits a `question` event, blocks until answered, and returns `_sdk.deny(ANSWER_TEMPLATE...)` carrying the reply. Every other tool returns `_sdk.allow(tool_input)`.

**Why `handle_id` is a parameter and not read from the SDK's context.** The SDK passes a
`ToolPermissionContext` **dataclass** (fields: `signal`, `suggestions`, `tool_use_id`,
`agent_id`, `blocked_path`, …) — not a dict, and with no field this adapter may add. The
per-step identity therefore comes from the closure built in the client factory, which
already knows the handle. Do not attempt `context.get(...)`; it will raise.

**Why the answer returns through `deny`.** `can_use_tool` may return only
`PermissionResultAllow` or `PermissionResultDeny`. Allowing `AskUserQuestion` would let the
tool execute, and a headless session has no human to answer it. `PermissionResultDeny`
carries a `message` that reaches the model, so it is the only path back. `ANSWER_TEMPLATE`
states explicitly that the message is the operator's decision rather than a refusal.
See *Risks requiring live verification* at the end of this plan.

The stub client contract used by tests (and satisfied by a thin wrapper over the real SDK):

```python
class Client(Protocol):
    async def connect(self) -> None: ...
    async def query(self, prompt: str) -> None: ...
    def receive_messages(self) -> AsyncIterator[object]: ...
    async def interrupt(self) -> None: ...
    async def disconnect(self) -> None: ...
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
        executor.can_use_tool(handle.id, "AskUserQuestion", tool_input)
    )

    await asyncio.sleep(0.05)
    question = next(e for e in collected if e.kind == "question")
    assert "Postgres or MySQL?" in question.prompt_md
    assert question.options == ["Postgres", "MySQL"]
    assert not intercept.done(), "the tool call must block until the operator answers"

    await executor.answer(handle, question.question_id, "Postgres")
    decision = await asyncio.wait_for(intercept, timeout=2)

    # The answer returns through the denial message - the only channel to the model.
    assert decision.behavior == "deny"
    assert "Postgres" in decision.message
    assert "not a refusal" in decision.message
    assert decision.interrupt is False
    await asyncio.wait_for(task, timeout=5)


async def test_other_tools_are_not_intercepted():
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req())

    decision = await asyncio.wait_for(
        executor.can_use_tool(handle.id, "Bash", {"command": "ls"}), timeout=2
    )

    assert decision.behavior == "allow"
    assert decision.updated_input == {"command": "ls"}


async def test_unrecognised_tool_is_denied_not_allowed():
    """The spec's posture is deny-by-default. Allowing everything not
    intercepted would make the allowlist decorative."""
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req())

    decision = await asyncio.wait_for(
        executor.can_use_tool(handle.id, "WebFetch", {"url": "https://example.com"}),
        timeout=2,
    )

    assert decision.behavior == "deny"
    assert "WebFetch" in decision.message


async def test_a_denial_is_visible_in_the_node_log():
    """A silent denial is indistinguishable from a step that just did nothing."""
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req())

    await executor.can_use_tool(handle.id, "WebFetch", {"url": "https://example.com"})
    events = await asyncio.wait_for(_drain(executor, handle), timeout=5)

    logs = [e.text for e in events if e.kind == "log"]
    assert any("denied WebFetch" in (t or "") for t in logs)


async def test_model_overrides_reach_the_options_as_agent_definitions(tmp_path):
    """A tier override must land on a real SDK field, not in the prompt text."""
    d = tmp_path / ".claude" / "agents"
    d.mkdir(parents=True)
    (d / "task-executor.md").write_text(
        "---\nname: task-executor\ndescription: Implements one task.\n"
        "tools: [Read, Write, Edit, Bash]\n---\nYou implement one task.\n",
        encoding="utf-8",
    )

    from implr_studio.executors import _sdk

    definitions = _sdk.agent_definitions(tmp_path, {"task-executor": "sonnet"})

    if not _sdk.SDK_AVAILABLE:
        pytest.skip("claude-agent-sdk is not installed")
    assert set(definitions) == {"task-executor"}
    assert definitions["task-executor"].model == "sonnet"
    # The on-disk definition is preserved - only the model changed.
    assert "You implement one task." in definitions["task-executor"].prompt
    assert definitions["task-executor"].description == "Implements one task."


async def test_override_for_an_agent_with_no_file_is_skipped(tmp_path):
    """Better an un-overridden tier than an agent replaced by a stub prompt."""
    from implr_studio.executors import _sdk

    assert _sdk.agent_definitions(tmp_path, {"ghost": "haiku"}) is None


async def test_permission_results_are_sdk_objects_not_dicts():
    """can_use_tool must return PermissionResult dataclasses; a dict is rejected."""
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req())

    decision = await executor.can_use_tool(handle.id, "Read", {"file_path": "/ws/a.md"})

    assert not isinstance(decision, dict)
    assert hasattr(decision, "behavior")


async def test_cancel_denies_a_blocked_question_with_interrupt():
    executor, _ = _executor([ResultMessage()])
    handle = await executor.start(_req("arch-gen"))

    async def consume():
        async for _ in executor.events(handle):
            pass

    task = asyncio.create_task(consume())
    intercept = asyncio.create_task(
        executor.can_use_tool(handle.id, "AskUserQuestion", {"questions": [
            {"question": "Which?", "header": "H", "options": [{"label": "A", "description": ""}]},
        ]})
    )
    await asyncio.sleep(0.05)

    await executor.cancel(handle)
    decision = await asyncio.wait_for(intercept, timeout=2)

    assert decision.behavior == "deny"
    assert decision.interrupt is True
    await asyncio.wait_for(task, timeout=5)


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

from . import _sdk, translate
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

    async def _hook(tool_name, tool_input, _context):
        # _context is the SDK's ToolPermissionContext dataclass. It carries no field
        # for our step identity, so the handle comes from this closure instead.
        return await can_use_tool(handle_id, tool_name, tool_input)

    options = ClaudeAgentOptions(
        cwd=str(request.workspace),
        permission_mode=PERMISSION_MODE,
        allowed_tools=list(ALLOWED_TOOLS),
        # Enables the Skill tool and project setting sources. Without it the
        # agent cannot invoke an implr skill at all.
        skills=_sdk.SKILLS,
        # Tier overrides for this node only; None when nothing was overridden.
        agents=_sdk.agent_definitions(request.workspace, request.models),
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

    async def can_use_tool(self, handle_id: str, tool_name: str, tool_input: dict):
        """Intercept AskUserQuestion; allow every other tool unchanged.

        `handle_id` is supplied by the closure in the client factory. The SDK's own
        ToolPermissionContext is a dataclass with no field this adapter may add, so
        it is not the carrier for per-step identity.
        """
        session = self._sessions.get(handle_id)

        if tool_name != _ASK_TOOL:
            # Deny by default. Returning allow for everything not intercepted -
            # the obvious implementation - would make the allowlist decorative,
            # and the spec's stated posture ("anything outside the allowlist is
            # denied and the denial appears in the node's log") a fiction.
            if tool_name in _sdk.PERMITTED_ON_REQUEST:
                return _sdk.allow(tool_input)
            reason = "tool %r is not permitted for implr steps" % tool_name
            if session is not None:
                await session.queue.put(StepEvent.log("· denied %s" % tool_name))
            return _sdk.deny(reason)

        if session is None:
            # An AskUserQuestion with no session to route it through cannot be
            # answered by anyone, so refuse rather than let it hang.
            return _sdk.deny("no operator channel is available for this step")

        question_id = "q-%d" % next(self._ids)
        prompt_md, options = translate.question_from_tool_input(tool_input)

        session.pending_question = question_id
        session.answered.clear()
        await session.queue.put(StepEvent.question(question_id, prompt_md, options))

        await session.answered.wait()
        if session.cancelled.is_set():
            return _sdk.deny("run cancelled by the operator", interrupt=True)

        # Deny is the return channel, not a refusal - see ANSWER_TEMPLATE.
        return _sdk.deny(_sdk.ANSWER_TEMPLATE.format(answer=session.answer_text))

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

Skipped by default. These are the only tests in the suite that spend tokens, and
they exist to prove the two things the stubbed tests cannot:

  1. the SDK accepts our options and returns a result at all;
  2. the agent treats a PermissionResultDeny message as an ANSWER and carries on -
     the single assumption in this plan that no offline test can settle.

Both use a throwaway workspace and a trivial prompt, not a real implr skill.
"""
import asyncio
from pathlib import Path

import pytest

from implr_studio.executors import _sdk, base
from implr_studio.executors.claude_code import ClaudeCodeExecutor

pytestmark = [
    pytest.mark.live,
    pytest.mark.asyncio,
    pytest.mark.skipif(not _sdk.SDK_AVAILABLE, reason="claude-agent-sdk is not installed"),
]


class _FixedPromptClient:
    """Wraps a real ClaudeSDKClient, substituting the prompt on query().

    ClaudeCodeExecutor.start always sends build_prompt(skill, args). A live probe
    wants a plain instruction rather than a slash command, so the substitution
    happens here instead of adding a test-only branch to production code.
    """

    def __init__(self, inner, prompt: str) -> None:
        self._inner = inner
        self._prompt = prompt

    async def connect(self):
        return await self._inner.connect()

    async def query(self, _prompt: str):
        return await self._inner.query(self._prompt)

    def receive_messages(self):
        return self._inner.receive_messages()

    async def interrupt(self):
        return await self._inner.interrupt()

    async def disconnect(self):
        return await self._inner.disconnect()


def _client_factory_with_prompt(prompt: str):
    """A factory matching the production signature but sending a fixed prompt.

    The point is to exercise transport and the permission callback, not to run an
    implr skill - a live test must never mutate a real workspace.
    """
    def factory(request, can_use_tool, handle_id):
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

        async def hook(tool_name, tool_input, _context):
            return await can_use_tool(handle_id, tool_name, tool_input)

        options = ClaudeAgentOptions(
            cwd=str(request.workspace),
            permission_mode=_sdk.PERMISSION_MODE,
            allowed_tools=list(_sdk.ALLOWED_TOOLS),
            can_use_tool=hook,
        )
        return _FixedPromptClient(ClaudeSDKClient(options=options), prompt)

    return factory


async def test_transport_returns_a_result(tmp_path: Path):
    """Confirms options are accepted and a ResultMessage comes back."""
    executor = ClaudeCodeExecutor(
        client_factory=_client_factory_with_prompt("Reply with the single word: ready")
    )
    request = base.StepRequest(
        node_id="live", skill="__probe__", args=(), workspace=tmp_path, timeout_seconds=120
    )

    handle = await executor.start(request)
    events = [e async for e in executor.events(handle)]

    assert events[-1].kind == "done"
    assert events[-1].outcome == base.OUTCOME_SUCCESS, events[-1].error
    assert any(e.kind == "log" for e in events)


async def test_agent_treats_a_denial_message_as_an_answer(tmp_path: Path):
    """THE load-bearing assumption of this plan.

    The agent is told to ask via AskUserQuestion. The adapter answers through the
    permission-denial message. This test proves the agent then acts on that answer
    instead of treating it as a refusal and giving up.

    If this fails, the fallback is the Phase 2 follow-up: edit arch-gen and
    dev-planner to call AskUserQuestion directly and return the answer as a real
    tool result. Do not paper over a failure here with a prose-parsing heuristic.
    """
    prompt = (
        "Ask me, using the AskUserQuestion tool, whether to use Postgres or MySQL. "
        "Once you have my answer, reply with exactly: CHOSEN=<my answer>\n\n"
        + _sdk.QUESTION_INSTRUCTION
    )
    executor = ClaudeCodeExecutor(client_factory=_client_factory_with_prompt(prompt))
    request = base.StepRequest(
        node_id="live", skill="__probe__", args=(), workspace=tmp_path, timeout_seconds=180
    )

    handle = await executor.start(request)
    collected: list[base.StepEvent] = []

    async def consume():
        async for event in executor.events(handle):
            collected.append(event)

    task = asyncio.create_task(consume())

    # Wait for the agent to ask.
    for _ in range(120):
        question = next((e for e in collected if e.kind == "question"), None)
        if question is not None:
            break
        await asyncio.sleep(0.5)
    assert question is not None, "the agent never called AskUserQuestion"

    await executor.answer(handle, question.question_id, "Postgres")
    await asyncio.wait_for(task, timeout=180)

    transcript = "\n".join(e.text or "" for e in collected if e.kind == "log")
    assert "CHOSEN=Postgres" in transcript or "Postgres" in transcript, (
        "the agent did not act on the answer delivered via the denial message.\n"
        "Transcript:\n%s" % transcript
    )
```

Note on `_FixedPromptClient`: `ClaudeCodeExecutor.start` always sends
`build_prompt(req.skill, req.args)`. The wrapper substitutes a plain instruction at
`query()` time, so production code needs no test-only branch. `skill="__probe__"` is
therefore never sent anywhere — it only satisfies `StepRequest`.

If you would rather exercise a real slash command, use a read-only one
(`/doc-ingest --dry-run`) against a scratch workspace — **never** a skill that writes, and
never the repository you are working in.

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
- [ ] `AskUserQuestion` is **absent** from both `ALLOWED_TOOLS` and `PERMITTED_ON_REQUEST`,
      asserted by test — allowlisting it would auto-approve the call before `can_use_tool`
      ran and silently disable every operator question.
- [ ] `skills="all"` is passed in `ClaudeAgentOptions`, and `"Skill"` is not in
      `allowed_tools`. Without the option no implr step can be invoked.
- [ ] `Agent` is in the allowlist alongside `Task`.
- [ ] An unrecognised tool is **denied**, and the denial appears as a `log` event.
- [ ] A tier override becomes an `AgentDefinition` whose `model` is the tier and whose
      `prompt` is the real body of `.claude/agents/<name>.md` — an override never replaces
      an agent with a stub, and an agent with no file is skipped rather than stubbed.
- [ ] `_sdk.py` imports cleanly — `ANSWER_TEMPLATE` uses `\n\n`, not a literal newline
      inside the string literal.

### Step 2b: The live test that matters most

Add to `studio/backend/tests/test_claude_live.py`:

```python
async def test_a_real_slash_command_invokes_a_real_implr_skill(tmp_path: Path):
    """The one production assumption no offline test can reach.

    Everything else about the adapter is verified with a stub client. But whether
    `client.query("/doc-ingest --registry-only --dry-run")` actually resolves to
    the installed implr skill - rather than being treated as literal prose - is a
    property of the CLI, the workspace's .claude/skills tree, and the `skills`
    option working together. If this fails, no pipeline runs at all, and the
    stubbed suite would still be green.

    Uses --dry-run against a throwaway workspace so nothing is written.
    """
    import shutil

    from implr_studio.executors._sdk import build_prompt
    from implr_studio import implr_bridge

    # A minimal installed workspace: the skill, and somewhere for it to look.
    repo = implr_bridge.repo_root()
    shutil.copytree(repo / "skills" / "doc-ingest", tmp_path / ".claude" / "skills" / "doc-ingest")
    (tmp_path / "docs" / "kb").mkdir(parents=True)
    (tmp_path / "docs" / "kb" / "note.md").write_text("# A note\n\nHello.\n", encoding="utf-8")

    executor = ClaudeCodeExecutor()
    request = base.StepRequest(
        node_id="live", skill="doc-ingest", args=("--registry-only", "--dry-run"),
        workspace=tmp_path, timeout_seconds=300,
    )

    handle = await executor.start(request)
    events = [e async for e in executor.events(handle)]

    assert events[-1].kind == "done"
    transcript = "\n".join(e.text or "" for e in events if e.kind == "log")
    assert events[-1].outcome == base.OUTCOME_SUCCESS, (
        "the step failed: %s\nTranscript:\n%s" % (events[-1].error, transcript)
    )
    # The skill ran, rather than the prompt being echoed as prose.
    assert "doc-ingest" in transcript.lower()
    assert build_prompt("doc-ingest", ("--registry-only", "--dry-run")).startswith(
        "/doc-ingest --registry-only --dry-run"
    )
```

---

## Risks requiring live verification

Everything else in this plan is settled by offline tests. These three are not, and all are
proven or disproven by `pytest -m live`:

0. **A slash command must actually invoke the installed skill.** `build_prompt` produces
   `/doc-ingest --registry-only`, and whether that resolves to the skill or is read as
   literal prose depends on the CLI, the workspace's `.claude/skills` tree and the `skills`
   option agreeing. Nothing offline can test it, and if it is wrong, no pipeline runs at
   all while the stubbed suite stays green. This is the first live test to run.

1. **The agent must treat a `PermissionResultDeny` message as an answer.** This is the
   return path for every operator reply. `can_use_tool` can only return allow or deny, and
   allowing `AskUserQuestion` would let a tool run that needs a human who is not there. If
   the agent reads the denial as a refusal and abandons the decision, the mechanism does
   not work and the fix is the Phase 2 follow-up below — **not** a prose-parsing fallback.
2. **The agent must honour the `AskUserQuestion` instruction.** `QUESTION_INSTRUCTION` is
   an instruction, not a guarantee. A step that asks in prose anyway completes without
   pausing rather than hanging, which is the safe failure, but the operator never sees the
   question.

Run `python -m pytest tests/test_claude_live.py -m live -v` before trusting an interactive
step (`arch-gen`, `ba-cr`, `dev-planner --brainstorm`) in a real run. Non-interactive steps
— `doc-ingest`, `dev-executor`, `dev-code-review` — do not depend on either assumption.

## Phase 2 follow-ups this plan makes concrete

1. **Edit `arch-gen` and `dev-planner` to call `AskUserQuestion` directly**, removing the dependency on the appended instruction being honoured. Small, targeted, and it makes question detection a guarantee rather than a strong convention.
2. **A second adapter.** The seam is proven only once something other than `claude_code.py` implements the Protocol. Until then, treat provider-neutrality as designed-for, not demonstrated.
