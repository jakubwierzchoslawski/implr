# implr Studio — Runtime Verification

**What this is:** the shared harness. The setup every probe needs, the free regression sweep,
the acceptance map, and the failure-mode table.

**What this is not:** the per-phase procedure. Each of the twenty-one phase documents carries
its own **Demo** section (the clickable proof) and **Definition of Done** (the checklist), and
those are authoritative. Duplicating them here would guarantee the two drift.

**Roadmap:** [`superpowers/plans/2026-08-25-studio-phases.md`](superpowers/plans/2026-08-25-studio-phases.md)
· **Design:** [`superpowers/specs/2026-08-25-implr-studio-design.md`](superpowers/specs/2026-08-25-implr-studio-design.md)
· **Hosted:** [`superpowers/specs/2026-08-25-implr-studio-hosted-design.md`](superpowers/specs/2026-08-25-implr-studio-hosted-design.md)

---

## How to verify a phase

Three things, in this order:

1. **The suite** — `python -m pytest` and, from Phase 0, `npm test && npm run build`.
   Table stakes. A green suite is not evidence the thing runs.
2. **The Demo** — in the phase document. A thing you click, and can hand to someone else to
   click. This is the gate.
3. **The Definition of Done** — in the phase document. The checklist, including the properties
   a demo cannot show (permission checks, source-level constraints, absence of a warning).

**"The tests pass" and "the thing runs" are different claims**, and the gap between them is
where this project's real risks live. Phase 15 is the extreme case: four failure modes there
pass every offline test while silently disabling a shipped feature.

---

## Where each phase's verification lives

| # | Phase | UI? | How you verify it |
|---|---|---|---|
| **−1** | [Restructure](superpowers/plans/2026-08-25-studio-phase-minus1-restructure.md) | no | **Backend/packaging.** `pip install -e packages/implr_validate` then `implr-validate --repo` from a directory that is not the repo root. No test contains `sys.path.insert`. |
| 0 | [Skeleton](superpowers/plans/2026-08-25-studio-phase-00-skeleton.md) | **yes** | `implr-studio --workspace $PROBE`, open the browser: dark shell, health dot goes green. Kill the server; the dot goes red. |
| 1 | [See the steps](superpowers/plans/2026-08-25-studio-phase-01-palette.md) | **yes** | Nine steps grouped by phase; the two uninstalled ones dashed; search filters. |
| 2 | [Draw a pipeline](superpowers/plans/2026-08-25-studio-phase-02-canvas.md) | **yes** | Drag two steps, connect, Save → `pipeline.yaml` on disk. Reload: the graph is intact. |
| 3 | [Refuse bad graphs](superpowers/plans/2026-08-25-studio-phase-03-validation.md) | **yes** | Make a cycle, Save. The finding is named; **nothing is written**. `git diff` proves it. |
| 4 | [Configure arguments](superpowers/plans/2026-08-25-studio-phase-04-arguments.md) | **yes** | Open a step, tick `--task`, type a value. A bad value is refused inline, before the request. |
| 5 | [Pick models](superpowers/plans/2026-08-25-studio-phase-05-models.md) | **yes** | Drop `task-executor` to Sonnet: node dots, mix meter and YAML all change. Select the default again → the override is **removed** from the YAML. |
| 6 | [Conditions](superpowers/plans/2026-08-25-studio-phase-06-conditions.md) | **yes** | Build an artefact gate. An illegal status is not offered — and is refused if you hand-edit it in. |
| 7 | [Input / Output tabs](superpowers/plans/2026-08-25-studio-phase-07-io-tabs.md) | **yes** | The Output tab shows the ten real `plan` fields. Switch to `review` (two fields) to prove nothing is hardcoded. |
| 8 | [Author a step](superpowers/plans/2026-08-25-studio-phase-08-author-a-step.md) | **yes** | **New step** → agent-backed → save. It appears in the palette, marked as yours. Then re-run the installer and confirm `steps.yaml` survived. |
| 9 | [Run one node](superpowers/plans/2026-08-25-studio-phase-09-run-one-node.md) | **yes** | Press Run; one node goes green. Free — `FakeExecutor`. |
| 10 | [Live logs](superpowers/plans/2026-08-25-studio-phase-10-live-logs.md) | **yes** | Lines appear **while** the step runs, not in one burst. Refresh mid-run: complete, no duplicates. |
| 11 | [Many nodes, real gates](superpowers/plans/2026-08-25-studio-phase-11-gates.md) | **yes** | A gate holds. Edit a file's frontmatter on disk. It opens with **no** operator action. |
| 12 | [Questions](superpowers/plans/2026-08-25-studio-phase-12-questions.md) | **yes** | Answer in the browser; the step continues in the **same** session — `len(ex.started) == 1`. |
| 13 | [Review & send back](superpowers/plans/2026-08-25-studio-phase-13-review.md) | **yes** | Reject with a note; it re-runs knowing why. Then retry an approved node and confirm it asks again. |
| 14 | [Failure & recovery](superpowers/plans/2026-08-25-studio-phase-14-failure-recovery.md) | **yes** | Script a failure: red node, run **paused**, downstream **pending**. Then `kill -9` mid-run, restart: done stays done, the interrupted node says **failed (restart)** and was not retried. |
| 15 | [Real model](superpowers/plans/2026-08-25-studio-phase-15-real-model.md) | **yes** (unchanged) | `implr-studio` with no `--fake`. A real `doc-ingest --dry-run` streams in. **The UI must not change** — `git diff --stat -- web/` is the assertion. **Costs tokens.** |
| 16 | [Containers](superpowers/plans/2026-08-25-studio-phase-16-containers.md) | **yes** | `docker compose up --build`. Palette from **Postgres**; run in a **separate container**. Then `docker run --rm implr-studio-api which git` → nothing. |
| 17 | [Tenancy & auth](superpowers/plans/2026-08-25-studio-phase-17-tenancy-auth.md) | **yes** | Two users in one tenant share the project list; a third tenant's user gets **404**. Then the RLS suite: an unscoped `SELECT` returns **zero rows**. |
| 18 | [Onboarding](superpowers/plans/2026-08-25-studio-phase-18-onboarding.md) | **yes** | A brand-new tenant: sign-in → repo → PR → template → six supervised dry-run steps, **under five minutes**, nothing committed. **Costs tokens.** |
| 19 | [Deploy to Azure](superpowers/plans/2026-08-25-studio-phase-19-deploy-azure.md) | **yes** | One `az deployment sub create`, then a real run streaming over HTTPS. Then each control verified: egress, private Postgres, no worker DB creds, least-privilege identities. **Costs tokens and money.** |

**Every phase has a UI demo except −1.** That was the point of re-cutting the work into vertical
slices: the one phase with no browser proof is the packaging restructure, and it is verified from
a shell instead.

**Token spend.** Phases −1 through 14 invoke **no model at all** — `FakeExecutor` arrives in
Phase 9 precisely so every run phase is free. Only 15, 18 and 19 cost anything.

---

## Prerequisites

```bash
python --version    # 3.11+ (repo currently runs 3.14.3)
node --version      # 18+, needed from Phase 0 onward
docker --version    # only from Phase 16
az --version        # only for Phase 19
```

Shell notes for this repo's primary environment (Windows + PowerShell). The bash forms match
the phase documents' own commit commands; PowerShell equivalents follow where they differ:

| Task | bash | PowerShell |
|---|---|---|
| Background a server | `cmd &` | `Start-Process -NoNewWindow cmd` |
| Stop a backgrounded server | `kill %1` | `Stop-Process -Name python` |
| Hard-kill for the Phase 14 probe | `kill -9 %1` | `Stop-Process -Name python -Force` |
| Set an env var for one command | `VAR=x cmd` | `$env:VAR="x"; cmd` |

**After Phase −1, `PYTHONPATH` is no longer needed.** `implr_validate` becomes a real installed
package with a console script:

```bash
pip install -e packages/implr_validate     # or: uv sync
implr-validate --repo --root .
```

Before Phase −1 lands, the old form still applies — every test file inserts `scripts/` on
`sys.path` itself, so running it as a module needs the path set explicitly:

```bash
PYTHONPATH=scripts python -m implr_validate --repo --root .
```

That divergence is exactly what Phase −1 removes, and it is why −1 comes first.

### One-time: build a throwaway workspace

Every probe from Phase 1 onward operates on a *target project*, never on this repo. Build a
disposable one with the real installer, so the fixture is a genuine implr workspace rather than a
hand-made approximation:

```bash
export IMPLR=$(pwd)                      # the implr repo
export PROBE=/tmp/studio-probe           # PowerShell: $env:PROBE="$env:TEMP\studio-probe"

rm -rf "$PROBE" && mkdir -p "$PROBE" && cd "$PROBE"
bash "$IMPLR/install.sh"                 # PowerShell: & "$env:IMPLR\install.ps1"
```

Invoke it as `bash install.sh` rather than `./install.sh` — on Windows the executable bit does
not survive a clone, so the direct form fails with "permission denied".

Confirm — these are the counts on a correct install:

```bash
ls "$PROBE/.claude/skills" | wc -l                      # 8 implr skills
ls "$PROBE/.claude/agents" | wc -l                      # 11 agent definitions
ls "$PROBE/docs/implr/config/implr.config.yaml"         # the agents: tier block lives here
ls "$PROBE/docs/implr/schemas/step-registry.json"       # only after Phase 1 has run
```

The agent count matters: Phase 1 asserts that every agent named in the shipped registry has a
definition, and Phase 5's tier selector reads its defaults from `implr.config.yaml`. A short
count here means a partial install, and several probes will fail for that reason rather than a
real one.

Note that `step-registry.json` is **absent** until Phase 1 ships it — the installer copies
`schemas/*.json`, so it appears in the workspace on the next install after Phase 1 lands. Before
then, `implr-studio` cannot start.

Add a small knowledge base so `doc-ingest` has something to read:

```bash
mkdir -p "$PROBE/docs/kb/billing"
cat > "$PROBE/docs/kb/billing/invoicing.md" <<'EOF'
# Invoicing rules

An invoice is issued monthly. Line items are immutable once issued.
Credit notes reference the original invoice. VAT is computed per line.
EOF
```

**Reset between probes:** `rm -rf "$PROBE" && ...` and re-run the installer. Nothing in this
document should ever be pointed at a repository you care about.

### One known gap in the fixture

`implr.config.yaml`'s commented `agents:` example names **`doc-ingest-extractor`**, whose agent
file the CHANGELOG records as removed. So the config's own example references an agent that does
not exist. This is harmless and it is a useful probe: Phase 15 asserts that
`agent_definitions` **skips** an agent whose file cannot be read rather than stubbing it, and
this is the real case to test it against.

---

## Gate 0 — repo hygiene

Run this first. Thirty seconds, and it prevents a painful history rewrite.

```bash
cd "$IMPLR"
git status --porcelain | grep -E "__pycache__|node_modules|\.egg-info|dist/" \
  && echo "FAIL: build artefacts are untracked-visible" || echo "OK: nothing stray"
implr-validate --repo --root .            # pre-Phase-−1: PYTHONPATH=scripts python -m implr_validate --repo --root .
```

Expected: `OK: nothing stray`, then `implr-validate: OK` and exit `0`.

The second command is also a **performance** gate. Once `npm install` has run,
`check_repo_prose` walks every `.md`/`.yaml` under the repo root — if `node_modules/` is not in
`repo_prose_checks.exempt_paths`, this goes from under a second to tens of seconds. If it feels
slow, that exemption is missing.

---

## The free regression sweep

Everything free, in order, from the repo root. Run this before every phase commit.

```bash
cd "$IMPLR" \
  && implr-validate --repo --root . \
  && python -m pytest tests/ -q \
  && python -m pytest packages/ -q \
  && (cd web && npm test && npm run build) \
  && echo "ALL FREE GATES PASS"
```

No model is invoked. Suitable for a pre-commit hook or CI.

**Three suites are deselected by default** and must stay that way, because each needs something
CI does not have:

| Marker | Needs | Introduced |
|---|---|---|
| `-m live` | an API key; **spends money** | Phase 15 |
| `-m docker` | a Docker daemon | Phase 16 |
| `-m postgres` | a Postgres instance | Phase 16 |
| `-m azure` | an Azure subscription; **spends money** | Phase 19 |

```bash
python -m pytest packages/ -q                 # the free suite
python -m pytest packages/ -m live -q         # opt in, costs tokens
python -m pytest packages/ -m postgres -q     # needs a database
```

A marker that is not registered in `pyproject.toml` becomes a silent typo — `-m liv` selects
nothing and reports success. Registering them is part of Phase 15's task list.

---

## Full-stack acceptance

After Phase 15, walk the design spec's success criteria. Each maps to a phase demo:

| # | Criterion | Verified by |
|---|---|---|
| 1 | Compose a pipeline by dragging and save valid YAML | Phase 2 demo |
| 2 | An illegal gate status is refused at save time, naming the legal states | Phase 6 demo |
| 3 | A run streams live to the browser | Phase 10 demo |
| 4 | A question reaches the browser and the answer reaches the step | Phase 12 (scripted) · Phase 15 (real) |
| 5 | An artefact gate holds until the frontmatter satisfies it, then opens unaided | Phase 11 demo |
| 6 | Restart mid-run recovers: done stays done, the interrupted node reports failed | Phase 14 demo, step 5 |
| 7 | Both suites pass with no LLM invoked | Phases −1–14 sweep |
| 8 | The Agents tab lists real agents with `implr.config.yaml` defaults | Phase 5 demo |
| 9 | A value-taking flag is validated, and reaches the executor as separate argv elements | Phase 4 demo · Phase 9 `build_argv` test |
| 10 | The Output tab renders the real `plan` contract | Phase 7 demo |
| 11 | `POST /api/runs` returns before the first node finishes | Phase 9 demo (202) · Phase 10 proves it |
| 12 | Dark with no stamp and on a light OS; light only when stamped | Phase 0 tokens guard |
| 13 | Every step can be human-in-the-loop, including root and terminal nodes | Phase 13 demo, steps 2–3 |
| 14 | A project can add a step implr does not ship | Phase 8 demo |

Then, after Phase 19, the hosted spec's criteria:

| # | Criterion | Verified by |
|---|---|---|
| 1 | `docker compose up` serves the console listing steps from the **database** | Phase 16 demo, step 2 |
| 2 | A custom skill is a row, appears in the palette, and is materialised into **only** its project's container | Phase 16 demo, step 6 |
| 3 | A skill named `../../etc/passwd` is rejected at write time | Phase 16 Task 5 |
| 4 | Two tenants are isolated, and an unscoped query returns zero rows | Phase 17 demo, steps 2–3 |
| 5 | A new tenant reaches a running pipeline in under five minutes | Phase 18 demo |
| 6 | The worker cannot reach the internet at large, or the database | Phase 19 demo, step 3 |

---

## Troubleshooting

Symptoms drawn from the failure modes these phases are built to avoid. **Sorted by how long
they take to diagnose without this table.**

### Setup and packaging

| Symptom | Likely cause | Where to look |
|---|---|---|
| `ModuleNotFoundError: implr_validate` | pre-Phase-−1: `scripts/` not on the path | `PYTHONPATH=scripts`, or land Phase −1 |
| `implr-validate` reports an `error:` for the registry | An agent has no `.claude/agents/<name>.md`, or `produces_artefact` is not a real type | `check_step_registry` |
| `implr-validate --repo` became slow | `node_modules/` not exempt from prose checks | `repo_prose_checks.exempt_paths` |
| `implr-studio` will not start: no registry | `step-registry.json` absent — the installer has not run since Phase 1 | re-run `install.sh` into `$PROBE` |
| A test passes that should not exist | A marker typo: `-m liv` selects nothing and exits 0 | `markers` in `pyproject.toml` |

### Run mode

| Symptom | Likely cause | Where to look |
|---|---|---|
| Logs arrive only when the run ends | A route awaits `wait_quiescent` | Phase 9 run routes; the source test |
| `POST /api/runs` returns 200 not 202 | Same cause | ditto |
| A fast run's log is empty | The socket closed on "terminal" without draining the backlog | Phase 10 stream handler |
| Answering a question hangs forever | The executor arms the pending question **after** yielding it | Phase 12 arming rule; `fake.py` |
| `no pending question` on answer | Same cause, different timing | ditto |
| Answering restarts the step from the top | `_streams` not cached, or popped in the question branch | Phase 12 `_run_node` |
| A second question fails after the first works | `_streams.pop` in the question branch rather than only the terminal one | ditto |
| A node stuck at `running`, route returns 500 | `_drive` missing its `except` | Phase 9 driver loop |
| `sqlite3` errors under load | A `Store` method not holding `self._lock` | Phase 9 `store.py` |
| A node stuck at `running` after a restart | `recover()` not wired, or wired as a background task | Phase 14 Task 4 |
| Approve is offered on a blocked node | `blocked` not outranking `awaiting-approval` in readiness | Phase 11 `node_readiness` |
| A gate opens with nothing on disk | Empty match set read as vacuously true | Phase 11 — it must be **False** |
| A re-run of an approved step is unsupervised | Approval stamps not cleared on retry | Phase 13 bookkeeping |
| Skipping a step opens a gate it should not | `skipped` treated as satisfying an artefact condition | Phase 14 — it satisfies the *dependency* only |

### The real model

| Symptom | Likely cause | Where to look |
|---|---|---|
| Every step "succeeds" but does nothing | `skills` not passed, so the slash command was read as prose | Phase 15 Task 0 — verify this **first** |
| The operator's question never appears | `AskUserQuestion` in `allowed_tools`, **or** `skills="all"` appending a bare `"Skill"` | Phase 15 — the shadow-warning test catches both |
| The agent apologises instead of continuing after an answer | `PermissionResultDeny(interrupt=True)` — it aborts the turn | Phase 15 Task 4 |
| A tier override makes an agent behave oddly | `AgentDefinition` built with an empty prompt, replacing the real one | Phase 15 `agent_definitions` |
| `maxTurns` has no effect | Passed as `max_turns` — `AgentDefinition` is camelCase for that field | ditto |
| A step fails with a bare stack trace | A budget or turn-cap stop not mapped to a readable summary | Phase 15 `translate.py` |
| Abort leaves a CLI process running | `aclose()` not disconnecting the client | Phase 15 Task 4 |

### Hosted

| Symptom | Likely cause | Where to look |
|---|---|---|
| The palette is empty on first boot | Plugin sync ran as a background task, after the router | Phase 16 Task 3 |
| A run works locally and hangs in compose | The worker cannot reach the callback, and exits 0 anyway | Phase 16 Task 7 |
| One tenant sees another's data | RLS enabled but inactive: the app role **owns** the tables | Phase 17 — `FORCE ROW LEVEL SECURITY` |
| A tenant can write another tenant's row | A policy with `USING` and no `WITH CHECK` | Phase 17 Task 3 |
| Requests intermittently see the wrong tenant | `SET` instead of `SET LOCAL` on a pooled connection | ditto |
| Everyone is logged out after a key rotation | JWKS cached with no unknown-`kid` refresh | Phase 17 Task 1 |
| Two tenants created for one company | `SELECT`-then-`INSERT` on first sign-in | Phase 17 Task 2 |
| A job fails instantly, "image pull error" | The FQDN allowlist is missing `mcr.microsoft.com` or the ACR blob endpoint | Phase 19 Task 2 |
| Everything works, nothing persists | The Postgres private DNS zone is not linked to the VNet | Phase 19 troubleshooting |
| Sign-in loops | The app registration's redirect URI does not match the Container Apps FQDN | ditto |

### UI

| Symptom | Likely cause | Where to look |
|---|---|---|
| Node text unreadable in light mode | A colour defined only inside a `[data-theme]` block | `tokens.css`; Phase 0 guard test |
| UI shows a status the backend never sends | A vocabulary hardcoded in TypeScript | it must come from `/api/.../registry` |
| The Output tab shows ten fields for every step | Same cause | Phase 7 — demo with `review` (two fields) |
| The log pane stays empty in hosted mode | The WebSocket has no token, or is blocked at ingress | Phase 17 Task 6; Phase 19 Task 5 |
| An unsaved pipeline is lost after an hour | A 401 on token expiry handled as a fatal error | Phase 17 Task 6 |
