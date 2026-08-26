"""The payload contract: one directory, complete, and nothing stale outside it."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"

SKILLS = ["implr-init", "doc-ingest", "arch-gen", "ba-requirements-gen",
          "ba-cr", "dev-planner", "dev-executor", "dev-code-review"]

AGENTS = ["arch-drafter", "arch-excerpter", "code-review-worker", "cr-applier",
          "cr-impact-analyzer", "doc-ingest-digester", "doc-ingest-synthesizer",
          "plan-runner", "plan-worker", "requirements-domain-worker", "task-executor"]


def test_every_skill_moved():
    for name in SKILLS:
        assert (PLUGIN / "skills" / name / "SKILL.md").is_file(), name
    assert len(list((PLUGIN / "skills").iterdir())) == len(SKILLS)


def test_every_agent_moved():
    for name in AGENTS:
        assert (PLUGIN / "agents" / ("%s.md" % name)).is_file(), name
    assert len(list((PLUGIN / "agents").glob("*.md"))) == len(AGENTS)


def test_the_contracts_moved():
    schemas = PLUGIN / "schemas"

    assert (schemas / "status-vocabulary.json").is_file()
    assert (schemas / "frontmatter-rules.json").is_file()
    assert len(list(schemas.glob("*.json"))) == 2
    assert len(list(schemas.glob("*.md"))) == 8


def test_templates_config_and_seeds_moved():
    assert len(list((PLUGIN / "templates").glob("*.md"))) == 8
    assert (PLUGIN / "config" / "implr.config.yaml").is_file()
    assert (PLUGIN / "config" / "DEV-STANDARDS.md").is_file()
    assert len(list((PLUGIN / "seeds").iterdir())) == 4


def test_the_old_locations_are_gone():
    """A stale copy is a second source of truth that nobody edits and everybody reads."""
    assert not (REPO / "skills").exists()
    assert not (REPO / "scaffold").exists()


def test_dot_claude_agents_is_generated_not_tracked():
    """plugin/agents is the source; .claude/agents is bootstrap output."""
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")

    assert ".claude/agents/" in ignore


def test_the_payload_is_one_copy_operation():
    """The container does `COPY plugin/ /app/plugin/`. Anything outside it that a
    target project needs breaks that, so assert the set of top-level entries."""
    entries = {p.name for p in PLUGIN.iterdir() if not p.name.startswith(".")}

    assert entries == {"skills", "agents", "steps", "schemas", "templates", "config", "seeds"}
