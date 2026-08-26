import json
from pathlib import Path

import pytest

from implr_studio import registry, serialize


@pytest.fixture
def reg(tmp_path: Path) -> registry.Registry:
    schema_dir, skills_dir = tmp_path / "schemas", tmp_path / "skills"
    schema_dir.mkdir(parents=True)
    steps = [
        {"id": "doc-ingest", "kind": "skill", "label": "Document Ingestion", "phase": "discovery",
         "skill": "doc-ingest",
         "args_allowed": [{"flag": "--dry-run", "takes_value": False, "note": "n"}],
         "args_default": [], "interactive": False,
         "agents": [{"name": "doc-ingest-digester", "fan_out": "1 per doc"}],
         "consumes": [{"path": "docs/kb/**", "note": ""}],
         "produces": [{"path": "docs/implr/kb-index/master-synthesis.md", "note": ""}],
         "produces_artefact": None, "description": "d"},
        {"id": "sec-review", "kind": "skill", "label": "Security Checks", "phase": "verify",
         "skill": "sec-review", "args_allowed": [], "args_default": [],
         "interactive": False, "agents": [], "consumes": [], "produces": [],
         "produces_artefact": None, "description": "planned"},
    ]
    (schema_dir / "step-registry.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    (skills_dir / "doc-ingest").mkdir(parents=True)
    (skills_dir / "doc-ingest" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return registry.load_registry(schema_dir, skills_dir)


def test_step_to_dict_exposes_availability(reg):
    steps = {s["id"]: s for s in serialize.registry_to_dict(reg)["steps"]}

    assert steps["doc-ingest"]["available"] is True
    assert steps["sec-review"]["available"] is False


def test_arg_specs_serialise_as_objects(reg):
    steps = {s["id"]: s for s in serialize.registry_to_dict(reg)["steps"]}

    assert steps["doc-ingest"]["args_allowed"] == [
        {"flag": "--dry-run", "takes_value": False, "value_pattern": None, "note": "n"},
    ]


def test_agents_and_io_serialise(reg):
    steps = {s["id"]: s for s in serialize.registry_to_dict(reg)["steps"]}

    assert steps["doc-ingest"]["agents"] == [
        {"name": "doc-ingest-digester", "fan_out": "1 per doc"}]
    assert steps["doc-ingest"]["consumes"][0]["path"] == "docs/kb/**"
    assert steps["doc-ingest"]["produces_artefact"] is None


def test_registry_to_dict_includes_phase_and_tier_order(reg):
    body = serialize.registry_to_dict(reg)

    assert body["phases"] == list(registry.PHASES)
    assert body["tiers"] == list(registry.TIERS)


def test_registry_to_dict_is_json_serializable(reg):
    json.dumps(serialize.registry_to_dict(reg))


def test_steps_keep_registry_order(reg):
    """Palette grouping relies on phase, but within a phase, file order is the order."""
    ids = [s["id"] for s in serialize.registry_to_dict(reg)["steps"]]

    assert ids == ["doc-ingest", "sec-review"]


def test_project_to_dict_exposes_no_filesystem_path(tmp_path: Path):
    """A project carries a workspace path internally. Serialising it would hand a
    client the one thing no route may return."""
    from implr_studio.context import ProjectRef

    project = ProjectRef(id="local", tenant_id="local", slug="acme", workspace=tmp_path)
    body = serialize.project_to_dict(project)

    assert body == {"id": "local", "slug": "acme", "name": "acme"}
    assert str(tmp_path) not in json.dumps(body)
