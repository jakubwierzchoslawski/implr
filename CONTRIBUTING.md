# Contributing to implr

Thanks for your interest in improving implr.

## Repository layout

```
implr/
├── skills/                     one folder per skill, each with a SKILL.md
│   ├── <skill>/phases/         per-skill dispatch prompt templates (v2.0)
│   └── implr-init/assets/      schemas, templates, config seeded into projects
├── .claude/agents/             dedicated subagent definitions (v2.0)
├── install.sh / .ps1 / .bat    cross-platform installers
├── docs/WORKFLOW.md            internal design deep-dive
├── README.md
├── CHANGELOG.md
└── LICENSE
```

## Design principles

1. **Skills are thin.** A skill is an instruction file (SKILL.md). Data — schemas, templates,
   config — lives under `skills/implr-init/assets/` and is placed into `docs/implr/` at init.
   Skills reference those paths; they do not bundle their own copies.
2. **Schemas are authoritative.** Every data structure is defined once in a schema file that all
   skills reference. Change the schema, not each skill's idea of it.
3. **Incremental by default.** Anything that processes the knowledge base must use checksums to
   avoid reprocessing unchanged inputs.
4. **Humans gate decisions.** Generation is automated; approval, architectural sign-off, and
   design choices remain human.

## Making changes

### Editing a skill
Edit `skills/<name>/SKILL.md`. The frontmatter `description` controls when Claude Code triggers
the skill — keep its trigger phrases accurate. In PRs that change behaviour, include a
before/after example of the skill's output.

### Editing schemas or templates
Edit the files under `skills/implr-init/assets/`. Remember these are copied into every project on
install/init, so changes are breaking if they alter the structure downstream skills parse.

### Adding a skill
1. Create `skills/<name>/SKILL.md`.
2. Add any assets under `skills/implr-init/assets/`.
3. Add the skill name to all three installers' skill lists.
4. Add it to the README skills table and command reference.
5. Validate the skill before opening the PR.

## Validation

Skills must have valid YAML frontmatter with `name` and `description`. Validate with the
skill-creator tooling, or ensure `SKILL.md` parses and the description is under the length limit.

## Authoring a dedicated subagent (v2.0+)

Dedicated subagents live at `.claude/agents/<agent-name>.md`. Each is a Markdown file with
YAML frontmatter (the contract) and a Markdown body (the agent's system prompt).

### Frontmatter contract

```yaml
---
name: <agent-name>                   # MUST match filename without .md extension
description: <one-line role>         # Used by the Agent tool catalogue
tools: [Read, Write, Bash, ...]      # Allowlist of tools the agent may call
default_model: haiku|sonnet|opus     # Used when implr.config.yaml does not override
---
```

### Authoring guidance

- **One job per agent.** If your agent has two unrelated phases, split it into two.
- **Restrict tools.** Workers that only read should not have Write. Workers that produce
  one file should not have Bash unless the format requires it.
- **Pick the right tier.** Haiku for mechanical extraction/formatting. Sonnet for analytic
  work (digest, synthesis, review). Opus only when judgement under discipline matters
  (TDD, SOLID enforcement).
- **Stable reads first.** The agent body must instruct the agent to read schemas, config,
  and standards BEFORE reading the dynamic input. This is what makes the 5-minute prompt
  cache work across dispatches.
- **Return structured summaries.** Use plain-text `key: value` lines, one per line, so the
  orchestrator can parse without regex gymnastics. List the exact keys in the agent body.

### How orchestrators dispatch

The skill's SKILL.md is the orchestrator. It reads `agents.<agent-name>` from
`implr.config.yaml`, falls back to the agent's `default_model`, and calls the `Agent` tool
with `subagent_type`, `model`, and a small scope payload (e.g. a file path or a requirement
id). The full phase instructions live in `skills/<skill>/phases/<phase>.md`.

## Prompt-cache-friendly ordering

Every SKILL.md and every `phases/*.md` must read stable inputs (schemas, config files)
before dynamic inputs (the file being processed, the requirement being planned, etc.).

This convention exists because Anthropic's 5-minute prompt cache reuses the conversation
prefix across calls. If a skill or phase reads dynamic content first, the cache key
diverges immediately and the prefix isn't reused. The hit is measurable on sessions with
many dispatches.

Pattern:

```markdown
## Read first (cache-friendly)
- docs/implr/schemas/<relevant-schema>.md
- docs/implr/config/implr.config.yaml
- docs/implr/config/DEV-STANDARDS.md  (if behavioural)

## Your scope (dynamic — from the orchestrator)
...

## Task
...
```

## Phase prompt files

Each heavy skill has a `phases/` subfolder. Each file is the dispatch prompt template the
orchestrator sends to a subagent.

- File path: `skills/<skill>/phases/<phase-name>.md`
- Naming: short verb or noun (`extract`, `digest`, `plan-one`, `apply`).
- Content: stable-reads-first block, scope block (with `{{PLACEHOLDERS}}` the orchestrator
  fills), task block, return summary block.

Phase files exist primarily to keep SKILL.md small and prompt-cache friendly. The
authoritative task instructions still live in the agent's system prompt body; the phase
file is the orchestration handle.

## Pull requests

- One logical change per PR.
- Update README.md and CHANGELOG.md when behaviour or commands change.
- For behaviour changes, describe the before and after.
