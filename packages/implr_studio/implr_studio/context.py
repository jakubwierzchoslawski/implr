"""The wired-up dependency bundle, built once at startup and injected everywhere.

Nothing in the API layer reaches for a global. Tests build a context pointed at a
temp workspace and get a fully functional app. It grows one field per phase: the
pipeline path in Phase 2, the store and orchestrator in Phase 9.
"""
from dataclasses import dataclass, field
from pathlib import Path

from .authz import LOCAL_TENANT, LocalPolicy, Policy
from .implr_bridge import resolve_schema_dir
from .registry import Registry, load_registry

LOCAL_PROJECT_ID = "local"


@dataclass(frozen=True)
class ProjectRef:
    """One target project. In local mode there is exactly one, pinned to the
    --workspace directory; a hosted tenant simply has more than one."""
    id: str
    tenant_id: str
    slug: str
    workspace: Path


@dataclass
class AppContext:
    mode: str
    projects: dict[str, ProjectRef]
    registry: Registry
    policy: Policy = field(default_factory=LocalPolicy)

    @property
    def workspace(self) -> Path:
        """The single local project's workspace. Local mode only - hosted routes
        resolve a project per request instead."""
        return next(iter(self.projects.values())).workspace


def build_context(workspace: Path) -> AppContext:
    workspace = Path(workspace).resolve()
    # Both from the WORKSPACE. Availability must be resolved against the target
    # project's installed skills, because the adapter runs with cwd=<workspace>
    # and that is where the CLI resolves a slash command from. Judging it against
    # the plugin source instead would let the palette call a step usable while
    # the agent cannot find it - which is what happens when the backend runs from
    # a different implr checkout than the project was installed from.
    reg = load_registry(
        resolve_schema_dir(workspace),
        workspace / ".claude" / "skills",
    )
    project = ProjectRef(
        id=LOCAL_PROJECT_ID,
        tenant_id=LOCAL_TENANT,
        slug=workspace.name,
        workspace=workspace,
    )
    return AppContext(mode="local", projects={project.id: project}, registry=reg)
