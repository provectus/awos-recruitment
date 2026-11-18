"""Registry loader — scans the registry directory and returns capabilities."""

from __future__ import annotations

import logging
from pathlib import Path

import frontmatter
import yaml
from pydantic import ValidationError as PydanticValidationError

from awos_recruitment_mcp.models import RegistryCapability
from awos_recruitment_mcp.models.hook_metadata import HookMetadata

logger = logging.getLogger(__name__)


def resolve_skill_paths(
    names: list[str],
    registry_path: str | Path,
) -> tuple[list[Path], list[str]]:
    """Resolve skill names to their directory paths under *registry_path*.

    For each name in *names*, checks whether ``skills/<name>/`` exists as a
    directory under the registry root.  Names that resolve to an existing
    directory are collected into the first element of the returned tuple;
    names that do not match any directory end up in the second element.

    Args:
        names: Skill directory names to look up.
        registry_path: Root directory of the registry.

    Returns:
        A ``(found_paths, not_found)`` tuple where *found_paths* is a list of
        :class:`~pathlib.Path` objects pointing to the matched skill
        directories and *not_found* is a list of names with no corresponding
        directory.
    """
    root = Path(registry_path)
    skills_dir = root / "skills"

    found: list[Path] = []
    not_found: list[str] = []

    for name in names:
        skill_path = skills_dir / name
        if skill_path.is_dir():
            found.append(skill_path)
        else:
            not_found.append(name)

    return found, not_found


def resolve_mcp_paths(
    names: list[str],
    registry_path: str | Path,
) -> tuple[list[Path], list[str]]:
    """Resolve MCP server names to their YAML file paths under *registry_path*.

    For each name in *names*, checks whether ``mcp/<name>.yaml`` exists as a
    file under the registry root.  Names that resolve to an existing file are
    collected into the first element of the returned tuple; names that do not
    match any file end up in the second element.

    Args:
        names: MCP server names to look up (without the ``.yaml`` suffix).
        registry_path: Root directory of the registry.

    Returns:
        A ``(found_paths, not_found)`` tuple where *found_paths* is a list of
        :class:`~pathlib.Path` objects pointing to the matched YAML files and
        *not_found* is a list of names with no corresponding file.
    """
    root = Path(registry_path)
    mcp_dir = root / "mcp"

    found: list[Path] = []
    not_found: list[str] = []

    for name in names:
        yaml_path = mcp_dir / f"{name}.yaml"
        if yaml_path.is_file():
            found.append(yaml_path)
        else:
            not_found.append(name)

    return found, not_found


def resolve_agent_paths(
    names: list[str],
    registry_path: str | Path,
) -> tuple[list[Path], list[str]]:
    """Resolve agent names to their Markdown file paths under *registry_path*.

    For each name in *names*, checks whether ``agents/<name>.md`` exists as a
    file under the registry root.  Names that resolve to an existing file are
    collected into the first element of the returned tuple; names that do not
    match any file end up in the second element.

    Args:
        names: Agent names to look up (without the ``.md`` suffix).
        registry_path: Root directory of the registry.

    Returns:
        A ``(found_paths, not_found)`` tuple where *found_paths* is a list of
        :class:`~pathlib.Path` objects pointing to the matched Markdown files
        and *not_found* is a list of names with no corresponding file.
    """
    root = Path(registry_path)
    agents_dir = root / "agents"

    found: list[Path] = []
    not_found: list[str] = []

    for name in names:
        md_path = agents_dir / f"{name}.md"
        if md_path.is_file():
            found.append(md_path)
        else:
            not_found.append(name)

    return found, not_found


def resolve_hook_paths(
    names: list[str],
    registry_path: str | Path,
) -> tuple[list[Path], list[str]]:
    """Resolve hook names to their directory paths under *registry_path*.

    For each name in *names*, checks whether ``hooks/<name>/`` exists as a
    directory under the registry root.  Names that resolve to an existing
    directory are collected into the first element of the returned tuple;
    names that do not match any directory end up in the second element.

    Args:
        names: Hook directory names to look up.
        registry_path: Root directory of the registry.

    Returns:
        A ``(found_paths, not_found)`` tuple where *found_paths* is a list of
        :class:`~pathlib.Path` objects pointing to the matched hook
        directories and *not_found* is a list of names with no corresponding
        directory.
    """
    root = Path(registry_path)
    hooks_dir = root / "hooks"

    found: list[Path] = []
    not_found: list[str] = []

    for name in names:
        hook_path = hooks_dir / name
        if hook_path.is_dir():
            found.append(hook_path)
        else:
            not_found.append(name)

    return found, not_found


def load_registry(registry_path: str | Path) -> list[RegistryCapability]:
    """Load all capabilities from the registry at *registry_path*.

    Scans four sub-trees:

    * ``skills/*/SKILL.md`` -- YAML front matter is parsed with
      *python-frontmatter*; each entry becomes a capability with
      ``type="skill"``.
    * ``mcp/*.yaml`` -- flat YAML files parsed with *pyyaml*; each entry
      becomes a capability with ``type="tool"``.
    * ``agents/*.md`` -- YAML front matter is parsed with
      *python-frontmatter*; each entry becomes a capability with
      ``type="agent"``.
    * ``hooks/*/HOOK.md`` -- YAML front matter is parsed with
      *python-frontmatter*; each entry becomes a capability with
      ``type="hook"``.

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
    capabilities.extend(_load_agents(root))
    capabilities.extend(_load_hooks(root))

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
                user_invoked=metadata.get("disable-model-invocation") is True,
            )
        )

    return results


def _load_hooks(root: Path) -> list[RegistryCapability]:
    """Parse ``hooks/*/HOOK.md`` files and return hook capabilities."""
    hooks_dir = root / "hooks"
    results: list[RegistryCapability] = []

    if not hooks_dir.is_dir():
        return results

    for entry in sorted(hooks_dir.iterdir()):
        if not entry.is_dir():
            continue

        hook_md = entry / "HOOK.md"
        if not hook_md.exists():
            continue

        try:
            post = frontmatter.load(str(hook_md))
        except Exception as exc:
            logger.warning(
                "Failed to parse front matter in %s", hook_md, exc_info=exc
            )
            continue

        # Hooks are executable configuration — unlike skills/agents, the
        # frontmatter is validated in full here so a malformed hook is
        # absent from the catalog instead of breaking at install time.
        # metadata goes in as-is: model_validate rejects a non-dict root
        # (top-level YAML list/scalar) with a ValidationError we catch,
        # whereas dict(post.metadata) would raise TypeError and crash the
        # whole registry load on one malformed file.
        try:
            meta = HookMetadata.model_validate(post.metadata)
        except PydanticValidationError as exc:
            logger.warning("Skipping hook %s: invalid metadata: %s", hook_md, exc)
            continue

        if meta.name != entry.name:
            logger.warning(
                "Skipping hook %s: frontmatter name '%s' does not match "
                "directory name '%s'",
                hook_md,
                meta.name,
                entry.name,
            )
            continue

        results.append(
            RegistryCapability(
                name=meta.name,
                description=meta.description,
                type="hook",
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


def _load_agents(root: Path) -> list[RegistryCapability]:
    """Parse ``agents/*.md`` files and return agent capabilities."""
    agents_dir = root / "agents"
    results: list[RegistryCapability] = []

    if not agents_dir.is_dir():
        return results

    for md_file in sorted(agents_dir.iterdir()):
        if not md_file.is_file() or md_file.suffix != ".md":
            continue

        try:
            post = frontmatter.load(str(md_file))
        except Exception:
            logger.warning("Failed to parse front matter in %s", md_file)
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
                type="agent",
            )
        )

    return results
