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

- Two deployment modes — `local` and `hosted` — from one codebase and **one API**.
- **Multi-tenant**: many tenants, many users per tenant, many projects per tenant.
- Authorization behind a **single seam**, permissive today, granular later without
  touching a call site.
- Containerisation: an API image and a **separate, isolated worker image** for run execution.
- Postgres as the control-plane store, replacing SQLite in hosted mode, with **row-level
  security** as the tenant backstop.
- Skills and agents stored in the database, materialised to disk per run.
- Azure service topology, with infrastructure-as-code.
- A repository restructure that makes the above buildable.

### Out of scope

- Multi-region, HA, or autoscaling beyond Container Apps defaults.
- Billing, quotas, or usage metering.
- A user belonging to more than one tenant. Tenancy comes from the identity provider.
- Per-project roles *enforced* — the tables and the seam exist, the policy does not use
  them yet. See *Authorization*.
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

## Tenancy

**Tenant → users → projects.** A tenant is the isolation boundary; every user and every
project belongs to exactly one. Nothing crosses it, ever, by any route.

**Tenancy is derived from the identity provider, not administered by us.** An Entra access
token carries `tid` (the Entra tenant) and `oid` (the object id of the user). The API resolves
`tenant = tenants WHERE entra_tid = tid` and `user = users WHERE (tenant_id, entra_oid)`.
That means:

- there is no "which tenant am I?" question for a client to get wrong, and no header a
  request can spoof;
- a user cannot belong to two tenants, because a token has one `tid`;
- an Entra B2B guest presents the *host* tenant's `tid`, which is the correct answer — they
  are acting inside that tenant;
- onboarding a tenant is one row, created on first successful sign-in from an allowed `tid`.

**Local mode is a single implicit tenant.** One tenant (`local`), one user (the operator,
tenant owner), one project (the `--workspace` directory). Nothing about local mode is
special-cased in the routes — it is the degenerate case of the same model, which is what
keeps the two modes from drifting.

| | Local | Hosted |
|---|---|---|
| Tenant | one, `local` | one row per Entra tenant |
| User | one, implicit owner | resolved from `oid` on every request |
| Projects | exactly one, the workspace | many |
| Auth | `AUTH_MODE=none` | `AUTH_MODE=entra`, bearer token validated per request |

### One API, project-scoped

Every project resource is addressed under its project. This is the single most consequential
change to the existing plans, because it moves `/api/pipeline` to
`/api/projects/{project_id}/pipeline`.

```
GET  /api/health                                     unauthenticated (liveness probe)
GET  /api/me                                         principal, tenant, granted permissions

GET  /api/projects                                   the tenant's projects
POST /api/projects                                   create

GET  /api/projects/{pid}/registry                    builtins + this project's catalogue
GET  /api/projects/{pid}/skills                      installed + custom, for the picker
GET  /api/projects/{pid}/steps                       authored steps
PUT  /api/projects/{pid}/steps
GET  /api/projects/{pid}/pipeline
PUT  /api/projects/{pid}/pipeline
GET  /api/projects/{pid}/runs
POST /api/projects/{pid}/runs
GET  /api/projects/{pid}/runs/{rid}
POST /api/projects/{pid}/runs/{rid}/answer
POST /api/projects/{pid}/runs/{rid}/approve
POST /api/projects/{pid}/runs/{rid}/nodes/{node}/retry
POST /api/projects/{pid}/runs/{rid}/nodes/{node}/skip
POST /api/projects/{pid}/runs/{rid}/cancel
WS   /api/projects/{pid}/runs/{rid}/stream

POST /api/internal/runs/{rid}/events                 worker callback, run-scoped token only
```

**Why not keep `/api/pipeline` and resolve the project implicitly?** Because that produces
two route shapes — one for local, one for hosted — and every client, test and runbook then
has to know which it is talking to. A single project-scoped shape with local mode pinning
`pid` to a well-known value costs one path segment and removes an entire class of divergence.
In local mode the UI reads its single project from `/api/projects` and never shows a picker.

**Run ids are UUIDv4**, not sequential, so a leaked id from one tenant reveals nothing and
guesses go nowhere. The run must still be verified to belong to `{pid}` — an unguessable id
is not authorization.

---

## Authorization

### What is enforced today

**Any member of a tenant may do anything to any project in that tenant.** That is the rule
you asked for, and it is the whole policy. What matters is that it lives in one place, so
tightening it later is a one-file change rather than an audit of forty routes.

### The seam

Three pieces, and the third is the one that makes the future cheap.

```python
# packages/implr_studio/authz.py

class Permission(StrEnum):
    PROJECT_READ   = "project.read"     # see a project, its pipeline, its runs
    PROJECT_WRITE  = "project.write"    # save a pipeline
    PROJECT_CREATE = "project.create"   # add a project to the tenant
    RUN_START      = "run.start"
    RUN_CONTROL    = "run.control"      # answer, approve, retry, skip, cancel
    STEP_AUTHOR    = "step.author"      # Phase 8 - write an instruction and a tool grant
    SKILL_AUTHOR   = "skill.author"
    TENANT_ADMIN   = "tenant.admin"     # manage users, tenant settings


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    tenant_role: str          # "owner" | "member"
    email: str


class Policy(Protocol):
    def allows(self, principal: Principal, permission: Permission,
               project: ProjectRef | None) -> bool: ...


def authorize(principal, permission, *, project=None) -> None:
    """Raise Forbidden unless the active policy allows it. Called by every route."""
```

**The permission verbs are named now, in full, even though the policy ignores most of the
distinction.** Naming them later would mean revisiting every call site to decide which verb
it meant — and that is exactly the audit this seam exists to avoid. `run.control` is separate
from `run.start` because "may trigger a run" and "may answer its questions" are obviously
different powers, even if today the same people hold both.

`TenantWidePolicy` — the whole of today's rule:

```python
class TenantWidePolicy:
    """Every member of a tenant may act on every project in that tenant.

    The tenant check is NOT a formality: `project.tenant_id != principal.tenant_id`
    is the only thing standing between two customers, and it is asserted here
    rather than in each route so it cannot be forgotten in one of them.
    """

    def allows(self, principal, permission, project):
        if project is not None and project.tenant_id != principal.tenant_id:
            return False
        if permission is Permission.TENANT_ADMIN:
            return principal.tenant_role == "owner"
        return True
```

### How granularity arrives later, with no call-site change

`project_grants` exists from the start and is **empty**. The rule that makes it a no-op today
and a switch tomorrow:

> A project with **no** grant rows is visible and writable by every member of its tenant.
> A project with **at least one** grant row is restricted to its grantees.

So enabling per-project restriction on one project is inserting a row. Every other project
keeps behaving exactly as before. No migration, no backfill, no flag day.

```python
class ProjectGrantPolicy(TenantWidePolicy):
    """Future. Open by default; restricted once explicitly granted."""

    def allows(self, principal, permission, project):
        if not super().allows(principal, permission, project):
            return False
        if project is None or not project.has_grants:
            return True                        # unrestricted, as today
        return project.grant_for(principal.user_id) >= _required_role(permission)
```

**The honest caveat.** "No grants means open" is a **fail-open** default. That is acceptable
*inside* a tenant, where the alternative is every new project being invisible until someone
grants it. It must never be used for anything that crosses a tenant — which is why the tenant
check in `TenantWidePolicy` runs *before* the grant check and is not part of the same
mechanism.

### Enforcement is layered, because a route check alone is not enough

| Layer | Mechanism | Catches |
|---|---|---|
| Route | `authorize(principal, verb, project=p)` | ordinary policy decisions |
| Repository | every query takes a tenant-scoped connection | a route that forgot to check |
| Database | **Postgres row-level security** | a query that forgot its `WHERE` |

RLS is the backstop that makes multi-tenancy defensible rather than merely intended. Each
transaction opens with the tenant pinned:

```sql
SET LOCAL app.tenant_id = '…';

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON projects
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Catalogue tables also hold shared builtins, which every tenant may read.
CREATE POLICY tenant_isolation ON skills
    USING (tenant_id IS NULL OR tenant_id = current_setting('app.tenant_id')::uuid);
```

With RLS on, a missing `WHERE tenant_id = …` returns **zero rows instead of another
customer's data**. That converts the worst class of bug in a multi-tenant system from a
breach into an empty list.

The API connects as a role **without** `BYPASSRLS`. Migrations run as a separate role that
has it. Getting that backwards silently disables everything above.

### Known cross-tenant leak vectors, and what closes each

Enumerated because each one is a place where the generic advice "scope by tenant" is not
obviously sufficient:

| Vector | Why it leaks | Closed by |
|---|---|---|
| `events.seq` is one global sequence | a cursor is just an integer; a client could ask for another tenant's range | the WS handler resolves `run → project → tenant` and filters; the cursor is a *position*, never an authorization |
| Materialised skills | writing the global catalogue into a run container hands one tenant another's custom prompts | materialise only `tenant_id IS NULL` builtins plus **this project's** rows |
| Project slugs | a global unique index leaks the existence of other tenants' projects through collisions | `UNIQUE (tenant_id, slug)` |
| Blob paths | a flat container makes one tenant's uploads guessable | `tenant/{tenant_id}/project/{project_id}/…` plus per-tenant SAS scoping |
| Worker callback | a compromised worker could post events onto another run | the run token is scoped to one `run_id`, and the endpoint verifies the run's tenant matches the token's |
| Error messages | "project X not found" versus "forbidden" reveals existence | **404, never 403, for a project outside your tenant** |

That last one is worth stating as a rule: a resource the principal may not see does not
exist, as far as the API is concerned.

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

**The run token names one run, and the callback verifies the tenant.** A token scoped only to
a run id would let a compromised worker post events onto a run it was not given, and in a
multi-tenant deployment that is a cross-tenant write. The callback resolves the run, compares
its `tenant_id` to the token's, and rejects a mismatch — so the token is a capability for one
run belonging to one tenant, not a general-purpose event writer.

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

Every tenant-owned table carries `tenant_id` **directly**, not by join. Reaching the tenant
through `run → pipeline → project` would make the RLS policy a subquery on every row, and
policies must be cheap enough that nobody is tempted to switch them off.

```sql
-- tenancy -------------------------------------------------------------------
tenants        (id uuid pk, entra_tid text unique, name, status, created_at)
users          (id uuid pk, tenant_id fk, entra_oid text, email, display_name,
                last_seen_at, created_at,
                UNIQUE (tenant_id, entra_oid))
tenant_members (tenant_id fk, user_id fk, role,           -- 'owner' | 'member'
                PK (tenant_id, user_id))

projects       (id uuid pk, tenant_id fk, slug, name, git_remote, default_branch,
                created_by fk users, created_at, archived_at,
                UNIQUE (tenant_id, slug))                 -- per tenant, never global

-- future-proofing: EMPTY today ---------------------------------------------
project_grants (project_id fk, user_id fk, role,          -- 'reader'|'designer'|'operator'
                granted_by fk users, granted_at,
                PK (project_id, user_id))
-- A project with NO rows here is open to every member of its tenant. One row
-- makes it restricted. That is how granular access arrives without a migration.

-- catalogue ----------------------------------------------------------------
skills         (id uuid pk, tenant_id fk null, project_id fk null,
                name, version, body, source, content_hash, enabled,
                created_by, created_at, updated_at)
               -- tenant_id NULL = builtin, shared, read-only, synced from plugin/
               -- source: 'builtin' | 'custom'
               -- UNIQUE NULLS NOT DISTINCT (tenant_id, project_id, name)
agents         (id uuid pk, tenant_id fk null, project_id fk null,
                name, description, prompt, tools jsonb, default_tier,
                source, content_hash, enabled, ...)
steps          (id uuid pk, tenant_id fk null, project_id fk null,
                step_id, kind, label, phase, skill_name, instruction,
                args_allowed jsonb, args_default jsonb, agents jsonb,
                consumes jsonb, produces jsonb, produces_artefact,
                description, source, enabled, ...)
               -- replaces step-registry.json AND steps.yaml

-- design -------------------------------------------------------------------
pipelines      (id uuid pk, tenant_id fk, project_id fk, name, graph jsonb,
                version, updated_by, updated_at)
               -- graph jsonb is exactly today's pipeline.yaml shape

-- execution ----------------------------------------------------------------
runs           (id uuid pk, tenant_id fk, project_id fk, pipeline_id fk,
                git_ref, git_sha, status, started_by fk users,
                created_at, updated_at, finished_at)
node_runs      (tenant_id fk, run_id fk, node_id, status, summary, error,
                manual_approved, started_at, finished_at,
                PK (run_id, node_id))
events         (seq bigserial pk, tenant_id fk, run_id fk, node_id,
                kind, payload jsonb, created_at)
questions      (id uuid pk, tenant_id fk, run_id fk, node_id, prompt_md,
                options jsonb, answer, answered_by fk users, answered_at,
                created_at)
```

`UNIQUE NULLS NOT DISTINCT` on the catalogue tables (Postgres 15+) is deliberate: without it
two builtin rows with `tenant_id IS NULL` and the same `name` would both be permitted,
because SQL treats NULLs as distinct. That would silently allow duplicate builtins.

Five notes on the shape:

- **`pipelines.graph` is versioned by row, not by history table.** A saved pipeline is
  small, and the audit trail that matters is git — the pipeline is written back to
  `docs/implr/config/pipeline.yaml` in the project's repo on save, exactly as in local mode.
  The table is the working copy; git is the history.
- **`pipelines.graph` is jsonb, not normalised into node/edge tables.** It is read and written
  whole, validated as a unit, and never queried by node. Normalising it would buy nothing and
  cost every save a transaction over dozens of rows.
- **`steps` replaces both `step-registry.json` and `steps.yaml`.** In hosted mode the
  registry *is* a table. `tenant_id IS NULL` rows are the builtins synced from
  `plugin/steps/`; project rows are what Phase 8 authors. The merge rule stays the same — a
  project row may not shadow a builtin `step_id`.
- **`node_runs`, `events` and `questions` carry a redundant `tenant_id`.** It is derivable
  from `run_id`, and denormalising it is the right call: RLS on `events` is consulted for
  every log line, and a policy that joins to `runs` to find the tenant would be the hottest
  query in the system. Denormalised, the policy is an integer comparison. The redundancy is
  enforced by a foreign key on `(tenant_id, run_id)` so it cannot drift.
- **`events.seq` stays one global sequence**, not per-tenant. Gaps are fine; ordering and the
  cursor contract are not. The cursor is a position, never an authorization — see the leak
  table above.

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

1. ~~Single-tenant or multi-tenant?~~ **Settled: multi-tenant.** See *Tenancy* and
   *Authorization*. The consequences carried through this document are row-level security as
   the isolation backstop, project-scoped routes, and a tenant check that runs before any
   other policy decision.
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

Tenancy and authorization:

10. Two users signing in from the same Entra tenant see the **same** project list, with no
    grants configured — the rule asked for.
11. A user from a different Entra tenant sees an empty project list, and a direct `GET` on
    another tenant's project id returns **404, not 403**.
12. Inserting one row into `project_grants` restricts that project to its grantees and leaves
    every other project in the tenant untouched — asserted without a migration and without a
    code change outside `authz.py`.
13. Every route calls `authorize(...)`. Asserted by a test that walks the FastAPI route table
    and fails on any handler that does not.
14. With RLS enabled, a deliberately tenant-unscoped query returns **zero rows** rather than
    another tenant's data. The API's database role does not have `BYPASSRLS`.
15. A run container is materialised with builtin skills plus exactly one project's custom
    skills — proven by asserting a second project's custom skill is absent from the tree.
16. Two projects in different tenants may share a slug.
