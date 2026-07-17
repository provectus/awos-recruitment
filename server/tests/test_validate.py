"""Tests for skill/MCP metadata models and the validation functions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from awos_recruitment_mcp.models import (
    AgentMetadata,
    HookEntry,
    HookMetadata,
    McpDefinition,
    McpServerConfig,
    SkillMetadata,
)
from awos_recruitment_mcp.validate import (
    validate_agents,
    validate_hooks,
    validate_mcp_definitions,
    validate_registry,
    validate_skills,
)


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
# AgentMetadata model tests
# ---------------------------------------------------------------------------


def test_valid_agent_metadata():
    """A dict with valid name and description should pass validation."""
    meta = AgentMetadata.model_validate(
        {"name": "my-agent", "description": "A useful agent"}
    )
    assert meta.name == "my-agent", (
        f"Expected name 'my-agent', got '{meta.name}'"
    )
    assert meta.description == "A useful agent", (
        f"Expected description 'A useful agent', got '{meta.description}'"
    )


def test_agent_missing_name():
    """Omitting the required 'name' field should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentMetadata.model_validate({"description": "No name provided"})
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "name" in error_fields, (
        f"Expected a validation error for 'name', got errors for: {error_fields}"
    )


def test_agent_empty_description():
    """An empty description should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentMetadata.model_validate({"name": "my-agent", "description": ""})
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "description" in error_fields, (
        f"Expected a validation error for 'description', got errors for: {error_fields}"
    )


def test_agent_invalid_name_format():
    """Names with uppercase letters should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        AgentMetadata.model_validate(
            {"name": "My-Agent", "description": "Bad name"}
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "name" in error_fields, (
        f"Expected a validation error for 'name', got errors for: {error_fields}"
    )


def test_agent_extra_fields_rejected():
    """An unknown field should be rejected (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        AgentMetadata.model_validate(
            {
                "name": "good-agent",
                "description": "Has extra field",
                "surprise": True,
            }
        )
    messages = [e["msg"] for e in exc_info.value.errors()]
    assert any("extra" in m.lower() for m in messages), (
        f"Expected an 'extra fields not permitted' error, got: {messages}"
    )


def test_agent_optional_fields():
    """Optional fields (model, skills) should work when provided."""
    meta = AgentMetadata.model_validate(
        {
            "name": "full-agent",
            "description": "Agent with all fields",
            "model": "sonnet",
            "skills": ["python-dev", "testing"],
        }
    )
    assert meta.model == "sonnet", (
        f"Expected model 'sonnet', got '{meta.model}'"
    )
    assert meta.skills == ["python-dev", "testing"], (
        f"Expected skills ['python-dev', 'testing'], got {meta.skills}"
    )


def test_agent_optional_fields_default_none():
    """Optional fields should default to None when omitted."""
    meta = AgentMetadata.model_validate(
        {"name": "minimal-agent", "description": "Minimal"}
    )
    assert meta.model is None, (
        f"Expected model to be None, got '{meta.model}'"
    )
    assert meta.skills is None, (
        f"Expected skills to be None, got {meta.skills}"
    )


# ---------------------------------------------------------------------------
# HookMetadata / HookEntry model tests
# ---------------------------------------------------------------------------


def test_valid_hook_metadata():
    """A dict with valid name, description, and hooks should pass validation."""
    meta = HookMetadata.model_validate(
        {
            "name": "docs-that-work-gate",
            "description": "Blocks commits when docs are stale",
            "hooks": [
                {"event": "PreToolUse", "matcher": "Bash", "timeout": 10}
            ],
        }
    )
    assert meta.name == "docs-that-work-gate", (
        f"Expected name 'docs-that-work-gate', got '{meta.name}'"
    )
    assert len(meta.hooks) == 1, (
        f"Expected exactly 1 hook entry, got {len(meta.hooks)}"
    )
    entry = meta.hooks[0]
    assert entry.event == "PreToolUse", (
        f"Expected event 'PreToolUse', got '{entry.event}'"
    )
    assert entry.matcher == "Bash", (
        f"Expected matcher 'Bash', got '{entry.matcher}'"
    )
    assert entry.timeout == 10, (
        f"Expected timeout 10, got {entry.timeout}"
    )


def test_hook_entry_optional_fields_default_none():
    """matcher and timeout should default to None when omitted."""
    entry = HookEntry.model_validate({"event": "SessionStart"})
    assert entry.matcher is None, (
        f"Expected matcher to be None, got '{entry.matcher}'"
    )
    assert entry.timeout is None, (
        f"Expected timeout to be None, got {entry.timeout}"
    )


def test_hook_missing_name():
    """Omitting the required 'name' field should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        HookMetadata.model_validate(
            {
                "description": "No name provided",
                "hooks": [{"event": "PreToolUse"}],
            }
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "name" in error_fields, (
        f"Expected a validation error for 'name', got errors for: {error_fields}"
    )


def test_hook_invalid_name_chars():
    """Names with uppercase letters or spaces should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        HookMetadata.model_validate(
            {
                "name": "My Hook!",
                "description": "Bad name",
                "hooks": [{"event": "PreToolUse"}],
            }
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "name" in error_fields, (
        f"Expected a validation error for 'name', got errors for: {error_fields}"
    )


def test_hook_invalid_event_value():
    """An unknown event literal should raise a validation error."""
    with pytest.raises(ValidationError) as exc_info:
        HookMetadata.model_validate(
            {
                "name": "bad-event",
                "description": "Has an unknown event",
                "hooks": [{"event": "NotARealEvent"}],
            }
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert any("event" in f for f in error_fields), (
        f"Expected a validation error for 'event', got errors for: {error_fields}"
    )


def test_hook_empty_hooks_list():
    """An empty hooks list should raise a validation error (min_length=1)."""
    with pytest.raises(ValidationError) as exc_info:
        HookMetadata.model_validate(
            {
                "name": "empty-hooks",
                "description": "No hook entries",
                "hooks": [],
            }
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "hooks" in error_fields, (
        f"Expected a validation error for 'hooks', got errors for: {error_fields}"
    )


def test_hook_zero_timeout_rejected():
    """A timeout of zero should be rejected (gt=0)."""
    with pytest.raises(ValidationError) as exc_info:
        HookEntry.model_validate({"event": "PreToolUse", "timeout": 0})
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "timeout" in error_fields, (
        f"Expected a validation error for 'timeout', got errors for: {error_fields}"
    )


def test_hook_negative_timeout_rejected():
    """A negative timeout should be rejected (gt=0)."""
    with pytest.raises(ValidationError) as exc_info:
        HookEntry.model_validate({"event": "PreToolUse", "timeout": -5})
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "timeout" in error_fields, (
        f"Expected a validation error for 'timeout', got errors for: {error_fields}"
    )


def test_hook_metadata_extra_fields_rejected():
    """An unknown field on HookMetadata should be rejected (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        HookMetadata.model_validate(
            {
                "name": "good-hook",
                "description": "Has extra field",
                "hooks": [{"event": "PreToolUse"}],
                "surprise": True,
            }
        )
    messages = [e["msg"] for e in exc_info.value.errors()]
    assert any("extra" in m.lower() for m in messages), (
        f"Expected an 'extra fields not permitted' error, got: {messages}"
    )


def test_hook_entry_extra_fields_rejected():
    """An unknown field on HookEntry should be rejected (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        HookEntry.model_validate(
            {"event": "PreToolUse", "command": "echo hi"}
        )
    messages = [e["msg"] for e in exc_info.value.errors()]
    assert any("extra" in m.lower() for m in messages), (
        f"Expected an 'extra fields not permitted' error, got: {messages}"
    )


# ---------------------------------------------------------------------------
# validate_skills function tests
# ---------------------------------------------------------------------------


def _make_skill_dir(tmp_path: Path, name: str, description: str) -> Path:
    """Create a minimal well-formed skill directory and return its path."""
    skill_dir = tmp_path / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n"
        "# Body\n\nContent here.\n"
    )
    return skill_dir


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


def test_validate_skill_rejects_unexpected_toplevel_dir(tmp_path: Path):
    """A non-allowlisted directory (e.g. rules/) should be flagged as unexpected."""
    skill_dir = _make_skill_dir(tmp_path, "has-rules", "stray rules folder")
    rules_dir = skill_dir / "rules"
    rules_dir.mkdir()
    (rules_dir / "rule-a.md").write_text("# Rule A\n")

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, (
        "Expected invalid result when a non-allowlisted folder is present"
    )
    error_messages = [e.message for e in results[0].errors]
    assert any("rules" in m and "Unexpected directory" in m for m in error_messages), (
        f"Expected an 'Unexpected directory \"rules/\"' error, got: {error_messages}"
    )


def test_validate_skill_rejects_unexpected_toplevel_file(tmp_path: Path):
    """An unknown top-level file should also be flagged."""
    skill_dir = _make_skill_dir(tmp_path, "has-extra", "stray file")
    (skill_dir / "notes.txt").write_text("scratch\n")

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert not results[0].valid
    error_messages = [e.message for e in results[0].errors]
    assert any("notes.txt" in m for m in error_messages), (
        f"Expected an error mentioning 'notes.txt', got: {error_messages}"
    )


def test_validate_skill_rejects_nested_references_dir(tmp_path: Path):
    """A subdirectory inside references/ should be flagged — the bundler only ships flat files."""
    skill_dir = _make_skill_dir(tmp_path, "nested-refs", "references has a subfolder")
    nested = skill_dir / "references" / "sub"
    nested.mkdir(parents=True)
    (nested / "buried.md").write_text("# Buried\n")

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert not results[0].valid
    error_messages = [e.message for e in results[0].errors]
    assert any("references/sub" in m for m in error_messages), (
        f"Expected an error mentioning 'references/sub', got: {error_messages}"
    )


def test_validate_skill_ignores_dotfiles(tmp_path: Path):
    """macOS/VCS dotfiles (.DS_Store, .gitkeep) must not trigger layout errors."""
    skill_dir = _make_skill_dir(tmp_path, "dotfiles-ok", "dotfiles should be ignored")
    (skill_dir / ".DS_Store").write_bytes(b"\x00\x01\x02")
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "a.md").write_text("# A\n")
    (refs / ".DS_Store").write_bytes(b"\x00\x01\x02")

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert results[0].valid, (
        f"Expected dotfiles to be ignored, got errors: "
        f"{[e.message for e in results[0].errors]}"
    )


def test_validate_skill_rejects_file_named_references(tmp_path: Path):
    """A regular file named 'references' must not satisfy the references/ dir slot."""
    skill_dir = _make_skill_dir(tmp_path, "file-refs", "references is a file, not a dir")
    (skill_dir / "references").write_text("oops, should be a directory\n")

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, (
        "Expected a file named 'references' to be rejected"
    )
    error_messages = [e.message for e in results[0].errors]
    assert any(
        "Unexpected file" in m and "references" in m for m in error_messages
    ), f"Expected 'Unexpected file references' error, got: {error_messages}"


def test_validate_skill_reports_multiple_layout_errors(tmp_path: Path):
    """One skill with several layout problems should surface every one."""
    skill_dir = _make_skill_dir(tmp_path, "many-issues", "lots of layout problems")
    (skill_dir / "rules").mkdir()
    (skill_dir / "rules" / "a.md").write_text("# A\n")
    (skill_dir / "notes.txt").write_text("scratch\n")
    nested = skill_dir / "references" / "sub"
    nested.mkdir(parents=True)
    (nested / "buried.md").write_text("# Buried\n")

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert not results[0].valid
    messages = [e.message for e in results[0].errors]
    assert any("rules/" in m and "Unexpected directory" in m for m in messages), (
        f"Expected rules/ directory error, got: {messages}"
    )
    assert any("notes.txt" in m and "Unexpected file" in m for m in messages), (
        f"Expected notes.txt file error, got: {messages}"
    )
    assert any("references/sub" in m for m in messages), (
        f"Expected nested references/sub error, got: {messages}"
    )


def test_validate_skill_allows_readme_and_flat_references(tmp_path: Path):
    """README.md at the top level and flat files under references/ are fine."""
    skill_dir = _make_skill_dir(tmp_path, "well-formed", "proper layout")
    (skill_dir / "README.md").write_text("# Readme\n")
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / "a.md").write_text("# A\n")
    (refs / "b.md").write_text("# B\n")

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert results[0].valid, (
        f"Expected layout to pass, got errors: "
        f"{[e.message for e in results[0].errors]}"
    )


# ---------------------------------------------------------------------------
# validate_hooks function tests
# ---------------------------------------------------------------------------


def _make_hook_dir(
    tmp_path: Path,
    name: str,
    description: str,
    *,
    body: str = "# Body\n\nManual injection instructions here.\n",
    metadata_name: str | None = None,
    entrypoint_mode: int | None = 0o755,
) -> Path:
    """Create a hook directory under ``tmp_path/hooks`` and return its path.

    Args:
        tmp_path: Registry root; ``hooks/<name>/`` is created beneath it.
        name: Hook directory name (also the metadata name unless overridden).
        description: Value for the ``description`` front-matter field.
        body: Markdown body written after the front matter.
        metadata_name: Override the front-matter ``name`` field to force a
            directory-vs-name mismatch; defaults to ``name``.
        entrypoint_mode: If not ``None``, an ``<name>.sh`` entrypoint is created
            with this file mode; pass ``None`` to omit the entrypoint entirely.
    """
    hook_dir = tmp_path / "hooks" / name
    hook_dir.mkdir(parents=True)
    front_name = metadata_name if metadata_name is not None else name
    (hook_dir / "HOOK.md").write_text(
        f"---\nname: {front_name}\ndescription: {description}\n"
        "hooks:\n"
        "  - event: PreToolUse\n"
        "    matcher: Edit|Write\n"
        "    timeout: 10\n"
        f"---\n\n{body}"
    )
    if entrypoint_mode is not None:
        entrypoint = hook_dir / f"{name}.sh"
        entrypoint.write_text("#!/bin/sh\nexit 0\n")
        entrypoint.chmod(entrypoint_mode)
    return hook_dir


def test_validate_hook_valid(tmp_path: Path):
    """A well-formed hook with an executable entrypoint should pass."""
    _make_hook_dir(tmp_path, "good-hook", "A perfectly valid hook.")

    results = validate_hooks(tmp_path)

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


def test_validate_hook_missing_hook_md(tmp_path: Path):
    """A subdirectory without HOOK.md should produce a 'not found' error."""
    (tmp_path / "hooks" / "no-file").mkdir(parents=True)

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result (missing HOOK.md)"
    error_messages = [e.message for e in results[0].errors]
    assert any("not found" in m.lower() for m in error_messages), (
        f"Expected a 'not found' error, got: {error_messages}"
    )


def test_validate_hook_directory_name_mismatch(tmp_path: Path):
    """A hook whose directory name differs from its metadata name should fail."""
    _make_hook_dir(
        tmp_path,
        "wrong-dir",
        "Directory mismatch test.",
        metadata_name="correct-name",
    )

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result for directory mismatch"
    error_fields = [e.field for e in results[0].errors]
    assert "name" in error_fields, (
        f"Expected a 'name' field error, got: {error_fields}"
    )
    error_messages = [e.message for e in results[0].errors]
    assert any("does not match" in m for m in error_messages), (
        f"Expected a 'does not match' error, got: {error_messages}"
    )


def test_validate_hook_empty_body(tmp_path: Path):
    """A HOOK.md with valid front matter but an empty body should fail."""
    _make_hook_dir(tmp_path, "empty-body", "A hook with no body.", body="")

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result (empty body)"
    error_messages = [e.message for e in results[0].errors]
    assert any("empty" in m.lower() for m in error_messages), (
        f"Expected an 'empty' body error, got: {error_messages}"
    )


def test_validate_hook_missing_entrypoint(tmp_path: Path):
    """A hook without its <name>.sh entrypoint should fail."""
    _make_hook_dir(
        tmp_path,
        "no-entry",
        "Missing entrypoint.",
        entrypoint_mode=None,
    )

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result (missing entrypoint)"
    error_messages = [e.message for e in results[0].errors]
    assert any(
        "no-entry.sh" in m and "not found" in m.lower() for m in error_messages
    ), f"Expected a missing-entrypoint error, got: {error_messages}"


def test_validate_hook_non_executable_entrypoint(tmp_path: Path):
    """An entrypoint present but not marked executable (chmod 644) should fail."""
    _make_hook_dir(
        tmp_path,
        "not-exec",
        "Non-executable entrypoint.",
        entrypoint_mode=0o644,
    )

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result (non-executable entrypoint)"
    error_messages = [e.message for e in results[0].errors]
    assert any(
        "not-exec.sh" in m and "not executable" in m.lower()
        for m in error_messages
    ), f"Expected a non-executable-entrypoint error, got: {error_messages}"


def test_validate_hook_rejects_unexpected_root_file(tmp_path: Path):
    """An unknown top-level file should be flagged as unexpected."""
    hook_dir = _make_hook_dir(tmp_path, "has-extra", "stray file")
    (hook_dir / "extra.txt").write_text("scratch\n")

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert not results[0].valid
    error_messages = [e.message for e in results[0].errors]
    assert any(
        "extra.txt" in m and "Unexpected file" in m for m in error_messages
    ), f"Expected an 'Unexpected file extra.txt' error, got: {error_messages}"


def test_validate_hook_rejects_bad_scripts_extension(tmp_path: Path):
    """A scripts/ file with a disallowed extension should be flagged."""
    hook_dir = _make_hook_dir(tmp_path, "bad-script", "scripts has a bad file")
    scripts = hook_dir / "scripts"
    scripts.mkdir()
    (scripts / "helper.rb").write_text("puts 'hi'\n")

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert not results[0].valid
    error_messages = [e.message for e in results[0].errors]
    assert any(
        "scripts/helper.rb" in m and "disallowed extension" in m
        for m in error_messages
    ), f"Expected a disallowed-extension error, got: {error_messages}"


def test_validate_hook_allows_scripts_with_allowed_extension(tmp_path: Path):
    """A scripts/ file with an allowed extension (.py) should pass."""
    hook_dir = _make_hook_dir(tmp_path, "good-script", "scripts has a good file")
    scripts = hook_dir / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text("print('hi')\n")

    results = validate_hooks(tmp_path)

    assert len(results) == 1
    assert results[0].valid, (
        f"Expected the result to be valid, got errors: "
        f"{[e.message for e in results[0].errors]}"
    )


def test_validate_hooks_missing_dir_returns_no_results(tmp_path: Path):
    """A registry with no hooks/ directory yields no results and no error."""
    results = validate_hooks(tmp_path)

    assert results == [], (
        f"Expected no results when hooks/ is absent, got: {results}"
    )


# ---------------------------------------------------------------------------
# McpDefinition / McpServerConfig model tests
# ---------------------------------------------------------------------------

_VALID_MCP_DICT = {
    "name": "test-server",
    "description": "A test MCP server for unit tests.",
    "config": {
        "test-server": {
            "type": "stdio",
            "command": "node",
            "args": ["server.js"],
        }
    },
}


def test_valid_mcp_definition():
    """A dict with valid name, description, and a single config entry should pass."""
    defn = McpDefinition.model_validate(_VALID_MCP_DICT)
    assert defn.name == "test-server", (
        f"Expected name 'test-server', got '{defn.name}'"
    )
    assert defn.description == "A test MCP server for unit tests.", (
        f"Expected correct description, got '{defn.description}'"
    )
    assert len(defn.config) == 1, (
        f"Expected exactly 1 config key, got {len(defn.config)}"
    )
    server_cfg = defn.config["test-server"]
    assert server_cfg.type == "stdio", (
        f"Expected type 'stdio', got '{server_cfg.type}'"
    )


def test_mcp_missing_config():
    """Omitting the required 'config' field should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        McpDefinition.model_validate(
            {"name": "no-config", "description": "Missing config field"}
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "config" in error_fields, (
        f"Expected a validation error for 'config', got errors for: {error_fields}"
    )


def test_mcp_multiple_config_keys():
    """A config dict with 2+ keys should raise a validation error."""
    with pytest.raises(ValidationError) as exc_info:
        McpDefinition.model_validate(
            {
                "name": "multi-config",
                "description": "Has two servers",
                "config": {
                    "server-a": {"type": "stdio", "command": "a"},
                    "server-b": {"type": "sse", "url": "http://localhost"},
                },
            }
        )
    messages = [e["msg"] for e in exc_info.value.errors()]
    assert any("exactly 1" in m for m in messages), (
        f"Expected an 'exactly 1 key' error, got: {messages}"
    )


def test_mcp_missing_type():
    """McpServerConfig without 'type' should raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        McpServerConfig.model_validate({"command": "node"})
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "type" in error_fields, (
        f"Expected a validation error for 'type', got errors for: {error_fields}"
    )


# ---------------------------------------------------------------------------
# validate_mcp_definitions integration tests
# ---------------------------------------------------------------------------


def _write_mcp_yaml(registry_root: Path, filename: str, content: str) -> None:
    """Helper: write a YAML file inside registry_root/mcp/."""
    mcp_dir = registry_root / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / filename).write_text(content)


def test_validate_mcp_valid(tmp_path: Path):
    """A well-formed MCP YAML file should pass validation with no errors."""
    _write_mcp_yaml(
        tmp_path,
        "good-server.yaml",
        (
            "name: good-server\n"
            "description: A valid MCP server definition.\n"
            "config:\n"
            "  good-server:\n"
            "    type: stdio\n"
            "    command: node\n"
            "    args:\n"
            "      - server.js\n"
        ),
    )

    results = validate_mcp_definitions(tmp_path)

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


def test_validate_registry_finds_all(tmp_path: Path):
    """validate_registry should discover skills/, mcp/, agents/, and hooks/ entries."""
    # Create a valid skill.
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: A demo skill\n---\n\n"
        "# Demo\n\nSome content.\n"
    )

    # Create a valid MCP definition.
    _write_mcp_yaml(
        tmp_path,
        "demo-server.yaml",
        (
            "name: demo-server\n"
            "description: A demo MCP server.\n"
            "config:\n"
            "  demo-server:\n"
            "    type: stdio\n"
            "    command: echo\n"
        ),
    )

    # Create a valid agent definition.
    _write_agent_md(
        tmp_path,
        "demo-agent.md",
        (
            "---\n"
            "name: demo-agent\n"
            "description: A demo agent.\n"
            "skills:\n"
            "  - demo-skill\n"
            "---\n\n"
            "# Demo Agent\n\nYou are a demo agent.\n"
        ),
    )

    # Create a valid hook definition.
    _make_hook_dir(
        tmp_path,
        "demo-hook",
        "A demo hook.",
        entrypoint_mode=0o755,
    )

    results = validate_registry(tmp_path)

    assert len(results) == 4, (
        f"Expected 4 results (1 skill + 1 MCP + 1 agent + 1 hook), "
        f"got {len(results)}"
    )
    assert all(r.valid for r in results), (
        f"Expected all results to be valid, got errors: "
        f"{[(r.file, [e.message for e in r.errors]) for r in results if not r.valid]}"
    )


# ---------------------------------------------------------------------------
# JSON output format test (CLI subprocess)
# ---------------------------------------------------------------------------


def test_json_output_format(tmp_path: Path):
    """The CLI with --format json should output valid JSON with the right structure."""
    # Create a valid skill.
    skill_dir = tmp_path / "skills" / "json-test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: json-test\ndescription: JSON output test\n---\n\n"
        "# JSON Test\n\nContent here.\n"
    )

    # Create a valid MCP definition.
    _write_mcp_yaml(
        tmp_path,
        "json-test.yaml",
        (
            "name: json-test\n"
            "description: For testing JSON output.\n"
            "config:\n"
            "  json-test:\n"
            "    type: stdio\n"
            "    command: echo\n"
        ),
    )

    # Create a valid agent definition.
    _write_agent_md(
        tmp_path,
        "json-test.md",
        (
            "---\n"
            "name: json-test\n"
            "description: Agent for JSON output test.\n"
            "skills:\n"
            "  - json-test\n"
            "---\n\n"
            "# JSON Test Agent\n\nYou are a test agent.\n"
        ),
    )

    # Create a valid hook definition.
    _make_hook_dir(
        tmp_path,
        "json-test",
        "Hook for JSON output test.",
        entrypoint_mode=0o755,
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "awos_recruitment_mcp.validate",
            "--format",
            "json",
            "--registry-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Expected exit code 0, got {result.returncode}. stderr: {result.stderr}"
    )

    data = json.loads(result.stdout)

    assert "valid" in data, "JSON output must contain 'valid' key"
    assert "errors" in data, "JSON output must contain 'errors' key"
    assert "summary" in data, "JSON output must contain 'summary' key"

    assert isinstance(data["valid"], bool), (
        f"'valid' should be a bool, got {type(data['valid']).__name__}"
    )
    assert data["valid"] is True, (
        f"Expected valid=true for clean registry, got {data['valid']}"
    )
    assert isinstance(data["errors"], list), (
        f"'errors' should be a list, got {type(data['errors']).__name__}"
    )
    assert data["errors"] == [], (
        f"Expected no errors, got: {data['errors']}"
    )

    summary = data["summary"]
    assert isinstance(summary, dict), (
        f"'summary' should be a dict, got {type(summary).__name__}"
    )
    assert summary["total"] == 4, (
        f"Expected total=4, got {summary['total']}"
    )
    assert summary["passed"] == 4, (
        f"Expected passed=4, got {summary['passed']}"
    )
    assert summary["failed"] == 0, (
        f"Expected failed=0, got {summary['failed']}"
    )


# ---------------------------------------------------------------------------
# Name-matching validation tests
# ---------------------------------------------------------------------------


def test_validate_skill_directory_name_mismatch(tmp_path: Path):
    """A skill whose directory name differs from its metadata name should fail."""
    skill_dir = tmp_path / "skills" / "wrong-dir"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: correct-name\ndescription: Directory mismatch test\n---\n\n"
        "# Mismatch\n\nSome content.\n"
    )

    results = validate_skills(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result for directory mismatch"
    error_fields = [e.field for e in results[0].errors]
    assert "name" in error_fields, (
        f"Expected a 'name' field error, got: {error_fields}"
    )
    error_messages = [e.message for e in results[0].errors]
    assert any("does not match" in m for m in error_messages), (
        f"Expected a 'does not match' error, got: {error_messages}"
    )


def test_validate_mcp_filename_mismatch(tmp_path: Path):
    """An MCP file whose stem differs from the name field should fail."""
    _write_mcp_yaml(
        tmp_path,
        "wrong-file.yaml",
        (
            "name: correct-name\n"
            "description: Filename mismatch test.\n"
            "config:\n"
            "  correct-name:\n"
            "    type: stdio\n"
            "    command: echo\n"
        ),
    )

    results = validate_mcp_definitions(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result for filename mismatch"
    error_fields = [e.field for e in results[0].errors]
    assert "name" in error_fields, (
        f"Expected a 'name' field error, got: {error_fields}"
    )
    error_messages = [e.message for e in results[0].errors]
    assert any("does not match" in m for m in error_messages), (
        f"Expected a 'does not match' error, got: {error_messages}"
    )


def test_mcp_name_rejects_uppercase():
    """McpDefinition.name must reject uppercase letters."""
    with pytest.raises(ValidationError) as exc_info:
        McpDefinition.model_validate(
            {
                "name": "My-Server",
                "description": "Uppercase in name",
                "config": {"my-server": {"type": "stdio", "command": "echo"}},
            }
        )
    error_fields = {
        ".".join(str(p) for p in e["loc"]) for e in exc_info.value.errors()
    }
    assert "name" in error_fields, (
        f"Expected a validation error for 'name', got errors for: {error_fields}"
    )


# ---------------------------------------------------------------------------
# validate_agents function tests
# ---------------------------------------------------------------------------


def _write_agent_md(registry_root: Path, filename: str, content: str) -> None:
    """Helper: write an agent .md file inside registry_root/agents/."""
    agents_dir = registry_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / filename).write_text(content)


def test_validate_agent_valid(tmp_path: Path):
    """A well-formed agent .md file should pass validation with no errors."""
    # Create skill directories that the agent references.
    (tmp_path / "skills" / "python-dev").mkdir(parents=True)
    (tmp_path / "skills" / "testing").mkdir(parents=True)

    _write_agent_md(
        tmp_path,
        "good-agent.md",
        (
            "---\n"
            "name: good-agent\n"
            "description: A valid agent definition.\n"
            "model: sonnet\n"
            "skills:\n"
            "  - python-dev\n"
            "  - testing\n"
            "---\n\n"
            "# Good Agent\n\nYou are a helpful assistant.\n"
        ),
    )

    results = validate_agents(tmp_path)

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


def test_validate_agent_invalid_metadata(tmp_path: Path):
    """An agent .md with invalid metadata should produce validation errors."""
    _write_agent_md(
        tmp_path,
        "bad-agent.md",
        (
            "---\n"
            "name: Bad Agent!\n"
            "description: \"\"\n"
            "---\n\n"
            "# Bad Agent\n\nSome content.\n"
        ),
    )

    results = validate_agents(tmp_path)

    assert len(results) == 1, (
        f"Expected exactly 1 result, got {len(results)}"
    )
    assert not results[0].valid, "Expected invalid result for bad metadata"
    error_fields = [e.field for e in results[0].errors]
    assert "name" in error_fields, (
        f"Expected a 'name' field error, got: {error_fields}"
    )


def test_validate_agent_filename_name_mismatch(tmp_path: Path):
    """An agent file whose stem differs from the name field should fail."""
    _write_agent_md(
        tmp_path,
        "wrong-file.md",
        (
            "---\n"
            "name: correct-name\n"
            "description: Filename mismatch test.\n"
            "---\n\n"
            "# Agent\n\nSystem prompt content.\n"
        ),
    )

    results = validate_agents(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result for filename mismatch"
    error_fields = [e.field for e in results[0].errors]
    assert "name" in error_fields, (
        f"Expected a 'name' field error, got: {error_fields}"
    )
    error_messages = [e.message for e in results[0].errors]
    assert any("does not match" in m for m in error_messages), (
        f"Expected a 'does not match' error, got: {error_messages}"
    )


def test_validate_agent_empty_body(tmp_path: Path):
    """An agent .md with valid front matter but an empty body should fail."""
    _write_agent_md(
        tmp_path,
        "empty-body.md",
        "---\nname: empty-body\ndescription: Agent with no body\n---\n",
    )

    results = validate_agents(tmp_path)

    assert len(results) == 1, (
        f"Expected exactly 1 result, got {len(results)}"
    )
    assert not results[0].valid, "Expected the result to be invalid (empty body)"
    error_messages = [e.message for e in results[0].errors]
    assert any("empty" in m.lower() for m in error_messages), (
        f"Expected an 'empty' body error, got: {error_messages}"
    )


def test_validate_agent_missing_skill_reference(tmp_path: Path):
    """An agent referencing a non-existent skill should produce a validation error."""
    _write_agent_md(
        tmp_path,
        "bad-ref.md",
        (
            "---\n"
            "name: bad-ref\n"
            "description: References a missing skill.\n"
            "skills:\n"
            "  - nonexistent-skill\n"
            "---\n\n"
            "# Agent\n\nSystem prompt here.\n"
        ),
    )

    results = validate_agents(tmp_path)

    assert len(results) == 1
    assert not results[0].valid, "Expected invalid result for missing skill reference"
    error_fields = [e.field for e in results[0].errors]
    assert "skills" in error_fields, (
        f"Expected a 'skills' field error, got: {error_fields}"
    )
    error_messages = [e.message for e in results[0].errors]
    assert any("nonexistent-skill" in m for m in error_messages), (
        f"Expected error mentioning 'nonexistent-skill', got: {error_messages}"
    )


def test_validate_agent_valid_skill_reference(tmp_path: Path):
    """An agent referencing an existing skill directory should pass."""
    # Create the skill directory.
    (tmp_path / "skills" / "real-skill").mkdir(parents=True)

    _write_agent_md(
        tmp_path,
        "ref-agent.md",
        (
            "---\n"
            "name: ref-agent\n"
            "description: References an existing skill.\n"
            "skills:\n"
            "  - real-skill\n"
            "---\n\n"
            "# Agent\n\nSystem prompt content.\n"
        ),
    )

    results = validate_agents(tmp_path)

    assert len(results) == 1
    assert results[0].valid, (
        f"Expected the result to be valid, got errors: "
        f"{[e.message for e in results[0].errors]}"
    )


# ---------------------------------------------------------------------------
# Smoke test against the real registry
# ---------------------------------------------------------------------------


def test_real_registry_passes():
    """Run validate_registry against the real registry and assert all entries pass."""
    # The real registry lives at ../../registry relative to server/.
    real_registry = Path(__file__).resolve().parent.parent.parent / "registry"

    if not real_registry.is_dir():
        pytest.skip(f"Real registry not found at {real_registry}")

    results = validate_registry(real_registry)

    assert len(results) > 0, "Expected at least one registry entry to validate"
    for result in results:
        assert result.valid, (
            f"Real registry file '{result.file}' failed validation: "
            f"{[e.message for e in result.errors]}"
        )
