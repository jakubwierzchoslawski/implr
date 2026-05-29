#!/usr/bin/env pwsh
# implr installer (macOS / Windows PowerShell / PowerShell Core)
#
# Usage:
#   ./install.ps1                 install skills to ./.claude/skills and scaffold ./docs/implr
#   ./install.ps1 -Global         install skills to ~/.claude/skills (scaffold targets ./)
#   ./install.ps1 -SkillsOnly     install skills only, no project scaffold
#
# Run from your project root.

[CmdletBinding()]
param(
  [switch]$Global,
  [switch]$SkillsOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsSrc = Join-Path $ScriptDir "skills"
$Skills = @("implr-init","doc-ingest","arch-gen","ba-requirements-gen","dev-planner","dev-executor","dev-code-review")

if ($Global) {
  $SkillsDest = Join-Path $HOME ".claude/skills"
} else {
  $SkillsDest = Join-Path (Get-Location) ".claude/skills"
}

Write-Host "implr installer"
Write-Host "==============="
Write-Host "Skills -> $SkillsDest"

New-Item -ItemType Directory -Force -Path $SkillsDest | Out-Null
foreach ($s in $Skills) {
  $src = Join-Path $SkillsSrc $s
  if (-not (Test-Path $src)) { Write-Error "Missing skill source: $s"; exit 1 }
  $dst = Join-Path $SkillsDest $s
  if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
  Copy-Item -Recurse -Force $src $dst
  Write-Host "  installed $s"
}

if ($SkillsOnly) {
  Write-Host "Skills installed. Run /implr-init inside Claude Code to scaffold the project."
  exit 0
}

$Assets = Join-Path $SkillsSrc "implr-init/assets"
$Root = (Get-Location).Path

Write-Host ""
Write-Host "Scaffolding project workspace under $Root/docs"

$dirs = @(
  "docs/kb",
  "docs/implr/config",
  "docs/implr/schemas",
  "docs/implr/templates",
  "docs/implr/kb-index/cache",
  "docs/implr/kb-index/digests/per-doc",
  "docs/implr/kb-index/domains",
  "docs/implr/requirements/functional",
  "docs/implr/requirements/non-functional",
  "docs/implr/plans/functional",
  "docs/implr/plans/non-functional",
  "docs/implr/reviews"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null }

$keep = @(
  "docs/kb",
  "docs/implr/kb-index/cache",
  "docs/implr/kb-index/digests/per-doc",
  "docs/implr/kb-index/domains",
  "docs/implr/requirements/functional",
  "docs/implr/requirements/non-functional",
  "docs/implr/plans/functional",
  "docs/implr/plans/non-functional",
  "docs/implr/reviews"
)
foreach ($d in $keep) {
  $gk = Join-Path $Root (Join-Path $d ".gitkeep")
  if (-not (Test-Path $gk)) { New-Item -ItemType File -Force -Path $gk | Out-Null }
}

# schemas + templates: plugin-owned, refreshed
Copy-Item -Force (Join-Path $Assets "schemas/*.md") (Join-Path $Root "docs/implr/schemas/")
Copy-Item -Force (Join-Path $Assets "templates/*.md") (Join-Path $Root "docs/implr/templates/")
Write-Host "  schemas and templates copied"

function Copy-IfAbsent($src, $dst) {
  if (-not (Test-Path $dst)) { Copy-Item -Force $src $dst; Write-Host "  created $dst" }
  else { Write-Host "  kept existing $dst" }
}
Copy-IfAbsent (Join-Path $Assets "config/implr.config.yaml") (Join-Path $Root "docs/implr/config/implr.config.yaml")
Copy-IfAbsent (Join-Path $Assets "config/DEV-STANDARDS.md")   (Join-Path $Root "docs/implr/config/DEV-STANDARDS.md")
Copy-IfAbsent (Join-Path $Assets "templates/CLAUDE-template.md") (Join-Path $Root "CLAUDE.md")

# interactive config seeding
$conf = Join-Path $Root "docs/implr/config/implr.config.yaml"
if ((Test-Path $conf) -and (Select-String -Path $conf -Pattern "REPLACE_ME" -Quiet)) {
  Write-Host ""
  $pname = Read-Host "Project name"
  $pstack = Read-Host "Stack hint (e.g. TypeScript, NestJS, PostgreSQL)"
  if ($pname) {
    (Get-Content $conf) -replace "name: REPLACE_ME", "name: $pname" | Set-Content $conf
    $claude = Join-Path $Root "CLAUDE.md"
    if (Test-Path $claude) { (Get-Content $claude) -replace "REPLACE_ME", "$pname" | Set-Content $claude }
  }
  if ($pstack) {
    (Get-Content $conf) -replace 'stack_hint: "REPLACE_ME"', "stack_hint: `"$pstack`"" | Set-Content $conf
  }
}

Write-Host ""
Write-Host "==============================================="
Write-Host "implr installed."
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Fill in [FILL IN] sections of docs/implr/config/DEV-STANDARDS.md"
Write-Host "  2. Add documentation to docs/kb/ (md, pdf, docx, xlsx, csv, txt)"
Write-Host "  3. In Claude Code, run: /doc-ingest"
Write-Host "  4. Then: /arch-gen   and   /ba-requirements-gen"
Write-Host "==============================================="
