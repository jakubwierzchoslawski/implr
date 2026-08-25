# implr Studio — Phase −1: Restructure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this phase task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pip install implr-validate` works, no test contains `sys.path.insert`, and one directory holds everything a target project receives — so a Dockerfile has something to install and one thing to copy.

**Roadmap:** `2026-08-25-studio-phases.md` · **Hosted design:** `../specs/2026-08-25-implr-studio-hosted-design.md` (*Repository restructure*) · **Runtime:** `../../RUNTIME.md`

**Must precede Phase 0**, which writes `studio/backend/pyproject.toml` at a path this phase replaces.

---

## Demo

```bash
# The packaging works, with no PYTHONPATH and no path hacks.
pip install -e packages/implr_validate
python -m implr_validate --repo --root .          # note: no PYTHONPATH=scripts
implr-validate --repo --root .                    # and a console script exists

# The hacks are gone.
grep -rn "sys.path.insert" tests/ && echo "FAIL" || echo "OK: no path hacks"

# One directory is the payload.
ls plugin/                                        # skills agents steps templates config seeds

# The installer no longer vendors a Python package by copying files.
grep -n "cp -f.*implr_validate" install.sh && echo "FAIL" || echo "OK: no vendoring"
```

And the thing that actually matters: `python -m pytest tests/ -q` still reports **68 passed**.
This phase moves files and changes nothing about behaviour, so any change in that number is a
mistake.

---

## Why this is a phase and not a chore

Four facts, each verified rather than assumed:

| Fact | Consequence |
|---|---|
| No root `pyproject.toml`, no lockfile, no root `package.json` | A Dockerfile has nothing to `pip install`. Containerisation is blocked, not merely inconvenient. |
| `install.sh` does `cp -f "$VALIDATE_SRC"/*.py "scripts/implr_validate/"` | Every target project holds a **divergent copy** of a Python package with no version pin. A bug fixed here is fixed nowhere else until someone re-runs the installer. |
| Six test files each do `sys.path.insert(0, ".../scripts")` | Works from the repo root, breaks from `/app`. And it is why every runbook in this repo says `PYTHONPATH=scripts`. |
| The payload is spread across `skills/`, `.claude/agents/` and three of `scaffold/`'s four subdirectories | "What does a project receive?" is not answerable by `ls`, and the container needs four `COPY` lines instead of one. |

### What this phase is *not*

`studio/` **does not exist yet** — Phase 0 creates it. So there is no `studio/backend` to move;
this phase only decides where Phase 0 will write. That removes most of the churn I first
expected, and it is the reason this phase is a day rather than a week.

---

## Target layout

```
implr/
├── pyproject.toml            NEW  workspace root
├── uv.lock                   NEW  reproducible images
│
├── packages/
│   ├── implr_validate/       WAS  scripts/implr_validate/   (8 modules)
│   │   ├── pyproject.toml
│   │   └── implr_validate/
│   └── implr_studio/         NEW  Phase 0 writes here
│
├── web/                      NEW  Phase 0 writes here
│
├── plugin/                   the payload — one directory, one lifecycle
│   ├── skills/               WAS  skills/                   (8)
│   ├── agents/               WAS  .claude/agents/           (11)
│   ├── steps/                NEW  Phase 1 writes step-registry.json here
│   ├── schemas/              WAS  scaffold/schemas/         (10)
│   ├── templates/            WAS  scaffold/templates/       (8)
│   ├── config/               WAS  scaffold/config/          (2)
│   └── seeds/                WAS  scaffold/seeds/           (4)
│
├── docker/                   already committed
├── deploy/azure/             Phase 19
├── docs/  tests/  install.{sh,ps1,bat}
```

`scaffold/` and `scripts/` disappear. `skills/` and `.claude/agents/` move under `plugin/`.

### The one behavioural change, stated plainly

`.claude/agents/` currently serves **two purposes**: it is the payload, and it is what *this*
repo uses when you run `/dev-executor` on implr itself. Moving it to `plugin/agents/` breaks
the second unless something puts it back.

So this phase makes the repo **dogfood its own installer**: `bash install.sh` run in the repo
root copies `plugin/agents/` → `.claude/agents/`, and `.claude/agents/` becomes gitignored
generated output.

That is a real cost — a fresh clone cannot run an implr skill until you bootstrap — and it
buys something worth having: **the installer is exercised on every developer setup** instead
of only when a customer runs it. A broken installer becomes a broken dev environment, which
is noticed immediately.

`CONTRIBUTING.md` gains the bootstrap step, and the phase gate checks it.

---

### Task 1: Root workspace and the `implr_validate` package

**Files:**
- Create: `pyproject.toml`, `packages/implr_validate/pyproject.toml`
- Move: `scripts/implr_validate/*.py` → `packages/implr_validate/implr_validate/`
- Modify: the six test files
- Test: `tests/test_packaging.py`

**Interfaces:**
- `implr_validate` importable with no path manipulation.
- Console script `implr-validate` → `implr_validate.cli:main`.

`implr_validate` stays **standard library only**. It is packaged, not rewritten — the package
declares no dependencies, which is what lets a target project install it without pulling in
FastAPI.

- [ ] **Step 1: Write the failing test**

Create `tests/test_packaging.py`:

```python
"""The packaging contract. These are the tests that make the path hacks unnecessary."""
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_implr_validate_imports_without_path_manipulation():
    """The whole point. If this fails, nothing else in the phase matters."""
    import implr_validate
    from implr_validate.contracts import load_contracts          # noqa: F401
    from implr_validate.checks import check_repo_prose            # noqa: F401

    assert implr_validate.__file__


def test_no_test_file_manipulates_sys_path():
    offenders = [
        p.name for p in (REPO / "tests").glob("*.py")
        if "sys.path.insert" in p.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_the_console_script_is_declared():
    data = tomllib.loads(
        (REPO / "packages" / "implr_validate" / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["scripts"]["implr-validate"] == "implr_validate.cli:main"


def test_implr_validate_declares_no_dependencies():
    """A target project installs this. It must not drag FastAPI in with it."""
    data = tomllib.loads(
        (REPO / "packages" / "implr_validate" / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"].get("dependencies", []) == []


def test_module_invocation_works_from_any_directory(tmp_path):
    """`python -m implr_validate` from /tmp is what breaks under a path hack."""
    result = subprocess.run(
        [sys.executable, "-m", "implr_validate", "--repo", "--root", str(REPO)],
        cwd=tmp_path, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "implr-validate: OK" in result.stdout


def test_the_root_workspace_declares_every_package():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    members = data["tool"]["uv"]["workspace"]["members"]

    assert "packages/implr_validate" in members
    assert "packages/implr_studio" in members


def test_scripts_and_scaffold_are_gone():
    """Left in place they become a second, stale source of truth."""
    assert not (REPO / "scripts").exists()
    assert not (REPO / "scaffold").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'implr_validate'`

- [ ] **Step 3: Move the package**

```bash
mkdir -p packages/implr_validate/implr_validate
git mv scripts/implr_validate/*.py packages/implr_validate/implr_validate/
rmdir scripts/implr_validate scripts
```

Use `git mv`, not `cp` then `rm` — history on eight files is worth keeping, and a reviewer
seeing a rename rather than a delete-plus-add can tell at a glance that nothing changed
inside.

- [ ] **Step 4: Write the manifests**

`packages/implr_validate/pyproject.toml`:

```toml
[project]
name = "implr-validate"
version = "3.0.0"
description = "Contract validation for implr workspaces"
requires-python = ">=3.11"
# Deliberately empty. A target project installs this package; it must not pull in
# the studio backend's dependency tree.
dependencies = []

[project.scripts]
implr-validate = "implr_validate.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["implr_validate*"]

[tool.setuptools.package-data]
# The contracts travel with the package so `implr-validate` works in a project
# that has not installed the plugin payload.
implr_validate = ["contracts/*.json"]
```

Root `pyproject.toml`:

```toml
[project]
name = "implr"
version = "3.0.0"
description = "Agentic SDLC pipeline builder and orchestrator"
requires-python = ">=3.11"
dependencies = []

[tool.uv.workspace]
members = ["packages/implr_validate", "packages/implr_studio"]

[tool.uv.sources]
implr-validate = { workspace = true }
implr-studio = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests", "packages"]
asyncio_mode = "auto"
```

`packages/implr_studio` is listed before it exists — `uv` tolerates a missing member with a
warning, and Phase 0 creates it. Listing it now means Phase 0 adds a directory rather than
editing the workspace root.

- [ ] **Step 5: Strip the path hacks**

In each of `tests/test_checks.py`, `test_cli.py`, `test_contracts.py`,
`test_fingerprint.py`, `test_frontmatter.py`, `test_sourceref.py`, delete the line:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
```

Leave the `import sys` / `import os` only where still used. Change nothing else — if a test
body changes, the move was not a move.

- [ ] **Step 6: Install and verify**

```bash
pip install -e packages/implr_validate
python -m pytest tests/ -q
```

Expected: **68 passed plus the new packaging tests.** A different number for the original 68
means something moved that should not have.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml packages tests
git commit -m "refactor: package implr_validate, remove sys.path hacks"
```

---

### Task 2: The `plugin/` payload

**Files:**
- Move: `skills/` → `plugin/skills/`, `.claude/agents/` → `plugin/agents/`, `scaffold/{schemas,templates,config,seeds}` → `plugin/`
- Create: `plugin/steps/.gitkeep`
- Modify: `.gitignore`
- Test: `tests/test_plugin_payload.py`

- [ ] **Step 1: Write the failing test**

```python
"""The payload contract: one directory, complete, and nothing stale outside it."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"

SKILLS = ["implr-init", "doc-ingest", "arch-gen", "ba-requirements-gen",
          "ba-cr", "dev-planner", "dev-executor", "dev-code-review"]

AGENTS = ["arch-drafter", "arch-excerpter", "code-review-worker", "cr-applier",
          "cr-impact-analyzer", "doc-ingest-digester", "doc-ingest-synthesizer",
          "plan-runner", "plan-worker", "requirements-domain-worker", "task-executor"]


def test_every_skill_moved():
    for name in SKILLS:
        assert (PLUGIN / "skills" / name / "SKILL.md").is_file(), name
    assert len(list((PLUGIN / "skills").iterdir())) == len(SKILLS)


def test_every_agent_moved():
    for name in AGENTS:
        assert (PLUGIN / "agents" / ("%s.md" % name)).is_file(), name
    assert len(list((PLUGIN / "agents").glob("*.md"))) == len(AGENTS)


def test_the_contracts_moved():
    schemas = PLUGIN / "schemas"

    assert (schemas / "status-vocabulary.json").is_file()
    assert (schemas / "frontmatter-rules.json").is_file()
    assert len(list(schemas.glob("*.json"))) == 2
    assert len(list(schemas.glob("*.md"))) == 8


def test_templates_config_and_seeds_moved():
    assert len(list((PLUGIN / "templates").glob("*.md"))) == 8
    assert (PLUGIN / "config" / "implr.config.yaml").is_file()
    assert (PLUGIN / "config" / "DEV-STANDARDS.md").is_file()
    assert len(list((PLUGIN / "seeds").iterdir())) == 4


def test_the_old_locations_are_gone():
    """A stale copy is a second source of truth that nobody edits and everybody reads."""
    assert not (REPO / "skills").exists()
    assert not (REPO / "scaffold").exists()


def test_dot_claude_agents_is_generated_not_tracked():
    """plugin/agents is the source; .claude/agents is bootstrap output."""
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")

    assert ".claude/agents/" in ignore


def test_the_payload_is_one_copy_operation():
    """The container does `COPY plugin/ /app/plugin/`. Anything outside it that a
    target project needs breaks that, so assert the set of top-level entries."""
    entries = {p.name for p in PLUGIN.iterdir() if not p.name.startswith(".")}

    assert entries == {"skills", "agents", "steps", "schemas", "templates", "config", "seeds"}
```

- [ ] **Step 2: Move**

```bash
mkdir -p plugin/steps
git mv skills plugin/skills
git mv .claude/agents plugin/agents
git mv scaffold/schemas   plugin/schemas
git mv scaffold/templates plugin/templates
git mv scaffold/config    plugin/config
git mv scaffold/seeds     plugin/seeds
rmdir scaffold
touch plugin/steps/.gitkeep
```

- [ ] **Step 3: Update the paths that referenced the old locations**

```bash
grep -rln "scaffold/schemas\|scaffold/templates\|scaffold/config\|scaffold/seeds" \
     --include="*.py" --include="*.md" --include="*.json" --include="*.sh" \
     --include="*.ps1" --include="*.bat" .
```

Three groups, and the third is easy to miss:

1. **`implr_validate`** — `cli._resolve_schema_dir` prefers `scaffold/schemas`; it becomes
   `plugin/schemas`, still falling back to `docs/implr/schemas`.
2. **The installers** — Task 3.
3. **`frontmatter-rules.json` itself** — `repo_prose_checks` has `banned_token_surfaces`,
   `enum_comment_surfaces`, `cache_path_surfaces`, `enum_check_exempt` and
   `format_presence_surfaces`, all of which name `scaffold/` or `skills/` paths. Miss these
   and `implr-validate --repo` silently stops checking anything, because a surface prefix that
   matches nothing is not an error.

Add to `.gitignore`:

```gitignore
# generated by the bootstrap; plugin/agents is the source
.claude/agents/
```

- [ ] **Step 4: Verify and commit**

```bash
python -m pytest tests/ -q
python -m implr_validate --repo --root .
```

Expected: all green, `implr-validate: OK`. Then a check that the third group was not missed:

```bash
python - <<'PY'
import json
r = json.load(open("plugin/schemas/frontmatter-rules.json", encoding="utf-8"))
c = r["repo_prose_checks"]
stale = [p for k in ("banned_token_surfaces", "enum_comment_surfaces",
                     "cache_path_surfaces", "enum_check_exempt",
                     "format_presence_surfaces")
         for p in c.get(k, []) if p.startswith(("scaffold/", "skills/"))]
print("stale surfaces:", stale or "none")
PY
```

Expected: `none`. If it prints anything, the prose checks are inert.

```bash
git add -A && git commit -m "refactor: one plugin/ directory for the target-project payload"
```

---

### Task 3: The installers stop vendoring Python

**Files:**
- Modify: `install.sh`, `install.ps1`, `install.bat`
- Create: `tests/test_installer.py`
- Modify: `CONTRIBUTING.md`

The installer currently copies eight `.py` files into `scripts/implr_validate/` in the target
project. It should install a package instead.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALLERS = ["install.sh", "install.ps1", "install.bat"]


def test_no_installer_copies_python_files():
    """Vendoring a package by shell script gives every project a divergent copy."""
    for name in INSTALLERS:
        text = (REPO / name).read_text(encoding="utf-8")
        assert "implr_validate" not in text or "pip install" in text, name


def test_every_installer_installs_the_package():
    for name in INSTALLERS:
        assert "implr-validate" in (REPO / name).read_text(encoding="utf-8"), name


def test_every_installer_reads_from_plugin():
    for name in INSTALLERS:
        text = (REPO / name).read_text(encoding="utf-8")
        assert "plugin" in text, name
        assert "scaffold" not in text, name


def test_the_installers_agree_on_the_skill_list():
    """Three files hand-synced is three chances to diverge. Assert they have not."""
    import re

    lists = []
    for name in INSTALLERS:
        text = (REPO / name).read_text(encoding="utf-8")
        lists.append(set(re.findall(r"\b(implr-init|doc-ingest|arch-gen|ba-requirements-gen"
                                    r"|ba-cr|dev-planner|dev-executor|dev-code-review)\b", text)))

    assert lists[0] == lists[1] == lists[2]
    assert len(lists[0]) == 8


def test_the_bootstrap_step_is_documented():
    """A fresh clone cannot run an implr skill until .claude/agents exists."""
    assert "install.sh" in (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Change the installers**

In `install.sh`, replace the vendoring block:

```bash
  # Always overwrite: implr_validate tool (plugin-owned)
  mkdir -p "scripts/implr_validate"
  cp -f "$VALIDATE_SRC"/*.py "scripts/implr_validate/"
  echo "  implr_validate tool installed"
```

with an install:

```bash
  # implr-validate is a package, not a copied directory: a target project pins a
  # version instead of receiving a snapshot that nothing will ever update.
  if command -v pip >/dev/null 2>&1; then
    pip install --quiet --upgrade "implr-validate @ file://$SCRIPT_DIR/packages/implr_validate"
    echo "  implr-validate installed ($(implr-validate --version 2>/dev/null || echo local))"
  else
    echo "  WARNING: pip not found - install implr-validate manually:"
    echo "    pip install $SCRIPT_DIR/packages/implr_validate"
  fi
```

Repoint the payload copies from `$SCAFFOLD_SRC` to `$PLUGIN_SRC="$SCRIPT_DIR/plugin"`, and
`$SKILLS_SRC` to `$PLUGIN_SRC/skills`, `$AGENTS_SRC` to `$PLUGIN_SRC/agents`. Mirror all of it
in `install.ps1` and `install.bat`.

**Do not silently skip on a missing `pip`.** A target project without `implr-validate` has no
contract validation, and a warning the user can act on beats a workspace that looks installed
and is not.

- [ ] **Step 3: Add the bootstrap note to `CONTRIBUTING.md`**

```markdown
## Developing implr on implr

`.claude/agents/` is generated. `plugin/agents/` is the source, so a fresh clone has no
agents and no skills registered until you bootstrap:

    bash install.sh            # or: pwsh install.ps1

This copies `plugin/skills/` and `plugin/agents/` into `.claude/`, which is what lets you run
`/dev-executor` on this repository. It also means **the installer is exercised on every
developer setup** — if it breaks, your dev environment breaks, and you find out immediately
rather than when a customer does.
```

- [ ] **Step 4: Verify against a throwaway workspace**

```bash
PROBE=$(mktemp -d)/probe && mkdir -p "$PROBE" && cd "$PROBE"
bash "$IMPLR/install.sh"

ls .claude/skills | wc -l          # 8
ls .claude/agents/*.md | wc -l     # 11
ls docs/implr/schemas/*.json       # 2
ls scripts/ 2>/dev/null && echo "FAIL: still vendoring" || echo "OK: no scripts/ copy"
implr-validate --workspace .       # the console script works in the target project
```

- [ ] **Step 5: Commit**

```bash
git add install.sh install.ps1 install.bat CONTRIBUTING.md tests/test_installer.py
git commit -m "refactor(install): install implr-validate as a package, read from plugin/"
```

---

### Task 4: Bootstrap this repo and confirm nothing regressed

Not a code task. The phase gate.

- [ ] **Step 1: Bootstrap**

```bash
cd "$IMPLR" && bash install.sh
ls .claude/agents/*.md | wc -l     # 11, generated
git status --porcelain .claude/    # empty - it is gitignored
```

- [ ] **Step 2: The full sweep**

```bash
python -m pytest tests/ -q                     # 68 + packaging + payload + installer
python -m implr_validate --repo --root .        # no PYTHONPATH
implr-validate --repo --root .                  # console script
git status --porcelain | grep -v "^ M docs/"    # nothing stray
```

- [ ] **Step 3: Confirm the container has one thing to copy**

```bash
grep -n "COPY plugin/" docker/*.Dockerfile      # both images
grep -n "COPY packages/" docker/*.Dockerfile    # both images
```

The Dockerfiles committed earlier already reference `plugin/` and `packages/` — they were
written against this layout, which is the other reason this phase comes first.

- [ ] **Step 4: Commit**

```bash
git commit -am "chore: bootstrap after restructure" --allow-empty
```

---

## Definition of Done

- [ ] `python -m pytest tests/ -q` reports the **original 68** plus the new packaging, payload
      and installer tests. A different count for the 68 means something moved that should not.
- [ ] `python -m implr_validate --repo --root .` exits `0` with **no** `PYTHONPATH`.
- [ ] `implr-validate --repo --root .` works — the console script exists.
- [ ] `python -m implr_validate` works from a directory that is not the repo root.
- [ ] No file in `tests/` contains `sys.path.insert`.
- [ ] `implr-validate`'s package declares **no** dependencies.
- [ ] `scripts/` and `scaffold/` no longer exist.
- [ ] `plugin/` contains exactly `skills agents steps schemas templates config seeds`, with 8
      skills, 11 agents, 2 JSON contracts, 8 templates, 2 configs, 4 seeds.
- [ ] No `repo_prose_checks` surface still names `scaffold/` or `skills/` — otherwise the prose
      checks pass by matching nothing.
- [ ] No installer copies `.py` files; all three install the package and read from `plugin/`.
- [ ] The three installers agree on the skill list, asserted by test.
- [ ] `.claude/agents/` is gitignored, and `CONTRIBUTING.md` documents the bootstrap.
- [ ] `bash install.sh` in a throwaway directory produces a working workspace with a working
      `implr-validate`.

---

## What the next phase gets

A repository a Dockerfile can build and a package a target project can pin. **Phase 0** now
creates `packages/implr_studio/` and `web/` rather than `studio/backend/` and
`studio/frontend/` — the only change to it is paths.
