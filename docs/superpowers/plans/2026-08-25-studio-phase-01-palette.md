# implr Studio — Phase 1: See the steps

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The left rail becomes a real palette — nine implr steps read off a shipped registry file, grouped by phase, with the two unimplemented ones dashed and explained, and a search box that filters them.

**Roadmap:** `2026-08-25-studio-phases.md` · **Spec:** `../specs/2026-08-25-implr-studio-design.md` · **Runtime:** `../../RUNTIME.md`

**Depends on:** Phase 0.

---

## Demo

Both processes up, browser open. The left rail lists:

```
DISCOVERY      Document Ingestion
DESIGN         Architecture Brief          ?
REQUIREMENTS   Requirements Generation
               Change Request              ?
PLANNING       Specification / Planning    ?
BUILD          Implementation
VERIFY         Code Review
               Testing                  soon   (dashed)
               Security Checks          soon   (dashed)
```

Hover a dashed one: *"…(not implemented yet - the skill does not exist)"*. Type `knowledge`
in the search box: only **Document Ingestion** survives. Type `zzz`: *"No step matches
'zzz'."*

Nothing is draggable yet — that's Phase 2. This phase proves the catalogue is real data from
real files, not a mockup.

---

## Scope boundary — not in this phase

No canvas, no dragging, no pipeline, no configurator, no runs. The palette items are inert
apart from search and tooltips. `args_allowed`, `agents`, `consumes`, `produces` and
`produces_artefact` are **loaded and served** but nothing renders them yet — phases 4–7 do.

**Why the registry ships whole rather than growing.** `step-registry.json` is a data file.
Shipping it complete in one go and letting the UI render an increasing share of it is far
cleaner than editing the same JSON in five phases. So the loader parses every field now, and
`GET /api/registry` serves every field now. What grows is the UI.

---

## Tech Stack

Python 3.11+, FastAPI. React + TypeScript, Vitest. No new dependencies.

## Global Constraints

- Nothing in the frontend hardcodes a step, phase, flag, agent or artefact type. It all
  arrives from `GET /api/registry`.
- `scripts/implr_validate` stays **standard library only** — the registry check
  re-implements the loader's rules rather than importing `implr_studio`, because
  `implr-validate` must keep working in a project that never installed the studio backend.
- A step whose `skills/<skill>/SKILL.md` is absent is **not an error**. It renders dashed and
  undraggable. That is how a planned step appears in the process diagram before it exists.
- Every colour is a token from Phase 0. `tokens.test.ts` enforces it.

---

## File Structure

| File | Responsibility |
|---|---|
| `scaffold/schemas/step-registry.json` | **NEW** — the catalogue. Installed to target projects by the existing `install.sh` rule that copies `schemas/*.json`. |
| `studio/backend/implr_studio/registry.py` | Loads and validates the registry; determines availability. |
| `studio/backend/implr_studio/serialize.py` | Pure dict conversions for API responses. No FastAPI import. |
| `studio/backend/implr_studio/context.py` | `AppContext` — the wired dependency bundle. Workspace + registry only, for now. |
| `studio/backend/implr_studio/api.py` | **Modified** — takes a context; adds `GET /api/registry`. |
| `studio/backend/implr_studio/server.py` | **Modified** — builds the context. |
| `scripts/implr_validate/checks.py` | **Modified** — gains `check_step_registry`. Stdlib only. |
| `scripts/implr_validate/cli.py` | **Modified** — calls it; exit code becomes level-aware. |
| `studio/frontend/src/types.ts` | Shared types mirroring the backend DTOs. |
| `studio/frontend/src/api.ts` | Typed `fetch` wrappers. No React. |
| `studio/frontend/src/panels/Palette.tsx` | Searchable phase-grouped step list. |

---

### Task 1: The registry file

**Files:**
- Create: `scaffold/schemas/step-registry.json`

Two conventions in this file, both load-bearing:

- `PATH` is the value pattern for anything filesystem-shaped:
  `^[A-Za-z0-9._/-]{1,200}$`. It admits no whitespace, no quotes, no `$`, no backticks.
- Every `agents[].name` must match a file in `.claude/agents/` and a key in
  `implr.config.yaml`'s `agents:` block. Task 2 enforces the first.

- [ ] **Step 1: Write the file**

```json
{
  "_comment": "Catalogue of pipeline steps for implr Studio. Adding a step here makes it appear in the palette and its agents in the step configurator; no code change is required. A step whose skills/<skill>/SKILL.md does not exist is rendered unavailable, not rejected.",
  "steps": [
    {
      "id": "doc-ingest",
      "kind": "skill",
      "label": "Document Ingestion",
      "phase": "discovery",
      "skill": "doc-ingest",
      "args_allowed": [
        { "flag": "--registry-only", "takes_value": false, "note": "fast scan, no digesting" },
        { "flag": "--file", "takes_value": true, "value_pattern": "^[A-Za-z0-9._/-]{1,200}$", "note": "one document only" },
        { "flag": "--rebuild", "takes_value": false, "note": "ignore the incremental cache" },
        { "flag": "--dry-run", "takes_value": false, "note": "report, write nothing" }
      ],
      "args_default": [],
      "interactive": false,
      "agents": [
        { "name": "doc-ingest-digester", "fan_out": "1 per changed doc" },
        { "name": "doc-ingest-synthesizer", "fan_out": "1 per domain" }
      ],
      "consumes": [
        { "path": "docs/kb/**", "note": "18 supported formats" },
        { "path": "docs/implr/kb-index/registry.md", "note": "incremental state" }
      ],
      "produces": [
        { "path": "docs/implr/kb-index/digests/per-doc/*.md", "note": "" },
        { "path": "docs/implr/kb-index/domains/*.md", "note": "" },
        { "path": "docs/implr/kb-index/master-synthesis.md", "note": "" }
      ],
      "produces_artefact": null,
      "description": "Reads everything under docs/kb/, digests each document, then rebuilds the per-domain and master syntheses that every later step depends on."
    },
    {
      "id": "arch-gen",
      "kind": "skill",
      "label": "Architecture Brief",
      "phase": "design",
      "skill": "arch-gen",
      "args_allowed": [
        { "flag": "--update", "takes_value": false, "note": "amend instead of replace" },
        { "flag": "--dry-run", "takes_value": false, "note": "report, write nothing" }
      ],
      "args_default": [],
      "interactive": true,
      "agents": [{ "name": "arch-drafter", "fan_out": "1" }],
      "consumes": [
        { "path": "docs/implr/kb-index/master-synthesis.md", "note": "required" },
        { "path": "docs/implr/config/DEV-STANDARDS.md", "note": "optional" }
      ],
      "produces": [{ "path": "docs/ARCHITECTURE.md", "note": "" }],
      "produces_artefact": null,
      "description": "Infers architectural decisions from the master synthesis and confirms each one with the operator before writing ARCHITECTURE.md."
    },
    {
      "id": "ba-requirements-gen",
      "kind": "skill",
      "label": "Requirements Generation",
      "phase": "requirements",
      "skill": "ba-requirements-gen",
      "args_allowed": [
        { "flag": "--domain", "takes_value": true, "value_pattern": "^[a-z0-9-]{1,60}$", "note": "restrict to one domain" },
        { "flag": "--reprocess", "takes_value": false, "note": "regenerate existing" },
        { "flag": "--dry-run", "takes_value": false, "note": "report, write nothing" }
      ],
      "args_default": [],
      "interactive": false,
      "agents": [{ "name": "requirements-domain-worker", "fan_out": "1 per domain" }],
      "consumes": [
        { "path": "docs/implr/kb-index/domains/*.md", "note": "per domain" },
        { "path": "docs/implr/kb-index/master-synthesis.md", "note": "NFR signals" }
      ],
      "produces": [],
      "produces_artefact": "requirement",
      "description": "Turns the digested knowledge base into numbered functional and non-functional requirements, one worker per domain."
    },
    {
      "id": "ba-cr",
      "kind": "skill",
      "label": "Change Request",
      "phase": "requirements",
      "skill": "ba-cr",
      "args_allowed": [
        { "flag": "--file", "takes_value": true, "value_pattern": "^[A-Za-z0-9._/-]{1,200}$", "note": "the CR document" },
        { "flag": "--ingest-file", "takes_value": true, "value_pattern": "^[A-Za-z0-9._/-]{1,200}$", "note": "ingest then analyse" },
        { "flag": "--impact-only", "takes_value": false, "note": "analyse, do not apply" },
        { "flag": "--dry-run", "takes_value": false, "note": "report, write nothing" }
      ],
      "args_default": [],
      "interactive": true,
      "agents": [
        { "name": "cr-impact-analyzer", "fan_out": "1" },
        { "name": "cr-applier", "fan_out": "1 per target" }
      ],
      "consumes": [
        { "path": "docs/kb/change-requests/*.md", "note": "" },
        { "path": "docs/implr/requirements/**", "note": "impact set" }
      ],
      "produces": [],
      "produces_artefact": "cr",
      "description": "Analyses what a Change Request would touch, shows the blast radius, then applies it across requirements and plans."
    },
    {
      "id": "dev-planner",
      "kind": "skill",
      "label": "Specification / Planning",
      "phase": "planning",
      "skill": "dev-planner",
      "args_allowed": [
        { "flag": "--all", "takes_value": false, "note": "every approved requirement" },
        { "flag": "--replan", "takes_value": false, "note": "rewrite needs-rework plans" },
        { "flag": "--brainstorm", "takes_value": false, "note": "ask before planning" },
        { "flag": "--coherence-check", "takes_value": false, "note": "cross-plan consistency" },
        { "flag": "--dry-run", "takes_value": false, "note": "report, write nothing" }
      ],
      "args_default": ["--all"],
      "interactive": true,
      "agents": [{ "name": "plan-worker", "fan_out": "1 per requirement" }],
      "consumes": [
        { "path": "docs/implr/requirements/**", "note": "status: approved" },
        { "path": "docs/ARCHITECTURE.md", "note": "" },
        { "path": "docs/implr/config/DEV-STANDARDS.md", "note": "" }
      ],
      "produces": [],
      "produces_artefact": "plan",
      "description": "Writes an implementation plan per approved requirement, with per-task TDD flags and injected NFR constraints."
    },
    {
      "id": "dev-executor",
      "kind": "skill",
      "label": "Implementation",
      "phase": "build",
      "skill": "dev-executor",
      "args_allowed": [
        { "flag": "--all", "takes_value": false, "note": "every ready plan" },
        { "flag": "--task", "takes_value": true, "value_pattern": "^[A-Za-z0-9._#/-]{1,80}$", "note": "one task id only" },
        { "flag": "--review", "takes_value": false, "note": "review after each plan" },
        { "flag": "--commit", "takes_value": false, "note": "commit per plan" },
        { "flag": "--verbose", "takes_value": false, "note": "stream task detail" },
        { "flag": "--dry-run", "takes_value": false, "note": "report, write nothing" }
      ],
      "args_default": ["--all"],
      "interactive": false,
      "agents": [
        { "name": "arch-excerpter", "fan_out": "1 per plan" },
        { "name": "plan-runner", "fan_out": "1 per plan, cap 5" },
        { "name": "task-executor", "fan_out": "1 per task" }
      ],
      "consumes": [
        { "path": "docs/implr/plans/**", "note": "status: ready" },
        { "path": "docs/ARCHITECTURE.md", "note": "excerpted per plan" },
        { "path": "docs/implr/config/DEV-STANDARDS.md", "note": "" }
      ],
      "produces": [
        { "path": "src/**", "note": "implementation" },
        { "path": "tests/**", "note": "tests first when TDD is required" }
      ],
      "produces_artefact": null,
      "description": "Implements ready plans task by task. Parses each plan into envelopes, then runs one task agent per task under TDD enforcement."
    },
    {
      "id": "dev-code-review",
      "kind": "skill",
      "label": "Code Review",
      "phase": "verify",
      "skill": "dev-code-review",
      "args_allowed": [
        { "flag": "--all", "takes_value": false, "note": "every implemented plan" },
        { "flag": "--verbose", "takes_value": false, "note": "full finding detail" }
      ],
      "args_default": ["--all"],
      "interactive": false,
      "agents": [{ "name": "code-review-worker", "fan_out": "1 per plan" }],
      "consumes": [
        { "path": "docs/implr/plans/**", "note": "acceptance criteria" },
        { "path": "src/**", "note": "the diff" }
      ],
      "produces": [],
      "produces_artefact": "review",
      "description": "Reviews what was built against each plan's acceptance criteria in a fresh context, then issues a verdict."
    },
    {
      "id": "qa-testing",
      "kind": "skill",
      "label": "Testing",
      "phase": "verify",
      "skill": "qa-testing",
      "args_allowed": [{ "flag": "--all", "takes_value": false, "note": "" }],
      "args_default": ["--all"],
      "interactive": false,
      "agents": [],
      "consumes": [],
      "produces": [],
      "produces_artefact": null,
      "description": "PLANNED - a dedicated test-execution step. Declared so it appears in the process diagram; the skill does not exist yet."
    },
    {
      "id": "sec-review",
      "kind": "skill",
      "label": "Security Checks",
      "phase": "verify",
      "skill": "sec-review",
      "args_allowed": [{ "flag": "--all", "takes_value": false, "note": "" }],
      "args_default": ["--all"],
      "interactive": false,
      "agents": [],
      "consumes": [],
      "produces": [],
      "produces_artefact": null,
      "description": "PLANNED - a dedicated security review step. Declared so it appears in the process diagram; the skill does not exist yet."
    }
  ]
}
```

- [ ] **Step 2: Confirm it reaches an installed workspace**

```bash
cd /tmp/studio-probe && bash "$IMPLR/install.sh"
ls docs/implr/schemas/step-registry.json
```

Expected: present. `install.sh` copies `schemas/*.json`, so no installer change is needed.

---

### Task 2: The registry loader

**Files:**
- Create: `studio/backend/implr_studio/registry.py`
- Test: `studio/backend/tests/test_registry.py`

**Interfaces:**
- Produces:
  - `registry.ArgSpec` — frozen: `flag`, `takes_value`, `value_pattern: str | None`, `note`.
  - `registry.AgentRef` — frozen: `name`, `fan_out`.
  - `registry.IOPath` — frozen: `path`, `note`.
  - `registry.Step` — frozen: `id`, `kind`, `label`, `phase`, `skill`, `args_allowed: tuple[ArgSpec, ...]`, `args_default: tuple[str, ...]`, `interactive`, `agents: tuple[AgentRef, ...]`, `consumes`, `produces`, `produces_artefact: str | None`, `description`, `available`.
  - `registry.KINDS = ("skill", "agent")` — every shipped entry is `"skill"`. The field is
    validated now and carried through so Phase 8 can add `"agent"` without reshaping `Step`
    or every fixture that constructs one.
  - `Step.flags -> tuple[str, ...]`, `Step.arg(flag) -> ArgSpec | None`, `Step.agent_names() -> tuple[str, ...]` — so callers never re-scan `args_allowed`.
  - `registry.Registry` — `.steps: dict[str, Step]`, `.get(id) -> Step | None`.
  - `registry.load_registry(schema_dir, skills_dir) -> Registry`
  - `registry.RegistryError`
  - `registry.PHASES = ("discovery", "design", "requirements", "planning", "build", "verify")`
  - `registry.TIERS = ("haiku", "sonnet", "opus")`

`args_allowed` entries are **objects, not strings** — several implr flags take a value, and a
flat whitelist makes those flags selectable and inert. A `takes_value: true` spec must carry
a `value_pattern`; the loader refuses one that does not, because an unvalidated value is the
one route by which a path could reach an argv vector unchecked.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_registry.py`:

```python
import json
from pathlib import Path

import pytest

from implr_studio import registry


def _write(schema_dir: Path, steps: list[dict]) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "step-registry.json").write_text(
        json.dumps({"steps": steps}), encoding="utf-8")


def _skill(skills_dir: Path, name: str) -> None:
    (skills_dir / name).mkdir(parents=True, exist_ok=True)
    (skills_dir / name / "SKILL.md").write_text("---\nname: %s\n---\n" % name, encoding="utf-8")


BASE = {
    "id": "doc-ingest",
    "kind": "skill",
    "label": "Document Ingestion",
    "phase": "discovery",
    "skill": "doc-ingest",
    "args_allowed": [
        {"flag": "--registry-only", "takes_value": False, "note": "fast scan"},
        {"flag": "--file", "takes_value": True,
         "value_pattern": "^[A-Za-z0-9._/-]{1,200}$", "note": "one document"},
    ],
    "args_default": [],
    "interactive": False,
    "agents": [{"name": "doc-ingest-digester", "fan_out": "1 per changed doc"}],
    "consumes": [{"path": "docs/kb/**", "note": "18 formats"}],
    "produces": [{"path": "docs/implr/kb-index/master-synthesis.md", "note": ""}],
    "produces_artefact": None,
    "description": "Indexes and digests the knowledge base.",
}


def test_loads_a_step(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.label == "Document Ingestion"
    assert step.phase == "discovery"
    assert step.flags == ("--registry-only", "--file")
    assert step.interactive is False


def test_step_is_available_when_the_skill_exists(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    assert registry.load_registry(schema_dir, skills_dir).get("doc-ingest").available is True


def test_step_is_unavailable_when_the_skill_is_missing(tmp_path: Path):
    """A planned step is not an error - it renders dashed in the palette."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, id="sec-review", skill="sec-review", phase="verify")])
    skills_dir.mkdir(parents=True)

    assert registry.load_registry(schema_dir, skills_dir).get("sec-review").available is False


def test_arg_specs_carry_value_metadata(tmp_path: Path):
    """A flat flag whitelist cannot express --file <path>. This is why args are objects."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.arg("--registry-only").takes_value is False
    assert step.arg("--file").takes_value is True
    assert step.arg("--file").value_pattern == "^[A-Za-z0-9._/-]{1,200}$"
    assert step.arg("--nope") is None


def test_value_taking_arg_without_a_pattern_rejected(tmp_path: Path):
    """An unvalidated value is the one way a path reaches an argv vector unchecked."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=[
        {"flag": "--file", "takes_value": True, "note": ""}])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="--file.*requires a value_pattern"):
        registry.load_registry(schema_dir, skills_dir)


def test_invalid_value_pattern_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=[
        {"flag": "--file", "takes_value": True, "value_pattern": "([unclosed", "note": ""}])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="not a valid regex"):
        registry.load_registry(schema_dir, skills_dir)


def test_bare_string_args_allowed_rejected(tmp_path: Path):
    """Refuse the pre-configurator format loudly rather than loading empty arg specs."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=["--dry-run"])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="must be objects"):
        registry.load_registry(schema_dir, skills_dir)


def test_duplicate_flag_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=[
        {"flag": "--dry-run", "takes_value": False, "note": ""},
        {"flag": "--dry-run", "takes_value": False, "note": ""}])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="duplicate flag"):
        registry.load_registry(schema_dir, skills_dir)


def test_args_default_must_name_an_allowed_flag(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_default=["--nope"])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="args_default entry '--nope' not in args_allowed"):
        registry.load_registry(schema_dir, skills_dir)


def test_args_default_cannot_name_a_value_taking_flag(tmp_path: Path):
    """A default cannot supply a value, so it must not select a flag that needs one."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_default=["--file"])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="args_default entry '--file' takes a value"):
        registry.load_registry(schema_dir, skills_dir)


def test_agents_load_in_dispatch_order(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, agents=[
        {"name": "arch-excerpter", "fan_out": "1 per plan"},
        {"name": "plan-runner", "fan_out": "1 per plan, cap 5"},
        {"name": "task-executor", "fan_out": "1 per task"}])])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.agent_names() == ("arch-excerpter", "plan-runner", "task-executor")
    assert step.agents[1].fan_out == "1 per plan, cap 5"


def test_duplicate_step_id_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE, dict(BASE)])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="duplicate step id: doc-ingest"):
        registry.load_registry(schema_dir, skills_dir)


def test_unknown_phase_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, phase="wibble")])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="unknown phase 'wibble'"):
        registry.load_registry(schema_dir, skills_dir)


def test_kind_is_loaded(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.kind == "skill"


def test_unknown_kind_rejected(tmp_path: Path):
    """Phase 8 adds 'agent'. Anything else is a typo, now and then."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, kind="wizard")])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="unknown kind 'wizard'"):
        registry.load_registry(schema_dir, skills_dir)


def test_every_shipped_step_is_kind_skill():
    """The plugin registry declares only skill-backed steps. Agent-backed ones
    are project-owned and live in steps.yaml from Phase 8."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    assert {s.kind for s in reg.steps.values()} == {"skill"}


def test_missing_required_field_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [{k: v for k, v in BASE.items() if k != "skill"}])
    skills_dir.mkdir(parents=True)

    with pytest.raises(registry.RegistryError, match="missing required field: skill"):
        registry.load_registry(schema_dir, skills_dir)


# --- against the real shipped file -----------------------------------------

def test_shipped_registry_is_valid():
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    assert len(reg.steps) == 9
    assert reg.get("doc-ingest").available is True
    assert reg.get("dev-executor").available is True
    assert reg.get("qa-testing").available is False
    assert reg.get("sec-review").available is False


def test_shipped_registry_agents_all_exist():
    """Every agent a step claims to dispatch must have a definition."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    for step in reg.steps.values():
        for agent in step.agents:
            assert (root / ".claude" / "agents" / ("%s.md" % agent.name)).is_file(), (
                "step %s claims agent %s, which has no definition" % (step.id, agent.name))


def test_shipped_registry_artefacts_are_real_types():
    """produces_artefact must name a frontmatter-rules.json artefact type."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    contracts = implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    for step in reg.steps.values():
        if step.produces_artefact is not None:
            assert step.produces_artefact in contracts.artefact_types


def test_shipped_registry_flags_exist_in_their_skills():
    """A flag the palette offers must be one the skill actually documents."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    for step in reg.steps.values():
        if not step.available:
            continue
        text = (root / "skills" / step.skill / "SKILL.md").read_text(encoding="utf-8")
        for flag in step.flags:
            assert flag in text, "step %s offers %s, absent from its SKILL.md" % (step.id, flag)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'registry'`

- [ ] **Step 3: Write the loader**

Create `studio/backend/implr_studio/registry.py`:

```python
"""Loads the declarative catalogue of pipeline steps.

Adding a step is a registry edit. Nothing here knows the name of any particular
step, agent, or artefact type - those are all data.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

PHASES = ("discovery", "design", "requirements", "planning", "build", "verify")
TIERS = ("haiku", "sonnet", "opus")

# "skill" runs a slash command and the SKILL.md owns the behaviour. "agent" is
# authored in the UI and the studio owns it - Phase 8. Declared here so the field
# is validated from the start rather than retrofitted.
KINDS = ("skill", "agent")

_REQUIRED_FIELDS = (
    "id", "kind", "label", "phase", "skill",
    "args_allowed", "args_default", "interactive",
    "agents", "consumes", "produces", "produces_artefact", "description",
)


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class ArgSpec:
    flag: str
    takes_value: bool
    value_pattern: str | None
    note: str


@dataclass(frozen=True)
class AgentRef:
    name: str
    fan_out: str


@dataclass(frozen=True)
class IOPath:
    path: str
    note: str


@dataclass(frozen=True)
class Step:
    id: str
    kind: str
    label: str
    phase: str
    skill: str
    args_allowed: tuple[ArgSpec, ...]
    args_default: tuple[str, ...]
    interactive: bool
    agents: tuple[AgentRef, ...]
    consumes: tuple[IOPath, ...]
    produces: tuple[IOPath, ...]
    produces_artefact: str | None
    description: str
    available: bool

    @property
    def flags(self) -> tuple[str, ...]:
        return tuple(a.flag for a in self.args_allowed)

    def arg(self, flag: str) -> ArgSpec | None:
        for spec in self.args_allowed:
            if spec.flag == flag:
                return spec
        return None

    def agent_names(self) -> tuple[str, ...]:
        return tuple(a.name for a in self.agents)


@dataclass(frozen=True)
class Registry:
    steps: dict[str, Step]

    def get(self, step_id: str) -> Step | None:
        return self.steps.get(step_id)


def _arg_specs(step_id: str, entries) -> tuple[ArgSpec, ...]:
    specs: list[ArgSpec] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or "flag" not in entry:
            raise RegistryError(
                "step %s: args_allowed entries must be objects with a 'flag' "
                "(bare strings were the pre-configurator format)" % step_id
            )
        flag = entry["flag"]
        if flag in seen:
            raise RegistryError("step %s: duplicate flag %r in args_allowed" % (step_id, flag))
        seen.add(flag)

        takes_value = bool(entry.get("takes_value", False))
        pattern = entry.get("value_pattern")
        if takes_value:
            if not pattern:
                raise RegistryError(
                    "step %s: arg %r takes a value and therefore requires a value_pattern"
                    % (step_id, flag)
                )
            try:
                re.compile(pattern)
            except re.error as e:
                raise RegistryError(
                    "step %s: arg %r value_pattern is not a valid regex: %s" % (step_id, flag, e)
                )
        specs.append(ArgSpec(
            flag=flag,
            takes_value=takes_value,
            value_pattern=pattern if takes_value else None,
            note=entry.get("note", ""),
        ))
    return tuple(specs)


def load_registry(schema_dir: Path, skills_dir: Path) -> Registry:
    path = Path(schema_dir) / "step-registry.json"
    if not path.is_file():
        raise RegistryError("step-registry.json not found at %s" % path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    steps: dict[str, Step] = {}
    for entry in raw.get("steps", []):
        for field in _REQUIRED_FIELDS:
            if field not in entry:
                raise RegistryError("missing required field: %s" % field)
        step_id = entry["id"]
        if step_id in steps:
            raise RegistryError("duplicate step id: %s" % step_id)
        if entry["kind"] not in KINDS:
            raise RegistryError(
                "step %s: unknown kind %r (legal: %s)"
                % (step_id, entry["kind"], list(KINDS))
            )
        if entry["phase"] not in PHASES:
            raise RegistryError(
                "step %s: unknown phase %r (legal: %s)"
                % (step_id, entry["phase"], list(PHASES))
            )

        specs = _arg_specs(step_id, entry["args_allowed"])
        by_flag = {s.flag: s for s in specs}
        for arg in entry["args_default"]:
            spec = by_flag.get(arg)
            if spec is None:
                raise RegistryError(
                    "step %s: args_default entry %r not in args_allowed" % (step_id, arg))
            if spec.takes_value:
                raise RegistryError(
                    "step %s: args_default entry %r takes a value, so it cannot be a default"
                    % (step_id, arg))

        artefact = entry["produces_artefact"]
        if artefact is not None and not isinstance(artefact, str):
            raise RegistryError("step %s: produces_artefact must be a string or null" % step_id)

        skill_md = Path(skills_dir) / entry["skill"] / "SKILL.md"
        steps[step_id] = Step(
            id=step_id,
            kind=entry["kind"],
            label=entry["label"],
            phase=entry["phase"],
            skill=entry["skill"],
            args_allowed=specs,
            args_default=tuple(entry["args_default"]),
            interactive=bool(entry["interactive"]),
            agents=tuple(AgentRef(name=a["name"], fan_out=a.get("fan_out", ""))
                         for a in entry["agents"]),
            consumes=tuple(IOPath(path=c["path"], note=c.get("note", ""))
                           for c in entry["consumes"]),
            produces=tuple(IOPath(path=p["path"], note=p.get("note", ""))
                           for p in entry["produces"]),
            produces_artefact=artefact,
            description=entry["description"],
            available=skill_md.is_file(),
        )
    return Registry(steps=steps)
```

- [ ] **Step 4: Run and commit**

Run: `cd studio/backend && python -m pytest tests/test_registry.py -v`

```bash
git add scaffold/schemas/step-registry.json studio/backend/implr_studio/registry.py studio/backend/tests/test_registry.py
git commit -m "feat(studio): step registry file and loader"
```

---

### Task 3: Context, serializer, and the registry route

**Files:**
- Create: `studio/backend/implr_studio/serialize.py`
- Create: `studio/backend/implr_studio/context.py`
- Modify: `studio/backend/implr_studio/api.py`, `server.py`
- Test: `studio/backend/tests/test_serialize.py`, `tests/test_api_registry.py`

**Interfaces:**
- Produces:
  - `serialize.step_to_dict(step) -> dict`, `serialize.registry_to_dict(reg) -> dict` → `{"steps": [...], "phases": [...], "tiers": [...]}`
  - `context.AppContext` — dataclass: `workspace: Path`, `registry`.
  - `context.build_context(workspace) -> AppContext` — loads the registry from the
    workspace's installed schemas, resolving availability against
    `<workspace>/.claude/skills/`.
  - `api.create_app(context)` — **signature change** from Phase 0's `workspace_name`.
  - `GET /api/registry`

`create_app` now takes the context rather than a name; `/api/health` reads
`context.workspace.name`. Phase 0's health tests need updating — that is the churn vertical
slicing buys, and it is a two-line change.

- [ ] **Step 1: Write the failing tests**

Create `studio/backend/tests/test_serialize.py`:

```python
import json
from pathlib import Path

import pytest

from implr_studio import registry, serialize


@pytest.fixture
def reg(tmp_path: Path) -> registry.Registry:
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    schema_dir.mkdir(parents=True)
    steps = [
        {"id": "doc-ingest", "kind": "skill", "label": "Document Ingestion", "phase": "discovery",
         "skill": "doc-ingest",
         "args_allowed": [{"flag": "--dry-run", "takes_value": False, "note": "n"}],
         "args_default": [], "interactive": False,
         "agents": [{"name": "doc-ingest-digester", "fan_out": "1 per doc"}],
         "consumes": [{"path": "docs/kb/**", "note": ""}],
         "produces": [{"path": "docs/implr/kb-index/master-synthesis.md", "note": ""}],
         "produces_artefact": None, "description": "d"},
        {"id": "sec-review", "kind": "skill", "label": "Security Checks", "phase": "verify",
         "skill": "sec-review", "args_allowed": [], "args_default": [],
         "interactive": False, "agents": [], "consumes": [], "produces": [],
         "produces_artefact": None, "description": "planned"},
    ]
    (schema_dir / "step-registry.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    (skills_dir / "doc-ingest").mkdir(parents=True)
    (skills_dir / "doc-ingest" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return registry.load_registry(schema_dir, skills_dir)


def test_step_to_dict_exposes_availability(reg):
    steps = {s["id"]: s for s in serialize.registry_to_dict(reg)["steps"]}

    assert steps["doc-ingest"]["available"] is True
    assert steps["sec-review"]["available"] is False


def test_arg_specs_serialise_as_objects(reg):
    steps = {s["id"]: s for s in serialize.registry_to_dict(reg)["steps"]}

    assert steps["doc-ingest"]["args_allowed"] == [
        {"flag": "--dry-run", "takes_value": False, "value_pattern": None, "note": "n"},
    ]


def test_agents_and_io_serialise(reg):
    steps = {s["id"]: s for s in serialize.registry_to_dict(reg)["steps"]}

    assert steps["doc-ingest"]["agents"] == [
        {"name": "doc-ingest-digester", "fan_out": "1 per doc"}]
    assert steps["doc-ingest"]["consumes"][0]["path"] == "docs/kb/**"
    assert steps["doc-ingest"]["produces_artefact"] is None


def test_registry_to_dict_includes_phase_and_tier_order(reg):
    body = serialize.registry_to_dict(reg)

    assert body["phases"] == list(registry.PHASES)
    assert body["tiers"] == list(registry.TIERS)


def test_registry_to_dict_is_json_serializable(reg):
    json.dumps(serialize.registry_to_dict(reg))


def test_steps_keep_registry_order(reg):
    """Palette grouping relies on phase, but within a phase, file order is the order."""
    ids = [s["id"] for s in serialize.registry_to_dict(reg)["steps"]]

    assert ids == ["doc-ingest", "sec-review"]
```

Create `studio/backend/tests/test_api_registry.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from implr_studio import context as ctx_mod
from implr_studio.api import create_app


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A target project with the real schemas AND skills installed."""
    from implr_studio import implr_bridge

    src = implr_bridge.repo_root() / "scaffold" / "schemas"
    dst = tmp_path / "docs" / "implr" / "schemas"
    dst.mkdir(parents=True)
    for f in src.glob("*.json"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    # Availability resolves against the WORKSPACE's installed skills, so a
    # realistic fixture installs them the way install.sh does.
    for skill_dir in (implr_bridge.repo_root() / "skills").iterdir():
        if not (skill_dir / "SKILL.md").is_file():
            continue
        target = tmp_path / ".claude" / "skills" / skill_dir.name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(
            (skill_dir / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8")

    return tmp_path


@pytest.fixture
def client(workspace: Path):
    with TestClient(create_app(ctx_mod.build_context(workspace))) as c:
        yield c


def test_registry_lists_every_step_with_availability(client):
    body = client.get("/api/registry").json()

    steps = {s["id"]: s for s in body["steps"]}
    assert len(steps) == 9
    assert steps["doc-ingest"]["available"] is True
    assert steps["sec-review"]["available"] is False


def test_registry_exposes_phase_and_tier_vocabularies(client):
    body = client.get("/api/registry").json()

    assert body["phases"] == ["discovery", "design", "requirements", "planning", "build", "verify"]
    assert body["tiers"] == ["haiku", "sonnet", "opus"]


def test_registry_serves_value_taking_flags(client):
    """The configurator needs this in Phase 4; serving it now costs nothing."""
    steps = {s["id"]: s for s in client.get("/api/registry").json()["steps"]}

    task = next(a for a in steps["dev-executor"]["args_allowed"] if a["flag"] == "--task")
    assert task["takes_value"] is True
    assert task["value_pattern"]


def test_registry_serves_the_agent_dispatch_map(client):
    steps = {s["id"]: s for s in client.get("/api/registry").json()["steps"]}

    assert [a["name"] for a in steps["dev-executor"]["agents"]] == [
        "arch-excerpter", "plan-runner", "task-executor"]


def test_registry_serves_the_step_kind(client):
    steps = {s["id"]: s for s in client.get("/api/registry").json()["steps"]}

    assert steps["doc-ingest"]["kind"] == "skill"


def test_availability_is_resolved_against_the_workspace_skills(tmp_path):
    """Not the implr repo's skills/ tree.

    The adapter runs with cwd=<workspace>, so that is where the CLI resolves a
    slash command from. A palette that consulted the plugin source instead could
    call a step usable while the agent cannot find it.
    """
    from implr_studio import implr_bridge

    src = implr_bridge.repo_root() / "scaffold" / "schemas"
    dst = tmp_path / "docs" / "implr" / "schemas"
    dst.mkdir(parents=True)
    for f in src.glob("*.json"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    # An empty workspace skills tree: every step reads unavailable, even though
    # the implr repo itself has all eight installed.
    (tmp_path / ".claude" / "skills").mkdir(parents=True)

    with TestClient(create_app(ctx_mod.build_context(tmp_path))) as c:
        steps = {s["id"]: s for s in c.get("/api/registry").json()["steps"]}
    assert all(s["available"] is False for s in steps.values())

    # Install one, and only that one becomes available.
    d = tmp_path / ".claude" / "skills" / "doc-ingest"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: doc-ingest\n---\n", encoding="utf-8")

    with TestClient(create_app(ctx_mod.build_context(tmp_path))) as c:
        steps = {s["id"]: s for s in c.get("/api/registry").json()["steps"]}
    assert steps["doc-ingest"]["available"] is True
    assert steps["arch-gen"]["available"] is False


def test_health_still_reports_the_workspace_name(client, workspace):
    assert client.get("/api/health").json()["workspace"] == workspace.name


def test_no_route_exposes_a_filesystem_path(client):
    blob = str(client.get("/openapi.json").json()).lower()

    for banned in ("workspace_path", "cwd", "directory", "file_path"):
        assert banned not in blob
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/backend && python -m pytest tests/test_serialize.py tests/test_api_registry.py -v`
Expected: FAIL — cannot import `serialize` / `context`

- [ ] **Step 3: Write `serialize.py`**

```python
"""Pure dict conversions for API responses. No FastAPI imports belong here."""
from .registry import PHASES, TIERS, Registry, Step


def step_to_dict(step: Step) -> dict:
    return {
        "id": step.id,
        "kind": step.kind,
        "label": step.label,
        "phase": step.phase,
        "skill": step.skill,
        "args_allowed": [
            {
                "flag": a.flag,
                "takes_value": a.takes_value,
                "value_pattern": a.value_pattern,
                "note": a.note,
            }
            for a in step.args_allowed
        ],
        "args_default": list(step.args_default),
        "interactive": step.interactive,
        "agents": [{"name": a.name, "fan_out": a.fan_out} for a in step.agents],
        "consumes": [{"path": p.path, "note": p.note} for p in step.consumes],
        "produces": [{"path": p.path, "note": p.note} for p in step.produces],
        "produces_artefact": step.produces_artefact,
        "description": step.description,
        "available": step.available,
    }


def registry_to_dict(reg: Registry) -> dict:
    # The whole registry is served now, even though the UI renders only a slice
    # of it until Phase 7. Serving the complete record avoids growing this
    # payload - and its tests - five separate times.
    return {
        "steps": [step_to_dict(s) for s in reg.steps.values()],
        "phases": list(PHASES),
        "tiers": list(TIERS),
    }
```

- [ ] **Step 4: Write `context.py`**

```python
"""The wired-up dependency bundle, built once at startup and injected everywhere.

Nothing in the API layer reaches for a global. Tests build a context pointed at a
temp workspace and get a fully functional app. It grows one field per phase: the
pipeline path in Phase 2, the store and orchestrator in Phase 9.
"""
from dataclasses import dataclass
from pathlib import Path

from .implr_bridge import repo_root, resolve_schema_dir
from .registry import load_registry


@dataclass
class AppContext:
    workspace: Path
    registry: object


def build_context(workspace: Path) -> AppContext:
    workspace = Path(workspace).resolve()
    # Both from the WORKSPACE. Availability must be resolved against the target
    # project's installed skills, because the adapter runs with cwd=<workspace>
    # and that is where the CLI resolves a slash command from. Judging it against
    # the implr repo's skills/ tree instead would let the palette call a step
    # usable while the agent cannot find it - which is what happens when the
    # backend runs from a different implr checkout than the project was
    # installed from.
    reg = load_registry(
        resolve_schema_dir(workspace),
        workspace / ".claude" / "skills",
    )
    return AppContext(workspace=workspace, registry=reg)
```

- [ ] **Step 5: Update `api.py` and `server.py`**

In `api.py`, change the signature and add the route:

```python
def create_app(context) -> FastAPI:
    app = FastAPI(title="implr Studio", version=VERSION)
    app.state.ctx = context

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "workspace": context.workspace.name,
            "version": VERSION,
        }

    @app.get("/api/registry")
    def get_registry() -> dict:
        return serialize.registry_to_dict(context.registry)

    # ... the root page, unchanged ...
    return app
```

Add `from . import serialize` at the top. In `server.py`, replace the `create_app` call:

```python
    from .context import build_context

    try:
        context = build_context(workspace)
    except Exception as e:
        sys.stderr.write("error: could not load the step registry: %s\n" % e)
        sys.stderr.write("hint: re-run the implr installer so docs/implr/schemas is current.\n")
        return 2

    app = create_app(context)
```

A missing or malformed registry now exits `2` with a hint rather than a traceback. Phase 0's
`test_api_health.py` needs its `create_app(workspace_name=...)` calls updated to pass a
context — build one with `build_context(tmp_path)` after copying the schemas in, exactly as
`test_api_registry.py` does.

- [ ] **Step 6: Run the whole backend suite and commit**

Run: `cd studio/backend && python -m pytest -v`

```bash
git add studio/backend
git commit -m "feat(studio): app context, registry serializer, and GET /api/registry"
```

---

### Task 4: Wire the registry check into implr-validate

**Files:**
- Modify: `scripts/implr_validate/checks.py`, `cli.py`
- Test: `tests/test_step_registry_check.py`

**Interfaces:**
- Produces:
  - `checks.check_step_registry(root, contracts) -> list[Finding]` — validates the registry against `skills/`, `.claude/agents/` and the artefact types.
  - `cli` exits `1` only when at least one finding is `level == "error"`. `"info"` findings print without failing.

This exists so a malformed registry is caught by the repo's own validator, not only by the
studio suite. A **planned step is `info`, never `error`** — otherwise adding `sec-review` to
the registry before writing the skill would break the build, which is exactly the workflow
the registry exists to enable.

- [ ] **Step 1: Write the failing test**

Create `tests/test_step_registry_check.py`:

```python
import json
import os

import pytest

from implr_validate.checks import check_step_registry
from implr_validate.contracts import load_contracts

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def contracts():
    return load_contracts(os.path.join(REPO, "scaffold", "schemas"))


def _write(root, steps):
    schema_dir = os.path.join(root, "scaffold", "schemas")
    os.makedirs(schema_dir, exist_ok=True)
    with open(os.path.join(schema_dir, "step-registry.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps}, f)


def _skill(root, name):
    d = os.path.join(root, "skills", name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: %s\n---\n" % name)


def _agent(root, name):
    d = os.path.join(root, ".claude", "agents")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "%s.md" % name), "w", encoding="utf-8") as f:
        f.write("---\nname: %s\n---\n" % name)


BASE = {
    "id": "doc-ingest", "kind": "skill", "label": "Document Ingestion", "phase": "discovery",
    "skill": "doc-ingest",
    "args_allowed": [{"flag": "--dry-run", "takes_value": False, "note": ""}],
    "args_default": [], "interactive": False,
    "agents": [], "consumes": [], "produces": [], "produces_artefact": None,
    "description": "d",
}


def test_valid_registry_has_no_findings(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [BASE])
    _skill(root, "doc-ingest")

    assert check_step_registry(root, contracts) == []


def test_missing_registry_file_is_not_an_error(tmp_path, contracts):
    """The registry is optional for repos that predate implr Studio."""
    assert check_step_registry(str(tmp_path), contracts) == []


def test_planned_step_is_info_not_error(tmp_path, contracts):
    """Designing ahead of implementation must not fail the build."""
    root = str(tmp_path)
    _write(root, [dict(BASE, id="sec-review", skill="sec-review", phase="verify")])
    os.makedirs(os.path.join(root, "skills"), exist_ok=True)

    findings = check_step_registry(root, contracts)

    assert len(findings) == 1
    assert findings[0].level == "info"
    assert "sec-review" in findings[0].message


def test_malformed_json_is_an_error_not_a_crash(tmp_path, contracts):
    root = str(tmp_path)
    schema_dir = os.path.join(root, "scaffold", "schemas")
    os.makedirs(schema_dir)
    with open(os.path.join(schema_dir, "step-registry.json"), "w", encoding="utf-8") as f:
        f.write("{not json")

    assert check_step_registry(root, contracts)[0].level == "error"


def test_bare_string_args_allowed_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, args_allowed=["--dry-run"])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "objects" in findings[0].message


def test_value_taking_arg_without_a_pattern_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, args_allowed=[{"flag": "--file", "takes_value": True, "note": ""}])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "value_pattern" in findings[0].message


def test_agent_without_a_definition_is_an_error(tmp_path, contracts):
    """A step that dispatches a non-existent agent renders a control that configures nothing."""
    root = str(tmp_path)
    _write(root, [dict(BASE, agents=[{"name": "ghost-worker", "fan_out": "1"}])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "ghost-worker" in findings[0].message


def test_declared_agent_with_a_definition_is_fine(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, agents=[{"name": "plan-worker", "fan_out": "1"}])])
    _skill(root, "doc-ingest")
    _agent(root, "plan-worker")

    assert check_step_registry(root, contracts) == []


def test_unknown_produces_artefact_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, produces_artefact="unicorn")])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "unicorn" in findings[0].message


def test_unknown_phase_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, phase="wibble")])
    _skill(root, "doc-ingest")

    assert check_step_registry(root, contracts)[0].level == "error"


def test_the_real_repo_registry_passes(contracts):
    """The shipped registry must be valid, with the two planned steps reported as info."""
    findings = check_step_registry(REPO, contracts)

    assert [f for f in findings if f.level == "error"] == []
    planned = {f.message for f in findings if f.level == "info"}
    assert any("qa-testing" in m for m in planned)
    assert any("sec-review" in m for m in planned)
```

Also add to `tests/test_cli.py`:

```python
def test_info_findings_do_not_fail_the_exit_code():
    """A planned step prints but must not break the build."""
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    from implr_validate.cli import main

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert main(["--repo", "--root", root]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_step_registry_check.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_step_registry'`

- [ ] **Step 3: Append the check to `checks.py`**

`checks.py` already imports `os` and `re`; add `import json` at the top. Then append:

```python
# --- step registry (implr Studio) ---

_REGISTRY_PHASES = ("discovery", "design", "requirements", "planning", "build", "verify")
_REGISTRY_KINDS = ("skill", "agent")
_REGISTRY_FIELDS = (
    "id", "kind", "label", "phase", "skill",
    "args_allowed", "args_default", "interactive",
    "agents", "consumes", "produces", "produces_artefact", "description",
)


def check_step_registry(root, contracts):
    """Validate scaffold/schemas/step-registry.json against skills/ and the contracts.

    A registered step whose skill does not exist yet is reported at level "info",
    never "error": designing a pipeline ahead of implementing its steps is the
    workflow the registry exists to support. Everything else - a malformed arg
    spec, an agent with no definition, an unknown artefact type - is an error,
    because each one produces a UI control that configures nothing.

    Deliberately re-implements the loader's rules rather than importing
    implr_studio: implr-validate must keep working in a project that has never
    installed the studio backend.
    """
    rel = os.path.join("scaffold", "schemas", "step-registry.json")
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return []

    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except ValueError as e:
        return [Finding("error", rel, "invalid JSON: %s" % e)]

    findings = []
    seen = set()
    for entry in raw.get("steps", []):
        step_id = entry.get("id", "<no id>")

        missing = [f for f in _REGISTRY_FIELDS if f not in entry]
        if missing:
            findings.append(Finding(
                "error", rel,
                "step %s missing required field(s): %s" % (step_id, ", ".join(missing))))
            continue

        if step_id in seen:
            findings.append(Finding("error", rel, "duplicate step id: %s" % step_id))
            continue
        seen.add(step_id)

        if entry["kind"] not in _REGISTRY_KINDS:
            findings.append(Finding(
                "error", rel,
                "step %s has unknown kind %r (legal: %s)"
                % (step_id, entry["kind"], list(_REGISTRY_KINDS))))

        if entry["phase"] not in _REGISTRY_PHASES:
            findings.append(Finding(
                "error", rel,
                "step %s has unknown phase %r (legal: %s)"
                % (step_id, entry["phase"], list(_REGISTRY_PHASES))))

        specs = {}
        for spec in entry["args_allowed"]:
            if not isinstance(spec, dict) or "flag" not in spec:
                findings.append(Finding(
                    "error", rel,
                    "step %s args_allowed entries must be objects with a 'flag'" % step_id))
                continue
            if spec["flag"] in specs:
                findings.append(Finding(
                    "error", rel,
                    "step %s has duplicate flag %r in args_allowed" % (step_id, spec["flag"])))
                continue
            specs[spec["flag"]] = spec
            if spec.get("takes_value"):
                pattern = spec.get("value_pattern")
                if not pattern:
                    findings.append(Finding(
                        "error", rel,
                        "step %s arg %r takes a value but has no value_pattern"
                        % (step_id, spec["flag"])))
                else:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        findings.append(Finding(
                            "error", rel,
                            "step %s arg %r has an invalid value_pattern: %s"
                            % (step_id, spec["flag"], e)))

        for arg in entry["args_default"]:
            spec = specs.get(arg)
            if spec is None:
                findings.append(Finding(
                    "error", rel,
                    "step %s args_default entry %r is not in args_allowed" % (step_id, arg)))
            elif spec.get("takes_value"):
                findings.append(Finding(
                    "error", rel,
                    "step %s args_default entry %r takes a value, so it cannot be a default"
                    % (step_id, arg)))

        for agent in entry["agents"]:
            name = agent.get("name") if isinstance(agent, dict) else None
            if not name:
                findings.append(Finding(
                    "error", rel, "step %s has an agent entry with no name" % step_id))
                continue
            if not os.path.isfile(os.path.join(root, ".claude", "agents", "%s.md" % name)):
                findings.append(Finding(
                    "error", rel,
                    "step %s dispatches agent %r, which has no .claude/agents/%s.md"
                    % (step_id, name, name)))

        artefact = entry["produces_artefact"]
        if artefact is not None and artefact not in contracts.artefact_types:
            findings.append(Finding(
                "error", rel,
                "step %s produces_artefact %r is not a known artefact type (known: %s)"
                % (step_id, artefact, sorted(contracts.artefact_types))))

        if not os.path.isfile(os.path.join(root, "skills", entry["skill"], "SKILL.md")):
            findings.append(Finding(
                "info", rel,
                "step %s is planned: skills/%s/SKILL.md does not exist yet"
                % (step_id, entry["skill"])))

    return findings
```

- [ ] **Step 4: Wire it into `cli.py` and make the exit code level-aware**

Change the import:

```python
from .checks import check_workspace, check_repo_prose, check_step_registry
```

In the `if args.repo:` block, after `contracts` is loaded, append:

```python
        findings.extend(check_step_registry(args.root, contracts))
```

Replace the reporting block at the end of `main`:

```python
    if findings:
        for fnd in findings:
            sys.stderr.write("%s: %s: %s\n" % (fnd.level, fnd.path, fnd.message))
        errors = [f for f in findings if f.level == "error"]
        sys.stderr.write("\n%d finding(s), %d error(s)\n" % (len(findings), len(errors)))
        if errors:
            return 1
    sys.stdout.write("implr-validate: OK\n")
    return 0
```

Every finding that existed before this change is level `"error"`, so no previously-failing
case starts passing. The only new behaviour is that `"info"` prints without failing.

- [ ] **Step 5: Verify and commit**

```bash
python -m pytest tests/ -q
PYTHONPATH=scripts python -m implr_validate --repo --root .
```

Expected: all tests pass; `implr-validate` exits `0` printing exactly two `info:` lines,
naming `qa-testing` and `sec-review`.

```bash
git add scripts/implr_validate tests/test_step_registry_check.py tests/test_cli.py
git commit -m "feat(validate): check step-registry.json, with planned steps reported as info"
```

---

### Task 5: The palette

**Files:**
- Create: `studio/frontend/src/types.ts`, `src/api.ts`, `src/panels/Palette.tsx`
- Modify: `studio/frontend/src/App.tsx`, `src/app.css`
- Test: `src/api.test.ts`, `src/panels/Palette.test.tsx`

**Interfaces:**
- Produces:
  - `types.ArgSpec`, `AgentRef`, `IOPath`, `StepDef`, `Tier` — mirroring the DTOs.
  - `api.getRegistry()`, `api.ValidationError` (unused until Phase 3, defined here so `api.ts` has one shape).
  - `Palette({ steps, phases })` — search box, phase groups, dashed unavailable items.

- [ ] **Step 1: Write the failing tests**

Create `studio/frontend/src/api.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from './api';

const okJson = (body: unknown) =>
  Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);

describe('api client', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it('uses relative /api paths so no host is hardcoded', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      okJson({ steps: [], phases: [], tiers: [] }));

    await api.getRegistry();

    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toBe('/api/registry');
    expect(url).not.toContain('http');
  });

  it('throws a plain error with the backend detail on failure', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      Promise.resolve({
        ok: false, status: 500, json: () => Promise.resolve({ detail: 'registry unreadable' }),
      } as Response));

    await expect(api.getRegistry()).rejects.toThrowError(/registry unreadable/);
  });
});
```

Create `studio/frontend/src/panels/Palette.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import Palette from './Palette';
import type { StepDef } from '../types';

const base = {
  args_allowed: [], args_default: [], interactive: false,
  agents: [], consumes: [], produces: [], produces_artefact: null,
};

const steps: StepDef[] = [
  { ...base, id: 'doc-ingest', label: 'Document Ingestion', phase: 'discovery',
    skill: 'doc-ingest', description: 'Indexes the knowledge base.', available: true },
  { ...base, id: 'arch-gen', label: 'Architecture Brief', phase: 'design',
    skill: 'arch-gen', description: 'Writes ARCHITECTURE.md.', available: true,
    interactive: true },
  { ...base, id: 'sec-review', label: 'Security Checks', phase: 'verify',
    skill: 'sec-review', description: 'Security review.', available: false },
];

const phases = ['discovery', 'design', 'verify'];

describe('Palette', () => {
  it('groups steps under their phase heading', () => {
    render(<Palette steps={steps} phases={phases} />);

    expect(screen.getByText('discovery')).toBeInTheDocument();
    expect(screen.getByText('verify')).toBeInTheDocument();
  });

  it('omits a phase heading with no steps', () => {
    render(<Palette steps={steps} phases={[...phases, 'build']} />);

    expect(screen.queryByText('build')).not.toBeInTheDocument();
  });

  it('marks an unimplemented step and explains why', () => {
    render(<Palette steps={steps} phases={phases} />);

    const planned = screen.getByText('Security Checks').closest('.chip-step')!;
    expect(planned.className).toContain('chip-step--off');
    expect(planned).toHaveAttribute('title', expect.stringMatching(/not implemented/i));
  });

  it('describes an available step in its tooltip', () => {
    render(<Palette steps={steps} phases={phases} />);

    expect(screen.getByText('Document Ingestion').closest('.chip-step'))
      .toHaveAttribute('title', 'Indexes the knowledge base.');
  });

  it('badges an interactive step', () => {
    render(<Palette steps={steps} phases={phases} />);

    expect(screen.getByText('asks')).toBeInTheDocument();
  });

  it('filters by label', async () => {
    render(<Palette steps={steps} phases={phases} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'architecture');

    expect(screen.getByText('Architecture Brief')).toBeInTheDocument();
    expect(screen.queryByText('Document Ingestion')).not.toBeInTheDocument();
  });

  it('filters by description too, not only label', async () => {
    render(<Palette steps={steps} phases={phases} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'knowledge');

    expect(screen.getByText('Document Ingestion')).toBeInTheDocument();
    expect(screen.queryByText('Security Checks')).not.toBeInTheDocument();
  });

  it('says so when nothing matches', async () => {
    render(<Palette steps={steps} phases={phases} />);

    await userEvent.type(screen.getByLabelText(/search steps/i), 'zzzz');

    expect(screen.getByText(/no step matches/i)).toBeInTheDocument();
  });

  it('renders an empty state before the registry arrives', () => {
    render(<Palette steps={[]} phases={phases} />);

    expect(screen.getByText(/loading steps/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio/frontend && npm test`
Expected: FAIL — cannot resolve `./api`, `./panels/Palette`

- [ ] **Step 3: Write `types.ts`**

```ts
export type Tier = 'haiku' | 'sonnet' | 'opus';

export interface ArgSpec {
  flag: string;
  takes_value: boolean;
  value_pattern: string | null;
  note: string;
}

export interface AgentRef { name: string; fan_out: string }
export interface IOPath { path: string; note: string }

export type StepKind = 'skill' | 'agent';

export interface StepDef {
  id: string;
  kind: StepKind;
  label: string;
  phase: string;
  skill: string;
  args_allowed: ArgSpec[];
  args_default: string[];
  interactive: boolean;
  agents: AgentRef[];
  consumes: IOPath[];
  produces: IOPath[];
  produces_artefact: string | null;
  description: string;
  available: boolean;
}

export interface Finding { code: string; message: string; node_id: string | null }
```

Phase 1 renders only `label`, `phase`, `description`, `interactive` and `available`. The rest
is typed now because the payload already carries it, and a partial type would have to be
widened four more times.

- [ ] **Step 4: Write `api.ts`**

```ts
/**
 * Typed fetch wrappers. Paths are relative so the dev proxy (and the built
 * bundle served by the backend) resolve them - never hardcode a host or port.
 */
import type { Finding, StepDef, Tier } from './types';

export class ValidationError extends Error {
  findings: Finding[];
  constructor(findings: Finding[]) {
    super(findings.map((f) => f.message).join('; ') || 'pipeline is invalid');
    this.name = 'ValidationError';
    this.findings = findings;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 422 && Array.isArray((body as { findings?: Finding[] }).findings)) {
      throw new ValidationError((body as { findings: Finding[] }).findings);
    }
    const detail = (body as { detail?: unknown }).detail;
    throw new Error(typeof detail === 'string' ? detail : `request failed: ${response.status}`);
  }
  return body as T;
}

export interface RegistryResponse {
  steps: StepDef[];
  phases: string[];
  tiers: Tier[];
}

export const getRegistry = () => request<RegistryResponse>('/registry');
```

- [ ] **Step 5: Write `Palette.tsx`**

```tsx
import { useMemo, useState } from 'react';
import type { StepDef } from '../types';

interface Props {
  steps: StepDef[];
  phases: string[];
}

export default function Palette({ steps, phases }: Props) {
  const [query, setQuery] = useState('');

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return steps;
    return steps.filter((s) =>
      `${s.label} ${s.id} ${s.description}`.toLowerCase().includes(q));
  }, [steps, query]);

  const groups = phases
    .map((phase) => ({ phase, items: matches.filter((s) => s.phase === phase) }))
    .filter((g) => g.items.length > 0);

  return (
    <aside className="rail">
      <div className="rail__search">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search steps…"
          aria-label="Search steps"
        />
      </div>

      <div className="rail__list">
        {steps.length === 0 && <p className="rail__empty">Loading steps…</p>}

        {steps.length > 0 && groups.length === 0 && (
          <p className="rail__empty">No step matches “{query}”.</p>
        )}

        {groups.map(({ phase, items }) => (
          <section key={phase}>
            <h3 className="phase">{phase}</h3>
            {items.map((step) => (
              <div
                key={step.id}
                className={`chip-step${step.available ? '' : ' chip-step--off'}`}
                title={
                  step.available
                    ? step.description
                    : `${step.description} (not implemented yet - the skill does not exist)`
                }
              >
                <span>{step.label}</span>
                <span className="chip-step__meta">
                  {!step.available && <span className="tag tag--soon">soon</span>}
                  {step.available && step.interactive && <span className="tag tag--ask">asks</span>}
                </span>
              </div>
            ))}
          </section>
        ))}
      </div>
    </aside>
  );
}
```

Dragging arrives in Phase 2; `draggable` is deliberately absent so nothing suggests an
affordance that does not work yet.

- [ ] **Step 6: Wire it into `App.tsx`**

Add registry loading alongside the existing health poll, and swap the left placeholder:

```tsx
  const [steps, setSteps] = useState<StepDef[]>([]);
  const [phases, setPhases] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const registry = await api.getRegistry();
        setSteps(registry.steps);
        setPhases(registry.phases);
      } catch (e) {
        setLoadError(String(e));
      }
    })();
  }, []);
```

Replace the left `<aside className="rail">` placeholder with `<Palette steps={steps} phases={phases} />`,
and surface `loadError` in the right rail so a broken registry is visible rather than an
empty palette.

- [ ] **Step 7: Add the styles**

Append to `app.css` — tokens only:

```css
.rail { display: flex; flex-direction: column; }
.rail__search { padding: .625rem; border-bottom: 1px solid var(--hair-soft); }
.rail__search input {
  width: 100%; background: var(--sunk); border: 1px solid var(--hair);
  border-radius: var(--r-sm); padding: .4rem .55rem; font-size: 12.5px;
}
.rail__search input::placeholder { color: var(--text-faint); }
.rail__list { overflow-y: auto; padding: .5rem .625rem 1rem; flex: 1; min-height: 0; }
.rail__empty { font-size: 12.5px; color: var(--text-faint); padding: .5rem 0; margin: 0; }

.phase {
  display: flex; align-items: center; gap: .45rem;
  font-family: var(--mono); font-size: 10px; letter-spacing: .12em;
  text-transform: uppercase; color: var(--text-faint);
  margin: 1rem 0 .4rem;
}
.rail__list section:first-child .phase { margin-top: .25rem; }
.phase::after { content: ""; flex: 1; height: 1px; background: var(--hair-soft); }

.chip-step {
  display: flex; align-items: center; gap: .5rem;
  background: var(--raised); border: 1px solid var(--hair);
  border-radius: var(--r-md); padding: .45rem .55rem;
  margin-bottom: .3rem; font-size: 12.5px; font-weight: 500;
  transition: border-color var(--t);
}
.chip-step:hover { border-color: var(--cyan); }
.chip-step--off { opacity: .42; border-style: dashed; }
.chip-step--off:hover { border-color: var(--hair); }
.chip-step__meta { margin-left: auto; display: flex; gap: .2rem; flex: none; }

.tag {
  font-family: var(--mono); font-size: 9px; font-weight: 600;
  letter-spacing: .04em; text-transform: uppercase;
  padding: .1rem .3rem; border-radius: 4px;
  border: 1px solid currentColor; opacity: .85;
}
.tag--ask  { color: var(--st-input); }
.tag--soon { color: var(--st-blocked); }
```

- [ ] **Step 8: Run, build, commit**

```bash
cd studio/frontend && npm test && npm run build
git add studio/frontend
git commit -m "feat(studio): searchable step palette from the live registry"
```

---

### Task 6: Run the demo

- [ ] **Step 1: Both processes up**

```bash
cd studio/backend && implr-studio --workspace /tmp/studio-probe    # terminal 1
cd studio/frontend && npm run dev                                   # terminal 2
```

- [ ] **Step 2: Confirm the palette**

- Six phase headings, in registry order — not alphabetical.
- Nine steps. `Testing` and `Security Checks` **dashed**, with a `soon` tag.
- `Architecture Brief`, `Change Request` and `Specification / Planning` carry an `asks` tag.
- Hover `Security Checks`: the tooltip ends *"(not implemented yet - the skill does not exist)"*.

- [ ] **Step 3: Confirm search**

Type `knowledge` → only **Document Ingestion**. Clear it → all nine return. Type `zzz` →
*"No step matches 'zzz'."*

- [ ] **Step 4: Confirm it is real data**

```bash
curl -s http://127.0.0.1:8765/api/registry | python -c "
import json, sys
d = json.load(sys.stdin)
print('steps :', len(d['steps']))
print('phases:', d['phases'])
print('tiers :', d['tiers'])
ex = next(s for s in d['steps'] if s['id'] == 'dev-executor')
print('executor agents:', [a['name'] for a in ex['agents']])
print('--task takes a value:',
      next(a for a in ex['args_allowed'] if a['flag'] == '--task')['takes_value'])
"
```

Expected: 9, the six phases, three tiers, the three executor agents, and `True`. The payload
already carries everything phases 4–7 will render.

- [ ] **Step 5: Confirm a broken registry fails loudly**

```bash
mv /tmp/studio-probe/docs/implr/schemas/step-registry.json /tmp/hold.json
cd studio/backend && implr-studio --workspace /tmp/studio-probe; echo "exit: $?"
mv /tmp/hold.json /tmp/studio-probe/docs/implr/schemas/step-registry.json
```

Expected: exit `2` with a message naming the registry and a hint to re-run the installer —
not a traceback, and not a server that starts with an empty palette.

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes, including the four
      shipped-registry tests that read the real files.
- [ ] `npm test` and `npm run build` pass.
- [ ] `python -m pytest tests/` at the repo root passes — the 68 pre-existing tests plus the
      registry check.
- [ ] `PYTHONPATH=scripts python -m implr_validate --repo --root .` exits `0` with exactly
      two `info:` lines.
- [ ] Every agent named in the shipped registry has a `.claude/agents/<name>.md`, and every
      `produces_artefact` names a real artefact type — asserted against the real repo.
- [ ] Every flag the registry offers appears in its skill's `SKILL.md`.
- [ ] A bare-string `args_allowed` entry is rejected by both the loader and the validator.
- [ ] No frontend file contains a hardcoded step, phase, flag or host.
- [ ] `implr-studio` exits `2` with an actionable message when the registry is missing.
- [ ] **The demo:** nine steps in six phase groups, two dashed with tooltips, search filters
      by label and by description, and an empty query restores all nine.

---

## What the next phase gets

A real catalogue, served whole, rendered in part. Phase 2 adds `pipeline.py`,
`GET`/`PUT /api/pipeline`, the React Flow canvas and drag-and-drop — so its demo is
*"drag two steps, connect them, Save, and `pipeline.yaml` appears on disk"*.
