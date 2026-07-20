"""FastMCP server instance for AWOS Recruitment.

This module instantiates the `FastMCP` server with project-level metadata.
Import `mcp` from here whenever you need to register tools, resources,
or prompts.
"""

import io
import tarfile
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastmcp import FastMCP
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from awos_recruitment_mcp.config import Config
from awos_recruitment_mcp.models.bundle import BundleRequest
from awos_recruitment_mcp.telemetry import init_telemetry, shutdown_telemetry, track_install
from awos_recruitment_mcp.registry import (
    load_registry,
    resolve_agent_paths,
    resolve_hook_paths,
    resolve_mcp_paths,
    resolve_skill_paths,
)
from awos_recruitment_mcp.search_index import build_index
from awos_recruitment_mcp.validate import (
    _ALLOWED_HOOK_SCRIPT_EXTENSIONS,
    _ALLOWED_SCRIPT_EXTENSIONS,
)

config = Config.from_env()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialise the capability search index on server startup.

    Loads every capability from the on-disk registry and builds an
    in-memory ChromaDB collection that tools can query throughout the
    server's lifetime.  The collection is exposed to tools via
    ``ctx.lifespan_context["collection"]``.
    """
    capabilities = load_registry(config.registry_path)
    collection = build_index(capabilities)
    init_telemetry(config)

    yield {"collection": collection}

    shutdown_telemetry()


mcp = FastMCP(
    name="AWOS Recruitment",
    version=config.version,
    instructions=(
        "This server provides AI coding assistants with a discovery engine "
        "for skills, agents, tools, and hooks. Use the search_capabilities "
        "tool to find capabilities matching a natural language query."
    ),
    lifespan=lifespan,
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Return server health status and version."""
    return JSONResponse({"status": "ok", "version": config.version}, status_code=200)


@mcp.custom_route("/bundle/skills", methods=["POST"])
async def bundle_skills(request: Request) -> Response:
    """Bundle one or more skills into a tar.gz archive.

    Expects a JSON body matching :class:`BundleRequest`.  Resolves each
    requested skill name to its on-disk directory, then streams back a
    gzip-compressed tar archive containing ``<name>/SKILL.md`` and any
    ``<name>/references/*`` or ``<name>/scripts/*`` files found for each skill.

    Returns 400 with a JSON error body when the request fails validation.
    """
    try:
        body = await request.json()
        bundle_request = BundleRequest.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            {"error": "Validation failed", "detail": exc.errors()},
            status_code=400,
        )

    unique_names = list(dict.fromkeys(bundle_request.names))
    found_paths, _not_found = resolve_skill_paths(
        unique_names, config.registry_path
    )

    for skill_dir in found_paths:
        track_install(skill_dir.name, "skill")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for skill_dir in found_paths:
            skill_name = skill_dir.name

            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                tar.add(str(skill_md), arcname=f"{skill_name}/SKILL.md")

            for subdir_name in ("references", "scripts"):
                subdir = skill_dir / subdir_name
                if subdir.is_dir():
                    for sub_file in sorted(subdir.iterdir()):
                        if not sub_file.is_file() or sub_file.name.startswith("."):
                            continue
                        if (
                            subdir_name == "scripts"
                            and sub_file.suffix not in _ALLOWED_SCRIPT_EXTENSIONS
                        ):
                            continue
                        tar.add(
                            str(sub_file),
                            arcname=f"{skill_name}/{subdir_name}/{sub_file.name}",
                        )

    return Response(content=buf.getvalue(), media_type="application/gzip")


@mcp.custom_route("/bundle/mcp", methods=["POST"])
async def bundle_mcp(request: Request) -> Response:
    """Bundle one or more MCP server configs into a tar.gz archive.

    Expects a JSON body matching :class:`BundleRequest`.  Resolves each
    requested MCP server name to its on-disk YAML file, then streams back
    a gzip-compressed tar archive containing ``<name>.yaml`` for each
    found entry.

    Returns 400 with a JSON error body when the request fails validation.
    """
    try:
        body = await request.json()
        bundle_request = BundleRequest.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            {"error": "Validation failed", "detail": exc.errors()},
            status_code=400,
        )

    unique_names = list(dict.fromkeys(bundle_request.names))
    found_paths, _not_found = resolve_mcp_paths(
        unique_names, config.registry_path
    )

    for yaml_path in found_paths:
        track_install(yaml_path.stem, "mcp_server")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for yaml_path in found_paths:
            tar.add(str(yaml_path), arcname=yaml_path.name)

    return Response(content=buf.getvalue(), media_type="application/gzip")


@mcp.custom_route("/bundle/agents", methods=["POST"])
async def bundle_agents(request: Request) -> Response:
    """Bundle one or more agent definitions into a tar.gz archive.

    Expects a JSON body matching :class:`BundleRequest`.  Resolves each
    requested agent name to its on-disk Markdown file, then streams back
    a gzip-compressed tar archive containing ``<name>.md`` for each
    found entry.

    Returns 400 with a JSON error body when the request fails validation.
    """
    try:
        body = await request.json()
        bundle_request = BundleRequest.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            {"error": "Validation failed", "detail": exc.errors()},
            status_code=400,
        )

    unique_names = list(dict.fromkeys(bundle_request.names))
    found_paths, _not_found = resolve_agent_paths(
        unique_names, config.registry_path
    )

    for md_path in found_paths:
        track_install(md_path.stem, "agent")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for md_path in found_paths:
            tar.add(str(md_path), arcname=md_path.name)

    return Response(content=buf.getvalue(), media_type="application/gzip")


@mcp.custom_route("/bundle/hooks", methods=["POST"])
async def bundle_hooks(request: Request) -> Response:
    """Bundle one or more hooks into a tar.gz archive.

    Expects a JSON body matching :class:`BundleRequest`.  Resolves each
    requested hook name to its on-disk directory, then streams back a
    gzip-compressed tar archive containing ``<name>/HOOK.md``, the
    ``<name>/<name>.sh`` entrypoint, and any ``<name>/scripts/*`` files
    filtered by :data:`_ALLOWED_HOOK_SCRIPT_EXTENSIONS` for each found hook.

    On-disk file modes are preserved in the archive, so the entrypoint's
    executable bit travels with the bundle.

    Returns 400 with a JSON error body when the request fails validation.
    """
    try:
        body = await request.json()
        bundle_request = BundleRequest.model_validate(body)
    except ValidationError as exc:
        return JSONResponse(
            {"error": "Validation failed", "detail": exc.errors()},
            status_code=400,
        )

    unique_names = list(dict.fromkeys(bundle_request.names))
    found_paths, _not_found = resolve_hook_paths(
        unique_names, config.registry_path
    )

    # A hook without its entrypoint would install as a settings entry
    # pointing at a script that doesn't exist — omit the whole directory so
    # the CLI reports it not-found instead of "installed". Filtering once up
    # front keeps telemetry honest too: a hook that ships nothing must not
    # be counted as an install.
    shippable = [d for d in found_paths if (d / f"{d.name}.sh").is_file()]

    for hook_dir in shippable:
        track_install(hook_dir.name, "hook")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for hook_dir in shippable:
            hook_name = hook_dir.name

            hook_md = hook_dir / "HOOK.md"
            if hook_md.is_file():
                tar.add(str(hook_md), arcname=f"{hook_name}/HOOK.md")

            entrypoint = hook_dir / f"{hook_name}.sh"
            tar.add(str(entrypoint), arcname=f"{hook_name}/{hook_name}.sh")

            scripts_dir = hook_dir / "scripts"
            if scripts_dir.is_dir():
                for sub_file in sorted(scripts_dir.iterdir()):
                    if not sub_file.is_file() or sub_file.name.startswith("."):
                        continue
                    if sub_file.suffix not in _ALLOWED_HOOK_SCRIPT_EXTENSIONS:
                        continue
                    tar.add(
                        str(sub_file),
                        arcname=f"{hook_name}/scripts/{sub_file.name}",
                    )

    return Response(content=buf.getvalue(), media_type="application/gzip")


# Import tool modules AFTER `mcp` is created so they can reference it without
# triggering a circular-import error.
import awos_recruitment_mcp.tools.search  # noqa: E402, F401 — registers MCP tools
