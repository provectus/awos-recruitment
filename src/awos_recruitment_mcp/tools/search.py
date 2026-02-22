"""Search tool for discovering capabilities in the registry.

This module registers the ``search_capabilities`` tool on the shared
:pydata:`~awos_recruitment_mcp.server.mcp` instance.  It is imported by
``server.py`` at module level so that tool registration happens at startup.
"""

from __future__ import annotations

from awos_recruitment_mcp.models.capability import CapabilityResult
from awos_recruitment_mcp.server import mcp

# ---------------------------------------------------------------------------
# Mock capability data (will be replaced by a real registry in later slices)
# ---------------------------------------------------------------------------

MOCK_CAPABILITIES: list[CapabilityResult] = [
    CapabilityResult(
        name="react-component-generator",
        description=(
            "Generates production-ready React components from natural-language "
            "specifications, including TypeScript types and unit tests."
        ),
        tags=["react", "typescript", "frontend", "components"],
    ),
    CapabilityResult(
        name="postgresql-migration-agent",
        description=(
            "Creates and validates PostgreSQL schema migrations with rollback "
            "support, foreign-key checks, and index recommendations."
        ),
        tags=["postgresql", "database", "migrations", "sql"],
    ),
    CapabilityResult(
        name="kubernetes-debugger",
        description=(
            "Diagnoses failing Kubernetes pods by inspecting events, logs, "
            "and resource limits, then suggests targeted fixes."
        ),
        tags=["kubernetes", "devops", "debugging", "infrastructure"],
    ),
    CapabilityResult(
        name="python-test-writer",
        description=(
            "Generates pytest test suites for Python modules, covering edge "
            "cases, mocking strategies, and parametrised scenarios."
        ),
        tags=["python", "testing", "pytest", "automation"],
    ),
    CapabilityResult(
        name="openapi-spec-linter",
        description=(
            "Validates OpenAPI 3.x specifications against best practices and "
            "reports naming inconsistencies, missing examples, and security gaps."
        ),
        tags=["openapi", "api-design", "validation", "rest"],
    ),
]


@mcp.tool
def search_capabilities(query: str) -> list[dict]:
    """Search the capability registry for skills, agents, and tools matching a query.

    Returns a ranked list of capabilities. Each result includes a name,
    description, and associated tags. Returns at most 10 results.
    """
    return [result.model_dump() for result in MOCK_CAPABILITIES[:10]]
