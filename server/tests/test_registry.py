"""Tests for the registry loader module."""

from __future__ import annotations

from pathlib import Path

import pytest

from awos_recruitment_mcp.registry import load_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(
    registry_root: Path,
    folder_name: str,
    name: str,
    description: str | None = None,
    body: str = "# Skill\n\nSome content.\n",
) -> None:
    """Write a SKILL.md file inside ``registry_root/skills/<folder_name>/``."""
    skill_dir = registry_root / "skills" / folder_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    front_matter_lines = [f"name: {name}"]
    if description is not None:
        front_matter_lines.append(f"description: {description}")

    content = "---\n" + "\n".join(front_matter_lines) + "\n---\n\n" + body
    (skill_dir / "SKILL.md").write_text(content)


def _write_mcp_yaml(
    registry_root: Path,
    filename: str,
    name: str,
    description: str | None = None,
) -> None:
    """Write an MCP YAML file inside ``registry_root/mcp/``."""
    mcp_dir = registry_root / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    lines = [f'name: "{name}"']
    if description is not None:
        lines.append(f'description: "{description}"')
    lines.extend(
        [
            "config:",
            f"  {filename.removesuffix('.yaml')}:",
            "    type: stdio",
            "    command: echo",
        ]
    )
    (mcp_dir / filename).write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Correct parsing
# ---------------------------------------------------------------------------


class TestCorrectParsing:
    """Given valid skill and MCP files, all capabilities are loaded correctly."""

    def test_loads_all_capabilities(self, tmp_path: Path) -> None:
        _write_skill(tmp_path, "python", "python-skill", "A Python skill")
        _write_skill(tmp_path, "typescript", "ts-skill", "A TypeScript skill")
        _write_mcp_yaml(tmp_path, "context7.yaml", "Context7", "Docs lookup")
        _write_mcp_yaml(tmp_path, "playwright.yaml", "Playwright", "Browser automation")

        caps = load_registry(tmp_path)

        assert len(caps) == 4, (
            f"Expected 4 capabilities, got {len(caps)}"
        )

    def test_skill_fields(self, tmp_path: Path) -> None:
        _write_skill(tmp_path, "demo", "demo-skill", "Demo description")

        caps = load_registry(tmp_path)

        assert len(caps) == 1
        cap = caps[0]
        assert cap.name == "demo-skill"
        assert cap.description == "Demo description"
        assert cap.type == "skill"

    def test_mcp_tool_fields(self, tmp_path: Path) -> None:
        _write_mcp_yaml(tmp_path, "my-tool.yaml", "My Tool", "Tool description")

        caps = load_registry(tmp_path)

        assert len(caps) == 1
        cap = caps[0]
        assert cap.name == "My Tool"
        assert cap.description == "Tool description"
        assert cap.type == "tool"


# ---------------------------------------------------------------------------
# Skip without description
# ---------------------------------------------------------------------------


class TestSkipWithoutDescription:
    """Entries missing or having empty descriptions are skipped."""

    def test_skill_no_description_field(self, tmp_path: Path) -> None:
        _write_skill(tmp_path, "no-desc", "no-desc-skill", description=None)

        caps = load_registry(tmp_path)

        assert len(caps) == 0, (
            f"Expected 0 capabilities (skill missing description), got {len(caps)}"
        )

    def test_skill_empty_description(self, tmp_path: Path) -> None:
        _write_skill(tmp_path, "empty-desc", "empty-desc-skill", description="")

        caps = load_registry(tmp_path)

        assert len(caps) == 0, (
            f"Expected 0 capabilities (skill empty description), got {len(caps)}"
        )

    def test_skill_whitespace_description(self, tmp_path: Path) -> None:
        _write_skill(tmp_path, "ws-desc", "ws-desc-skill", description="   ")

        caps = load_registry(tmp_path)

        assert len(caps) == 0, (
            f"Expected 0 capabilities (skill whitespace description), got {len(caps)}"
        )

    def test_mcp_no_description_field(self, tmp_path: Path) -> None:
        _write_mcp_yaml(tmp_path, "no-desc.yaml", "No Desc Tool", description=None)

        caps = load_registry(tmp_path)

        assert len(caps) == 0, (
            f"Expected 0 capabilities (MCP missing description), got {len(caps)}"
        )

    def test_mcp_empty_description(self, tmp_path: Path) -> None:
        _write_mcp_yaml(tmp_path, "empty-desc.yaml", "Empty Desc", description="")

        caps = load_registry(tmp_path)

        assert len(caps) == 0, (
            f"Expected 0 capabilities (MCP empty description), got {len(caps)}"
        )


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------


class TestTypeInference:
    """Skills get type='skill', MCP definitions get type='tool'."""

    def test_skills_have_type_skill(self, tmp_path: Path) -> None:
        _write_skill(tmp_path, "alpha", "alpha-skill", "Alpha description")

        caps = load_registry(tmp_path)

        assert all(c.type == "skill" for c in caps), (
            f"Expected all types to be 'skill', got {[c.type for c in caps]}"
        )

    def test_mcp_tools_have_type_tool(self, tmp_path: Path) -> None:
        _write_mcp_yaml(tmp_path, "beta.yaml", "Beta Tool", "Beta description")

        caps = load_registry(tmp_path)

        assert all(c.type == "tool" for c in caps), (
            f"Expected all types to be 'tool', got {[c.type for c in caps]}"
        )

    def test_mixed_types(self, tmp_path: Path) -> None:
        _write_skill(tmp_path, "s1", "s1-skill", "Skill desc")
        _write_mcp_yaml(tmp_path, "t1.yaml", "T1 Tool", "Tool desc")

        caps = load_registry(tmp_path)

        types = {c.type for c in caps}
        assert types == {"skill", "tool"}, (
            f"Expected both 'skill' and 'tool' types, got {types}"
        )


# ---------------------------------------------------------------------------
# Empty registry
# ---------------------------------------------------------------------------


class TestEmptyRegistry:
    """An empty registry directory returns an empty list."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        caps = load_registry(tmp_path)

        assert caps == [], (
            f"Expected empty list for empty registry, got {caps}"
        )

    def test_empty_skills_and_mcp_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "skills").mkdir()
        (tmp_path / "mcp").mkdir()

        caps = load_registry(tmp_path)

        assert caps == [], (
            f"Expected empty list for registry with empty sub-dirs, got {caps}"
        )


# ---------------------------------------------------------------------------
# Smoke test against the real registry
# ---------------------------------------------------------------------------


def test_real_registry_loads_all_capabilities() -> None:
    """Load the real registry and verify the expected number of capabilities."""
    real_registry = Path(__file__).resolve().parent.parent.parent / "registry"

    if not real_registry.is_dir():
        pytest.skip(f"Real registry not found at {real_registry}")

    caps = load_registry(real_registry)

    assert len(caps) == 4, (
        f"Expected 4 capabilities (2 skills + 2 tools), got {len(caps)}: "
        f"{[(c.name, c.type) for c in caps]}"
    )

    skill_caps = [c for c in caps if c.type == "skill"]
    tool_caps = [c for c in caps if c.type == "tool"]

    assert len(skill_caps) == 2, (
        f"Expected 2 skills, got {len(skill_caps)}: {[c.name for c in skill_caps]}"
    )
    assert len(tool_caps) == 2, (
        f"Expected 2 tools, got {len(tool_caps)}: {[c.name for c in tool_caps]}"
    )
