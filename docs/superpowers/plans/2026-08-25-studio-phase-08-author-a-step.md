# implr Studio — Phase 8: Author a step

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Press **New step**, describe a step that implr does not ship, and drag it onto the canvas.

**Roadmap:** `2026-08-25-studio-phases.md` · **Design:** `../specs/2026-08-25-implr-studio-design.md` (*Registry concept*) · **Hosted:** `../specs/2026-08-25-implr-studio-hosted-design.md` (*The Phase 8 problem, restated*) · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 7 — the authoring surface writes arg specs, agent definitions and I/O
paths. It needs every field the configurator already renders, because authoring a shape the UI
cannot display is building blind.

**Not on the run path.** Nothing in 9–15 depends on this phase. If the nine shipped steps are
enough for now, skip it and come back.

---

## Demo

Press **New step** at the top of the palette.

Choose **agent-backed**. Name it `Lint & Format`, phase `verify`, write an instruction, add one
agent on `haiku` with `[Read, Edit, Bash]`. Save.

`docs/implr/config/steps.yaml` appears — a file the installer will never touch. The step shows
up in the palette under *verify*, marked as **yours**. Drag it onto the canvas, connect it after
Code Review, Save the pipeline. It validates like any other node.

Then the three refusals, each of which is the point of a test:

```bash
# grant it WebFetch  -> refused, naming the permitted set
# name it doc-ingest -> refused, naming the collision
# name it ../evil    -> refused at write time
```

Finally author a **skill-backed** step pointing at an installed skill the plugin registry does
not declare. It appears **available**. Point another at a made-up skill name: it appears
**dashed**, exactly as an uninstalled shipped step does.

---

## Why this phase exists

Before it, the palette is exactly the nine steps implr ships, and adding a tenth means
hand-writing a `SKILL.md` in the plugin source and reinstalling. That is fine for the plugin
author and impossible for a customer.

Worse, there is no *safe* place to put one. `install.sh` copies `schemas/*.json` under a comment
reading **"Always overwrite: schemas and templates (plugin-owned)"**, so a project that
hand-edits its installed `step-registry.json` silently loses the change on the next install. The
loss is silent, which is the part that matters: you would discover it the next time a pipeline
failed to load.

So the answer is a second file with a different owner.

| File | Owner | Installer | Contains |
|---|---|---|---|
| `plugin/steps/step-registry.json` | implr | overwritten every install | the nine shipped steps |
| `docs/implr/config/steps.yaml` | the project | **never touched** | steps this project added |

`steps.yaml` is committed to the project's repo, reviewed like any other config, and merged over
the plugin registry by `id`.

---

## Scope boundary — not in this phase

- **No editing a shipped step.** Overriding `doc-ingest` would be occasionally useful and
  permanently confusing: two people reading the same pipeline would disagree about what a node
  does. A collision on `id` is an **error**, not a merge.
- **An agent-backed step takes no arguments.** See *Global constraints* — this one is a security
  decision, not a scheduling one.
- **No skill *body* authoring.** You may point a step at an installed skill; you may not write
  the `SKILL.md` from the UI. That arrives with the hosted catalogue (Phase 16), where a skill is
  a row and the write path can be audited.
- **No step deletion while in use.** Deleting a step that a saved pipeline references would break
  that pipeline on next load. Deletion is allowed only when no pipeline references it, and the
  refusal names the pipelines.
- **Not offered during onboarding.** Phase 18 deliberately never mentions this surface. It stays
  reachable from the palette.

---

## Global constraints

**An agent-backed step takes no arguments.** Interpolating an operator-typed value into a prompt
is prompt injection by construction — the operator becomes an author of the agent's
instructions, and every downstream tool grant is exercised on their behalf. Appending the value
as a literal flag is worse than useless: it offers a control the agent may silently ignore, so
the UI would show a knob that does nothing. If you need a variant, author two steps. This is
asserted by test, not just documented.

**`tools` is a subset of one declared permitted set.** Authoring must not be a route around the
permission posture. That set is declared **here**, as `registry.PERMITTED_TOOLS`, and Phase 15's
adapter imports it rather than redeclaring — so a tool this validator accepts is exactly a tool
the adapter will grant, and the two cannot drift.

The direction matters and it is easy to get backwards. The permitted set is a **policy**
statement, not an adapter implementation detail, and Phase 8 sits on the 4→8 branch while the
adapter arrives at the end of the 9→15 chain. Declaring it in `_sdk.py` would make this phase
depend on a module that does not exist yet.

**Every authored name is a path component somewhere.** A skill name becomes a directory under
`.claude/skills/`; a step id becomes a YAML key and a URL segment. Validate the shape at **write
time**, once, rather than sanitising at each use.

**Authored steps are visually distinct on the canvas and in the palette.** Not decoration: the
reason a node behaves unlike its neighbours is that somebody in your tenant wrote it, and that
should be legible without opening the modal.

---

## The honest caveat, which the UI states too

implr's value is that `task-executor`'s prose has been refined to enforce TDD and SOLID, and that
`code-review-worker` has a checklist somebody argued about. A hand-typed step has **no TDD
enforcement, no review gate, and no iteration history**.

That makes this surface excellent for `lint-and-format`, `generate-diagram`, `tag-release` — and
wrong for *"write the implementation"*. The authoring modal says so, in the modal, where the
decision is being made. Anything that turns out to be load-bearing should graduate into a real
`SKILL.md` in the plugin.

---

## File Structure

| File | Responsibility |
|---|---|
| `packages/implr_studio/registry.py` | **Modified** — second source, merge, discovery, authored-step validation. |
| `packages/implr_studio/steps_config.py` | Read/write `steps.yaml`. Separate from `registry` because one is a loader and the other is a writer. |
| `packages/implr_studio/api.py` | **Modified** — `/api/projects/{pid}/skills`, `/api/projects/{pid}/steps`. |
| `packages/implr_studio/checks.py` | **Modified** — `check_steps_config` for `implr-validate`. |
| `web/src/modal/StepAuthor.tsx` | The authoring surface. |
| `web/src/panels/Palette.tsx` | **Modified** — **New step**, the project-owned marker. |
| `web/src/nodes/StepNode.tsx` | **Modified** — the agent-backed marker. |
| `web/src/api.ts` | **Modified** — `getSkills`, `getSteps`, `putSteps`. |

---

### Task 1: Discover what is actually installed

**Files:**
- Modify: `packages/implr_studio/registry.py`
- Test: `packages/implr_studio/tests/test_discovery.py`

**Interfaces:**
- `registry.SkillInfo` — frozen dataclass: `name`, `description`, `path`.
- `registry.discover_skills(workspace) -> dict[str, SkillInfo]` — reads
  `<workspace>/.claude/skills/*/SKILL.md` frontmatter.

Phase 1 already resolves *availability* against that directory. This returns the **descriptions**
too, so the picker can show what a skill does rather than only that it exists.

- [ ] **Step 1: Write the failing test**

```python
from implr_studio import registry


def _skill(root, name, body="---\nname: %s\ndescription: does a thing\n---\n\n# %s\n"):
    d = root / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(body % (name, name), encoding="utf-8")
    return d


def test_discovers_an_installed_skill(tmp_path):
    _skill(tmp_path, "lint-and-format")

    found = registry.discover_skills(tmp_path)

    assert set(found) == {"lint-and-format"}
    assert found["lint-and-format"].description == "does a thing"


def test_an_empty_workspace_discovers_nothing(tmp_path):
    assert registry.discover_skills(tmp_path) == {}


def test_a_directory_without_skill_md_is_ignored(tmp_path):
    (tmp_path / ".claude" / "skills" / "notaskill").mkdir(parents=True)

    assert registry.discover_skills(tmp_path) == {}


def test_the_directory_name_wins_over_a_disagreeing_frontmatter_name(tmp_path):
    """The Skill tool resolves by directory. If frontmatter disagrees, the
    directory is the truth - otherwise the picker offers a name that cannot
    be invoked."""
    _skill(tmp_path, "real-name", "---\nname: wishful\ndescription: d\n---\n")

    found = registry.discover_skills(tmp_path)

    assert set(found) == {"real-name"}


def test_unreadable_frontmatter_yields_a_named_skill_with_no_description(tmp_path):
    """A skill with a broken header still exists and is still invocable.
    Hiding it would be a worse lie than showing it without a description."""
    _skill(tmp_path, "broken", "no frontmatter at all\n")

    found = registry.discover_skills(tmp_path)

    assert set(found) == {"broken"}
    assert found["broken"].description == ""


def test_discovery_does_not_follow_a_symlink_out_of_the_workspace(tmp_path):
    """Otherwise `.claude/skills/x -> /etc` makes the picker a directory browser."""
    outside = tmp_path.parent / "outside-skills"
    (outside / "sneaky").mkdir(parents=True, exist_ok=True)
    (outside / "sneaky" / "SKILL.md").write_text("---\nname: sneaky\n---\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    try:
        (tmp_path / ".claude" / "skills" / "link").symlink_to(outside / "sneaky")
    except (OSError, NotImplementedError):
        return                      # unprivileged Windows: nothing to assert

    assert registry.discover_skills(tmp_path) == {}
```

The last test is skipped rather than xfailed on Windows without developer mode, because a symlink
cannot be created there at all — and the check it guards still runs in CI and in the container.

- [ ] **Step 2: Implement, run, commit**

Reuse the frontmatter parser `implr_validate` already has rather than writing a second one.

```bash
git commit -m "feat(registry): discover installed skills with descriptions"
```

---

### Task 2: `steps.yaml`, merged by id

**Files:**
- Create: `packages/implr_studio/steps_config.py`
- Modify: `packages/implr_studio/registry.py`
- Test: `packages/implr_studio/tests/test_steps_config.py`

**Interfaces:**
- `steps_config.load(workspace) -> list[dict]` — `[]` when the file is absent.
- `steps_config.save(workspace, steps)` — atomic write (temp + replace).
- `steps_config.PATH = "docs/implr/config/steps.yaml"`
- `registry.load_registry(workspace)` merges: plugin steps, then authored steps.
- `Step` gains `kind`, `source`, `instruction`, and per-agent `prompt` / `tools` / `max_turns`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import registry, steps_config


def test_an_absent_file_yields_no_authored_steps(tmp_path):
    """Every project that predates this phase must load identically."""
    assert steps_config.load(tmp_path) == []


def test_an_authored_step_joins_the_registry(tmp_path, plugin_registry):
    steps_config.save(tmp_path, [{
        "id": "lint-and-format", "kind": "agent", "label": "Lint & Format",
        "phase": "verify", "instruction": "Run the formatter, then the linter.",
        "agents": [{"name": "formatter", "prompt": "You format code.", "model": "haiku"}],
    }])

    reg = registry.load_registry(tmp_path)

    assert reg.step("lint-and-format").source == "project"
    assert reg.step("doc-ingest").source == "plugin"     # untouched


def test_a_collision_with_a_shipped_step_is_an_error(tmp_path, plugin_registry):
    """Not last-write-wins. Two people reading one pipeline would disagree
    about what the node does, and neither would be wrong."""
    steps_config.save(tmp_path, [{
        "id": "doc-ingest", "kind": "agent", "label": "My doc-ingest",
        "phase": "discover", "instruction": "...",
        "agents": [{"name": "a", "prompt": "p"}]}])

    with pytest.raises(registry.RegistryError, match="doc-ingest"):
        registry.load_registry(tmp_path)


def test_two_authored_steps_may_not_collide_with_each_other(tmp_path, plugin_registry):
    steps_config.save(tmp_path, [
        {"id": "dup", "kind": "agent", "label": "A", "phase": "verify",
         "instruction": "i", "agents": [{"name": "a", "prompt": "p"}]},
        {"id": "dup", "kind": "agent", "label": "B", "phase": "verify",
         "instruction": "i", "agents": [{"name": "a", "prompt": "p"}]},
    ])

    with pytest.raises(registry.RegistryError, match="dup"):
        registry.load_registry(tmp_path)


def test_save_is_atomic(tmp_path, monkeypatch):
    """A crash mid-write must not leave a half-file: steps.yaml is read on
    every registry load, so a truncated one breaks the whole console."""
    steps_config.save(tmp_path, [{"id": "ok", "kind": "agent", "label": "Ok",
                                  "phase": "verify", "instruction": "i",
                                  "agents": [{"name": "a", "prompt": "p"}]}])
    good = (tmp_path / steps_config.PATH).read_text(encoding="utf-8")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(steps_config.os, "replace", boom)
    with pytest.raises(OSError):
        steps_config.save(tmp_path, [{"id": "other", "kind": "agent", "label": "X",
                                      "phase": "verify", "instruction": "i",
                                      "agents": [{"name": "a", "prompt": "p"}]}])

    assert (tmp_path / steps_config.PATH).read_text(encoding="utf-8") == good


def test_the_file_is_written_under_docs_implr_config(tmp_path):
    """Not under .claude/, and not next to the plugin registry: the path is
    the whole point - install.sh must never overwrite it."""
    steps_config.save(tmp_path, [])

    assert (tmp_path / "docs" / "implr" / "config" / "steps.yaml").exists()
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(registry): project-owned steps.yaml merged by id"
```

---

### Task 3: Validating an authored step

**Files:**
- Modify: `packages/implr_studio/registry.py`
- Test: `packages/implr_studio/tests/test_authored_validation.py`

**Interfaces:**
- `registry.validate_authored(steps, permitted_tools, phases) -> list[Finding]` — reuses Phase 3's
  `Finding`, so the API returns findings in one shape everywhere.
- Codes: `bad-kind`, `missing-skill`, `missing-instruction`, `missing-agent-prompt`,
  `illegal-tier`, `bad-max-turns`, `forbidden-tool`, `bad-identifier`, `agent-step-takes-args`,
  `duplicate-step-id`, `unknown-phase`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from implr_studio import registry

PERMITTED = registry.PERMITTED_TOOLS


def _step(**kw):
    base = {"id": "s", "kind": "agent", "label": "S", "phase": "verify",
            "instruction": "do it", "agents": [{"name": "a", "prompt": "p"}]}
    base.update(kw)
    return base


def codes(step):
    return [f.code for f in registry.validate_authored([step], PERMITTED, registry.PHASES)]


# --- kind -----------------------------------------------------------------

def test_kind_must_be_one_of_two_values():
    assert codes(_step(kind="wizard")) == ["bad-kind"]


def test_a_skill_step_requires_a_skill():
    assert codes(_step(kind="skill", skill=None)) == ["missing-skill"]


def test_an_agent_step_requires_a_non_empty_instruction():
    assert codes(_step(instruction="   ")) == ["missing-instruction"]


def test_an_agent_needs_a_prompt():
    assert codes(_step(agents=[{"name": "a", "prompt": ""}])) == ["missing-agent-prompt"]


# --- the security-shaped rules --------------------------------------------

def test_an_agent_step_may_not_declare_args():
    """Interpolating an operator value into a prompt is prompt injection by
    construction. Author two steps instead."""
    assert codes(_step(args_allowed={"--depth": {"type": "int"}})) == ["agent-step-takes-args"]


@pytest.mark.parametrize("tool", ["WebFetch", "WebSearch", "Artifact", "NotebookEdit"])
def test_a_tool_outside_the_permitted_set_is_refused(tool):
    findings = registry.validate_authored(
        [_step(agents=[{"name": "a", "prompt": "p", "tools": ["Read", tool]}])],
        PERMITTED, registry.PHASES)

    assert [f.code for f in findings] == ["forbidden-tool"]
    assert tool in findings[0].message
    assert "Read" in findings[0].message        # names the permitted set


def test_the_permitted_set_is_a_frozen_declaration():
    """Declared here, imported by the Phase 15 adapter. Frozen so a call site
    cannot mutate the policy for the rest of the process."""
    assert isinstance(registry.PERMITTED_TOOLS, frozenset)
    assert "Read" in registry.PERMITTED_TOOLS
    assert "WebFetch" not in registry.PERMITTED_TOOLS


@pytest.mark.parametrize("bad", [
    "../evil", "a/b", "a\\b", ".hidden", "-leading", "", "  ", "a" * 65,
    "CON", "sk ill", "sk;ill", "skíll",
])
def test_an_identifier_that_is_not_a_safe_path_component_is_refused(bad):
    """Every id becomes a YAML key, a URL segment, and - for skills - a
    directory name. Validate the shape once, at write time."""
    assert "bad-identifier" in codes(_step(id=bad))


def test_a_legal_identifier_passes():
    assert codes(_step(id="lint-and-format")) == []


# --- the ordinary ones ----------------------------------------------------

def test_tier_must_be_known():
    assert codes(_step(agents=[{"name": "a", "prompt": "p", "model": "gpt"}])) == ["illegal-tier"]


@pytest.mark.parametrize("bad", [0, -1, "many", 1.5])
def test_max_turns_must_be_a_positive_int(bad):
    assert codes(_step(agents=[{"name": "a", "prompt": "p", "max_turns": bad}])) == [
        "bad-max-turns"]


def test_phase_must_be_one_the_palette_can_show():
    """An unknown phase means the step exists and is invisible."""
    assert codes(_step(phase="someday")) == ["unknown-phase"]


def test_a_valid_step_produces_no_findings():
    assert codes(_step()) == []


def test_a_skill_step_pointing_at_an_uninstalled_skill_is_valid_but_unavailable():
    """Same rule as a shipped step: not installed is a *display* state, not
    an error. A pipeline may be authored before the skill is installed."""
    findings = registry.validate_authored(
        [_step(kind="skill", skill="not-installed-yet", instruction=None)],
        PERMITTED, registry.PHASES)

    assert findings == []
```

The reserved-name case (`CON`) is in the list because `steps.yaml` is authored on one platform and
materialised on another. A step id that cannot be a directory on Windows is a step that works
until somebody runs the worker on Windows.

- [ ] **Step 2: Implement**

`PERMITTED_TOOLS` is a module-level `frozenset` in `registry.py`. Phase 15 will `from
implr_studio.registry import PERMITTED_TOOLS` and carries the test asserting it did not
redeclare — a test that belongs there, because that is where the drift would happen.

- [ ] **Step 3: Run, commit**

```bash
git commit -m "feat(registry): validate authored steps"
```

---

### Task 4: The routes

**Files:**
- Modify: `packages/implr_studio/api.py`
- Test: `packages/implr_studio/tests/test_api_steps.py`

**Interfaces:**
- `GET /api/projects/{pid}/skills` → `{skills: [{name, description, available}]}` — `SKILL_AUTHOR` not
  required to *read*; `PROJECT_READ` is enough.
- `GET /api/projects/{pid}/steps` → the authored steps only.
- `PUT /api/projects/{pid}/steps` → validated; **422 with findings**; `Permission.STEP_AUTHOR`.
- `DELETE /api/projects/{pid}/steps/{sid}` → **409** naming the pipelines that reference it.

- [ ] **Step 1: Write the failing test**

```python
def test_get_skills_lists_installed_skills(client, workspace):
    body = client.get(url("/skills")).json()

    assert {s["name"] for s in body["skills"]} >= {"doc-ingest", "arch-gen"}


def test_put_steps_writes_the_file(client, workspace):
    r = client.put(url("/steps"), json={"steps": [VALID_STEP]})

    assert r.status_code == 200
    assert (workspace / "docs/implr/config/steps.yaml").exists()


def test_an_invalid_step_is_422_with_findings_and_writes_nothing(client, workspace):
    r = client.put(url("/steps"), json={"steps": [dict(VALID_STEP, phase="someday")]})

    assert r.status_code == 422
    assert [f["code"] for f in r.json()["detail"]["findings"]] == ["unknown-phase"]
    assert not (workspace / "docs/implr/config/steps.yaml").exists()


def test_the_new_step_appears_in_the_registry_response(client):
    client.put(url("/steps"), json={"steps": [VALID_STEP]})

    ids = [s["id"] for s in client.get(url("/registry")).json()["steps"]]

    assert VALID_STEP["id"] in ids


def test_deleting_a_step_a_pipeline_uses_is_409(client):
    client.put(url("/steps"), json={"steps": [VALID_STEP]})
    client.put(url("/pipeline"), json=pipeline_using(VALID_STEP["id"]))

    r = client.delete(url("/steps/%s" % VALID_STEP["id"]))

    assert r.status_code == 409
    assert "pipeline" in r.json()["detail"].lower()


def test_deleting_an_unused_step_succeeds(client):
    client.put(url("/steps"), json={"steps": [VALID_STEP]})

    assert client.delete(url("/steps/%s" % VALID_STEP["id"])).status_code == 200


def test_put_steps_requires_step_author(app):
    assert permission_for(app, "PUT", "/api/projects/{pid}/steps") is Permission.STEP_AUTHOR


def test_get_skills_only_requires_project_read(app):
    """Reading the catalogue is not authoring. A designer who may not write
    steps still needs to see which skills exist."""
    assert permission_for(app, "GET", "/api/projects/{pid}/skills") is Permission.PROJECT_READ
```

- [ ] **Step 2: Implement, run, commit**

```bash
git commit -m "feat(api): skills and steps routes"
```

---

### Task 5: `implr-validate` learns about `steps.yaml`

**Files:**
- Modify: `packages/implr_studio/checks.py` (or the `implr_validate` check registry, per Phase −1)
- Test: `packages/implr_studio/tests/test_check_steps.py`

**Interfaces:**
- `check_steps_config(root) -> list[Finding]` — same validation, run from CI.

The UI cannot be the only gate. `steps.yaml` is committed, which means it can be edited in an
editor, merged badly, or arrive in a pull request — and the first time anyone notices would
otherwise be a console that fails to load its registry.

- [ ] **Step 1: Write the failing test**

```python
def test_a_repo_with_no_steps_yaml_passes(tmp_path):
    assert check_steps_config(tmp_path) == []


def test_a_bad_steps_yaml_fails_the_check(tmp_path):
    write_steps(tmp_path, [{"id": "x", "kind": "wizard"}])

    assert [f.code for f in check_steps_config(tmp_path)] == ["bad-kind"]


def test_unparseable_yaml_is_reported_not_raised(tmp_path):
    (tmp_path / "docs/implr/config").mkdir(parents=True)
    (tmp_path / "docs/implr/config/steps.yaml").write_text("steps: [{", encoding="utf-8")

    findings = check_steps_config(tmp_path)

    assert [f.code for f in findings] == ["unparseable-steps-yaml"]
```

- [ ] **Step 2: Implement, run, commit**

---

### Task 6: The authoring surface

**Files:**
- Create: `web/src/modal/StepAuthor.tsx`
- Modify: `web/src/panels/Palette.tsx`, `web/src/nodes/StepNode.tsx`, `web/src/api.ts`, `web/src/app.css`
- Test: `web/src/modal/StepAuthor.test.tsx`

**Interfaces:**
- `StepAuthor({ mode, initial, skills, permittedTools, onSave, onClose })` — reuses Phase 4's
  `Modal.tsx` shell.
- Kind chooser first, because it changes which fields exist.
- Palette: a **New step** button; authored steps carry a *project-owned* marker.
- `StepNode`: an agent-backed node carries a distinct marker on the canvas.

- [ ] **Step 1: Write the failing test**

```tsx
it('asks for the kind before anything else');
it('shows the skill picker for a skill-backed step and no instruction field');
it('shows the instruction field for an agent-backed step and no skill picker');
it('shows no arguments editor for an agent-backed step');
it('offers only permitted tools, from the server payload');
it('disables Save until id, label, phase and the kind-specific fields are filled');
it('renders server findings against the field they name, not as a toast');
it('shows the honest caveat about TDD and review, in the modal');
it('marks an installed skill as available and a made-up one as dashed');
it('keeps the typed draft when a save is rejected');
```

Three of these are load-bearing rather than cosmetic:

- **No arguments editor for an agent-backed step.** If the field is rendered and then refused by
  the server, the UI has taught the operator that the rule is arbitrary. Do not render it.
- **Only permitted tools, from the server payload.** Hardcoding the list in TSX is how it drifts
  from `_sdk.PERMITTED_TOOLS`. The server sends it; the UI renders what it is sent.
- **Keeps the draft when a save is rejected.** Authoring a step is minutes of typing. Losing it to
  a 422 is the difference between a surface people use and one they use once.

- [ ] **Step 2: Implement, run, build, commit**

```bash
git commit -m "feat(ui): author a step"
```

---

### Task 7: Run the demo

- [ ] **Step 1: An agent-backed step**

`Lint & Format`, phase `verify`, one `haiku` agent with `[Read, Edit, Bash]`. Save.
`docs/implr/config/steps.yaml` appears. It is in the palette under *verify*, marked as yours.

- [ ] **Step 2: On the canvas**

Drag it in, connect it after Code Review, Save. It validates like any other node and carries the
agent-backed marker.

- [ ] **Step 3: The three refusals**

Grant it `WebFetch` → refused, naming the permitted set. Rename it `doc-ingest` → refused, naming
the collision. Rename it `../evil` → refused.

- [ ] **Step 4: A skill-backed step**

Point one at an installed skill the plugin registry does not declare → **available**. Point
another at a made-up name → **dashed**, like an uninstalled shipped step.

- [ ] **Step 5: The installer does not eat it**

Re-run the installer over the workspace. `steps.yaml` is **unchanged** and the step is still in
the palette. This is the whole reason the file is where it is, so verify it rather than assuming.

- [ ] **Step 6: CI sees it too**

Hand-edit `steps.yaml` to something invalid and run `implr-validate --repo`. It fails, naming the
step.

---

## Definition of Done

- [ ] `python -m pytest` and `npm test` pass; `npm run build` passes.
- [ ] A project with **no** `steps.yaml` loads byte-identically to Phase 7.
- [ ] An authored step appears in `/api/.../registry` with `source: "project"`.
- [ ] A collision with a shipped id is a **RegistryError**, not a silent override.
- [ ] Two authored steps may not collide with each other.
- [ ] `registry.PERMITTED_TOOLS` is a frozen declaration — the single source Phase 15 imports.
- [ ] An agent-backed step declaring args is refused, and the UI never renders the field.
- [ ] Path-shaped, reserved and over-long identifiers are refused at write time.
- [ ] `steps.yaml` is written atomically; a failed write leaves the previous file intact.
- [ ] Deleting a referenced step is a 409 that names the pipelines.
- [ ] `PUT /steps` requires `STEP_AUTHOR`; `GET /skills` requires only `PROJECT_READ`.
- [ ] `implr-validate --repo` validates `steps.yaml` and reports unparseable YAML as a finding.
- [ ] **The installer leaves `steps.yaml` alone**, verified by re-running it.
- [ ] The modal states the TDD/review caveat.
- [ ] A rejected save keeps the draft.

---

## Known limitations, kept

**No versioning.** Editing an authored step changes it for every pipeline that references it,
including runs in flight. Git is the history — `steps.yaml` is committed, so a diff exists — but
there is no in-product "this run used version 2" record until the hosted catalogue arrives in
Phase 16, where a step is a row with a `content_hash`.

**No sharing between projects.** A step authored in one project's `steps.yaml` is invisible to
the next. That is correct for local mode and wrong for a tenant with nine repositories; Phase 16
makes the catalogue tenant-scoped, and that is where sharing belongs.

---

## What the next phase gets

An open catalogue. **Phase 9** starts execution and does not care where a step came from: the
`StepExecutor` contract takes a skill name and an argv, and an authored step produces both. The
one thing 9 inherits from here is that `registry.step(id)` may return something nobody at
Anthropic wrote — which is exactly why the permitted-tool set is shared rather than duplicated.
