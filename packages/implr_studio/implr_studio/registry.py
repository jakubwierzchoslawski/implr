"""Loads the declarative catalogue of pipeline steps.

Adding a step is a registry edit. Nothing here knows the name of any particular
step, agent, or artefact type - those are all data.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

PHASES = ("discovery", "design", "requirements", "planning", "build", "verify")
TIERS = ("haiku", "sonnet", "opus")

# "skill" runs a slash command and the SKILL.md owns the behaviour. "agent" is
# authored in the UI and the studio owns it - Phase 8. Declared here so the field
# is validated from the start rather than retrofitted.
KINDS = ("skill", "agent")

_REQUIRED_FIELDS = (
    "id", "kind", "label", "phase", "skill",
    "args_allowed", "args_default", "interactive",
    "agents", "consumes", "produces", "produces_artefact", "description",
)


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class ArgSpec:
    flag: str
    takes_value: bool
    value_pattern: str | None
    note: str


@dataclass(frozen=True)
class AgentRef:
    name: str
    fan_out: str


@dataclass(frozen=True)
class IOPath:
    path: str
    note: str


@dataclass(frozen=True)
class Step:
    id: str
    kind: str
    label: str
    phase: str
    skill: str
    args_allowed: tuple[ArgSpec, ...]
    args_default: tuple[str, ...]
    interactive: bool
    agents: tuple[AgentRef, ...]
    consumes: tuple[IOPath, ...]
    produces: tuple[IOPath, ...]
    produces_artefact: str | None
    description: str
    available: bool

    @property
    def flags(self) -> tuple[str, ...]:
        return tuple(a.flag for a in self.args_allowed)

    def arg(self, flag: str) -> ArgSpec | None:
        for spec in self.args_allowed:
            if spec.flag == flag:
                return spec
        return None

    def agent_names(self) -> tuple[str, ...]:
        return tuple(a.name for a in self.agents)


@dataclass(frozen=True)
class Registry:
    steps: dict[str, Step]

    def get(self, step_id: str) -> Step | None:
        return self.steps.get(step_id)


def _arg_specs(step_id: str, entries) -> tuple[ArgSpec, ...]:
    specs: list[ArgSpec] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or "flag" not in entry:
            raise RegistryError(
                "step %s: args_allowed entries must be objects with a 'flag' "
                "(bare strings were the pre-configurator format)" % step_id
            )
        flag = entry["flag"]
        if flag in seen:
            raise RegistryError("step %s: duplicate flag %r in args_allowed" % (step_id, flag))
        seen.add(flag)

        takes_value = bool(entry.get("takes_value", False))
        pattern = entry.get("value_pattern")
        if takes_value:
            if not pattern:
                raise RegistryError(
                    "step %s: arg %r takes a value and therefore requires a value_pattern"
                    % (step_id, flag)
                )
            try:
                re.compile(pattern)
            except re.error as e:
                raise RegistryError(
                    "step %s: arg %r value_pattern is not a valid regex: %s" % (step_id, flag, e)
                )
        specs.append(ArgSpec(
            flag=flag,
            takes_value=takes_value,
            value_pattern=pattern if takes_value else None,
            note=entry.get("note", ""),
        ))
    return tuple(specs)


def load_registry(schema_dir: Path, skills_dir: Path) -> Registry:
    path = Path(schema_dir) / "step-registry.json"
    if not path.is_file():
        raise RegistryError("step-registry.json not found at %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except ValueError as e:
        raise RegistryError("step-registry.json at %s is not valid JSON: %s" % (path, e))

    steps: dict[str, Step] = {}
    for entry in raw.get("steps", []):
        for field in _REQUIRED_FIELDS:
            if field not in entry:
                raise RegistryError("missing required field: %s" % field)
        step_id = entry["id"]
        if step_id in steps:
            raise RegistryError("duplicate step id: %s" % step_id)
        if entry["kind"] not in KINDS:
            raise RegistryError(
                "step %s: unknown kind %r (legal: %s)"
                % (step_id, entry["kind"], list(KINDS))
            )
        if entry["phase"] not in PHASES:
            raise RegistryError(
                "step %s: unknown phase %r (legal: %s)"
                % (step_id, entry["phase"], list(PHASES))
            )

        specs = _arg_specs(step_id, entry["args_allowed"])
        by_flag = {s.flag: s for s in specs}
        for arg in entry["args_default"]:
            spec = by_flag.get(arg)
            if spec is None:
                raise RegistryError(
                    "step %s: args_default entry %r not in args_allowed" % (step_id, arg))
            if spec.takes_value:
                raise RegistryError(
                    "step %s: args_default entry %r takes a value, so it cannot be a default"
                    % (step_id, arg))

        artefact = entry["produces_artefact"]
        if artefact is not None and not isinstance(artefact, str):
            raise RegistryError("step %s: produces_artefact must be a string or null" % step_id)

        skill_md = Path(skills_dir) / entry["skill"] / "SKILL.md"
        steps[step_id] = Step(
            id=step_id,
            kind=entry["kind"],
            label=entry["label"],
            phase=entry["phase"],
            skill=entry["skill"],
            args_allowed=specs,
            args_default=tuple(entry["args_default"]),
            interactive=bool(entry["interactive"]),
            agents=tuple(AgentRef(name=a["name"], fan_out=a.get("fan_out", ""))
                         for a in entry["agents"]),
            consumes=tuple(IOPath(path=c["path"], note=c.get("note", ""))
                           for c in entry["consumes"]),
            produces=tuple(IOPath(path=p["path"], note=p.get("note", ""))
                           for p in entry["produces"]),
            produces_artefact=artefact,
            description=entry["description"],
            available=skill_md.is_file(),
        )
    return Registry(steps=steps)
