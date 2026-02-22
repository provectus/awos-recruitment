"""Data models for the AWOS Recruitment MCP server."""

__all__ = [
    "CapabilityResult",
    "McpDefinition",
    "McpServerConfig",
    "RegistryCapability",
    "SkillMetadata",
]

from awos_recruitment_mcp.models.capability import CapabilityResult, RegistryCapability
from awos_recruitment_mcp.models.mcp_definition import McpDefinition, McpServerConfig
from awos_recruitment_mcp.models.skill_metadata import SkillMetadata
