# Contributing to implr

Thanks for your interest in improving implr.

## Repository layout

```
implr/
├── skills/                     one folder per skill, each with a SKILL.md
│   └── implr-init/assets/      schemas, templates, config seeded into projects
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

## Pull requests

- One logical change per PR.
- Update README.md and CHANGELOG.md when behaviour or commands change.
- For behaviour changes, describe the before and after.
