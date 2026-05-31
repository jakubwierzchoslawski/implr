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
$SkillsSrc = Join-Path $ScriptDir "skills"
$AgentsSrc = Join-Path $ScriptDir ".claude/agents"
$ScaffoldSrc = Join-Path $ScriptDir "scaffold"
$Skills = @("implr-init","doc-ingest","arch-gen","ba-requirements-gen","ba-cr","dev-planner","dev-executor","dev-code-review")

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
if (-not (Test-Path $ScaffoldSrc)) { Write-Error "Missing scaffold source: $ScaffoldSrc"; exit 1 }
New-Item -ItemType Directory -Force -Path $AgentsDest | Out-Null
Copy-Item -Force (Join-Path $AgentsSrc "*.md") $AgentsDest
$agentCount = (Get-ChildItem -Path $AgentsDest -Filter "*.md" -File).Count
Write-Host "  installed $agentCount agents"

# Workspace scaffolding always targets the current project (CWD), regardless of -Global.
Scaffold-Workspace

Write-Host ""
Write-Host "==============================================="
Write-Host "implr installed."
Write-Host "  Skills and agents are in .claude/"
Write-Host ""
Write-Host "Next step:"
Write-Host "  Open your project in Claude Code and run: /implr-init"
Write-Host "  This configures your project name, stack, and standards."
Write-Host "==============================================="
