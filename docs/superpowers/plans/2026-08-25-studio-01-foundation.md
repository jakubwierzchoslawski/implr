# implr Studio — Plan 1: Foundation (Registry, Pipeline Config, Gates)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-data foundation of implr Studio — the step registry, the `pipeline.yaml` config format, DAG validation, and gate validation/evaluation — with no runtime, no HTTP, and no LLM involvement.

**Architecture:** A new Python package `studio/backend/implr_studio/`. It reuses the existing `scripts/implr_validate` package (frontmatter parsing and the authoritative state machines) through a single bridge module, so artefact-status semantics have exactly one source of truth. Everything in this plan is synchronous, filesystem-only, and unit-testable.

**Tech Stack:** Python 3.11+, PyYAML (studio only), pytest. The existing `implr_validate` package stays standard-library-only — this plan must not add dependencies to it.

**Spec:** `docs/superpowers/specs/2026-08-25-implr-studio-design.md`

**Runtime verification:** `docs/RUNTIME.md` — how to prove this plan actually runs, not just that its suite passes.

## Global Constraints

- `scripts/implr_validate` remains **standard library only**. Never add an import of `yaml` or any third-party package to it.
- Artefact statuses and artefact types are never hardcoded. They are read from `scaffold/schemas/status-vocabulary.json` and `scaffold/schemas/frontmatter-rules.json` via `implr_validate.contracts.load_contracts`.
- Frontmatter is parsed only via `implr_validate.frontmatter.parse_frontmatter`. Do not write a second parser.
- Path globs from `frontmatter-rules.json` use `/` separators and must be converted with `.replace("/", os.sep)` before use, matching `implr_validate.checks.check_workspace`.
- An artefact gate with `quantifier: all` over an **empty match set evaluates False**, never vacuously True.
- Python target: 3.11+. The repo's current interpreter is 3.14.3.

---

## File Structure

| File | Responsibility |
|---|---|
| `scaffold/schemas/step-registry.json` | Declarative catalogue of pipeline steps. Installed to target projects by the existing `install.sh` rule that copies `schemas/*.json`. |
| `studio/backend/pyproject.toml` | Package metadata and dependencies for the studio backend. |
| `studio/backend/implr_studio/__init__.py` | Package marker. |
| `studio/backend/implr_studio/implr_bridge.py` | The **only** module that knows where `scripts/implr_validate` lives. Re-exports `parse_frontmatter`, `load_contracts`, `FrontmatterError`. |
| `studio/backend/implr_studio/registry.py` | Loads and validates `step-registry.json`; determines per-step availability. |
| `studio/backend/implr_studio/pipeline.py` | `pipeline.yaml` load/save, dataclasses, DAG validation. |
| `studio/backend/implr_studio/gates.py` | Gate validation (save-time) and gate evaluation (runtime). |
| `studio/backend/tests/conftest.py` | Fixtures building throwaway workspace trees. |
| `studio/backend/tests/test_registry.py` | Registry tests. |
| `studio/backend/tests/test_pipeline.py` | Config and DAG tests. |
| `studio/backend/tests/test_gates.py` | Gate validation and evaluation tests. |
| `scripts/implr_validate/checks.py` | **Modified** — gains `check_step_registry`. Stays stdlib-only. |
| `scripts/implr_validate/cli.py` | **Modified** — calls the new check; exit code becomes level-aware. |
| `tests/test_step_registry_check.py` | Registry validation inside the existing validator suite. |

---

### Task 0: Ignore the build artefacts these plans create

**Files:**
- Modify: `.gitignore`
- Modify: `scaffold/schemas/frontmatter-rules.json` (`repo_prose_checks.exempt_paths`)

The six plans introduce `pip install -e` (which writes `*.egg-info/`), `npm install` (which
writes `studio/frontend/node_modules/`), `npm run build` (`dist/`), pytest caches, and a
SQLite database under `docs/implr/.studio/`. The current `.gitignore` covers none of them,
and the repo already carries untracked `tests/__pycache__/*.pyc` for exactly that reason.
Plan 5 Task 1 runs `npm install` and then `git add studio/frontend` — without this task,
that commits `node_modules`.

Do this first. It costs a minute now and is a painful history rewrite later.

- [ ] **Step 1: Extend `.gitignore`**

Append:

```gitignore
# python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
# node
node_modules/
studio/frontend/dist/
# studio run state (per-workspace, never committed)
docs/implr/.studio/
```

- [ ] **Step 2: Exempt node_modules from the prose checks**

`check_repo_prose` walks **every** `.md`, `.yaml` and `.yml` file under the repo root
looking for `kb_supported_formats` drift. After `npm install` that means crawling tens of
thousands of files on every `implr-validate --repo`. Add to
`repo_prose_checks.exempt_paths` in `scaffold/schemas/frontmatter-rules.json` — two new
entries in the existing array, alongside `"docs/superpowers/"`:

```text
    "studio/frontend/node_modules/",
    "studio/frontend/dist/",
```

- [ ] **Step 3: Verify**

Run: `python -m implr_validate --repo --root .`
Expected: exit `0`, and noticeably fast even with `node_modules` present.

Run: `git status --porcelain`
Expected: no `__pycache__`, `node_modules`, `dist` or `.egg-info` entries.

- [ ] **Step 4: Commit**

```bash
git add .gitignore scaffold/schemas/frontmatter-rules.json
git commit -m "chore: ignore build artefacts introduced by implr Studio"
```

---

### Task 1: Package scaffolding and the implr_validate bridge

**Files:**
- Create: `studio/backend/pyproject.toml`
- Create: `studio/backend/implr_studio/__init__.py`
- Create: `studio/backend/implr_studio/implr_bridge.py`
- Test: `studio/backend/tests/test_bridge.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `implr_bridge.repo_root() -> pathlib.Path` — the implr repo root.
  - `implr_bridge.parse_frontmatter(text: str) -> dict`
  - `implr_bridge.FrontmatterError` (exception class)
  - `implr_bridge.load_contracts(schema_dir: str) -> Contracts`
  - `implr_bridge.resolve_schema_dir(root: pathlib.Path) -> pathlib.Path` — prefers `<root>/scaffold/schemas`, falls back to `<root>/docs/implr/schemas`.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_bridge.py`:

```python
from pathlib import Path

from implr_studio import implr_bridge


def test_repo_root_contains_scripts_implr_validate():
    root = implr_bridge.repo_root()
    assert (root / "scripts" / "implr_validate" / "__init__.py").is_file()


def test_parse_frontmatter_is_the_implr_validate_parser():
    text = "---\nreq_id: REQ-F-001\nstatus: approved\n---\nbody\n"
    assert implr_bridge.parse_frontmatter(text) == {
        "req_id": "REQ-F-001",
        "status": "approved",
    }


def test_load_contracts_exposes_requirement_states():
    schema_dir = implr_bridge.resolve_schema_dir(implr_bridge.repo_root())
    contracts = implr_bridge.load_contracts(str(schema_dir))
    assert contracts.states_for("requirement") == {
        "draft", "under-review", "approved", "rejected", "superseded",
    }


def test_resolve_schema_dir_prefers_scaffold(tmp_path: Path):
    (tmp_path / "scaffold" / "schemas").mkdir(parents=True)
    (tmp_path / "docs" / "implr" / "schemas").mkdir(parents=True)
    assert implr_bridge.resolve_schema_dir(tmp_path) == tmp_path / "scaffold" / "schemas"


def test_resolve_schema_dir_falls_back_to_installed_workspace(tmp_path: Path):
    (tmp_path / "docs" / "implr" / "schemas").mkdir(parents=True)
    assert implr_bridge.resolve_schema_dir(tmp_path) == tmp_path / "docs" / "implr" / "schemas"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_studio'`

- [ ] **Step 3: Create the package files**

Create `studio/backend/pyproject.toml`:

```toml
[project]
name = "implr-studio"
version = "0.1.0"
description = "Visual SDLC pipeline builder and orchestrator for implr"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["implr_studio*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `studio/backend/implr_studio/__init__.py` (empty file).

Create `studio/backend/implr_studio/implr_bridge.py`:

```python
"""The single point of coupling between implr Studio and scripts/implr_validate.

No other studio module may import from implr_validate directly. Keeping the
coupling in one file means a change to implr_validate's layout is a one-file fix.
"""
import sys
from pathlib import Path


def repo_root() -> Path:
    """The implr repository root.

    implr_bridge.py lives at <root>/studio/backend/implr_studio/implr_bridge.py,
    so the root is four parents up.
    """
    return Path(__file__).resolve().parents[3]


def _ensure_scripts_on_path() -> None:
    scripts = str(repo_root() / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


_ensure_scripts_on_path()

# Re-exported so the rest of the studio package never imports implr_validate itself.
from implr_validate.contracts import load_contracts          # noqa: E402
from implr_validate.frontmatter import (                     # noqa: E402
    FrontmatterError,
    parse_frontmatter,
)

__all__ = [
    "repo_root",
    "resolve_schema_dir",
    "load_contracts",
    "parse_frontmatter",
    "FrontmatterError",
]


def resolve_schema_dir(root: Path) -> Path:
    """Mirror implr_validate.cli._resolve_schema_dir.

    A plugin-source checkout has scaffold/schemas; an installed workspace has
    docs/implr/schemas.
    """
    candidate = Path(root) / "scaffold" / "schemas"
    if candidate.is_dir():
        return candidate
    return Path(root) / "docs" / "implr" / "schemas"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pip install -e ".[dev]" && python -m pytest tests/test_bridge.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/pyproject.toml studio/backend/implr_studio studio/backend/tests
git commit -m "feat(studio): package scaffolding and implr_validate bridge"
```

---

### Task 2: Step registry file and loader

**Files:**
- Create: `scaffold/schemas/step-registry.json`
- Create: `studio/backend/implr_studio/registry.py`
- Test: `studio/backend/tests/test_registry.py`

**Interfaces:**
- Consumes: `implr_bridge.repo_root`, `implr_bridge.resolve_schema_dir` from Task 1.
- Produces:
  - `registry.ArgSpec` — frozen dataclass: `flag: str`, `takes_value: bool`, `value_pattern: str | None`, `note: str`.
  - `registry.AgentRef` — frozen dataclass: `name: str`, `fan_out: str`.
  - `registry.IOPath` — frozen dataclass: `path: str`, `note: str`.
  - `registry.Step` — frozen dataclass: `id`, `label`, `phase`, `skill`, `args_allowed: tuple[ArgSpec, ...]`, `args_default: tuple[str, ...]`, `interactive: bool`, `agents: tuple[AgentRef, ...]`, `consumes: tuple[IOPath, ...]`, `produces: tuple[IOPath, ...]`, `produces_artefact: str | None`, `description: str`, `available: bool`.
  - `Step.arg(flag) -> ArgSpec | None` and `Step.flags -> tuple[str, ...]` — convenience for validation, so callers never re-scan `args_allowed`.
  - `registry.Registry` — has `.steps: dict[str, Step]` and `.get(step_id) -> Step | None`.
  - `registry.load_registry(schema_dir: Path, skills_dir: Path) -> Registry`
  - `registry.RegistryError` (exception).
  - `registry.PHASES: tuple[str, ...]` = `("discovery", "design", "requirements", "planning", "build", "verify")`.
  - `registry.TIERS: tuple[str, ...]` = `("haiku", "sonnet", "opus")`.

`args_allowed` entries are **objects, not strings** — several implr flags take a value
(`--file`, `--task`, `--domain`), and a flat whitelist makes those flags selectable and
inert. A `takes_value: true` spec must carry a `value_pattern`; the loader rejects one that
does not, because an unvalidated value is the one place a path could reach an argv vector
unchecked.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_registry.py`:

```python
import json
from pathlib import Path

import pytest

from implr_studio import registry


def _write_registry(schema_dir: Path, steps: list[dict]) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "step-registry.json").write_text(
        json.dumps({"steps": steps}), encoding="utf-8"
    )


def _make_skill(skills_dir: Path, name: str) -> None:
    (skills_dir / name).mkdir(parents=True, exist_ok=True)
    (skills_dir / name / "SKILL.md").write_text("---\nname: %s\n---\n" % name, encoding="utf-8")


BASE_STEP = {
    "id": "doc-ingest",
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
    _write_registry(schema_dir, [BASE_STEP])
    _make_skill(skills_dir, "doc-ingest")

    reg = registry.load_registry(schema_dir, skills_dir)

    step = reg.get("doc-ingest")
    assert step.label == "Document Ingestion"
    assert step.phase == "discovery"
    assert step.flags == ("--registry-only", "--file")
    assert step.interactive is False


def test_arg_specs_carry_value_metadata(tmp_path: Path):
    """A flat flag whitelist cannot express --file <path>. This is why args are objects."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write_registry(schema_dir, [BASE_STEP])
    _make_skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.arg("--registry-only").takes_value is False
    assert step.arg("--file").takes_value is True
    assert step.arg("--file").value_pattern == "^[A-Za-z0-9._/-]{1,200}$"
    assert step.arg("--nope") is None


def test_value_taking_arg_without_a_pattern_rejected(tmp_path: Path):
    """An unvalidated value is the one way a path reaches an argv vector unchecked."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    bad = dict(BASE_STEP, args_allowed=[{"flag": "--file", "takes_value": True, "note": ""}])
    _write_registry(schema_dir, [bad])
    _make_skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="--file.*requires a value_pattern"):
        registry.load_registry(schema_dir, skills_dir)


def test_invalid_value_pattern_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    bad = dict(BASE_STEP, args_allowed=[
        {"flag": "--file", "takes_value": True, "value_pattern": "([unclosed", "note": ""},
    ])
    _write_registry(schema_dir, [bad])
    _make_skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="not a valid regex"):
        registry.load_registry(schema_dir, skills_dir)


def test_agents_are_loaded_in_dispatch_order(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    step = dict(BASE_STEP, agents=[
        {"name": "arch-excerpter", "fan_out": "1 per plan"},
        {"name": "plan-runner", "fan_out": "1 per plan, cap 5"},
        {"name": "task-executor", "fan_out": "1 per task"},
    ])
    _write_registry(schema_dir, [step])
    _make_skill(skills_dir, "doc-ingest")

    loaded = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert [a.name for a in loaded.agents] == ["arch-excerpter", "plan-runner", "task-executor"]
    assert loaded.agents[1].fan_out == "1 per plan, cap 5"


def test_produces_artefact_must_be_null_or_a_string(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write_registry(schema_dir, [dict(BASE_STEP, produces_artefact="plan")])
    _make_skill(skills_dir, "doc-ingest")

    assert registry.load_registry(schema_dir, skills_dir).get("doc-ingest").produces_artefact == "plan"


def test_duplicate_flag_in_args_allowed_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    bad = dict(BASE_STEP, args_allowed=[
        {"flag": "--dry-run", "takes_value": False, "note": ""},
        {"flag": "--dry-run", "takes_value": False, "note": ""},
    ])
    _write_registry(schema_dir, [bad])
    _make_skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="duplicate flag"):
        registry.load_registry(schema_dir, skills_dir)


def test_step_is_available_when_skill_exists(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write_registry(schema_dir, [BASE_STEP])
    _make_skill(skills_dir, "doc-ingest")

    assert registry.load_registry(schema_dir, skills_dir).get("doc-ingest").available is True


def test_step_is_unavailable_when_skill_missing(tmp_path: Path):
    """A planned step is not an error - it renders greyed-out in the palette."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    planned = dict(BASE_STEP, id="sec-review", skill="sec-review", phase="verify")
    _write_registry(schema_dir, [planned])
    skills_dir.mkdir(parents=True)

    reg = registry.load_registry(schema_dir, skills_dir)

    assert reg.get("sec-review").available is False


def test_duplicate_step_ids_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write_registry(schema_dir, [BASE_STEP, dict(BASE_STEP)])
    _make_skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="duplicate step id: doc-ingest"):
        registry.load_registry(schema_dir, skills_dir)


def test_unknown_phase_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write_registry(schema_dir, [dict(BASE_STEP, phase="wibble")])
    _make_skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="unknown phase 'wibble'"):
        registry.load_registry(schema_dir, skills_dir)


def test_missing_required_field_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    incomplete = {k: v for k, v in BASE_STEP.items() if k != "skill"}
    _write_registry(schema_dir, [incomplete])
    skills_dir.mkdir(parents=True)

    with pytest.raises(registry.RegistryError, match="missing required field: skill"):
        registry.load_registry(schema_dir, skills_dir)


def test_args_default_must_be_subset_of_args_allowed(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write_registry(schema_dir, [dict(BASE_STEP, args_default=["--nope"])])
    _make_skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="args_default entry '--nope' not in args_allowed"):
        registry.load_registry(schema_dir, skills_dir)


def test_args_default_cannot_name_a_value_taking_flag(tmp_path: Path):
    """A default cannot supply a value, so it must not select a flag that needs one."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write_registry(schema_dir, [dict(BASE_STEP, args_default=["--file"])])
    _make_skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="args_default entry '--file' takes a value"):
        registry.load_registry(schema_dir, skills_dir)


def test_shipped_registry_is_valid():
    """The real scaffold/schemas/step-registry.json must load against the real skills/."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    assert reg.get("doc-ingest").available is True
    assert reg.get("dev-executor").available is True
    assert reg.get("sec-review").available is False


def test_shipped_registry_agents_match_the_real_agent_definitions():
    """Every agent a step claims to dispatch must exist in .claude/agents/."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    for step in reg.steps.values():
        for agent in step.agents:
            assert (root / ".claude" / "agents" / ("%s.md" % agent.name)).is_file(), (
                "step %s claims agent %s, which has no definition" % (step.id, agent.name)
            )


def test_shipped_registry_artefacts_are_real_types():
    """produces_artefact must name a frontmatter-rules.json artefact type."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    schema_dir = implr_bridge.resolve_schema_dir(root)
    contracts = implr_bridge.load_contracts(str(schema_dir))
    reg = registry.load_registry(root / "scaffold" / "schemas", root / "skills")

    for step in reg.steps.values():
        if step.produces_artefact is not None:
            assert step.produces_artefact in contracts.artefact_types
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'registry'`

- [ ] **Step 3: Write the registry file**

Create `scaffold/schemas/step-registry.json`:

Two conventions in this file, both load-bearing:

- `PATH` is the value pattern for anything filesystem-shaped:
  `^[A-Za-z0-9._/-]{1,200}$`. It admits no whitespace, no quotes, no `$`, no backticks and
  no `..` traversal beyond what the backend's own path resolution rejects.
- Every `agents[].name` must match a file in `.claude/agents/` and a key in
  `implr.config.yaml`'s `agents:` block. The tests above enforce the first; drift in the
  second shows up as a step whose tier selector has no default.

```json
{
  "_comment": "Catalogue of pipeline steps for implr Studio. Adding a step here makes it appear in the palette and its agents in the step configurator; no code change is required. A step whose skills/<skill>/SKILL.md does not exist is rendered unavailable, not rejected.",
  "steps": [
    {
      "id": "doc-ingest",
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

- [ ] **Step 4: Write the loader**

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

_REQUIRED_FIELDS = (
    "id", "label", "phase", "skill",
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
        if entry["phase"] not in PHASES:
            raise RegistryError(
                "step %s: unknown phase %r (legal: %s)" % (step_id, entry["phase"], list(PHASES))
            )

        specs = _arg_specs(step_id, entry["args_allowed"])
        by_flag = {s.flag: s for s in specs}
        for arg in entry["args_default"]:
            spec = by_flag.get(arg)
            if spec is None:
                raise RegistryError(
                    "step %s: args_default entry %r not in args_allowed" % (step_id, arg)
                )
            if spec.takes_value:
                raise RegistryError(
                    "step %s: args_default entry %r takes a value, so it cannot be a default"
                    % (step_id, arg)
                )

        artefact = entry["produces_artefact"]
        if artefact is not None and not isinstance(artefact, str):
            raise RegistryError(
                "step %s: produces_artefact must be a string or null" % step_id
            )

        skill_md = Path(skills_dir) / entry["skill"] / "SKILL.md"
        steps[step_id] = Step(
            id=step_id,
            label=entry["label"],
            phase=entry["phase"],
            skill=entry["skill"],
            args_allowed=specs,
            args_default=tuple(entry["args_default"]),
            interactive=bool(entry["interactive"]),
            agents=tuple(
                AgentRef(name=a["name"], fan_out=a.get("fan_out", ""))
                for a in entry["agents"]
            ),
            consumes=tuple(
                IOPath(path=c["path"], note=c.get("note", "")) for c in entry["consumes"]
            ),
            produces=tuple(
                IOPath(path=p["path"], note=p.get("note", "")) for p in entry["produces"]
            ),
            produces_artefact=artefact,
            description=entry["description"],
            available=skill_md.is_file(),
        )
    return Registry(steps=steps)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_registry.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add scaffold/schemas/step-registry.json studio/backend/implr_studio/registry.py studio/backend/tests/test_registry.py
git commit -m "feat(studio): step registry file and loader"
```

---

### Task 3: Pipeline config load, save, and round-trip

**Files:**
- Create: `studio/backend/implr_studio/pipeline.py`
- Test: `studio/backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `registry.Registry`, `registry.Step` from Task 2.
- Produces:
  - `pipeline.Gate` — frozen dataclass: `type: str`, `artefact: str | None`, `quantifier: str | None`, `require: dict[str, str] | None`.
  - `pipeline.Node` — frozen dataclass: `id: str`, `step: str`, `args: tuple[str, ...]`, `arg_values: dict[str, str]`, `models: dict[str, str]`, `position: dict[str, float]`.

`arg_values` maps a selected flag to its value; `models` maps an agent name to a tier.
Both are sparse and both default to empty, so a `pipeline.yaml` written before these fields
existed loads unchanged — an absent `models` entry means "inherit the project default from
`implr.config.yaml`", which is exactly the old behaviour.
  - `pipeline.Edge` — frozen dataclass: `source: str`, `target: str`, `gate: Gate`.
  - `pipeline.Pipeline` — frozen dataclass: `version: int`, `nodes: tuple[Node, ...]`, `edges: tuple[Edge, ...]`.
  - `pipeline.load_pipeline(path: Path) -> Pipeline`
  - `pipeline.save_pipeline(path: Path, p: Pipeline) -> None`
  - `pipeline.pipeline_from_dict(data: dict) -> Pipeline`
  - `pipeline.pipeline_to_dict(p: Pipeline) -> dict`
  - `pipeline.PipelineError` (exception).

Note: `Edge` uses `source`/`target` rather than `from`/`to` because `from` is a Python keyword. The YAML keys remain `from`/`to`; conversion happens in `pipeline_from_dict` / `pipeline_to_dict`.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_pipeline.py`:

```python
from pathlib import Path

import pytest
import yaml

from implr_studio import pipeline

VALID_YAML = """\
version: 1
nodes:
  - id: ingest
    step: doc-ingest
    args: []
    position: {x: 80, y: 120}
  - id: reqs
    step: ba-requirements-gen
    args: []
    position: {x: 320, y: 120}
edges:
  - from: ingest
    to: reqs
    gate:
      type: artifact
      artefact: requirement
      quantifier: all
      require: {status: approved}
"""


def test_load_parses_nodes_and_edges(tmp_path: Path):
    path = tmp_path / "pipeline.yaml"
    path.write_text(VALID_YAML, encoding="utf-8")

    p = pipeline.load_pipeline(path)

    assert p.version == 1
    assert [n.id for n in p.nodes] == ["ingest", "reqs"]
    assert p.nodes[0].step == "doc-ingest"
    assert p.edges[0].source == "ingest"
    assert p.edges[0].target == "reqs"
    assert p.edges[0].gate.type == "artifact"
    assert p.edges[0].gate.require == {"status": "approved"}


def test_gate_defaults_to_none_type_when_omitted(tmp_path: Path):
    path = tmp_path / "pipeline.yaml"
    path.write_text(
        "version: 1\n"
        "nodes:\n"
        "  - {id: a, step: doc-ingest, args: [], position: {x: 0, y: 0}}\n"
        "  - {id: b, step: arch-gen, args: [], position: {x: 1, y: 0}}\n"
        "edges:\n"
        "  - {from: a, to: b}\n",
        encoding="utf-8",
    )

    p = pipeline.load_pipeline(path)

    assert p.edges[0].gate.type == "none"
    assert p.edges[0].gate.artefact is None


def test_round_trip_preserves_structure(tmp_path: Path):
    src = tmp_path / "in.yaml"
    src.write_text(VALID_YAML, encoding="utf-8")
    loaded = pipeline.load_pipeline(src)

    out = tmp_path / "out.yaml"
    pipeline.save_pipeline(out, loaded)

    assert pipeline.load_pipeline(out) == loaded


def test_saved_yaml_uses_from_and_to_keys(tmp_path: Path):
    """The on-disk format stays human-editable; source/target are Python-side only."""
    src = tmp_path / "in.yaml"
    src.write_text(VALID_YAML, encoding="utf-8")
    out = tmp_path / "out.yaml"

    pipeline.save_pipeline(out, pipeline.load_pipeline(src))

    raw = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert raw["edges"][0]["from"] == "ingest"
    assert raw["edges"][0]["to"] == "reqs"
    assert "source" not in raw["edges"][0]


def test_unsupported_version_rejected(tmp_path: Path):
    path = tmp_path / "pipeline.yaml"
    path.write_text("version: 99\nnodes: []\nedges: []\n", encoding="utf-8")

    with pytest.raises(pipeline.PipelineError, match="unsupported pipeline version: 99"):
        pipeline.load_pipeline(path)


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(pipeline.PipelineError, match="pipeline config not found"):
        pipeline.load_pipeline(tmp_path / "nope.yaml")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'pipeline'`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/pipeline.py`:

```python
"""Load, validate, and save docs/implr/config/pipeline.yaml."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SUPPORTED_VERSION = 1
GATE_TYPES = ("none", "manual", "artifact", "artifact+manual")
QUANTIFIERS = ("all", "any")


class PipelineError(Exception):
    pass


@dataclass(frozen=True)
class Gate:
    type: str = "none"
    artefact: str | None = None
    quantifier: str | None = None
    require: dict | None = None


@dataclass(frozen=True)
class Node:
    id: str
    step: str
    args: tuple[str, ...] = ()
    arg_values: dict = field(default_factory=dict)
    models: dict = field(default_factory=dict)
    position: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    gate: Gate = Gate()


@dataclass(frozen=True)
class Pipeline:
    version: int
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


def _gate_from_dict(data: dict | None) -> Gate:
    if not data:
        return Gate()
    gate_type = data.get("type", "none")
    if gate_type not in GATE_TYPES:
        raise PipelineError(
            "unknown gate type %r (legal: %s)" % (gate_type, list(GATE_TYPES))
        )
    quantifier = data.get("quantifier")
    if quantifier is not None and quantifier not in QUANTIFIERS:
        raise PipelineError(
            "unknown quantifier %r (legal: %s)" % (quantifier, list(QUANTIFIERS))
        )
    return Gate(
        type=gate_type,
        artefact=data.get("artefact"),
        quantifier=quantifier,
        require=dict(data["require"]) if data.get("require") else None,
    )


def _gate_to_dict(gate: Gate) -> dict:
    out: dict = {"type": gate.type}
    if gate.artefact is not None:
        out["artefact"] = gate.artefact
    if gate.quantifier is not None:
        out["quantifier"] = gate.quantifier
    if gate.require is not None:
        out["require"] = dict(gate.require)
    return out


def pipeline_from_dict(data: dict) -> Pipeline:
    version = data.get("version", SUPPORTED_VERSION)
    if version != SUPPORTED_VERSION:
        raise PipelineError("unsupported pipeline version: %s" % version)

    nodes = []
    for entry in data.get("nodes") or []:
        for required in ("id", "step"):
            if required not in entry:
                raise PipelineError("node missing required field: %s" % required)
        nodes.append(Node(
            id=entry["id"],
            step=entry["step"],
            args=tuple(entry.get("args") or ()),
            arg_values=dict(entry.get("arg_values") or {}),
            models=dict(entry.get("models") or {}),
            position=dict(entry.get("position") or {}),
        ))

    edges = []
    for entry in data.get("edges") or []:
        for required in ("from", "to"):
            if required not in entry:
                raise PipelineError("edge missing required field: %s" % required)
        edges.append(Edge(
            source=entry["from"],
            target=entry["to"],
            gate=_gate_from_dict(entry.get("gate")),
        ))

    return Pipeline(version=version, nodes=tuple(nodes), edges=tuple(edges))


def _node_to_dict(n: Node) -> dict:
    """Sparse on purpose: a node with no values or overrides serialises exactly as
    it did before those fields existed, so diffs stay readable."""
    out: dict = {"id": n.id, "step": n.step, "args": list(n.args)}
    if n.arg_values:
        out["arg_values"] = dict(n.arg_values)
    if n.models:
        out["models"] = dict(n.models)
    out["position"] = dict(n.position)
    return out


def pipeline_to_dict(p: Pipeline) -> dict:
    return {
        "version": p.version,
        "nodes": [_node_to_dict(n) for n in p.nodes],
        "edges": [
            {"from": e.source, "to": e.target, "gate": _gate_to_dict(e.gate)}
            for e in p.edges
        ],
    }


def load_pipeline(path: Path) -> Pipeline:
    path = Path(path)
    if not path.is_file():
        raise PipelineError("pipeline config not found: %s" % path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return pipeline_from_dict(data)


def save_pipeline(path: Path, p: Pipeline) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(pipeline_to_dict(p), f, sort_keys=False, default_flow_style=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_pipeline.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add studio/backend/implr_studio/pipeline.py studio/backend/tests/test_pipeline.py
git commit -m "feat(studio): pipeline.yaml load, save, and round-trip"
```

---

### Task 4: DAG validation

**Files:**
- Modify: `studio/backend/implr_studio/pipeline.py` (append `validate_pipeline` and `Finding`)
- Test: `studio/backend/tests/test_pipeline_validation.py`

**Interfaces:**
- Consumes: `pipeline.Pipeline`, `pipeline.Node`, `pipeline.Edge` from Task 3; `registry.Registry` from Task 2.
- Produces:
  - `pipeline.Finding` — frozen dataclass: `code: str`, `message: str`, `node_id: str | None = None`.
  - `pipeline.validate_pipeline(p: Pipeline, reg) -> list[Finding]` — empty list means valid. The `reg` parameter is a `registry.Registry`, left unannotated so that `pipeline.py` needs no import of `registry.py` purely for a type hint. Duck-typed on `.get(step_id)`, which also makes the validator trivial to test with a stub.

Finding codes used by later plans and the frontend: `unknown-step`, `disallowed-arg`,
`missing-arg-value`, `bad-arg-value`, `orphan-arg-value`, `unknown-agent`, `illegal-tier`,
`duplicate-node-id`, `unknown-edge-node`, `cycle`, `unreachable-node`, `no-root`.

The five arg/model codes are what make the configurator honest. Without them the UI can
offer a value field whose contents nothing checks, and a tier selector that can name an
agent the step never dispatches.

Availability is deliberately **not** checked here — a pipeline may reference a registered-but-unimplemented step at design time. Run-start enforcement lives in Plan 3.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_pipeline_validation.py`:

```python
import json
from pathlib import Path

import pytest

from implr_studio import pipeline, registry


@pytest.fixture
def reg(tmp_path: Path) -> registry.Registry:
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    schema_dir.mkdir(parents=True)
    steps = []
    for step_id, skill in (("doc-ingest", "doc-ingest"), ("arch-gen", "arch-gen"), ("sec-review", "sec-review")):
        steps.append({
            "id": step_id, "label": step_id, "phase": "discovery", "skill": skill,
            "args_allowed": [
                {"flag": "--dry-run", "takes_value": False, "note": ""},
                {"flag": "--file", "takes_value": True,
                 "value_pattern": "^[A-Za-z0-9._/-]{1,200}$", "note": ""},
            ],
            "args_default": [],
            "interactive": False,
            "agents": [{"name": "plan-worker", "fan_out": "1"}],
            "consumes": [], "produces": [], "produces_artefact": None,
            "description": "",
        })
    (schema_dir / "step-registry.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    for skill in ("doc-ingest", "arch-gen"):          # sec-review intentionally missing
        (skills_dir / skill).mkdir(parents=True)
        (skills_dir / skill / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return registry.load_registry(schema_dir, skills_dir)


def _p(nodes, edges, version=1) -> pipeline.Pipeline:
    return pipeline.pipeline_from_dict({"version": version, "nodes": nodes, "edges": edges})


def _codes(findings) -> list[str]:
    return [f.code for f in findings]


def test_valid_pipeline_has_no_findings(reg):
    p = _p(
        [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
        [{"from": "a", "to": "b"}],
    )
    assert pipeline.validate_pipeline(p, reg) == []


def test_single_node_pipeline_is_valid(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}], [])
    assert pipeline.validate_pipeline(p, reg) == []


def test_unknown_step_rejected(reg):
    p = _p([{"id": "a", "step": "does-not-exist"}], [])
    findings = pipeline.validate_pipeline(p, reg)
    assert _codes(findings) == ["unknown-step"]
    assert "does-not-exist" in findings[0].message


def test_registered_but_unavailable_step_is_accepted(reg):
    """Designing ahead of implementation is allowed; run start enforces availability."""
    p = _p([{"id": "a", "step": "sec-review"}], [])
    assert pipeline.validate_pipeline(p, reg) == []


def test_disallowed_arg_rejected(reg):
    p = _p([{"id": "a", "step": "doc-ingest", "args": ["--wat"]}], [])
    findings = pipeline.validate_pipeline(p, reg)
    assert _codes(findings) == ["disallowed-arg"]
    assert "--wat" in findings[0].message


# --- arg values (the configurator's value fields) ---------------------------

def test_value_taking_arg_without_a_value_rejected(reg):
    """Selecting --file and supplying nothing is the G1 gap; it must not save."""
    p = _p([{"id": "a", "step": "doc-ingest", "args": ["--file"]}], [])

    findings = pipeline.validate_pipeline(p, reg)

    assert _codes(findings) == ["missing-arg-value"]
    assert "--file" in findings[0].message


def test_value_taking_arg_with_a_valid_value_accepted(reg):
    p = _p([{
        "id": "a", "step": "doc-ingest", "args": ["--file"],
        "arg_values": {"--file": "docs/kb/billing/rules.md"},
    }], [])

    assert pipeline.validate_pipeline(p, reg) == []


@pytest.mark.parametrize("value", [
    "docs/kb/a.md; rm -rf /",
    "$(whoami)",
    "`id`",
    "docs/kb/has space.md",
    'docs/kb/"quoted".md',
])
def test_value_failing_the_pattern_rejected(reg, value):
    """Shell metacharacters never reach an argv vector - rejected on the way in."""
    p = _p([{
        "id": "a", "step": "doc-ingest", "args": ["--file"],
        "arg_values": {"--file": value},
    }], [])

    assert _codes(pipeline.validate_pipeline(p, reg)) == ["bad-arg-value"]


def test_arg_value_for_an_unselected_flag_rejected(reg):
    """A stale value left behind after unchecking the flag is a bug, not a nicety."""
    p = _p([{
        "id": "a", "step": "doc-ingest", "args": [],
        "arg_values": {"--file": "docs/kb/a.md"},
    }], [])

    assert _codes(pipeline.validate_pipeline(p, reg)) == ["orphan-arg-value"]


def test_non_value_arg_ignores_arg_values(reg):
    p = _p([{"id": "a", "step": "doc-ingest", "args": ["--dry-run"]}], [])

    assert pipeline.validate_pipeline(p, reg) == []


# --- model overrides -------------------------------------------------------

def test_model_override_for_a_dispatched_agent_accepted(reg):
    p = _p([{"id": "a", "step": "doc-ingest", "models": {"plan-worker": "haiku"}}], [])

    assert pipeline.validate_pipeline(p, reg) == []


def test_model_override_for_an_undispatched_agent_rejected(reg):
    p = _p([{"id": "a", "step": "doc-ingest", "models": {"task-executor": "opus"}}], [])

    findings = pipeline.validate_pipeline(p, reg)

    assert _codes(findings) == ["unknown-agent"]
    assert "task-executor" in findings[0].message


def test_illegal_model_tier_rejected(reg):
    p = _p([{"id": "a", "step": "doc-ingest", "models": {"plan-worker": "gpt-4"}}], [])

    findings = pipeline.validate_pipeline(p, reg)

    assert _codes(findings) == ["illegal-tier"]
    assert "haiku" in findings[0].message


def test_absent_models_means_inherit_the_project_default(reg):
    """Pipelines written before this field existed must stay valid."""
    p = _p([{"id": "a", "step": "doc-ingest"}], [])

    assert pipeline.validate_pipeline(p, reg) == []
    assert p.nodes[0].models == {}


def test_duplicate_node_id_rejected(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}, {"id": "a", "step": "arch-gen"}], [])
    assert "duplicate-node-id" in _codes(pipeline.validate_pipeline(p, reg))


def test_edge_referencing_unknown_node_rejected(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}], [{"from": "a", "to": "ghost"}])
    findings = pipeline.validate_pipeline(p, reg)
    assert "unknown-edge-node" in _codes(findings)


def test_cycle_rejected(reg):
    p = _p(
        [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
        [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    )
    assert "cycle" in _codes(pipeline.validate_pipeline(p, reg))


def test_self_loop_is_a_cycle(reg):
    p = _p([{"id": "a", "step": "doc-ingest"}], [{"from": "a", "to": "a"}])
    assert "cycle" in _codes(pipeline.validate_pipeline(p, reg))


def test_no_root_reported(reg):
    """Every node having an inbound edge means nothing can start."""
    p = _p(
        [{"id": "a", "step": "doc-ingest"}, {"id": "b", "step": "arch-gen"}],
        [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    )
    assert "no-root" in _codes(pipeline.validate_pipeline(p, reg))


def test_unreachable_node_reported(reg):
    """An island node with no path from any root can never run."""
    p = _p(
        [
            {"id": "a", "step": "doc-ingest"},
            {"id": "b", "step": "arch-gen"},
            {"id": "c", "step": "arch-gen"},
            {"id": "d", "step": "arch-gen"},
        ],
        [{"from": "a", "to": "b"}, {"from": "c", "to": "d"}, {"from": "d", "to": "c"}],
    )
    findings = pipeline.validate_pipeline(p, reg)
    unreachable = [f for f in findings if f.code == "unreachable-node"]
    assert {f.node_id for f in unreachable} == {"c", "d"}


def test_empty_pipeline_is_valid(reg):
    """An empty canvas is a legal thing to save while designing."""
    assert pipeline.validate_pipeline(_p([], []), reg) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_pipeline_validation.py -v`
Expected: FAIL — `AttributeError: module 'implr_studio.pipeline' has no attribute 'validate_pipeline'`

- [ ] **Step 3: Append the implementation to `pipeline.py`**

Add to the end of `studio/backend/implr_studio/pipeline.py`:

```python
@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    node_id: str | None = None


def _validate_args(node: Node, step) -> list[Finding]:
    """Flags must be allowed; value-taking flags must have a matching value.

    Values are checked against the arg spec's regex here and passed as separate
    argv elements later - never interpolated into a shell string. Both halves
    matter: the pattern stops nonsense early, the argv vector stops injection.
    """
    import re

    findings: list[Finding] = []
    selected = set(node.args)

    for arg in node.args:
        spec = step.arg(arg)
        if spec is None:
            findings.append(Finding(
                "disallowed-arg",
                "node %s: arg %r not allowed for step %s (allowed: %s)"
                % (node.id, arg, node.step, list(step.flags)),
                node.id,
            ))
            continue
        if not spec.takes_value:
            continue
        value = node.arg_values.get(arg)
        if value is None or value == "":
            findings.append(Finding(
                "missing-arg-value",
                "node %s: arg %r requires a value" % (node.id, arg),
                node.id,
            ))
            continue
        if not re.fullmatch(spec.value_pattern, str(value)):
            findings.append(Finding(
                "bad-arg-value",
                "node %s: value %r for %r does not match %s"
                % (node.id, value, arg, spec.value_pattern),
                node.id,
            ))

    for arg in node.arg_values:
        if arg not in selected:
            findings.append(Finding(
                "orphan-arg-value",
                "node %s: arg_values has %r, which is not a selected arg" % (node.id, arg),
                node.id,
            ))

    return findings


def _validate_models(node: Node, step) -> list[Finding]:
    """A tier override must name an agent this step actually dispatches."""
    from .registry import TIERS

    findings: list[Finding] = []
    known = set(step.agent_names())
    for agent, tier in node.models.items():
        if agent not in known:
            findings.append(Finding(
                "unknown-agent",
                "node %s: step %s does not dispatch agent %r (dispatches: %s)"
                % (node.id, node.step, agent, sorted(known) or "none"),
                node.id,
            ))
            continue
        if tier not in TIERS:
            findings.append(Finding(
                "illegal-tier",
                "node %s: %r is not a legal model tier for %s (legal: %s)"
                % (node.id, tier, agent, list(TIERS)),
                node.id,
            ))
    return findings


def _find_cycle_nodes(node_ids: set[str], edges) -> set[str]:
    """Return every node that participates in a cycle, via iterative DFS colouring."""
    adjacency: dict[str, list[str]] = {n: [] for n in node_ids}
    for e in edges:
        if e.source in adjacency and e.target in node_ids:
            adjacency[e.source].append(e.target)

    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in node_ids}
    in_cycle: set[str] = set()

    for start in sorted(node_ids):
        if colour[start] != WHITE:
            continue
        stack = [(start, iter(adjacency[start]))]
        path = [start]
        colour[start] = GREY
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                if colour[child] == GREY:
                    # Everything from `child` to the top of `path` is in the cycle.
                    in_cycle.update(path[path.index(child):])
                    continue
                if colour[child] == WHITE:
                    colour[child] = GREY
                    path.append(child)
                    stack.append((child, iter(adjacency[child])))
                    advanced = True
                    break
            if not advanced:
                colour[node] = BLACK
                stack.pop()
                path.pop()
    return in_cycle


def validate_pipeline(p: Pipeline, reg) -> list[Finding]:
    """Return findings; an empty list means the pipeline is valid to save.

    Step *availability* is deliberately not checked: designing ahead of a skill's
    implementation is permitted, and run start enforces availability instead.
    """
    findings: list[Finding] = []

    seen: set[str] = set()
    for node in p.nodes:
        if node.id in seen:
            findings.append(Finding("duplicate-node-id", "duplicate node id: %s" % node.id, node.id))
            continue
        seen.add(node.id)

        step = reg.get(node.step)
        if step is None:
            findings.append(
                Finding("unknown-step", "node %s: unknown step %r" % (node.id, node.step), node.id)
            )
            continue

        findings.extend(_validate_args(node, step))
        findings.extend(_validate_models(node, step))

    node_ids = seen
    for e in p.edges:
        for end in (e.source, e.target):
            if end not in node_ids:
                findings.append(Finding(
                    "unknown-edge-node",
                    "edge %s -> %s references unknown node %r" % (e.source, e.target, end),
                    end,
                ))

    live_edges = [e for e in p.edges if e.source in node_ids and e.target in node_ids]

    cycle_nodes = _find_cycle_nodes(node_ids, live_edges)
    if cycle_nodes:
        findings.append(Finding(
            "cycle",
            "pipeline contains a cycle involving: %s" % ", ".join(sorted(cycle_nodes)),
        ))

    if node_ids:
        has_inbound = {e.target for e in live_edges}
        roots = node_ids - has_inbound
        if not roots:
            findings.append(Finding("no-root", "pipeline has no starting node (every node has a dependency)"))
        else:
            adjacency: dict[str, list[str]] = {n: [] for n in node_ids}
            for e in live_edges:
                adjacency[e.source].append(e.target)
            reached: set[str] = set()
            queue = list(roots)
            while queue:
                current = queue.pop()
                if current in reached:
                    continue
                reached.add(current)
                queue.extend(adjacency[current])
            for orphan in sorted(node_ids - reached):
                findings.append(Finding(
                    "unreachable-node",
                    "node %s cannot be reached from any starting node" % orphan,
                    orphan,
                ))

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_pipeline_validation.py -v`
Expected: 12 passed

- [ ] **Step 5: Run the whole suite to check for regressions**

Run: `cd studio/backend && python -m pytest -v`
Expected: all tests from Tasks 1-4 pass

- [ ] **Step 6: Commit**

```bash
git add studio/backend/implr_studio/pipeline.py studio/backend/tests/test_pipeline_validation.py
git commit -m "feat(studio): DAG validation for pipeline configs"
```

---

### Task 5: Gate validation and evaluation

**Files:**
- Create: `studio/backend/implr_studio/gates.py`
- Test: `studio/backend/tests/test_gates.py`

**Interfaces:**
- Consumes: `pipeline.Gate`, `pipeline.Finding` from Tasks 3-4; `implr_bridge.load_contracts`, `implr_bridge.parse_frontmatter`, `implr_bridge.resolve_schema_dir` from Task 1.
- Produces:
  - `gates.validate_gate(gate: Gate, contracts) -> list[Finding]` — save-time schema check.
  - `gates.evaluate_gate(gate: Gate, workspace: Path, contracts) -> bool` — runtime check.
  - Finding codes: `unknown-artefact-type`, `unknown-artefact-field`, `illegal-status`, `missing-artefact`, `missing-quantifier`.

- [ ] **Step 1: Write the failing test**

Create `studio/backend/tests/test_gates.py`:

```python
from pathlib import Path

import pytest

from implr_studio import gates, implr_bridge, pipeline


@pytest.fixture
def contracts():
    root = implr_bridge.repo_root()
    return implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))


def _gate(**kwargs) -> pipeline.Gate:
    return pipeline.Gate(**kwargs)


def _write_req(workspace: Path, req_id: str, status: str) -> None:
    d = workspace / "docs" / "implr" / "requirements" / "functional"
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s.md" % req_id.lower())).write_text(
        "---\nreq_id: %s\nstatus: %s\n---\nbody\n" % (req_id, status), encoding="utf-8"
    )


def _write_plan(workspace: Path, plan_id: str, status: str) -> None:
    d = workspace / "docs" / "implr" / "plans" / "functional"
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s.md" % plan_id.lower())).write_text(
        "---\nplan_id: %s\nstatus: %s\n---\nbody\n" % (plan_id, status), encoding="utf-8"
    )


# --- validation -------------------------------------------------------------

def test_gate_type_none_needs_no_artefact(contracts):
    assert gates.validate_gate(_gate(type="none"), contracts) == []


def test_gate_type_manual_needs_no_artefact(contracts):
    assert gates.validate_gate(_gate(type="manual"), contracts) == []


def test_valid_artifact_gate_passes(contracts):
    g = _gate(type="artifact", artefact="requirement", quantifier="all", require={"status": "approved"})
    assert gates.validate_gate(g, contracts) == []


def test_unknown_artefact_type_rejected(contracts):
    g = _gate(type="artifact", artefact="unicorn", quantifier="all", require={"status": "approved"})
    findings = gates.validate_gate(g, contracts)
    assert [f.code for f in findings] == ["unknown-artefact-type"]


def test_missing_artefact_rejected(contracts):
    g = _gate(type="artifact", quantifier="all", require={"status": "approved"})
    assert [f.code for f in gates.validate_gate(g, contracts)] == ["missing-artefact"]


def test_missing_quantifier_rejected(contracts):
    g = _gate(type="artifact", artefact="requirement", require={"status": "approved"})
    assert [f.code for f in gates.validate_gate(g, contracts)] == ["missing-quantifier"]


def test_unknown_field_rejected(contracts):
    g = _gate(type="artifact", artefact="requirement", quantifier="all", require={"colour": "blue"})
    findings = gates.validate_gate(g, contracts)
    assert [f.code for f in findings] == ["unknown-artefact-field"]


def test_status_outside_state_machine_rejected(contracts):
    """'complete' is not a plan status - the plan machine uses ready/in-progress/done/..."""
    g = _gate(type="artifact", artefact="plan", quantifier="all", require={"status": "complete"})
    findings = gates.validate_gate(g, contracts)
    assert [f.code for f in findings] == ["illegal-status"]
    assert "ready" in findings[0].message      # message names the legal states


def test_artifact_and_manual_gate_is_validated_like_artifact(contracts):
    g = _gate(type="artifact+manual", artefact="unicorn", quantifier="all", require={"status": "approved"})
    assert [f.code for f in gates.validate_gate(g, contracts)] == ["unknown-artefact-type"]


# --- evaluation -------------------------------------------------------------

def test_gate_none_always_open(tmp_path: Path, contracts):
    assert gates.evaluate_gate(_gate(type="none"), tmp_path, contracts) is True


def test_gate_manual_is_never_auto_open(tmp_path: Path, contracts):
    """A manual gate is released by the operator, not by evaluation."""
    assert gates.evaluate_gate(_gate(type="manual"), tmp_path, contracts) is False


def test_all_quantifier_true_when_every_file_matches(tmp_path: Path, contracts):
    _write_req(tmp_path, "REQ-F-001", "approved")
    _write_req(tmp_path, "REQ-F-002", "approved")
    g = _gate(type="artifact", artefact="requirement", quantifier="all", require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is True


def test_all_quantifier_false_when_one_file_differs(tmp_path: Path, contracts):
    _write_req(tmp_path, "REQ-F-001", "approved")
    _write_req(tmp_path, "REQ-F-002", "draft")
    g = _gate(type="artifact", artefact="requirement", quantifier="all", require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_any_quantifier_true_when_one_file_matches(tmp_path: Path, contracts):
    _write_plan(tmp_path, "PLAN-F-001", "ready")
    _write_plan(tmp_path, "PLAN-F-002", "blocked")
    g = _gate(type="artifact", artefact="plan", quantifier="any", require={"status": "ready"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is True


def test_any_quantifier_false_when_no_file_matches(tmp_path: Path, contracts):
    _write_plan(tmp_path, "PLAN-F-001", "blocked")
    g = _gate(type="artifact", artefact="plan", quantifier="any", require={"status": "ready"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_all_over_empty_match_set_is_false(tmp_path: Path, contracts):
    """SPEC RULE: a gate must not open merely because nothing has been produced yet."""
    g = _gate(type="artifact", artefact="requirement", quantifier="all", require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_any_over_empty_match_set_is_false(tmp_path: Path, contracts):
    g = _gate(type="artifact", artefact="requirement", quantifier="any", require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_artifact_plus_manual_does_not_auto_open(tmp_path: Path, contracts):
    """The artefact half may hold, but the operator still has to approve."""
    _write_req(tmp_path, "REQ-F-001", "approved")
    g = _gate(type="artifact+manual", artefact="requirement", quantifier="all", require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_artifact_condition_of_combined_gate_is_queryable(tmp_path: Path, contracts):
    _write_req(tmp_path, "REQ-F-001", "approved")
    g = _gate(type="artifact+manual", artefact="requirement", quantifier="all", require={"status": "approved"})

    assert gates.artefact_condition_holds(g, tmp_path, contracts) is True


@pytest.mark.parametrize("body,label", [
    ("---\nreq_id: REQ-F-002\nstatus: approved\n", "unterminated frontmatter block"),
    ("no frontmatter at all\n", "no frontmatter block"),
])
def test_unparseable_frontmatter_counts_as_not_matching(tmp_path: Path, contracts, body, label):
    """A file implr_validate cannot parse must not be able to satisfy a gate.

    Both inputs genuinely raise FrontmatterError - verified against
    implr_validate.frontmatter directly. Do not substitute malformed *values*
    (e.g. an unclosed inline list): the restricted parser accepts those as
    strings and the test would then pass for the wrong reason.
    """
    d = tmp_path / "docs" / "implr" / "requirements" / "functional"
    d.mkdir(parents=True)
    (d / "broken.md").write_text(body, encoding="utf-8")
    _write_req(tmp_path, "REQ-F-001", "approved")
    g = _gate(type="artifact", artefact="requirement", quantifier="all", require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_file_missing_the_required_field_does_not_match(tmp_path: Path, contracts):
    """Distinct from unparseable: parses cleanly, but has no 'status' at all."""
    d = tmp_path / "docs" / "implr" / "requirements" / "functional"
    d.mkdir(parents=True)
    (d / "nostatus.md").write_text("---\nreq_id: REQ-F-002\n---\nbody\n", encoding="utf-8")
    g = _gate(type="artifact", artefact="requirement", quantifier="any", require={"status": "approved"})

    assert gates.evaluate_gate(g, tmp_path, contracts) is False


def test_multi_field_require_needs_all_fields(tmp_path: Path, contracts):
    d = tmp_path / "docs" / "implr" / "requirements" / "functional"
    d.mkdir(parents=True)
    (d / "r1.md").write_text(
        "---\nreq_id: REQ-F-001\nstatus: approved\ntype: functional\n---\nbody\n", encoding="utf-8"
    )
    match = _gate(type="artifact", artefact="requirement", quantifier="all",
                  require={"status": "approved", "type": "functional"})
    mismatch = _gate(type="artifact", artefact="requirement", quantifier="all",
                     require={"status": "approved", "type": "non-functional"})

    assert gates.evaluate_gate(match, tmp_path, contracts) is True
    assert gates.evaluate_gate(mismatch, tmp_path, contracts) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio/backend && python -m pytest tests/test_gates.py -v`
Expected: FAIL — `ImportError: cannot import name 'gates'`

- [ ] **Step 3: Write the implementation**

Create `studio/backend/implr_studio/gates.py`:

```python
"""Gate validation (save-time) and gate evaluation (runtime).

Artefact types, their path globs, their fields, and the legal statuses all come
from the contract JSON files. Nothing here hardcodes implr's vocabulary.
"""
import glob
import os
from pathlib import Path

from .implr_bridge import parse_frontmatter
from .pipeline import Finding, Gate

_ARTEFACT_GATE_TYPES = ("artifact", "artifact+manual")


def _artefact_fields(spec: dict) -> set[str]:
    return set(spec.get("required", [])) | set(spec.get("optional", [])) | {
        rule_field
        for rule in spec.get("conditional_required", [])
        for rule_field in rule.get("require", [])
    }


def validate_gate(gate: Gate, contracts) -> list[Finding]:
    """Check a gate against the contract files. Empty list means valid to save."""
    if gate.type not in _ARTEFACT_GATE_TYPES:
        return []

    if not gate.artefact:
        return [Finding("missing-artefact", "gate type %r requires an 'artefact'" % gate.type)]

    spec = contracts.artefact_types.get(gate.artefact)
    if spec is None:
        return [Finding(
            "unknown-artefact-type",
            "unknown artefact type %r (legal: %s)"
            % (gate.artefact, sorted(contracts.artefact_types)),
        )]

    if not gate.quantifier:
        return [Finding("missing-quantifier", "gate type %r requires a 'quantifier'" % gate.type)]

    findings: list[Finding] = []
    known_fields = _artefact_fields(spec)
    for field, value in (gate.require or {}).items():
        if field not in known_fields:
            findings.append(Finding(
                "unknown-artefact-field",
                "artefact %s has no field %r (known: %s)"
                % (gate.artefact, field, sorted(known_fields)),
            ))
            continue
        if field == "status":
            legal = contracts.states_for(spec["status_machine"])
            if value not in legal:
                findings.append(Finding(
                    "illegal-status",
                    "%r is not a legal %s status (legal: %s)"
                    % (value, gate.artefact, sorted(legal)),
                ))
    return findings


def _matching_files(workspace: Path, spec: dict) -> list[Path]:
    found: list[Path] = []
    for pattern in spec["path_globs"]:
        native = pattern.replace("/", os.sep)
        found.extend(Path(p) for p in glob.glob(os.path.join(str(workspace), native)))
    return sorted(set(found))


def _file_matches(path: Path, require: dict) -> bool:
    try:
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    except Exception:
        # Unparseable frontmatter cannot satisfy a requirement about its fields.
        return False
    return all(str(fm.get(field, "")) == str(value) for field, value in require.items())


def artefact_condition_holds(gate: Gate, workspace: Path, contracts) -> bool:
    """Evaluate only the artefact half of a gate, ignoring any manual component."""
    spec = contracts.artefact_types.get(gate.artefact or "")
    if spec is None:
        return False

    files = _matching_files(Path(workspace), spec)
    if not files:
        # SPEC RULE: an empty match set never satisfies a gate, under any quantifier.
        return False

    require = gate.require or {}
    results = (_file_matches(p, require) for p in files)
    return all(results) if gate.quantifier == "all" else any(results)


def evaluate_gate(gate: Gate, workspace: Path, contracts) -> bool:
    """True when the gate is open without operator action.

    A gate with a manual component is never opened by evaluation - the operator
    releases it - so both 'manual' and 'artifact+manual' return False here.
    """
    if gate.type == "none":
        return True
    if gate.type in ("manual", "artifact+manual"):
        return False
    return artefact_condition_holds(gate, workspace, contracts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio/backend && python -m pytest tests/test_gates.py -v`
Expected: 23 passed (the unparseable-frontmatter test is parametrized into 2 cases)

- [ ] **Step 5: Run the whole suite**

Run: `cd studio/backend && python -m pytest -v`
Expected: all tests pass (Tasks 1-5)

- [ ] **Step 6: Verify the existing implr test suite still passes**

Run: `cd ../.. && python -m pytest tests/ -q`
Expected: the pre-existing `implr_validate` suite passes unchanged — this plan must not have altered it.

- [ ] **Step 7: Commit**

```bash
git add studio/backend/implr_studio/gates.py studio/backend/tests/test_gates.py
git commit -m "feat(studio): gate validation and evaluation against artefact frontmatter"
```

---

### Task 6: Wire the registry check into implr-validate

**Files:**
- Modify: `scripts/implr_validate/checks.py` (add `check_step_registry`)
- Modify: `scripts/implr_validate/cli.py` (call it under `--repo`; make the exit code level-aware)
- Test: `tests/test_step_registry_check.py`

**Interfaces:**
- Consumes: nothing from the studio package — this runs inside the **existing stdlib-only**
  validator and must not import `implr_studio`, `yaml`, or anything third-party.
- Produces:
  - `checks.check_step_registry(root, contracts) -> list[Finding]` — validates
    `scaffold/schemas/step-registry.json` against `skills/`, `.claude/agents/`, and the
    artefact types in `contracts`.
  - `cli` exits `1` only when at least one finding is `level == "error"`. Findings at
    `level == "info"` print but do not fail the build.

`re` must be imported in `checks.py` (it already is) and `json` added. The check stays
standard-library only — it deliberately re-implements the loader's rules rather than
importing `implr_studio`, because `implr_validate` must keep working in a project that has
never installed the studio backend.

This task exists because the spec's *Step Registry → Validation* section requires it and no
other task delivers it. A planned step must be reported without failing CI — otherwise
adding `sec-review` to the registry before writing the skill would break the build, which is
exactly the workflow the registry is meant to enable.

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
    "id": "doc-ingest", "label": "Document Ingestion", "phase": "discovery",
    "skill": "doc-ingest",
    "args_allowed": [{"flag": "--dry-run", "takes_value": False, "note": ""}],
    "args_default": [],
    "interactive": False,
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


def test_duplicate_id_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [BASE, dict(BASE)])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert [f.level for f in findings] == ["error"]
    assert "duplicate" in findings[0].message


def test_unknown_phase_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, phase="wibble")])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "wibble" in findings[0].message


def test_missing_required_field_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [{k: v for k, v in BASE.items() if k != "skill"}])

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "skill" in findings[0].message


def test_args_default_outside_args_allowed_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, args_default=["--nope"])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "--nope" in findings[0].message


def test_malformed_json_is_an_error_not_a_crash(tmp_path, contracts):
    root = str(tmp_path)
    schema_dir = os.path.join(root, "scaffold", "schemas")
    os.makedirs(schema_dir)
    with open(os.path.join(schema_dir, "step-registry.json"), "w", encoding="utf-8") as f:
        f.write("{not json")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"


def test_value_taking_arg_without_a_pattern_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, args_allowed=[
        {"flag": "--file", "takes_value": True, "note": ""},
    ])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "value_pattern" in findings[0].message


def test_bare_string_args_allowed_is_an_error(tmp_path, contracts):
    """The pre-configurator format must fail loudly, not load with empty arg specs."""
    root = str(tmp_path)
    _write(root, [dict(BASE, args_allowed=["--dry-run"])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "objects" in findings[0].message


def test_agent_without_a_definition_is_an_error(tmp_path, contracts):
    """A tier selector for a non-existent agent configures nothing."""
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


def test_real_produces_artefact_is_fine(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, produces_artefact="plan")])
    _skill(root, "doc-ingest")

    assert check_step_registry(root, contracts) == []


def test_the_real_repo_registry_passes(contracts):
    """The shipped registry must be valid, with the two planned steps reported as info."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    findings = check_step_registry(root, contracts)

    assert [f for f in findings if f.level == "error"] == []
    planned = {f.message for f in findings if f.level == "info"}
    assert any("qa-testing" in m for m in planned)
    assert any("sec-review" in m for m in planned)
```

Also add to `tests/test_cli.py`:

```python
def test_info_findings_do_not_fail_the_exit_code(tmp_path, capsys):
    """A planned step prints but must not break the build."""
    from implr_validate.cli import main

    assert main(["--repo", "--root", "."]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_step_registry_check.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_step_registry'`

- [ ] **Step 3: Add the check to `checks.py`**

Append to `scripts/implr_validate/checks.py`:

```python
# --- step registry (implr Studio) ---

_REGISTRY_PHASES = ("discovery", "design", "requirements", "planning", "build", "verify")
_REGISTRY_FIELDS = (
    "id", "label", "phase", "skill",
    "args_allowed", "args_default", "interactive",
    "agents", "consumes", "produces", "produces_artefact", "description",
)


def check_step_registry(root, contracts):
    """Validate scaffold/schemas/step-registry.json against skills/ and the contracts.

    A registered step whose skill does not exist yet is reported at level "info",
    never "error": designing a pipeline ahead of implementing its steps is the
    workflow the registry exists to support. Everything else - a malformed arg
    spec, an agent with no definition, an unknown artefact type - is an error,
    because each one produces a configurator control that configures nothing.
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
                "error", rel, "step %s missing required field(s): %s" % (step_id, ", ".join(missing))
            ))
            continue

        if step_id in seen:
            findings.append(Finding("error", rel, "duplicate step id: %s" % step_id))
            continue
        seen.add(step_id)

        if entry["phase"] not in _REGISTRY_PHASES:
            findings.append(Finding(
                "error", rel,
                "step %s has unknown phase %r (legal: %s)"
                % (step_id, entry["phase"], list(_REGISTRY_PHASES)),
            ))

        specs = {}
        for spec in entry["args_allowed"]:
            if not isinstance(spec, dict) or "flag" not in spec:
                findings.append(Finding(
                    "error", rel,
                    "step %s args_allowed entries must be objects with a 'flag'" % step_id,
                ))
                continue
            if spec["flag"] in specs:
                findings.append(Finding(
                    "error", rel,
                    "step %s has duplicate flag %r in args_allowed" % (step_id, spec["flag"]),
                ))
                continue
            specs[spec["flag"]] = spec
            if spec.get("takes_value"):
                pattern = spec.get("value_pattern")
                if not pattern:
                    findings.append(Finding(
                        "error", rel,
                        "step %s arg %r takes a value but has no value_pattern"
                        % (step_id, spec["flag"]),
                    ))
                else:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        findings.append(Finding(
                            "error", rel,
                            "step %s arg %r has an invalid value_pattern: %s"
                            % (step_id, spec["flag"], e),
                        ))

        for arg in entry["args_default"]:
            spec = specs.get(arg)
            if spec is None:
                findings.append(Finding(
                    "error", rel,
                    "step %s args_default entry %r is not in args_allowed" % (step_id, arg),
                ))
            elif spec.get("takes_value"):
                findings.append(Finding(
                    "error", rel,
                    "step %s args_default entry %r takes a value, so it cannot be a default"
                    % (step_id, arg),
                ))

        # Every claimed agent must have a definition. A step that dispatches a
        # non-existent agent renders a tier selector that configures nothing.
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
                    % (step_id, name, name),
                ))

        artefact = entry["produces_artefact"]
        if artefact is not None and artefact not in contracts.artefact_types:
            findings.append(Finding(
                "error", rel,
                "step %s produces_artefact %r is not a known artefact type (known: %s)"
                % (step_id, artefact, sorted(contracts.artefact_types)),
            ))

        skill_md = os.path.join(root, "skills", entry["skill"], "SKILL.md")
        if not os.path.isfile(skill_md):
            findings.append(Finding(
                "info", rel,
                "step %s is planned: skills/%s/SKILL.md does not exist yet"
                % (step_id, entry["skill"]),
            ))

    return findings
```

Add `import json` to the top of `checks.py` if it is not already imported.

- [ ] **Step 4: Wire it into `cli.py` and make the exit code level-aware**

In `scripts/implr_validate/cli.py`, change the import line:

```python
from .checks import check_workspace, check_repo_prose, check_step_registry
```

In the `if args.repo:` block, append one line (after `contracts` is already loaded there):

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

Every one of the 20 findings that existed before this change is level `"error"`, so no
previously-failing case starts passing. The only new behaviour is that `"info"` findings
print without failing.

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_step_registry_check.py tests/test_cli.py -v`
Expected: all pass

- [ ] **Step 6: Run the full pre-existing suite for regressions**

Run: `python -m pytest tests/ -q`
Expected: all 68 pre-existing tests still pass, plus the new ones

- [ ] **Step 7: Verify against the real repo**

Run: `python -m implr_validate --repo --root .`
Expected: exit code 0, with two `info:` lines naming `qa-testing` and `sec-review`

- [ ] **Step 8: Commit**

```bash
git add scripts/implr_validate/checks.py scripts/implr_validate/cli.py tests/test_step_registry_check.py tests/test_cli.py
git commit -m "feat(validate): check step-registry.json, with planned steps reported as info"
```

---

## Definition of Done

- [ ] `python -m pytest` in `studio/backend/` passes with all tests from Tasks 1-5.
- [ ] `python -m pytest tests/` at the repo root still passes unchanged.
- [ ] `scaffold/schemas/step-registry.json` loads against the real `skills/` directory, reporting `doc-ingest` and `dev-executor` as available and `qa-testing` / `sec-review` as unavailable.
- [ ] No third-party import was added to `scripts/implr_validate`.
- [ ] A gate requiring `status: complete` on a `plan` is rejected with a message naming the legal plan states.
- [ ] An `all` gate over zero matching files evaluates `False`.
- [ ] `python -m implr_validate --repo --root .` exits `0` and reports the two planned
      steps at `info` level.
- [ ] The 68 pre-existing `implr_validate` tests still pass.

Configurator schema, added with the design:

- [ ] `args_allowed` entries are objects; a bare-string entry is rejected by both the
      loader and `check_step_registry`.
- [ ] Every `takes_value: true` arg spec has a compilable `value_pattern`, and a spec
      without one is rejected at load.
- [ ] Selecting a value-taking flag with no value produces `missing-arg-value`; a value
      containing `;`, `$(`, a backtick, a space or a quote produces `bad-arg-value`.
- [ ] Every agent named in the shipped registry has a `.claude/agents/<name>.md` file, and
      every `produces_artefact` names a real `frontmatter-rules.json` type — both asserted
      against the real repo, not a fixture.
- [ ] A `models` override naming an agent the step does not dispatch produces
      `unknown-agent`; a tier outside `haiku | sonnet | opus` produces `illegal-tier`.
- [ ] A `pipeline.yaml` with no `arg_values` and no `models` round-trips byte-identically
      to the pre-configurator format — the new keys are omitted when empty.
