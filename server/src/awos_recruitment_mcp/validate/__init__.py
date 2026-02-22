"""Registry validation logic for skills (and, in the future, MCP definitions)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
from pydantic import ValidationError as PydanticValidationError

from awos_recruitment_mcp.models import SkillMetadata


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
        try:
            SkillMetadata.model_validate(dict(post.metadata))
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


def validate_registry(registry_path: Path) -> list[ValidationResult]:
    """Validate the entire registry at *registry_path*.

    Currently only validates skills.  MCP definitions will be added in a
    future slice.

    Returns:
        Combined list of :class:`ValidationResult` objects.
    """

    results: list[ValidationResult] = []
    results.extend(validate_skills(registry_path))
    return results
