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
from awos_recruitment_mcp.models.check import CheckRequest
from awos_recruitment_mcp.models.telemetry import TelemetryRequest
from awos_recruitment_mcp.telemetry import (
    init_telemetry,
    shutdown_telemetry,
    track_client_event,
    track_install,
)
from awos_recruitment_mcp.registry import (
    load_registry,
    resolve_agent_paths,
    resolve_hook_paths,
    resolve_mcp_paths,
    resolve_skill_paths,
)
from awos_recruitment_mcp.registry_index import (
    RemovedFileError,
    build_registry_index,
    iter_skill_files,
)
from awos_recruitment_mcp.search_index import build_index
from awos_recruitment_mcp.update_check import check_skills, track_check
from awos_recruitment_mcp.validate import _ALLOWED_HOOK_SCRIPT_EXTENSIONS

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
        "tool to find capabilities matching a natural language query. "
        "Installed skills are copies that do not update themselves. If the "
        "project has a .claude/skills/ directory, offer once per session to "
        "run `npx @provectusinc/awos-recruitment skill status`; do not run it "
        "without asking and do not repeat the offer."
    ),
    lifespan=lifespan,
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Return server health status and version."""
    return JSONResponse({"status": "ok", "version": config.version}, status_code=200)


@mcp.custom_route("/index.json", methods=["GET"])
async def registry_index(request: Request) -> JSONResponse:
    """Return content hashes of every skill and tombstones for removed capabilities.

    The CLI compares these hashes with its lock file to find outdated,
    locally modified or removed installs.  Computed from the registry on
    disk at request time, the same files ``/bundle/*`` serves.
    """
    try:
        index = build_registry_index(config.registry_path)
    except RemovedFileError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(index, status_code=200)


@mcp.custom_route("/check", methods=["POST"])
async def check_updates(request: Request) -> Response:
    """Compare a project's lock file with the registry.

    The ``skill-update-check`` hook POSTs ``.claude/awos-recruitment.lock.json``
    as is.  With ``Accept: text/plain`` the body is the one-line summary
    (empty when everything is current); otherwise a JSON document with
    ``summary``, ``outdated``, ``removed``, ``unknown``, ``up_to_date`` and
    ``command``.  Returns 400 when the body is not a lock file.
    """
    try:
        body = await request.json()
        check_request = CheckRequest.model_validate(body)
    except (ValidationError, ValueError) as exc:
        detail = exc.errors() if isinstance(exc, ValidationError) else str(exc)
        return JSONResponse({"error": "Validation failed", "detail": detail}, status_code=400)

    try:
        index = build_registry_index(config.registry_path)
    except RemovedFileError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    installed = {name: entry.hash for name, entry in check_request.skills.items()}
    result = check_skills(installed, index)

    if check_request.project_id is not None:
        track_check(check_request.project_id, result, source="hook")

    if "text/plain" in request.headers.get("accept", ""):
        return Response(content=result.summary, media_type="text/plain")
    return JSONResponse(result.to_dict(), status_code=200)


@mcp.custom_route("/telemetry", methods=["POST"])
async def client_telemetry(request: Request) -> Response:
    """Accept update-related events from the CLI.

    The CLI reports ``capability_update_checked``, ``capability_updated``
    and ``capability_removed_in_use`` after ``skill status`` / ``skill
    update``.  Events are keyed by the project's random id only.

    Returns 204 on success, 400 when the body fails validation.
    """
    try:
        body = await request.json()
        telemetry_request = TelemetryRequest.model_validate(body)
    except (ValidationError, ValueError) as exc:
        detail = exc.errors() if isinstance(exc, ValidationError) else str(exc)
        return JSONResponse(
            {"error": "Validation failed", "detail": detail},
            status_code=400,
        )

    for event in telemetry_request.events:
        properties: dict[str, int | bool | str] = dict(event.properties)
        if event.capability_name is not None:
            properties["capability_name"] = event.capability_name
        if event.capability_type is not None:
            properties["capability_type"] = event.capability_type
        track_client_event(telemetry_request.project_id, event.event, properties)

    return Response(status_code=204)


@mcp.custom_route("/bundle/skills", methods=["POST"])
async def bundle_skills(request: Request) -> Response:
    """Bundle one or more skills into a tar.gz archive.

    Expects a JSON body matching :class:`BundleRequest`.  Resolves each
    requested skill name to its on-disk directory, then streams back a
    gzip-compressed tar archive containing ``<name>/SKILL.md`` and any
    ``<name>/references/*``, ``<name>/scripts/*`` or ``<name>/assets/*`` files
    found for each skill. ``evals/`` is deliberately left out: it holds the
    author's test cases, not anything the installed skill reads.

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
            for rel_path, abs_path in iter_skill_files(skill_dir):
                tar.add(str(abs_path), arcname=f"{skill_dir.name}/{rel_path}")

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
