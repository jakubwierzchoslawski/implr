# implr Studio — API + UI image.
#
# Trust level: HIGH. This container holds the database connection, the managed
# identity, and every project's data. It therefore deliberately does NOT contain
# git, Node, or the Claude Code CLI — it must be incapable of executing a step.
# Run execution happens in worker.Dockerfile, which has the opposite posture.
#
# Build from the repo root:
#   docker build -f docker/api.Dockerfile -t implr-studio-api .

# ---------------------------------------------------------------- web bundle
FROM node:22-alpine AS web

WORKDIR /build

# Manifests first so a source-only change does not re-resolve dependencies.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build          # tsc -b && vite build  ->  /build/dist


# ---------------------------------------------------------------- python deps
FROM python:3.12-slim AS deps

# uv rather than pip: it resolves the workspace from uv.lock in one frozen step,
# so the image is reproducible and there is exactly one lock for the repo.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/venv \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /src

# Manifests and lock only, so this layer caches across source edits.
COPY pyproject.toml uv.lock ./
COPY packages/implr_contracts/pyproject.toml packages/implr_contracts/
COPY packages/implr_validate/pyproject.toml  packages/implr_validate/
COPY packages/implr_studio/pyproject.toml    packages/implr_studio/

RUN uv sync --frozen --no-dev --no-install-workspace

# Now the sources, and install the workspace packages themselves.
COPY packages/ packages/
RUN uv sync --frozen --no-dev


# ---------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    IMPLR_MODE=hosted \
    PATH="/venv/bin:$PATH"

# Non-root. Hosted mode adds a read-only root filesystem on top of this at the
# Container Apps level; nothing here writes outside /tmp.
RUN groupadd --system --gid 10001 implr \
 && useradd  --system --uid 10001 --gid implr --no-create-home implr

WORKDIR /app

COPY --from=deps /venv /venv

# The plugin payload: builtin skills, agents, steps, templates, seeds. Read at
# boot and synced into the database — see "Skills and agents: database as
# source, disk as projection" in the hosted design spec. Read-only here.
COPY --chown=root:root plugin/ /app/plugin/

# The built SPA, served by the same process at /.
COPY --from=web --chown=root:root /build/dist /app/web/dist

USER implr

EXPOSE 8000

# No git, no node, no claude CLI on PATH — asserted by a test, because the
# separation is a security property rather than a packaging accident.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status==200 else 1)"

# Bind 0.0.0.0 inside the container only. The container is not the network
# boundary — Container Apps ingress is, and it terminates TLS and enforces
# Entra auth in front of this. Local mode never uses this image.
CMD ["uvicorn", "implr_studio.asgi:app", \
     "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
