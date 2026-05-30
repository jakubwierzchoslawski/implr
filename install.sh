#!/usr/bin/env bash
# implr installer (Linux / generic bash)
#
# Usage:
#   ./install.sh            install skills to ./.claude/skills and scaffold ./docs/implr
#   ./install.sh --global   install skills to ~/.claude/skills (scaffold still targets ./)
#   ./install.sh --skills-only   install skills only, no project scaffold
#
# Run from your project root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"
AGENTS_SRC="$SCRIPT_DIR/.claude/agents"
SKILLS=(implr-init doc-ingest arch-gen ba-requirements-gen ba-cr dev-planner dev-executor dev-code-review)

GLOBAL=false
SKILLS_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --global) GLOBAL=true ;;
    --skills-only) SKILLS_ONLY=true ;;
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
  if [ ! -d "$SKILLS_SRC/$s" ]; then echo "Missing skill source: $s"; exit 1; fi
  rm -rf "${SKILLS_DEST:?}/$s"
  cp -r "$SKILLS_SRC/$s" "$SKILLS_DEST/$s"
  echo "  installed $s"
done

mkdir -p "$AGENTS_DEST"
cp -r "$AGENTS_SRC/." "$AGENTS_DEST/"
AGENT_COUNT=$(find "$AGENTS_DEST" -maxdepth 1 -name "*.md" | wc -l | tr -d ' ')
echo "  installed $AGENT_COUNT agents -> $AGENTS_DEST"

if [ "$SKILLS_ONLY" = true ]; then
  echo "Skills and agents installed. Run /implr-init inside Claude Code to scaffold the project."
  exit 0
fi

ASSETS="$SKILLS_SRC/implr-init/assets"
ROOT="$(pwd)"

echo ""
echo "Scaffolding project workspace under $ROOT/docs"

mkdir -p \
  "$ROOT/docs/kb" \
  "$ROOT/docs/kb/change-requests" \
  "$ROOT/docs/implr/config" \
  "$ROOT/docs/implr/schemas" \
  "$ROOT/docs/implr/templates" \
  "$ROOT/docs/implr/kb-index/cache" \
  "$ROOT/docs/implr/kb-index/digests/per-doc" \
  "$ROOT/docs/implr/kb-index/domains" \
  "$ROOT/docs/implr/requirements/functional" \
  "$ROOT/docs/implr/requirements/non-functional" \
  "$ROOT/docs/implr/plans/functional" \
  "$ROOT/docs/implr/plans/non-functional" \
  "$ROOT/docs/implr/reviews"

# keep empty managed dirs under git
for d in \
  "$ROOT/docs/kb" \
  "$ROOT/docs/implr/kb-index/cache" \
  "$ROOT/docs/implr/kb-index/digests/per-doc" \
  "$ROOT/docs/implr/kb-index/domains" \
  "$ROOT/docs/implr/requirements/functional" \
  "$ROOT/docs/implr/requirements/non-functional" \
  "$ROOT/docs/implr/plans/functional" \
  "$ROOT/docs/implr/plans/non-functional" \
  "$ROOT/docs/implr/reviews"; do
  [ -f "$d/.gitkeep" ] || touch "$d/.gitkeep"
done

# schemas + templates: plugin-owned, always refreshed
cp -f "$ASSETS"/schemas/*.md "$ROOT/docs/implr/schemas/"
cp -f "$ASSETS"/templates/*.md "$ROOT/docs/implr/templates/"
echo "  schemas and templates copied"

# config + DEV-STANDARDS + CLAUDE: user-owned, never overwrite
copy_if_absent() {
  if [ ! -f "$2" ]; then cp "$1" "$2"; echo "  created $2"; else echo "  kept existing $2"; fi
}
copy_if_absent "$ASSETS/config/implr.config.yaml" "$ROOT/docs/implr/config/implr.config.yaml"
copy_if_absent "$ASSETS/config/DEV-STANDARDS.md"   "$ROOT/docs/implr/config/DEV-STANDARDS.md"
copy_if_absent "$ASSETS/templates/CLAUDE-template.md" "$ROOT/CLAUDE.md"

# interactive config seeding (best-effort)
CONF="$ROOT/docs/implr/config/implr.config.yaml"
if grep -q "REPLACE_ME" "$CONF" 2>/dev/null; then
  echo ""
  read -r -p "Project name: " PNAME || PNAME=""
  read -r -p "Stack hint (e.g. TypeScript, NestJS, PostgreSQL): " PSTACK || PSTACK=""
  if [ -n "$PNAME" ]; then
    sed -i.bak "s|name: REPLACE_ME|name: $PNAME|" "$CONF" && rm -f "$CONF.bak"
    # also fill CLAUDE.md project name
    [ -f "$ROOT/CLAUDE.md" ] && sed -i.bak "s|REPLACE_ME|$PNAME|" "$ROOT/CLAUDE.md" && rm -f "$ROOT/CLAUDE.md.bak"
  fi
  if [ -n "$PSTACK" ]; then
    sed -i.bak "s|stack_hint: \"REPLACE_ME\"|stack_hint: \"$PSTACK\"|" "$CONF" && rm -f "$CONF.bak"
  fi
fi

echo ""
echo "==============================================="
echo "implr installed."
echo "  .claude/skills/ and .claude/agents/ are ready."
echo ""
echo "Next steps:"
echo "  1. Fill in [FILL IN] sections of docs/implr/config/DEV-STANDARDS.md"
echo "  2. Add documentation to docs/kb/ (md, pdf, docx, xlsx, csv, txt)"
echo "  3. In Claude Code, run: /doc-ingest"
echo "  4. Then: /arch-gen   and   /ba-requirements-gen"
echo "==============================================="
