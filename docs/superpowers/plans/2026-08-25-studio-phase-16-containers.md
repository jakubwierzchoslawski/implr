# implr Studio — Phase 16: Containers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docker compose up --build`, and the same console runs a pipeline in a **separate container** against a catalogue served from **Postgres**.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-hosted-design.md` (*Isolation*, *Skills and agents: database as source, disk as projection*, *Containers*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 15. Deploying a console that cannot run a pipeline proves nothing, and the
two-image split only makes sense once the worker has real teeth.

**The three files already exist** — `docker/api.Dockerfile`, `docker/worker.Dockerfile`,
`docker/compose.yaml` were written and committed earlier. This phase makes them **build, run and
pass tests**, which is a different and larger job than writing them.

---

## Demo

```bash
docker compose -f docker/compose.yaml up --build
open http://127.0.0.1:8000
```

The console loads. The palette lists steps **from Postgres**, seeded in flight from
`plugin/skills/` at boot. Press Run: a **separate worker container** starts, executes the step,
and streams events back through the callback endpoint into the same WebSocket the browser is
already reading.

Then the four assertions that are security properties rather than packaging details:

```bash
docker run --rm implr-studio-api which git          # nothing
docker run --rm implr-studio-api which claude       # nothing
docker inspect implr-studio-worker-1 --format \
  '{{range .Config.Env}}{{println .}}{{end}}' | grep DATABASE_URL   # nothing
docker exec implr-studio-api-1 touch /app/x         # read-only filesystem
```

Each of those is a `docker` command in the demo *and* a test in the suite, because "we forgot to
keep git out of the API image" is exactly the kind of regression a Dockerfile edit introduces
silently.

---

## Why this phase exists

Local mode has one process, one SQLite file, files on disk, and full trust. Hosted mode has
none of those. Four seams carry the difference, and every one of them is a seam rather than an
`if` for the same reason: the third implementation is Azure, and it arrives in Phase 19.

| Seam | Local | Compose | Azure (Phase 19) |
|---|---|---|---|
| `RunLauncher` | `InProcessLauncher` | `SubprocessLauncher` | `ContainerAppsJobLauncher` |
| `CatalogueSource` | `FileCatalogue` | `DbCatalogue` | `DbCatalogue` |
| `Store` dialect | SQLite | Postgres | Postgres |
| Blob | local dir | Azurite | Blob Storage |

**Two implementations is when you build the seam; three is when you regret not having.** By the
time Phase 19 needs a launcher that calls the Azure control plane, the interface has already been
exercised by two very different implementations.

---

## Scope boundary — not in this phase

- **No row-level security, no tenancy, no auth.** Postgres arrives here; **RLS arrives in Phase
  17**. That ordering is deliberate and it has one hard consequence: *the compose stack is not
  safe to expose*, and `AUTH_MODE=dev` trusts a header. The dependency graph says 17 before 19 for
  exactly this reason, and it is the one edge not to reorder.
- **No Azure anything.** No bicep, no Container Apps, no Key Vault. Azurite stands in for Blob.
- **No log archive to Blob.** The `events` table keeps everything for now; the archive threshold is
  a Phase 19 retention decision.
- **No multi-worker scheduling.** One container per run, started when the run starts. No queue, no
  concurrency limit, no fairness — a single-tenant compose stack does not need one.
- **No migration tooling beyond a schema bootstrap.** Alembic is right eventually and not while
  the schema is still moving.

---

## Global constraints

**The API must never be able to execute a step.** Not "should not" — *cannot*. No git, no Node, no
Claude CLI on `PATH`. This is asserted by a test that runs `which` inside the built image, because
a Dockerfile is edited by people in a hurry and the property is invisible until it is exploited.

**The worker has no database credentials.** It reports through a callback endpoint scoped to a
single run id, authenticated by a token that is minted per job and expires. A worker that could
reach Postgres could read every tenant's runs, and the worker is the container running
model-authored shell commands.

**The callback is not a public API.** It is under `/api/internal/`, it accepts only a valid
run-scoped token, and it refuses to write to any run other than the one in its token. Tested
adversarially, not just happily.

**Materialisation is a security boundary, not a filter.** Phase 15 established why: the SDK's
`skills=` list hides a skill from the model's listing but *leaves its files readable via Read and
Bash*. So a project's skills reach the container by being **written into `/workspace/.claude/`
and nothing else's being written**. Never by materialising a tenant's whole catalogue and
filtering.

**Every name that becomes a path is validated before it becomes a path.** A skill row named
`../../etc/passwd` is refused at write time *and* at materialise time. Two checks, because the
row could predate the validation.

**`IMPLR_MODE` is read once, at startup, into a frozen config object.** Not consulted at call
sites. A mode check scattered through the code is how a hosted deployment ends up taking a local
branch under load.

**The plugin payload travels in the image.** A run must not depend on the API being reachable to
obtain builtin skills. Project-scoped custom skills arrive in the job payload.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/config.py` | **Modified** — `IMPLR_MODE`, frozen settings, one parse. |
| `packages/implr_studio/launchers/base.py` | `RunLauncher` Protocol. |
| `packages/implr_studio/launchers/in_process.py` | Local: today's behaviour, behind the interface. |
| `packages/implr_studio/launchers/subprocess.py` | Compose: `docker run`. |
| `packages/implr_studio/catalogue/base.py` | `CatalogueSource` Protocol. |
| `packages/implr_studio/catalogue/files.py` | Local: `step-registry.json` + `steps.yaml`. |
| `packages/implr_studio/catalogue/db.py` | Hosted: tables. |
| `packages/implr_studio/catalogue/sync.py` | Boot-time sync of `plugin/` into the tables. |
| `packages/implr_studio/store_pg.py` | Postgres dialect behind the `Store` interface. |
| `packages/implr_studio/schema.sql` | Bootstrap DDL. |
| `packages/implr_studio/materialise.py` | Rows → `/workspace/.claude/`. |
| `packages/implr_studio/worker.py` | The worker entrypoint: clone, materialise, run, report. |
| `packages/implr_studio/api.py` | **Modified** — `/api/internal/runs/{rid}/events`. |
| `packages/implr_studio/jobtoken.py` | Mint and verify the run-scoped token. |
| `docker/*` | **Existing** — made to build and pass. |

---

### Task 1: One mode, read once

**Files:**
- Modify: `packages/implr_studio/config.py`
- Test: `packages/implr_studio/tests/test_mode.py`

**Interfaces:**
- `config.Mode` — `LOCAL = "local"`, `HOSTED = "hosted"`, `WORKER = "worker"`.
- `config.Settings` — frozen dataclass; `from_env(env) -> Settings`.
- `Settings.mode`, `.database_url`, `.blob_endpoint`, `.plugin_dir`, `.launcher`, `.worker_image`,
  `.callback_url`, `.auth_mode`.

- [ ] **Step 1: Write the failing test**

```python
import dataclasses

import pytest

from implr_studio import config


def test_settings_are_frozen():
    """Read once at startup. A mutable settings object invites a call site to
    'temporarily' flip a mode, and that is how a hosted deployment takes a
    local branch."""
    s = config.Settings.from_env({"IMPLR_MODE": "local"})

    with pytest.raises(dataclasses.FrozenInstanceError):
        s.mode = config.Mode.HOSTED


def test_the_default_mode_is_local():
    """`implr-studio --workspace .` must keep working with no environment."""
    assert config.Settings.from_env({}).mode is config.Mode.LOCAL


def test_hosted_requires_a_database_url():
    """Fail at startup, naming the variable - not on the first request."""
    with pytest.raises(config.ConfigError, match="DATABASE_URL"):
        config.Settings.from_env({"IMPLR_MODE": "hosted"})


def test_worker_mode_must_not_have_a_database_url():
    """The refusal is the security property. A worker that can reach Postgres
    can read every tenant's runs, and the worker is the container running
    model-authored shell commands."""
    with pytest.raises(config.ConfigError, match="DATABASE_URL"):
        config.Settings.from_env({"IMPLR_MODE": "worker",
                                  "DATABASE_URL": "postgresql://x/y",
                                  "CALLBACK_URL": "http://api/x"})


def test_worker_mode_requires_a_callback_url():
    with pytest.raises(config.ConfigError, match="CALLBACK_URL"):
        config.Settings.from_env({"IMPLR_MODE": "worker"})


def test_an_unknown_mode_is_refused_by_name():
    with pytest.raises(config.ConfigError, match="staging"):
        config.Settings.from_env({"IMPLR_MODE": "staging"})


def test_auth_mode_dev_is_refused_outside_a_dev_launcher():
    """AUTH_MODE=dev trusts a header. It is correct for compose and a breach
    anywhere a real launcher is configured."""
    with pytest.raises(config.ConfigError, match="AUTH_MODE"):
        config.Settings.from_env({"IMPLR_MODE": "hosted",
                                  "DATABASE_URL": "postgresql://x/y",
                                  "AUTH_MODE": "dev",
                                  "RUN_LAUNCHER": "containerapps-job"})


def test_no_module_reads_the_environment_directly(source_tree):
    """One parse. Grep is the right tool here: a stray os.environ read is
    invisible in review and behaves differently in each mode."""
    offenders = [p for p in source_tree.glob("**/*.py")
                 if p.name not in ("config.py", "cli.py")
                 and ("os.environ" in p.read_text(encoding="utf-8")
                      or "os.getenv" in p.read_text(encoding="utf-8"))]

    assert offenders == []
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(config): one mode, parsed once, frozen"
```

---

### Task 2: The launcher seam

**Files:**
- Create: `packages/implr_studio/launchers/{base,in_process,subprocess}.py`
- Modify: `packages/implr_studio/orchestrator.py`, `api.py`
- Test: `packages/implr_studio/tests/test_launchers.py`

**Interfaces:**

```python
class RunLauncher(Protocol):
    async def launch(self, job: JobSpec) -> LaunchHandle: ...
    async def cancel(self, handle: LaunchHandle) -> None: ...
```

- `JobSpec` — frozen: `run_id`, `project_id`, `tenant_id`, `git_remote`, `git_ref`, `pipeline`
  (the graph), `catalogue` (the materialisation payload), `callback_url`, `token`.
- `InProcessLauncher` — runs today's `Orchestrator` in this process.
- `SubprocessLauncher` — `docker run --rm -e ... implr-studio-worker`.

- [ ] **Step 1: Write the failing test**

```python
def test_the_local_launcher_still_behaves_like_phase_15(orch):
    """The seam must be invisible in local mode. If run mode changes at all,
    the abstraction was drawn in the wrong place."""
    ...
    assert orch.node_statuses(run_id)["a"] == rs.SUCCEEDED


def test_a_job_spec_is_frozen():
    """It is serialised, signed, and handed to a container. A mutable spec
    means the thing you signed and the thing you sent can differ."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        job.run_id = "other"


def test_the_job_spec_carries_no_secret(job):
    """It is visible in `docker inspect` and in Azure job history. The API key
    is injected by the platform, never by the spec."""
    blob = json.dumps(dataclasses.asdict(job))

    assert "ANTHROPIC_API_KEY" not in blob
    assert "sk-ant" not in blob
    assert "postgresql://" not in blob


def test_the_subprocess_launcher_passes_no_database_url(fake_docker):
    argv = fake_docker.last_argv

    assert not any(a.startswith("DATABASE_URL") for a in argv)


def test_the_subprocess_launcher_mounts_workspace_as_tmpfs(fake_docker):
    assert "--tmpfs" in fake_docker.last_argv


def test_the_subprocess_launcher_drops_privileges(fake_docker):
    argv = " ".join(fake_docker.last_argv)

    assert "--security-opt no-new-privileges" in argv
    assert "--read-only" in argv


def test_cancel_removes_the_container(fake_docker):
    """Phase 14's Abort, one layer down. Without this, Abort updates the
    database and the container keeps running - and billing."""
    await launcher.cancel(handle)

    assert fake_docker.killed == [handle.container_id]


def test_a_launch_failure_fails_the_run_with_a_readable_error(fake_docker):
    """'docker: Error response from daemon' in a red box is not an
    instruction. Name the image and the likely cause."""
    fake_docker.fail("no such image: implr-studio-worker")

    ...
    assert "implr-studio-worker" in error
    assert "build" in error.lower()


def test_both_launchers_satisfy_the_protocol():
    for cls in (InProcessLauncher, SubprocessLauncher):
        assert isinstance(cls(**minimal_kwargs(cls)), RunLauncher)
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(launcher): the run launcher seam, in-process and subprocess"
```

---

### Task 3: The catalogue seam, and boot-time sync

**Files:**
- Create: `packages/implr_studio/catalogue/{base,files,db,sync}.py`
- Test: `packages/implr_studio/tests/test_catalogue.py`, `test_catalogue_sync.py`

**Interfaces:**
- `CatalogueSource` Protocol: `steps(project_id)`, `skills(project_id)`, `agents(project_id)`.
- `FileCatalogue(workspace)` — wraps Phase 1 + Phase 8 loading, unchanged behaviour.
- `DbCatalogue(conn)` — the same three methods over `steps` / `skills` / `agents`.
- `sync.sync_plugin(conn, plugin_dir) -> SyncReport` — idempotent, content-hash based.

**Sync is content-hash based and idempotent.** A restart must not churn rows; a *changed* builtin
must update. And a builtin must never overwrite a project's row, because the merge rule from Phase
8 still holds in the database.

- [ ] **Step 1: Write the failing test**

```python
def test_both_sources_satisfy_the_protocol():
    for src in (FileCatalogue(workspace), DbCatalogue(conn)):
        assert isinstance(src, CatalogueSource)


def test_the_two_sources_agree_on_the_shipped_steps(workspace, conn):
    """The migration test. If the db catalogue disagrees with the file one on
    the nine shipped steps, every pipeline authored locally breaks hosted."""
    sync.sync_plugin(conn, workspace / "plugin")

    files = {s.id: s for s in FileCatalogue(workspace).steps(None)}
    rows = {s.id: s for s in DbCatalogue(conn).steps(PROJECT)}

    assert set(files) == set(rows)
    for sid in files:
        assert files[sid].label == rows[sid].label
        assert files[sid].agents == rows[sid].agents


def test_sync_is_idempotent(conn, plugin_dir):
    first = sync.sync_plugin(conn, plugin_dir)
    second = sync.sync_plugin(conn, plugin_dir)

    assert first.inserted == 8 and first.updated == 0
    assert second.inserted == 0 and second.updated == 0


def test_a_changed_builtin_updates_on_the_next_boot(conn, plugin_dir):
    sync.sync_plugin(conn, plugin_dir)
    (plugin_dir / "skills/doc-ingest/SKILL.md").write_text(NEW_BODY, encoding="utf-8")

    report = sync.sync_plugin(conn, plugin_dir)

    assert report.updated == 1


def test_sync_never_touches_a_project_row(conn, plugin_dir):
    """Phase 8's rule, in the database: a builtin may not shadow a project
    step, and it may certainly not overwrite one."""
    insert_project_step(conn, step_id="lint-and-format", project_id=PROJECT)

    sync.sync_plugin(conn, plugin_dir)

    assert project_step(conn, "lint-and-format") is not None


def test_a_builtin_removed_from_the_plugin_is_disabled_not_deleted(conn, plugin_dir):
    """A pipeline may still reference it. Deleting the row makes that pipeline
    unloadable; disabling makes the node dashed, which is the state the UI
    already knows how to render."""
    sync.sync_plugin(conn, plugin_dir)
    (plugin_dir / "skills/ba-cr").rename(plugin_dir / "skills/.gone")

    sync.sync_plugin(conn, plugin_dir)

    row = builtin_skill(conn, "ba-cr")
    assert row is not None and row["enabled"] is False


def test_two_builtins_with_the_same_name_cannot_both_exist(conn):
    """UNIQUE NULLS NOT DISTINCT. Without it, `tenant_id IS NULL` rows are
    treated as distinct by SQL and duplicate builtins pass silently."""
    with pytest.raises(IntegrityError):
        insert_builtin(conn, name="doc-ingest")
        insert_builtin(conn, name="doc-ingest")


def test_sync_runs_before_the_server_serves(client_factory):
    """Same discipline as Phase 14's recovery: no request may observe an
    unseeded catalogue, or the first palette load is empty."""
    client = client_factory(mode="hosted")

    assert len(client.get(url("/registry")).json()["steps"]) == 9
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(catalogue): the catalogue seam and idempotent plugin sync"
```

---

### Task 4: Postgres behind the Store interface

**Files:**
- Create: `packages/implr_studio/store_pg.py`, `schema.sql`
- Test: `packages/implr_studio/tests/test_store_contract.py`

**Interfaces:**
- `store_pg.PgStore(dsn)` — the same public surface as the SQLite `Store`.
- **One shared contract suite**, parameterised over both stores.

The shared suite is the whole design. A second store implementation that has its own tests will
diverge from the first, and the divergence will be found by a run that behaves differently in
production than in the tests.

- [ ] **Step 1: Write the failing test**

```python
@pytest.fixture(params=["sqlite", "postgres"])
def store(request, tmp_path, pg_dsn):
    if request.param == "postgres":
        pytest.importorskip("psycopg")
        if pg_dsn is None:
            pytest.skip("no postgres available")
        return PgStore(pg_dsn)
    return Store(tmp_path / "runs.db")


def test_every_public_method_is_implemented_by_both():
    """Discovered by reflection, so a method added to one and forgotten in the
    other fails immediately rather than at the first hosted run that needs it."""
    sqlite_api = public_methods(Store)
    pg_api = public_methods(PgStore)

    assert sqlite_api == pg_api


def test_events_seq_is_monotonic(store): ...
def test_a_run_round_trips(store): ...
def test_node_status_transitions_persist(store): ...
def test_questions_round_trip(store): ...
def test_review_feedback_accumulates(store): ...
def test_keyset_pagination_over_runs(store): ...
def test_unfinished_nodes_spans_runs(store): ...


def test_concurrent_writers_do_not_interleave(store):
    """Phase 9's two-thread hammer, now against both dialects. The failure
    mode differs - sqlite raises 'database is locked', Postgres silently
    serialises - and both must pass."""
    ...


def test_the_schema_declares_tenant_id_on_every_owned_table(schema_sql):
    """Phase 17's RLS policies attach to these columns. A table that reaches
    17 without tenant_id needs a migration under a live policy, which is the
    worst time to discover it."""
    for table in ("projects", "pipelines", "runs", "node_runs", "events",
                  "questions", "skills", "agents", "steps"):
        assert "tenant_id" in columns_of(schema_sql, table), table


def test_node_runs_events_and_questions_have_a_composite_fk(schema_sql):
    """tenant_id is denormalised onto these three so Phase 17's policy is an
    integer comparison rather than a join. The composite FK is what stops the
    redundancy from drifting."""
    for table in ("node_runs", "events", "questions"):
        assert has_fk(schema_sql, table, ("tenant_id", "run_id")), table
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(store): postgres behind the store interface, one contract suite"
```

---

### Task 5: Materialisation

**Files:**
- Create: `packages/implr_studio/materialise.py`
- Test: `packages/implr_studio/tests/test_materialise.py`

**Interfaces:**
- `materialise(payload, root) -> MaterialiseReport` — writes `.claude/skills/*/SKILL.md` and
  `.claude/agents/*.md` under `root`.
- `SAFE_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import materialise


@pytest.mark.parametrize("name", [
    "../../etc/passwd", "..", "a/b", "a\\b", "/abs", "C:\\x",
    ".hidden", "with space", "UPPER", "trailing-", "-leading", "", "a" * 64,
])
def test_an_unsafe_skill_name_is_refused(tmp_path, name):
    """Two checks exist for this: at write time in the API, and here. Here is
    the one that matters, because a row could predate the validation."""
    with pytest.raises(materialise.UnsafeName, match="name"):
        materialise.materialise({"skills": [{"name": name, "body": "x"}]}, tmp_path)


def test_nothing_is_written_when_a_name_is_refused(tmp_path):
    """All-or-nothing. A half-materialised workspace runs with some skills
    missing, which looks like a model failure rather than a setup failure."""
    with pytest.raises(materialise.UnsafeName):
        materialise.materialise({"skills": [{"name": "ok", "body": "x"},
                                            {"name": "../evil", "body": "y"}]}, tmp_path)

    assert not (tmp_path / ".claude").exists()


def test_a_symlink_in_the_target_is_not_followed(tmp_path):
    """`.claude/skills -> /etc` in a repo we just cloned is attacker-supplied
    if the repo is."""
    (tmp_path / ".claude").mkdir()
    try:
        (tmp_path / ".claude" / "skills").symlink_to("/etc")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(materialise.UnsafeTarget):
        materialise.materialise({"skills": [{"name": "ok", "body": "x"}]}, tmp_path)


def test_only_the_payload_is_written(tmp_path):
    """THE isolation test. Phase 15 established that `skills=` is a context
    filter, not a sandbox: unlisted skills stay readable via Read and Bash.
    So isolation is 'the other tenant's files are not here', full stop."""
    materialise.materialise({"skills": [{"name": "mine", "body": "x"}]}, tmp_path)

    assert [p.name for p in (tmp_path / ".claude/skills").iterdir()] == ["mine"]


def test_a_resolved_path_outside_the_root_is_refused(tmp_path):
    """Belt and braces after SAFE_NAME: assert on the resolved path, so a
    future name rule that lets something through still cannot escape."""
    ...


def test_the_report_lists_what_was_written(tmp_path):
    """It goes into the run log. 'which skills did this run actually have'
    is the first question when a step behaves oddly."""
    report = materialise.materialise(PAYLOAD, tmp_path)

    assert report.skills == ["arch-gen", "doc-ingest"]


def test_materialisation_is_idempotent(tmp_path):
    materialise.materialise(PAYLOAD, tmp_path)
    materialise.materialise(PAYLOAD, tmp_path)

    assert count_files(tmp_path / ".claude") == expected
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(worker): materialise a project's catalogue, and only it"
```

---

### Task 6: The callback endpoint and the job token

**Files:**
- Create: `packages/implr_studio/jobtoken.py`
- Modify: `packages/implr_studio/api.py`
- Test: `packages/implr_studio/tests/test_callback.py`

**Interfaces:**
- `jobtoken.mint(run_id, tenant_id, ttl) -> str` — HMAC over a compact claim set.
- `jobtoken.verify(token) -> Claims` — raises on expiry, tamper, wrong audience.
- `POST /api/internal/runs/{rid}/events` — accepts a batch of events; requires the token.
- `POST /api/internal/runs/{rid}/answer-wait` — the worker's side of a question.

- [ ] **Step 1: Write the failing test**

```python
def test_the_worker_can_report_its_own_run(client, token):
    r = client.post("/api/internal/runs/%s/events" % RUN,
                    headers={"Authorization": "Bearer %s" % token},
                    json={"events": [LOG_EVENT]})

    assert r.status_code == 202


def test_a_token_for_one_run_cannot_write_to_another(client, token):
    """THE adversarial test. The worker is the container running
    model-authored shell commands; a token that is merely 'a valid token' is
    a cross-run write primitive."""
    r = client.post("/api/internal/runs/%s/events" % OTHER_RUN,
                    headers={"Authorization": "Bearer %s" % token},
                    json={"events": [LOG_EVENT]})

    assert r.status_code == 403
    assert store.events(OTHER_RUN) == []


def test_no_token_is_401(client): ...
def test_a_tampered_token_is_401(client): ...
def test_an_expired_token_is_401(client): ...


def test_the_token_carries_no_tenant_data_beyond_the_ids(token):
    """It travels in an environment variable, visible to `docker inspect` and
    in Azure job history."""
    claims = jobtoken.verify(token)

    assert set(claims) == {"run_id", "tenant_id", "exp", "aud"}


def test_the_signing_key_is_required_at_startup():
    """An unsigned callback endpoint is an unauthenticated write path to every
    run. Refuse to boot rather than defaulting to a dev key."""
    with pytest.raises(config.ConfigError, match="JOB_TOKEN_KEY"):
        config.Settings.from_env({"IMPLR_MODE": "hosted",
                                  "DATABASE_URL": "postgresql://x/y"})


def test_the_internal_routes_are_not_in_the_public_schema(client):
    """They must not appear in /openapi.json alongside the routes a browser
    calls. Documenting a write path for the least-trusted component is an
    invitation."""
    paths = client.get("/openapi.json").json()["paths"]

    assert not any(p.startswith("/api/internal") for p in paths)


def test_the_events_land_in_the_same_stream_the_browser_reads(client, token):
    """The point of the whole design: the browser does not know or care that
    the run happened in another container."""
    client.post(cb_url, headers=auth(token), json={"events": [LOG_EVENT]})

    frames = read_ws(client, RUN)
    assert any(f["text"] == LOG_EVENT["text"] for f in frames)


def test_a_report_for_a_terminal_run_is_refused(client, token):
    """A worker that survives its own cancellation must not resurrect a run."""
    store.set_run_status(RUN, rs.RUN_CANCELLED)

    r = client.post(cb_url, headers=auth(token), json={"events": [LOG_EVENT]})

    assert r.status_code == 409
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(api): run-scoped callback for the worker"
```

---

### Task 7: The worker entrypoint

**Files:**
- Create: `packages/implr_studio/worker.py`
- Test: `packages/implr_studio/tests/test_worker.py`

**Interfaces:**
- `python -m implr_studio.worker` — reads the job spec from the environment, then:
  clone → materialise → orchestrate → report → exit.
- Exit code `0` only on terminal run success.

- [ ] **Step 1: Write the failing test**

```python
def test_it_clones_the_ref_from_the_spec(fake_git): ...


def test_it_clones_shallow_at_the_named_sha(fake_git):
    """A branch name races: the run reports a sha it did not execute. And a
    full clone of a large monorepo is minutes of billed container time."""
    assert "--depth" in fake_git.argv
    assert SHA in fake_git.argv


def test_it_materialises_before_running(order):
    assert order.index("materialise") < order.index("orchestrate")


def test_it_reports_events_as_they_happen(fake_callback):
    """Not at the end. Phase 10's progressive log must survive the extra hop,
    or the container boundary silently un-does it."""
    assert fake_callback.batches_seen > 1


def test_it_exits_non_zero_when_the_run_fails(): ...
def test_it_exits_zero_only_on_terminal_success(): ...


def test_it_exits_non_zero_when_the_callback_is_unreachable():
    """A run whose events went nowhere is not a successful run, however well
    the agent did. Exiting 0 would strand it as `running` forever."""
    ...


def test_a_clone_failure_reports_a_readable_error_before_exiting():
    """The most common real failure: a revoked credential. It must arrive in
    the run's own log, not only in container stderr nobody reads."""
    ...
    assert "authentic" in reported_error.lower() or "permission" in reported_error.lower()


def test_it_writes_nothing_outside_the_workspace(tmp_path):
    """The image mounts / read-only except /workspace. Assert the code agrees,
    so the failure is a test rather than a crash at 3am in Azure."""
    ...


def test_the_api_key_is_read_from_the_environment_not_the_spec():
    assert "ANTHROPIC_API_KEY" not in json.dumps(spec_as_sent)


def test_it_flushes_pending_events_before_exiting():
    """The last few lines of a run - including the error - are the ones you
    most want. Batching that drops its tail on exit loses exactly those."""
    ...
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(worker): clone, materialise, run, report, exit"
```

---

### Task 8: The images actually build, and stay honest

**Files:**
- Modify: `docker/api.Dockerfile`, `docker/worker.Dockerfile`, `docker/compose.yaml`, `pyproject.toml`
- Test: `packages/implr_studio/tests/test_images.py` (marked `docker`)

**Interfaces:**
- `pytest.mark.docker` — needs a daemon; deselected by default like `live`.
- `CLAUDE_CLI_VERSION` becomes a **pinned** default, not `latest`.

- [ ] **Step 1: Write the failing test**

```python
pytestmark = pytest.mark.docker


def test_the_api_image_has_no_git():
    """A security property, not a packaging accident. Asserted because a
    Dockerfile is edited by people in a hurry."""
    assert run_in("implr-studio-api", "which git").returncode != 0


@pytest.mark.parametrize("tool", ["git", "node", "npm", "claude", "ssh", "curl"])
def test_the_api_image_cannot_execute_a_step(tool):
    assert run_in("implr-studio-api", "which %s" % tool).returncode != 0


def test_the_api_image_runs_as_non_root():
    assert run_in("implr-studio-api", "id -u").stdout.strip() == "10001"


def test_the_api_image_filesystem_is_writable_only_at_tmp():
    assert run_in("implr-studio-api", "touch /app/x", read_only=True).returncode != 0
    assert run_in("implr-studio-api", "touch /tmp/x", read_only=True).returncode == 0


def test_the_worker_image_has_the_toolchain():
    for tool in ("git", "node", "claude"):
        assert run_in("implr-studio-worker", "which %s" % tool).returncode == 0


def test_the_worker_image_runs_as_non_root():
    assert run_in("implr-studio-worker", "id -u").stdout.strip() == "10001"


def test_the_worker_container_has_no_database_url(compose_up):
    env = inspect_env("implr-studio-worker")

    assert "DATABASE_URL" not in env


def test_the_claude_cli_version_is_pinned(dockerfile):
    """An unpinned agent runtime is an unreviewed change to how every step
    behaves, arriving whenever someone rebuilds."""
    assert "CLAUDE_CLI_VERSION=latest" not in dockerfile


def test_the_healthcheck_passes(compose_up):
    assert wait_healthy("implr-studio-api", timeout=60)


def test_the_api_starts_with_a_read_only_root(compose_up):
    """compose.yaml sets read_only: true. If the app needs to write anywhere
    but /tmp, this is where it is discovered."""
    assert wait_healthy("implr-studio-api", timeout=60)
```

- [ ] **Step 2: Fix what the tests find, pin the CLI, run, commit**

```bash
git commit -m "build(docker): images build, and the trust split is asserted"
```

---

### Task 9: Run the demo

- [ ] **Step 1: Up**

```bash
docker compose -f docker/compose.yaml up --build
```

Both images build. `api` reaches **healthy**. The console loads at `127.0.0.1:8000`.

- [ ] **Step 2: The catalogue came from Postgres**

The palette lists nine steps. Prove where they came from:

```bash
docker compose exec db psql -U implr -d implr -c \
  "select step_id, source from steps order by step_id;"
```

Nine rows, `source = builtin`. Then `docker compose restart api` and confirm the sync reports
**0 inserted, 0 updated** — idempotent.

- [ ] **Step 3: A run in another container**

Press Run. `docker ps` shows a **second container**. Log lines stream **progressively** into the
browser. It exits; the node reports `succeeded`.

- [ ] **Step 4: The four security assertions**

```bash
docker run --rm implr-studio-api which git      # nothing
docker run --rm implr-studio-api which claude   # nothing
docker exec implr-studio-api-1 touch /app/x     # refused
docker inspect <worker> | grep DATABASE_URL     # nothing
```

- [ ] **Step 5: The adversarial one**

Take the worker's token from `docker inspect` and use it to post events to a **different** run id.
**403**, and the other run's event list is unchanged.

- [ ] **Step 6: Isolation of skills**

Author a custom skill in project A. Start a run in project **B**. In the worker container:

```bash
ls /workspace/.claude/skills
```

Project A's skill is **not there**. This is the one that matters — Phase 15 established that the
`skills=` list would not have saved you.

- [ ] **Step 7: Local mode is unchanged**

```bash
implr-studio --workspace $PROBE --fake
```

Identical to Phase 15. SQLite, files, one process. The seams are invisible.

---

## Definition of Done

- [ ] `python -m pytest` passes; `docker` and `live` suites deselected by default.
- [ ] `Settings` is frozen, parsed once; no module outside `config.py`/`cli.py` reads the
      environment, asserted by a source scan.
- [ ] Hosted mode without `DATABASE_URL` or `JOB_TOKEN_KEY` refuses to boot, naming the variable.
- [ ] **Worker mode with a `DATABASE_URL` refuses to boot.**
- [ ] `AUTH_MODE=dev` is refused with a real launcher configured.
- [ ] Both launchers satisfy `RunLauncher`; `JobSpec` is frozen and carries no secret.
- [ ] `SubprocessLauncher` passes no `DATABASE_URL`, mounts `/workspace` as tmpfs, sets
      `--read-only` and `no-new-privileges`, and `cancel` removes the container.
- [ ] Both catalogue sources satisfy `CatalogueSource` and **agree on the nine shipped steps**.
- [ ] Plugin sync is idempotent, updates a changed builtin, **never touches a project row**, and
      disables rather than deletes a removed builtin.
- [ ] Sync completes before the server serves.
- [ ] `PgStore` and `Store` expose the identical public surface, asserted by reflection, and pass
      **one shared contract suite** including the concurrency hammer.
- [ ] `schema.sql` has `tenant_id` on every owned table and composite FKs on `node_runs`,
      `events`, `questions` — Phase 17 needs both.
- [ ] Materialisation refuses unsafe names, refuses a symlinked target, writes **nothing** on
      refusal, writes **only** the payload, and is idempotent.
- [ ] The job token is run-scoped: **a token for one run gets 403 on another**, and nothing is
      written.
- [ ] `/api/internal/*` is absent from `/openapi.json`.
- [ ] A callback for a terminal run is a 409.
- [ ] The worker clones shallow at a **sha**, materialises before running, reports progressively,
      flushes on exit, exits non-zero on failure *and* on an unreachable callback.
- [ ] **API image:** no git, node, npm, claude, ssh or curl; uid 10001; writable only at `/tmp`.
- [ ] **Worker image:** has git, node, claude; uid 10001; CLI version **pinned**, not `latest`.
- [ ] `docker compose up --build` reaches healthy and runs a pipeline in a separate container.
- [ ] Project A's custom skill is absent from project B's worker workspace.
- [ ] **Local mode is byte-for-byte the Phase 15 experience.**

---

## Known limitations, kept

**No RLS yet.** Postgres arrives here with `tenant_id` columns and no policies. The compose stack
is therefore **not safe to expose** — `AUTH_MODE=dev` trusts a header, and a bug in a route's
scoping is a cross-tenant read. Phase 17 closes it, and the graph's `17 before 19` edge is what
keeps this window off the internet.

**One container per run, started eagerly.** No queue, no concurrency cap, no fairness. A tenant
that starts thirty runs starts thirty containers. Container Apps Jobs has its own concurrency
controls, which is where this belongs rather than in application code.

**Events are unbounded in Postgres.** No archive to Blob, no retention. A `dev-executor` run over
twenty plans produces a great deal of append-only text, and Postgres is the wrong home for it at
volume. Phase 19 sets the threshold.

**Azurite is stubbed, not used.** It is in the compose file so the Blob code path has somewhere to
point when Phase 19 needs it.

---

## What the next phase gets

A hosted topology with no identity. **Phase 17** adds tenants, users, projects, Entra token
validation and row-level security — and it can, because this phase put `tenant_id` on every owned
table and a composite foreign key on the three hot ones. Adding a column under a live RLS policy is
the migration nobody wants; doing it here, before any policy exists, costs nothing.
