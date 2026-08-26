#!/usr/bin/env pwsh
# implr installer (Windows PowerShell / PowerShell Core / macOS)
#
# Usage:
#   ./install.ps1           install skills + agents to ./.claude/
#   ./install.ps1 -Global   install skills + agents to ~/.claude/
#
# Run from your project root, then run /implr-init inside Claude Code.

[CmdletBinding()]
param(
  [switch]$Global
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PluginSrc = Join-Path $ScriptDir "plugin"
$SkillsSrc = Join-Path $PluginSrc "skills"
$AgentsSrc = Join-Path $PluginSrc "agents"
$ValidatePkg = Join-Path $ScriptDir "packages/implr_validate"
$Skills = @("implr-init","doc-ingest","arch-gen","ba-requirements-gen","ba-cr","dev-planner","dev-executor","dev-code-review")

function Initialize-Workspace {
    Write-Host ""
    Write-Host "Provisioning workspace..."

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
    Get-ChildItem -Path (Join-Path $PluginSrc "schemas") -Filter "*.md" | ForEach-Object {
        Copy-Item -Force $_.FullName "docs\implr\schemas\"
    }
    Get-ChildItem -Path (Join-Path $PluginSrc "schemas") -Filter "*.json" | ForEach-Object {
        Copy-Item -Force $_.FullName "docs\implr\schemas\"
    }
    Get-ChildItem -Path (Join-Path $PluginSrc "templates") -Filter "*.md" | ForEach-Object {
        Copy-Item -Force $_.FullName "docs\implr\templates\"
    }
    Write-Host "  schemas and templates installed"

    # implr-validate is a package, not a copied directory: a target project pins a
    # version instead of receiving a snapshot that nothing will ever update.
    if (Get-Command pip -ErrorAction SilentlyContinue) {
        # A plain path, not a file:// URL: pip does not accept file:// with a
        # drive-lettered Windows path.
        #
        # Bootstrapping implr itself installs editable, so a contributor's edits
        # to packages/implr_validate take effect. A target project gets a normal
        # install: its copy must keep working if the implr checkout moves away.
        if ((Resolve-Path $ScriptDir).Path -eq (Get-Location).Path) {
            pip install --quiet --upgrade --editable $ValidatePkg
            Write-Host "  implr-validate installed (editable - this is the implr repo)"
        } else {
            pip install --quiet --upgrade $ValidatePkg
            Write-Host "  implr-validate installed"
        }
    } else {
        Write-Host "  WARNING: pip not found - install implr-validate manually:"
        Write-Host "    pip install $ValidatePkg"
    }

    # Skip if exists: config files (user-owned after first write)
    foreach ($f in @("implr.config.yaml", "DEV-STANDARDS.md")) {
        $dest = "docs\implr\config\$f"
        $src  = Join-Path $PluginSrc "config\$f"
        if (-not (Test-Path $dest)) {
            Copy-Item $src $dest
            Write-Host "  created $dest"
        } else {
            Write-Host "  kept existing $dest"
        }
    }

    # Skip if exists: CLAUDE.md at project root
    if (-not (Test-Path "CLAUDE.md")) {
        Copy-Item (Join-Path $PluginSrc "templates\CLAUDE-template.md") "CLAUDE.md"
        Write-Host "  created CLAUDE.md"
    } else {
        Write-Host "  kept existing CLAUDE.md"
    }

    # Skip if exists: cr-index.md seed
    if (-not (Test-Path "docs\implr\requirements\cr-index.md")) {
        Copy-Item (Join-Path $PluginSrc "seeds\cr-index.md") "docs\implr\requirements\cr-index.md"
        Write-Host "  created docs\implr\requirements\cr-index.md"
    } else {
        Write-Host "  kept existing docs\implr\requirements\cr-index.md"
    }

    # Skip if exists: resolved-contradictions.md seed
    if (-not (Test-Path "docs\implr\requirements\resolved-contradictions.md")) {
        Copy-Item (Join-Path $PluginSrc "seeds\resolved-contradictions.md") "docs\implr\requirements\resolved-contradictions.md"
        Write-Host "  created docs\implr\requirements\resolved-contradictions.md"
    } else {
        Write-Host "  kept existing docs\implr\requirements\resolved-contradictions.md"
    }

    # Skip if exists: DOD.md seed at docs/implr/DOD.md
    if (-not (Test-Path "docs\implr\DOD.md")) {
        Copy-Item (Join-Path $PluginSrc "seeds\DOD.md") "docs\implr\DOD.md"
        Write-Host "  created docs\implr\DOD.md"
    } else {
        Write-Host "  kept existing docs\implr\DOD.md"
    }

    Write-Host "  workspace provisioned"
}

if ($Global) {
  $SkillsDest = Join-Path $HOME ".claude/skills"
  $AgentsDest = Join-Path $HOME ".claude/agents"
} else {
  $SkillsDest = Join-Path (Get-Location) ".claude/skills"
  $AgentsDest = Join-Path (Get-Location) ".claude/agents"
}

Write-Host "implr installer"
Write-Host "==============="
Write-Host "Skills -> $SkillsDest"
Write-Host "Agents -> $AgentsDest"

New-Item -ItemType Directory -Force -Path $SkillsDest | Out-Null
foreach ($s in $Skills) {
  $src = Join-Path $SkillsSrc $s
  if (-not (Test-Path $src)) { Write-Error "Missing skill source: $s"; exit 1 }
  $dst = Join-Path $SkillsDest $s
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  Copy-Item -Recurse -Force $src $dst
  Write-Host "  installed $s"
}

if (-not (Test-Path $AgentsSrc)) { Write-Error "Missing agents source: $AgentsSrc"; exit 1 }
if (-not (Test-Path $PluginSrc)) { Write-Error "Missing plugin payload: $PluginSrc"; exit 1 }
if (-not (Test-Path (Join-Path $ValidatePkg "pyproject.toml"))) { Write-Error "Missing implr-validate package: $ValidatePkg"; exit 1 }
New-Item -ItemType Directory -Force -Path $AgentsDest | Out-Null
Copy-Item -Force (Join-Path $AgentsSrc "*.md") $AgentsDest
$agentCount = (Get-ChildItem -Path $AgentsDest -Filter "*.md" -File).Count
Write-Host "  installed $agentCount agents"

    # Remove deprecated executor-worker.md if present (replaced by plan-runner.md in v3)
    $oldAgent = Join-Path $AgentsDest "executor-worker.md"
    if (Test-Path $oldAgent) {
        Remove-Item -Force $oldAgent
        Write-Host "  removed deprecated agent: executor-worker.md (replaced by plan-runner.md in v3)"
    }

# Workspace provisioning always targets the current project (CWD), regardless of -Global.
Initialize-Workspace

Write-Host ""
Write-Host "==============================================="
Write-Host "implr installed."
Write-Host "  Skills and agents are in .claude/"
Write-Host ""
Write-Host "Next step:"
Write-Host "  Open your project in Claude Code and run: /implr-init"
Write-Host "  This configures your project name, stack, and standards."
Write-Host "==============================================="
