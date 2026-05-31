# implr-init: Move Workspace Scaffolding to Installer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all file/directory operations out of the `/implr-init` LLM skill and into the install scripts so that `/implr-init` only collects config answers and substitutes placeholders.

**Architecture:** A new top-level `scaffold/` directory replaces `skills/implr-init/assets/` as the source of truth for workspace files. The three install scripts gain a `scaffold_workspace` function that creates `docs/implr/` dirs and copies scaffold files. `skills/implr-init/SKILL.md` is rewritten as a pure config configurator: 8 questions, in-place substitutions on three files, and creation of `<src>/frontend/` and `<src>/backend/` subdirs.

**Tech Stack:** Bash (install.sh), PowerShell (install.ps1), Windows Batch (install.bat), Markdown (SKILL.md, README.md)

---

### Task 1: Set up scaffold/ directory

**Files:**
- Create: `scaffold/config/implr.config.yaml` (moved)
- Create: `scaffold/config/DEV-STANDARDS.md` (moved, then updated)
- Create: `scaffold/schemas/` (6 files moved)
- Create: `scaffold/templates/` (6 files moved)
- Create: `scaffold/seeds/cr-index.md` (new)
- Delete: `skills/implr-init/assets/` (removed after move)

- [ ] **Step 1: Create scaffold/ directory structure**

```bash
mkdir -p scaffold/config scaffold/schemas scaffold/templates scaffold/seeds
```

- [ ] **Step 2: Move all assets using git mv**

```bash
git mv skills/implr-init/assets/config/implr.config.yaml scaffold/config/implr.config.yaml
git mv skills/implr-init/assets/config/DEV-STANDARDS.md scaffold/config/DEV-STANDARDS.md
git mv skills/implr-init/assets/schemas/kb-index-schema.md scaffold/schemas/kb-index-schema.md
git mv skills/implr-init/assets/schemas/requirement-schema.md scaffold/schemas/requirement-schema.md
git mv skills/implr-init/assets/schemas/plan-schema.md scaffold/schemas/plan-schema.md
git mv skills/implr-init/assets/schemas/review-schema.md scaffold/schemas/review-schema.md
git mv skills/implr-init/assets/schemas/jira-schema.md scaffold/schemas/jira-schema.md
git mv skills/implr-init/assets/schemas/cr-schema.md scaffold/schemas/cr-schema.md
git mv skills/implr-init/assets/templates/ARCHITECTURE-template.md scaffold/templates/ARCHITECTURE-template.md
git mv skills/implr-init/assets/templates/CLAUDE-template.md scaffold/templates/CLAUDE-template.md
git mv skills/implr-init/assets/templates/requirement-template.md scaffold/templates/requirement-template.md
git mv skills/implr-init/assets/templates/plan-template.md scaffold/templates/plan-template.md
git mv skills/implr-init/assets/templates/review-template.md scaffold/templates/review-template.md
git mv skills/implr-init/assets/templates/cr-template.md scaffold/templates/cr-template.md
```

- [ ] **Step 3: Remove now-empty assets/ directories**

```bash
rmdir skills/implr-init/assets/config
rmdir skills/implr-init/assets/schemas
rmdir skills/implr-init/assets/templates
rmdir skills/implr-init/assets
```

On Windows PowerShell use:
```powershell
Remove-Item -Recurse -Force skills/implr-init/assets
```

- [ ] **Step 4: Create scaffold/seeds/cr-index.md**

Write the file with this exact content:

```markdown
# CR Index

> Maintained by ba-cr. Do not edit manually.

## Change Requests

| CR ID  | Title | Status | Change Type | Affected Reqs | Applied At |
|--------|-------|--------|-------------|---------------|------------|

## Pending Human Action

_(none)_
```

- [ ] **Step 5: Update scaffold/config/DEV-STANDARDS.md — §1 Project Stack**

Replace the entire §1 block (lines 12–24 of the current file) with:

```markdown
## 1. Project Stack

```
Frontend:         REPLACE_ME_FRONTEND
Backend:          REPLACE_ME_BACKEND
Database + ORM:   REPLACE_ME_DB
HTTP client:      [FILL IN] e.g. axios / native fetch
Auth:             [FILL IN] e.g. JWT access + refresh tokens
Cache / Queue:    [FILL IN] e.g. Redis 7 / BullMQ
```
```

- [ ] **Step 6: Update scaffold/config/DEV-STANDARDS.md — §7 versioning line**

In §7 API Design, replace:
```
- Versioning: [FILL IN] e.g. URL prefix /api/v1 or header API-Version
```
With:
```
- Versioning: REPLACE_ME_VERSIONING
```

- [ ] **Step 7: Verify scaffold/ tree**

```bash
find scaffold/ -type f | sort
```

Expected output:
```
scaffold/config/DEV-STANDARDS.md
scaffold/config/implr.config.yaml
scaffold/schemas/cr-schema.md
scaffold/schemas/jira-schema.md
scaffold/schemas/kb-index-schema.md
scaffold/schemas/plan-schema.md
scaffold/schemas/requirement-schema.md
scaffold/schemas/review-schema.md
scaffold/seeds/cr-index.md
scaffold/templates/ARCHITECTURE-template.md
scaffold/templates/CLAUDE-template.md
scaffold/templates/cr-template.md
scaffold/templates/plan-template.md
scaffold/templates/requirement-template.md
scaffold/templates/review-template.md
```

- [ ] **Step 8: Verify skills/implr-init/assets/ is gone**

```bash
test ! -d skills/implr-init/assets && echo "OK: assets removed" || echo "FAIL: assets still exists"
```

Expected: `OK: assets removed`

- [ ] **Step 9: Commit**

```bash
git add scaffold/ skills/implr-init/
git commit -m "refactor(scaffold): move assets to scaffold/, add seeds/cr-index.md, update DEV-STANDARDS.md placeholders"
```

---

### Task 2: Update install.sh

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Add SCAFFOLD_SRC variable after existing source variables**

After the line `AGENTS_SRC="$SCRIPT_DIR/.claude/agents"` add:

```bash
SCAFFOLD_SRC="$SCRIPT_DIR/scaffold"
```

- [ ] **Step 2: Add scaffold_workspace function before the main install block**

Insert this function after the `GLOBAL=false` / argument-parsing block and before the `if [ "$GLOBAL" = true ]` block:

```bash
scaffold_workspace() {
  echo ""
  echo "Scaffolding workspace..."

  # Create workspace directories (idempotent)
  for d in \
    "docs/kb" \
    "docs/kb/change-requests" \
    "docs/implr/config" \
    "docs/implr/schemas" \
    "docs/implr/templates" \
    "docs/implr/kb-index/cache" \
    "docs/implr/kb-index/digests/per-doc" \
    "docs/implr/kb-index/domains" \
    "docs/implr/requirements/functional" \
    "docs/implr/requirements/non-functional" \
    "docs/implr/plans/functional" \
    "docs/implr/plans/non-functional" \
    "docs/implr/reviews"
  do
    mkdir -p "$d"
  done

  # Always overwrite: schemas and templates (plugin-owned)
  cp -f "$SCAFFOLD_SRC"/schemas/*.md "docs/implr/schemas/"
  cp -f "$SCAFFOLD_SRC"/templates/*.md "docs/implr/templates/"
  echo "  schemas and templates installed"

  # Skip if exists: config files (user-owned after first write)
  for f in implr.config.yaml DEV-STANDARDS.md; do
    dest="docs/implr/config/$f"
    if [ ! -f "$dest" ]; then
      cp "$SCAFFOLD_SRC/config/$f" "$dest"
      echo "  created $dest"
    else
      echo "  kept existing $dest"
    fi
  done

  # Skip if exists: CLAUDE.md at project root
  if [ ! -f "CLAUDE.md" ]; then
    cp "$SCAFFOLD_SRC/templates/CLAUDE-template.md" "CLAUDE.md"
    echo "  created CLAUDE.md"
  else
    echo "  kept existing CLAUDE.md"
  fi

  # Skip if exists: cr-index.md seed
  if [ ! -f "docs/implr/requirements/cr-index.md" ]; then
    cp "$SCAFFOLD_SRC/seeds/cr-index.md" "docs/implr/requirements/cr-index.md"
    echo "  created docs/implr/requirements/cr-index.md"
  else
    echo "  kept existing docs/implr/requirements/cr-index.md"
  fi

  echo "  workspace scaffolded"
}
```

- [ ] **Step 3: Call scaffold_workspace after the agents install block**

After the line `echo "  installed agents"` and before the final summary block, add:

```bash
scaffold_workspace
```

- [ ] **Step 4: Update the final summary message**

Replace:
```bash
echo "Next step:"
echo "  Open your project in Claude Code and run: /implr-init"
echo "  This scaffolds docs/implr/ and sets up your config."
```

With:
```bash
echo "Next step:"
echo "  Open your project in Claude Code and run: /implr-init"
echo "  This configures your project name, stack, and standards."
```

- [ ] **Step 5: Validate the script parses cleanly**

```bash
bash -n install.sh && echo "OK: syntax valid" || echo "FAIL: syntax error"
```

Expected: `OK: syntax valid`

- [ ] **Step 6: Smoke-test in a temp directory**

```bash
mkdir -p /tmp/implr-test && cd /tmp/implr-test && bash /path/to/implr/install.sh
```

Verify:
- `docs/implr/schemas/` contains 6 `.md` files
- `docs/implr/templates/` contains 6 `.md` files
- `docs/implr/config/implr.config.yaml` exists with `REPLACE_ME` placeholders
- `docs/implr/config/DEV-STANDARDS.md` exists with `REPLACE_ME_FRONTEND` in §1
- `CLAUDE.md` exists with `REPLACE_ME` placeholder
- `docs/implr/requirements/cr-index.md` exists

- [ ] **Step 7: Smoke-test idempotency (re-run in the same directory)**

```bash
bash /path/to/implr/install.sh
```

Verify: output contains `kept existing` lines for config files; schemas/templates are refreshed without error.

- [ ] **Step 8: Commit**

```bash
git add install.sh
git commit -m "feat(install): scaffold workspace dirs and files in install.sh"
```

---

### Task 3: Update install.ps1

**Files:**
- Modify: `install.ps1`

- [ ] **Step 1: Add $ScaffoldSrc variable after existing source variables**

After the line `$AgentsSrc = Join-Path $ScriptDir ".claude/agents"` add:

```powershell
$ScaffoldSrc = Join-Path $ScriptDir "scaffold"
```

- [ ] **Step 2: Add Scaffold-Workspace function**

Insert this function after the `$AgentsSrc` / `$ScaffoldSrc` declarations and before the `if ($Global)` block:

```powershell
function Scaffold-Workspace {
    Write-Host ""
    Write-Host "Scaffolding workspace..."

    # Create workspace directories (idempotent)
    $dirs = @(
        "docs\kb",
        "docs\kb\change-requests",
        "docs\implr\config",
        "docs\implr\schemas",
        "docs\implr\templates",
        "docs\implr\kb-index\cache",
        "docs\implr\kb-index\digests\per-doc",
        "docs\implr\kb-index\domains",
        "docs\implr\requirements\functional",
        "docs\implr\requirements\non-functional",
        "docs\implr\plans\functional",
        "docs\implr\plans\non-functional",
        "docs\implr\reviews"
    )
    foreach ($d in $dirs) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }

    # Always overwrite: schemas and templates (plugin-owned)
    Get-ChildItem -Path (Join-Path $ScaffoldSrc "schemas") -Filter "*.md" | ForEach-Object {
        Copy-Item -Force $_.FullName "docs\implr\schemas\"
    }
    Get-ChildItem -Path (Join-Path $ScaffoldSrc "templates") -Filter "*.md" | ForEach-Object {
        Copy-Item -Force $_.FullName "docs\implr\templates\"
    }
    Write-Host "  schemas and templates installed"

    # Skip if exists: config files (user-owned after first write)
    foreach ($f in @("implr.config.yaml", "DEV-STANDARDS.md")) {
        $dest = "docs\implr\config\$f"
        $src  = Join-Path $ScaffoldSrc "config\$f"
        if (-not (Test-Path $dest)) {
            Copy-Item $src $dest
            Write-Host "  created $dest"
        } else {
            Write-Host "  kept existing $dest"
        }
    }

    # Skip if exists: CLAUDE.md at project root
    if (-not (Test-Path "CLAUDE.md")) {
        Copy-Item (Join-Path $ScaffoldSrc "templates\CLAUDE-template.md") "CLAUDE.md"
        Write-Host "  created CLAUDE.md"
    } else {
        Write-Host "  kept existing CLAUDE.md"
    }

    # Skip if exists: cr-index.md seed
    if (-not (Test-Path "docs\implr\requirements\cr-index.md")) {
        Copy-Item (Join-Path $ScaffoldSrc "seeds\cr-index.md") "docs\implr\requirements\cr-index.md"
        Write-Host "  created docs\implr\requirements\cr-index.md"
    } else {
        Write-Host "  kept existing docs\implr\requirements\cr-index.md"
    }

    Write-Host "  workspace scaffolded"
}
```

- [ ] **Step 3: Call Scaffold-Workspace after the agents install block**

After the line `Write-Host "  installed $agentCount agents"` and before the final summary block, add:

```powershell
Scaffold-Workspace
```

- [ ] **Step 4: Update the final summary message**

Replace:
```powershell
Write-Host "  Open your project in Claude Code and run: /implr-init"
Write-Host "  This scaffolds docs/implr/ and sets up your config."
```

With:
```powershell
Write-Host "  Open your project in Claude Code and run: /implr-init"
Write-Host "  This configures your project name, stack, and standards."
```

- [ ] **Step 5: Validate the script parses cleanly**

```powershell
$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path "install.ps1"), [ref]$null, [ref]$null); Write-Host "OK: syntax valid"
```

Expected: `OK: syntax valid`

- [ ] **Step 6: Smoke-test in a temp directory**

```powershell
$tmp = Join-Path $env:TEMP "implr-test"; New-Item -ItemType Directory -Force $tmp | Out-Null
Set-Location $tmp; & "C:\path\to\implr\install.ps1"
```

Verify the same files as Task 2 Step 6.

- [ ] **Step 7: Commit**

```bash
git add install.ps1
git commit -m "feat(install): scaffold workspace dirs and files in install.ps1"
```

---

### Task 4: Update install.bat

**Files:**
- Modify: `install.bat`

- [ ] **Step 1: Add SCAFFOLD_SRC variable after existing source variables**

After the line `set "AGENTS_SRC=%SCRIPT_DIR%.claude\agents"` add:

```bat
set "SCAFFOLD_SRC=%SCRIPT_DIR%scaffold"
```

- [ ] **Step 2: Add :scaffold_workspace subroutine**

Insert this subroutine at the end of the file, after the final `endlocal` line (batch subroutines must come after `endlocal` or be placed before the main flow with a `goto :eof` guard):

Add a `call :scaffold_workspace` line after the `echo   installed agents` line and before the final summary block, then append the subroutine before `endlocal`:

```bat
call :scaffold_workspace
```

And append the subroutine just before `endlocal`:

```bat
goto :after_scaffold

:scaffold_workspace
echo.
echo Scaffolding workspace...

if not exist "docs\kb" mkdir "docs\kb"
if not exist "docs\kb\change-requests" mkdir "docs\kb\change-requests"
if not exist "docs\implr\config" mkdir "docs\implr\config"
if not exist "docs\implr\schemas" mkdir "docs\implr\schemas"
if not exist "docs\implr\templates" mkdir "docs\implr\templates"
if not exist "docs\implr\kb-index\cache" mkdir "docs\implr\kb-index\cache"
if not exist "docs\implr\kb-index\digests\per-doc" mkdir "docs\implr\kb-index\digests\per-doc"
if not exist "docs\implr\kb-index\domains" mkdir "docs\implr\kb-index\domains"
if not exist "docs\implr\requirements\functional" mkdir "docs\implr\requirements\functional"
if not exist "docs\implr\requirements\non-functional" mkdir "docs\implr\requirements\non-functional"
if not exist "docs\implr\plans\functional" mkdir "docs\implr\plans\functional"
if not exist "docs\implr\plans\non-functional" mkdir "docs\implr\plans\non-functional"
if not exist "docs\implr\reviews" mkdir "docs\implr\reviews"

for %%F in ("%SCAFFOLD_SRC%\schemas\*.md") do copy /y "%%F" "docs\implr\schemas\" >nul
for %%F in ("%SCAFFOLD_SRC%\templates\*.md") do copy /y "%%F" "docs\implr\templates\" >nul
echo   schemas and templates installed

if not exist "docs\implr\config\implr.config.yaml" (
    copy /y "%SCAFFOLD_SRC%\config\implr.config.yaml" "docs\implr\config\implr.config.yaml" >nul
    echo   created docs\implr\config\implr.config.yaml
) else (
    echo   kept existing docs\implr\config\implr.config.yaml
)
if not exist "docs\implr\config\DEV-STANDARDS.md" (
    copy /y "%SCAFFOLD_SRC%\config\DEV-STANDARDS.md" "docs\implr\config\DEV-STANDARDS.md" >nul
    echo   created docs\implr\config\DEV-STANDARDS.md
) else (
    echo   kept existing docs\implr\config\DEV-STANDARDS.md
)

if not exist "CLAUDE.md" (
    copy /y "%SCAFFOLD_SRC%\templates\CLAUDE-template.md" "CLAUDE.md" >nul
    echo   created CLAUDE.md
) else (
    echo   kept existing CLAUDE.md
)

if not exist "docs\implr\requirements\cr-index.md" (
    copy /y "%SCAFFOLD_SRC%\seeds\cr-index.md" "docs\implr\requirements\cr-index.md" >nul
    echo   created docs\implr\requirements\cr-index.md
) else (
    echo   kept existing docs\implr\requirements\cr-index.md
)

echo   workspace scaffolded
goto :eof

:after_scaffold
```

- [ ] **Step 3: Update the final summary message**

Replace:
```bat
echo   Open your project in Claude Code and run: /implr-init
echo   This scaffolds docs\implr\ and sets up your config.
```

With:
```bat
echo   Open your project in Claude Code and run: /implr-init
echo   This configures your project name, stack, and standards.
```

- [ ] **Step 4: Smoke-test in a temp directory (Windows CMD)**

```bat
mkdir %TEMP%\implr-test
cd %TEMP%\implr-test
C:\path\to\implr\install.bat
```

Verify: same files as Task 2 Step 6 but with backslash paths.

- [ ] **Step 5: Commit**

```bash
git add install.bat
git commit -m "feat(install): scaffold workspace dirs and files in install.bat"
```

---

### Task 5: Rewrite skills/implr-init/SKILL.md

**Files:**
- Modify: `skills/implr-init/SKILL.md`

- [ ] **Step 1: Replace the entire file content**

Write `skills/implr-init/SKILL.md` with this exact content:

```markdown
---
name: implr-init
description: >
  Configures the implr workspace after the installer has scaffolded docs/implr/. Asks 8
  setup questions (project name, frontend/backend/db stack, paths, TDD threshold, API
  versioning), substitutes placeholders in implr.config.yaml, DEV-STANDARDS.md, and
  CLAUDE.md, and creates <src>/frontend/ and <src>/backend/ subdirectories. Idempotent:
  re-running re-asks all questions and re-applies substitutions.
---

# implr-init Skill

You configure the implr workspace: collect project details and substitute placeholders in
three config files. The installer already created all directories and copied all files —
your only job is questions, substitutions, and two source subdirectory creates.

---

## Pre-flight

Check whether `docs/implr/config/implr.config.yaml` exists. If it does not, halt with:

```
Workspace not found. Run the installer first (install.sh / install.ps1 / install.bat),
then re-run /implr-init.
```

---

## Step 1 — Collect answers (one question at a time)

Ask all questions in order. Collect all answers before any file operation.
Accept the stated default silently if the user presses enter with no input.

| # | Question | Default |
|---|----------|---------|
| 1 | Project name? | _(required — no default)_ |
| 2a | Frontend technology? | `React` |
| 2b | Backend technology? | `Python` |
| 2c | Database + ORM? | `PostgreSQL 16, SQLAlchemy 2.0` |
| 3 | Source folder? | `src` |
| 4 | Tests folder? | `tests` |
| 5 | Default TDD threshold — M / L / XL? | `M` |
| 6 | API versioning strategy? | `/api/v1` |

On re-init (config files already contain real values, not REPLACE_ME), still ask all
questions. The substitution step replaces whatever current value is at each location.

---

## Step 2 — Create source subdirectories

Create these directories (idempotent — no error if they already exist):

```
<answer 3>/
<answer 3>/frontend/
<answer 3>/backend/
```

Example: user answers `dupajas` → create `dupajas/`, `dupajas/frontend/`, `dupajas/backend/`.

---

## Step 3 — Apply substitutions

Edit three files in-place. Apply all substitutions for each file in a single pass.
On re-init, replace whatever current value is at each target location — not just
REPLACE_ME literals. Asset files are opaque: do not deep-read them to reason about content.

### `docs/implr/config/implr.config.yaml`

| Field path | Replace current value with |
|------------|---------------------------|
| `project.name` value | answer 1 |
| `project.stack_hint` value | `"<answer 2a>, <answer 2b>, <answer 2c>"` |
| `paths.src` value | answer 3 (skip if answer equals default `src`) |
| `paths.tests` value | answer 4 (skip if answer equals default `tests`) |
| `behaviour.default_tdd_threshold` value | answer 5 (skip if answer equals default `M`) |

### `docs/implr/config/DEV-STANDARDS.md`

| Location | Replace current value with |
|----------|---------------------------|
| `REPLACE_ME_FRONTEND` in §1 | answer 2a |
| `REPLACE_ME_BACKEND` in §1 | answer 2b |
| `REPLACE_ME_DB` in §1 | answer 2c |
| `REPLACE_ME_VERSIONING` in §7 | answer 6 |

### `CLAUDE.md` (project root)

| Location | Replace current value with |
|----------|---------------------------|
| `REPLACE_ME` | answer 1 (project name) |

---

## Step 4 — Report

```
✅ implr configured
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Updated:
  docs/implr/config/implr.config.yaml
  docs/implr/config/DEV-STANDARDS.md
  CLAUDE.md

Created:
  <answer 3>/frontend/
  <answer 3>/backend/

Remaining [FILL IN] sections in DEV-STANDARDS.md (open in your editor):
  §2 Folder Structure
  §3 Naming Conventions
  §4 Architecture Patterns (DI, Error Handling, Validation)
  §9 Logging and Observability
  §11 Environment Configuration

Next steps:
  1. Complete the remaining [FILL IN] sections of docs/implr/config/DEV-STANDARDS.md
  2. Add your documentation to docs/kb/
  3. Run /doc-ingest to index and digest your knowledge base
  4. Run /arch-gen to generate docs/ARCHITECTURE.md
  5. Run /ba-requirements-gen to generate requirements
```
```

- [ ] **Step 2: Verify the file has no references to `assets/`**

```bash
grep -n "assets" skills/implr-init/SKILL.md
```

Expected: no output (zero matches).

- [ ] **Step 3: Commit**

```bash
git add skills/implr-init/SKILL.md
git commit -m "feat(implr-init): rewrite as pure config configurator — 8 questions, in-place substitutions"
```

---

### Task 6: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update "What the installer creates" section**

Replace:
```markdown
```
your-project/
└── .claude/
    ├── skills/    eight implr skills
    └── agents/    ten dedicated subagents
```

That's it. Open your project in Claude Code and run `/implr-init` to scaffold `docs/implr/`.
```

With:
```markdown
```
your-project/
├── .claude/
│   ├── skills/    eight implr skills
│   └── agents/    ten dedicated subagents
├── docs/
│   ├── kb/                      (add your documents here)
│   │   └── change-requests/
│   └── implr/                   plugin workspace (schemas, templates, config with placeholders)
└── CLAUDE.md                    project briefing template
```

Open your project in Claude Code and run `/implr-init` to fill in your project name,
stack, and standards.
```

- [ ] **Step 2: Update Quick Start Step 2**

Replace:
```markdown
This asks you 14 setup questions (project name, stack, paths, conventions), then creates
`docs/implr/` with your config, schemas, and templates pre-filled.
```

With:
```markdown
This asks you 8 setup questions (project name, frontend/backend/db stack, paths, TDD
threshold, API versioning), substitutes your answers into the config files, and creates
`<src>/frontend/` and `<src>/backend/` subdirectories.
```

- [ ] **Step 3: Update the Full Pipeline Step 1 (SETUP)**

Replace:
```
Installer copies skills + agents to .claude/; /implr-init scaffolds docs/implr/ and seeds config + standards
```

With:
```
Installer copies skills + agents to .claude/ and scaffolds docs/implr/ with schemas, templates, and config placeholders; /implr-init fills in project name, stack, and standards
```

- [ ] **Step 4: Update "How You Interact With implr" table row for implr-init**

Replace:
```markdown
| `implr-init` | Interactive | 14 setup questions (project name, stack, paths, TDD threshold, API conventions, Git branch prefix, optional Jira) — once at first init; silent on re-init |
```

With:
```markdown
| `implr-init` | Interactive | 8 setup questions (project name, frontend/backend/db stack, paths, TDD threshold, API versioning) — re-asked on every run to re-apply substitutions |
```

- [ ] **Step 5: Update the implr-init Skills Reference section**

Replace the paragraph starting "Scaffolds `docs/implr/`..." through the closing code block:
```markdown
Scaffolds `docs/implr/` and all its subdirectories, then asks 14 setup questions (project
name, stack, paths, TDD threshold, API conventions, Git branch prefix, optional Jira) to
pre-fill `implr.config.yaml` and `DEV-STANDARDS.md`. Also creates `CLAUDE.md` and initialises
the `cr-index.md`. On re-init, skips the questions and refreshes only plugin-owned files
(schemas and templates). `.claude/agents/` is shipped by the installer, not by this skill.

```
/implr-init
```
```

With:
```markdown
Asks 8 setup questions (project name, frontend/backend/db stack, paths, TDD threshold, API
versioning) and substitutes answers into `docs/implr/config/implr.config.yaml`,
`docs/implr/config/DEV-STANDARDS.md`, and `CLAUDE.md`. Also creates `<src>/frontend/` and
`<src>/backend/` subdirectories. The installer handles all directory creation and file copying;
this skill is config-only. Re-running re-asks all questions so you can update your stack.

```
/implr-init
```
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): update installer and implr-init descriptions for scaffold-based flow"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `scaffold/` directory with moved assets | Task 1 |
| `scaffold/seeds/cr-index.md` | Task 1 Step 4 |
| DEV-STANDARDS.md §1 new placeholders (REPLACE_ME_FRONTEND/BACKEND/DB) | Task 1 Steps 5–6 |
| DEV-STANDARDS.md §7 REPLACE_ME_VERSIONING | Task 1 Step 6 |
| `skills/implr-init/assets/` deleted | Task 1 Step 3 |
| install.sh scaffold_workspace function | Task 2 |
| install.ps1 Scaffold-Workspace function | Task 3 |
| install.bat scaffold section | Task 4 |
| SKILL.md rewrite: pre-flight, 8 questions, substitutions, subfolders, report | Task 5 |
| README.md updates | Task 6 |
| Idempotency: schemas/templates always overwrite | Tasks 2–4 |
| Idempotency: config/CLAUDE.md/cr-index skip if exists | Tasks 2–4 |
| Re-init: re-asks questions, re-applies substitutions to current values | Task 5 SKILL.md |
| Source folder creates frontend/ and backend/ subdirs | Task 5 SKILL.md Step 2 |

All spec requirements covered. No placeholders (TBD/TODO) in the plan. Type consistency: placeholder names `REPLACE_ME_FRONTEND`, `REPLACE_ME_BACKEND`, `REPLACE_ME_DB`, `REPLACE_ME_VERSIONING` used consistently between Task 1 (DEV-STANDARDS.md edits) and Task 5 (SKILL.md substitution table).
