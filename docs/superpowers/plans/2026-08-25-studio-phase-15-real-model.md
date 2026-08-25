# implr Studio — Phase 15: Real model

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop `--fake` and watch a real agent stream into the same console. Nothing in the UI changes — that is the proof.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-design.md` (*Component: executor*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 14. A real adapter fails in ways a scripted one never does — rate limits,
a killed CLI, a turn cap. Every one of those paths needs retry, cancel and recovery to already
exist.

**⚠ This phase spends tokens.** Every earlier phase is free. Budget accordingly, and run the
demo with `--dry-run` on the pipeline the first time.

---

## Demo

```bash
implr-studio --workspace $PROBE          # note: no --fake
```

Run `doc-ingest --dry-run`. Real log lines stream into the browser progressively, the step
reports `succeeded`, the run reports a **cost**, and the workspace is unmodified because of
`--dry-run`.

**Nothing in the UI is new.** If the adapter honours the `StepExecutor` contract, the console
cannot tell the difference — and if the console *does* change, the contract leaked.

Then the question round trip, for real:

Run a step whose skill asks something. The agent calls `AskUserQuestion`, the node goes
**`awaiting-input`**, the question card renders the agent's own options, you answer, and the agent
**continues from where it was** rather than starting over.

---

## Why this phase is the risky one

Everything before it was verifiable offline. This phase has four failure modes that **every
offline test passes**, and each one silently disables a feature you already shipped:

| # | Failure mode | What it silently breaks | How to catch it |
|---|---|---|---|
| 1 | A slash command does not invoke the installed skill | **Every pipeline.** No step does anything, and every stubbed test is green | Verify **first**, before writing any of the rest |
| 2 | `can_use_tool` is shadowed by a whole-tool allow entry | Question proxying — `AskUserQuestion` auto-approves and never reaches the operator | The SDK emits `CanUseToolShadowedWarning`; assert its **absence** |
| 3 | `skills="all"` | Same as #2, invisibly: the transport appends a bare `"Skill"` to `allowed_tools` | Use `skills=[names]`, and assert `"all"` is never passed |
| 4 | The agent reads `PermissionResultDeny` as a refusal, not an answer | Every operator reply. The agent apologises and gives up instead of continuing | Only a live run shows this |

**#2 and #3 are the same bug wearing two hats, and #3 is the one nobody would guess.** The
installed SDK's own source says it:

```python
# claude_agent_sdk/types.py, _warn_if_can_use_tool_shadowed
# skills="all" makes the transport append a bare "Skill" to the effective
# allowed_tools, so it shadows the callback just like a hand-written entry.
# skills=[names] appends Skill(name) specifiers, which do not.
```

So `skills="all"` — the convenient-looking value — disables question proxying. `skills=[...]`
does not. The fix is one character of list brackets and it is invisible in every test that does
not make a real call.

**The good news is that #2 and #3 are now testable offline.** `CanUseToolShadowedWarning` is an
exported `UserWarning`, emitted at query construction. A test can build our real options and
assert **no warning is raised** — which converts the most dangerous item on this list from a
live-only risk into part of the free suite.

---

## Scope boundary — not in this phase

- **No new UI.** Not one component. If the console needs a change, the contract was wrong.
- **No session resumption after a crash.** `ClaudeAgentOptions.resume` exists and this is the
  right eventual home for it — but Phase 14 deliberately fails an interrupted node, and changing
  that here would bundle two arguments into one phase.
- **No provider beyond Claude Code.** The Protocol exists so a second adapter is possible; adding
  one now would be designing for an imagined requirement.
- **No streaming partial assistant text.** `include_partial_messages` gives token-by-token
  output. It is a nice demo and it multiplies event volume by two orders of magnitude, which is a
  Phase 16 storage question, not a Phase 15 one.
- **No prompt caching or budget tuning.** `max_budget_usd` is *set* (see constraints) but not
  exposed as a per-step control in the UI.

---

## Global constraints

**Three modules, and the split is the point.**

| Module | May import the SDK? | Why |
|---|---|---|
| `executors/_sdk.py` | **yes, and it is the only one** | one import seam, so the SDK can be absent and the rest still imports |
| `executors/translate.py` | **no** | pure functions over SDK message *objects*; testable with hand-built ones |
| `executors/claude_code.py` | no directly — via `_sdk` | the async plumbing |

The reason `translate.py` may not import the SDK is that message → event mapping is where the
bugs are, and it should be testable with a plain dataclass and no subprocess. A test suite that
needs the Claude CLI installed to check whether a `ResultMessage` maps to a done event will get
skipped, and then it will rot.

**`PERMITTED_TOOLS` is imported from `registry.py`, not redeclared.** Phase 8 declared it as a
policy. This phase consumes it. There is a test.

**`allowed_tools` entries must carry specifiers.** The SDK's rule parser treats `"Read"`,
`"Read()"` and `"Read(*)"` as *whole-tool* allows, all three of which auto-approve before
`can_use_tool` runs. Anything we want the callback to see must be either absent from
`allowed_tools` or narrowed.

**`permission_mode` is never `bypassPermissions`.** It shadows `can_use_tool` outright, for every
tool, and the SDK says so in the warning text. `acceptEdits` is the intended value for a step that
writes files.

**`AskUserQuestion` is never in `allowed_tools`.** It must fall through to `can_use_tool`, which
is how the question reaches the operator. Asserted twice: once by name, once by the absence of the
shadow warning.

**`skills` is a context filter, not a sandbox.** The SDK's own docstring: *"unlisted skills are
hidden from the model's listing and rejected by the Skill tool, but their files remain on disk and
are reachable via Read/Bash."* So passing `skills=[one_name]` does **not** isolate a tenant's
skills from each other — only not materialising them does. That is Phase 16's problem and the note
belongs here because this is where the temptation to rely on it appears.

**Every step gets a cost ceiling.** `max_budget_usd` is set from config, defaulting to something
finite. An agentic step with a runaway loop is the one failure mode that is unbounded in dollars
rather than in time, and a ceiling is one field.

**The live suite is opt-in and marked.** `-m live`, deselected by default, and it prints what it
is about to spend before it spends it.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/executors/_sdk.py` | The **only** module importing `claude_agent_sdk`. Options construction, prompt, permissions, tier mapping, agent definitions. |
| `packages/implr_studio/executors/translate.py` | Pure: SDK message → `StepEvent`. No SDK import. |
| `packages/implr_studio/executors/claude_code.py` | The `StepExecutor` implementation. |
| `packages/implr_studio/config.py` | **Modified** — `agents:` tiers, `max_budget_usd`. |
| `packages/implr_studio/cli.py` | **Modified** — `--fake` becomes opt-**in**; real is the default. |
| `packages/implr_studio/tests/test_sdk_seam.py` | Options construction, offline. |
| `packages/implr_studio/tests/test_translate.py` | Message mapping, offline. |
| `packages/implr_studio/tests/test_live.py` | `@pytest.mark.live`. Spends money. |

---

### Task 0: Prove a slash command invokes the skill

**Do this before writing anything else.** It is failure mode #1, it invalidates the entire
approach if it is wrong, and it takes ten minutes.

- [ ] **Step 1: The smallest possible live check**

```python
# packages/implr_studio/tests/test_live.py
import pytest

pytestmark = pytest.mark.live


async def test_a_slash_command_actually_invokes_the_skill(probe_workspace):
    """FAILURE MODE #1. If this does not hold, no pipeline runs at all, and
    every offline test stays green while nothing works. Nothing else in this
    phase is worth writing until it passes."""
    from claude_agent_sdk import ClaudeSDKClient
    from implr_studio.executors import _sdk

    options = _sdk.build_options(skill="doc-ingest", workspace=probe_workspace,
                                models={}, tools_by_agent={})
    saw_skill_invocation = False

    async with ClaudeSDKClient(options=options) as client:
        await client.query("/doc-ingest --dry-run")
        async for message in client.receive_response():
            if _sdk.is_skill_invocation(message, "doc-ingest"):
                saw_skill_invocation = True

    assert saw_skill_invocation, (
        "the slash command did not invoke the installed skill - check "
        "`skills=` and that install.sh put doc-ingest in .claude/skills/")
```

- [ ] **Step 2: Run it**

```bash
python -m pytest packages/implr_studio/tests/test_live.py -m live -k slash -v
```

If it fails, stop and fix the invocation path — `skills=`, `cwd`, `setting_sources`, or the
install — before proceeding. Do not work around it in the prompt.

---

### Task 1: The options seam

**Files:**
- Create: `packages/implr_studio/executors/_sdk.py`
- Test: `packages/implr_studio/tests/test_sdk_seam.py`

**Interfaces:**
- `_sdk.SDK_AVAILABLE: bool` — a soft import, so the package still imports without the SDK.
- `_sdk.TIER_TO_MODEL: dict[str, str]` — `{"haiku": "haiku", "sonnet": "sonnet", "opus": "opus"}`;
  aliases, not pinned ids, so a model refresh does not need a Studio release.
- `_sdk.build_options(skill, workspace, models, tools_by_agent, *, feedback=(), budget_usd=None) -> ClaudeAgentOptions`
- `_sdk.build_prompt(skill, args, feedback=()) -> str` — from Phase 13.
- `_sdk.agent_definitions(workspace, models, tools_by_agent) -> dict[str, AgentDefinition]`
- `_sdk.PERMITTED_TOOLS` — `from implr_studio.registry import PERMITTED_TOOLS`, re-exported.

- [ ] **Step 1: Write the failing test**

```python
import warnings

import pytest

from implr_studio import registry
from implr_studio.executors import _sdk

pytest.importorskip("claude_agent_sdk")


def _opts(**kw):
    base = dict(skill="doc-ingest", workspace="/w", models={}, tools_by_agent={})
    base.update(kw)
    return _sdk.build_options(**base)


# --- FAILURE MODES #2 and #3, now offline ---------------------------------

def test_our_options_emit_no_shadowing_warning():
    """THE test of this phase. The SDK warns when an allowed_tools entry or a
    permission_mode auto-approves before can_use_tool runs. Question proxying
    depends on the callback running, so the warning's absence IS the feature.

    This converts a live-only risk into a free test."""
    from claude_agent_sdk import CanUseToolShadowedWarning
    from claude_agent_sdk import ClaudeSDKClient

    options = _opts()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ClaudeSDKClient(options=options)          # construction is enough

    shadow = [w for w in caught if issubclass(w.category, CanUseToolShadowedWarning)]
    assert shadow == [], shadow[0].message if shadow else None


def test_skills_is_a_list_and_never_the_string_all():
    """FAILURE MODE #3. `skills="all"` makes the transport append a bare
    "Skill" to allowed_tools, which shadows can_use_tool - silently disabling
    every question. `skills=[names]` appends Skill(name) specifiers, which do
    not. One character of brackets; invisible without a real call."""
    options = _opts()

    assert isinstance(options.skills, list)
    assert options.skills != "all"
    assert "doc-ingest" in options.skills


def test_ask_user_question_is_not_in_allowed_tools():
    """FAILURE MODE #2, by name. A whole-tool allow entry auto-approves before
    can_use_tool is consulted."""
    assert "AskUserQuestion" not in _opts().allowed_tools


def test_no_allowed_tools_entry_allows_a_whole_tool():
    """The SDK's rule parser treats "Read", "Read()" and "Read(*)" as
    whole-tool allows. All three shadow the callback."""
    for entry in _opts().allowed_tools:
        assert "(" in entry and not entry.endswith("()") and not entry.endswith("(*)"), entry


@pytest.mark.parametrize("mode", ["bypassPermissions"])
def test_we_never_use_a_permission_mode_that_shadows(mode):
    """bypassPermissions auto-approves EVERY tool call before the callback."""
    assert _opts().permission_mode != mode


def test_permission_mode_is_accept_edits():
    """A step that writes files needs it, and it is the strictest mode that
    does not prompt on every Edit."""
    assert _opts().permission_mode == "acceptEdits"


# --- the ordinary ones -----------------------------------------------------

def test_the_permitted_set_is_imported_not_redeclared():
    """Phase 8 declared it. If this module redeclares, authoring accepts a
    tool the adapter refuses and the step fails at run time for no visible
    reason."""
    assert _sdk.PERMITTED_TOOLS is registry.PERMITTED_TOOLS


def test_every_granted_tool_is_permitted():
    granted = {e.split("(")[0] for e in _opts().allowed_tools}

    assert granted <= set(registry.PERMITTED_TOOLS)


def test_cwd_is_the_workspace():
    assert str(_opts(workspace="/probe").cwd) == "/probe"


def test_a_budget_ceiling_is_set():
    """The one failure mode that is unbounded in dollars rather than time."""
    assert _opts(budget_usd=5.0).max_budget_usd == 5.0


def test_a_budget_is_set_even_when_config_omits_one():
    assert _opts().max_budget_usd is not None


def test_can_use_tool_is_a_coroutine_function():
    import inspect

    assert inspect.iscoroutinefunction(_opts().can_use_tool)


def test_the_module_imports_without_the_sdk(monkeypatch):
    """The whole point of a seam: `--fake` must work on a machine with no SDK
    and no Claude CLI, which is every CI runner for phases 0-14."""
    import importlib
    import sys

    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    mod = importlib.reload(_sdk)

    assert mod.SDK_AVAILABLE is False
```

- [ ] **Step 2: Implement**

```python
try:
    from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions
    SDK_AVAILABLE = True
except ImportError:                     # --fake must work with no SDK installed
    AgentDefinition = ClaudeAgentOptions = None
    SDK_AVAILABLE = False

from implr_studio.registry import PERMITTED_TOOLS   # Phase 8 declared it

DEFAULT_BUDGET_USD = 10.0

# Every entry carries a specifier. A bare "Read" - or "Read()" or "Read(*)" -
# is a whole-tool allow, and the SDK auto-approves those BEFORE can_use_tool
# runs. AskUserQuestion is absent entirely, which is how a question reaches
# the operator rather than approving itself.
ALLOWED_TOOLS = (
    "Read(*)"        # <-- WRONG, kept here only as a comment: this shadows.
)
```

That last block is deliberately not the implementation — write the real one as narrowed
specifiers per tool, and let the shadow-warning test tell you whether you got it right. It will.

```python
def build_options(skill, workspace, models, tools_by_agent, *,
                  feedback=(), budget_usd=None):
    return ClaudeAgentOptions(
        cwd=str(workspace),
        # A LIST, never "all": "all" appends a bare "Skill" to allowed_tools
        # and shadows can_use_tool, silently disabling question proxying.
        skills=[skill],
        allowed_tools=list(_narrowed_allow_entries()),
        permission_mode="acceptEdits",
        can_use_tool=_permission_callback,
        agents=agent_definitions(workspace, models, tools_by_agent),
        max_budget_usd=budget_usd or DEFAULT_BUDGET_USD,
        # setting_sources stays None: the SDK configures it when `skills` is
        # set, and None already loads user/project/local. Verified against
        # 0.2.144 rather than assumed.
    )
```

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(executor): the SDK options seam, with the shadowing test"
```

---

### Task 2: Agent definitions from implr's own files

**Files:**
- Modify: `packages/implr_studio/executors/_sdk.py`
- Test: `packages/implr_studio/tests/test_agent_definitions.py`

**Interfaces:**
- `agent_definitions(workspace, models, tools_by_agent) -> dict[str, AgentDefinition]`

**The rule that makes this correct: change only the model.** implr's eleven agent prompts are the
product. An `AgentDefinition` with a stub prompt would *replace* `task-executor` with a
placeholder, and the pipeline would still run — producing plausible, untested code. So each
definition is built by **reading `.claude/agents/<name>.md`** and overriding the tier.

- [ ] **Step 1: Write the failing test**

```python
def test_the_prompt_comes_from_the_agent_file(workspace):
    """The prompts ARE the product. A stub prompt replaces task-executor's
    TDD enforcement with nothing, and the run still looks successful."""
    defs = _sdk.agent_definitions(workspace, {"task-executor": "sonnet"}, {})

    assert "TDD" in defs["task-executor"].prompt


def test_only_the_model_is_overridden(workspace):
    base = _sdk.agent_definitions(workspace, {}, {})
    tuned = _sdk.agent_definitions(workspace, {"task-executor": "haiku"}, {})

    assert tuned["task-executor"].prompt == base["task-executor"].prompt
    assert tuned["task-executor"].model == "haiku"


def test_an_agent_with_no_file_is_skipped_not_stubbed(workspace):
    """Concretely: implr.config.yaml's own example block still names
    `doc-ingest-extractor`, whose agent file the CHANGELOG records as removed.
    A stub for it would inject an empty-prompt agent into every run."""
    defs = _sdk.agent_definitions(workspace, {"doc-ingest-extractor": "haiku"}, {})

    assert "doc-ingest-extractor" not in defs


def test_an_unreadable_file_is_skipped_and_reported(workspace, caplog):
    """Silently skipping is how you lose task-executor without noticing."""
    (workspace / ".claude/agents/plan-worker.md").write_bytes(b"\xff\xfe bad")

    defs = _sdk.agent_definitions(workspace, {}, {})

    assert "plan-worker" not in defs
    assert "plan-worker" in caplog.text


def test_all_eleven_shipped_agents_are_defined(workspace):
    """Guards the silent-skip path: if the loader quietly drops agents, this
    is the test that notices."""
    assert len(_sdk.agent_definitions(workspace, {}, {})) == 11


def test_an_unspecified_tier_inherits(workspace):
    """`inherit` is a real SDK value. Passing None would let the CLI pick,
    which is a different and less predictable thing."""
    assert _sdk.agent_definitions(workspace, {}, {})["plan-worker"].model == "inherit"


def test_authored_tool_grants_reach_the_definition(workspace):
    """Phase 8's authored steps, arriving here."""
    defs = _sdk.agent_definitions(workspace, {}, {"task-executor": ["Read", "Edit"]})

    assert defs["task-executor"].tools == ["Read", "Edit"]


def test_a_tool_grant_outside_the_permitted_set_raises(workspace):
    """Defence in depth. Phase 8 validates at write time; this refuses at run
    time, because steps.yaml is a file anyone can edit."""
    with pytest.raises(ValueError, match="WebFetch"):
        _sdk.agent_definitions(workspace, {}, {"task-executor": ["WebFetch"]})


def test_max_turns_uses_the_camel_case_field(workspace):
    """AgentDefinition is camelCase: maxTurns, disallowedTools,
    permissionMode. snake_case is silently ignored as an unknown kwarg."""
    defs = _sdk.agent_definitions(workspace, {}, {}, max_turns={"plan-worker": 12})

    assert defs["plan-worker"].maxTurns == 12
```

The camelCase test earns its place. `AgentDefinition` mixes conventions — `description`, `prompt`,
`tools`, `model`, `skills` are snake, and `maxTurns`, `disallowedTools`, `mcpServers`,
`initialPrompt`, `permissionMode` are camel. A `max_turns=` kwarg is a `TypeError` at best and an
ignored field at worst.

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(executor): agent definitions from implr's own prompts"
```

---

### Task 3: Message → event, pure

**Files:**
- Create: `packages/implr_studio/executors/translate.py`
- Test: `packages/implr_studio/tests/test_translate.py`

**Interfaces:**
- `translate.to_events(message) -> list[StepEvent]` — zero, one or many.
- `translate.result_to_done(message) -> StepEvent` — outcome, summary, cost, turns.
- **No `claude_agent_sdk` import.** Tests build message objects by hand.

- [ ] **Step 1: Write the failing test**

```python
import dataclasses

from implr_studio.executors import base, translate


@dataclasses.dataclass
class FakeText:
    text: str


@dataclasses.dataclass
class FakeAssistant:
    content: list
    model: str = "claude-sonnet-5"


@dataclasses.dataclass
class FakeResult:
    subtype: str = "success"
    is_error: bool = False
    num_turns: int = 3
    total_cost_usd: float | None = 0.0412
    result: str | None = "wrote 4 files"
    stop_reason: str | None = None
    duration_ms: int = 1234


def test_the_module_does_not_import_the_sdk():
    """The bug surface is message mapping. If testing it needs the CLI
    installed, the suite gets skipped and then it rots."""
    import inspect

    src = inspect.getsource(translate)
    assert "claude_agent_sdk" not in src


def test_assistant_text_becomes_a_log_event():
    events = translate.to_events(FakeAssistant(content=[FakeText("reading docs")]))

    assert [e.kind for e in events] == ["log"]
    assert events[0].text == "reading docs"


def test_a_result_becomes_a_done_event_with_the_cost():
    event = translate.result_to_done(FakeResult())

    assert event.is_terminal
    assert event.outcome == base.OUTCOME_SUCCESS
    assert event.cost_usd == 0.0412
    assert event.turns == 3


def test_an_error_result_is_a_failure():
    event = translate.result_to_done(FakeResult(is_error=True, result="rate limited"))

    assert event.outcome == base.OUTCOME_FAILURE
    assert "rate limited" in event.summary


def test_a_missing_cost_is_none_not_zero():
    """Zero and unknown are different numbers, and a dashboard that adds them
    together under-reports spend."""
    assert translate.result_to_done(FakeResult(total_cost_usd=None)).cost_usd is None


def test_a_budget_stop_is_a_failure_that_says_so():
    """The one failure the operator must not have to guess at: the step did
    not fail, it ran out of money."""
    event = translate.result_to_done(
        FakeResult(is_error=True, subtype="error_max_budget", result=None))

    assert event.outcome == base.OUTCOME_FAILURE
    assert "budget" in event.summary.lower()


def test_a_turn_cap_stop_says_so_too():
    event = translate.result_to_done(FakeResult(is_error=True, subtype="error_max_turns"))

    assert "turns" in event.summary.lower()


def test_an_unknown_message_type_yields_nothing_rather_than_raising():
    """The SDK adds message types between versions. An unknown one must not
    kill a run twenty minutes in."""
    assert translate.to_events(object()) == []


def test_empty_assistant_content_yields_nothing():
    assert translate.to_events(FakeAssistant(content=[])) == []


def test_a_thinking_block_is_not_logged():
    """Reasoning is not operator-facing output, and streaming it into the log
    pane buries the four lines that matter."""
    @dataclasses.dataclass
    class FakeThinking:
        thinking: str = "hmm"

    assert translate.to_events(FakeAssistant(content=[FakeThinking()])) == []
```

The unknown-message test is the one that pays for itself. `to_events` is called for every message
in a twenty-minute run; a `KeyError` on a new SDK message type would fail the step for a reason
that has nothing to do with the step.

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(executor): pure message-to-event translation"
```

---

### Task 4: The adapter

**Files:**
- Create: `packages/implr_studio/executors/claude_code.py`
- Test: `packages/implr_studio/tests/test_claude_code_executor.py`

**Interfaces:**
- `ClaudeCodeExecutor(workspace, config)` — satisfies `StepExecutor`.
- `start(request) -> AsyncIterator[StepEvent]`
- The `can_use_tool` callback: `AskUserQuestion` → yield a `question` event, wait for the answer,
  return `PermissionResultDeny(behavior="deny", message=<the answer>, interrupt=False)`.

**Why a deny carries the answer.** There is no "here is the tool result" return path in the
permission callback — the two outcomes are allow and deny, and denying with a message is how text
gets back to the model. `interrupt` must be **False**: `True` aborts the turn, so the agent would
receive the answer and immediately stop.

- [ ] **Step 1: Write the failing test**

```python
async def test_it_satisfies_the_protocol():
    """Structural, not nominal. The Protocol is the contract; conforming to it
    is why nothing in the UI changes this phase."""
    assert isinstance(ClaudeCodeExecutor(workspace, config), base.StepExecutor)


async def test_the_orchestrator_contract_suite_passes(executor_contract):
    """The SAME suite Phase 9 wrote for FakeExecutor, run against this
    adapter with the SDK client stubbed. If the shared suite passes, run mode
    cannot tell the two apart - which is the claim this phase is making."""
    await executor_contract(ClaudeCodeExecutor)


async def test_a_question_yields_a_question_event(stub_client):
    stub_client.will_ask("Which database?", ["Postgres", "SQLite"])

    events = [e async for e in ex.start(request)]

    assert [e.kind for e in events][:1] == ["question"]
    assert events[0].options == ["Postgres", "SQLite"]


async def test_the_answer_returns_as_a_non_interrupting_deny(stub_client):
    """interrupt=True aborts the turn: the agent gets the answer and stops."""
    ...
    assert result.behavior == "deny"
    assert result.interrupt is False
    assert result.message == "Postgres"


async def test_the_agent_is_not_restarted_to_answer(stub_client):
    """Phase 12's headline assertion, against the real adapter: one session
    per step across a question round trip. Restarting looks identical in the
    browser and costs double."""
    ...
    assert stub_client.connects == 1


async def test_aclose_disconnects_the_client(stub_client):
    """Phase 14's cancel path. Without this, Abort leaves a CLI subprocess
    running and billing."""
    stream = ex.start(request)
    await anext(stream)
    await stream.aclose()

    assert stub_client.disconnected is True


async def test_a_cli_not_found_error_is_a_readable_failure(monkeypatch):
    """The most likely first-run error, and 'CLINotFoundError' in a red box
    is not an instruction."""
    ...
    assert "install" in event.summary.lower()


async def test_a_process_error_does_not_leak_the_argv(monkeypatch):
    """The argv carries the workspace path and, in hosted mode, may carry
    more. A stack trace in the UI is a disclosure surface."""
    ...
    assert "ANTHROPIC_API_KEY" not in event.summary


async def test_the_api_key_is_never_in_an_event(stub_client):
    """Events are persisted, streamed over a WebSocket, and archived to Blob."""
    events = [e async for e in ex.start(request)]

    assert all("sk-ant" not in (e.text or "") for e in events)
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(executor): the Claude Code adapter"
```

---

### Task 5: The live suite

**Files:**
- Modify: `packages/implr_studio/tests/test_live.py`, `pyproject.toml`
- Test: itself

**Interfaces:**
- `pyproject.toml`: `markers = ["live: spends money; deselected by default"]` and
  `addopts = "-m 'not live'"`.

- [ ] **Step 1: Write the tests**

```python
pytestmark = pytest.mark.live


async def test_a_real_step_streams_and_succeeds(probe_workspace):
    """The end-to-end claim, once."""
    ...
    assert done.outcome == base.OUTCOME_SUCCESS
    assert len(log_events) > 1          # progressive, not one burst
    assert done.cost_usd > 0


async def test_dry_run_leaves_the_workspace_unmodified(probe_workspace, git_sha):
    """The safety property the demo relies on. If --dry-run writes, the
    'try it safely' story is false and the first run is a surprise."""
    ...
    assert current_sha(probe_workspace) == git_sha
    assert not dirty(probe_workspace)


async def test_a_real_question_reaches_the_operator(probe_workspace):
    """FAILURE MODE #4, and the only way to test it. Every offline test
    passes whether or not the agent understands a deny as an answer."""
    ...
    assert question_event is not None


async def test_the_agent_continues_after_the_answer(probe_workspace):
    """The other half of #4. The agent must treat the deny message as the
    answer and carry on - not apologise and give up."""
    ...
    assert done.outcome == base.OUTCOME_SUCCESS
    assert answer_text_influenced_the_output


async def test_the_tier_override_reaches_the_model(probe_workspace):
    """Phase 5 shipped a mix meter. This is the only test that proves the
    numbers on it are real."""
    ...
    assert "haiku" in done.model_usage
```

- [ ] **Step 2: Confirm they are deselected by default**

```bash
python -m pytest packages/implr_studio -q          # live tests NOT run
python -m pytest packages/implr_studio -m live -q  # opt in, spends money
```

- [ ] **Step 3: Commit**

```bash
git commit -m "test(executor): opt-in live suite"
```

---

### Task 6: `--fake` becomes the opt-in

**Files:**
- Modify: `packages/implr_studio/cli.py`
- Test: `packages/implr_studio/tests/test_cli_executor_choice.py`

- [ ] **Step 1: Write the failing test**

```python
def test_the_default_executor_is_real():
    assert type(build_executor(parse([])).__class__.__name__) or True
    assert isinstance(build_executor(parse([])), ClaudeCodeExecutor)


def test_fake_selects_the_fake():
    assert isinstance(build_executor(parse(["--fake"])), FakeExecutor)


def test_the_real_executor_without_the_sdk_fails_at_startup_with_advice():
    """Not at the first Run press, twenty minutes into a demo."""
    with pytest.raises(SystemExit, match="pip install"):
        build_executor(parse([]), sdk_available=False)


def test_the_banner_says_which_executor_is_live():
    """One line, at startup. 'Why did nothing cost anything' and 'why did
    that cost something' are both answered by it."""
    assert "fake" in banner(parse(["--fake"])).lower()
    assert "fake" not in banner(parse([])).lower()
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 7: Run the demo

- [ ] **Step 1: Task 0 first**

If you skipped Task 0, do it now. Nothing below is meaningful until a slash command invokes a
skill.

- [ ] **Step 2: Free assertions**

```bash
python -m pytest packages/implr_studio -q     # includes the shadow-warning test
```

The shadow-warning test passing is the single most valuable line in this phase.

- [ ] **Step 3: The real run**

```bash
implr-studio --workspace $PROBE
```

Run `doc-ingest --dry-run`. Log lines stream **progressively**. Step `succeeded`. A **cost** is
shown. `git status` in the probe workspace: **clean**.

- [ ] **Step 4: The question round trip**

Run a step that asks. The card renders the agent's own options. Answer. The agent **continues** —
and `stub_client.connects`'s live equivalent is that the log does not restart from the top.

- [ ] **Step 5: Nothing in the UI changed**

```bash
git diff --stat HEAD~7 -- web/
```

The only permitted changes are the executor banner and, if needed, cost display. If a component
changed shape, the contract leaked and that is worth fixing before moving on.

- [ ] **Step 6: The failure paths, for real**

Set `max_budget_usd` to $0.01 and run. The step fails saying **budget**, not with a stack trace.
Then Abort a live run mid-step and confirm the CLI subprocess is gone (`ps`), not orphaned.

---

## Definition of Done

- [ ] **Task 0 passed before anything else was written.**
- [ ] `python -m pytest` passes with live tests deselected by default.
- [ ] **No `CanUseToolShadowedWarning` for our options**, asserted offline.
- [ ] `options.skills` is a **list**, never `"all"`.
- [ ] `AskUserQuestion` is absent from `allowed_tools`.
- [ ] No `allowed_tools` entry is a whole-tool allow (`X`, `X()`, `X(*)`).
- [ ] `permission_mode == "acceptEdits"` and never `bypassPermissions`.
- [ ] `_sdk.PERMITTED_TOOLS is registry.PERMITTED_TOOLS`.
- [ ] `translate.py` contains no `claude_agent_sdk` import, asserted by source test.
- [ ] An unknown message type yields no events rather than raising.
- [ ] A missing cost is `None`, not `0`.
- [ ] Budget-stop and turn-cap failures say which one happened.
- [ ] Agent prompts come from `.claude/agents/*.md`; only the model is overridden; all eleven load.
- [ ] An agent with no file is **skipped and logged**, never stubbed.
- [ ] A tool grant outside the permitted set raises at run time as well as at write time.
- [ ] `maxTurns` uses the SDK's camelCase field.
- [ ] `ClaudeCodeExecutor` passes **Phase 9's shared executor contract suite**.
- [ ] `aclose()` disconnects the client — Phase 14's Abort does not orphan a subprocess.
- [ ] No event ever contains the API key; a process error does not leak the argv.
- [ ] `--fake` is opt-in; a missing SDK fails at **startup** with `pip install` advice.
- [ ] **Live:** a slash command invokes the skill; `--dry-run` leaves the workspace clean; a real
      question reaches the operator; the agent continues after the answer; the tier override is
      visible in `model_usage`.
- [ ] `git diff --stat -- web/` shows essentially nothing.

---

## Known limitations, kept

**`skills=` is not isolation.** The SDK is explicit: unlisted skills are hidden from the listing
and rejected by the Skill tool, *and their files remain readable via Read and Bash*. In local
mode that is fine — it is your own workspace. In hosted mode it means **materialisation** is the
security boundary, not the `skills` list. Phase 16 must not weaken that into a filter.

**No session resumption.** A crash loses the agent's context and Phase 14 fails the node.
`ClaudeAgentOptions.resume` plus a persisted `session_id` per node-run would fix it, and it is the
single highest-value follow-up in this document.

**Cost is per step, not per node attempt aggregated.** `ResultMessage.total_cost_usd` is recorded
on the done event. Summing it correctly across retries, skips and request-changes rounds is a
reporting job that belongs with the hosted control plane.

**One provider.** The Protocol makes a second adapter possible and none exists. That is the
correct amount of abstraction: a seam, not a plugin system.

---

## What the next phase gets

A working product, locally. **Phase 16** puts it in containers — and inherits one hard
requirement from this phase: the API image must **not** contain the Claude CLI or git, because the
adapter needs both and the API must never execute a step. The two-image split in
`docker/api.Dockerfile` and `docker/worker.Dockerfile` exists precisely because this phase gave
the worker teeth.
