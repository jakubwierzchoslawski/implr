# Design Spec: implr Studio — Visual SDLC Pipeline Builder & Orchestrator

**Date:** 2026-08-25
**Status:** Draft — awaiting review
**Author:** jakubwierzchoslawski

---

## Problem

implr's skills (`doc-ingest`, `arch-gen`, `ba-requirements-gen`, `dev-planner`,
`dev-executor`, `dev-code-review`, `ba-cr`) each work well in isolation, but there is no
orchestrator. Today the operator must:

1. Know the correct order to invoke skills in.
2. Know the implicit preconditions between them (a requirement must reach `approved`
   before `dev-planner` will plan it; a plan must be `ready` before `dev-executor` will
   execute it).
3. Invoke each skill by hand as a slash command, watch it finish, inspect artefact
   frontmatter to confirm the next step's gate is satisfied, then invoke the next one.

The ordering exists only as convention in prose and in each skill's own precondition
checks. It is neither declared anywhere machine-readable nor visible as a whole. A new
operator cannot see the process; an experienced one repeats the same manual sequencing on
every project.

Additionally, the desired process includes steps that do not exist as skills yet
(dedicated testing and security-check steps). Any orchestrator must accommodate steps
added later without code changes.

---

## Solution Overview

**implr Studio** — a locally hosted web application, added as a new top-level `studio/`
directory in this repository, providing:

1. A **drag-and-drop canvas** where the operator composes an SDLC pipeline from available
   implr steps and connects them into a directed acyclic graph.
2. A **declarative pipeline config** (`docs/implr/config/pipeline.yaml`) saved into the
   target project — the machine-readable statement of the process that does not exist
   today.
3. An **orchestrator service** that executes that pipeline: invoking each step, evaluating
   gates against artefact frontmatter, pausing for human approval, proxying a step's
   interactive questions to the browser, and persisting run state so runs survive a
   restart.
4. A **provider-neutral `StepExecutor` interface** with exactly one implementation in this
   phase (Claude Code), so additional LLM providers can be added later without reworking
   the orchestrator.
5. A **per-step configurator** — a modal, opened from any node, that selects the step's
   arguments (including flags that take a value), the **model tier for each subagent that
   step dispatches**, and shows the step's input sources and output artefact contract.
6. A **shipped design system** (`studio/frontend/src/tokens.css`) — dark-first, with the
   saturated palette reserved exclusively for run state and model tier, so colour in this
   UI is always data.

---

## Scope

This spec covers **Phase 1 only**. Phase 2 is explicitly deferred and specified separately.

### In scope (Phase 1)

- Step registry (declarative catalogue of available steps).
- Pipeline config format and its validation.
- Visual builder frontend (design mode + run mode).
- Orchestrator backend: run lifecycle, gate evaluation, persistence, streaming.
- Generic `StepExecutor` interface.
- One adapter: Claude Code, via the `claude-agent-sdk` Python package.
- Interactive-step proxying: a step's questions surface in the browser; answers are sent
  back into the running step.

### Out of scope (Phase 2, deferred)

- Auditing and rewriting existing skill instructions to remove Claude-Code-specific
  conventions and tool names.
- A second provider adapter.
- Structured (multiple-choice) rendering of skill questions — see *Known Limitations*.
- Multiple concurrent workspaces per service instance.
- Any authentication, multi-user support, or remote hosting.

### Explicitly not built

- New implr skills for testing or security checks. Those are registry entries pointing at
  skills that do not exist yet; the builder renders them as unavailable until the
  corresponding `skills/<name>/SKILL.md` exists.

---

## Approach Selected

**Python backend (FastAPI) + React frontend (Vite + React Flow).**

The decisive factor is gate evaluation. Gates are questions about artefact frontmatter
("are all requirements `approved`?"). `scripts/implr_validate` already parses that
frontmatter and already loads the authoritative state machines from
`scaffold/schemas/status-vocabulary.json` and `scaffold/schemas/frontmatter-rules.json`.
A Python backend imports and reuses that code directly. Any other stack would reimplement
it, creating a second source of truth for artefact status semantics — exactly what
`status-vocabulary.json`'s own header forbids.

React Flow is used for the canvas because node/edge graph editing with pan, zoom,
selection, and connection handles is its purpose; hand-rolling it is weeks of work with a
worse result.

### Approaches rejected

- **All-TypeScript (Node + React).** One language across the stack and simpler for a
  single maintainer, but it duplicates the frontmatter and state-machine parsing in
  JavaScript, creating a second source of truth. Rejected on that basis alone.
- **Electron desktop app.** Native filesystem and process access, but a localhost backend
  already grants the browser everything it needs. Adds packaging and update complexity for
  no capability gain.

---

## Architecture

```
implr repo
├── scaffold/schemas/
│   ├── status-vocabulary.json     (existing — authoritative state machines)
│   ├── frontmatter-rules.json     (existing — artefact types, path globs)
│   └── step-registry.json         (NEW — catalogue of pipeline steps)
├── scripts/implr_validate/        (existing — imported by the backend)
└── studio/                        (NEW)
    ├── backend/
    │   ├── registry.py            loads + validates step-registry.json
    │   ├── pipeline.py            pipeline.yaml load/save, DAG validation
    │   ├── gates.py               gate evaluation via implr_validate
    │   ├── orchestrator.py        run lifecycle, scheduling, pause/resume
    │   ├── store.py               SQLite persistence
    │   ├── api.py                 FastAPI routes + WebSocket
    │   └── executors/
    │       ├── base.py            StepExecutor Protocol, StepEvent types
    │       ├── claude_code.py     the one adapter
    │       └── fake.py            scripted executor for tests
    └── frontend/                  Vite + React + React Flow

target project (operated on)
└── docs/implr/config/pipeline.yaml   (NEW — written by the builder)
```

The backend operates on **one target project per service instance**, given at startup
(`--workspace <path>`, defaulting to the current directory). Multi-workspace support is
deferred.

---

## Component: Step Registry

**File:** `scaffold/schemas/step-registry.json` (installed to the target project alongside
the other schemas, consistent with how `implr_validate` resolves its schema directory).

The registry is the catalogue of what can be dragged onto the canvas. It exists so that
adding a future step requires **only a registry entry**, never a code change in the
builder, backend, or frontend.

```json
{
  "steps": [
    {
      "id": "doc-ingest",
      "label": "Document Ingestion",
      "phase": "discovery",
      "skill": "doc-ingest",
      "args_allowed": [
        { "flag": "--registry-only", "takes_value": false, "note": "fast scan, no digesting" },
        { "flag": "--file", "takes_value": true, "value_pattern": "^[A-Za-z0-9._/-]{1,200}$",
          "note": "one document only" },
        { "flag": "--rebuild", "takes_value": false, "note": "ignore the incremental cache" },
        { "flag": "--dry-run", "takes_value": false, "note": "report, write nothing" }
      ],
      "args_default": [],
      "interactive": false,
      "agents": [
        { "name": "doc-ingest-digester", "fan_out": "1 per changed doc" },
        { "name": "doc-ingest-synthesizer", "fan_out": "1 per domain" }
      ],
      "consumes": [
        { "path": "docs/kb/**", "note": "18 formats" },
        { "path": "docs/implr/kb-index/registry.md", "note": "incremental state" }
      ],
      "produces": [
        { "path": "docs/implr/kb-index/digests/per-doc/*.md" },
        { "path": "docs/implr/kb-index/master-synthesis.md" }
      ],
      "produces_artefact": null,
      "description": "Indexes and digests the knowledge base under docs/kb/."
    },
    {
      "id": "dev-planner",
      "label": "Specification / Planning",
      "phase": "planning",
      "skill": "dev-planner",
      "args_allowed": [
        { "flag": "--all", "takes_value": false, "note": "every approved requirement" },
        { "flag": "--brainstorm", "takes_value": false, "note": "ask before planning" }
      ],
      "args_default": ["--all"],
      "interactive": true,
      "agents": [{ "name": "plan-worker", "fan_out": "1 per requirement" }],
      "consumes": [{ "path": "docs/implr/requirements/**", "note": "status: approved" }],
      "produces": [],
      "produces_artefact": "plan",
      "description": "Creates implementation plans from approved requirements."
    }
  ]
}
```

### Field semantics

| Field | Meaning |
|---|---|
| `id` | Registry key referenced by `pipeline.yaml` nodes. |
| `label` | Display name in the palette and on the canvas node. |
| `phase` | Palette grouping only (`discovery`, `design`, `requirements`, `planning`, `build`, `verify`). No execution meaning. |
| `skill` | The implr skill name. Must correspond to `skills/<skill>/SKILL.md`. |
| `args_allowed` | Array of **arg specs**, not bare strings. Each has `flag`, `takes_value`, an optional `value_pattern` (required when `takes_value` is true) and an optional `note` shown in the configurator. A pipeline naming a flag outside this list, or supplying a value that fails the pattern, fails validation. |
| `args_default` | Flags (bare strings) applied when the node is first dropped onto the canvas. Every entry must name an `args_allowed` flag whose `takes_value` is false. |
| `interactive` | Whether the step is expected to ask the operator questions mid-run. Drives UI affordances only; the proxy channel is always available. |
| `agents` | The subagents this step dispatches, in dispatch order. `name` must be a key in `implr.config.yaml`'s `agents:` block; `fan_out` is descriptive text shown in the configurator. Drives the model-tier selector and the model-mix meter. |
| `consumes` | What the step reads. `{path, note}`. **Descriptive** — see *Known Limitations*. |
| `produces` | Files the step writes. `{path, note}`. Descriptive. |
| `produces_artefact` | The `frontmatter-rules.json` artefact type this step produces, or `null`. When set, the configurator's Output tab renders that type's required fields and legal statuses — the same vocabulary a downstream gate reads. |
| `description` | Plain-language summary. Shown as the configurator's lead paragraph and the palette tooltip. |

### Registry, pipeline, config: three files, three owners

The single most important thing to hold about the registry is what it is *not*. It is a
**vocabulary**, not a process. Three files divide the work:

| File | Answers | Owner | Changes when |
|---|---|---|---|
| `scaffold/schemas/step-registry.json` | *What steps exist, and what can I configure on each?* | implr (plugin) | a new skill ships |
| `docs/implr/config/steps.yaml` | *What steps has this project added?* | the project | you author one |
| `docs/implr/config/pipeline.yaml` | *Which steps did I pick, how are they connected, what did I set?* | the project | you design |
| `docs/implr/config/implr.config.yaml` → `agents:` | *Which model tier does each subagent run on?* | the project | you tune cost |

A node says `step: doc-ingest` — a *reference* into the catalogue, never a copy of it. So a
step gaining a new flag reaches every existing pipeline's configurator without touching a
single `pipeline.yaml`.

The registry also deliberately does **not** own three things it easily could have, each of
which lives somewhere that is already authoritative:

- **statuses** → `status-vocabulary.json`. A gate's legal values come from there.
- **artefact shape** → `frontmatter-rules.json`. `produces_artefact: "plan"` is a pointer into it.
- **model tiers** → `implr.config.yaml`. The registry names *which* agents a step dispatches; that file says what tier each runs at.

Copying any of those into the registry would have been easier and would have created a
second source of truth.

### Authoritative fields versus descriptive ones

Read as JSON, every field looks equally binding. It is not, and conflating the two groups is
the likeliest way to misread the format:

| Field | Status | What depends on it |
|---|---|---|
| `id`, `kind`, `skill` | **authoritative** | node references resolve through it; the adapter builds `/doc-ingest` from `skill` |
| `args_allowed` | **authoritative** | gates the configurator's controls *and* rejects a save |
| `agents[].name` | **authoritative** | validated against `.claude/agents/`; drives the tier selector |
| `produces_artefact` | **authoritative** | validated against `frontmatter-rules.json`; renders the Output contract |
| `phase` | display only | palette grouping. **No execution meaning whatsoever** |
| `interactive` | display only | a badge. The question channel is always live regardless |
| `consumes`, `produces` | **descriptive only** | rendered in Input/Output. Nothing validates them |
| `agents[].fan_out` | descriptive only | free prose (`"1 per plan, cap 5"`). Nothing computes concurrency from it |

Two of these are active confusion risks and are worth stating in the UI as well as here.
**`phase` looks like a sequence and is not** — the palette reads discovery → design → … →
verify, which invites the assumption that reordering it reorders a run. Execution order comes
only from edges. And **`consumes` / `produces` look enforced and are not** — a per-skill input
contract does not exist, so those fields are documentation that happens to live in a schema.

### Two kinds of step

`kind` is the field that decides who owns a step's behaviour, and the two answers have very
different configurability:

| | `kind: "skill"` | `kind: "agent"` |
|---|---|---|
| What runs | `/doc-ingest --dry-run` as a slash command | a prompt the studio composes from `instruction` |
| Who owns the behaviour | the `SKILL.md` | the operator, in the UI |
| Configure arguments | ✅ from `args_allowed` | ✗ — see below |
| Configure *which* agents | ✗ **the skill decides** | ✅ |
| Configure an agent's prompt / tool grant | ✗ | ✅ |
| Configure model tier | ✅ | ✅ |
| Declared in | the plugin registry, or `steps.yaml` | `steps.yaml` only |
| Availability | needs `.claude/skills/<skill>/SKILL.md` | always available |

The asymmetry in the middle rows is a hard architectural boundary, not an unfinished
feature. `doc-ingest` dispatches `doc-ingest-digester` and `doc-ingest-synthesizer` because
that is written in its SKILL.md prose; the studio sends a slash command and the skill decides
the rest. The registry's `agents[]` array for a skill-backed step is therefore **describing**
what the skill does, so the tier selector has something real to attach to — it is not
configuring it. The Agents tab renders read-only for `kind: "skill"` apart from the tier.

For `kind: "agent"` the studio owns the whole invocation, so everything is configurable.
Each entry maps onto a real `ClaudeAgentOptions` field — `instruction` becomes the prompt,
`agents[]` becomes the `agents` dict of `AgentDefinition`, and each one's `prompt`, `tools`,
`model` and `max_turns` are that dataclass's own fields. Nothing is shimmed.

**An agent-backed step takes no arguments.** Interpolating an operator-supplied value into a
prompt is prompt injection by construction, and appending flags as literal text would offer
a control the agent may silently ignore. If you need a variant, author two steps.

### Project-owned steps

`docs/implr/config/steps.yaml` is a **project-scoped registry** — the same schema as the
plugin file, plus `kind` and the agent-backed fields. It exists for two reasons.

The first is the one you would expect: authoring a step from the UI has to write somewhere.

The second is a bug it fixes. `install.sh` copies `schemas/*.json` under a comment reading
*"Always overwrite: schemas and templates (plugin-owned)"*. So a project that hand-edited its
installed `step-registry.json` silently loses the change on the next install — meaning
**there was no way for a project to have a step implr does not ship**. `steps.yaml` is never
touched by the installer.

Entries are merged over the plugin registry **by `id`, and a collision is an error**, with a
message telling you to pick a different id. Overriding a shipped step would be occasionally
useful and permanently confusing; retuning `dev-executor`'s arguments is plugin territory.

An authored step:

```yaml
# docs/implr/config/steps.yaml - project-owned, never overwritten by the installer
version: 1
steps:
  - id: lint-and-format
    kind: agent
    label: Lint & Format
    phase: verify
    instruction: |
      Run the project's linter and formatter. Fix what is auto-fixable.
      Report anything needing a human decision. Do not change program logic.
    agents:
      - name: linter
        model: haiku
        tools: [Read, Edit, Bash]
        max_turns: 12
        prompt: |
          You run linters and formatters. You never change program logic.
    consumes: [{ path: "src/**" }]
    produces: [{ path: "src/**", note: "formatting only" }]
    produces_artefact: null

  # kind: skill also works here - this is how a node points at an installed
  # skill the plugin registry does not declare. You author its arg specs too.
  - id: custom-migrations
    kind: skill
    label: Run Migrations
    phase: build
    skill: db-migrate
    args_allowed:
      - { flag: "--dry-run", takes_value: false, note: "plan only" }
    args_default: []
    agents: []
    consumes: []
    produces: []
    produces_artefact: null
```

**An authored step may not grant itself tools the adapter would deny.** Every `tools` entry
must be a member of the adapter's permitted set, checked at save time. Otherwise the
authoring surface becomes a way around the permission posture.

### Agent-backed steps are deliberately second-class

A UI that authors agent prompts is a UI that authors prompts — with no TDD enforcement, no
review gate, and no iteration history. implr's actual value is that `task-executor`'s prose
has been refined to enforce TDD and SOLID, and `dev-code-review`'s to audit against
acceptance criteria. A hand-typed step bypasses every bit of that.

So agent-backed steps are excellent for glue — `lint-and-format`, `generate-diagram`,
`post-summary`, `run-migrations` — and the wrong tool for *"write the implementation"*. The
canvas marks them distinctly so nobody mistakes a five-minute prompt for a hardened skill,
and a custom step that turns out to be load-bearing should graduate into a real `SKILL.md`.

### Why model tier is per agent, not per step

`docs/implr/config/implr.config.yaml` already ships an `agents:` block mapping each implr
subagent to `haiku | sonnet | opus`. That block is the existing, authoritative place model
choice lives. The configurator therefore edits **it**, and the registry's `agents` array
exists only to tell the UI which of those keys are relevant to a given step. Inventing a
per-step `model` field would create a second source of truth for the same decision — the
mistake `status-vocabulary.json`'s own header forbids for statuses, applied to models.

A consequence worth stating: two nodes running the same step share the project-level
default, but a node may override any of its agents' tiers locally (see `models` in the
pipeline config below). The override lives on the node, so the same step can run cheap in
one branch and expensive in another.

### Availability

A `kind: "skill"` entry whose skill is not installed is **not an error**. It renders in the
palette as unavailable — dashed, non-draggable — with a tooltip explaining the skill is not
implemented yet. This is how planned steps (a dedicated testing step, a dedicated
security-check step) appear in the process diagram before they exist. A `kind: "agent"` step
is always available; there is no skill for it to be missing.

**Availability is resolved against `<workspace>/.claude/skills/<skill>/SKILL.md`** — the
target project's installed skills, not the implr repo's `skills/` source tree. This matters:
the adapter runs with `cwd=<workspace>`, so that is where the CLI resolves a slash command
from. Judging availability against the plugin source instead would let the palette report a
step as usable while the agent cannot find it — which is exactly what happens when the studio
backend runs from a different implr checkout than the one the project was installed from.

The same directory is what step **discovery** reads, so the authoring UI can offer every
installed skill rather than only the ones the plugin registry declares.

A pipeline that *references* an unavailable step fails validation at run start, not at
save time. Designing ahead of implementation is permitted; executing a non-existent skill
is not.

Note the distinction from DAG validation below: a node naming a `step` that is **not in the
registry at all** is rejected at save time, because it is a typo. A node naming a
registered-but-unimplemented step is accepted at save time and rejected at run start,
because it is a plan.

### Validation

`implr-validate --repo` gains a check: every registry entry's `phase` is one of the known
phases, every `id` is unique, and every entry either has a real `skills/<skill>/SKILL.md`
or is reported as an informational (non-failing) "planned step" finding.

---

## Component: Pipeline Config

**File:** `docs/implr/config/pipeline.yaml` in the target project.

```yaml
version: 1

nodes:
  - id: ingest
    step: doc-ingest
    args: ["--digest"]
    position: { x: 80, y: 120 }

  - id: arch
    step: arch-gen
    args: []
    position: { x: 320, y: 120 }

  - id: reqs
    step: ba-requirements-gen
    args: []
    position: { x: 560, y: 120 }

  - id: plan
    step: dev-planner
    args: []
    position: { x: 800, y: 120 }

  - id: build
    step: dev-executor
    args: ["--all", "--task"]
    # values for flags whose arg spec has takes_value: true
    arg_values:
      "--task": "PLAN-F-004#3"
    # per-agent model overrides; absent agents inherit implr.config.yaml
    models:
      task-executor: sonnet
    position: { x: 1040, y: 120 }

  - id: review
    step: dev-code-review
    args: []
    position: { x: 1280, y: 120 }

edges:
  - { from: ingest, to: arch,  gate: { type: none } }
  - { from: arch,   to: reqs,  gate: { type: none } }

  - from: reqs
    to: plan
    gate:
      type: artifact+manual
      artefact: requirement
      quantifier: all
      require: { status: approved }

  - from: plan
    to: build
    gate:
      type: artifact
      artefact: plan
      quantifier: any
      require: { status: ready }

  - { from: build, to: review, gate: { type: none } }
```

`position` is builder-owned layout state. The orchestrator ignores it.

`arg_values` and `models` are both optional and both sparse. An absent `arg_values` entry
for a value-taking flag is a validation error; an absent `models` entry simply means
"inherit the project default", which is what every pipeline written before this field
existed does. Existing `pipeline.yaml` files therefore stay valid.

### DAG validation (at save time)

The config is rejected with an actionable error if:

- Any `node.step` is not a registry `id`.
- Any `node.args` entry does not name a flag in that step's `args_allowed`.
- Any `node.args` flag whose spec has `takes_value: true` has no `arg_values` entry.
- Any `arg_values` value fails its arg spec's `value_pattern`.
- Any `arg_values` key is not a selected flag in `node.args`.
- Any `models` key is not one of that step's registry `agents`.
- Any `models` value is outside `haiku | sonnet | opus`.
- Node `id`s are not unique.
- Any edge references an unknown node `id`.
- The graph contains a cycle.
- Any node is unreachable from a root node (a node with no inbound edges).
- The graph has no root node.

The value rules exist because several implr flags genuinely take an argument —
`doc-ingest --file <path>`, `dev-executor --task <id>`, `ba-requirements-gen --domain
<name>`, `ba-cr --file <path>`. A flat flag whitelist makes those flags selectable and
inert, which is worse than not offering them.

**Values are never interpolated into a shell string.** They are validated against
`value_pattern` and then passed as separate argv elements, so a value containing shell
metacharacters is inert as well as pattern-rejected.

Validation runs in the backend, not the frontend, so the same rules apply whether the file
was written by the builder or edited by hand.

---

## Component: Gates

A gate is the condition on an edge that must hold before the downstream node may run. The
gate language is deliberately minimal — a fixed shape, not a general expression evaluator —
because every construct it admits is a construct the builder UI must render and validate.

### Gate types

| `type` | Behaviour |
|---|---|
| `none` | The downstream node becomes eligible as soon as the upstream node succeeds. |
| `manual` | The run pauses; the operator clicks **Approve** in the UI to release the edge. |
| `artifact` | The downstream node becomes eligible when the artefact condition evaluates true. |
| `artifact+manual` | Both: the artefact condition must hold **and** the operator must approve. |

### Artefact gate evaluation

```yaml
gate:
  type: artifact
  artefact: requirement       # key in frontmatter-rules.json -> artefact_types
  quantifier: all             # all | any
  require: { status: approved }
```

Evaluation algorithm:

1. Look up `artefact` in `frontmatter-rules.json` → `artefact_types[artefact]`.
2. Glob the target project using that type's `path_globs`.
3. Parse each matched file's frontmatter with `implr_validate.frontmatter.parse_frontmatter`.
4. Test each parsed frontmatter against every key/value in `require`.
5. Apply `quantifier`: `all` — every matched file passes; `any` — at least one passes.

**Empty match set:** if the glob matches no files, `all` evaluates **false**, not
vacuously true. A gate demanding approved requirements must not open when no requirements
exist. This is stated explicitly because the vacuous-truth reading is the natural one and
it is wrong here.

### Gate validation (at save time)

- `artefact` must be a key in `frontmatter_rules.artefact_types`.
- Every key in `require` must be a field that artefact type declares (in `required` or
  `optional`).
- If `require` constrains `status`, the value must be a member of that artefact's state
  machine in `status-vocabulary.json`.

This last check is the concrete payoff of the Python backend: a gate demanding
`status: complete` on a plan is rejected at save time, because the plan machine's states
are `ready | in-progress | done | blocked | needs-rework`. The operator learns this while
designing, not three steps into a run.

---

## Component: StepExecutor Interface

The provider-neutral contract. Nothing Claude-specific crosses this boundary; that is the
entire mechanism by which Phase 2 stays possible.

```python
# studio/backend/executors/base.py

@dataclass(frozen=True)
class StepRequest:
    node_id: str
    skill: str                 # e.g. "dev-executor"
    args: list[str]            # e.g. ["--all"]
    workspace: Path
    timeout_seconds: int | None

@dataclass(frozen=True)
class StepEvent:
    kind: Literal["log", "question", "artifact", "done"]
    payload: dict

class StepExecutor(Protocol):
    async def start(self, req: StepRequest) -> StepHandle: ...
    def events(self, h: StepHandle) -> AsyncIterator[StepEvent]: ...
    async def answer(self, h: StepHandle, question_id: str, text: str) -> None: ...
    async def cancel(self, h: StepHandle) -> None: ...
```

### Event payloads

| `kind` | Payload |
|---|---|
| `log` | `{ text: str }` — streamed output for the node's log pane. |
| `question` | `{ question_id: str, prompt_md: str, options: list[str] \| None }` — the step wants operator input. `options` is always `None` in Phase 1 (see *Known Limitations*). |
| `artifact` | `{ path: str }` — best-effort notice that a file was written. Advisory only; gates read the filesystem, never this event. |
| `done` | `{ outcome: "success" \| "failure", summary: str, error: str \| None }` |

`StepRequest` carries `skill` and `args` as **data**, not as a formatted command line. The
adapter decides what they mean. The Claude adapter renders them as the slash command
`/dev-executor --all`. A future adapter could instead load `skills/dev-executor/SKILL.md`
as a system prompt into its own tool-calling loop. Neither choice leaks into the
orchestrator.

---

## Component: Claude Code Adapter

The one Phase 1 implementation, in `studio/backend/executors/claude_code.py`.

It drives Claude Code through the **`claude-agent-sdk` Python package** (`ClaudeSDKClient`),
not a raw subprocess, and translates between the SDK's message stream and `StepEvent`:

| SDK message | Mapped to |
|---|---|
| Assistant text content block | `log` |
| Tool-use / tool-result activity | `log` (condensed to one line per tool call) |
| `AskUserQuestion` intercepted in `can_use_tool` | `question` — carries the agent's own options |
| `ResultMessage` | `done` |
| SDK error / non-zero termination | `done` with `outcome: "failure"` |

**How a question is detected.** This is the part of the design that had to change once the
protocol was checked against the documentation rather than assumed.

An earlier draft of this spec claimed that a turn ending without a terminal result was a
protocol-level signal meaning "input wanted." **That is not documented and must not be
relied on.** The docs do not state whether a `result` message ends every turn or only the
session, and they define no signal distinguishing "the agent is asking" from "the agent
finished." Bidirectional `stream-json` on stdin is likewise an SDK capability, not a
documented CLI flag.

The mechanism used instead is structural. The adapter appends a short instruction to the
prompt it sends — *when you need a decision from the operator, ask via the
`AskUserQuestion` tool* — and registers a `can_use_tool` callback. When the agent calls
that tool, the callback intercepts it, emits a `question` event carrying the agent's own
options, and blocks until `answer()` supplies a reply, which is returned as the tool
result. The agent then continues **in the same session** with its context intact.

Two consequences worth noting. First, detection is a tool-call interception rather than
text parsing, so it does not depend on how any individual skill phrases itself. Second,
because the agent supplies real options, the UI can render actual choices rather than a
free-text box — the `options` field on the `question` event stops being unused. Neither
requires editing a single existing skill file.

If the agent answers in prose without calling the tool, the step simply runs to completion
without asking; the adapter does not guess. That is a deliberate failure mode: a missed
question surfaces as a step that finished with an unexpected result, which the operator can
see, rather than as a run that hangs on a heuristic that misfired.

**Permissions.** The adapter runs with `permission_mode="acceptEdits"`.
`bypassPermissions` is deliberately not used: this agent is driven by a web page, and
unrestricted shell access on that path is not a default anyone should inherit without
choosing it. (The SDK also refuses to consult `can_use_tool` at all under
`bypassPermissions`, so using it would silently disable question proxying.)

Three details about the allowlist are load-bearing, and all three were verified against
`claude-agent-sdk` 0.2.144 rather than assumed:

1. **`AskUserQuestion` must NOT appear in `allowed_tools`.** An `allowed_tools` entry that
   names a whole tool auto-approves it *before* `can_use_tool` is consulted — the SDK ships
   a warning helper that says exactly this. Allowlisting the tool the adapter exists to
   intercept would defeat the entire question-proxying mechanism, silently. The tool is
   left out so its calls fall through to the callback.
2. **Deny is the default for anything unrecognised.** `can_use_tool` returns
   `PermissionResultDeny` for any tool outside the known-good set, with a message naming
   the tool, and the denial is emitted as a `log` event so it appears in the node's output.
   Returning `allow` for everything not intercepted — the obvious implementation — would
   make the allowlist decorative.
3. **Skills are enabled through `skills`, not `allowed_tools`.** implr installs its skills
   to `<project>/.claude/skills/<name>/SKILL.md`, and the SDK gates the `Skill` tool behind
   the `skills` option, which "configures everything needed (including allowing the `Skill`
   tool)". Passing `"Skill"` in `allowed_tools` is deprecated. The adapter passes
   `skills="all"`, without which no implr step can be invoked at all.

The tool set also includes **`Agent`** alongside `Task`: implr's own subagent definitions
declare `tools: [..., Agent]`, and `doc-ingest`, `ba-requirements-gen`, `dev-planner`,
`dev-executor` and `dev-code-review` all depend on subagent dispatch.

**Model selection.** `ClaudeAgentOptions` accepts an `agents` dict of `AgentDefinition`,
each carrying its own `model`. The node's `models` overrides map directly onto those
fields — the adapter does not shim, re-prompt, or pass a model name in the prompt text.
Agents the node does not override are omitted, so they resolve to the project default from
`implr.config.yaml`.

---

## Component: Orchestrator & Run Lifecycle

### Node run states

```
pending ──> blocked ──> running ──> succeeded
              │           │  ↑
              │           │  └────── awaiting-input   (question asked, answer sent)
              │           │
              │           ├────────> failed ──> running   (operator: retry)
              │           │              └─────> skipped  (operator: skip)
              │           └────────> cancelled
              │
              └────────> awaiting-approval ──> running     (manual gate released)
```

| State | Meaning |
|---|---|
| `pending` | Not yet eligible; upstream not finished. |
| `blocked` | Upstream succeeded but a gate has not opened. |
| `running` | The executor is active. |
| `awaiting-input` | A `question` event arrived; waiting on the operator's answer. |
| `awaiting-approval` | A `manual` gate is waiting on the operator. |
| `succeeded` / `failed` / `skipped` / `cancelled` | Terminal. |

### Run states

`running | paused | succeeded | failed | cancelled`

### Scheduling

After each node reaches a terminal state, the orchestrator re-evaluates every node whose
inbound edges all originate from terminal-successful nodes, opens the gates that now
evaluate true, and starts every eligible node.

The scheduler is written to start every eligible node, but is bounded by a configurable
concurrency cap set to **1** in Phase 1 — implr steps write to shared artefact directories
and concurrent cross-step writes are unproven. In practice this means eligible nodes queue
and run one at a time; the graph may branch, but Phase 1 executes it serially. Raising the
cap is a config change, not a rewrite.

### Failure handling

A failed node sets the run to `paused` and leaves downstream nodes `pending`. The UI offers
**Retry node**, **Skip node**, or **Abort run**. Retry is safe because implr steps are
file-based and re-runnable; a step re-reads current artefact state on each invocation.
Skipping a node marks it `skipped` and treats its outbound edges as satisfiable, on the
operator's authority.

### Persistence

SQLite at `docs/implr/.studio/runs.db` in the target project. Tables: `runs`, `node_runs`,
`events`, `questions`. Every state transition and every log line is written before it is
broadcast, so a service restart mid-run recovers the full run state and the operator
resumes rather than restarting. A node that was `running` when the service died is
recovered as `failed` with an explanatory summary — the child process did not survive, and
claiming otherwise would be a lie about what happened.

---

## Component: HTTP & WebSocket API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/registry` | The step catalogue (each entry annotated `available: bool`), plus `contracts` — every artefact type's fields, legal statuses and path globs — plus `agents`, the `implr.config.yaml` tier defaults per subagent. One call populates the whole configurator, and the status vocabulary keeps exactly one source of truth. |
| `GET` | `/api/pipeline` | Current `pipeline.yaml`, parsed. |
| `PUT` | `/api/pipeline` | Validate and save. `422` with a list of findings on failure. |
| `POST` | `/api/runs` | Start a run of the saved pipeline. Returns `202` with `{run_id}` **immediately**, before the run advances. |
| `GET` | `/api/runs` | Run history. |
| `GET` | `/api/runs/{id}` | Full run state including per-node status. |
| `POST` | `/api/runs/{id}/answer` | Answer a pending question. |
| `POST` | `/api/runs/{id}/approve` | Release a manual gate. |
| `POST` | `/api/runs/{id}/nodes/{node}/retry` | Retry a failed node. |
| `POST` | `/api/runs/{id}/nodes/{node}/skip` | Skip a failed node. |
| `POST` | `/api/runs/{id}/cancel` | Cancel the run. |
| `WS` | `/api/runs/{id}/stream` | Live `StepEvent`s and state transitions. |

The WebSocket replays persisted events from a client-supplied cursor on connect, so a
browser refresh mid-run loses no output.

**Every mutating route returns as soon as the state change is persisted — it never waits
for the run to settle.** This is stated explicitly because the natural implementation is
the wrong one: awaiting quiescence inside `POST /api/runs` makes the response deterministic
and the tests simple, at the cost of holding one HTTP request open for the entire run. A
`dev-executor` node can run for twenty minutes; the browser would learn the `run_id` only
after the pipeline stopped, so it could not open the WebSocket until there was nothing
left to stream. Live output is the point of Run mode, and it is incompatible with a
blocking start.

Tests therefore poll `GET /api/runs/{id}` through a helper rather than relying on the route
to block. That helper is the only place test-only waiting logic lives.

---

## Component: Design System

Shipped as `studio/frontend/src/tokens.css` and imported before every other stylesheet.
It is a file, not a description, so "the design" cannot drift from the plan.

**Dark is the default, in every theme state.** The bare `:root` block carries the complete
dark palette. There is deliberately **no `prefers-color-scheme` query** — a viewer on a
light OS still gets the dark console. Light appears only when the document is explicitly
stamped `data-theme="light"`, which redefines the same token set. This is a product
decision, not an oversight: the console is an operations surface that sits open beside a
terminal.

**Colour is data.** The accent is achromatic — bone `#eceae4` for primary actions — with a
single cyan `#3ed8c9` for focus, selection and links. Every saturated hue in the palette is
reserved, and the reservation is the rule that keeps the UI readable:

| Token group | Meaning | Values |
|---|---|---|
| `--st-*` | Node run state | running, succeeded, failed, blocked, awaiting-input, awaiting-approval, skipped, pending |
| `--tier-*` | Model tier | haiku, sonnet, opus |
| `--gate` | Edge condition | one amber |
| `--bone`, `--cyan` | Brand / interaction | achromatic + one cyan |

No component may introduce a saturated colour outside those groups. A brand hue that
competed with `--st-failed` would make a failing node harder to spot, which is the one
thing this UI exists to show.

**Type.** Three faces, three roles, loaded from Google Fonts (the only host the artifact
CSP admits, and the only external request the built bundle makes):

- **Sora** — display: the product mark, headings, modal titles.
- **Manrope** — UI and body, down to 11px chrome. Chosen for legibility at small sizes.
- **JetBrains Mono** — the technical layer: flags, artefact ids, schema fields, model
  names, node ids, log output.

Each `font-family` declares a real fallback stack, so a blocked font request degrades
rather than silently reflowing.

---

## Component: Frontend

One canvas, two modes, and a modal configurator.

**Design mode.** A searchable palette on the left grouped by `phase`, with unimplemented
steps dashed and non-draggable. Drag onto the canvas to create a node; drag between ports
to create an edge. The right rail is **not** a form — it shows pipeline health: step and
gate counts, the validation findings, and a **model-mix meter** summing every node's agent
tiers, because model tier is the dominant cost driver and the operator should see it
without opening anything.

**The step configurator.** Clicking a node opens a modal with four tabs. This replaces the
first design's inline inspector, which could not hold this much without becoming a
scroll-trap.

| Tab | Contents |
|---|---|
| **Run** | The step's `description` as a lead paragraph, then its `args_allowed` as checkboxes — with a text input beside any flag whose `takes_value` is true, disabled until the flag is selected. Unimplemented steps show a banner explaining that the run will refuse to start them. Interactive steps show a banner explaining that their questions surface in Run mode. |
| **Agents** | One card per registry `agent`: its name, `fan_out`, its role, a **model-tier selector** (haiku / sonnet / opus) defaulting to the `implr.config.yaml` value and marked *overridden* when changed, and its declared tool grant with repository-mutating tools (`Write`, `Edit`, `Bash`, `Agent`) visually distinguished. |
| **Input** | The step's `consumes` paths, and its inbound edges' gates with a jump into the gate editor. Carries an explicit banner that this tab is descriptive. |
| **Output** | The step's `produces` paths, and — when `produces_artefact` is set — that artefact type's required fields and legal statuses, rendered from the contract files. Plus the outbound edges it feeds. |

The modal footer names the files an Apply will write: always `pipeline.yaml`, and
additionally `implr.config.yaml` when any model tier was overridden. Escape closes it; the
scrim closes it; focus moves into the dialog on open.

**The gate editor** is the same modal shell with one pane, opened by clicking an edge. Its
artefact and status dropdowns are populated from the schema files, so an invalid gate is
hard to express and refused by the backend if it is. It renders the chosen gate as a plain
sentence — *"Implementation starts once at least one plan is ready"* — beneath the
dropdowns, because `any plan status=ready` is precise but not friendly.

**Run mode.** The same graph, each node's stripe tinted by run state and its status named
in a badge beneath it. Gates show open (✓) or held (⋯). The right rail carries the selected
node's log, and its state's affordance: a question card with the agent's own options as
buttons plus a free-text box for `awaiting-input`, Approve for `awaiting-approval`,
Retry / Skip / Abort for `failed`, and for `blocked` an explanation that the gate advances
on its own and needs no action.

---

## Testing Strategy

The load-bearing decision is `FakeExecutor` — a `StepExecutor` implementation that replays
a scripted sequence of `StepEvent`s, including questions, failures, and timeouts. It lets
the orchestrator, gate evaluator, persistence layer, and WebSocket layer be tested
end-to-end with zero LLM invocations and zero token spend. Any orchestration behaviour that
cannot be tested through `FakeExecutor` is a design smell.

**Backend (pytest):**

- Registry: loading, uniqueness, availability detection against a fixture `skills/` tree.
- Pipeline: DAG validation — each rejection rule above gets a test asserting the specific
  error, including cycle detection and the unreachable-node case.
- Gates: evaluation against fixture project trees with real frontmatter, covering `all`
  and `any`, mixed-status sets, and the **empty match set returns false** case.
- Gate validation: an unknown artefact type, an unknown field, and a status outside the
  state machine are each rejected at save time.
- Orchestrator: state-machine transitions, concurrent-branch scheduling, failure pausing
  the run, retry, skip, and resume-after-restart (recovering a `running` node as `failed`).
- Adapter: the SDK-message → `StepEvent` mapping is tested against fake message objects,
  with no SDK installed and no subprocess. `AskUserQuestion` interception, deny-by-default
  for unrecognised tools, and the model-override → `AgentDefinition` mapping each get
  explicit coverage.
- Arg values: a missing value for a `takes_value` flag, a value failing `value_pattern`,
  and a value containing shell metacharacters are each rejected at save time.
- Model overrides: an unknown agent name and an illegal tier are each rejected at save time.

**Frontend (Vitest + React Testing Library):**

- Palette-to-canvas drop reducer.
- Pipeline serialization round-trip: load YAML → edit → save → byte-comparable structure,
  including `arg_values` and `models`.
- Run-mode rendering per node state, including the question and approval affordances.
- The step configurator: each tab renders from registry data alone; a value input is
  disabled until its flag is selected; changing a tier marks the agent overridden and
  updates the footer's file list; Escape closes the modal.
- A `tokens.css` guard test asserting no component stylesheet declares a saturated colour
  outside the reserved `--st-*` / `--tier-*` / `--gate` groups. This is the one design rule
  worth enforcing mechanically, because violating it degrades the UI's only real job.

**Live tests:** one opt-in suite marked `@pytest.mark.live`, skipped by default, exercising
the real Claude adapter against a throwaway fixture project. Never part of the default run.

---

## Security Constraints

This service executes an LLM agent that writes files and runs shell commands in the target
repository. Accordingly:

- The backend binds `127.0.0.1` only. Binding any other interface is not a configuration
  option.
- No authentication is implemented, because the service must never be reachable by anyone
  but the local operator. This is a constraint on deployment, not a gap to fill later.
- The `workspace` path is fixed at service startup. No API route accepts a path from the
  client, so no request can direct execution at another directory.
- `args` are validated against the registry's `args_allowed` whitelist before reaching the
  adapter, and are passed as an argument vector — never interpolated into a shell string.

---

## Known Limitations

**Question detection depends on the agent honouring an instruction.** implr's interactive
skills ask in plain prose — `arch-gen` Phase 3 presents each decision as formatted text,
`dev-planner` Phase 3 batches open questions as a prose block. The adapter instructs the
agent to route such moments through the `AskUserQuestion` tool instead, which is reliable
in practice but is an instruction, not a guarantee. A step that asks in prose anyway will
run to completion without pausing rather than hang. Editing those two skills to call the
tool directly removes the dependency entirely and is the obvious Phase 2 follow-up.

**A missed question is visible, not silent.** The adapter deliberately does not guess from
free text. The cost is that an unhonoured instruction shows up as a step that finished with
an odd result rather than as an explicit prompt — inspectable in the node log, but not
signposted.

**Existing skills remain Claude-Code-flavoured.** Phase 1 deliberately runs them unmodified
through the Claude adapter. The `StepExecutor` interface is provider-neutral, but the
*skills* are not yet; a second adapter is not merely a matter of implementing the Protocol.
That work is Phase 2 and is the reason Phase 2 exists.

**Phase 1 executes serially.** The graph supports parallel branches and the scheduler is
written for them, but the concurrency cap is 1, so branches queue rather than overlap. The
reason is that concurrent implr steps writing to shared artefact directories is unproven.
Raising the cap is a config change once that is validated.

**The configurator's Input tab is descriptive, not enforced.** `consumes` documents what a
step reads so the graph is legible; nothing validates it. A real per-skill input contract
does not exist today, and inventing one here would mean asserting a schema the skills do
not actually honour. The tab carries a banner saying so, rather than implying a guarantee.

**Manual approval is recorded per node, not per edge.** `node_runs.manual_approved` is a
single flag read by every inbound edge, so a node with two inbound approval gates opens
both from one click, and a retry does not clear it. Correct for the linear six-step
pipeline; wrong for a genuine join. The gate editor warns when it would matter. Scoping
approval to `(run_id, edge)` is the fix and is deferred.

**Model overrides are per node, not per run.** There is no "run this whole pipeline on
Sonnet" switch. The model-mix meter exists so the operator can see the aggregate before
starting, but changing it means visiting the nodes that matter.

---

## Open Questions

None. Both forks raised during design — execution model and interactive-step handling —
were settled: a generic interface with a single Claude Code adapter, and full UI proxying
of interactive steps.

---

## Success Criteria

1. The operator composes the six-step pipeline (ingest → architecture → requirements →
   planning → implementation → review) by dragging, connecting, and saving — producing a
   valid `docs/implr/config/pipeline.yaml`.
2. A gate demanding a status outside an artefact's state machine is rejected at save time
   with a message naming the valid states.
3. Starting a run executes `doc-ingest` in the target project, streams its output to the
   browser live, and advances to the next node on success.
4. Running `arch-gen` surfaces its decision-confirmation questions in the browser, and the
   operator's typed answers reach the step, which proceeds in the same session.
5. A pipeline blocked on an `artifact` gate stays blocked until the underlying frontmatter
   actually satisfies it, and advances without operator action once it does.
6. Killing and restarting the backend mid-run recovers the run: completed nodes stay
   completed, and the interrupted node is reported as failed rather than silently retried.
7. The full backend and frontend test suites pass without invoking any LLM.
8. Clicking the Implementation node opens the configurator, whose **Agents** tab lists
   `arch-excerpter`, `plan-runner` and `task-executor` with the tier defaults read from
   `implr.config.yaml`; dropping `task-executor` to `sonnet` marks it overridden, updates
   the model-mix meter, and writes a `models:` entry on that node when saved.
9. Selecting `dev-executor --task` without supplying a value is rejected at save time with
   a message naming the flag; supplying `PLAN-F-004#3` is accepted and reaches the executor
   as two separate argv elements.
10. The configurator's **Output** tab for the Planning step lists the ten required `plan`
    frontmatter fields and the five legal plan statuses, read from the contract files — the
    same set the downstream gate editor offers.
11. `POST /api/runs` returns a `run_id` before the first node finishes, and the browser's
    WebSocket receives log events while the run is still going.
12. The console renders dark with no `data-theme` stamp and on a light OS; only an explicit
    `data-theme="light"` produces the light palette.
