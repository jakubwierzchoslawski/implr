"""The authorization seam.

Every route calls authorize(), from Phase 1, even in local mode where the policy
always says yes. Two reasons this exists before it is needed:

  - The permission verbs are named in full from the start. Naming them later means
    revisiting every call site to decide which verb it meant, which is exactly the
    audit the seam exists to prevent.
  - Phase 17 swaps LocalPolicy for a tenant-aware policy and no route changes.

A test walks the FastAPI route table and fails on any handler that does not call
authorize. /api/health is the one documented exemption: it is the container
liveness probe, and a probe that needs a token cannot report that the token
service is down.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

LOCAL_TENANT = "local"


class Permission(str, Enum):
    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"
    RUN_START = "run.start"
    RUN_CONTROL = "run.control"
    STEP_AUTHOR = "step.author"
    SKILL_AUTHOR = "skill.author"
    TENANT_ADMIN = "tenant.admin"


class Forbidden(Exception):
    """The policy refused. Surfaced as 403 by an exception handler in api.py."""


@dataclass(frozen=True)
class Principal:
    id: str
    tenant_id: str
    display_name: str


def local_principal() -> Principal:
    """Local mode is a single implicit tenant: one tenant, one user, one project.
    Nothing about it is special-cased in the routes - it is the degenerate case of
    the same model, which is what keeps the two modes from drifting."""
    return Principal(id="local", tenant_id=LOCAL_TENANT, display_name="local operator")


class Policy(Protocol):
    def allows(self, principal: Principal, permission: Permission, project=None) -> bool:
        ...


class LocalPolicy:
    """Loopback, one operator, no auth. Everything is permitted.

    The value is not the answer but the call site: by Phase 17 every route already
    states which permission it needs and against which project.
    """

    def allows(self, principal: Principal, permission: Permission, project=None) -> bool:
        return True


def authorize(principal: Principal, permission: Permission, project=None,
              policy: Policy | None = None) -> None:
    """Raise Forbidden unless the policy permits this principal that permission.

    policy is injected by the caller (the route reads it off the AppContext) and
    defaults to LocalPolicy so a test can call this without wiring a context.
    """
    if not (policy or LocalPolicy()).allows(principal, permission, project):
        raise Forbidden(
            "%s is not permitted %s" % (principal.id, permission.value))
