"""Registry validation logic for skills and MCP definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
import yaml
from pydantic import ValidationError as PydanticValidationError

from awos_recruitment_mcp.models import AgentMetadata, McpDefinition, SkillMetadata


@dataclass(frozen=True, slots=True)
class ValidationError:
    """A single validation problem found in a registry file.

    Attributes:
        file: Relative path to the file with the problem.
        field: Name of the problematic field, or ``None`` for file-level issues.
        message: Human-readable description of the problem.
    """

    file: str
    field: str | None
    message: str


@dataclass(slots=True)
class ValidationResult:
    """Aggregated validation outcome for a single registry file.

    Attributes:
        file: Relative path to the validated file.
        valid: ``True`` when no errors were found.
        errors: List of individual validation errors (empty when valid).
    """

    file: str
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)


def validate_skills(registry_path: Path) -> list[ValidationResult]:
    """Validate every skill definition under *registry_path*/skills.

    Each immediate subdirectory of ``skills/`` is expected to contain a
    ``SKILL.md`` file whose YAML front matter conforms to
    :class:`~awos_recruitment_mcp.models.SkillMetadata` and whose markdown body
    is non-empty.

    Returns:
        A list of :class:`ValidationResult` objects, one per subdirectory.
    """

    skills_dir = registry_path / "skills"
    results: list[ValidationResult] = []

    if not skills_dir.is_dir():
        return results

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue

        skill_md = entry / "SKILL.md"
        relative_path = str(skill_md.relative_to(registry_path))

        if not skill_md.exists():
            results.append(
                ValidationResult(
                    file=relative_path,
                    valid=False,
                    errors=[
                        ValidationError(
                            file=relative_path,
                            field=None,
                            message="SKILL.md not found",
                        )
                    ],
                )
            )
            continue

        errors: list[ValidationError] = []

        try:
            post = frontmatter.load(str(skill_md))
        except Exception as exc:
            errors.append(
                ValidationError(
                    file=relative_path,
                    field=None,
                    message=f"Failed to parse front matter: {exc}",
                )
            )
            results.append(
                ValidationResult(file=relative_path, valid=False, errors=errors)
            )
            continue

        # Validate metadata against the Pydantic model.
        metadata = dict(post.metadata)
        try:
            SkillMetadata.model_validate(metadata)
        except PydanticValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err["loc"]) or None
                errors.append(
                    ValidationError(
                        file=relative_path,
                        field=loc,
                        message=err["msg"],
                    )
                )

        # Ensure the directory name matches the metadata name.
        meta_name = metadata.get("name")
        if meta_name is not None and entry.name != meta_name:
            errors.append(
                ValidationError(
                    file=relative_path,
                    field="name",
                    message=(
                        f"Skill directory '{entry.name}' does not match "
                        f"metadata name '{meta_name}'"
                    ),
                )
            )

        # Ensure the markdown body is non-empty.
        if not post.content.strip():
            errors.append(
                ValidationError(
                    file=relative_path,
                    field=None,
                    message="Skill body (markdown content) is empty",
                )
            )

        results.append(
            ValidationResult(
                file=relative_path,
                valid=len(errors) == 0,
                errors=errors,
            )
        )

    return results


def validate_mcp_definitions(registry_path: Path) -> list[ValidationResult]:
    """Validate every MCP definition under *registry_path*/mcp.

    Each ``.yaml`` file in the ``mcp/`` directory is expected to conform to
    :class:`~awos_recruitment_mcp.models.McpDefinition`.

    Returns:
        A list of :class:`ValidationResult` objects, one per YAML file.
    """

    mcp_dir = registry_path / "mcp"
    results: list[ValidationResult] = []

    if not mcp_dir.is_dir():
        return results

    for yaml_file in sorted(mcp_dir.iterdir()):
        if not yaml_file.is_file() or yaml_file.suffix != ".yaml":
            continue

        relative_path = str(yaml_file.relative_to(registry_path))
        errors: list[ValidationError] = []

        # Parse YAML.
        try:
            with open(yaml_file, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            errors.append(
                ValidationError(
                    file=relative_path,
                    field=None,
                    message=f"Failed to parse YAML: {exc}",
                )
            )
            results.append(
                ValidationResult(file=relative_path, valid=False, errors=errors)
            )
            continue

        if not isinstance(data, dict):
            errors.append(
                ValidationError(
                    file=relative_path,
                    field=None,
                    message="YAML content is not a mapping",
                )
            )
            results.append(
                ValidationResult(file=relative_path, valid=False, errors=errors)
            )
            continue

        # Validate against the Pydantic model.
        try:
            McpDefinition.model_validate(data)
        except PydanticValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err["loc"]) or None
                errors.append(
                    ValidationError(
                        file=relative_path,
                        field=loc,
                        message=err["msg"],
                    )
                )
        except ValueError as exc:
            errors.append(
                ValidationError(
                    file=relative_path,
                    field="config",
                    message=str(exc),
                )
            )

        # Ensure the filename (without extension) matches the name field.
        mcp_name = data.get("name")
        if mcp_name is not None and yaml_file.stem != mcp_name:
            errors.append(
                ValidationError(
                    file=relative_path,
                    field="name",
                    message=(
                        f"MCP filename '{yaml_file.stem}' does not match "
                        f"name field '{mcp_name}'"
                    ),
                )
            )

        results.append(
            ValidationResult(
                file=relative_path,
                valid=len(errors) == 0,
                errors=errors,
            )
        )

    return results


def validate_agents(registry_path: Path) -> list[ValidationResult]:
    """Validate every agent definition under *registry_path*/agents.

    Each ``.md`` file in the ``agents/`` directory is expected to have YAML
    front matter conforming to
    :class:`~awos_recruitment_mcp.models.AgentMetadata` and a non-empty
    markdown body (the system prompt).

    Returns:
        A list of :class:`ValidationResult` objects, one per ``.md`` file.
    """

    agents_dir = registry_path / "agents"
    results: list[ValidationResult] = []

    if not agents_dir.is_dir():
        return results

    for md_file in sorted(agents_dir.iterdir()):
        if not md_file.is_file() or md_file.suffix != ".md":
            continue

        relative_path = str(md_file.relative_to(registry_path))
        errors: list[ValidationError] = []

        # Parse front matter.
        try:
            post = frontmatter.load(str(md_file))
        except Exception as exc:
            errors.append(
                ValidationError(
                    file=relative_path,
                    field=None,
                    message=f"Failed to parse front matter: {exc}",
                )
            )
            results.append(
                ValidationResult(file=relative_path, valid=False, errors=errors)
            )
            continue

        # Validate metadata against the Pydantic model.
        metadata = dict(post.metadata)
        try:
            AgentMetadata.model_validate(metadata)
        except PydanticValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(part) for part in err["loc"]) or None
                errors.append(
                    ValidationError(
                        file=relative_path,
                        field=loc,
                        message=err["msg"],
                    )
                )

        # Ensure the filename stem matches the metadata name.
        meta_name = metadata.get("name")
        if meta_name is not None and md_file.stem != meta_name:
            errors.append(
                ValidationError(
                    file=relative_path,
                    field="name",
                    message=(
                        f"Agent filename '{md_file.stem}' does not match "
                        f"name field '{meta_name}'"
                    ),
                )
            )

        # Ensure the markdown body (system prompt) is non-empty.
        if not post.content.strip():
            errors.append(
                ValidationError(
                    file=relative_path,
                    field=None,
                    message="Agent body (system prompt) is empty",
                )
            )

        # Cross-validate skill references against registry/skills/.
        skills = metadata.get("skills")
        if isinstance(skills, list):
            for skill_name in skills:
                skill_dir = registry_path / "skills" / skill_name
                if not skill_dir.is_dir():
                    errors.append(
                        ValidationError(
                            file=relative_path,
                            field="skills",
                            message=(
                                f"Referenced skill '{skill_name}' not found "
                                f"in registry skills directory"
                            ),
                        )
                    )

        results.append(
            ValidationResult(
                file=relative_path,
                valid=len(errors) == 0,
                errors=errors,
            )
        )

    return results


def validate_registry(registry_path: Path) -> list[ValidationResult]:
    """Validate the entire registry at *registry_path*.

    Validates both skill definitions and MCP server definitions.

    Returns:
        Combined list of :class:`ValidationResult` objects.
    """

    results: list[ValidationResult] = []
    results.extend(validate_skills(registry_path))
    results.extend(validate_mcp_definitions(registry_path))
    results.extend(validate_agents(registry_path))
    return results
