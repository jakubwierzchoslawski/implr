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

---

## Scope

This spec covers **Phase 1 only**. Phase 2 is explicitly deferred and specified separately.

### In scope (Phase 1)

- Step registry (declarative catalogue of available steps).
- Pipeline config format and its validation.
- Visual builder frontend (design mode + run mode).
- Orchestrator backend: run lifecycle, gate evaluation, persistence, streaming.
- Generic `StepExecutor` interface.
- One adapter: Claude Code, via its bidirectional `stream-json` headless protocol.
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
      "args_allowed": ["--digest", "--registry-only", "--file"],
      "args_default": ["--digest"],
      "interactive": false,
      "produces": ["digest", "synthesis"],
      "description": "Indexes and digests the knowledge base under docs/kb/."
    },
    {
      "id": "arch-gen",
      "label": "Architecture Brief",
      "phase": "design",
      "skill": "arch-gen",
      "args_allowed": ["--dry-run", "--update"],
      "args_default": [],
      "interactive": true,
      "produces": ["architecture"],
      "description": "Generates docs/ARCHITECTURE.md; confirms each decision with the user."
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
| `args_allowed` | Whitelist of flags the node config UI offers. A pipeline referencing a flag outside this list fails validation. |
| `args_default` | Args applied when the node is first dropped onto the canvas. |
| `interactive` | Whether the step is expected to ask the operator questions mid-run. Drives UI affordances only; the proxy channel is always available. |
| `produces` | Free-form labels shown on the node. Documentation, not execution logic. |
| `description` | Tooltip text. |

### Availability

A registry entry whose `skills/<skill>/SKILL.md` does not exist is **not an error**. It is
rendered in the palette as unavailable (greyed, non-draggable) with a tooltip explaining
the skill is not implemented yet. This is how planned steps — a dedicated testing step, a
dedicated security-check step — appear in the process diagram before they exist.

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
    args: ["--all"]
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

### DAG validation (at save time)

The config is rejected with an actionable error if:

- Any `node.step` is not a registry `id`.
- Any `node.args` entry is outside that step's `args_allowed`.
- Node `id`s are not unique.
- Any edge references an unknown node `id`.
- The graph contains a cycle.
- Any node is unreachable from a root node (a node with no inbound edges).
- The graph has no root node.

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

**Permissions.** The adapter runs with `acceptEdits` plus an explicit `--allowedTools`
allowlist covering what implr skills need. Anything outside the allowlist is denied and the
denial appears in the node's log. `bypassPermissions` is deliberately not used: this agent
is driven by a web page, and unrestricted shell access on that path is not a default anyone
should inherit without choosing it.

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
| `GET` | `/api/registry` | The step catalogue, each entry annotated `available: bool`. |
| `GET` | `/api/pipeline` | Current `pipeline.yaml`, parsed. |
| `PUT` | `/api/pipeline` | Validate and save. `422` with a list of findings on failure. |
| `POST` | `/api/runs` | Start a run of the saved pipeline. |
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

---

## Component: Frontend

One canvas, two modes.

**Design mode.** A palette on the left, grouped by `phase`, with unavailable steps greyed.
Drag onto the canvas to create a node; drag between handles to create an edge. Selecting a
node opens a config panel offering only that step's `args_allowed`. Selecting an edge opens
the gate editor, whose artefact and status dropdowns are populated from the schema files —
so an invalid gate is difficult to express, and rejected by the backend if it is.

**Run mode.** The same graph, nodes tinted by run state, with a live log pane per node. A
node in `awaiting-input` renders its question as markdown with a free-text answer box; a
node in `awaiting-approval` renders an Approve button. Failed nodes offer Retry / Skip /
Abort.

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
- Adapter: the Claude stream-event → `StepEvent` mapping is tested against recorded
  fixture streams, with no subprocess. The turn-end-means-question mapping gets explicit
  coverage.

**Frontend (Vitest + React Testing Library):**

- Palette-to-canvas drop reducer.
- Pipeline serialization round-trip: load YAML → edit → save → byte-comparable structure.
- Run-mode rendering per node state, including the question and approval affordances.

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
