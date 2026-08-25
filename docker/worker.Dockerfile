# implr Studio — run worker image.
#
# Trust level: LOW. This container executes an LLM agent that runs shell commands
# and writes files. It runs ONE pipeline run and exits.
#
# Everything below follows from that. It has:
#   - no database credentials
#   - no managed identity
#   - no access to any other run's state
#   - a read-only root filesystem except /workspace
#   - egress restricted by the platform to the Anthropic API and the git remote
#
# It receives its work as a signed job payload and reports progress back over a
# callback endpoint scoped to a single run id. See "Isolation" in
# docs/superpowers/specs/2026-08-25-implr-studio-hosted-design.md.
#
# Build from the repo root:
#   docker build -f docker/worker.Dockerfile -t implr-studio-worker .

# ---------------------------------------------------------------- python deps
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /src

COPY pyproject.toml uv.lock ./
COPY packages/implr_contracts/pyproject.toml packages/implr_contracts/
COPY packages/implr_validate/pyproject.toml  packages/implr_validate/
COPY packages/implr_studio/pyproject.toml    packages/implr_studio/

RUN uv sync --frozen --no-dev --no-install-workspace

COPY packages/ packages/
RUN uv sync --frozen --no-dev


# ---------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    IMPLR_MODE=worker \
    PATH="/venv/bin:$PATH" \
    HOME=/workspace \
    # The Claude Code CLI writes session state under HOME; pointing it at the
    # ephemeral workspace keeps the root filesystem writable-free.
    NPM_CONFIG_UPDATE_NOTIFIER=false

# Unlike the API image, this one genuinely needs a toolchain: git to clone the
# target repository, Node to host the Claude Code CLI, and the ordinary unix
# tools implr skills invoke through Bash.
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
        git \
        ca-certificates \
        curl \
        nodejs \
        npm \
        ripgrep \
 && rm -rf /var/lib/apt/lists/*

# The CLI the SDK drives. Pinned: an unpinned agent runtime is an unreviewed
# change to how every step behaves.
ARG CLAUDE_CLI_VERSION=latest
RUN npm install -g --no-fund --no-audit "@anthropic-ai/claude-code@${CLAUDE_CLI_VERSION}" \
 && npm cache clean --force

RUN groupadd --system --gid 10001 implr \
 && useradd  --system --uid 10001 --gid implr --no-create-home implr

COPY --from=deps /venv /venv

# The plugin payload travels with the image so a run does not depend on the API
# being reachable to obtain builtin skills. Project-scoped custom skills arrive
# in the job payload and are materialised into /workspace/.claude/skills.
COPY --chown=root:root plugin/ /app/plugin/

# The only writable path. Declared as a volume so the platform mounts ephemeral
# storage here and the rest of the filesystem can be read-only.
RUN mkdir -p /workspace && chown implr:implr /workspace
VOLUME ["/workspace"]
WORKDIR /workspace

USER implr

# One run, then exit. The entrypoint clones the ref from the job payload,
# materialises the project's skills and agents, drives the orchestrator, streams
# events to the callback endpoint, and returns a non-zero exit code if the run
# did not reach a terminal success.
ENTRYPOINT ["python", "-m", "implr_studio.worker"]
