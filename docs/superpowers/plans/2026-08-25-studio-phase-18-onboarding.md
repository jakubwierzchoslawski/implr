# implr Studio — Phase 18: Onboarding

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A brand-new tenant goes from first sign-in to a supervised dry run of a real pipeline in **under five minutes**, without running a shell command and without seeing a blank canvas.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-hosted-design.md` (*Onboarding: subscription to first run*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 17 (tenancy & auth) — onboarding creates tenants, users and projects, so they must exist first.

**Reference mock:** the six screens and the inbox, clickable — see the artifact linked from the design spec. The mock is the specification for layout and copy; this document is the specification for behaviour.

---

## Demo

Sign in as a brand-new Entra tenant. Connect a repository with no implr workspace. Merge the
pull request it opens. Choose *Full SDLC*. Click through six supervised dry-run steps.

Then check the two things that make it real rather than a happy path:

```bash
# Nothing was committed to the customer's repository.
git -C /tmp/probe-repo log --oneline origin/main | head -3    # unchanged since the setup PR

# And the flow is resumable: kill the browser at step 3 and come back.
curl -s -H "Authorization: Bearer $TOKEN" \
     http://127.0.0.1:8000/api/onboarding | python -m json.tool
# { "state": "awaiting_merge", "project_id": "...", "pr_number": 482, ... }
```

Under five minutes, three real decisions — which repository, which template, whether to
approve each step — and a repository that is byte-identical apart from a PR the customer
merged themselves.

---

## Scope boundary — not in this phase

- **No billing, no subscription management.** "Subscribed" is assumed; the tenant exists
  because someone signed in.
- **No custom step authoring.** Phase 8's surface stays reachable from the palette and is
  never mentioned by this flow. Learn the nine shipped steps first.
- **No GitLab, no Bitbucket, no Azure DevOps.** One provider, done properly. The
  `RepoProvider` seam is defined so a second is additive.
- **No notifications.** The inbox makes them implementable; sending them is later.
- **No invite flow.** A second user from the same directory signs in and is already a member —
  that is Phase 17's tenant-wide rule, and it is enough.

---

## Production-grade constraints

This phase touches a customer's repository and their identity provider on their first
interaction with the product. Six constraints follow, and each one has a task below.

1. **Resumable, server-side.** Onboarding state lives in Postgres, not in the browser. A
   customer who closes the tab at step 3 returns to step 3. Client-side wizard state is the
   default mistake here and it strands people.
2. **Idempotent PR creation.** Double-clicks, retries and duplicate webhooks must not open two
   pull requests. Keyed, not guarded by a boolean.
3. **Webhooks are unreliable, so poll as well.** GitHub delivery is at-least-once and
   sometimes zero-times. Merge detection needs a webhook *and* a reconciliation poll, both
   idempotent.
4. **Never persist an installation token.** They are short-lived by design; store the App
   private key in Key Vault and mint tokens per call.
5. **Verify every webhook.** HMAC-SHA256 over the raw body, constant-time compare. An
   unverified webhook endpoint is an unauthenticated write path into your tenant data.
6. **Instrument the funnel.** You cannot fix a five-minute target you cannot measure. Every
   state transition is an event with a tenant, a duration and an outcome.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/onboarding/state.py` | The persisted state machine. No I/O beyond the store. |
| `packages/implr_studio/onboarding/routes.py` | `/api/onboarding` — read state, advance it. |
| `packages/implr_studio/repo/base.py` | `RepoProvider` Protocol. No provider names. |
| `packages/implr_studio/repo/github.py` | The one implementation. |
| `packages/implr_studio/repo/fake.py` | Scripted provider for tests. Zero network. |
| `packages/implr_studio/onboarding/workspace.py` | What the setup PR contains, built from `plugin/`. |
| `packages/implr_studio/onboarding/templates.py` | The five pipeline templates. |
| `packages/implr_studio/webhooks.py` | Signature verification and dispatch. |
| `web/src/onboarding/*.tsx` | The six screens. |
| `web/src/panels/Inbox.tsx` | The daily surface. |

---

### Task 1: The persisted state machine

**Files:**
- Create: `packages/implr_studio/onboarding/state.py`
- Test: `tests/onboarding/test_state.py`

**Interfaces:**
- `OnboardingState` — `StrEnum`: `signed_in`, `repo_selected`, `awaiting_merge`, `workspace_ready`, `template_chosen`, `first_run`, `done`.
- `Onboarding` — frozen dataclass: `tenant_id`, `user_id`, `state`, `project_id | None`, `pr_number | None`, `template | None`, `run_id | None`, `started_at`, `updated_at`.
- `advance(current: Onboarding, event: Event) -> Onboarding` — pure. Raises `IllegalTransition`.
- `store.get_onboarding(tenant_id)`, `store.put_onboarding(o)`.

**Pure, and keyed on the tenant rather than the user.** Onboarding is a property of the
tenant: if two colleagues sign in on day one, the second must land in the flow the first
started, not begin a parallel one. That is the whole reason this is server-side.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio.onboarding import state as st


def _at(s: st.OnboardingState) -> st.Onboarding:
    return st.Onboarding(tenant_id="t1", user_id="u1", state=s)


def test_starts_signed_in():
    o = st.begin(tenant_id="t1", user_id="u1")

    assert o.state is st.OnboardingState.signed_in
    assert o.project_id is None


def test_selecting_a_repo_creates_the_project_reference():
    o = st.advance(_at(st.OnboardingState.signed_in),
                   st.RepoSelected(project_id="p1", needs_workspace=True))

    assert o.state is st.OnboardingState.awaiting_merge
    assert o.project_id == "p1"


def test_a_repo_that_already_has_implr_skips_the_pr():
    """Detection short-circuits the whole PR dance. Half of onboarding, gone."""
    o = st.advance(_at(st.OnboardingState.signed_in),
                   st.RepoSelected(project_id="p1", needs_workspace=False))

    assert o.state is st.OnboardingState.workspace_ready
    assert o.pr_number is None


def test_merge_advances_from_awaiting_merge():
    o = st.advance(
        st.Onboarding(tenant_id="t1", user_id="u1",
                      state=st.OnboardingState.awaiting_merge,
                      project_id="p1", pr_number=482),
        st.PrMerged(pr_number=482))

    assert o.state is st.OnboardingState.workspace_ready


def test_a_merge_for_a_different_pr_is_ignored_not_an_error():
    """Another PR merging in the same repo must not advance onboarding."""
    before = st.Onboarding(tenant_id="t1", user_id="u1",
                           state=st.OnboardingState.awaiting_merge,
                           project_id="p1", pr_number=482)

    after = st.advance(before, st.PrMerged(pr_number=999))

    assert after == before


def test_a_duplicate_merge_event_is_a_no_op():
    """GitHub delivers at-least-once. The second delivery must change nothing."""
    o = st.Onboarding(tenant_id="t1", user_id="u1",
                      state=st.OnboardingState.workspace_ready,
                      project_id="p1", pr_number=482)

    assert st.advance(o, st.PrMerged(pr_number=482)) == o


def test_choosing_a_template_requires_a_ready_workspace():
    with pytest.raises(st.IllegalTransition, match="awaiting_merge"):
        st.advance(_at(st.OnboardingState.awaiting_merge), st.TemplateChosen(template="full"))


def test_the_flow_reaches_done():
    o = st.begin(tenant_id="t1", user_id="u1")
    o = st.advance(o, st.RepoSelected(project_id="p1", needs_workspace=False))
    o = st.advance(o, st.TemplateChosen(template="full"))
    o = st.advance(o, st.RunStarted(run_id="r1"))
    o = st.advance(o, st.RunFinished())

    assert o.state is st.OnboardingState.done


def test_going_back_is_allowed_within_the_prefix():
    """The rail lets you revisit a completed step; the state machine must permit it."""
    o = _at(st.OnboardingState.template_chosen)

    back = st.advance(o, st.Rewound(to=st.OnboardingState.repo_selected))

    assert back.state is st.OnboardingState.repo_selected


def test_rewinding_forward_is_refused():
    with pytest.raises(st.IllegalTransition):
        st.advance(_at(st.OnboardingState.signed_in),
                   st.Rewound(to=st.OnboardingState.first_run))
```

- [ ] **Step 2: Run to verify it fails, then implement, then run again**

The implementation is a dict of `(state, event type) -> handler`. Two rules the tests pin
down and that are easy to get wrong:

- **An event for the wrong subject is ignored, not an error.** A merge for PR #999 while we
  are waiting on #482 returns the state unchanged. Raising would turn an unrelated repository
  event into a 500 in a webhook handler, and GitHub would retry it forever.
- **A duplicate event is a no-op.** Same reasoning. Idempotency is a property of the state
  machine, not something the caller remembers to check.

- [ ] **Step 3: Demo**

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/onboarding
```

Returns `{"state": "signed_in", ...}` for a fresh tenant. **Close the browser, reopen it, and
the flow resumes where it was** — that is the whole point of this task and the only thing
worth checking by hand.

- [ ] **Step 4: Commit**

```bash
git add packages/implr_studio/onboarding tests/onboarding
git commit -m "feat(onboarding): persisted, resumable state machine"
```

---

### Task 2: The repository provider seam

**Files:**
- Create: `packages/implr_studio/repo/base.py`, `repo/fake.py`, `repo/github.py`
- Test: `tests/repo/test_fake.py`, `tests/repo/test_github_unit.py`

**Interfaces:**

```python
class RepoProvider(Protocol):
    async def list_repos(self, installation) -> list[RepoInfo]: ...
    async def read_file(self, repo, ref, path) -> bytes | None: ...
    async def open_pr(self, repo, base, head, title, body,
                      files: dict[str, bytes], idempotency_key: str) -> PrInfo: ...
    async def get_pr(self, repo, number) -> PrInfo: ...
```

No provider name appears in `base.py` — the same discipline `StepExecutor` applies to model
providers, for the same reason. `fake.py` is scripted and does no network I/O, so every test
below and in Tasks 3–5 is free and offline.

**Three production details, all tested:**

- **Installation tokens are minted per call and never stored.** The App private key lives in
  Key Vault; `github.py` exchanges it for a short-lived installation token, uses it, and drops
  it. Persisting one is a credential with a ten-minute fuse in your database.
- **Repo listing is paginated.** An org with 300 repositories must not silently show 30.
- **Rate limits are respected.** On `403` with `x-ratelimit-remaining: 0`, back off until
  `x-ratelimit-reset` rather than hammering.

- [ ] **Step 1: Tests worth writing out**

```python
async def test_list_repos_follows_pagination():
    """An org with 300 repos must not silently show the first page."""

async def test_installation_token_is_not_persisted():
    """Assert the store was never asked to write it - a short-lived credential in a
    database is a liability with no upside."""

async def test_rate_limit_backs_off_until_reset():
    """403 + x-ratelimit-remaining: 0 -> wait, do not retry immediately."""

async def test_read_file_returns_none_for_a_missing_path():
    """Workspace detection depends on distinguishing 'absent' from 'error'."""

async def test_a_5xx_is_retried_and_a_4xx_is_not():
    """Retrying a 422 just burns rate limit and confuses the customer."""
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(onboarding): repository provider seam with a scripted fake"
```

---

### Task 3: Workspace detection and idempotent PR creation

**Files:**
- Create: `packages/implr_studio/onboarding/workspace.py`
- Test: `tests/onboarding/test_workspace.py`

**Interfaces:**
- `detect(provider, repo, ref) -> WorkspaceState` — `absent | current | outdated`.
- `build_setup_files() -> dict[str, bytes]` — read from `plugin/`, the same payload `install.sh` writes.
- `open_setup_pr(provider, project, ...) -> PrInfo` — **idempotent**.

**Detection reads one file**, `docs/implr/schemas/status-vocabulary.json`, and compares a
version. Not `docs/implr/` as a directory: a repo can have an empty `docs/implr/` from a
half-finished manual install, and treating that as "current" leaves the customer with a
broken workspace and no PR.

**Idempotency is keyed, not flagged.** The key is
`sha256(project_id, base_ref, workspace_version)`. Before opening a PR, look for an open one
with that key in its body as an HTML comment; if found, return it.

> A boolean `pr_opened` column is the obvious approach and it is wrong: it is written *after*
> the PR is created, so a crash between the two leaves the flag false and the next attempt
> opens a second PR. A key derived from the request survives that, because the check happens
> against GitHub's state rather than ours.

- [ ] **Step 1: Write the failing test**

```python
async def test_detects_an_absent_workspace(fake_provider):
    fake_provider.files = {}

    assert await workspace.detect(fake_provider, "acme/x", "main") is workspace.State.absent


async def test_an_empty_docs_implr_is_still_absent(fake_provider):
    """A half-finished manual install must not read as 'current'."""
    fake_provider.files = {"docs/implr/.gitkeep": b""}

    assert await workspace.detect(fake_provider, "acme/x", "main") is workspace.State.absent


async def test_detects_a_current_workspace(fake_provider):
    fake_provider.files = {
        "docs/implr/schemas/status-vocabulary.json": _real_vocabulary_bytes()}

    assert await workspace.detect(fake_provider, "acme/x", "main") is workspace.State.current


async def test_setup_files_are_exactly_what_the_installer_writes():
    """The PR must not drift from install.sh - a customer onboarded through the UI
    and one onboarded by hand must end up with the same workspace."""
    files = workspace.build_setup_files()

    assert "docs/implr/schemas/status-vocabulary.json" in files
    assert "docs/implr/config/implr.config.yaml" in files
    assert len([k for k in files if k.startswith(".claude/skills/")]) == 8
    assert len([k for k in files if k.startswith(".claude/agents/")]) == 11


async def test_opening_the_pr_twice_returns_the_same_pr(fake_provider):
    """Double-click, retry, duplicate webhook - one PR."""
    first = await workspace.open_setup_pr(fake_provider, PROJECT)
    second = await workspace.open_setup_pr(fake_provider, PROJECT)

    assert first.number == second.number
    assert fake_provider.open_pr_calls == 1


async def test_a_crash_after_creation_still_does_not_duplicate(fake_provider):
    """The failure mode a boolean flag cannot survive: the PR exists, our write did not."""
    await workspace.open_setup_pr(fake_provider, PROJECT)
    # Simulate losing our own record entirely.
    store.clear_onboarding(PROJECT.tenant_id)

    again = await workspace.open_setup_pr(fake_provider, PROJECT)

    assert fake_provider.open_pr_calls == 1
    assert again.number is not None


async def test_the_pr_never_targets_the_default_branch_directly(fake_provider):
    pr = await workspace.open_setup_pr(fake_provider, PROJECT)

    assert pr.head != PROJECT.default_branch
    assert fake_provider.pushes_to_default == 0
```

That last assertion is a policy test, not a plumbing test. Writing to someone's default
branch as an onboarding side effect is the kind of thing that gets a tool banned, and it is
worth a test that fails loudly if someone "optimises" the flow later.

- [ ] **Step 2: Implement, run**

- [ ] **Step 3: Demo**

Point a local run at a scratch GitHub repo with no implr workspace. Click *Open pull request*.
A PR appears. **Click it again** — no second PR. Check the repo's branch list: one
`implr/setup-<short-key>` branch, and `main` untouched.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(onboarding): workspace detection and keyed-idempotent setup PR"
```

---

### Task 4: Merge detection — webhook plus reconciliation

**Files:**
- Create: `packages/implr_studio/webhooks.py`
- Modify: `packages/implr_studio/onboarding/routes.py`
- Test: `tests/test_webhooks.py`

**Interfaces:**
- `POST /api/webhooks/github` — verify, dispatch, `204`.
- `reconcile_pending_merges()` — a periodic job polling every `awaiting_merge` onboarding.

**Both, not either.** A webhook alone strands any customer whose delivery was dropped, and
they will not know why. A poll alone makes the UI feel dead for up to the poll interval. So:
webhook for latency, poll every 60s for correctness, and both funnel into the same idempotent
`advance()`.

**Signature verification is the security boundary of this task.** The endpoint is
unauthenticated by necessity — GitHub has no bearer token for us — so HMAC is the only thing
between it and an attacker advancing another tenant's onboarding.

- [ ] **Step 1: Write the failing test**

```python
def test_a_valid_signature_is_accepted(client):
    body = json.dumps({"action": "closed", "pull_request": {"number": 482, "merged": True}}).encode()
    sig = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()

    r = client.post("/api/webhooks/github", content=body,
                    headers={"x-hub-signature-256": sig, "x-github-event": "pull_request"})

    assert r.status_code == 204


def test_a_missing_signature_is_rejected(client):
    r = client.post("/api/webhooks/github", json={"action": "closed"})

    assert r.status_code == 401


def test_a_wrong_signature_is_rejected(client):
    body = b'{"action":"closed"}'

    r = client.post("/api/webhooks/github", content=body,
                    headers={"x-hub-signature-256": "sha256=" + "0" * 64,
                             "x-github-event": "pull_request"})

    assert r.status_code == 401


def test_the_signature_is_computed_over_the_RAW_body(client):
    """Re-serialising the JSON changes the bytes and breaks the HMAC. The handler
    must hash what arrived, not what it parsed."""


def test_comparison_is_constant_time():
    """Assert hmac.compare_digest is used - a == comparison on a MAC is a timing oracle."""
    source = inspect.getsource(webhooks)
    assert "compare_digest" in source
    assert re.search(r"if\s+sig\s*==", source) is None


def test_a_duplicate_delivery_advances_onboarding_once(client, store):
    """At-least-once delivery. The second one must be a no-op, not a double advance."""
    for _ in range(2):
        client.post("/api/webhooks/github", content=MERGE_BODY, headers=SIGNED)

    assert store.get_onboarding("t1").state is OnboardingState.workspace_ready
    assert store.transition_count("t1") == 1


def test_an_unrelated_event_type_is_ignored(client):
    r = client.post("/api/webhooks/github", content=PUSH_BODY,
                    headers={**SIGNED_PUSH, "x-github-event": "push"})

    assert r.status_code == 204        # accepted and dropped, not 400


def test_reconcile_advances_an_onboarding_whose_webhook_was_lost(store, fake_provider):
    """The failure this job exists for: GitHub never delivered, the customer is stuck."""
    store.put_onboarding(awaiting_merge_at(pr=482))
    fake_provider.prs[482] = PrInfo(number=482, merged=True)

    reconcile_pending_merges()

    assert store.get_onboarding("t1").state is OnboardingState.workspace_ready


def test_reconcile_is_idempotent(store, fake_provider):
    ...


def test_reconcile_ignores_a_closed_but_unmerged_pr(store, fake_provider):
    """A customer who closes the PR without merging has said no. Do not advance."""
    fake_provider.prs[482] = PrInfo(number=482, merged=False, closed=True)

    reconcile_pending_merges()

    assert store.get_onboarding("t1").state is OnboardingState.awaiting_merge
```

- [ ] **Step 2: Implement, run**

- [ ] **Step 3: Demo**

With the local stack running and a scratch repo: merge the setup PR on GitHub. **The UI
advances without a refresh.** Then test the fallback properly — stop the webhook tunnel,
merge a second setup PR on another project, and confirm the UI still advances within 60
seconds.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(onboarding): verified webhooks plus a reconciliation poll"
```

---

### Task 5: Templates, materialised atomically

**Files:**
- Create: `packages/implr_studio/onboarding/templates.py`
- Test: `tests/onboarding/test_templates.py`

**Interfaces:**
- `TEMPLATES: dict[str, Template]` — the five from the design: `full`, `reqs`, `build`, `cr`, `blank`.
- `materialise(template_id, project, conn) -> Pipeline` — **one transaction**.

**Every template sets `approval: before` on every node.** That is what makes the first run a
step-by-step wizard, and it is a property of the template rather than a global setting so a
customer can drop it per node afterwards.

**Every template sets the model mix to Sonnet.** implr's own default puts `plan-runner` and
`task-executor` on Opus. Onboarding overrides both, because the first bill should not be the
first surprise.

- [ ] **Step 1: Write the failing test**

```python
def test_every_template_validates_against_the_real_registry(reg):
    """A template that cannot be saved is worse than no template."""
    for name, tpl in templates.TEMPLATES.items():
        findings = validate_pipeline(tpl.pipeline, reg)
        assert findings == [], "%s: %s" % (name, findings)


def test_every_node_of_every_template_is_supervised():
    for name, tpl in templates.TEMPLATES.items():
        for node in tpl.pipeline.nodes:
            assert node.approval == "before", "%s/%s" % (name, node.id)


def test_every_template_pins_sonnet():
    """implr's default is two Opus agents in dev-executor. Onboarding does not inherit it."""
    for name, tpl in templates.TEMPLATES.items():
        for node in tpl.pipeline.nodes:
            for tier in node.models.values():
                assert tier == "sonnet", "%s/%s" % (name, node.id)


def test_the_blank_template_is_empty_and_valid():
    tpl = templates.TEMPLATES["blank"]

    assert tpl.pipeline.nodes == ()
    assert validate_pipeline(tpl.pipeline, REG) == []


def test_full_sdlc_is_the_six_step_chain():
    ids = [n.step for n in templates.TEMPLATES["full"].pipeline.nodes]

    assert ids == ["doc-ingest", "arch-gen", "ba-requirements-gen",
                   "dev-planner", "dev-executor", "dev-code-review"]


def test_materialise_is_atomic(store, failing_conn):
    """A pipeline row with no step rows is a project that cannot run and cannot be
    fixed from the UI. Half a template is worse than none."""
    with pytest.raises(DatabaseError):
        templates.materialise("full", PROJECT, failing_conn)

    assert store.get_pipeline(PROJECT.id) is None


def test_materialise_twice_does_not_duplicate(store, conn):
    templates.materialise("full", PROJECT, conn)
    templates.materialise("full", PROJECT, conn)

    assert len(store.list_pipelines(PROJECT.id)) == 1


def test_a_materialised_template_writes_pipeline_yaml_to_the_repo(fake_provider):
    """The pipeline is control-plane state AND a file in their repo - git is the history."""
    templates.materialise("full", PROJECT, conn)

    assert "docs/implr/config/pipeline.yaml" in fake_provider.last_commit_files
```

- [ ] **Step 2: Implement, run, demo, commit**

Demo: pick each of the five templates in turn on a scratch project and confirm the canvas
renders a valid graph with an approval badge on every node. Then `cat` the
`pipeline.yaml` the service committed and confirm it matches what the canvas shows.

---

### Task 6: The first run — supervised and dry

**Files:**
- Modify: `packages/implr_studio/onboarding/routes.py`
- Test: `tests/onboarding/test_first_run.py`

**Interfaces:**
- `first_run_overrides(pipeline) -> Pipeline` — adds `--dry-run` to every node whose step declares it.

**Only to steps that declare `--dry-run` in `args_allowed`.** Adding a flag a skill does not
accept would fail the run with an argument error, which is a spectacularly bad first
impression. Steps without it (`dev-code-review`) run normally — they write only review
artefacts, which is the point.

- [ ] **Step 1: Write the failing test**

```python
def test_dry_run_is_added_to_every_step_that_supports_it(reg):
    out = first_run_overrides(TEMPLATES["full"].pipeline, reg)

    for node in out.nodes:
        step = reg.get(node.step)
        if "--dry-run" in step.flags:
            assert "--dry-run" in node.args, node.id


def test_dry_run_is_not_added_to_a_step_that_would_reject_it(reg):
    """A flag the skill does not accept fails the run with an argument error."""
    out = first_run_overrides(TEMPLATES["full"].pipeline, reg)
    review = next(n for n in out.nodes if n.step == "dev-code-review")

    assert "--dry-run" not in review.args


def test_the_override_does_not_mutate_the_saved_pipeline(store):
    """The dry run is a property of THIS run, not of the pipeline. A customer who
    turns off approval later must not silently inherit --dry-run forever."""
    saved = store.get_pipeline(PROJECT.id)

    first_run_overrides(saved, REG)

    assert store.get_pipeline(PROJECT.id) == saved


def test_only_the_first_run_of_a_project_is_dry(store):
    ...


def test_the_run_reports_that_it_was_dry(store):
    """The console must say so, or the customer thinks it did the work."""
    run = store.get_run(RUN_ID)

    assert run["dry_run"] is True
```

- [ ] **Step 2: Implement, run**

- [ ] **Step 3: Demo — the phase gate**

Click through all six steps. At each one, read the log, read *would have written*, click
**Accept**. Then, once:

- click **Request changes** with a note, and confirm the step re-runs and the second attempt's
  `StepRequest` carried the note (Phase 13's machinery, exercised here for real);
- confirm `git log origin/main` on the customer repo is **unchanged** apart from the setup PR.

- [ ] **Step 4: Commit**

---

### Task 7: The inbox

**Files:**
- Create: `web/src/panels/Inbox.tsx`
- Modify: `packages/implr_studio/api.py` — `GET /api/inbox`
- Test: `tests/test_api_inbox.py`, `web/src/panels/Inbox.test.tsx`

**Interfaces:**
- `GET /api/inbox` → `{needs: [...], running: [...], recent: [...]}` across **every project
  the principal may read**, newest first.

This is the phase's least glamorous and most-used surface. With approval on by default a
paused run is the *normal* state, so a canvas-first console is wrong for daily use.

**It is also the easiest place to leak across tenants**, because it is the one query that
deliberately spans projects. Two tests below exist for that reason.

- [ ] **Step 1: Write the failing test**

```python
def test_inbox_spans_every_project_in_the_tenant(client):
    body = client.get("/api/inbox").json()

    assert {r["project"] for r in body["needs"]} == {"acme-platform", "billing-svc"}


def test_inbox_never_shows_another_tenants_work(client_other_tenant):
    """The one query that deliberately spans projects is the one most likely to
    span tenants by accident."""
    assert client_other_tenant.get("/api/inbox").json() == {
        "needs": [], "running": [], "recent": []}


def test_inbox_respects_project_visibility(client, store):
    """Empty today - project_grants is unused - but the query must go through the
    policy, so enabling grants later needs no change here."""
    ...


def test_needs_you_includes_every_human_waiting_state(client):
    states = {r["state"] for r in client.get("/api/inbox").json()["needs"]}

    assert states <= {"awaiting-review", "awaiting-input", "awaiting-approval", "failed"}


def test_blocked_is_not_in_needs_you(client):
    """A blocked node advances on its own. Putting it in an action list trains people
    to ignore the list."""
    states = {r["state"] for r in client.get("/api/inbox").json()["needs"]}

    assert "blocked" not in states


def test_rows_are_newest_first(client):
    ages = [r["updated_at"] for r in client.get("/api/inbox").json()["needs"]]

    assert ages == sorted(ages, reverse=True)
```

`test_blocked_is_not_in_needs_you` is the one worth arguing about. A blocked node *is* waiting
— but not on a human. Listing it teaches the customer that the list contains things they
cannot act on, and a list like that stops being read.

- [ ] **Step 2: Implement, run**

- [ ] **Step 3: Demo**

Two projects, four things waiting. The inbox shows all four with the right state colours.
Click a row: it opens **the review card / the question / the failure**, not the canvas.
Act on it and the row leaves the list.

- [ ] **Step 4: Commit**

---

### Task 8: Instrument the funnel

**Files:**
- Modify: `packages/implr_studio/onboarding/state.py`
- Test: `tests/onboarding/test_telemetry.py`

Every transition emits a structured event: `tenant_id`, `from`, `to`, `duration_ms`,
`outcome`. Application Insights in Azure; stdout locally.

**You cannot hold a five-minute target you cannot measure**, and the interesting number is
not the mean — it is *where people stop*. The prediction worth testing is that step 3 is the
drop-off, because it is the only one that leaves the product.

- [ ] **Step 1: Write the failing test**

```python
def test_every_transition_emits_an_event(events):
    run_the_whole_flow()

    assert [e["to"] for e in events] == [
        "signed_in", "awaiting_merge", "workspace_ready",
        "template_chosen", "first_run", "done"]


def test_events_carry_the_duration_in_that_state(events):
    assert all(e["duration_ms"] >= 0 for e in events[1:])


def test_an_abandoned_onboarding_is_reported(events, clock):
    """A tenant sitting in awaiting_merge for a week is a lost customer, and the
    only place that is visible is here."""
    store.put_onboarding(awaiting_merge_at(days_ago=7))

    report_stalled_onboardings()

    assert any(e["event"] == "onboarding.stalled" for e in events)


def test_no_event_carries_a_repository_name_or_an_email(events):
    """Telemetry is operational, not a customer data export."""
    blob = json.dumps(events)

    assert "acme/" not in blob
    assert "@" not in blob
```

That last test matters more than it looks. Funnel telemetry is the easiest place to
accidentally start exporting customer identifiers to a third-party analytics sink.

- [ ] **Step 2: Implement, run, commit**

---

## Definition of Done

- [ ] `python -m pytest` passes; every onboarding test runs against `repo/fake.py` with **zero
      network calls**.
- [ ] `npm test` and `npm run build` pass.
- [ ] Onboarding state is server-side: closing the browser mid-flow and reopening resumes at
      the same step, proven by a test and by hand.
- [ ] Opening the setup PR twice — including after losing our own record of it — produces
      **one** PR.
- [ ] The setup PR never targets the default branch, asserted by a test.
- [ ] `build_setup_files()` matches what `install.sh` writes: 8 skills, 11 agents, the
      schemas, the config, the templates.
- [ ] Webhook signatures are verified over the **raw** body with `compare_digest`; a missing
      or wrong signature is `401`.
- [ ] A duplicate webhook delivery advances onboarding **once**.
- [ ] A lost webhook is recovered by the reconciliation poll within 60s.
- [ ] A PR closed **without** merging does not advance onboarding.
- [ ] All five templates validate against the real registry, set `approval: before` on every
      node, and pin every agent to Sonnet.
- [ ] `materialise` is atomic — a failure leaves no pipeline row.
- [ ] `--dry-run` is added only to steps whose `args_allowed` contains it, and the override
      does not mutate the saved pipeline.
- [ ] The inbox spans every project in the tenant and **no** project outside it.
- [ ] `blocked` does not appear in *Needs you*.
- [ ] No installation token is ever written to the database.
- [ ] No telemetry event contains a repository name or an email address.
- [ ] **The demo:** a brand-new tenant reaches a supervised dry run in under five minutes, and
      the customer's repository is unchanged apart from a PR they merged themselves.

---

## What the next phase gets

A product a customer can start using without being taught. **Phase 19** deploys it: bicep,
the Azure runbook, Entra sign-in on a real domain, and a run executing in a Container Apps
Job with no database credentials.
