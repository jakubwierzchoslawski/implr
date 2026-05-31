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
$Skills = @("implr-init","doc-ingest","arch-gen","ba-requirements-gen","ba-cr","dev-planner","dev-executor","dev-code-review")

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
New-Item -ItemType Directory -Force -Path $AgentsDest | Out-Null
Copy-Item -Force (Join-Path $AgentsSrc "*.md") $AgentsDest
$agentCount = (Get-ChildItem -Path $AgentsDest -Filter "*.md" -File).Count
Write-Host "  installed $agentCount agents"

Write-Host ""
Write-Host "==============================================="
Write-Host "implr installed."
Write-Host "  Skills and agents are in .claude/"
Write-Host ""
Write-Host "Next step:"
Write-Host "  Open your project in Claude Code and run: /implr-init"
Write-Host "  This scaffolds docs/implr/ and sets up your config."
Write-Host "==============================================="
