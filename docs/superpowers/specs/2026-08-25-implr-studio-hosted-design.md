# Design Spec: implr Studio — Hosted on Azure

**Date:** 2026-08-25
**Status:** Draft — awaiting review. **Supersedes parts of** `2026-08-25-implr-studio-design.md`.
**Author:** jakubwierzchoslawski

---

## Read this first

The existing Studio spec makes three decisions **explicitly and deliberately**:

> The backend binds `127.0.0.1` only. Binding any other interface is not a configuration option.
>
> No authentication is implemented, because the service must never be reachable by anyone but the local operator. This is a constraint on deployment, not a gap to fill later.
>
> Do not put it behind a tunnel, a reverse proxy, or a port-forward.

Deploying to Azure reverses all three. That is not a configuration change — it is a
different product with a different threat model, because **the thing being deployed executes
an LLM agent that runs shell commands and writes files.** A network-reachable endpoint that
does that is remote code execution offered as a feature.

This document is the design for doing it anyway, safely. The single most important section is
*Isolation*, and if only one thing survives review it should be that one.

**What does not change:** the local mode. `implr-studio --workspace .` on a laptop stays
exactly as specified, loopback-only and unauthenticated. The hosted mode is a second
deployment target, not a replacement — and the two share the API and the UI but not the
execution model.

---

## Scope

### In scope

- Two deployment modes — `local` and `hosted` — from one codebase.
- Containerisation: an API image and a **separate, isolated worker image** for run execution.
- Postgres as the control-plane store, replacing SQLite in hosted mode.
- Skills and agents stored in the database, materialised to disk per run.
- Authentication, projects, and per-project isolation.
- Azure service topology, with infrastructure-as-code.
- A repository restructure that makes the above buildable.

### Out of scope

- Multi-region, HA, or autoscaling beyond Container Apps defaults.
- Billing, quotas, or usage metering.
- A migration path for existing local `runs.db` files. Local runs stay local.
- Running the *target repository* anywhere but a fresh clone per run.

---

## The decision that shapes everything else: what lives where

"Everything in a database" needs one qualification, and getting it wrong would destroy
implr's value proposition.

implr's entire output is **markdown files in your git repository** — `REQ-F-001.md`,
`PLAN-F-004.md`, `docs/ARCHITECTURE.md`, `REVIEW-*.md`, plus `src/**` and `tests/**`. Those
are deliverables. They are reviewable, diffable, and go through pull requests. Moving them
into a database would make them invisible to every tool your team already uses.

So the split is:

| | Control plane → **database** | Work product → **git** |
|---|---|---|
| What | steps, skills, agents, pipelines, runs, events, questions, users, projects | requirements, plans, reviews, `ARCHITECTURE.md`, source, tests |
| Why | needs querying, versioning, multi-user access, an API | needs diffing, review, PRs, blame |
| Lifetime | permanent, the service owns it | the customer's repo owns it |

**Gate evaluation still reads the filesystem** — of the *checked-out working copy* inside the
run's container. That is unchanged from the local design, and it is why gates keep working:
`docs/implr/requirements/**/*.md` exists because the repo was cloned, not because a database
row was rendered.

Everything else moves to Postgres. Including, notably, skills — which is the interesting case.

---

## Skills and agents: database as source, disk as projection

**The constraint:** the Claude Code CLI resolves skills from
`<cwd>/.claude/skills/<name>/SKILL.md`. You cannot hand it a database row. Verified against
`claude-agent-sdk` 0.2.144: the `skills` option is a *filter* over discovered skills, and
`plugins` accepts only local plugins. Agents are the exception — `ClaudeAgentOptions.agents`
takes programmatic `AgentDefinition` objects, so those need no disk at all.

**The design:** the database is the source of truth; the run's working directory is a
**projection** of it, built at run start and destroyed at run end. This is how CI works — git
is the source of truth, the runner checks out.

```
                    ┌─────────────────────────────┐
  plugin/skills/    │  Postgres                   │
  plugin/agents/ ──►│  skills, agents             │
  (image build,     │  (builtin + custom rows)    │
   or admin sync)   └──────────────┬──────────────┘
                                   │  materialise at run start
                                   ▼
                    <workspace>/.claude/skills/<name>/SKILL.md
                    <workspace>/.claude/agents/<name>.md
                                   │
                                   ▼
                         Claude Code CLI reads from disk
```

**Builtin skills are seeded from `plugin/skills/` in flight**, not baked into a migration.
On boot the API reads that directory, hashes each `SKILL.md`, and upserts any row whose hash
differs — so shipping a new skill version is an image deploy, and the folder stays the
authoring surface for builtins. A row whose `source = 'builtin'` is replaced on sync; a row
whose `source = 'custom'` is never touched.

**Custom skills are database-only and project-scoped.** This is the answer to *where do
custom skills live*: not in a folder anyone has to mount, and not in the customer's repo
where they would be overwritten by the next `install.sh`. They live in the `skills` table,
scoped to a project, edited through the UI, versioned by row.

**Availability** stops being a `stat()` and becomes a query: is there an enabled skill row
with this name for this project? That removes the local-mode footgun entirely — the
palette and the executor consult the same source.

### Materialisation is a security boundary, not a convenience

Writing skill text to disk means the run container's `.claude/` tree is **assembled from
database content**. Three rules follow, and all three are load-bearing:

1. **Names are validated on write, not on materialise.** A skill name must match
   `^[a-z][a-z0-9-]{0,63}$`. Without that, `name = "../../etc/cron.d/x"` is a path traversal
   with a database row as the payload.
2. **Only skills enabled for *this* project are written.** Materialising the global catalogue
   into every run leaks one tenant's custom skills into another's container.
3. **The materialised tree is inside the ephemeral workspace** and dies with the container.
   Nothing is written to a shared volume.

---

## Isolation: the part that matters

The API must never execute a step. Run execution happens in a **separate, single-use
container** with no access to anything the API can reach.

| Control | Local mode | Hosted mode |
|---|---|---|
| Who executes | the API process | a per-run Container Apps **Job** |
| Workspace | your repo, in place | a fresh `git clone`, destroyed after |
| Filesystem | your whole machine | read-only root; one writable ephemeral volume |
| Network egress | unrestricted | allowlist: Anthropic API, the git remote, nothing else |
| Identity | your user | non-root, no managed identity, no Key Vault access |
| Secrets | your env | injected per job, scoped to that job |
| Concurrency | 1 | 1 per run; N runs in parallel across jobs |
| Timeout | none | hard wall-clock cap, job killed |
| Blast radius | your machine | one clone of one branch |

**Why the API cannot execute.** The API holds the database connection, the managed identity,
and every tenant's data. A step runs `Bash`. If those share a process, one prompt away from
`psql` is every customer's data. This separation is not defence in depth; it is the only
defence.

**The worker has no database credentials.** It receives its work as a signed job payload
(pipeline, materialised skills, git ref, run id) and reports back over an authenticated
callback endpoint scoped to that single run id. It cannot read another run's state.

**Egress allowlist matters more than ingress.** An agent that can reach the open internet can
exfiltrate the repository it was just given. Container Apps with a VNet and a NAT gateway
plus an Azure Firewall FQDN rule is the mechanism.

### The Phase 8 problem, restated

Phase 8 lets an operator author an agent-backed step: an instruction, plus agents with their
own prompts and **tool grants**. Locally that is a text editor for your own machine. Hosted,
it is a web form that runs arbitrary prompts with `Bash` in your infrastructure.

The `tools ⊆ permitted set` check specified in Phase 8 stops being tidiness and becomes the
authorisation boundary. Hosted mode adds two more:

- **A per-project tool ceiling.** A project may be configured such that authored steps cannot
  request `Bash` at all — read-only agents only. Default for any project the operator does
  not own.
- **Authoring is a distinct permission** from running or designing. A viewer who can trigger
  a run must not be able to write the prompt that runs.

---

## Data model

Postgres. SQLAlchemy Core (not the ORM — the existing `store.py` is already hand-written SQL
and the query surface is small).

```sql
-- identity ------------------------------------------------------------------
users        (id, entra_oid unique, email, display_name, created_at)
projects     (id, slug unique, name, git_remote, default_branch, created_at)
memberships  (user_id, project_id, role)          -- role: owner|designer|operator|viewer
                                                  -- PK (user_id, project_id)

-- catalogue ----------------------------------------------------------------
skills       (id, project_id null, name, version, body, source, content_hash,
              enabled, created_at, updated_at)
             -- project_id NULL = builtin/global. source: 'builtin'|'custom'
             -- UNIQUE (coalesce(project_id,'00000000-...'), name)
agents       (id, project_id null, name, description, prompt, tools jsonb,
              default_tier, source, content_hash, enabled, ...)
steps        (id, project_id null, step_id, kind, label, phase, skill_name,
              instruction, args_allowed jsonb, args_default jsonb,
              agents jsonb, consumes jsonb, produces jsonb,
              produces_artefact, description, source, enabled, ...)
             -- replaces step-registry.json AND steps.yaml

-- design -------------------------------------------------------------------
pipelines    (id, project_id, name, graph jsonb, version, updated_by, updated_at)
             -- graph jsonb is exactly today's pipeline.yaml shape

-- execution ----------------------------------------------------------------
runs         (id, project_id, pipeline_id, git_ref, git_sha, status,
              started_by, created_at, updated_at, finished_at)
node_runs    (run_id, node_id, status, summary, error, manual_approved,
              started_at, finished_at)                     -- PK (run_id, node_id)
events       (seq bigserial, run_id, node_id, kind, payload jsonb, created_at)
questions    (id, run_id, node_id, prompt_md, options jsonb, answer,
              answered_by, answered_at, created_at)
```

Three notes on the shape:

- **`events.seq` stays a single monotonic sequence** because the WebSocket cursor-replay
  contract depends on it. `bigserial` global rather than per-run: gaps are fine, ordering is
  not.
- **`pipelines.graph` is jsonb, not normalised into node/edge tables.** It is read and written
  whole, validated as a unit, and never queried by node. Normalising it would buy nothing and
  cost every save a transaction over dozens of rows.
- **`steps` replaces both `step-registry.json` and `steps.yaml`.** In hosted mode the
  registry *is* a table. `project_id IS NULL` rows are the builtins synced from
  `plugin/steps/`; project rows are what Phase 8 authors. The merge rule stays the same — a
  project row may not shadow a builtin `step_id`.

### Local mode keeps SQLite

`store.py` gains a thin dialect seam. Local uses SQLite at
`docs/implr/.studio/runs.db` and reads the catalogue from files; hosted uses Postgres and
reads it from tables. The seam is one module, and the orchestrator does not know which it is
talking to — which is exactly the discipline the `StepExecutor` Protocol already applies to
providers.

**Large logs go to Blob Storage.** `events` keeps the recent tail (last N per run) and
archives beyond that, because a `dev-executor` run over twenty plans produces a lot of log
lines and Postgres is the wrong place for append-only text at volume.

---

## Repository restructure

Honest assessment of the current tree: it is a clean **plugin source tree** for a local
tool, and it has no packaging story at all. Specifically:

| Problem | Evidence | Why it blocks containerisation |
|---|---|---|
| No root manifest | no `pyproject.toml`, no lockfile, no `package.json` at root | a Dockerfile has nothing to `pip install` |
| `implr_validate` is vendored by shell | `cp -f "$VALIDATE_SRC"/*.py` in `install.sh` | every project gets a divergent copy; no version pin |
| Import by path hack | every test does `sys.path.insert(..., "scripts")` | breaks the moment it runs from `/app` |
| Named `scripts/` but is a library | `scripts/implr_validate/` is an importable package | misleading; excluded from packaging by convention |
| `skills/` at root, `agents` under `.claude/` | asymmetric | the plugin payload is split across two conventions for no reason |
| `scaffold/` holds four lifecycles | schemas, templates, config, seeds | contracts are code-adjacent; templates are user-facing |
| Installer triplicated | `install.sh`, `.ps1`, `.bat` hand-synced | three chances to diverge |

### Proposed layout

```
implr/
├── pyproject.toml               # NEW  workspace root; declares the packages below
├── uv.lock                      # NEW  or requirements.lock — reproducible images
│
├── packages/
│   ├── implr_contracts/         # was scaffold/schemas/*.json  (+ a loader)
│   ├── implr_validate/          # was scripts/implr_validate/  — a real package
│   └── implr_studio/            # was studio/backend/implr_studio/
│
├── web/                         # was studio/frontend/
│
├── plugin/                      # everything installed INTO a target project
│   ├── skills/<name>/SKILL.md   # was skills/          (8)
│   ├── agents/<name>.md         # was .claude/agents/  (11)
│   ├── steps/step-registry.json # was scaffold/schemas/step-registry.json
│   ├── templates/               # was scaffold/templates/  (8)
│   ├── config/                  # was scaffold/config/     (2)
│   └── seeds/                   # was scaffold/seeds/      (4)
│
├── docker/
│   ├── api.Dockerfile           # FastAPI + built web bundle
│   ├── worker.Dockerfile        # git + node + Claude CLI + the agent
│   └── compose.yaml             # local dev: api, worker, postgres, azurite
│
├── deploy/azure/
│   ├── main.bicep
│   ├── modules/*.bicep
│   └── README.md                # the setup runbook
│
├── .claude/                     # dev-time only: THIS repo's own agents/skills
├── docs/
└── tests/
```

**Why `plugin/`.** Everything the installer copies into a target project is one thing with
one lifecycle, and today it is spread across `skills/`, `.claude/agents/` and three of
`scaffold/`'s four subdirectories. Putting it under one root makes the installer a single
directory copy, makes the container `COPY plugin/ /app/plugin/` trivial, and makes "what does
a project receive" answerable by `ls`.

**Why `packages/`.** A root `pyproject.toml` with three packages replaces the `sys.path`
hack, the `cp -f` vendoring, and the `PYTHONPATH=scripts` incantation in every runbook.
`implr-validate` becomes `pip install implr-validate` — so a target project pins a version
instead of receiving a snapshot.

**What this costs.** Every path in fifteen phase documents, the three installers, and every
test's import line. It is a day of mechanical work and it must happen **before Phase 0**,
because Phase 0 creates `studio/backend/pyproject.toml` at a path this proposal deletes.

### Minimal alternative

If the full move is too much churn, the irreducible subset for containerisation is:

1. Root `pyproject.toml` declaring `implr_validate` and `implr_studio` as packages.
2. `scripts/implr_validate` → `packages/implr_validate` (kills the path hack).
3. `docker/` and `deploy/azure/`.

Skip `plugin/`, keep `skills/` and `.claude/agents/` where they are, and let the Dockerfile
`COPY` three directories instead of one. Everything else still works.

---

## Containers

Two images, because the API and the agent have opposite trust levels.

**`docker/api.Dockerfile`** — multi-stage. Node builds the web bundle; the Python runtime
serves it plus the API. No git, no Claude CLI, no shell tools the agent needs. Non-root,
read-only root filesystem.

**`docker/worker.Dockerfile`** — has git, Node, and the Claude Code CLI. Runs one job and
exits. Non-root, read-only root except `/workspace`, no managed identity.

Both are in this repo alongside a `compose.yaml` that brings up api + worker + Postgres +
Azurite, so hosted mode is developable without an Azure subscription.

---

## Azure services

| Service | Role | Why this one |
|---|---|---|
| **Container Apps** (app) | the API + UI | scale-to-zero, revisions, free managed TLS, built-in Entra auth |
| **Container Apps Jobs** (event/manual) | one job per run | ephemeral, per-run isolation, hard timeout, no shared filesystem |
| **Azure Database for PostgreSQL** — Flexible Server | control plane | private endpoint, PITR, no server management |
| **Blob Storage** | log archive, uploaded KB documents | the 18 ingest formats arrive as blobs, not repo commits |
| **Key Vault** | `ANTHROPIC_API_KEY`, git PAT, DB password | referenced by Container Apps secrets, never in config |
| **Container Registry** | images | ACR tasks can build on push |
| **Managed Identity** (user-assigned) | ACR pull, Key Vault get, Blob write | **API only.** The worker gets none |
| **Entra ID app registration** | authentication | Container Apps EasyAuth is the cheap path; the API still validates the token itself |
| **VNet + private endpoint** | Postgres reachability | the database must not have a public endpoint |
| **NAT Gateway + Azure Firewall** | worker egress allowlist | FQDN rules: `api.anthropic.com`, the git host, nothing else |
| **Log Analytics + Application Insights** | traces, run diagnostics | Container Apps ships console output here by default |

### Topology

```
      Entra ID
         │ (OIDC)
         ▼
 ┌───────────────────┐        ┌──────────────────────────┐
 │ Container App     │        │  Key Vault               │
 │  api + web        │◄──MI──►│  ANTHROPIC_API_KEY, PAT  │
 │  (public HTTPS)   │        └──────────────────────────┘
 └─────┬────────┬────┘
       │        │ starts a job per run
       │        ▼
       │  ┌──────────────────────────────────┐
       │  │ Container Apps Job  (per run)    │
       │  │  git clone → materialise skills  │
       │  │  → run the agent → callback      │
       │  │  no MI · no DB creds · ephemeral │
       │  └──────────────┬───────────────────┘
       │                 │ egress via Firewall FQDN allowlist
       │                 ▼   api.anthropic.com · git remote
       │
       ▼ private endpoint
 ┌───────────────────┐   ┌──────────────┐
 │ PostgreSQL Flex   │   │ Blob Storage │
 └───────────────────┘   └──────────────┘
```

The setup runbook — resource creation, role assignments, the firewall rules, and how to get
a first project working — belongs in `deploy/azure/README.md` and is written alongside the
bicep.

---

## What this does to the fifteen phases

The phase sequence survives; the deployment target is orthogonal to it. Four changes:

| Phase | Change |
|---|---|
| **−1** *(new, before 0)* | The restructure: root `pyproject.toml`, `packages/`, `plugin/`. Must precede Phase 0, which currently writes a manifest at a path this deletes. |
| **0** | Paths move. Adds `--mode local\|hosted` and a `docker/compose.yaml` so the shell runs in a container from day one. |
| **1** | The catalogue is read through a `CatalogueSource` seam — files in local mode, tables in hosted. Availability becomes a query. |
| **9** *(Run one node)* | Gains a second `RunLauncher`: in-process for local, Container Apps Job for hosted. The `StepExecutor` Protocol is unchanged. |

Plus a new phase after 14:

| **15** | **Deploy to Azure.** Bicep, the runbook, Entra auth, and an end-to-end run in a real subscription. |

The auth/projects/roles work is not a phase — it cuts across 1, 9 and 15, and should be
specified separately rather than smeared through the sequence.

---

## Open questions I cannot settle alone

1. **Single-tenant or multi-tenant?** One deployment per customer is dramatically simpler:
   project isolation becomes deployment isolation, and the whole `memberships`/tool-ceiling
   apparatus can wait. Multi-tenant needs row-level security in Postgres and a much harder
   review of the worker boundary. **My recommendation: single-tenant first.** Ship one
   deployment per customer, add tenancy when someone is paying for it.
2. **Who supplies the Anthropic credential?** Platform key (you pay, you meter) or
   bring-your-own (they pay, you never see spend). BYO is safer and simpler; a platform key
   needs quotas before it needs anything else.
3. **How does the worker reach the customer's repo?** A GitHub App is the right answer for
   scoped, revocable, auditable access. A PAT in Key Vault is the fast answer and ages badly.
4. **Is `--dry-run` the default in hosted mode?** An agent that writes to a real branch on a
   button press, in someone else's infrastructure, deserves a deliberate opt-in.

---

## Success criteria

1. `docker compose up` brings up API, worker, Postgres and Azurite; the UI loads and lists
   steps from the **database**, seeded in flight from `plugin/skills/`.
2. A custom skill authored in the UI is stored as a row, appears in the palette, and is
   materialised into the run container's `.claude/skills/` — and into no other project's.
3. A skill named `../../etc/passwd` is rejected at write time.
4. A run executes in a Container Apps Job with no database credentials, and its output
   streams to the browser through the callback endpoint.
5. The worker cannot resolve `example.com`; it can resolve `api.anthropic.com`.
6. The API container has no `git` and no Claude CLI on its `PATH`.
7. Postgres has no public endpoint; the API reaches it over a private endpoint.
8. `implr-studio --workspace .` on a laptop still binds loopback, needs no auth, and reads
   the catalogue from files — the local mode is not regressed.
9. `pip install implr-validate` works, and no test contains `sys.path.insert`.
