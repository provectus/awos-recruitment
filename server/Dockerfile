# ---- Builder stage ----
# Installs dependencies and pre-downloads the ONNX embedding model
# so the runtime image can start without network access to model registries.

FROM python:3.12-slim AS builder

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests first for optimal layer caching.
# The build context is the repo root, so paths are relative to that.
COPY server/pyproject.toml server/uv.lock ./

# Install third-party dependencies into a virtual environment WITHOUT
# building the project itself.  This layer is cached as long as the
# lock file does not change.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Pre-download the ONNX embedding model BEFORE copying source code
# so that code-only changes do not re-trigger the download.
# chromadb resolves the cache via Path.home() / ".cache/chroma/...";
# set HOME=/app so the model lands in a predictable location.
ENV HOME=/app
RUN .venv/bin/python -c "\
from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2; \
ONNXMiniLM_L6_V2()(['test'])"

# Copy the server source code so uv can build and install the project
# package into the venv (makes `python -m awos_recruitment_mcp` work).
COPY server/src/ /app/src/

# Now install the project itself (fast -- deps are already cached).
# --no-editable ensures the package is installed as a proper wheel
# rather than a .pth editable link, so the source tree is not needed
# in the runtime stage.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---- Runtime stage ----
# Minimal image with only the venv, cached model, and registry.

FROM python:3.12-slim AS runtime

# Create a non-root user for running the server.
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

# Copy the virtual environment from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy the pre-downloaded ONNX model cache from the builder.
# chromadb resolves the cache via Path.home() / ".cache/chroma/...".
COPY --from=builder --chown=1000:1000 /app/.cache/chroma /app/.cache/chroma

# Copy the registry (read-only capability catalog).
COPY registry/ /app/registry/

# Tell the server where to find the registry inside the container.
ENV AWOS_REGISTRY_PATH=/app/registry

# Set HOME=/app so chromadb resolves the ONNX model cache at
# /app/.cache/chroma/ (matching the builder stage path).
ENV HOME=/app

# Put the venv's bin directory first on PATH so `python` resolves
# to the venv interpreter with all installed packages.
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Drop privileges -- run as the non-root user.
USER appuser

ENTRYPOINT ["python", "-m", "awos_recruitment_mcp"]
