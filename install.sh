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
SKILLS=(implr-init doc-ingest arch-gen ba-requirements-gen ba-cr dev-planner dev-executor dev-code-review)

GLOBAL=false
for arg in "$@"; do
  case "$arg" in
    --global) GLOBAL=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

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
mkdir -p "$AGENTS_DEST"
cp -f "$AGENTS_SRC/"*.md "$AGENTS_DEST/"
echo "  installed agents"

echo ""
echo "==============================================="
echo "implr installed."
echo "  Skills and agents are in .claude/"
echo ""
echo "Next step:"
echo "  Open your project in Claude Code and run: /implr-init"
echo "  This scaffolds docs/implr/ and sets up your config."
echo "==============================================="
