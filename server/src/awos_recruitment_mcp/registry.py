"""Registry loader — scans the registry directory and returns capabilities."""

from __future__ import annotations

import logging
from pathlib import Path

import frontmatter
import yaml

from awos_recruitment_mcp.models import RegistryCapability

logger = logging.getLogger(__name__)


def load_registry(registry_path: str | Path) -> list[RegistryCapability]:
    """Load all capabilities from the registry at *registry_path*.

    Scans two sub-trees:

    * ``skills/*/SKILL.md`` -- YAML front matter is parsed with
      *python-frontmatter*; each entry becomes a capability with
      ``type="skill"``.
    * ``mcp/*.yaml`` -- flat YAML files parsed with *pyyaml*; each entry
      becomes a capability with ``type="tool"``.

    Entries that have no ``description`` (or an empty/whitespace-only
    description) are silently skipped.

    Args:
        registry_path: Root directory of the registry.

    Returns:
        A list of :class:`RegistryCapability` objects.
    """
    root = Path(registry_path)
    capabilities: list[RegistryCapability] = []

    capabilities.extend(_load_skills(root))
    capabilities.extend(_load_mcp_tools(root))

    return capabilities


def _load_skills(root: Path) -> list[RegistryCapability]:
    """Parse ``skills/*/SKILL.md`` files and return skill capabilities."""
    skills_dir = root / "skills"
    results: list[RegistryCapability] = []

    if not skills_dir.is_dir():
        return results

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue

        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            post = frontmatter.load(str(skill_md))
        except Exception:
            logger.warning("Failed to parse front matter in %s", skill_md)
            continue

        metadata: dict = dict(post.metadata)
        name = metadata.get("name")
        description = metadata.get("description")

        if not name or not isinstance(name, str):
            continue
        if not description or not isinstance(description, str) or not description.strip():
            continue

        results.append(
            RegistryCapability(
                name=name,
                description=description,
                type="skill",
            )
        )

    return results


def _load_mcp_tools(root: Path) -> list[RegistryCapability]:
    """Parse ``mcp/*.yaml`` files and return tool capabilities."""
    mcp_dir = root / "mcp"
    results: list[RegistryCapability] = []

    if not mcp_dir.is_dir():
        return results

    for yaml_file in sorted(mcp_dir.iterdir()):
        if not yaml_file.is_file() or yaml_file.suffix != ".yaml":
            continue

        try:
            with open(yaml_file, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError:
            logger.warning("Failed to parse YAML in %s", yaml_file)
            continue

        if not isinstance(data, dict):
            continue

        name = data.get("name")
        description = data.get("description")

        if not name or not isinstance(name, str):
            continue
        if not description or not isinstance(description, str) or not description.strip():
            continue

        results.append(
            RegistryCapability(
                name=name,
                description=description,
                type="tool",
            )
        )

    return results
