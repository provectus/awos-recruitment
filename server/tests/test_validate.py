"""Tests for the skill metadata model and the validate_skills function."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from awos_recruitment_mcp.models import SkillMetadata
from awos_recruitment_mcp.validate import validate_skills


# ---------------------------------------------------------------------------
# SkillMetadata model tests
# ---------------------------------------------------------------------------


def test_valid_skill_metadata():
    """A dict with a valid name and description should pass validation."""
    meta = SkillMetadata.model_validate(
        {"name": "my-skill", "description": "A useful skill"}
    )
    assert meta.name == "my-skill", (
        f"Expected name 'my-skill', got '{meta.name}'"
    )
    assert meta.description == "A useful skill", (
        f"Expected description 'A useful skill', got '{meta.description}'"
    )


def test_skill_missing_name():
    """Omitting the required 'name' field should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        SkillMetadata.model_validate({"description": "No name provided"})
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "name" in error_fields, (
        f"Expected a validation error for 'name', got errors for: {error_fields}"
    )


def test_skill_invalid_name_chars():
    """Names with uppercase letters or spaces should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        SkillMetadata.model_validate(
            {"name": "My Skill!", "description": "Bad name"}
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "name" in error_fields, (
        f"Expected a validation error for 'name', got errors for: {error_fields}"
    )


def test_skill_unknown_field():
    """An unknown field should be rejected (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        SkillMetadata.model_validate(
            {
                "name": "good-name",
                "description": "Has extra field",
                "surprise": True,
            }
        )
    messages = [e["msg"] for e in exc_info.value.errors()]
    assert any("extra" in m.lower() for m in messages), (
        f"Expected an 'extra fields not permitted' error, got: {messages}"
    )


# ---------------------------------------------------------------------------
# validate_skills function tests
# ---------------------------------------------------------------------------


def test_validate_skill_empty_body(tmp_path: Path):
    """A SKILL.md with valid front matter but an empty body should produce errors."""
    skill_dir = tmp_path / "skills" / "empty-body"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: empty-body\ndescription: A skill with no body\n---\n"
    )

    results = validate_skills(tmp_path)

    assert len(results) == 1, (
        f"Expected exactly 1 result, got {len(results)}"
    )
    assert not results[0].valid, "Expected the result to be invalid (empty body)"
    error_messages = [e.message for e in results[0].errors]
    assert any("empty" in m.lower() for m in error_messages), (
        f"Expected an 'empty' body error, got: {error_messages}"
    )


def test_validate_skill_missing_skill_md(tmp_path: Path):
    """A subdirectory without SKILL.md should produce an error."""
    skill_dir = tmp_path / "skills" / "no-file"
    skill_dir.mkdir(parents=True)

    results = validate_skills(tmp_path)

    assert len(results) == 1, (
        f"Expected exactly 1 result, got {len(results)}"
    )
    assert not results[0].valid, "Expected the result to be invalid (missing file)"
    error_messages = [e.message for e in results[0].errors]
    assert any("not found" in m.lower() for m in error_messages), (
        f"Expected a 'not found' error, got: {error_messages}"
    )


def test_validate_skill_valid(tmp_path: Path):
    """A well-formed SKILL.md should pass validation with no errors."""
    skill_dir = tmp_path / "skills" / "good-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: good-skill\ndescription: A perfectly valid skill\n---\n\n"
        "# Good Skill\n\nThis skill does good things.\n"
    )

    results = validate_skills(tmp_path)

    assert len(results) == 1, (
        f"Expected exactly 1 result, got {len(results)}"
    )
    assert results[0].valid, (
        f"Expected the result to be valid, got errors: "
        f"{[e.message for e in results[0].errors]}"
    )
    assert results[0].errors == [], (
        f"Expected no errors, got: {results[0].errors}"
    )
