# implr Studio — Runtime Verification

> ## ⚠ Being restructured
>
> The work has been re-cut from six horizontal layer plans into **fourteen vertical phases**
> — see [`superpowers/plans/2026-08-25-studio-phases.md`](superpowers/plans/2026-08-25-studio-phases.md).
> Each phase now carries its own **Demo** and **Definition of Done** sections, which are the
> primary verification gate.
>
> This document is still organised by the old layer plans. Its **Prerequisites**,
> **Gate 0**, **regression sweep** and **Troubleshooting** sections apply unchanged and are
> the reason to keep reading it. Its per-plan probes are being folded into the phase
> documents as those are written; phases 0–3 already have theirs inline.
>
> Until the fold is complete: use the phase document's Demo section as the gate, and this
> document for the shared setup and the failure-mode table.

How to prove each of the six implr Studio plans actually works, plan by plan, at the
layer it lives in: pure data, contract, backend, API, UI, adapter.

**Companion to:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md` and
`docs/superpowers/plans/2026-08-25-studio-0{1..6}-*.md`

---

## How to read this

Each plan gets four sections, and the third is the one that matters:

| Section | Question it answers |
|---|---|
| **What exists after this plan** | What you can actually hold in your hands. |
| **Automated gate** | Does the suite pass? Copy-paste commands, exact expected output. |
| **Runtime probe** | Does the thing *run*? A real invocation, not a test. |
| **Not testable yet** | What you must not conclude from a green suite. |

The **Runtime probe** exists because "the tests pass" and "the thing runs" are different
claims, and the gap between them is where this project's real risks live. Two of the six
plans produce nothing runnable on their own — that is stated plainly rather than papered
over with a probe that only proves the test suite imports.

**Token spend.** Every probe here is free except the ones in *Plan 6 — live*. Those are the
only commands in this document that call a model. They are marked, and they are opt-in.

---

## Prerequisites

```bash
python --version    # 3.11+ (repo currently runs 3.14.3)
node --version      # 18+, only needed from Plan 5 onward
```

Shell notes for this repo's primary environment (Windows + PowerShell). The bash forms are
given first since they match the plans' own commit commands; PowerShell equivalents follow
where they differ:

| Task | bash | PowerShell |
|---|---|---|
| Set an env var for one command | `PYTHONPATH=scripts python …` | `$env:PYTHONPATH="scripts"; python …` |
| Background a server | `cmd &` | `Start-Process -NoNewWindow cmd` |
| Stop a backgrounded server | `kill %1` | `Stop-Process -Name python` |

`implr_validate` is **not** an installed package — each test file inserts `scripts/` on
`sys.path` itself. Running it as a module therefore needs the path set explicitly:

```bash
PYTHONPATH=scripts python -m implr_validate --repo --root .
```

### One-time: build a throwaway workspace

Every probe from Plan 3 onward operates on a *target project*, never on this repo. Build a
disposable one with the real installer, so the fixture is a genuine implr workspace rather
than a hand-made approximation:

```bash
export IMPLR=$(pwd)                      # the implr repo
export PROBE=/tmp/studio-probe           # PowerShell: $env:PROBE="$env:TEMP\studio-probe"

rm -rf "$PROBE" && mkdir -p "$PROBE" && cd "$PROBE"
bash "$IMPLR/install.sh"                 # PowerShell: & "$env:IMPLR\install.ps1"
```

Invoke it as `bash install.sh` rather than `./install.sh` — on Windows the executable bit
does not survive a clone, so the direct form fails with "permission denied".

That gives you `docs/implr/{config,schemas,requirements,plans,…}`, `docs/kb/`,
`.claude/skills/`, `.claude/agents/` and `scripts/implr_validate/`. Confirm — these are the
counts on a correct install:

```bash
ls "$PROBE/.claude/skills" | wc -l                      # 8 implr skills
ls "$PROBE/.claude/agents" | wc -l                      # 11 agent definitions
ls "$PROBE/docs/implr/config/implr.config.yaml"         # the agents: tier block lives here
ls "$PROBE/docs/implr/schemas/step-registry.json"       # only after Plan 1 has run
```

The agent count matters: Plan 1 asserts that every agent named in the shipped registry has
a definition, and the configurator's tier selector reads its defaults from
`implr.config.yaml`. A short count here means a partial install, and several probes below
will fail for that reason rather than a real one.

Note that `step-registry.json` is **absent** until Plan 1 ships it into
`scaffold/schemas/` — the installer copies `schemas/*.json`, so it appears in the workspace
on the next install after Plan 1 lands. Before then, `implr-studio` cannot start.

Add a small knowledge base so `doc-ingest` has something to read:

```bash
mkdir -p "$PROBE/docs/kb/billing"
cat > "$PROBE/docs/kb/billing/invoicing.md" <<'EOF'
# Invoicing rules

An invoice is issued monthly. Line items are immutable once issued.
Credit notes reference the original invoice. VAT is computed per line.
EOF
```

**Reset between probes:** `rm -rf "$PROBE" && ...` and re-run the installer. Nothing in
this document should ever be pointed at a repository you care about.

---

## Gate 0 — repo hygiene (Plan 1, Task 0)

Run this first. It is thirty seconds and it prevents a painful history rewrite.

```bash
cd "$IMPLR"
git status --porcelain | grep -E "__pycache__|node_modules|\.egg-info|dist/" && echo "FAIL: build artefacts are untracked-visible" || echo "OK: nothing stray"
PYTHONPATH=scripts python -m implr_validate --repo --root .
```

Expected: `OK: nothing stray`, then `implr-validate: OK` and exit `0`.

The second command is also a **performance** gate. After Plan 5 runs `npm install`,
`check_repo_prose` walks every `.md`/`.yaml` under the repo root — if `node_modules/` is not
in `repo_prose_checks.exempt_paths`, this goes from under a second to tens of seconds. If it
feels slow, that exemption is missing.

---

## Plan 1 — Foundation (pure data)

### What exists after this plan

`studio/backend/implr_studio/` with `implr_bridge`, `registry`, `pipeline`, `gates`. All
synchronous, filesystem-only. Plus `check_step_registry` inside `implr_validate`.

### Automated gate

```bash
cd "$IMPLR/studio/backend"
python -m pip install -e ".[dev]"
python -m pytest -v

cd "$IMPLR"
python -m pytest tests/ -q                                    # 68 pre-existing + new
PYTHONPATH=scripts python -m implr_validate --repo --root .
```

Expected: studio suite green; root suite green with **68 pre-existing tests still passing**;
`implr-validate` exits `0` and prints exactly two `info:` lines naming `qa-testing` and
`sec-review`. An `error:` line here means the shipped registry is malformed — most likely an
agent with no `.claude/agents/<name>.md`, or a `produces_artefact` that is not a real type.

### Runtime probe

This plan has no server and no CLI, so the probe is a real interpreter session against the
real schema files. It exercises the three things this plan exists to do:

```bash
cd "$IMPLR/studio/backend"
python - <<'EOF'
from pathlib import Path
from implr_studio import gates, implr_bridge, pipeline, registry

root = implr_bridge.repo_root()
contracts = implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))
reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

# 1. The catalogue loads, with availability and agents.
print("--- steps ---")
for step in reg.steps.values():
    agents = ", ".join(a.name for a in step.agents) or "-"
    print("%-22s %-12s available=%-5s agents=%s"
          % (step.id, step.phase, step.available, agents))

# 2. A gate demanding an illegal status is refused, and the message names the
#    legal ones. This is the headline payoff of the Python backend.
bad = pipeline.Gate(type="artifact", artefact="plan",
                    quantifier="all", require={"status": "complete"})
print("\n--- illegal gate ---")
for f in gates.validate_gate(bad, contracts):
    print(f.code, "|", f.message)

# 3. A value-taking flag with no value is refused at save time.
p = pipeline.pipeline_from_dict({
    "version": 1,
    "nodes": [{"id": "build", "step": "dev-executor", "args": ["--task"]}],
    "edges": [],
})
print("\n--- missing arg value ---")
for f in pipeline.validate_pipeline(p, reg):
    print(f.code, "|", f.message)

# 4. And a shell-metacharacter value is refused by pattern.
p = pipeline.pipeline_from_dict({
    "version": 1,
    "nodes": [{"id": "build", "step": "dev-executor", "args": ["--task"],
               "arg_values": {"--task": "x; rm -rf /"}}],
    "edges": [],
})
print("\n--- injection attempt ---")
for f in pipeline.validate_pipeline(p, reg):
    print(f.code, "|", f.message)
EOF
```

Expected: nine steps listed with `qa-testing` / `sec-review` at `available=False` and no
agents; then `illegal-status` naming `ready, in-progress, done, blocked, needs-rework`; then
`missing-arg-value` naming `--task`; then `bad-arg-value`.

Then the empty-match-set rule, which is easy to get backwards:

```bash
cd "$IMPLR/studio/backend"
python - <<'EOF'
from pathlib import Path
from implr_studio import gates, implr_bridge, pipeline

ws = Path("/tmp/studio-probe")     # PowerShell: use your $PROBE path
contracts = implr_bridge.load_contracts(
    str(implr_bridge.resolve_schema_dir(implr_bridge.repo_root())))
g = pipeline.Gate(type="artifact", artefact="requirement",
                  quantifier="all", require={"status": "approved"})

print("no requirements exist ->", gates.evaluate_gate(g, ws, contracts))

d = ws / "docs" / "implr" / "requirements" / "functional"
d.mkdir(parents=True, exist_ok=True)
(d / "req-f-001.md").write_text(
    "---\nreq_id: REQ-F-001\nstatus: draft\n---\nbody\n", encoding="utf-8")
print("one draft requirement   ->", gates.evaluate_gate(g, ws, contracts))

(d / "req-f-001.md").write_text(
    "---\nreq_id: REQ-F-001\nstatus: approved\n---\nbody\n", encoding="utf-8")
print("one approved requirement->", gates.evaluate_gate(g, ws, contracts))
EOF
```

Expected: `False`, `False`, `True`. The first `False` is the one that matters — an `all`
gate over zero files must not open.

### Not testable yet

Nothing executes. There is no orchestrator, no HTTP, no model. A green suite here says the
data model is sound; it says nothing about whether a pipeline can run.

---

## Plan 2 — Executor contract

### What exists after this plan

`executors/base.py` (types + Protocol) and `executors/fake.py`. No I/O, no provider.

### Automated gate

```bash
cd "$IMPLR/studio/backend"
python -m pytest tests/test_executor_base.py tests/test_fake_executor.py -v
```

Two assertions in there carry more weight than the rest:

- `test_base_module_names_no_provider` — greps `base.py` for vendor and transport words. If
  it fails, the abstraction has already leaked and Phase 2 is dead.
- `test_question_can_be_answered_after_the_iterator_is_abandoned` — the contract the
  orchestrator actually relies on. An executor can pass every other question test and still
  fail this one, because the others keep consuming the stream and the orchestrator does not.

### Runtime probe

There is deliberately no probe. This plan is a Protocol and a test double; the only thing to
run is the suite. Any "probe" would be a test wearing a costume.

What you *can* do is confirm the contract is honoured structurally:

```bash
cd "$IMPLR/studio/backend"
python - <<'EOF'
import inspect
from implr_studio.executors import base, fake

print("FakeExecutor satisfies StepExecutor:",
      isinstance(fake.FakeExecutor(), base.StepExecutor))
print("event kinds:", base.EVENT_KINDS)

src = inspect.getsource(base).lower()
leaked = [w for w in ("claude", "anthropic", "openai", "gpt", "gemini", "subprocess")
          if w in src]
print("provider words in base.py:", leaked or "none")

# The arming rule: pending_question must be set before the question is yielded.
body = inspect.getsource(fake.FakeExecutor.events)
arm = body.index("pending_question")
yld = body.index("yield event")
print("question armed before yield:", arm < yld)
EOF
```

Expected: `True`, the four kinds, `none`, `True`.

### Not testable yet

`FakeExecutor` proves the orchestrator can be driven; it proves nothing about whether a real
provider can be. That is Plan 6, and only its live suite settles it.

---

## Plan 3 — Orchestrator & persistence (backend)

### What exists after this plan

`runstate`, `store` (SQLite), `orchestrator` — the full run lifecycle, driven entirely
through `FakeExecutor`.

### Automated gate

```bash
cd "$IMPLR/studio/backend"
python -m pytest tests/test_store.py tests/test_orchestrator_*.py -v
```

### Runtime probe

Drive a real pipeline end to end with no model and no HTTP. This is the first probe that
proves something *executes*:

```bash
cd "$IMPLR/studio/backend"
python - <<'EOF'
import asyncio, tempfile
from pathlib import Path

from implr_studio import implr_bridge, orchestrator, pipeline, registry
from implr_studio import runstate as rs
from implr_studio.executors import base
from implr_studio.executors.fake import FakeExecutor
from implr_studio.store import Store

root = implr_bridge.repo_root()
contracts = implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))
reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

PIPE = {
    "version": 1,
    "nodes": [
        {"id": "ingest", "step": "doc-ingest"},
        {"id": "arch",   "step": "arch-gen"},
        {"id": "reqs",   "step": "ba-requirements-gen"},
    ],
    "edges": [
        {"from": "ingest", "to": "arch", "gate": {"type": "none"}},
        {"from": "arch", "to": "reqs", "gate": {
            "type": "artifact", "artefact": "requirement",
            "quantifier": "all", "require": {"status": "approved"}}},
    ],
}


async def main():
    tmp = Path(tempfile.mkdtemp())
    store = Store(tmp / "runs.db")
    ex = FakeExecutor({
        "doc-ingest": [base.StepEvent.log("scanning 34 docs"),
                       base.StepEvent.done("success", "12 digested")],
        "arch-gen":   [base.StepEvent.log("11 decisions inferred"),
                       base.StepEvent.question("q1", "Postgres or MySQL?",
                                               options=["Postgres", "MySQL"]),
                       base.StepEvent.log("noted"),
                       base.StepEvent.done("success", "ARCHITECTURE.md written")],
    }, default=[base.StepEvent.done("success", "ok")])

    orch = orchestrator.Orchestrator(tmp, reg, contracts, ex, store)
    p = pipeline.pipeline_from_dict(PIPE)

    run_id = await orch.start_run(p)
    await orch.wait_quiescent(run_id)
    print("1. after start        ", orch.node_statuses(run_id), orch.run_status(run_id))

    q = store.pending_question(run_id, "arch")
    print("2. question surfaced  ", q["prompt_md"], "| options:", q["options"])

    await orch.answer(run_id, q["id"], "Postgres")
    await orch.wait_quiescent(run_id)
    print("3. after answering    ", orch.node_statuses(run_id), orch.run_status(run_id))
    print("   step started once? ", [r.skill for r in ex.started])

    # reqs is BLOCKED: no approved requirements exist on disk.
    d = tmp / "docs" / "implr" / "requirements" / "functional"
    d.mkdir(parents=True, exist_ok=True)
    (d / "req-f-001.md").write_text(
        "---\nreq_id: REQ-F-001\nstatus: approved\n---\nb\n", encoding="utf-8")

    await orch.retry(run_id, "reqs") if False else None
    orch._spawn_driver(run_id)              # re-evaluate now the gate can open
    await orch.wait_quiescent(run_id)
    print("4. gate opened        ", orch.node_statuses(run_id), orch.run_status(run_id))

    # Restart recovery: a node persisted as running did not survive.
    store.set_node_status(run_id, "reqs", rs.RUNNING)
    store.close()
    store2 = Store(tmp / "runs.db")
    orch2 = orchestrator.Orchestrator(tmp, reg, contracts, FakeExecutor(), store2)
    print("5. recovered runs     ", orch2.recover())
    print("   reqs is now        ", orch2.node_statuses(run_id)["reqs"])
    print("   error says         ", store2.get_node(run_id, "reqs")["error"])
    store2.close()

asyncio.run(main())
EOF
```

Expected, line by line:

1. `ingest` succeeded, `arch` **awaiting-input**, `reqs` pending; run **paused**.
2. The question text and its two options, read back out of SQLite.
3. All three of `ingest`/`arch` succeeded, `reqs` **blocked** — and `ex.started` lists
   `doc-ingest` and `arch-gen` **once each**. If `arch-gen` appears twice, answering
   restarted the step instead of resuming its stream, and the agent lost its context.
4. `reqs` succeeded once an approved requirement exists on disk. The gate opened because the
   *filesystem* changed, not because any event said so.
5. `['<run id>']`, then `failed`, then an error naming the restart.

### Not testable yet

No HTTP, no browser, no model. Concurrency is capped at 1, so nothing here exercises
parallel branches beyond proving they queue.

---

## Plan 4 — HTTP & WebSocket API

### What exists after this plan

`context`, `serialize`, `api`, `server` and the `implr-studio` console script. The whole
backend is now reachable over loopback.

### Automated gate

```bash
cd "$IMPLR/studio/backend"
python -m pip install -e ".[dev]"          # picks up fastapi/uvicorn/httpx
python -m pytest -v
```

Security assertions worth reading the output for:

- `test_no_route_accepts_a_filesystem_path` — scans `/openapi.json` for any parameter that
  would let a request redirect execution at another directory.
- `test_server_binds_localhost_only` — greps `server.py` for `0.0.0.0` and `--host`.
- `test_start_returns_202_before_the_run_finishes` — the step parks on an unanswered
  question, so a blocking start would hang this test rather than pass it slowly.

### Runtime probe

Start the real server against the throwaway workspace, with the scripted executor so
nothing costs a token:

```bash
cd "$IMPLR/studio/backend"
implr-studio --fake --workspace "$PROBE" &
sleep 2
```

PowerShell: `Start-Process -NoNewWindow implr-studio -ArgumentList '--fake','--workspace',"$env:PROBE"`

**1. Bound to loopback only.** The single most important check in this document:

```bash
curl -s -o /dev/null -w "loopback: %{http_code}\n" http://127.0.0.1:8765/api/registry
curl -s -m 3 -o /dev/null -w "external: %{http_code}\n" "http://$(hostname):8765/api/registry" || echo "external: refused (correct)"
```

Expected: `loopback: 200`, and the second **refused or timing out**. If the second returns
200 the service is reachable off-box, which is a deployment failure, not a feature.

**2. The registry populates the whole configurator in one call:**

```bash
curl -s http://127.0.0.1:8765/api/registry | python -m json.tool | head -60
curl -s http://127.0.0.1:8765/api/registry | python -c "
import json,sys
d = json.load(sys.stdin)
print('steps        :', len(d['steps']))
print('phases       :', d['phases'])
print('tiers        :', d['tiers'])
print('contracts    :', sorted(d['contracts']))
print('plan states  :', d['contracts']['plan']['states'])
print('agent tiers  :', d['agent_defaults'] or '(all project defaults)')
print('agent tools  :', sorted(d['agent_tools'])[:4], '...')
ex = next(s for s in d['steps'] if s['id']=='dev-executor')
print('executor args:', [a['flag'] for a in ex['args_allowed']])
print('  --task takes a value:', next(a for a in ex['args_allowed'] if a['flag']=='--task')['takes_value'])
print('executor agents:', [a['name'] for a in ex['agents']])
"
```

Expected: 9 steps, six phases, three tiers, the four artefact types, the five real plan
states, eleven agents with their declared tools, and `dev-executor` reporting `--task` as
value-taking with three dispatched agents.

**3. Save is refused for an impossible condition:**

```bash
curl -s -X PUT http://127.0.0.1:8765/api/pipeline \
  -H 'Content-Type: application/json' \
  -d '{"version":1,
       "nodes":[{"id":"plan","step":"dev-planner","args":[],"position":{"x":0,"y":0}},
                {"id":"build","step":"dev-executor","args":["--all"],"position":{"x":200,"y":0}}],
       "edges":[{"from":"plan","to":"build",
                 "gate":{"type":"artifact","artefact":"plan","quantifier":"all",
                         "require":{"status":"complete"}}}]}' \
  -w "\nHTTP %{http_code}\n" | python -m json.tool 2>/dev/null || true

ls "$PROBE/docs/implr/config/pipeline.yaml" 2>/dev/null && echo "FAIL: rejected save wrote a file" || echo "OK: nothing written"
```

Expected: `HTTP 422`, an `illegal-status` finding whose message names the five legal plan
states, and **no file on disk**.

**4. A value-taking flag with no value is refused:**

```bash
curl -s -X PUT http://127.0.0.1:8765/api/pipeline \
  -H 'Content-Type: application/json' \
  -d '{"version":1,"nodes":[{"id":"build","step":"dev-executor","args":["--task"],"position":{"x":0,"y":0}}],"edges":[]}' \
  -w "\nHTTP %{http_code}\n"
```

Expected: `422` with `missing-arg-value`.

**5. A valid save, then a run that streams:**

```bash
curl -s -X PUT http://127.0.0.1:8765/api/pipeline \
  -H 'Content-Type: application/json' \
  -d '{"version":1,
       "nodes":[{"id":"ingest","step":"doc-ingest","args":[],"position":{"x":0,"y":0}},
                {"id":"arch","step":"arch-gen","args":[],"position":{"x":240,"y":0}}],
       "edges":[{"from":"ingest","to":"arch","gate":{"type":"none"}}]}' \
  -w "\nHTTP %{http_code}\n"

cat "$PROBE/docs/implr/config/pipeline.yaml"

RUN=$(curl -s -X POST http://127.0.0.1:8765/api/runs -w "\n%{http_code}\n")
echo "$RUN"
```

Expected: `200` on the save; the YAML on disk using `from:`/`to:` keys; then **`202`** with a
`run_id`. A `200` here means someone reintroduced a blocking start.

**6. The WebSocket actually streams, and replays from a cursor:**

```bash
cd "$IMPLR/studio/backend"
RUN_ID=$(curl -s -X POST http://127.0.0.1:8765/api/runs | python -c "import json,sys; print(json.load(sys.stdin)['run_id'])")
python - "$RUN_ID" <<'EOF'
import asyncio, json, sys
import websockets                    # ships with uvicorn[standard]

run_id = sys.argv[1]

async def main():
    url = "ws://127.0.0.1:8765/api/runs/%s/stream?cursor=0" % run_id
    seen, last = 0, 0
    async with websockets.connect(url) as ws:
        try:
            while True:
                frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if frame["type"] == "events":
                    for e in frame["events"]:
                        seen += 1
                        last = e["seq"]
                        print("  seq=%-3d %-8s %s" % (e["seq"], e["kind"],
                              str(e["payload"])[:70]))
                elif frame["type"] == "run-status":
                    print("  run-status:", frame["status"])
                elif frame["type"] == "error":
                    print("  error:", frame["message"]); break
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            pass
    print("events received:", seen)

    # Reconnect from the last cursor: must return nothing already seen.
    async with websockets.connect(
            "ws://127.0.0.1:8765/api/runs/%s/stream?cursor=%d" % (run_id, last)) as ws:
        try:
            while True:
                frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if frame["type"] == "events":
                    stale = [e["seq"] for e in frame["events"] if e["seq"] <= last]
                    print("stale replays:", stale or "none")
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            print("cursor replay clean")

asyncio.run(main())
EOF
```

Expected: a stream of `status` and `log` events, a terminal `run-status`, then
`cursor replay clean` with no stale sequence numbers.

**7. The root page explains itself before the UI is built:**

```bash
curl -s http://127.0.0.1:8765/ | head -20
```

Expected: an HTML page naming `npm run dev` / `npm run build`. **Never** a 404 — someone who
runs the server and opens the URL must be told what to do next.

**8. Operator actions:**

```bash
R=$(curl -s -X POST http://127.0.0.1:8765/api/runs | python -c "import json,sys; print(json.load(sys.stdin)['run_id'])")
sleep 1
curl -s http://127.0.0.1:8765/api/runs/$R | python -m json.tool | head -30
curl -s -X POST http://127.0.0.1:8765/api/runs/$R/nodes/ingest/retry -w "\nretry(succeeded node): %{http_code}\n"
curl -s -X POST http://127.0.0.1:8765/api/runs/$R/cancel -w "\ncancel: %{http_code}\n"
```

Expected: run detail with per-node status; `409` for retrying a node that did not fail;
`200` for cancel.

Stop the server: `kill %1` (bash) / `Stop-Process -Name implr-studio` (PowerShell).

### Not testable yet

No UI. And `--fake` means nothing has verified that a real provider can run an implr step —
the API is proven, the execution is simulated.

---

## Plan 5 — Frontend (UI)

### What exists after this plan

`studio/frontend/` — the console, the step configurator, run mode, and `tokens.css` as the
shipped design system.

### Automated gate

```bash
cd "$IMPLR/studio/frontend"
npm install
npm test
npm run build          # typecheck + bundle
```

`src/tokens.test.ts` is the design gate, and it is the one to watch. It fails the build if:

- a reserved token group is missing;
- `app.css` introduces **any** saturated hex of its own (colour must always be data);
- a `prefers-color-scheme` query appears (dark is the product default, not the OS's choice);
- a `font-family` has no fallback stack.

### Runtime probe

Two terminals. Backend with the scripted executor, frontend from Vite:

```bash
# terminal 1
cd "$IMPLR/studio/backend" && implr-studio --fake --workspace "$PROBE"

# terminal 2
cd "$IMPLR/studio/frontend" && npm run dev
```

Open the address Vite prints. Vite proxies `/api` to `127.0.0.1:8765`, which is why no
frontend file contains a host or a port.

Walk this list. Each item maps to a design decision, and the *expected* column is what
failure looks like if you skim:

| # | Do this | Expect | Fails as |
|---|---|---|---|
| 1 | Load the page with no OS dark mode | Dark console | Light UI → a `prefers-color-scheme` query crept in |
| 2 | Search the palette for `security` | Only Security Checks, dashed, not draggable | Draggable → availability not wired |
| 3 | Drag Document Ingestion onto the canvas | Node appears where dropped | Appears at origin → `screenToFlowPosition` missing |
| 4 | Drag from a node's right port to another's left | Edge appears | No edge → `onConnect` not wired |
| 5 | Click the Implementation node | Configurator opens on **Run** | Inline panel → old design |
| 6 | Run tab: look at `--task` | Value input present but **disabled** | Enabled → the flag/value coupling is missing |
| 7 | Tick `--task`, leave value blank | Inline *needs a value* | Nothing → G1 not closed |
| 8 | Type `has space` into it | Inline *not a valid value* | Accepted → pattern not applied |
| 9 | Type `PLAN-F-004#3` | Warning clears; node shows `--task PLAN-F-004#3` | Node shows bare `--task` → value not rendered |
| 10 | Agents tab | `arch-excerpter`, `plan-runner`, `task-executor` with fan-out and tool chips | Empty → registry `agents` not served |
| 11 | Note which tools are tinted | `Write`/`Edit`/`Bash`/`Agent` distinct | All same → mutating tools not marked |
| 12 | Drop `task-executor` to Sonnet | Marked *overridden*; node tier dots change; footer gains `implr.config.yaml` | No footer change → override not tracked |
| 13 | Set it back to the project default | Override **clears** (no `models` entry) | Still marked overridden → default was pinned, not cleared |
| 14 | Right rail | Model-mix meter shifts; "most expensive" names a step | Static → `mixFor` not wired |
| 15 | Input tab | Read paths, the inbound condition, and a *descriptive only* banner | No banner → implies enforcement that does not exist |
| 16 | Output tab on the Planning node | 10 required `plan` fields, 5 legal statuses, path glob | Hardcoded-looking list → not read from `contracts` |
| 17 | Press Escape | Modal closes | Stays → keyboard handling missing |
| 18 | Click the `plan → build` edge | Gate editor; status dropdown offers only plan states | Offers `approved` → wrong machine |
| 19 | Read the sentence under it | *"Implementation starts once at least one plan is ready."* | Missing → `gateSentence` not wired |
| 20 | Set the gate to `manual` | Warning about approval being per step | Missing → G3 not surfaced |
| 21 | Press Save | `pipeline.yaml` appears in `$PROBE` | 422 → check the findings in the rail |
| 22 | Press Run pipeline | Nodes tint and logs fill **progressively** | All at once at the end → a blocking start returned |
| 23 | Reach an `awaiting-input` node | Question card with the agent's options as buttons **and** a free-text box | Only text box → options not rendered |
| 24 | Find a `blocked` node | Explanation that it advances on its own, **no** Approve button | Approve shown → blocked confused with awaiting-approval |
| 25 | In devtools: `document.documentElement.dataset.theme = 'light'` | Everything stays legible | Unreadable text → a colour defined only in a dark block |

Confirm what the UI actually wrote:

```bash
cat "$PROBE/docs/implr/config/pipeline.yaml"
```

Expected: `arg_values` and `models` present only on the nodes where you set them, and absent
everywhere else.

**Single-process check** — the built bundle served by the backend, no Vite:

```bash
cd "$IMPLR/studio/frontend" && npm run build
cd "$IMPLR/studio/backend" && implr-studio --fake --workspace "$PROBE"
curl -s http://127.0.0.1:8765/ | head -5              # the SPA, not the "not built" page
curl -s -o /dev/null -w "api still wins: %{http_code}\n" http://127.0.0.1:8765/api/registry
```

Expected: SPA HTML, and `200` from `/api/registry` — the catch-all mount must not shadow the
API.

### Not testable yet

Drag-and-drop is not simulable in jsdom (`dataTransfer` is unimplemented), which is why
items 3–4 above are manual. And every step you ran was scripted — no model has been invoked.

---

## Plan 6 — Claude Code adapter

### What exists after this plan

`_sdk` (import seam, prompt, permissions, tier mapping), `translate` (pure), `claude_code`
(the adapter), and an opt-in live suite.

### Automated gate — free

```bash
cd "$IMPLR/studio/backend"
python -m pip install -e ".[dev]"
python -m pytest -v                          # live tests are deselected by addopts
python -m pytest -m live --collect-only      # confirms they exist but are excluded
```

Expected: the default run collects **no** live test; the second command lists them.

Then verify the three permission facts by inspection, because each one silently disables a
whole feature if it regresses:

```bash
cd "$IMPLR/studio/backend"
python - <<'EOF'
import inspect
from implr_studio.executors import _sdk

print("AskUserQuestion allowlisted:",
      "AskUserQuestion" in _sdk.ALLOWED_TOOLS, "(must be False)")
print("  reason: a whole-tool allow entry auto-approves BEFORE can_use_tool runs,")
print("          which would silently disable every operator question.")
print("skills option           :", _sdk.SKILLS, "(must be 'all')")
print("  reason: the SDK gates the Skill tool behind it; without it no implr")
print("          step can be invoked at all.")
print("Agent tool allowlisted  :", "Agent" in _sdk.ALLOWED_TOOLS, "(must be True)")
print("permission mode         :", _sdk.PERMISSION_MODE, "(must be acceptEdits)")

src = inspect.getsource(_sdk)
banned = [w for w in ("bypassPermissions", "dangerously-skip-permissions") if w in src]
print("dangerous flags         :", banned or "none")

print("prompt:", repr(_sdk.build_prompt("dev-executor", ("--all",))[:48]), "…")
print("answer template renders:", "\\n\\n" in repr(_sdk.ANSWER_TEMPLATE))
EOF
```

If `claude-agent-sdk` is installed, also confirm the adapter's options are ones the SDK
actually accepts — this catches an SDK upgrade breaking the contract:

```bash
cd "$IMPLR/studio/backend"
python - <<'EOF'
import dataclasses, typing
from claude_agent_sdk import ClaudeAgentOptions
from implr_studio.executors import _sdk

fields = {f.name: f for f in dataclasses.fields(ClaudeAgentOptions)}
legal = typing.get_args(fields["permission_mode"].type)
print("permission_mode accepted:", _sdk.PERMISSION_MODE in legal)
for name in ("skills", "agents", "allowed_tools", "can_use_tool", "cwd"):
    print("option present:", name, name in fields)
EOF
```

### Runtime probe — **costs tokens**

Everything above is free. The two probes below call a real model. They are the only place
the two undecidable assumptions get settled, and both are worth the spend once.

**A. A real slash command must invoke a real skill.** If this fails, no pipeline runs at
all — and the entire stubbed suite stays green while it is broken. Run this first:

```bash
cd "$IMPLR/studio/backend"
python -m pytest tests/test_claude_live.py -m live -k slash_command -v
```

**B. The agent must treat a permission denial as an answer.** This is the return path for
every operator reply:

```bash
python -m pytest tests/test_claude_live.py -m live -v
```

If B fails, the fix is the Phase 2 follow-up — edit `arch-gen` and `dev-planner` to call
`AskUserQuestion` directly — **not** a prose-parsing heuristic.

**C. End to end, for real.** The full stack against a real model, on a throwaway workspace.
This is the only command in this document that both spends tokens and writes files:

```bash
cd "$IMPLR/studio/backend"
implr-studio --workspace "$PROBE" &          # NOTE: no --fake
sleep 2
curl -s -X PUT http://127.0.0.1:8765/api/pipeline \
  -H 'Content-Type: application/json' \
  -d '{"version":1,"nodes":[{"id":"ingest","step":"doc-ingest","args":["--dry-run"],"position":{"x":0,"y":0}}],"edges":[]}'
curl -s -X POST http://127.0.0.1:8765/api/runs
```

Then watch it in the browser (`npm run dev` in terminal 2) and confirm:

- log lines arrive **while the step is still running**, not in one burst at the end;
- the step reports `succeeded`, not `failed` with "the session ended without reporting a
  result";
- `$PROBE/docs/implr/kb-index/` is untouched, because `--dry-run` was passed.

Use `--dry-run` first. Only drop it once A, B and C have all passed.

### Not testable offline

Both A and B, by construction. A green offline suite for Plan 6 means the translation and
control flow are right; it says nothing about whether the CLI resolves `/doc-ingest` or
whether the model reads a denial as an answer.

---

## Full-stack acceptance

After all six plans, walk the spec's success criteria. Each maps to something above:

| # | Criterion | Verified by |
|---|---|---|
| 1 | Compose the six-step pipeline by dragging and save valid YAML | Plan 5 probe, items 3–4, 21 |
| 2 | An illegal gate status is refused at save time, naming the legal states | Plan 4 probe 3; Plan 5 item 18 |
| 3 | A run streams live to the browser | Plan 5 item 22; Plan 4 probe 6 |
| 4 | An interactive step's question reaches the browser and the answer reaches the step | Plan 3 probe steps 2–3 (scripted); Plan 6 probe B (real) |
| 5 | An artefact gate holds until the frontmatter satisfies it, then opens unaided | Plan 3 probe step 4 |
| 6 | Restart mid-run recovers: done stays done, the interrupted node reports failed | Plan 3 probe step 5 |
| 7 | Both suites pass with no LLM invoked | Plans 1–5 automated gates |
| 8 | The configurator's Agents tab lists real agents with `implr.config.yaml` defaults | Plan 5 items 10–13 |
| 9 | A value-taking flag is validated, and reaches the executor as separate argv elements | Plan 5 items 6–9; Plan 1 probe |
| 10 | The Output tab renders the real `plan` contract | Plan 5 item 16 |
| 11 | `POST /api/runs` returns before the first node finishes | Plan 4 probe 5 |
| 12 | Dark with no stamp and on a light OS; light only when stamped | Plan 5 items 1, 25 |

### One-command regression sweep

Everything free, in order, from the repo root:

```bash
cd "$IMPLR" \
  && PYTHONPATH=scripts python -m implr_validate --repo --root . \
  && python -m pytest tests/ -q \
  && (cd studio/backend && python -m pytest -q) \
  && (cd studio/frontend && npm test && npm run build) \
  && echo "ALL FREE GATES PASS"
```

No model is invoked. Suitable for a pre-commit hook or CI.

---

## Troubleshooting

Symptoms drawn from the failure modes these plans are built to avoid:

| Symptom | Likely cause | Where to look |
|---|---|---|
| `ModuleNotFoundError: implr_validate` | `scripts/` not on the path | `PYTHONPATH=scripts` |
| `implr-validate` reports an `error:` for the registry | An agent has no `.claude/agents/<name>.md`, or `produces_artefact` is not a real type | `check_step_registry` |
| `implr-validate --repo` became slow | `node_modules/` not exempt from prose checks | `repo_prose_checks.exempt_paths` |
| Answering a question hangs forever | The executor arms the pending question *after* yielding it | Plan 2 arming rule; `fake.py events()` |
| `no pending question` on answer | Same cause, different timing | ditto |
| Answering restarts the step from the top | `_streams` not cached, or reset on resume | Plan 3 `_run_node` |
| A node stuck at `running`, route returns 500 | `_drive` missing its `except` | Plan 3 driver loop |
| `sqlite3` errors under load | A `Store` method not holding `self._lock` | Plan 3 `store.py` |
| Logs arrive only when the run ends | A route awaits `wait_quiescent` | Plan 4 run routes |
| `POST /api/runs` returns 200 not 202 | Same cause | ditto |
| The operator's question never appears | `AskUserQuestion` is in `allowed_tools` | Plan 6 `_sdk.ALLOWED_TOOLS` |
| Every step "succeeds" but does nothing | `skills` not passed, so the slash command was read as prose | Plan 6 `SKILLS` |
| A subagent dispatch is denied | `Agent` missing from the allowlist | ditto |
| A tier override makes an agent behave oddly | `AgentDefinition` built with an empty prompt, replacing the real one | Plan 6 `agent_definitions` |
| `_sdk` will not import | `ANSWER_TEMPLATE` has a literal newline instead of `\n\n` | Plan 6 Task 1 |
| Node text unreadable in light mode | A colour defined only inside a `[data-theme]` block | `tokens.css` |
| UI shows a status the backend never sends | A vocabulary hardcoded in TypeScript | must come from `/api/registry` |
