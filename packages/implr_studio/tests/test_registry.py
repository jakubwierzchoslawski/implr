import json
from pathlib import Path

import pytest

from implr_studio import registry


def _write(schema_dir: Path, steps: list[dict]) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "step-registry.json").write_text(
        json.dumps({"steps": steps}), encoding="utf-8")


def _skill(skills_dir: Path, name: str) -> None:
    (skills_dir / name).mkdir(parents=True, exist_ok=True)
    (skills_dir / name / "SKILL.md").write_text("---\nname: %s\n---\n" % name, encoding="utf-8")


BASE = {
    "id": "doc-ingest",
    "kind": "skill",
    "label": "Document Ingestion",
    "phase": "discovery",
    "skill": "doc-ingest",
    "args_allowed": [
        {"flag": "--registry-only", "takes_value": False, "note": "fast scan"},
        {"flag": "--file", "takes_value": True,
         "value_pattern": "^[A-Za-z0-9._/-]{1,200}$", "note": "one document"},
    ],
    "args_default": [],
    "interactive": False,
    "agents": [{"name": "doc-ingest-digester", "fan_out": "1 per changed doc"}],
    "consumes": [{"path": "docs/kb/**", "note": "18 formats"}],
    "produces": [{"path": "docs/implr/kb-index/master-synthesis.md", "note": ""}],
    "produces_artefact": None,
    "description": "Indexes and digests the knowledge base.",
}


def test_loads_a_step(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.label == "Document Ingestion"
    assert step.phase == "discovery"
    assert step.flags == ("--registry-only", "--file")
    assert step.interactive is False


def test_step_is_available_when_the_skill_exists(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    assert registry.load_registry(schema_dir, skills_dir).get("doc-ingest").available is True


def test_step_is_unavailable_when_the_skill_is_missing(tmp_path: Path):
    """A planned step is not an error - it renders dashed in the palette."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, id="sec-review", skill="sec-review", phase="verify")])
    skills_dir.mkdir(parents=True)

    assert registry.load_registry(schema_dir, skills_dir).get("sec-review").available is False


def test_arg_specs_carry_value_metadata(tmp_path: Path):
    """A flat flag whitelist cannot express --file <path>. This is why args are objects."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.arg("--registry-only").takes_value is False
    assert step.arg("--file").takes_value is True
    assert step.arg("--file").value_pattern == "^[A-Za-z0-9._/-]{1,200}$"
    assert step.arg("--nope") is None


def test_value_taking_arg_without_a_pattern_rejected(tmp_path: Path):
    """An unvalidated value is the one way a path reaches an argv vector unchecked."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=[
        {"flag": "--file", "takes_value": True, "note": ""}])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="--file.*requires a value_pattern"):
        registry.load_registry(schema_dir, skills_dir)


def test_invalid_value_pattern_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=[
        {"flag": "--file", "takes_value": True, "value_pattern": "([unclosed", "note": ""}])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="not a valid regex"):
        registry.load_registry(schema_dir, skills_dir)


def test_bare_string_args_allowed_rejected(tmp_path: Path):
    """Refuse the pre-configurator format loudly rather than loading empty arg specs."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=["--dry-run"])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="must be objects"):
        registry.load_registry(schema_dir, skills_dir)


def test_duplicate_flag_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_allowed=[
        {"flag": "--dry-run", "takes_value": False, "note": ""},
        {"flag": "--dry-run", "takes_value": False, "note": ""}])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="duplicate flag"):
        registry.load_registry(schema_dir, skills_dir)


def test_args_default_must_name_an_allowed_flag(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_default=["--nope"])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError,
                       match="args_default entry '--nope' not in args_allowed"):
        registry.load_registry(schema_dir, skills_dir)


def test_args_default_cannot_name_a_value_taking_flag(tmp_path: Path):
    """A default cannot supply a value, so it must not select a flag that needs one."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, args_default=["--file"])])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="args_default entry '--file' takes a value"):
        registry.load_registry(schema_dir, skills_dir)


def test_agents_load_in_dispatch_order(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, agents=[
        {"name": "arch-excerpter", "fan_out": "1 per plan"},
        {"name": "plan-runner", "fan_out": "1 per plan, cap 5"},
        {"name": "task-executor", "fan_out": "1 per task"}])])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.agent_names() == ("arch-excerpter", "plan-runner", "task-executor")
    assert step.agents[1].fan_out == "1 per plan, cap 5"


def test_duplicate_step_id_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE, dict(BASE)])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="duplicate step id: doc-ingest"):
        registry.load_registry(schema_dir, skills_dir)


def test_unknown_phase_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, phase="wibble")])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="unknown phase 'wibble'"):
        registry.load_registry(schema_dir, skills_dir)


def test_kind_is_loaded(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [BASE])
    _skill(skills_dir, "doc-ingest")

    step = registry.load_registry(schema_dir, skills_dir).get("doc-ingest")

    assert step.kind == "skill"


def test_unknown_kind_rejected(tmp_path: Path):
    """Phase 8 adds 'agent'. Anything else is a typo, now and then."""
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [dict(BASE, kind="wizard")])
    _skill(skills_dir, "doc-ingest")

    with pytest.raises(registry.RegistryError, match="unknown kind 'wizard'"):
        registry.load_registry(schema_dir, skills_dir)


def test_missing_required_field_rejected(tmp_path: Path):
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    _write(schema_dir, [{k: v for k, v in BASE.items() if k != "skill"}])
    skills_dir.mkdir(parents=True)

    with pytest.raises(registry.RegistryError, match="missing required field: skill"):
        registry.load_registry(schema_dir, skills_dir)


# --- against the real shipped file -----------------------------------------

def _shipped():
    """The plugin payload: plugin/schemas is the catalogue, plugin/skills the
    availability source. Both moved there in Phase -1."""
    from implr_studio import implr_bridge

    root = implr_bridge.repo_root()
    return root, registry.load_registry(root / "plugin" / "schemas", root / "plugin" / "skills")


def test_every_shipped_step_is_kind_skill():
    """The plugin registry declares only skill-backed steps. Agent-backed ones
    are project-owned and live in steps.yaml from Phase 8."""
    _, reg = _shipped()

    assert {s.kind for s in reg.steps.values()} == {"skill"}


def test_shipped_registry_is_valid():
    _, reg = _shipped()

    assert len(reg.steps) == 9
    assert reg.get("doc-ingest").available is True
    assert reg.get("dev-executor").available is True
    assert reg.get("qa-testing").available is False
    assert reg.get("sec-review").available is False


def test_shipped_registry_agents_all_exist():
    """Every agent a step claims to dispatch must have a definition."""
    root, reg = _shipped()

    for step in reg.steps.values():
        for agent in step.agents:
            assert (root / "plugin" / "agents" / ("%s.md" % agent.name)).is_file(), (
                "step %s claims agent %s, which has no definition" % (step.id, agent.name))


def test_shipped_registry_artefacts_are_real_types():
    """produces_artefact must name a frontmatter-rules.json artefact type."""
    from implr_studio import implr_bridge

    root, reg = _shipped()
    contracts = implr_bridge.load_contracts(str(implr_bridge.resolve_schema_dir(root)))

    for step in reg.steps.values():
        if step.produces_artefact is not None:
            assert step.produces_artefact in contracts.artefact_types


def test_shipped_registry_flags_exist_in_their_skills():
    """A flag the palette offers must be one the skill actually documents."""
    root, reg = _shipped()

    for step in reg.steps.values():
        if not step.available:
            continue
        text = (root / "plugin" / "skills" / step.skill / "SKILL.md").read_text(encoding="utf-8")
        for flag in step.flags:
            assert flag in text, "step %s offers %s, absent from its SKILL.md" % (step.id, flag)
