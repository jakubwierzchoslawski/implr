# implr Studio — Phase 19: Deploy to Azure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A real run, in a real subscription, streaming to a browser over HTTPS with Entra sign-in — and every control verified rather than assumed.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-hosted-design.md` (*Azure services*, *Topology*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 17. **Do not put an unauthenticated agent runner on the public internet.**
Of every edge in the dependency graph, that is the one not to reorder.

**⚠ This phase spends money and writes to a real repository.** Run the pipeline with `--dry-run`
first. It also creates billable Azure resources — the teardown script is part of the deliverable,
not an afterthought.

---

## Demo

```bash
az deployment sub create \
  --location westeurope \
  --template-file deploy/azure/main.bicep \
  --parameters deploy/azure/params.dev.bicepparam
```

Open the app's HTTPS URL. Entra sign-in. Connect a repository. Run a pipeline. Log lines stream
into the browser from a Container Apps Job you can see in the portal.

Then the controls, each **verified**:

```bash
# the worker cannot reach the internet at large, but can reach Anthropic
az containerapp job start -n implr-worker -g $RG \
  --command "sh -c 'getent hosts example.com; getent hosts api.anthropic.com'"

# postgres has no public endpoint
az postgres flexible-server show -n $PG -g $RG --query network

# the worker has no database credentials
az containerapp job show -n implr-worker -g $RG --query "properties.template.containers[0].env"
```

Then tear it down and confirm the bill stops:

```bash
az group delete -n $RG --yes
```

---

## A correction to the design spec, stated up front

The hosted design says the worker gets **no managed identity**. That is not achievable, and
noticing why is better than discovering it during a deployment.

**A Container Apps Job must pull its own image.** Pulling from a private ACR requires an
identity with `AcrPull`. So the job has an identity whether we like it or not; the question was
never *whether* but *how narrow*.

Given that, the right shape is:

> The worker job has a **user-assigned managed identity with exactly two role assignments**:
> `AcrPull` on the registry, and `Key Vault Secrets User` scoped to **one secret** — the Anthropic
> key. No Blob, no Postgres, no ARM, no other secret, no subscription-level anything.

The alternative — the API resolving the key and passing it in the job-start payload — is worse,
and worse in a non-obvious way: a job-start template override lands in **ARM activity logs and
job execution history**, which are retained, exportable, and readable by anyone with Reader on
the resource group. A scoped identity keeps the secret out of every log.

**Consequence for the spec's table:** the *Managed Identity* row changes from "API only. The
worker gets none" to "API: ACR pull, Key Vault, Blob. Worker: ACR pull and **one** Key Vault
secret." Update it as part of this phase; do not leave the two documents disagreeing.

The properties that actually mattered are unchanged and still asserted: **no database
credentials, no Blob access, no ARM permissions, no access to any other run's state.**

---

## The three open questions, decided

The hosted spec left three deliberately. Proceeding needs answers, so here they are with the
reasoning; each is a one-line change if you disagree.

**1. Who supplies the Anthropic credential? → Bring-your-own, per tenant.**
You never see their spend, they never wait on your quota, and a runaway `dev-executor` loop is
their bill and their incident. A platform key needs per-tenant metering, quotas and a spend
alarm *before* it needs anything else — that is a product, not a phase. Store one secret per
tenant, named `anthropic-key-{tenant_id}`, and grant the job identity `Key Vault Secrets User` at
the **secret** scope, not the vault scope.

Note this makes the "one secret" above "one secret per tenant", and the grant is created when a
tenant supplies a key. That is a real complication and it is the right one: the failure mode of
the simpler design is one tenant's key running another tenant's work.

**2. How does the worker reach the repository? → A GitHub App.**
Scoped to selected repositories, revocable by the customer without involving you, auditable in
their org's log, and it issues short-lived installation tokens rather than a credential that
lives in your vault forever. A PAT is faster today and ages into an incident: it is long-lived,
broadly scoped, attributed to a human who will eventually leave, and its rotation is a
conversation.

**3. Is `--dry-run` the hosted default? → Yes, for a project's first run.**
An agent that writes to a real branch on a button press, in someone else's infrastructure,
deserves a deliberate opt-in. After the first successful dry run the console offers "run for
real" and remembers the choice per project. Phase 18 already builds this; this phase makes it
the hosted default rather than a suggestion.

---

## Scope boundary — not in this phase

- **No multi-region, no geo-redundancy.** One region, zone-redundant where the SKU gives it free.
- **No autoscaling tuning.** Container Apps defaults, min replicas 0 for the API (scale-to-zero is
  most of why it was chosen).
- **No blue/green or canary.** Container Apps revisions exist; using them properly is a release-
  engineering phase.
- **No cost dashboards or budget automation.** A budget **alert** is in scope; acting on it is not.
- **No SOC2/ISO evidence collection.** The controls exist and are tested; producing an auditor's
  package is separate work.
- **No customer-managed keys.** Platform-managed encryption at rest.
- **No private ingress.** The API is public by design — customers sign in from browsers. Postgres
  is what must not be public.

---

## Global constraints

**Everything is in bicep, and the bicep is the only way anything is created.** A resource created
by hand in the portal is a resource nobody can recreate and nobody remembers to delete. The
runbook contains `az deployment` commands and no portal click-paths except where the platform
genuinely offers no API (the GitHub App creation, which is on GitHub's side anyway).

**Two identities, both user-assigned, neither shared.** User-assigned rather than system-assigned
so the role assignments survive a container app being replaced — a system-assigned identity is
deleted with its resource, and re-deploying then silently drops every grant.

**Least privilege is asserted, not intended.** A test enumerates each identity's role
assignments and fails on anything unexpected. "We meant to remove that" is not a control.

**The egress allowlist must include the platform's own dependencies.** This is the mistake that
costs an afternoon: an FQDN allowlist tight enough to feel secure blocks Container Apps from
pulling images, reaching its own control plane, and shipping logs — and the failure looks like a
broken image rather than a firewall rule. The allowlist is derived from the platform
documentation and **tested by a job that actually runs**, not by reading it.

**Postgres is created with private access and never had a public endpoint.** Flexible Server
cannot be moved between public and private access after creation — getting this wrong means
recreating the server, which for a database with customer data is a migration.

**No secret is ever a bicep parameter with a value in a file.** Key Vault references only.
`params.*.bicepparam` is committed; it contains resource names and no secrets.

**Teardown is a deliverable.** A script that removes everything, verified by running it. A demo
environment nobody can delete becomes a permanent line on a bill.

---

## File Structure

| File | Responsibility |
|---|---|
| `deploy/azure/main.bicep` | Subscription-scope entry: resource group + modules. |
| `deploy/azure/modules/network.bicep` | VNet, subnets, NAT, Azure Firewall, FQDN rules, UDR. |
| `deploy/azure/modules/data.bicep` | Postgres Flexible Server (private), Blob, private endpoints. |
| `deploy/azure/modules/vault.bicep` | Key Vault (RBAC), secrets, role assignments. |
| `deploy/azure/modules/registry.bicep` | ACR. |
| `deploy/azure/modules/identity.bicep` | The two user-assigned identities and every role assignment. |
| `deploy/azure/modules/app.bicep` | Container Apps environment, the API app, EasyAuth. |
| `deploy/azure/modules/job.bicep` | The worker job, manual trigger. |
| `deploy/azure/modules/observability.bicep` | Log Analytics, App Insights, the budget alert. |
| `deploy/azure/params.dev.bicepparam` | Names only. No secrets. |
| `deploy/azure/README.md` | **The runbook.** Prerequisites → first run → teardown. |
| `deploy/azure/teardown.sh` | Removes everything. |
| `.github/workflows/images.yml` | Build and push both images to ACR. |
| `packages/implr_studio/launchers/containerapps.py` | `ContainerAppsJobLauncher`. |
| `packages/implr_studio/blob.py` | Log archive + KB uploads. |
| `packages/implr_studio/tests/test_azure_controls.py` | Marked `azure`. Asserts the controls. |

---

### Task 1: The Container Apps Job launcher

**Files:**
- Create: `packages/implr_studio/launchers/containerapps.py`
- Test: `packages/implr_studio/tests/test_containerapps_launcher.py`

**Interfaces:**
- `ContainerAppsJobLauncher(subscription, resource_group, job_name, credential)` — satisfies
  Phase 16's `RunLauncher`.
- `launch(job)` → starts an execution with env overrides; returns the execution name as the handle.
- `cancel(handle)` → stops that execution.

**The third implementation of the seam.** If it needs the interface to change, Phase 16 drew it in
the wrong place — that is worth knowing now rather than accommodating quietly.

- [ ] **Step 1: Write the failing test**

```python
def test_it_satisfies_the_launcher_protocol():
    """Third implementation, unchanged interface. If this needed a new method,
    the seam was wrong."""
    assert isinstance(ContainerAppsJobLauncher(**kw), RunLauncher)


def test_launch_starts_an_execution_with_the_job_spec(fake_arm):
    await launcher.launch(job)

    assert fake_arm.last_path.endswith("/start")
    assert env_of(fake_arm.last_body)["IMPLR_RUN_ID"] == job.run_id


def test_no_secret_is_in_the_start_payload(fake_arm):
    """THE test. A job-start template override lands in ARM activity logs and
    job execution history - retained, exportable, and readable by anyone with
    Reader on the resource group. The key comes from the job's own scoped
    Key Vault reference instead."""
    await launcher.launch(job)

    body = json.dumps(fake_arm.last_body)
    assert "ANTHROPIC_API_KEY" not in body
    assert "sk-ant" not in body
    assert "postgresql://" not in body


def test_the_job_token_is_passed_as_a_secret_ref_not_a_literal(fake_arm):
    """Phase 16's run-scoped token. Short-lived, but 'short-lived' and
    'written to a retained log' still compose badly."""
    assert "secretRef" in json.dumps(fake_arm.last_body)


def test_cancel_stops_that_execution_only(fake_arm):
    """Phase 14's Abort, three layers down. Stopping the wrong execution
    aborts another tenant's run."""
    await launcher.cancel(handle)

    assert fake_arm.last_path.endswith("/executions/%s/stop" % handle.execution)


def test_a_quota_error_is_a_readable_failure(fake_arm):
    """The most likely real failure on a new subscription, and 'RequestFailed'
    in a red box is not an instruction."""
    fake_arm.fail(429, "quota exceeded for Microsoft.App/jobs")

    ...
    assert "quota" in error.lower()


def test_a_403_from_arm_names_the_missing_role(fake_arm):
    """The second most likely, and the fix is a role assignment - which the
    error should name rather than making somebody guess."""
    fake_arm.fail(403, "does not have authorization to perform action")

    ...
    assert "role" in error.lower() or "permission" in error.lower()


def test_transient_arm_failures_are_retried_with_backoff(fake_arm):
    """ARM is eventually consistent and rate-limited. One 429 must not fail a
    run the user just started."""
    fake_arm.fail_times(2, 429)

    await launcher.launch(job)

    assert fake_arm.attempts == 3


def test_it_does_not_retry_a_403(fake_arm):
    """Retrying an authorization failure is a delay dressed as resilience."""
    fake_arm.fail(403, "forbidden")

    with pytest.raises(LaunchError):
        await launcher.launch(job)
    assert fake_arm.attempts == 1


def test_launching_is_idempotent_per_run(fake_arm):
    """A double-click, or a retried HTTP request, must not start two
    containers against one workspace. Two agents writing one git worktree is
    the worst bug in this document."""
    await launcher.launch(job)
    await launcher.launch(job)

    assert fake_arm.start_calls == 1
```

That last test is the one to write first. Two workers cloning and writing the same repository at
the same time produces a corrupt result that looks like a model failure.

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(launcher): container apps job launcher"
```

---

### Task 2: Network — the part that is easy to get wrong

**Files:**
- Create: `deploy/azure/modules/network.bicep`
- Test: `packages/implr_studio/tests/test_azure_controls.py` (marked `azure`)

**Interfaces:**
- VNet with four subnets: `apps` (delegated to `Microsoft.App/environments`), `jobs`,
  `postgres` (delegated to `Microsoft.DBforPostgreSQL/flexibleServers`), `firewall`.
- Azure Firewall with **application rules** (FQDN), a route table pointing `0.0.0.0/0` at it, and
  the UDR attached to the jobs subnet.

- [ ] **Step 1: Write the allowlist, with the platform's own dependencies**

```bicep
// FQDN application rules for the worker subnet.
//
// The trap: an allowlist tight enough to feel secure blocks Container Apps from
// pulling images and reaching its own control plane - and the failure surfaces
// as "image pull error", not "firewall". Both groups below are required.
var workRules = [
  'api.anthropic.com'          // the model
  'github.com'                 // git over HTTPS
  'codeload.github.com'        // github's archive/clone endpoint
  'registry.npmjs.org'         // the pinned Claude CLI is already in the image;
                               // this is for skills that install a dev toolchain
]

var platformRules = [
  'mcr.microsoft.com'          // base images
  '*.data.mcr.microsoft.com'
  '${acrName}.azurecr.io'      // our images
  '*.blob.core.windows.net'    // ACR layer storage AND our log archive
  'login.microsoftonline.com'  // managed identity token acquisition
  '*.vault.azure.net'          // the one scoped secret
  'dc.services.visualstudio.com'   // App Insights
  '*.monitor.azure.com'
]
```

- [ ] **Step 2: Write the failing test**

```python
pytestmark = pytest.mark.azure


def test_the_worker_cannot_resolve_an_arbitrary_host():
    """The whole point of the egress rules. Run it as a real job, because a
    firewall rule that reads correctly and does not apply is the normal
    failure mode."""
    out = run_job_command("getent hosts example.com; echo rc=$?")

    assert "rc=0" not in out


def test_the_worker_can_reach_anthropic():
    out = run_job_command("curl -s -o /dev/null -w '%{http_code}' "
                          "https://api.anthropic.com/v1/messages")

    assert out.strip() in ("401", "400")      # reached it; refused, as expected


def test_the_worker_can_clone_the_repository():
    assert run_job_command("git ls-remote %s HEAD" % REPO).returncode == 0


def test_the_worker_cannot_reach_the_database():
    """It has no credentials. It should also have no route."""
    out = run_job_command("timeout 5 sh -c '</dev/tcp/%s/5432'; echo rc=$?" % PG_FQDN)

    assert "rc=0" not in out


def test_the_worker_cannot_reach_the_api_management_plane():
    out = run_job_command("curl -s -m 5 -o /dev/null -w '%{http_code}' "
                          "https://management.azure.com/subscriptions?api-version=2020-01-01")

    assert out.strip() in ("000",)            # blocked, not merely unauthorized


def test_the_platform_dependencies_are_reachable():
    """The other half. If this fails, the job cannot start at all - and the
    error will point at the image, not the firewall."""
    assert run_job_command("getent hosts mcr.microsoft.com").returncode == 0


def test_postgres_has_no_public_endpoint():
    net = az("postgres flexible-server show -n %s --query network" % PG)

    assert net["publicNetworkAccess"] == "Disabled"


def test_postgres_is_not_resolvable_from_outside_the_vnet():
    """The property, not the setting. A private DNS zone misconfiguration can
    leave the setting right and the name resolving publicly."""
    assert public_dns_lookup(PG_FQDN) is None
```

- [ ] **Step 3: Implement, deploy, run, commit**

```bash
git commit -m "deploy(azure): network, firewall and the egress allowlist"
```

---

### Task 3: Identity, and least privilege as an assertion

**Files:**
- Create: `deploy/azure/modules/identity.bicep`, `vault.bicep`
- Test: `packages/implr_studio/tests/test_azure_controls.py`

**Interfaces:**
- `id-implr-api` — `AcrPull` on ACR, `Key Vault Secrets User` on the vault, `Storage Blob Data
  Contributor` on the container, and a **custom role** with exactly
  `Microsoft.App/jobs/start/action` and `Microsoft.App/jobs/executions/*/stop/action`.
- `id-implr-worker` — `AcrPull` on ACR, and `Key Vault Secrets User` **at secret scope** on the
  Anthropic secrets. Nothing else.

**Why a custom role for starting jobs.** The built-in `Container Apps Contributor` lets the holder
edit the job definition — including its image and its identity. An identity that can rewrite the
worker's image is an identity that can run arbitrary code with the worker's permissions. Start and
stop are the two verbs the API needs.

- [ ] **Step 1: Write the failing test**

```python
def test_the_api_identity_has_exactly_the_expected_roles():
    """Enumerated, not spot-checked. 'We meant to remove that one' is not a
    control."""
    roles = role_assignments(API_IDENTITY)

    assert roles == {
        ("AcrPull", ACR_ID),
        ("Key Vault Secrets User", VAULT_ID),
        ("Storage Blob Data Contributor", CONTAINER_ID),
        ("implr Job Starter", JOB_ID),
    }


def test_the_worker_identity_has_exactly_two_roles():
    roles = role_assignments(WORKER_IDENTITY)

    assert {r[0] for r in roles} == {"AcrPull", "Key Vault Secrets User"}


def test_the_worker_key_vault_grant_is_scoped_to_secrets_not_the_vault():
    """Vault scope would let the worker read the database password and the git
    credential. Secret scope is one line of bicep and the difference between
    a compromised worker and a compromised deployment."""
    scopes = [s for r, s in role_assignments(WORKER_IDENTITY)
              if r == "Key Vault Secrets User"]

    assert all("/secrets/" in s for s in scopes)


def test_the_worker_identity_has_no_data_plane_role():
    for role, _ in role_assignments(WORKER_IDENTITY):
        assert "Blob" not in role
        assert "PostgreSQL" not in role
        assert "Contributor" not in role or role == "AcrPull"


def test_the_job_starter_role_cannot_edit_the_job():
    """An identity that can rewrite the worker's image can run arbitrary code
    with the worker's permissions."""
    perms = custom_role_permissions("implr Job Starter")

    assert perms["actions"] == ["Microsoft.App/jobs/start/action",
                                "Microsoft.App/jobs/executions/*/stop/action"]
    assert not any(a.endswith("/write") for a in perms["actions"])


def test_both_identities_are_user_assigned():
    """System-assigned identities are deleted with their resource, and
    re-deploying then silently drops every role assignment above."""
    for ident in (API_IDENTITY, WORKER_IDENTITY):
        assert ident["type"] == "Microsoft.ManagedIdentity/userAssignedIdentities"


def test_the_vault_uses_rbac_not_access_policies():
    """Access policies are per-vault and coarse; they cannot express
    secret-scoped grants, which the worker's grant depends on."""
    assert az("keyvault show -n %s" % VAULT)["properties"]["enableRbacAuthorization"] is True


def test_no_secret_value_appears_in_any_deployment_parameter():
    """Deployment history is retained and readable with Reader."""
    for d in az("deployment group list -g %s" % RG):
        assert "sk-ant" not in json.dumps(d)
        assert "password" not in json.dumps(d.get("properties", {}).get("parameters", {}))


def test_the_api_cannot_read_the_worker_workspace():
    """There is nothing to read - the job's storage is ephemeral. Asserted
    because 'we'll add a shared volume for logs' is a tempting shortcut that
    would undo the isolation."""
    assert job_volumes(JOB) == []
```

- [ ] **Step 2: Implement, deploy, run, commit**

```bash
git commit -m "deploy(azure): two identities, least privilege, asserted"
```

---

### Task 4: Data — Postgres, Blob, and the log archive

**Files:**
- Create: `deploy/azure/modules/data.bicep`, `packages/implr_studio/blob.py`
- Test: `packages/implr_studio/tests/test_blob.py`, `test_azure_controls.py`

**Interfaces:**
- Postgres Flexible Server, **private access**, delegated subnet, private DNS zone, PITR on.
- Two roles created by a bootstrap job: `implr_migrator` (owner) and `implr_app` (no `BYPASSRLS`) —
  Phase 17's requirement, now created by infrastructure rather than by hand.
- `blob.archive_events(run_id, events)` — beyond `EVENT_TAIL_KEEP` per run.
- Blob layout: `tenant/{tenant_id}/project/{project_id}/run/{run_id}/log.ndjson`.

- [ ] **Step 1: Write the failing test**

```python
def test_the_blob_path_is_tenant_prefixed():
    """A flat container makes one tenant's uploads guessable. The prefix is
    also what makes per-tenant SAS scoping possible later."""
    path = blob.log_path(tenant_id=T, project_id=P, run_id=R)

    assert path.startswith("tenant/%s/" % T)


def test_a_path_cannot_be_escaped_by_an_id():
    """Ids come from the database, but the function is also called from a
    worker whose input is a job payload."""
    with pytest.raises(ValueError):
        blob.log_path(tenant_id="../other", project_id=P, run_id=R)


def test_archiving_leaves_the_tail_in_postgres(store):
    """The recent tail is what the UI reads on load. Archiving all of it makes
    every run page a blob fetch."""
    archive_and_prune(store, RUN)

    assert len(store.events(RUN)) == blob.EVENT_TAIL_KEEP


def test_an_archived_run_still_renders_its_full_log(client):
    """Otherwise the archive is a delete with extra steps."""
    body = client.get(url("/runs/%s/log" % RUN)).json()

    assert len(body["events"]) == TOTAL


def test_archiving_is_not_on_the_hot_path(api_source):
    """A blob write in the event-append path adds latency to every log line
    and a new failure mode to every run."""
    assert "archive_events" not in append_event_source


def test_the_app_role_exists_and_lacks_bypassrls():
    """Phase 17's requirement, now created by infrastructure. A role created
    by hand in one environment is a role missing in the next."""
    row = query_as_admin("select rolbypassrls from pg_roles where rolname='implr_app'")

    assert row["rolbypassrls"] is False


def test_the_app_role_is_not_the_table_owner():
    assert all(o != "implr_app" for o in table_owners())


def test_point_in_time_restore_is_enabled():
    assert az("postgres flexible-server show -n %s" % PG)["backup"]["backupRetentionDays"] >= 7


def test_the_database_password_is_a_key_vault_reference(app_config):
    """Not a literal, not a deployment parameter."""
    assert app_config["secrets"]["db-password"]["keyVaultUrl"].startswith("https://")
```

- [ ] **Step 2: Implement, deploy, run, commit**

```bash
git commit -m "deploy(azure): private postgres, blob archive, db roles from bicep"
```

---

### Task 5: The app, EasyAuth, and observability

**Files:**
- Create: `deploy/azure/modules/app.bicep`, `job.bicep`, `observability.bicep`
- Test: `packages/implr_studio/tests/test_azure_controls.py`

**Interfaces:**
- Container Apps environment, VNet-integrated, workload profile.
- The API app: external ingress, managed TLS, min replicas **0**, `authConfigs` for Entra.
- The worker job: `triggerType: 'Manual'`, `replicaTimeout`, `replicaRetryLimit: 0`.
- Log Analytics, App Insights, and a **budget alert** on the resource group.

**`replicaRetryLimit: 0` is a decision, not a default.** Phase 14 established that automatic retry
of an agent step is wrong: a step that failed by half-writing a file will half-write it again, and
a crash loop bills. The platform must not retry behind the orchestrator's back.

- [ ] **Step 1: Write the failing test**

```python
def test_the_api_requires_authentication_at_the_ingress():
    """Defence in depth: EasyAuth in front, and the API validates the token
    itself. Either alone is one misconfiguration from open."""
    r = requests.get("%s/api/projects" % APP_URL)

    assert r.status_code in (302, 401)


def test_the_api_validates_the_token_itself_not_just_easyauth():
    """A forged EasyAuth header must not be enough. If the platform is the
    only check, a bypass of it is total."""
    r = requests.get("%s/api/projects" % APP_URL,
                     headers={"X-MS-CLIENT-PRINCIPAL-ID": "forged"})

    assert r.status_code == 401


def test_health_is_reachable_unauthenticated():
    """Container Apps probes it before any identity exists."""
    assert requests.get("%s/api/health" % APP_URL).status_code == 200


def test_tls_is_managed_and_http_redirects():
    assert requests.get(APP_URL.replace("https://", "http://"),
                        allow_redirects=False).status_code in (301, 307, 308)


def test_the_api_scales_to_zero():
    """Most of why Container Apps was chosen. A demo environment that bills
    at idle is a demo environment somebody deletes."""
    assert az("containerapp show -n %s" % APP)["properties"]["template"]["scale"]["minReplicas"] == 0


def test_the_job_does_not_retry():
    """Phase 14: automatic retry of an agent step is wrong. The platform must
    not do it behind the orchestrator's back."""
    assert az("containerapp job show -n %s" % JOB)["properties"]["configuration"][
        "replicaRetryLimit"] == 0


def test_the_job_has_a_hard_timeout():
    """An agent loop is unbounded in time as well as in dollars."""
    assert 0 < az("containerapp job show -n %s" % JOB)["properties"]["configuration"][
        "replicaTimeout"] <= 7200


def test_the_job_has_no_database_url():
    env = job_env(JOB)

    assert "DATABASE_URL" not in env


def test_the_websocket_survives_the_ingress():
    """Container Apps ingress supports it; a misconfigured transport setting
    silently downgrades Phase 10's live log to nothing."""
    assert ws_roundtrip("%s/api/projects/%s/runs/%s/stream" % (WS_URL, P, R))


def test_a_budget_alert_exists():
    """The cheapest control in this document. An agent runner with no budget
    alarm is one bad loop from a memorable invoice."""
    assert az("consumption budget list -g %s" % RG) != []


def test_run_logs_reach_log_analytics():
    """When a job fails before the callback works, this is the only evidence."""
    assert query_logs("ContainerAppConsoleLogs_CL | where ContainerName_s == 'worker'") != []
```

- [ ] **Step 2: Implement, deploy, run, commit**

```bash
git commit -m "deploy(azure): container app, easyauth, job, observability"
```

---

### Task 6: Images, from CI

**Files:**
- Create: `.github/workflows/images.yml`
- Test: the workflow itself

**Interfaces:**
- OIDC federated credential to Azure — **no** stored `AZURE_CREDENTIALS` secret.
- Both images built and pushed, tagged with the commit sha **and** `latest`.
- The deployment references the **sha**, never `latest`.

- [ ] **Step 1: Write it**

```yaml
name: images
on:
  push:
    branches: [main]
permissions:
  id-token: write        # OIDC to Azure. No long-lived credential in secrets.
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
      - run: az acr login -n ${{ vars.ACR_NAME }}
      - name: api
        run: |
          docker build -f docker/api.Dockerfile \
            -t ${{ vars.ACR_NAME }}.azurecr.io/implr-studio-api:${{ github.sha }} .
          docker push ${{ vars.ACR_NAME }}.azurecr.io/implr-studio-api:${{ github.sha }}
      - name: worker
        run: |
          docker build -f docker/worker.Dockerfile \
            -t ${{ vars.ACR_NAME }}.azurecr.io/implr-studio-worker:${{ github.sha }} .
          docker push ${{ vars.ACR_NAME }}.azurecr.io/implr-studio-worker:${{ github.sha }}
```

- [ ] **Step 2: Assert the deployment pins a sha**

```python
def test_the_deployment_references_a_sha_not_latest():
    """`latest` means the running code is whatever was pushed most recently -
    unreviewable, unrollbackable, and different between the app and the job."""
    for image in (app_image(), job_image()):
        assert not image.endswith(":latest")
        assert re.search(r":[0-9a-f]{40}$", image)


def test_the_app_and_the_job_run_the_same_sha():
    """A worker one commit ahead of the API is a contract mismatch nobody
    would think to look for."""
    assert sha_of(app_image()) == sha_of(job_image())
```

- [ ] **Step 3: Commit**

```bash
git commit -m "ci: build both images to ACR over OIDC"
```

---

### Task 7: The runbook, and teardown

**Files:**
- Create: `deploy/azure/README.md`, `deploy/azure/teardown.sh`

**The runbook's structure**, because a runbook that is a wall of `az` commands does not get
followed:

1. **What you need before you start** — subscription with `Microsoft.App` registered, an Entra app
   registration, a GitHub App, and an Anthropic key. With the *exact* commands, and what each is
   for.
2. **Deploy** — one `az deployment sub create`, then the image build, then the revision update.
3. **First tenant** — sign in, and what happens automatically (Phase 17 provisions).
4. **First project** — Phase 18's flow.
5. **Verify the controls** — the same commands as this phase's demo. Not optional; the section
   says so.
6. **What it costs** — an honest table at idle and under a run, with the scale-to-zero caveat.
7. **Teardown** — one script, and how to confirm the bill stopped.
8. **Troubleshooting** — the failures that will actually happen, with their real causes:

| Symptom | Real cause |
|---|---|
| Job fails instantly, "image pull error" | The firewall allowlist is missing `mcr.microsoft.com` or the ACR blob endpoint |
| Job starts, agent never responds | `api.anthropic.com` not in the allowlist, or the Key Vault grant is at vault scope and was removed |
| API returns 500 on every request | `implr_app` role not created, or it owns the tables (Phase 17) |
| Sign-in loops | Redirect URI in the app registration does not match the Container Apps FQDN |
| Log pane stays empty | WebSocket blocked at ingress, or the callback token key differs between app and job |
| Everything works, nothing persists | Postgres private DNS zone not linked to the VNet; the app is talking to a different server |

- [ ] **Step 1: Write both**
- [ ] **Step 2: Run teardown, and redeploy from scratch**

The redeploy is the test. A runbook that has only been followed forwards once, by its author, on a
subscription with leftover state, is a hypothesis.

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(deploy): the azure runbook and teardown"
```

---

### Task 8: Run the demo

- [ ] **Step 1: Deploy from nothing**

Fresh resource group. One `az deployment sub create`. Then images, then the revision.

- [ ] **Step 2: Sign in and run**

Entra sign-in over managed TLS. Connect a repository. Run a pipeline with `--dry-run`. Log lines
stream from a Container Apps Job you can watch in the portal. The repository is **unmodified**.

- [ ] **Step 3: The controls, each verified**

- `example.com` unresolvable from the worker; `api.anthropic.com` reachable.
- Postgres `publicNetworkAccess: Disabled`, and not resolvable from outside the VNet.
- The worker job has **no** `DATABASE_URL`.
- The worker identity has **exactly** `AcrPull` and one secret-scoped Key Vault grant.
- The API identity cannot rewrite the job definition.
- The deployment references a **sha**; app and job match.
- A budget alert exists.

- [ ] **Step 4: Failure paths in the real thing**

Abort a live run → the job execution stops in the portal, not just in the UI. Kill the API
revision mid-run → on the new revision, Phase 14's recovery reports the node `failed` naming the
restart. Set the job timeout to 60s and run something longer → the node fails saying **timeout**,
not with a stack trace.

- [ ] **Step 5: Then, for real**

One real run without `--dry-run`, on a throwaway repository. It opens a branch and a PR. Check
the diff.

- [ ] **Step 6: Tear it down**

```bash
./deploy/azure/teardown.sh
```

Then redeploy from the runbook, following it literally.

---

## Definition of Done

- [ ] `python -m pytest` passes; `azure`-marked tests pass against a real subscription.
- [ ] `ContainerAppsJobLauncher` satisfies Phase 16's `RunLauncher` **unchanged**.
- [ ] **No secret in a job-start payload**, in a deployment parameter, or in deployment history.
- [ ] Launching is **idempotent per run** — a double-click starts one container.
- [ ] Transient ARM failures are retried with backoff; a 403 is not retried and names the role.
- [ ] Worker egress: `example.com` blocked, `api.anthropic.com` reachable, git reachable, Postgres
      unreachable, ARM unreachable — **each tested by a job that ran**.
- [ ] The platform's own FQDN dependencies are in the allowlist and reachable.
- [ ] Postgres has no public endpoint and is not publicly resolvable; PITR ≥ 7 days.
- [ ] `implr_app` is created **by bicep**, lacks `BYPASSRLS`, and owns no tables.
- [ ] The API identity has **exactly** four role assignments, one of them a custom start/stop role
      that cannot edit the job.
- [ ] The worker identity has **exactly** `AcrPull` and `Key Vault Secrets User` **at secret
      scope**, and no data-plane role.
- [ ] Both identities are user-assigned; the vault uses RBAC.
- [ ] The job has no volumes — nothing shared with the API.
- [ ] EasyAuth is on **and** the API validates the token itself; a forged principal header is 401.
- [ ] `/api/health` is unauthenticated; HTTP redirects to HTTPS; the API scales to zero.
- [ ] The job has `replicaRetryLimit: 0` and a hard timeout ≤ 2h.
- [ ] The WebSocket survives the ingress.
- [ ] A **budget alert** exists; worker console logs reach Log Analytics.
- [ ] CI uses OIDC, not a stored credential; the deployment pins a **sha**; app and job shas match.
- [ ] The blob log archive is tenant-prefixed, escape-proof, leaves the tail in Postgres, renders a
      full log, and is **not** on the event-append hot path.
- [ ] `deploy/azure/README.md` covers prerequisites → deploy → first tenant → first project →
      verify → cost → teardown → troubleshooting.
- [ ] **Teardown ran, and a redeploy from the runbook succeeded.**
- [ ] The hosted design spec's *Managed Identity* row is corrected, and the three open questions
      are marked settled with the decisions above.

---

## Known limitations, kept

**Single region.** No failover. A region outage is an outage. Multi-region needs a replicated
database and a story for in-flight runs, which is a larger design than this phase.

**No per-tenant spend metering.** BYO keys mean you never see their spend — which is the *point*,
and also means you cannot warn them before they are surprised. `ResultMessage.total_cost_usd` is
recorded per step (Phase 15), so the data exists; the dashboard does not.

**The GitHub App's installation token lives in memory.** Short-lived and never persisted, which is
right — and it means a run that outlives the token needs a refresh path. Long `dev-executor` runs
will find this.

**The firewall allowlist will need maintenance.** Azure adds endpoints. When a job starts failing
to pull an image after a platform update, the allowlist is the first place to look — which is why
the troubleshooting table leads with it.

**No customer-managed keys, no VNet-injected private ingress, no auditor package.** All defensible
for a first production deployment and all things an enterprise procurement process will ask about.

---

## What comes after this

The product is deployed and the phase list is done. What the sequence deliberately left for later,
in the order it will be asked for:

1. **Session resumption** (Phase 15's follow-up) — the highest-value single item. It turns a
   crashed twenty-minute `dev-executor` run from a full retry into a resume.
2. **Per-artefact rejection** (Phase 13's follow-up) — makes request-changes cheap instead of a
   full re-run.
3. **`ProjectGrantPolicy`, wired** (Phase 17) — the table, the policy and the tests exist; turning
   it on is a config line plus a role editor UI.
4. **Retention and archive policy** (Phase 16) — events grow without bound.
5. **Spend metering** — needed the moment anyone asks for a platform key instead of BYO.
