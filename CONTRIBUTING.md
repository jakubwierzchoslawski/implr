# Contributing to implr

Thanks for your interest in improving implr.

## Repository layout

```
implr/
├── plugin/                     the payload — everything a target project receives
│   ├── skills/                 one folder per skill, each with a SKILL.md
│   │   └── <skill>/phases/     per-skill dispatch prompt templates
│   ├── agents/                 dedicated subagent definitions
│   ├── schemas/                the authoritative contracts
│   ├── templates/              artefact templates seeded into projects
│   ├── config/                 implr.config.yaml, DEV-STANDARDS.md
│   ├── seeds/                  skip-if-exists starter documents
│   └── steps/                  step registry (from Phase 1)
├── packages/
│   └── implr_validate/         the contract validator, an installable package
├── install.sh / .ps1 / .bat    cross-platform installers
├── docs/WORKFLOW.md            internal design deep-dive
├── tests/
├── README.md
├── CHANGELOG.md
└── LICENSE
```

`plugin/` is one directory with one lifecycle: what it contains is exactly what a
target project receives, so a container needs one `COPY` line and "what does a
project get?" is answerable by `ls`.

## Developing implr on implr

`.claude/agents/` is generated. `plugin/agents/` is the source, so a fresh clone has no
agents and no skills registered until you bootstrap:

    bash install.sh            # or: pwsh install.ps1

This copies `plugin/skills/` and `plugin/agents/` into `.claude/`, which is what lets you run
`/dev-executor` on this repository. It also means **the installer is exercised on every
developer setup** — if it breaks, your dev environment breaks, and you find out immediately
rather than when a customer does.

It also installs the validator as a package, so `implr-validate --repo --root .` works
with no `PYTHONPATH`.

## Design principles

1. **Skills are thin.** A skill is an instruction file (SKILL.md). Data — schemas, templates,
   config — lives under `plugin/schemas/`, `plugin/templates/` and `plugin/config/` and is placed into `docs/implr/` at init.
   Skills reference those paths; they do not bundle their own copies.
2. **Schemas are authoritative.** Every data structure is defined once in a schema file that all
   skills reference. Change the schema, not each skill's idea of it.
3. **Incremental by default.** Anything that processes the knowledge base must use checksums to
   avoid reprocessing unchanged inputs.
4. **Humans gate decisions.** Generation is automated; approval, architectural sign-off, and
   design choices remain human.

## Making changes

### Editing a skill
Edit `plugin/skills/<name>/SKILL.md`. The frontmatter `description` controls when Claude Code triggers
the skill — keep its trigger phrases accurate. In PRs that change behaviour, include a
before/after example of the skill's output.

### Editing schemas or templates
Edit the files under `plugin/schemas/`, `plugin/templates/` and `plugin/config/`. Remember these are copied into every project on
install/init, so changes are breaking if they alter the structure downstream skills parse.

### Adding a skill
1. Create `plugin/skills/<name>/SKILL.md`.
2. Add any schemas, templates or seeds under `plugin/`.
3. Add the skill name to all three installers' skill lists.
4. Add it to the README skills table and command reference.
5. Validate the skill before opening the PR.

## Validation

Skills must have valid YAML frontmatter with `name` and `description`. Validate with the
skill-creator tooling, or ensure `SKILL.md` parses and the description is under the length limit.

## Authoring a dedicated subagent (v2.0+)

Dedicated subagents live at `plugin/agents/<agent-name>.md`. Each is a Markdown file with
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
id). The full phase instructions live in `plugin/skills/<skill>/phases/<phase>.md`.

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

- File path: `plugin/skills/<skill>/phases/<phase-name>.md`
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
