# implr Studio — Phase 17: Tenancy & auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two colleagues sign in and share a project list. Someone from another company signs in and sees nothing — and a deliberately broken query returns **zero rows** rather than their data.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-hosted-design.md` (*Tenancy*, *Authorization*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 16 — tenancy needs Postgres, and Postgres arrives with the containers. Phase
16 also put `tenant_id` on every owned table, which is what makes the policies below cheap.

**This is the phase the graph refuses to reorder.** `17 before 19`: do not put an unauthenticated
agent runner on the public internet. Of every edge in the dependency graph, that is the one.

---

## Demo

Sign in as two users from the **same** Entra tenant. Both see the same project list; either can
save a pipeline; each action is attributed to whoever did it.

Sign in from a **different** tenant. The project list is empty. Then `GET` the first tenant's
project id directly:

**404. Not 403.** A resource you may not see does not exist.

Then insert one row by hand and watch exactly one project become restricted:

```sql
insert into project_grants (project_id, user_id, role)
values ('<project-a>', '<user-1>', 'operator');
```

Project A is now restricted to user 1. Its siblings are untouched. No migration, no flag day.

And the assertion that decides whether any of this is real:

```bash
python -m pytest packages/implr_studio/tests/test_rls.py -v
```

A deliberately tenant-unscoped `SELECT * FROM projects` returns **zero rows**.

---

## Why this phase exists

Phase 1 built the authorization seam and filled it with `LocalPolicy`, which allows everything.
Every route has been calling `authorize(...)` since then with the right verb and the right project.
That was the investment; this phase is the payoff — swapping one class.

What it must add beyond that swap is the part a route check cannot do:

| Layer | Mechanism | Catches |
|---|---|---|
| Route | `authorize(principal, verb, project=p)` | ordinary policy decisions |
| Repository | every query takes a tenant-scoped connection | a route that forgot to check |
| **Database** | **Postgres row-level security** | **a query that forgot its `WHERE`** |

The third layer is what makes multi-tenancy defensible rather than merely intended. With RLS on, a
missing `WHERE tenant_id = …` returns an **empty list** instead of another customer's data. That
converts the worst class of bug in a multi-tenant system from a breach into a support ticket.

---

## Scope boundary — not in this phase

- **No per-project role enforcement.** `project_grants` exists and stays **empty**;
  `ProjectGrantPolicy` is written and **not wired**. The rule shipping is the one asked for: any
  member of a tenant may act on any project in it.
- **No user management UI.** No invite flow, no role editor. A tenant's first signer-in becomes
  `owner`; everyone after is `member`. Changing that is a SQL statement.
- **No SSO beyond Entra.** One identity provider. The token validator is a seam, so a second is
  possible; adding one now is designing for an imagined customer.
- **No API keys or service principals.** Humans in browsers only. The one machine identity is the
  worker's run-scoped job token from Phase 16, which is deliberately not part of this system.
- **No audit log surface.** Actions are attributed in the database (`started_by`, `updated_by`,
  `answered_by`); there is no screen that reads them. Phase 18's inbox is the first one that does.
- **No tenant self-service billing, quotas or suspension.** `tenants.status` exists and is always
  `active`.

---

## Global constraints

**404, never 403, for anything outside your tenant.** "Project not found" and "forbidden" leak
different information: the second confirms the resource exists. This is a rule about the *cross-
tenant* case specifically — a 403 within your own tenant is fine and more helpful.

**The tenant check runs before every other policy decision, in one place.**
`project.tenant_id != principal.tenant_id` is the only thing standing between two customers. It
lives in `TenantWidePolicy.allows`, not in forty routes.

**The API role must not have `BYPASSRLS`, and must not own the tables.** Both, because either one
alone silently disables everything below. `BYPASSRLS` is the obvious one; **table ownership is the
one that gets missed** — Postgres exempts a table's owner from its own RLS policies unless the
table is set to `FORCE ROW LEVEL SECURITY`. Migrations run as the owner; the app connects as a
separate, non-owning, non-bypassing role. Asserted by test.

**Every policy has a `WITH CHECK`, not only a `USING`.** `USING` governs which rows you can *see*
and therefore update or delete. It says nothing about what you may **write**. Without `WITH CHECK`,
a tenant can `INSERT` a row carrying somebody else's `tenant_id` — a write-side leak that reads
perfectly on the read side.

**`SET LOCAL`, never `SET`.** The tenant pin must be transaction-scoped. A pooled connection that
keeps a session-level setting hands the next request the previous request's tenant, and that
request will look completely normal in the logs.

**Auto-provision on first sign-in, with an upsert.** Two colleagues signing in simultaneously is
the normal case on day one, not an edge case. `SELECT`-then-`INSERT` races and produces either a
duplicate tenant or a 500 on somebody's very first impression.

**Token validation is strict about `alg` and `aud`.** An allowlist of signing algorithms (never
`none`, never a symmetric algorithm), and the audience must be *our* client id. Both are
textbook JWT failures and both are one line.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/authz.py` | **Modified** — `TenantWidePolicy`, `ProjectGrantPolicy` (unwired). |
| `packages/implr_studio/auth/entra.py` | Token validation: JWKS, `alg`, `aud`, `iss`, `exp`, `tid`, `oid`. |
| `packages/implr_studio/auth/dev.py` | `AUTH_MODE=dev`: trusts a header. Compose only. |
| `packages/implr_studio/auth/middleware.py` | Bearer → `Principal`, or 401. |
| `packages/implr_studio/tenancy.py` | Provisioning, `tenant_scoped_connection`. |
| `packages/implr_studio/schema_rls.sql` | Policies, roles, grants. |
| `packages/implr_studio/api.py` | **Modified** — `/api/me`, `/api/projects`. |
| `web/src/app/ProjectSwitcher.tsx` | The switcher. Hidden at one project. |
| `web/src/app/SignIn.tsx` | The redirect, and the signed-out state. |

---

### Task 1: Token validation

**Files:**
- Create: `packages/implr_studio/auth/entra.py`, `auth/dev.py`
- Test: `packages/implr_studio/tests/test_entra.py`

**Interfaces:**
- `entra.Validator(tenant_policy, client_id, jwks_url)`
- `validate(token) -> Claims` — raises `AuthError` on anything wrong.
- `Claims` — frozen: `tid`, `oid`, `email`, `name`, `exp`.
- `entra.ALLOWED_ALGS = frozenset({"RS256"})`
- `entra.CLOCK_SKEW_SECONDS = 60`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio.auth import entra


def test_a_valid_token_yields_claims(signed):
    claims = validator.validate(signed(tid=TID, oid=OID, aud=CLIENT_ID))

    assert claims.tid == TID
    assert claims.oid == OID


# --- the textbook failures, each one line to prevent ----------------------

def test_alg_none_is_refused(unsigned):
    """The oldest JWT bug there is."""
    with pytest.raises(entra.AuthError, match="alg"):
        validator.validate(unsigned(tid=TID, oid=OID))


def test_a_symmetric_alg_is_refused(hs256_signed):
    """Algorithm confusion: sign with HS256 using the PUBLIC key as the HMAC
    secret, and a naive verifier accepts it."""
    with pytest.raises(entra.AuthError, match="alg"):
        validator.validate(hs256_signed(tid=TID, oid=OID))


def test_the_wrong_audience_is_refused(signed):
    """A token minted for Microsoft Graph is a perfectly valid Entra token.
    It is not a token for us."""
    with pytest.raises(entra.AuthError, match="aud"):
        validator.validate(signed(aud="https://graph.microsoft.com"))


def test_an_expired_token_is_refused(signed):
    with pytest.raises(entra.AuthError, match="exp"):
        validator.validate(signed(exp=past()))


def test_a_not_yet_valid_token_is_refused(signed):
    with pytest.raises(entra.AuthError, match="nbf"):
        validator.validate(signed(nbf=future()))


def test_a_small_clock_skew_is_tolerated(signed):
    """Otherwise a 200ms clock difference logs people out at random, and the
    bug report is 'it works on my machine'."""
    assert validator.validate(signed(exp=seconds_ago(30))) is not None


def test_a_token_signed_by_an_unknown_key_is_refused(foreign_signed):
    with pytest.raises(entra.AuthError, match="signature"):
        validator.validate(foreign_signed())


def test_the_issuer_must_match_the_tid_claim(signed):
    """The cross-tenant one. In a multi-tenant app the issuer embeds the
    tenant id; an issuer for tenant A carrying tid B is not a token either
    tenant issued."""
    with pytest.raises(entra.AuthError, match="iss"):
        validator.validate(signed(tid=TID_A, iss=issuer_for(TID_B)))


def test_a_token_with_no_tid_is_refused(signed):
    """A personal Microsoft account has no tenant. Without tid there is
    nothing to isolate by, and defaulting to *any* tenant is the whole bug."""
    with pytest.raises(entra.AuthError, match="tid"):
        validator.validate(signed(tid=None))


def test_a_token_with_no_oid_is_refused(signed):
    """oid is the stable user id. `email` is mutable and reassignable, so
    keying users on it hands a departed employee's projects to their
    successor."""
    with pytest.raises(entra.AuthError, match="oid"):
        validator.validate(signed(oid=None))


# --- the JWKS cache -------------------------------------------------------

def test_jwks_is_cached(http_spy, signed):
    for _ in range(5):
        validator.validate(signed())

    assert http_spy.calls == 1


def test_an_unknown_kid_refreshes_the_cache_once(http_spy, signed):
    """Entra rotates keys. Without a refresh every user is locked out until a
    redeploy."""
    validator.validate(signed(kid="new-key"))

    assert http_spy.calls == 2


def test_repeated_unknown_kids_do_not_refresh_repeatedly(http_spy, signed):
    """Otherwise a garbage token is an unauthenticated request amplifier
    against Microsoft's endpoint, and our own rate limit."""
    for _ in range(50):
        with pytest.raises(entra.AuthError):
            validator.validate(signed(kid="garbage"))

    assert http_spy.calls <= 2


def test_a_jwks_fetch_failure_is_a_503_not_a_401(http_spy, signed):
    """'Your credentials are invalid' when the truth is 'we cannot reach the
    identity provider' sends the user to reset a password that is fine."""
    http_spy.fail()

    with pytest.raises(entra.ProviderUnavailable):
        validator.validate(signed(kid="uncached"))


# --- the dev backdoor -----------------------------------------------------

def test_dev_auth_is_unavailable_unless_mode_is_dev():
    """It trusts a header. It must be impossible to reach in any real
    configuration, not merely discouraged."""
    with pytest.raises(config.ConfigError):
        build_validator(settings(auth_mode="dev", launcher="containerapps-job"))
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(auth): strict Entra token validation"
```

---

### Task 2: Provisioning, and the principal

**Files:**
- Create: `packages/implr_studio/tenancy.py`, `auth/middleware.py`
- Test: `packages/implr_studio/tests/test_provisioning.py`

**Interfaces:**
- `tenancy.resolve_principal(conn, claims) -> Principal` — upserts tenant, user, membership.
- `middleware`: `Authorization: Bearer …` → `request.state.principal`, or **401**.

- [ ] **Step 1: Write the failing test**

```python
def test_first_sign_in_creates_the_tenant_and_the_user(conn):
    p = tenancy.resolve_principal(conn, claims(tid=TID, oid=OID))

    assert tenant_by_entra_tid(conn, TID) is not None
    assert p.tenant_role == "owner"


def test_the_second_user_of_a_tenant_is_a_member(conn):
    tenancy.resolve_principal(conn, claims(tid=TID, oid=OID_1))

    p = tenancy.resolve_principal(conn, claims(tid=TID, oid=OID_2))

    assert p.tenant_role == "member"
    assert count_tenants(conn) == 1


def test_simultaneous_first_sign_ins_produce_one_tenant(conn_factory):
    """Two colleagues signing in at the same time is day one, not an edge
    case. SELECT-then-INSERT races into a duplicate tenant or a 500 on
    somebody's first impression."""
    results = run_concurrently(
        [lambda: tenancy.resolve_principal(conn_factory(), claims(tid=TID, oid=o))
         for o in (OID_1, OID_2, OID_3)])

    assert count_tenants(conn) == 1
    assert len({r.tenant_id for r in results}) == 1


def test_a_returning_user_is_not_duplicated(conn):
    a = tenancy.resolve_principal(conn, claims(tid=TID, oid=OID))
    b = tenancy.resolve_principal(conn, claims(tid=TID, oid=OID))

    assert a.user_id == b.user_id
    assert count_users(conn) == 1


def test_a_changed_email_updates_the_user_and_keeps_the_id(conn):
    """People marry, companies rebrand. Keying on oid means the projects
    follow the person."""
    a = tenancy.resolve_principal(conn, claims(oid=OID, email="old@x.com"))

    b = tenancy.resolve_principal(conn, claims(oid=OID, email="new@x.com"))

    assert b.user_id == a.user_id
    assert user_email(conn, a.user_id) == "new@x.com"


def test_the_same_oid_in_two_tenants_is_two_users(conn):
    """A consultant with guest accounts in two customers' tenants. UNIQUE is
    (tenant_id, entra_oid), not entra_oid."""
    a = tenancy.resolve_principal(conn, claims(tid=TID_A, oid=OID))
    b = tenancy.resolve_principal(conn, claims(tid=TID_B, oid=OID))

    assert a.user_id != b.user_id


def test_no_token_is_401(client):
    assert client.get("/api/projects").status_code == 401


def test_an_invalid_token_is_401_and_says_nothing_more(client):
    """No 'signature mismatch', no 'expired at 14:03'. The client cannot act
    on the detail and an attacker can."""
    r = client.get("/api/projects", headers={"Authorization": "Bearer xxx"})

    assert r.status_code == 401
    assert r.json()["detail"] == "unauthenticated"


def test_health_is_reachable_without_a_token(client):
    """Container Apps probes it before any identity exists."""
    assert client.get("/api/health").status_code == 200


def test_the_principal_is_never_taken_from_the_body_or_a_query_param(api_source):
    """A tenant_id or user_id that arrives in a payload is attacker-controlled.
    It must come from the validated token, only."""
    assert "body.tenant_id" not in api_source
    assert "request.query_params.get(\"tenant_id\")" not in api_source
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(auth): provisioning on first sign-in, and the principal"
```

---

### Task 3: Row-level security

**Files:**
- Create: `packages/implr_studio/schema_rls.sql`
- Modify: `packages/implr_studio/store_pg.py`, `tenancy.py`
- Test: `packages/implr_studio/tests/test_rls.py`

**Interfaces:**
- `tenancy.tenant_scoped(conn, tenant_id)` — context manager; `BEGIN; SET LOCAL app.tenant_id = …`.
- Roles: `implr_migrator` (owns the tables), `implr_app` (**no** `BYPASSRLS`, **not** the owner).
- Every owned table: `ENABLE` + `FORCE ROW LEVEL SECURITY`, with `USING` **and** `WITH CHECK`.

- [ ] **Step 1: Write the failing test**

```python
pytestmark = pytest.mark.postgres


# --- the load-bearing one -------------------------------------------------

def test_an_unscoped_query_returns_zero_rows(app_conn, two_tenants):
    """THE test of this phase. A route that forgets its WHERE must return an
    empty list, not another customer's data. Everything else here exists to
    make sure this one cannot be quietly bypassed."""
    with tenancy.tenant_scoped(app_conn, TENANT_A):
        rows = app_conn.execute("select * from projects").fetchall()   # no WHERE

    assert rows != []                                  # tenant A's own, visible
    assert all(r["tenant_id"] == TENANT_A for r in rows)
    assert len(rows) == count_projects_of(TENANT_A)


# --- the two ways to silently disable all of the above -------------------

def test_the_app_role_does_not_bypass_rls(admin_conn):
    row = admin_conn.execute(
        "select rolbypassrls from pg_roles where rolname = 'implr_app'").fetchone()

    assert row["rolbypassrls"] is False


def test_the_app_role_does_not_own_the_tables(admin_conn):
    """The one that gets missed. Postgres exempts a table's OWNER from its own
    policies unless the table is FORCE ROW LEVEL SECURITY - so an app that
    connects as the owner has RLS enabled and inactive."""
    owners = admin_conn.execute(
        "select tableowner from pg_tables where schemaname = 'public'").fetchall()

    assert all(o["tableowner"] != "implr_app" for o in owners)


def test_every_owned_table_forces_rls(admin_conn):
    """Belt and braces: even if ownership changes, FORCE keeps the policies
    active."""
    rows = admin_conn.execute(
        "select relname, relrowsecurity, relforcerowsecurity from pg_class "
        "where relname = any(%s)", (OWNED_TABLES,)).fetchall()

    assert len(rows) == len(OWNED_TABLES)
    for r in rows:
        assert r["relrowsecurity"] is True, r["relname"]
        assert r["relforcerowsecurity"] is True, r["relname"]


def test_every_policy_has_a_with_check(admin_conn):
    """USING governs what you can SEE. It says nothing about what you may
    WRITE. Without WITH CHECK a tenant can INSERT a row carrying somebody
    else's tenant_id - a write-side leak that reads perfectly."""
    rows = admin_conn.execute(
        "select tablename, policyname, with_check from pg_policies "
        "where schemaname = 'public'").fetchall()

    assert rows != []
    for r in rows:
        assert r["with_check"] is not None, (r["tablename"], r["policyname"])


def test_inserting_another_tenants_row_is_refused(app_conn):
    with tenancy.tenant_scoped(app_conn, TENANT_A):
        with pytest.raises(InsufficientPrivilege):
            app_conn.execute(
                "insert into projects (id, tenant_id, slug, name) values (%s,%s,%s,%s)",
                (uuid4(), TENANT_B, "sneaky", "Sneaky"))


def test_updating_another_tenants_row_affects_nothing(app_conn, two_tenants):
    with tenancy.tenant_scoped(app_conn, TENANT_A):
        cur = app_conn.execute("update projects set name = 'owned' where tenant_id = %s",
                               (TENANT_B,))

    assert cur.rowcount == 0
    assert project_name(TENANT_B) != "owned"


def test_deleting_another_tenants_row_affects_nothing(app_conn, two_tenants):
    ...
    assert cur.rowcount == 0


# --- the pooling bug ------------------------------------------------------

def test_the_tenant_pin_does_not_survive_the_transaction(app_conn):
    """SET LOCAL, never SET. A pooled connection carrying a session-level pin
    hands the next request the previous request's tenant - and that request
    looks completely normal in the logs."""
    with tenancy.tenant_scoped(app_conn, TENANT_A):
        pass

    value = app_conn.execute(
        "select current_setting('app.tenant_id', true)").fetchone()[0]
    assert value in (None, "")


def test_a_query_with_no_pin_at_all_returns_zero_rows(app_conn):
    """Fail closed. A code path that forgot to open a scope must see nothing,
    not everything."""
    rows = app_conn.execute("select * from projects").fetchall()

    assert rows == []


def test_a_pin_set_to_a_nonsense_value_returns_zero_rows(app_conn):
    ...
    assert rows == []


# --- the shared builtins exception ---------------------------------------

def test_builtin_catalogue_rows_are_visible_to_every_tenant(app_conn):
    """The one deliberate exception: skills/agents/steps with tenant_id IS
    NULL are shared. The policy says so explicitly rather than by omission."""
    with tenancy.tenant_scoped(app_conn, TENANT_A):
        names = {r["name"] for r in app_conn.execute(
            "select name from skills where tenant_id is null").fetchall()}

    assert "doc-ingest" in names


def test_a_tenant_cannot_write_a_builtin(app_conn):
    """tenant_id IS NULL is readable by all, writable by none of them.
    Otherwise one tenant edits doc-ingest for everybody."""
    with tenancy.tenant_scoped(app_conn, TENANT_A):
        with pytest.raises(InsufficientPrivilege):
            app_conn.execute("update skills set body = 'x' where tenant_id is null")


def test_a_tenant_cannot_see_another_tenants_custom_skill(app_conn):
    """The same policy, the other direction. Custom prompts are the customer's
    intellectual property."""
    ...
    assert names == {"my-own"}


# --- the hot tables ------------------------------------------------------

@pytest.mark.parametrize("table", ["runs", "node_runs", "events", "questions",
                                   "pipelines", "projects", "skills", "agents",
                                   "steps", "project_grants"])
def test_isolation_holds_on_every_table(app_conn, two_tenants, table):
    """Enumerated, not sampled. The table somebody adds next is the one that
    leaks, and this is the list they have to add to."""
    with tenancy.tenant_scoped(app_conn, TENANT_A):
        rows = app_conn.execute("select tenant_id from %s" % table).fetchall()

    assert all(r["tenant_id"] in (TENANT_A, None) for r in rows)


def test_the_events_policy_is_not_a_join(admin_conn):
    """events is consulted for every log line. A policy that joins to runs to
    find the tenant would be the hottest query in the system - which is why
    Phase 16 denormalised tenant_id onto it."""
    policy = get_policy(admin_conn, "events")

    assert "join" not in policy.lower()
    assert "select" not in policy.lower()
```

- [ ] **Step 2: Implement**

```sql
-- Two roles. Getting this backwards silently disables every policy below.
CREATE ROLE implr_migrator LOGIN;          -- owns the tables, runs migrations
CREATE ROLE implr_app      LOGIN;          -- the API. NO BYPASSRLS, owns nothing

ALTER TABLE projects OWNER TO implr_migrator;
GRANT SELECT, INSERT, UPDATE, DELETE ON projects TO implr_app;

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
-- FORCE so the policy applies even to the owner. Without it, a future change
-- that connects as the owner turns isolation off with no error and no warning.
ALTER TABLE projects FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON projects
    USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Catalogue tables carry shared builtins: readable by all, writable by none.
CREATE POLICY tenant_read ON skills FOR SELECT
    USING (tenant_id IS NULL
           OR tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY tenant_write ON skills FOR ALL
    USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

`current_setting('app.tenant_id', true)` — the `true` makes a missing setting return `NULL`
rather than raising, and `NULL = anything` is `NULL`, so the row is excluded. **Failing closed by
construction** rather than by a check somebody has to remember to write.

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(db): row-level security, forced, with WITH CHECK"
```

---

### Task 4: The real policy

**Files:**
- Modify: `packages/implr_studio/authz.py`
- Test: `packages/implr_studio/tests/test_authz_policy.py`

**Interfaces:**
- `TenantWidePolicy` — replaces `LocalPolicy` in hosted mode.
- `ProjectGrantPolicy(TenantWidePolicy)` — written, tested, **not wired**.
- `authorize(...)` unchanged. That is the point.

- [ ] **Step 1: Write the failing test**

```python
def test_a_member_may_act_on_any_project_in_their_tenant():
    """The rule as asked for."""
    for perm in Permission:
        if perm is Permission.TENANT_ADMIN:
            continue
        assert policy.allows(member_of(TENANT_A), perm, project_in(TENANT_A))


def test_nobody_may_act_on_a_project_in_another_tenant():
    """The only line standing between two customers. Enumerated over every
    permission, because 'we only forgot one verb' is how this fails."""
    for perm in Permission:
        assert not policy.allows(member_of(TENANT_A), perm, project_in(TENANT_B))


def test_tenant_admin_requires_the_owner_role():
    assert not policy.allows(member_of(TENANT_A), Permission.TENANT_ADMIN, None)
    assert policy.allows(owner_of(TENANT_A), Permission.TENANT_ADMIN, None)


def test_the_tenant_check_precedes_the_permission_check():
    """A cross-tenant TENANT_ADMIN request must be refused for being
    cross-tenant, not evaluated as an admin question."""
    assert not policy.allows(owner_of(TENANT_A), Permission.TENANT_ADMIN,
                             project_in(TENANT_B))


def test_every_permission_verb_is_used_by_at_least_one_route(app):
    """Phase 1 named all eight deliberately. An unused verb means a route is
    checking the wrong thing - most likely a broader thing."""
    used = {r.permission for r in routes_of(app)}

    assert set(Permission) - {Permission.TENANT_ADMIN} <= used


def test_every_project_scoped_route_declares_a_permission(app):
    """The audit this seam exists to avoid. A route with no declaration is
    unguarded, and it looks exactly like the others in review."""
    undeclared = [r for r in routes_of(app)
                  if "{pid}" in r.path and r.permission is None]

    assert undeclared == []


# --- the future, tested and unwired --------------------------------------

def test_an_ungranted_project_is_open_to_the_tenant():
    """Fail-open, deliberately, and only INSIDE a tenant: the alternative is
    every new project being invisible until somebody grants it."""
    assert grant_policy.allows(member_of(TENANT_A), Permission.PROJECT_WRITE,
                               project_in(TENANT_A, grants=[]))


def test_one_grant_row_restricts_exactly_that_project():
    p = project_in(TENANT_A, grants=[(OTHER_USER, "operator")])

    assert not grant_policy.allows(member_of(TENANT_A), Permission.PROJECT_WRITE, p)


def test_a_grant_does_not_override_the_tenant_check():
    """The fail-open default must never reach across a tenant. The tenant check
    runs first and is not part of the same mechanism."""
    p = project_in(TENANT_B, grants=[(THIS_USER, "operator")])

    assert not grant_policy.allows(member_of(TENANT_A), Permission.PROJECT_WRITE, p)


def test_the_grant_policy_is_not_the_active_policy(app):
    """Written and tested, not wired. Shipping an untested-in-production policy
    by accident is worse than shipping the simple one on purpose."""
    assert isinstance(app.state.policy, TenantWidePolicy)
    assert not isinstance(app.state.policy, ProjectGrantPolicy)
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(authz): TenantWidePolicy, and ProjectGrantPolicy ready"
```

---

### Task 5: `/api/me`, projects, and 404-not-403

**Files:**
- Modify: `packages/implr_studio/api.py`
- Test: `packages/implr_studio/tests/test_api_tenancy.py`

**Interfaces:**
- `GET /api/me` → `{user, tenant, role, projects_count}`
- `GET /api/projects` → the tenant's projects.
- `POST /api/projects` → `PROJECT_CREATE`; slug unique **per tenant**.

- [ ] **Step 1: Write the failing test**

```python
def test_two_users_in_one_tenant_see_the_same_projects(client_a1, client_a2):
    assert ids(client_a1.get("/api/projects")) == ids(client_a2.get("/api/projects"))


def test_a_user_from_another_tenant_sees_none(client_b):
    assert client_b.get("/api/projects").json()["projects"] == []


def test_a_cross_tenant_project_id_is_404_not_403(client_b, project_a):
    """403 confirms the resource exists. A resource you may not see does not
    exist, as far as this API is concerned."""
    r = client_b.get("/api/projects/%s/pipeline" % project_a)

    assert r.status_code == 404


@pytest.mark.parametrize("method,path", CROSS_TENANT_ROUTE_MATRIX)
def test_every_project_scoped_route_is_404_cross_tenant(client_b, method, path):
    """Enumerated over the whole route table, not sampled. One route that
    returns 403 is an existence oracle for every project id."""
    assert client_b.request(method, path).status_code == 404


def test_a_run_id_from_another_tenant_is_404(client_b, run_a):
    """Nested resources are the ones that get forgotten: the project check
    passes because the pid is the caller's own, and the rid is not."""
    assert client_b.get(url_b("/runs/%s" % run_a)).status_code == 404


def test_a_websocket_cursor_cannot_read_another_tenants_events(client_b, run_a):
    """Phase 10's cursor, revisited under tenancy. A cursor is a POSITION,
    never an authorization - and events.seq is one global sequence."""
    frames = try_ws(client_b, run_id=run_a, cursor=0)

    assert frames == []


def test_two_tenants_may_use_the_same_project_slug(client_a1, client_b):
    """A global unique index leaks the existence of other tenants' projects
    through collision errors."""
    client_a1.post("/api/projects", json={"slug": "platform", "name": "Platform"})

    assert client_b.post("/api/projects",
                         json={"slug": "platform", "name": "Platform"}).status_code == 201


def test_a_duplicate_slug_within_a_tenant_is_409(client_a1):
    ...
    assert r.status_code == 409


def test_me_reports_the_tenant_and_the_role(client_a1):
    body = client_a1.get("/api/me").json()

    assert body["role"] in ("owner", "member")
    assert "tenant" in body


def test_actions_are_attributed(client_a1, store):
    run_id = start_run(client_a1)

    assert store.get_run(run_id)["started_by"] == user_id_of(client_a1)


def test_the_pid_in_the_path_is_never_trusted_without_a_lookup(api_source):
    """The path parameter is attacker-supplied. Every route resolves it to a
    row under the tenant pin before using it."""
    assert "load_project(" in api_source
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(api): me, projects, and 404 for anything outside your tenant"
```

---

### Task 6: Sign-in and the project switcher

**Files:**
- Create: `web/src/app/SignIn.tsx`, `web/src/app/ProjectSwitcher.tsx`
- Modify: `web/src/api.ts`, `web/src/app/App.tsx`
- Test: `web/src/app/ProjectSwitcher.test.tsx`, `SignIn.test.tsx`

**Interfaces:**
- The switcher is **hidden when the tenant has exactly one project**, so local mode and a
  single-project tenant look unchanged.
- A 401 mid-session shows a re-sign-in prompt, not an error toast.

- [ ] **Step 1: Write the failing test**

```tsx
it('hides the switcher when there is exactly one project');
it('shows the switcher at two or more');
it('shows the signed-in user and tenant');
it('prompts to sign in again on a 401 rather than showing an error');
it('does not lose an unsaved pipeline when the session expires');
it('shows an empty state with Create project when the tenant has none');
it('sends the token on every request including the WebSocket');
it('renders a restricted project no differently, because today none are');
```

Two of these are the ones people feel:

- **"does not lose an unsaved pipeline when the session expires"** — a token expires in an hour and
  designing a pipeline takes longer than that. Losing the canvas to a token refresh is the kind of
  bug that ends the trial.
- **"sends the token on every request including the WebSocket"** — the WebSocket is the one that
  gets forgotten, because it works locally where auth is off.

- [ ] **Step 2: Implement, run, build, commit**

```bash
git commit -m "feat(ui): sign-in and the project switcher"
```

---

### Task 7: Run the demo

- [ ] **Step 1: Two colleagues**

Sign in as two users from one Entra tenant. Same project list. Either can save. `GET /api/me`
shows the first as `owner` and the second as `member`. `runs.started_by` attributes correctly.

- [ ] **Step 2: A different company**

Sign in from another tenant. Project list **empty**. `GET` tenant A's project id → **404**. Try
the route matrix — every project-scoped route, **404**. Try the WebSocket with tenant A's run id
and cursor 0 → nothing.

- [ ] **Step 3: The backstop**

```bash
python -m pytest packages/implr_studio/tests/test_rls.py -v
```

Unscoped `SELECT` → zero rows. `implr_app` has no `BYPASSRLS`. `implr_app` owns nothing. Every
owned table `FORCE`s RLS. Every policy has a `WITH CHECK`.

Then break it on purpose, once, so you have seen it work:

```sql
ALTER ROLE implr_app BYPASSRLS;
```

Re-run. **The tests fail.** Revert it. A backstop nobody has watched catch something is a
hypothesis.

- [ ] **Step 4: Granularity, without a migration**

Insert one `project_grants` row. Nothing changes — `ProjectGrantPolicy` is not wired. That is
correct and worth seeing: the table is ready, the policy is tested, the switch is one line in
Phase 19's config if you want it.

- [ ] **Step 5: Slugs**

Create `platform` in both tenants. Both succeed. Create it twice in one → **409**.

- [ ] **Step 6: Local mode is unchanged**

```bash
implr-studio --workspace $PROBE --fake
```

No sign-in, no switcher, no tenant. `LocalPolicy`, SQLite, one project.

---

## Definition of Done

- [ ] `python -m pytest` passes; the `postgres`-marked RLS suite passes against a real Postgres.
- [ ] Token validation refuses: `alg: none`, a symmetric `alg`, the wrong `aud`, expiry, `nbf`, an
      unknown signing key, an `iss`/`tid` mismatch, a missing `tid`, a missing `oid`.
- [ ] A 60-second clock skew is tolerated.
- [ ] JWKS is cached; an unknown `kid` refreshes **once**; repeated garbage does not amplify; a
      fetch failure is a 503, not a 401.
- [ ] `AUTH_MODE=dev` is unreachable with a real launcher.
- [ ] First sign-in provisions tenant + user + membership; the first user is `owner`.
- [ ] **Concurrent first sign-ins produce one tenant.**
- [ ] A returning user is not duplicated; a changed email keeps the user id; the same `oid` in two
      tenants is two users.
- [ ] 401 says only `unauthenticated`; `/api/health` needs no token.
- [ ] The principal never comes from a body or a query parameter.
- [ ] **An unscoped `SELECT` returns zero rows.**
- [ ] `implr_app` lacks `BYPASSRLS` **and** owns no tables; every owned table `FORCE`s RLS.
- [ ] **Every policy has a `WITH CHECK`**; inserting another tenant's row is refused; updating and
      deleting affect zero rows.
- [ ] The tenant pin is `SET LOCAL` and does not survive its transaction; no pin → zero rows.
- [ ] Builtin catalogue rows are readable by every tenant and writable by none.
- [ ] The `events` policy is a comparison, not a join.
- [ ] Isolation asserted on **every** owned table by name.
- [ ] `TenantWidePolicy` refuses every verb cross-tenant; the tenant check runs first.
- [ ] Every project-scoped route declares a permission; every verb is used by some route.
- [ ] `ProjectGrantPolicy` is tested and **not wired**.
- [ ] Every project-scoped route is **404** cross-tenant, over the whole route matrix — including
      nested run ids and the WebSocket cursor.
- [ ] Slugs are unique per tenant, not globally.
- [ ] Actions are attributed to the acting user.
- [ ] The switcher hides at one project; a mid-session 401 does not lose the canvas; the token is
      sent on the WebSocket.
- [ ] **You have watched the RLS tests fail** with `BYPASSRLS` granted, then reverted it.
- [ ] Local mode is unchanged.

---

## Known limitations, kept

**Per-project roles are not enforced.** `project_grants` is empty and `ProjectGrantPolicy` is
unwired. This is the rule that was asked for, and the cost of tightening it later is one line —
which was the entire point of naming eight permission verbs in Phase 1 rather than two.

**"No grants means open" is fail-open.** Acceptable *inside* a tenant, where the alternative is
every new project being invisible until someone grants it. It must never be the mechanism for
anything crossing a tenant, which is why the tenant check is a separate, earlier gate.

**No user management surface.** The first signer-in is `owner`; the rest are `member`. Promoting
someone is a SQL statement. A tenant whose owner leaves the company needs a DBA.

**No audit surface.** Attribution is recorded and unreadable. Phase 18's inbox is the first screen
that surfaces any of it.

**RLS is not a substitute for the route checks.** It catches a missing `WHERE`; it cannot catch a
route that reads the right tenant's data and shows it to the wrong *person* within that tenant.
That distinction is what `ProjectGrantPolicy` will be for.

---

## What the next phase gets

Real identities and real isolation — which is what makes onboarding possible at all. **Phase 18**
creates tenants, projects and users from a browser, and it cannot exist before they do. It also
inherits the one screen this phase deliberately did not build: attribution is in the database, and
the inbox is where it finally becomes visible.
