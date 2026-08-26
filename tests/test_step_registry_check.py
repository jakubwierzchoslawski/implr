import json
import os

import pytest

from implr_validate.checks import check_step_registry
from implr_validate.contracts import load_contracts

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def contracts():
    return load_contracts(os.path.join(REPO, "plugin", "schemas"))


def _write(root, steps):
    schema_dir = os.path.join(root, "plugin", "schemas")
    os.makedirs(schema_dir, exist_ok=True)
    with open(os.path.join(schema_dir, "step-registry.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps}, f)


def _skill(root, name):
    d = os.path.join(root, "plugin", "skills", name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: %s\n---\n" % name)


def _agent(root, name):
    d = os.path.join(root, "plugin", "agents")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "%s.md" % name), "w", encoding="utf-8") as f:
        f.write("---\nname: %s\n---\n" % name)


BASE = {
    "id": "doc-ingest", "kind": "skill", "label": "Document Ingestion", "phase": "discovery",
    "skill": "doc-ingest",
    "args_allowed": [{"flag": "--dry-run", "takes_value": False, "note": ""}],
    "args_default": [], "interactive": False,
    "agents": [], "consumes": [], "produces": [], "produces_artefact": None,
    "description": "d",
}


def test_valid_registry_has_no_findings(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [BASE])
    _skill(root, "doc-ingest")

    assert check_step_registry(root, contracts) == []


def test_missing_registry_file_is_not_an_error(tmp_path, contracts):
    """The registry is optional for repos that predate implr Studio."""
    assert check_step_registry(str(tmp_path), contracts) == []


def test_planned_step_is_info_not_error(tmp_path, contracts):
    """Designing ahead of implementation must not fail the build."""
    root = str(tmp_path)
    _write(root, [dict(BASE, id="sec-review", skill="sec-review", phase="verify")])
    os.makedirs(os.path.join(root, "plugin", "skills"), exist_ok=True)

    findings = check_step_registry(root, contracts)

    assert len(findings) == 1
    assert findings[0].level == "info"
    assert "sec-review" in findings[0].message


def test_malformed_json_is_an_error_not_a_crash(tmp_path, contracts):
    root = str(tmp_path)
    schema_dir = os.path.join(root, "plugin", "schemas")
    os.makedirs(schema_dir)
    with open(os.path.join(schema_dir, "step-registry.json"), "w", encoding="utf-8") as f:
        f.write("{not json")

    assert check_step_registry(root, contracts)[0].level == "error"


def test_bare_string_args_allowed_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, args_allowed=["--dry-run"])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "objects" in findings[0].message


def test_value_taking_arg_without_a_pattern_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, args_allowed=[{"flag": "--file", "takes_value": True, "note": ""}])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "value_pattern" in findings[0].message


def test_agent_without_a_definition_is_an_error(tmp_path, contracts):
    """A step that dispatches a non-existent agent renders a control that configures nothing."""
    root = str(tmp_path)
    _write(root, [dict(BASE, agents=[{"name": "ghost-worker", "fan_out": "1"}])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "ghost-worker" in findings[0].message


def test_declared_agent_with_a_definition_is_fine(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, agents=[{"name": "plan-worker", "fan_out": "1"}])])
    _skill(root, "doc-ingest")
    _agent(root, "plan-worker")

    assert check_step_registry(root, contracts) == []


def test_unknown_produces_artefact_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, produces_artefact="unicorn")])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "unicorn" in findings[0].message


def test_unknown_phase_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, phase="wibble")])
    _skill(root, "doc-ingest")

    assert check_step_registry(root, contracts)[0].level == "error"


def test_duplicate_step_id_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [BASE, dict(BASE)])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "duplicate step id" in findings[0].message


def test_args_default_naming_an_unknown_flag_is_an_error(tmp_path, contracts):
    root = str(tmp_path)
    _write(root, [dict(BASE, args_default=["--nope"])])
    _skill(root, "doc-ingest")

    findings = check_step_registry(root, contracts)

    assert findings[0].level == "error"
    assert "--nope" in findings[0].message


def test_the_real_repo_registry_passes(contracts):
    """The shipped registry must be valid, with the two planned steps reported as info."""
    findings = check_step_registry(REPO, contracts)

    assert [f for f in findings if f.level == "error"] == []
    planned = {f.message for f in findings if f.level == "info"}
    assert any("qa-testing" in m for m in planned)
    assert any("sec-review" in m for m in planned)
