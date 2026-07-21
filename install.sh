#!/usr/bin/env bash
# implr installer (macOS / Linux)
#
# Usage:
#   ./install.sh            install skills + agents to ./.claude/
#   ./install.sh --global   install skills + agents to ~/.claude/
#
# Run from your project root, then run /implr-init inside Claude Code.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"
AGENTS_SRC="$SCRIPT_DIR/.claude/agents"
SCAFFOLD_SRC="$SCRIPT_DIR/scaffold"
VALIDATE_SRC="$SCRIPT_DIR/scripts/implr_validate"
SKILLS=(implr-init doc-ingest arch-gen ba-requirements-gen ba-cr dev-planner dev-executor dev-code-review)

GLOBAL=false
for arg in "$@"; do
  case "$arg" in
    --global) GLOBAL=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

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
  cp -f "$SCAFFOLD_SRC"/schemas/*.json "docs/implr/schemas/"
  cp -f "$SCAFFOLD_SRC"/templates/*.md "docs/implr/templates/"
  echo "  schemas and templates installed"

  # Always overwrite: implr_validate tool (plugin-owned)
  mkdir -p "scripts/implr_validate"
  cp -f "$VALIDATE_SRC"/*.py "scripts/implr_validate/"
  echo "  implr_validate tool installed"

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

  # Skip if exists: resolved-contradictions.md seed
  if [ ! -f "docs/implr/requirements/resolved-contradictions.md" ]; then
    cp "$SCAFFOLD_SRC/seeds/resolved-contradictions.md" "docs/implr/requirements/resolved-contradictions.md"
    echo "  created docs/implr/requirements/resolved-contradictions.md"
  else
    echo "  kept existing docs/implr/requirements/resolved-contradictions.md"
  fi

  # Skip if exists: DOD.md seed
  if [ ! -f "docs/implr/DOD.md" ]; then
    cp "$SCRIPT_DIR/scaffold/seeds/DOD.md" "docs/implr/DOD.md"
    echo "  created docs/implr/DOD.md"
  else
    echo "  kept existing docs/implr/DOD.md"
  fi

  echo "  workspace scaffolded"
}

if [ "$GLOBAL" = true ]; then
  SKILLS_DEST="$HOME/.claude/skills"
  AGENTS_DEST="$HOME/.claude/agents"
else
  SKILLS_DEST="$(pwd)/.claude/skills"
  AGENTS_DEST="$(pwd)/.claude/agents"
fi

echo "implr installer"
echo "==============="
echo "Skills -> $SKILLS_DEST"
echo "Agents -> $AGENTS_DEST"

mkdir -p "$SKILLS_DEST"
for s in "${SKILLS[@]}"; do
  if [ ! -d "$SKILLS_SRC/$s" ]; then echo "ERROR: Missing skill source: $s"; exit 1; fi
  rm -rf "${SKILLS_DEST:?}/$s"
  cp -r "$SKILLS_SRC/$s" "$SKILLS_DEST/$s"
  echo "  installed $s"
done

if [ ! -d "$AGENTS_SRC" ]; then echo "ERROR: Missing agents source: $AGENTS_SRC"; exit 1; fi
if [ ! -d "$SCAFFOLD_SRC" ]; then echo "ERROR: Missing scaffold source: $SCAFFOLD_SRC"; exit 1; fi
if [ ! -d "$VALIDATE_SRC" ]; then echo "ERROR: Missing implr_validate source: $VALIDATE_SRC"; exit 1; fi
mkdir -p "$AGENTS_DEST"
cp -f "$AGENTS_SRC/"*.md "$AGENTS_DEST/"
echo "  installed agents"

# Remove deprecated executor-worker.md if present
if [ -f "$AGENTS_DEST/executor-worker.md" ]; then
    rm -f "$AGENTS_DEST/executor-worker.md"
    echo "  removed deprecated agent: executor-worker.md (replaced by plan-runner.md in v3)"
fi

# Workspace scaffolding always targets the current project (CWD), regardless of --global.
scaffold_workspace

echo ""
echo "==============================================="
echo "implr installed."
echo "  Skills and agents are in .claude/"
echo ""
echo "Next step:"
echo "  Open your project in Claude Code and run: /implr-init"
echo "  This configures your project name, stack, and standards."
echo "==============================================="
