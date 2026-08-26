"""Pure dict conversions for API responses. No FastAPI imports belong here."""
from .registry import PHASES, TIERS, Registry, Step


def step_to_dict(step: Step) -> dict:
    return {
        "id": step.id,
        "kind": step.kind,
        "label": step.label,
        "phase": step.phase,
        "skill": step.skill,
        "args_allowed": [
            {
                "flag": a.flag,
                "takes_value": a.takes_value,
                "value_pattern": a.value_pattern,
                "note": a.note,
            }
            for a in step.args_allowed
        ],
        "args_default": list(step.args_default),
        "interactive": step.interactive,
        "agents": [{"name": a.name, "fan_out": a.fan_out} for a in step.agents],
        "consumes": [{"path": p.path, "note": p.note} for p in step.consumes],
        "produces": [{"path": p.path, "note": p.note} for p in step.produces],
        "produces_artefact": step.produces_artefact,
        "description": step.description,
        "available": step.available,
    }


def registry_to_dict(reg: Registry) -> dict:
    # The whole registry is served now, even though the UI renders only a slice
    # of it until Phase 7. Serving the complete record avoids growing this
    # payload - and its tests - five separate times.
    return {
        "steps": [step_to_dict(s) for s in reg.steps.values()],
        "phases": list(PHASES),
        "tiers": list(TIERS),
    }


def project_to_dict(project) -> dict:
    # Deliberately NOT project.workspace. A ProjectRef carries the path because
    # the orchestrator needs it; handing it to a client would be the one thing no
    # route may return.
    return {"id": project.id, "slug": project.slug, "name": project.slug}
