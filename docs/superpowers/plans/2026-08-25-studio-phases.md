# implr Studio — Phase Roadmap

**Status:** authoritative task breakdown. Supersedes the six layer plans
(`2026-08-25-studio-0{1..6}-*.md`), which are retained only until their content has been
redistributed into the phases below.

**Design reference:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md` — still the
single source of truth for *what* is being built. This document governs *in what order*.

**Runtime verification:** `docs/RUNTIME.md`

---

## Why phases and not layers

The first breakdown was six horizontal layers: all the data, then the executor contract,
then the orchestrator, then the API, then the UI, then the adapter. Four of those six
produced nothing anyone could look at, and the UI — which is the product — landed last.

That ordering produced a real defect. `POST /api/runs` was written to block until the run
settled, because that made the responses tidy and the tests deterministic. It also made
live streaming impossible. Nobody noticed for four plans, because nothing was consuming the
API. A UI calling that endpoint would have caught it in ten minutes.

So the axis is rotated. Each phase below is a **thin vertical slice through every layer**
that ends in something you can open in a browser and exercise by hand. The backend stops
being a thing you finish and becomes a thing that arrives just-in-time, sliced to serve
whatever the UI just grew.

**Two rules that make this work:**

1. **Every phase ends in a demo.** Not a green suite — a green suite is table stakes. A
   thing you can click, and hand to someone else to click.
2. **A phase contains only the backend its UI increment needs.** Gate evaluation is not in
   the foundation; it arrives in Phase 10, with gates. Restart recovery arrives in Phase 12,
   with failure handling. Resist building ahead — a layer built before its consumer exists
   is a layer with no feedback.

**The cost, stated plainly.** Vertical slicing means touching the same file repeatedly:
`registry.py` grows in phases 1, 5, 6 and 7; `store.py` in 8, 9 and 12; `api.py` in almost
all of them. That is more total churn than building each file once, and occasionally a later
phase will outgrow an earlier phase's shape and force a small refactor. You are buying
continuous verifiability with that churn.

---

## The phases

Token spend is called out because it is the one cost that is not reversible. **Phases 0–12
invoke no model at all** — `FakeExecutor` arrives in Phase 8 precisely so that every run
phase is free. Only Phase 13 costs anything.

| # | Phase | Demo at the end | Tokens |
|---|---|---|---|
| 0 | [Skeleton](2026-08-25-studio-phase-00-skeleton.md) | `implr-studio` starts; browser shows the dark shell and a live health dot | none |
| 1 | [See the steps](2026-08-25-studio-phase-01-palette.md) | Nine real steps grouped by phase; the two unimplemented ones dashed; search filters | none |
| 2 | [Draw a pipeline](2026-08-25-studio-phase-02-canvas.md) | Drag two steps, connect them, Save → `pipeline.yaml` on disk; reload keeps the graph | none |
| 3 | [Refuse bad graphs](2026-08-25-studio-phase-03-validation.md) | Make a cycle, Save, see the finding named; nothing written to disk | none |
| 4 | Configure arguments | Open a step, tick `--task`, type a value; a bad value is refused inline | none |
| 5 | Pick models | Drop `task-executor` to Sonnet; the node's dots, the mix meter and the YAML all change | none |
| 6 | Conditions | Build an artefact gate; an illegal status is not offered, and is refused if hand-edited in | none |
| 7 | Input / Output tabs | The Output tab shows the ten real `plan` fields and five legal statuses | none |
| 8 | Run one node | Press Run; one node goes green | none |
| 9 | Live logs | Log lines appear *while* the step is running; a refresh loses nothing | none |
| 10 | Many nodes, real gates | A gate holds; you edit a file on disk; it opens with no operator action | none |
| 11 | Questions | Answer a question in the browser; the step continues in the same session | none |
| 12 | Failure & recovery | Kill the server mid-run, reopen, resume rather than restart | none |
| 13 | Real model | A real `doc-ingest --dry-run` streams into the browser | **yes** |

---

## Phase specifications

Phases 0–3 have their own documents. The rest are specified here until theirs are written.

### Phase 4 — Configure arguments

**UI increment.** Clicking a node opens the configurator modal with **one tab, Run**. It
shows the step's description as a lead paragraph, then its `args_allowed` as checkboxes,
with a text input beside any flag whose `takes_value` is true — disabled until the flag is
selected. Selecting a value-taking flag with no value, or a value failing its
`value_pattern`, is flagged inline before you can save. Banners explain an unimplemented
step and an interactive one.

**Backend slice.** `pipeline.Node` gains `arg_values`. `validate_pipeline` gains
`missing-arg-value`, `bad-arg-value` and `orphan-arg-value`. Nothing else.

**Ships:** `modal/Modal.tsx` (the dialog shell — scrim, head, tabs, footer, Escape, focus),
`modal/StepConfig.tsx` with only the Run pane.

**Demo:** open Implementation, tick `--task`, leave it blank → *needs a value*. Type
`has space` → *not a valid value*. Type `PLAN-F-004#3` → warning clears, the node on the
canvas reads `--task PLAN-F-004#3`, Save writes `arg_values` into the YAML. Then clear it
and Save → 422 naming the flag.

**Why the value field is the whole point of this phase:** several implr flags genuinely take
an argument — `--file`, `--task`, `--domain`. A flat flag whitelist makes them selectable
and inert, which is worse than not offering them.

---

### Phase 5 — Pick models

**UI increment.** The configurator gains its **Agents** tab: one card per agent the step
dispatches, showing its name, fan-out, role, a model-tier selector defaulting to the
project value and marked *overridden* when changed, and its declared tool grant with
repository-mutating tools visually distinct. The node card grows a row of tier dots. The
right rail grows the **model-mix meter** and names the most expensive step.

**Backend slice.** `serialize.agent_defaults(workspace)` reads `implr.config.yaml`'s
`agents:` block; `serialize.agent_tools(repo_root)` reads `.claude/agents/*.md` frontmatter.
`pipeline.Node` gains `models`. `validate_pipeline` gains `unknown-agent` and
`illegal-tier`. `GET /api/registry` grows `tiers`, `agent_defaults`, `agent_tools`.

**Ships:** `models.ts` (`resolveTier`, `isOverridden`, `mixFor`, `worstTier`),
`panels/HealthPanel.tsx` meter, the Agents pane.

**Demo:** open Implementation → Agents. Three agents listed, `plan-runner` and
`task-executor` on Opus from `implr.config.yaml`. Drop `task-executor` to Sonnet: it marks
*overridden*, the node's dots change, the mix meter shifts, the modal footer gains
`implr.config.yaml`. Set it back to Opus: the override **clears** rather than pinning, and
`models` disappears from the YAML.

**The load-bearing decision:** tier is per agent, not per step, because
`implr.config.yaml` already owns that mapping. The configurator edits *that* block. A
per-step `model` field would be a second source of truth for the same decision.

---

### Phase 6 — Conditions

**UI increment.** Clicking an edge opens the gate editor — the same modal shell, one pane.
Four dropdowns (condition, artefact, how many, required status), populated from the schema
files, so an impossible condition is hard to express. Beneath them, the condition restated
as a plain sentence. Edges grow gate chips on the canvas.

**Backend slice.** `gates.validate_gate` (save-time only — no runtime evaluation yet).
`serialize.contracts_to_dict`. `GET /api/registry` grows `contracts`. `PUT /api/pipeline`
merges gate findings into the same list.

**Ships:** `gates.ts` (`gateLabel`, `gateSentence`), `modal/GateConfig.tsx`,
`edges/GateEdge.tsx` label rendering.

**Demo:** click `plan → build`, set condition to `artifact`, artefact `plan`, how many
`any`, status `ready`. The chip reads `any plan status=ready` and the sentence reads
*"Implementation starts once at least one plan is ready."* The status dropdown offers only
the five plan states — `approved` is not among them. Hand-edit the YAML to
`status: complete`, reload, Save → 422 naming the five legal states.

---

### Phase 7 — Input / Output tabs

**UI increment.** The configurator's last two tabs. **Input** lists what the step reads and
its inbound conditions, with a jump into the gate editor, and carries an explicit banner
that it is descriptive. **Output** lists what it writes and, where the step produces a
status-carrying artefact, that artefact's required fields, optional fields, legal statuses
and path globs.

**Backend slice.** None new — `consumes`, `produces`, `produces_artefact` shipped with the
registry in Phase 1; `contracts` shipped in Phase 6. This phase is pure UI, which is why it
is cheap and why it comes after 6.

**Demo:** Planning → Output shows ten required `plan` fields, `rework_cr` as optional, five
statuses, and `docs/implr/plans/functional/*.md`. Implementation → Output shows `src/**` and
`tests/**` and says there is no frontmatter contract. Implementation → Input shows the
plans glob and the inbound condition with an Edit button that opens Phase 6's editor.

---

### Phase 8 — Run one node

The first phase with an executor. Deliberately minimal: **one node, no gates, no logs, no
questions.**

**Backend slice.** `executors/base.py` (the full contract — it is small and splitting it
would be worse), `executors/fake.py`, `runstate.py`, `store.py` (runs + node_runs only; no
events, no questions), a single-node `Orchestrator`, `POST /api/runs` returning **202**,
`GET /api/runs/{id}`.

**Ships:** run mode: the mode switch, node status stripes, `panels/RunPanel.tsx` showing
run id and per-node status.

**Demo:** save a one-node pipeline, press Run, watch the node go `running` then `succeeded`
without a model being called. `GET /api/runs` lists it.

**Do not** add `wait_quiescent` to the route to make the demo tidy. The route returns 202
immediately; the UI polls. That constraint exists from this phase onward and Phase 9 depends
on it.

---

### Phase 9 — Live logs

**Backend slice.** `store` gains the `events` table with its monotonic `seq`;
`WS /api/runs/{id}/stream` with cursor replay; the orchestrator persists every event before
it is observable.

**Ships:** `api.openStream`, `store.applyEvents`, the log pane in `RunPanel`.

**Demo:** press Run on a step scripted with several log lines and a delay. Lines appear
**progressively**, not in one burst at the end. Refresh the browser mid-run: the log is
complete and nothing is duplicated.

**This is the phase that proves Phase 8's 202 was right.** If logs arrive all at once, a
route is waiting for the run to settle.

---

### Phase 10 — Many nodes, real gates

**Backend slice.** `gates.evaluate_gate` and `artefact_condition_holds` (runtime, reading
the filesystem), `node_readiness`, the driver loop, `blocked` and `awaiting-approval`
states, the approve route.

**Ships:** blocked/awaiting-approval affordances in `RunPanel` — and the distinction between
them, which is the usability trap of run mode: `blocked` advances on its own and offers no
button; `awaiting-approval` needs the operator.

**Demo:** a two-node pipeline gated on `all requirement status=approved`. Press Run. Node 1
succeeds, node 2 shows `blocked` with an explanation. Write an approved requirement file
into the workspace by hand. Node 2 advances **with no click**. Then the empty-match-set
rule: delete the requirement, re-run, confirm the gate does *not* open.

---

### Phase 11 — Questions

**Backend slice.** `question` events, the `questions` table, `awaiting-input`,
`POST /api/runs/{id}/answer`, and the executor **question arming rule** — a pending question
must be recorded *before* the event is emitted, because the orchestrator abandons the event
iterator the moment a question arrives and only resumes after the answer lands.

**Ships:** the question card — the agent's own options as buttons **and** a free-text box,
because the operator may want to say something the agent did not offer.

**Demo:** a scripted `arch-gen` asks which database. The card appears with two option
buttons. Click one; the step continues and completes. Then the assertion that matters:
`ex.started` must list `arch-gen` **once**. Twice means answering restarted the step from
the top instead of resuming its stream, and a real agent would have lost its context.

---

### Phase 12 — Failure & recovery

**Backend slice.** `failed` / `skipped` / `cancelled`, retry / skip / cancel routes,
`Orchestrator.recover()`, the exception-safe driver loop, and the `Store` lock.

**Ships:** Retry / Skip / Abort in `RunPanel`, the error block, run history.

**Demo:** a step scripted to fail. The node goes red, the error shows, the run pauses and
downstream nodes stay `pending` — not `failed`. Retry with a fixed script: it succeeds.
Then restart recovery: start a run, `kill` the server mid-step, restart it, reopen the
browser — completed nodes stay completed and the interrupted node reports `failed` with an
error naming the restart. It is not silently retried.

---

### Phase 13 — Real model

**Backend slice.** `executors/_sdk.py` (import seam, prompt, permissions, tier mapping),
`executors/translate.py` (pure message → event mapping), `executors/claude_code.py`, and the
opt-in `-m live` suite.

**Ships:** nothing new in the UI. That is the point — if the adapter honours the
`StepExecutor` contract, the console does not change.

**Demo:** `implr-studio --workspace $PROBE` with **no** `--fake`. Run
`doc-ingest --dry-run`. Real log lines stream into the browser, the step reports
`succeeded`, and the workspace is unmodified because of `--dry-run`.

**Three things only this phase can settle**, and all three are invisible to the offline
suite:

1. A slash command must actually invoke the installed skill. If it does not, no pipeline
   runs at all while every stubbed test stays green. Verify this **first**.
2. `AskUserQuestion` must not be in `allowed_tools` — a whole-tool allow entry auto-approves
   before `can_use_tool` is consulted, which silently disables question proxying.
3. The agent must read a `PermissionResultDeny` message as an *answer* rather than a
   refusal. That is the return path for every operator reply.

---

## Dependency graph

Not a straight line. Phases 4–7 all depend only on 1–3, so they can be reordered or
parallelised. Phases 8–12 are strictly sequential.

```
0 ─> 1 ─> 2 ─> 3 ─┬─> 4 ─> 5
                  ├─> 6 ─> 7
                  └─> 8 ─> 9 ─> 10 ─> 11 ─> 12 ─> 13
```

- **4 before 5** — the Agents tab reuses the modal shell the Run tab introduces.
- **6 before 7** — the Output tab renders the `contracts` payload Phase 6 adds.
- **6 before 10** — save-time gate validation before runtime gate evaluation, so an
  unrunnable condition cannot be saved in the first place.
- **8 before 9** — the 202 contract must exist before streaming can prove it.

The first genuinely useful stopping point is **Phase 7**: a complete pipeline *designer*
with no execution. That is a shippable product on its own, and worth treating as a
milestone rather than a waypoint.

---

## Where the old plans' content went

The six layer plans are retained until every row below is done. They are the source; nothing
in them is discarded, only redistributed.

| Old plan | Redistributed into |
|---|---|
| **1** Foundation | 0 (bridge, hygiene) · 1 (registry) · 2 (pipeline config) · 3 (DAG validation) · 4 (arg values) · 5 (models) · 6 (gate validation) |
| **2** Executor contract | 8 (base + fake) · 11 (question arming rule) |
| **3** Orchestrator | 8 (store, runstate, single-node driver) · 9 (events) · 10 (gates, scheduling) · 11 (questions) · 12 (recovery, lock, operator actions) |
| **4** API | 0 (server, static mount) · 1 (registry route) · 2 (pipeline routes) · 3 (422 findings) · 5 (agent payloads) · 6 (contracts) · 8 (run routes) · 9 (WebSocket) · 12 (operator routes) |
| **5** Frontend | 0 (scaffolding, tokens) · 1 (palette) · 2 (canvas) · 3 (findings) · 4 (modal + Run tab) · 5 (Agents tab, meter) · 6 (gate editor) · 7 (Input/Output tabs) · 8–12 (run mode, incrementally) |
| **6** Claude adapter | 13, whole |

---

## Conventions every phase document follows

- **Goal** — one sentence, phrased as the demo.
- **Demo** — the clickable proof, near the top rather than buried at the end.
- **Scope boundary** — an explicit *not in this phase* list. This is what keeps a phase thin.
- **Tasks** — TDD steps with `- [ ]` checkboxes: failing test, run it, implement, run it,
  commit.
- **Definition of Done** — including the demo, not only the suite.

Every phase commits independently and leaves `main` releasable. Run the free regression
sweep in `docs/RUNTIME.md` before each commit.
