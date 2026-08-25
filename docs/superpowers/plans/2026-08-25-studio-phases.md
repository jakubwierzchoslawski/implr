# implr Studio — Phase Roadmap

**Status:** authoritative task breakdown. Supersedes the six layer plans
(`2026-08-25-studio-0{1..6}-*.md`), which are retained only until their content has been
redistributed into the phases below.

**Design references:**
- `docs/superpowers/specs/2026-08-25-implr-studio-design.md` — what is being built.
- `docs/superpowers/specs/2026-08-25-implr-studio-hosted-design.md` — tenancy, authorization,
  containers, Azure. **Supersedes parts of the first**, notably the security posture and the
  route shape.

This document governs *in what order*.

**Runtime verification:** `docs/RUNTIME.md`

---

## Two things that cut across every phase

Both come from the hosted design and neither is a phase of its own, because both must be
present from the first route rather than retrofitted.

### 1. Routes are project-scoped from Phase 1

`/api/projects/{pid}/pipeline`, not `/api/pipeline`. **Local mode is the degenerate case** —
one tenant, one user, one project pinned to the `--workspace` directory — so there is one API
shape, not two. A local UI reads its single project from `/api/projects` and never renders a
picker.

The alternative, resolving the project implicitly in local mode, produces two route shapes
that every client, test and runbook has to distinguish. One extra path segment buys the
removal of that entire class of divergence.

### 2. `authorize()` is called by every route from Phase 1

Even in local mode, where the policy always says yes. The seam is
`authz.authorize(principal, permission, project=…)`, and the permission verbs are named in
full from the start — `project.read`, `project.write`, `run.start`, `run.control`,
`step.author`, `skill.author`, `tenant.admin`.

**Naming them later would mean revisiting every call site to decide which verb it meant**,
which is exactly the audit the seam exists to prevent. Phase 17 swaps `LocalPolicy` for
`TenantWidePolicy` and no route changes.

A test walks the FastAPI route table and fails on any handler that does not call
`authorize` — added in Phase 1 and kept green from then on.

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
   the foundation; it arrives in Phase 10, with gates. Restart recovery arrives in Phase 14,
   with failure handling. Resist building ahead — a layer built before its consumer exists
   is a layer with no feedback.

**The cost, stated plainly.** Vertical slicing means touching the same file repeatedly:
`registry.py` grows in phases 1, 5, 6 and 7; `store.py` in 9, 10, 13 and 14; `api.py` in almost
all of them. That is more total churn than building each file once, and occasionally a later
phase will outgrow an earlier phase's shape and force a small refactor. You are buying
continuous verifiability with that churn.

---

## The phases

Token spend is called out because it is the one cost that is not reversible. **Phases 0–14
invoke no model at all** — `FakeExecutor` arrives in Phase 9 precisely so that every run
phase is free. Phases 15, 18 and 19 are the only ones that cost anything.

| # | Phase | Demo at the end | Tokens |
|---|---|---|---|
| **−1** | **[Restructure](2026-08-25-studio-phase-minus1-restructure.md)** | `pip install implr-validate` works; no test contains `sys.path.insert` | none |
| 0 | [Skeleton](2026-08-25-studio-phase-00-skeleton.md) | `implr-studio` starts; browser shows the dark shell and a live health dot | none |
| 1 | [See the steps](2026-08-25-studio-phase-01-palette.md) | Nine real steps grouped by phase; the two unimplemented ones dashed; search filters | none |
| 2 | [Draw a pipeline](2026-08-25-studio-phase-02-canvas.md) | Drag two steps, connect them, Save → `pipeline.yaml` on disk; reload keeps the graph | none |
| 3 | [Refuse bad graphs](2026-08-25-studio-phase-03-validation.md) | Make a cycle, Save, see the finding named; nothing written to disk | none |
| 4 | [Configure arguments](2026-08-25-studio-phase-04-arguments.md) | Open a step, tick `--task`, type a value; a bad value is refused inline | none |
| 5 | [Pick models](2026-08-25-studio-phase-05-models.md) | Drop `task-executor` to Sonnet; the node's dots, the mix meter and the YAML all change | none |
| 6 | [Conditions](2026-08-25-studio-phase-06-conditions.md) | Build an artefact gate; an illegal status is not offered, and is refused if hand-edited in | none |
| 7 | [Input / Output tabs](2026-08-25-studio-phase-07-io-tabs.md) | The Output tab shows the ten real `plan` fields and five legal statuses | none |
| 8 | **Author a step** | Create your own step in the UI — point it at any installed skill, or write its instruction and agents outright — and drag it onto the canvas | none |
| 9 | [Run one node](2026-08-25-studio-phase-09-run-one-node.md) | Press Run; one node goes green | none |
| 10 | [Live logs](2026-08-25-studio-phase-10-live-logs.md) | Log lines appear *while* the step is running; a refresh loses nothing | none |
| 11 | [Many nodes, real gates](2026-08-25-studio-phase-11-gates.md) | A gate holds; you edit a file on disk; it opens with no operator action | none |
| 12 | [Questions](2026-08-25-studio-phase-12-questions.md) | Answer a question in the browser; the step continues in the same session | none |
| 13 | **[Review & send back](2026-08-25-studio-phase-13-review.md)** | Reject a step's output with a note; it re-runs knowing why | none |
| 14 | Failure & recovery | Kill the server mid-run, reopen, resume rather than restart | none |
| 15 | Real model | A real `doc-ingest --dry-run` streams into the browser | **yes** |
| 16 | **Containers** | `docker compose up` serves the console; the API image has no `git` and no Claude CLI | none |
| 17 | **Tenancy & auth** | Two users in one Entra tenant see the same projects; a third tenant's user sees none | none |
| 18 | **[Onboarding](2026-08-25-studio-phase-18-onboarding.md)** | A new tenant goes from sign-in to a supervised dry run in under five minutes | **yes** |
| 19 | **Deploy to Azure** | A run executes in a Container Apps Job and streams to the browser | **yes** |

Twenty-one phases, `−1` through `19`. Phases 16–19 are the hosting work, and none is
reachable until 15 is done: deploying a console that cannot run a pipeline proves nothing.

**Phase 13 is new and is not optional.** Answering the question *"can every step be
human-in-the-loop?"* honestly turned up four gaps — a root node cannot be gated, a terminal
node's output cannot be reviewed, there is no review-and-send-back, and an approval survives
a retry. See *Component: Human-in-the-loop* in the design spec. Without 13, "HITL" means
"approve, or re-roll the dice".

---

## Phase specifications

Phases −1, 0–7, 9–13 and 18 have their own documents. Phases 8, 14–17 and 19 are specified here until theirs are written.

### Phase −1 — Restructure


**Must precede Phase 0**, which currently writes `studio/backend/pyproject.toml` at a path
this phase deletes.

The tree today is a clean plugin source with **no packaging story**: no root manifest,
`implr_validate` vendored into target projects by `cp -f` in `install.sh`, every test doing
its own `sys.path.insert`, and a Python library living in a directory called `scripts/`. A
Dockerfile has nothing to install.

**Ships:** a root `pyproject.toml` + lock declaring three packages; `scripts/implr_validate`
→ `packages/implr_validate`; `studio/backend/implr_studio` → `packages/implr_studio`;
`scaffold/schemas/*.json` → `packages/implr_contracts`; `skills/`, `.claude/agents/` and the
rest of `scaffold/` → `plugin/`; `studio/frontend` → `web/`. The three installers become one
directory copy plus a `pip install`.

**Demo:** `pip install -e packages/implr_validate && python -m implr_validate --repo --root .`
with **no** `PYTHONPATH`. `grep -r sys.path.insert tests/` returns nothing.

**Minimal alternative** if the full move is too much churn: root manifest, move
`implr_validate` only, add `docker/`. Leave `skills/` and `.claude/agents/` where they are and
let the Dockerfile `COPY` three directories instead of one. Everything downstream still works.


---

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

**Read-only apart from the tier, and say so.** For a `kind: "skill"` step the Agents tab is
*describing* what the skill's own prose dispatches — the studio sends `/doc-ingest` and the
SKILL.md decides the rest. Only the tier is genuinely configurable, because that maps onto
`ClaudeAgentOptions`. The pane therefore renders the name, fan-out and tool grant as facts
and the tier as a control, with a line saying which is which. Phase 8's `kind: "agent"`
steps make the whole card editable; a UI that looked editable here and silently discarded
the edit would be worse than one that admits the boundary.


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

### Phase 8 — Author a step


The phase that turns the catalogue from closed to open. Until now the palette is exactly the
nine steps implr ships, and adding one means hand-writing a `SKILL.md` in the plugin source
and reinstalling. After this phase you can create a step from the UI.

**Two kinds, one surface.** A `kind: "skill"` step points at any **installed** skill —
discovered from `<workspace>/.claude/skills/` — and you author its arg specs. A
`kind: "agent"` step has no skill: you write its `instruction`, and its agents' prompts,
tool grants, tiers and turn caps, all of which map onto real `ClaudeAgentOptions` fields.

**Backend slice.**

- `registry.load_registry` gains a second source: `docs/implr/config/steps.yaml`, merged
  over the plugin registry **by `id`, with a collision reported as an error**. Overriding a
  shipped step would be occasionally useful and permanently confusing.
- `registry.discover_skills(workspace) -> dict[str, SkillInfo]` — reads
  `<workspace>/.claude/skills/*/SKILL.md` frontmatter for `name` and `description`.
- `Step` gains `kind`, `instruction`, and per-agent `prompt` / `tools` / `max_turns`.
- Authored-step validation: `kind` in the two legal values; `kind: skill` requires `skill`;
  `kind: agent` requires a non-empty `instruction` and each agent a `name` and `prompt`;
  `model` in `TIERS`; `max_turns` a positive int; **`tools` a subset of the adapter's
  permitted set**, so authoring cannot route around the permission posture.
- `GET /api/skills` — the discovered skills, for the picker.
- `GET`/`PUT /api/steps` — read and write `steps.yaml`, validated, 422 with findings.

**Ships:** `modal/StepAuthor.tsx` — the authoring surface, reusing `Modal.tsx`. A **New
step** button at the top of the palette. Authored steps appear in the palette in their chosen
phase, visually marked as project-owned. An agent-backed node carries a distinct marker on
the canvas.

**Demo:** press **New step**. Choose *agent-backed*, name it `Lint & Format`, phase
`verify`, write an instruction, add one agent on `haiku` with `[Read, Edit, Bash]`. Save →
`docs/implr/config/steps.yaml` appears. It shows up in the palette under verify, marked as
yours. Drag it onto the canvas, connect it after Code Review, Save the pipeline. Then try to
grant it `WebFetch` → refused, naming the permitted set. Then author a *skill-backed* step
pointing at an installed skill the plugin registry does not declare, and confirm it appears
available while a made-up skill name appears dashed.

**Why `steps.yaml` and not the plugin registry.** `install.sh` copies `schemas/*.json` under
a comment reading *"Always overwrite: schemas and templates (plugin-owned)"*, so a project
that hand-edited its installed `step-registry.json` silently loses the change on the next
install. Before this phase there is **no way for a project to have a step implr does not
ship**. `steps.yaml` is project-owned, committed, and never touched by the installer.

**Deliberately not in this phase.** An agent-backed step takes **no arguments** —
interpolating an operator value into a prompt is prompt injection by construction, and
appending flags as literal text would offer a control the agent may silently ignore. If you
need a variant, author two steps. Editing a *shipped* step is also out: that is plugin
territory.

**The honest caveat, which the UI states too.** A surface that authors agent prompts has no
TDD enforcement, no review gate, and no iteration history. implr's value is that
`task-executor`'s prose has been refined to enforce TDD and SOLID. A hand-typed step bypasses
all of it — excellent for `lint-and-format` or `generate-diagram`, wrong for *"write the
implementation"*. Anything that turns out to be load-bearing should graduate into a real
`SKILL.md`.


---

### Phase 9 — Run one node


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

### Phase 10 — Live logs


**Backend slice.** `store` gains the `events` table with its monotonic `seq`;
`WS /api/runs/{id}/stream` with cursor replay; the orchestrator persists every event before
it is observable.

**Ships:** `api.openStream`, `store.applyEvents`, the log pane in `RunPanel`.

**Demo:** press Run on a step scripted with several log lines and a delay. Lines appear
**progressively**, not in one burst at the end. Refresh the browser mid-run: the log is
complete and nothing is duplicated.

**This is the phase that proves Phase 9's 202 was right.** If logs arrive all at once, a
route is waiting for the run to settle.


---

### Phase 11 — Many nodes, real gates


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

### Phase 12 — Questions


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

### Phase 13 — Review & send back


The phase that makes "human-in-the-loop" mean more than *approve, or re-roll the dice*.

**Why it exists.** Asking whether every step could be HITL turned up four gaps in the
orchestrator: a root node cannot be gated (`node_readiness` returns `READY` when there is no
inbound edge), a terminal node's output cannot be reviewed (approval releases a *downstream*
edge, and a terminal node has none), there is no way to reject with feedback, and an approval
survives a retry. See *Component: Human-in-the-loop* in the design spec.

**Backend slice.**

- `Node` gains `approval: none | before | after | both`. HITL moves from the **edge** to the
  **node**, because *"should a human look at this step"* is a property of the step. Edge gates
  keep artefact conditions, which genuinely are facts about a connection.
- `node_readiness` consults `approval == before` **even for a node with no inbound edge** —
  the one-line fix that makes a root node supervisable.
- New node state `awaiting-review`: succeeded, output present, waiting on a human. The run
  cannot report success while any node sits in it, which is what makes a terminal node
  reviewable.
- `StepRequest` gains `feedback: tuple[str, ...]` — accumulated rejection notes, oldest
  first. A tuple, not a string: the second rejection must not erase the first, and an agent
  that already failed twice benefits from knowing both objections.
- `approved_before_at/by`, `approved_after_at/by`, `review_feedback`, `attempt` replace
  `manual_approved`. **Both stamps clear on retry and on request-changes** — a re-run of a
  supervised step is supervised again. The current design's failure to do this only shows up
  when someone re-runs a step they had already approved and it proceeds without asking,
  which is precisely when they were paying least attention.
- Routes: `POST .../nodes/{node}/accept`, `POST .../nodes/{node}/request-changes`.

**Ships:** the review card in `RunPanel` — the step's summary, the paths it wrote, its log,
and three actions: **Accept**, **Request changes** (with a text box), **Accept with a note**.
Plus an `approval` control in the configurator's Run tab.

**Demo:** set `approval: after` on Architecture Brief. Run. The node reaches
`awaiting-review` rather than `succeeded`, and the run stays paused with downstream nodes
`pending`. Read the output, click **Request changes**, type *the persistence decision is
unjustified*. The node re-runs, `ex.started` shows two attempts, and the second `StepRequest`
carries the note. Accept the second attempt; the run proceeds.

Then the two fixes that are easiest to forget. Set `approval: before` on the **root** node
and confirm it waits — the pre-Phase-13 code runs it immediately. And retry an
already-approved node, confirming it asks again.

**Known limitation, kept.** Request-changes re-runs the **whole** step. There is no way to
say "keep requirements 1-6, redo 7". implr steps are file-based and idempotent so a re-run is
safe, but it is not cheap: a rejected `dev-executor` node redoes every task in the plan.
Narrowing it needs per-artefact rejection, which needs a step to report what it produced and
accept a subset on re-entry. Deferred, and worth doing.


---

### Phase 14 — Failure & recovery


**Backend slice.** `failed` / `skipped` / `cancelled`, retry / skip / cancel routes,
`Orchestrator.recover()`, the exception-safe driver loop, and the `Store` lock.

**Ships:** Retry / Skip / Abort in `RunPanel`, the error block, run history.

**Demo:** a step scripted to fail. The node goes red, the error shows, the run pauses and
downstream nodes stay `pending` — not `failed`. Retry with a fixed script: it succeeds.
Then restart recovery: start a run, `kill` the server mid-step, restart it, reopen the
browser — completed nodes stay completed and the interrupted node reports `failed` with an
error naming the restart. It is not silently retried.


---

### Phase 15 — Real model


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

### Phase 16 — Containers


**Ships:** `docker/api.Dockerfile`, `docker/worker.Dockerfile`, `docker/compose.yaml` — all
three already written and committed; this phase makes them build and pass tests. Plus the
`RunLauncher` seam: `InProcessLauncher` for local, `SubprocessLauncher` for compose.

**Backend slice.** `IMPLR_MODE` (`local` | `hosted` | `worker`). A `CatalogueSource` seam:
files in local mode, tables in hosted. Postgres behind the existing `Store` interface. The
worker entrypoint: clone, materialise, run, report.

**Demo:** `docker compose up --build`. The console loads at `127.0.0.1:8000`, the palette
lists steps **from Postgres** seeded in flight from `plugin/skills/`, and a run executes in a
separate worker container. Then two assertions that are security properties, not packaging
details: `docker run --rm implr-studio-api which git` finds nothing, and the worker container
has no `DATABASE_URL`.

**Why the launcher is a seam and not an `if`.** Local runs in-process; compose shells out;
Azure starts a Container Apps Job. Three implementations of one interface, chosen by mode —
the same discipline the `StepExecutor` Protocol applies to providers.


---

### Phase 17 — Tenancy & auth


The phase where the authorization seam built in Phase 1 gets a real policy.

**Backend slice.** `tenants`, `users`, `tenant_members`, `projects`, `project_grants`. Entra
token validation (issuer, audience, signature, expiry) resolving `tid` → tenant and `oid` →
user, creating both on first sign-in. **Postgres row-level security** on every tenant-owned
table, with the API connecting as a role that does **not** have `BYPASSRLS`. `LocalPolicy` is
replaced by `TenantWidePolicy`.

**Ships:** `/api/me`, `/api/projects` (list + create), and a project switcher in the app bar —
hidden when the tenant has exactly one project, so local mode looks unchanged.

**Demo:** sign in as two users from the same Entra tenant; both see the same project list and
either can save a pipeline. Sign in from a *different* tenant: the list is empty, and a direct
`GET` on the first tenant's project id returns **404, not 403** — a resource you may not see
does not exist. Then insert one `project_grants` row by hand and watch exactly that project
become restricted while its siblings do not.

**The load-bearing test.** With RLS on, run a deliberately tenant-unscoped query and assert it
returns **zero rows** rather than another tenant's data. That is what converts the worst class
of multi-tenant bug from a breach into an empty list, and it only holds if the API's role
lacks `BYPASSRLS` — so assert that too.

**What is deliberately not built.** Per-project role enforcement. `project_grants` exists and
is empty; `ProjectGrantPolicy` is written but not wired. The rule shipping here is the one
asked for: any member of a tenant may act on any project in it.


---

### Phase 18 — Onboarding


**Target: under five minutes from first sign-in to a running pipeline.** The two decisions
that matter most are both about *not* doing something: not asking the customer to run a shell
script, and not starting them on a blank canvas.

**Ships:**

- A GitHub App integration: authorise, list repositories, pick one and a branch.
- **Repository preparation as a pull request.** If `docs/implr/` is absent, open a PR adding
  exactly what `install.sh` writes, with a body explaining each directory. A hosted customer
  must never be told to clone a repo and run bash — that is where onboarding dies. A PR, never
  a push to the default branch: writing to someone's default branch as an onboarding side
  effect is how a tool gets banned, and the PR gives them a natural place to say no.
- Five pipeline **templates** — Full SDLC, Requirements only, Build approved plans, Change
  request, Blank — each materialised with `approval: before` on **every** node, so the first
  run is a step-by-step wizard. A blank canvas asks the customer to know implr's step ordering
  before they have seen it work, which is the exact problem Studio exists to solve.
- The first run defaults to `--dry-run` on every writing step, with the console saying so and
  offering to re-run for real once it finishes.
- The model mix defaults to Sonnet throughout rather than implr's own two-Opus default, so
  the first bill is not the first surprise.
- **The inbox** — the daily surface. Everything across the tenant waiting on a human, newest
  first, one click from row to decision. With approval on by default a paused run is the
  *normal* state, which makes a canvas-first console wrong for daily use: the canvas is where
  you design, occasionally.

**Demo:** sign in as a brand-new Entra tenant. Connect a repository with no implr workspace,
merge the PR it opens, choose *Full SDLC*, and click through six supervised dry-run steps.
Nothing was committed to the repository, and the whole thing took under five minutes.

**Deliberately not offered during onboarding:** authoring a custom step. Phase 8's surface is
powerful and is the wrong thing to show someone in their first five minutes. It stays
reachable from the palette; the flow never mentions it. Learn the nine shipped steps, and
author the tenth when one of them is missing.

**This phase spends tokens** — the dry run is real.


---

### Phase 19 — Deploy to Azure


**Ships:** `deploy/azure/main.bicep` and modules; `deploy/azure/README.md` as the setup
runbook; a GitHub Actions workflow building both images to ACR.

**Backend slice.** `ContainerAppsJobLauncher`. Key Vault references for
`ANTHROPIC_API_KEY`, the git credential and the database password. Blob Storage for the log
archive and uploaded KB documents. Managed identity for the API — **and none for the worker**.

**Demo:** a real run, in a real subscription, streaming to a browser over HTTPS with Entra
sign-in. Then the controls, each verified rather than assumed: the worker cannot resolve
`example.com` but can resolve `api.anthropic.com`; Postgres has no public endpoint; the
worker job has no managed identity and no database credentials.

**This phase spends tokens** and writes to a real repository. Run it with `--dry-run` on the
pipeline first.


## Dependency graph

Not a straight line. Phases 4–7 depend only on 1–3, so they can be reordered or
parallelised. Phases 9–14 are strictly sequential.

```
-1 ─> 0 ─> 1 ─> 2 ─> 3 ─┬─> 4 ─> 5 ─> 6 ─> 7 ─> 8
                        └─> 9 ─> 10 ─> 11 ─> 12 ─> 13 ─> 14 ─> 15
                                                                 │
                                              16 ─> 17 ─> 18 ─> 19
```

- **4 → 5 → 6 → 7 is a chain, not two branches.** Phase 4 introduces `Modal.tsx`, and both
  the Agents pane (5) and the gate editor (6) reuse it; Phase 7's Output tab renders the
  `contracts` payload Phase 6 adds. An earlier draft of this graph showed (4→5) and (6→7) as
  parallel, which was wrong — the gate editor is a modal.
- **7 before 8** — the authoring surface writes arg specs, agent definitions and I/O paths, so
  it needs every field the configurator already renders. Authoring a shape the UI cannot
  display would be building blind.
- **6 before 11** — save-time gate validation before runtime gate evaluation, so an
  unrunnable condition cannot be saved in the first place.
- **9 before 10** — the 202 contract must exist before streaming can prove it.
- **8 is not on the run path.** Nothing in 9–14 depends on it, so it can be deferred or
  skipped if the shipped nine steps are enough for now.
- **−1 before 0** — Phase 0 writes a manifest at a path the restructure deletes.
- **12 before 13** — review-and-send-back reuses the question round trip's plumbing: a node
  that pauses, an operator action, and a step that resumes.
- **15 before 16** — deploying a console that cannot run a pipeline proves nothing.
- **16 before 17** — tenancy needs Postgres, and Postgres arrives with the containers.
- **17 before 18** — onboarding creates tenants, projects and users; it cannot exist before
  they do.
- **17 before 19** — do not put an unauthenticated agent runner on the public internet. Of
  every edge in this graph, this is the one not to reorder.

Three useful stopping points. **Phase 7** is a complete pipeline *designer* for the nine
steps implr ships — no execution, no hosting, and shippable on its own. **Phase 8** makes that
designer open-ended. **Phase 15** is the whole local product working. Execution starts at 9
and hosting at 16.

Note that **9 branches from 3, not from 7**: the run phases need the canvas and validation, not
the configurator. If execution matters more to you than configuration, 4–8 can wait.

---

## Where the old plans' content went

The six layer plans are retained until every row below is done. They are the source; nothing
in them is discarded, only redistributed.

| Old plan | Redistributed into |
|---|---|
| **1** Foundation | 0 (bridge, hygiene) · 1 (registry) · 2 (pipeline config) · 3 (DAG validation) · 4 (arg values) · 5 (models) · 6 (gate validation) · 8 (`steps.yaml` merge, discovery) |
| **2** Executor contract | 9 (base + fake) · 12 (question arming rule) |
| **3** Orchestrator | 9 (store, runstate, single-node driver) · 10 (events) · 11 (gates, scheduling) · 12 (questions) · 13 (recovery, lock, operator actions) |
| **4** API | 0 (server, static mount) · 1 (registry route) · 2 (pipeline routes) · 3 (422 findings) · 5 (agent payloads) · 6 (contracts) · 8 (`/api/skills`, `/api/steps`) · 9 (run routes) · 10 (WebSocket) · 13 (operator routes) |
| **5** Frontend | 0 (scaffolding, tokens) · 1 (palette) · 2 (canvas) · 3 (findings) · 4 (modal + Run tab) · 5 (Agents tab, meter) · 6 (gate editor) · 7 (Input/Output tabs) · 8 (authoring surface) · 9–13 (run mode, incrementally) |
| **6** Claude adapter | 14, whole — plus `agent_definitions` gaining authored prompts and tool grants |

Phase 8 is the one phase with no ancestor in the six layer plans. It exists because the old
breakdown assumed a closed catalogue, and never asked whether a project could add a step of
its own. It could not.

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
