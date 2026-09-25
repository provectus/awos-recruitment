"""Tests for the skill-quality gate (Anthropic skill-authoring best practices).

One violation test and one passing test per rule. Errors come from the
Pydantic models (front matter) and validate/quality.py (body and references);
warnings never make a result invalid unless the CLI runs with --strict.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from awos_recruitment_mcp.models import AgentMetadata, SkillMetadata
from awos_recruitment_mcp.validate import (
    ValidationResult,
    validate_agents,
    validate_skills,
)

GOOD_DESCRIPTION = "Formats widgets. Use when the user asks to format widgets."


def _make_skill(
    tmp_path: Path,
    body: str = "# Widgets\n\nFormat them.\n",
    description: str = GOOD_DESCRIPTION,
    name: str = "widget-skill",
    references: dict[str, str] | None = None,
    extra_files: dict[str, str] | None = None,
) -> Path:
    """Create a skill directory with the given body and reference files."""
    skill_dir = tmp_path / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {json.dumps(description)}\n---\n\n{body}"
    )
    for ref_name, content in (references or {}).items():
        (skill_dir / "references").mkdir(exist_ok=True)
        (skill_dir / "references" / ref_name).write_text(content)
    for rel, content in (extra_files or {}).items():
        (skill_dir / rel).write_text(content)
    return skill_dir


def _only_result(tmp_path: Path) -> ValidationResult:
    results = validate_skills(tmp_path)
    assert len(results) == 1, f"Expected exactly 1 result, got {len(results)}"
    return results[0]


def _rules(issues: list) -> list[str | None]:
    return [issue.rule for issue in issues]


def _model_messages(exc: pytest.ExceptionInfo[ValidationError]) -> list[str]:
    return [e["msg"] for e in exc.value.errors()]


# ---------------------------------------------------------------------------
# Front matter (errors, enforced by the Pydantic models)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", [SkillMetadata, AgentMetadata])
@pytest.mark.parametrize("name", ["claude-helper", "anthropic-tools", "my-claude"])
def test_name_rejects_reserved_words(model, name: str):
    """Rule name-reserved-word: 'anthropic'/'claude' are rejected in names."""
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({"name": name, "description": GOOD_DESCRIPTION})
    messages = _model_messages(exc_info)
    assert any("reserved word" in m for m in messages), (
        f"name-reserved-word: expected '{name}' to be rejected, got {messages}"
    )


@pytest.mark.parametrize("model", [SkillMetadata, AgentMetadata])
def test_name_without_reserved_words_passes(model):
    """Rule name-reserved-word: an ordinary name is accepted."""
    meta = model.model_validate({"name": "pdf-tools", "description": GOOD_DESCRIPTION})
    assert meta.name == "pdf-tools", "name-reserved-word: valid name was altered"


@pytest.mark.parametrize("model", [SkillMetadata, AgentMetadata])
def test_name_rejects_xml_tags(model):
    """Rule name-xml: a name carrying an XML tag is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({"name": "<tool>", "description": GOOD_DESCRIPTION})
    assert exc_info.value.errors(), "name-xml: expected '<tool>' to be rejected"


@pytest.mark.parametrize("model", [SkillMetadata, AgentMetadata])
def test_description_max_length(model):
    """Rule description-length: 1024 chars pass, 1025 chars fail."""
    model.model_validate({"name": "ok-name", "description": "a" * 1024})
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({"name": "ok-name", "description": "a" * 1025})
    messages = _model_messages(exc_info)
    assert any("1025 characters" in m and "1024" in m for m in messages), (
        f"description-length: expected a 1024-char limit error, got {messages}"
    )


@pytest.mark.parametrize("model", [SkillMetadata, AgentMetadata])
def test_description_rejects_xml_tags(model):
    """Rule description-xml: XML tags in a description are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(
            {"name": "ok-name", "description": "Use when <example>x</example>."}
        )
    messages = _model_messages(exc_info)
    assert any("XML tags" in m for m in messages), (
        f"description-xml: expected an XML-tag error, got {messages}"
    )


@pytest.mark.parametrize("model", [SkillMetadata, AgentMetadata])
def test_description_comparison_operators_pass(model):
    """Rule description-xml: '<' and '>' that are not tags are accepted."""
    model.model_validate(
        {"name": "ok-name", "description": "Use when latency < 5 ms or n > 3."}
    )


def test_validator_reports_description_length_as_error(tmp_path: Path):
    """Rule description-length surfaces through validate_skills as an error."""
    _make_skill(tmp_path, description="Use when x. " + "a" * 1024)
    result = _only_result(tmp_path)
    assert not result.valid, "description-length: over-long description passed"
    assert any(e.field == "description" for e in result.errors), (
        f"description-length: expected a 'description' error, got {result.errors}"
    )


# ---------------------------------------------------------------------------
# SKILL.md body length (error)
# ---------------------------------------------------------------------------


def test_body_over_500_lines_fails(tmp_path: Path):
    """Rule skill-body-length: 501 body lines is an error."""
    _make_skill(tmp_path, body="line\n" * 501)
    result = _only_result(tmp_path)
    assert "skill-body-length" in _rules(result.errors), (
        f"skill-body-length: expected an error, got {_rules(result.errors)}"
    )
    assert not result.valid, "skill-body-length: result should be invalid"


def test_body_of_500_lines_passes(tmp_path: Path):
    """Rule skill-body-length: exactly 500 body lines is fine."""
    _make_skill(tmp_path, body="line\n" * 500)
    result = _only_result(tmp_path)
    assert "skill-body-length" not in _rules(result.errors), (
        "skill-body-length: 500 lines should pass"
    )


# ---------------------------------------------------------------------------
# Relative links (error)
# ---------------------------------------------------------------------------


def test_broken_link_in_skill_md_fails(tmp_path: Path):
    """Rule broken-link: a link to a missing file is an error with its line."""
    _make_skill(tmp_path, body="# T\n\nSee [guide](references/missing.md).\n")
    result = _only_result(tmp_path)
    broken = [e for e in result.errors if e.rule == "broken-link"]
    assert broken, f"broken-link: expected an error, got {_rules(result.errors)}"
    assert broken[0].file == "skills/widget-skill/SKILL.md", (
        f"broken-link: wrong file {broken[0].file}"
    )
    assert broken[0].line == 8, (
        f"broken-link: expected file line 8 (4 front-matter lines + body), got {broken[0].line}"
    )


def test_broken_link_in_reference_fails(tmp_path: Path):
    """Rule broken-link: references/*.md links are resolved from references/."""
    _make_skill(
        tmp_path,
        body="# T\n\nSee [a](references/a.md).\n",
        references={"a.md": "# A\n\nBack to [skill](../SKILL.md), [x](nope.md).\n"},
    )
    result = _only_result(tmp_path)
    broken = [e for e in result.errors if e.rule == "broken-link"]
    assert len(broken) == 1, (
        f"broken-link: expected only 'nope.md' to be broken, got {broken}"
    )
    assert broken[0].file.endswith("references/a.md"), (
        f"broken-link: wrong file {broken[0].file}"
    )


def test_link_outside_skill_dir_fails(tmp_path: Path):
    """Rule broken-link: a link that escapes the skill directory is an error."""
    skill_dir = _make_skill(tmp_path, body="# T\n\nSee [other](../other/SKILL.md).\n")
    (skill_dir.parent / "other").mkdir()
    (skill_dir.parent / "other" / "SKILL.md").write_text("x")
    result = validate_skills(tmp_path)
    ours = next(r for r in result if "widget-skill" in r.file)
    assert "broken-link" in _rules(ours.errors), (
        f"broken-link: link outside the skill dir passed, got {_rules(ours.errors)}"
    )


def test_link_to_unbundled_readme_fails(tmp_path: Path):
    """Rule broken-link: README.md exists but is not shipped, so linking it fails."""
    _make_skill(
        tmp_path,
        body="# T\n\nSee [readme](README.md).\n",
        extra_files={"README.md": "# Readme\n"},
    )
    result = _only_result(tmp_path)
    assert "broken-link" in _rules(result.errors), (
        f"broken-link: link to unbundled README.md passed, got {_rules(result.errors)}"
    )


def test_valid_links_pass(tmp_path: Path):
    """Rule broken-link: existing files, anchors, URLs and code samples pass."""
    body = (
        "# T\n\n"
        "See [guide](references/guide.md#setup) and [top](#t).\n"
        "Docs at [site](https://example.com/x.md) and [mail](mailto:a@b.c).\n"
        "Code `[x](not-a-link.md)` is ignored.\n\n"
        "```python\nclass Foo[T](Protocol): ...\n```\n"
    )
    _make_skill(tmp_path, body=body, references={"guide.md": "# Guide\n"})
    result = _only_result(tmp_path)
    assert "broken-link" not in _rules(result.errors), (
        f"broken-link: valid links flagged: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Windows-style paths (error)
# ---------------------------------------------------------------------------


def test_backslash_link_fails(tmp_path: Path):
    """Rule windows-path: a link with backslashes is an error."""
    _make_skill(
        tmp_path,
        body="# T\n\nSee [g](references\\guide.md).\n",
        references={"guide.md": "# G\n"},
    )
    result = _only_result(tmp_path)
    assert "windows-path" in _rules(result.errors), (
        f"windows-path: backslash link passed, got {_rules(result.errors)}"
    )


def test_backslash_path_in_inline_code_fails(tmp_path: Path):
    """Rule windows-path: a backslash file path in inline code is an error."""
    _make_skill(tmp_path, body="# T\n\nRun `python scripts\\helper.py`.\n")
    result = _only_result(tmp_path)
    assert "windows-path" in _rules(result.errors), (
        f"windows-path: backslash code path passed, got {_rules(result.errors)}"
    )


def test_forward_slash_paths_pass(tmp_path: Path):
    """Rule windows-path: forward slashes and regex escapes pass."""
    _make_skill(
        tmp_path,
        body="# T\n\nRun `python scripts/helper.py`; match `\\d+`.\n",
    )
    result = _only_result(tmp_path)
    assert "windows-path" not in _rules(result.errors), (
        f"windows-path: forward-slash path flagged: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Agent skill references (error)
# ---------------------------------------------------------------------------


def _write_agent(tmp_path: Path, skills: list[str]) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_yaml = "".join(f"  - {s}\n" for s in skills)
    (agents_dir / "helper.md").write_text(
        f"---\nname: helper\ndescription: Helps.\nskills:\n{skills_yaml}---\n\n"
        "You help.\n"
    )


def test_agent_unknown_skill_fails(tmp_path: Path):
    """Rule agent-skill-exists: an agent naming a missing skill is an error."""
    _write_agent(tmp_path, ["ghost-skill"])
    (result,) = validate_agents(tmp_path)
    assert "agent-skill-exists" in _rules(result.errors), (
        f"agent-skill-exists: missing skill passed, got {_rules(result.errors)}"
    )


def test_agent_known_skill_passes(tmp_path: Path):
    """Rule agent-skill-exists: an agent naming an existing skill passes."""
    _make_skill(tmp_path)
    _write_agent(tmp_path, ["widget-skill"])
    (result,) = validate_agents(tmp_path)
    assert result.valid, f"agent-skill-exists: valid reference failed: {result.errors}"


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def test_warnings_do_not_invalidate(tmp_path: Path):
    """A skill with only warnings stays valid and keeps errors empty."""
    _make_skill(tmp_path, description="Formats widgets.")
    result = _only_result(tmp_path)
    assert result.valid, f"Warnings must not invalidate, got {result.errors}"
    assert result.errors == [], f"Expected no errors, got {result.errors}"
    assert all(w.severity == "warning" for w in result.warnings), (
        f"Expected only warnings, got {result.warnings}"
    )


def test_long_reference_without_toc_warns(tmp_path: Path):
    """Rule reference-toc: a 101-line reference with no contents warns."""
    _make_skill(
        tmp_path,
        body="# T\n\nSee [a](references/a.md).\n",
        references={"a.md": "# A\n" + "text\n" * 100},
    )
    result = _only_result(tmp_path)
    assert "reference-toc" in _rules(result.warnings), (
        f"reference-toc: expected a warning, got {_rules(result.warnings)}"
    )


@pytest.mark.parametrize(
    "content",
    [
        "# A\n\n## Contents\n- One\n- Two\n\n" + "text\n" * 100,
        "# A\n\n## Table of Contents\n\n" + "text\n" * 100,
        "# A\n\n1. [One](#one)\n2. [Two](#two)\n3. [Three](#three)\n\n"
        + "text\n" * 100,
        "# A\n" + "text\n" * 99,
    ],
    ids=["contents-heading", "toc-heading", "anchor-list", "short-file"],
)
def test_reference_with_toc_or_short_passes(tmp_path: Path, content: str):
    """Rule reference-toc: a contents section near the top, or ≤100 lines, passes."""
    _make_skill(
        tmp_path,
        body="# T\n\nSee [a](references/a.md).\n",
        references={"a.md": content},
    )
    result = _only_result(tmp_path)
    assert "reference-toc" not in _rules(result.warnings), (
        f"reference-toc: should pass, got {result.warnings}"
    )


def test_reference_with_toc_below_window_warns(tmp_path: Path):
    """Rule reference-toc: a contents heading buried past line 40 does not count."""
    content = "# A\n" + "text\n" * 50 + "## Contents\n" + "text\n" * 60
    _make_skill(
        tmp_path,
        body="# T\n\nSee [a](references/a.md).\n",
        references={"a.md": content},
    )
    result = _only_result(tmp_path)
    assert "reference-toc" in _rules(result.warnings), (
        f"reference-toc: buried TOC accepted, got {_rules(result.warnings)}"
    )


def test_nested_reference_warns(tmp_path: Path):
    """Rule nested-reference: a reference linking another reference warns."""
    _make_skill(
        tmp_path,
        body="# T\n\nSee [a](references/a.md).\n",
        references={"a.md": "# A\n\nSee [b](b.md).\n", "b.md": "# B\n"},
    )
    result = _only_result(tmp_path)
    assert "nested-reference" in _rules(result.warnings), (
        f"nested-reference: expected a warning, got {_rules(result.warnings)}"
    )


def test_reference_linking_back_to_skill_md_passes(tmp_path: Path):
    """Rule nested-reference: links back to SKILL.md and to itself do not count."""
    _make_skill(
        tmp_path,
        body="# T\n\nSee [a](references/a.md).\n",
        references={"a.md": "# A\n\nBack to [skill](../SKILL.md#t), [top](a.md#a).\n"},
    )
    result = _only_result(tmp_path)
    assert "nested-reference" not in _rules(result.warnings), (
        f"nested-reference: link to SKILL.md flagged: {result.warnings}"
    )


def test_description_without_trigger_warns(tmp_path: Path):
    """Rule description-trigger: a description that never says when to use it warns."""
    _make_skill(tmp_path, description="Formats widgets and gadgets.")
    result = _only_result(tmp_path)
    assert "description-trigger" in _rules(result.warnings), (
        f"description-trigger: expected a warning, got {_rules(result.warnings)}"
    )


@pytest.mark.parametrize(
    "description",
    [
        "Formats widgets. Use when the user asks to format widgets.",
        "This skill should be used when the user asks to \"format a widget\".",
        "Formats widgets. Triggers on 'widget', 'gadget'.",
    ],
)
def test_description_with_trigger_passes(tmp_path: Path, description: str):
    """Rule description-trigger: common trigger phrasings pass."""
    _make_skill(tmp_path, description=description)
    result = _only_result(tmp_path)
    assert "description-trigger" not in _rules(result.warnings), (
        f"description-trigger: '{description}' flagged"
    )


@pytest.mark.parametrize(
    "description",
    [
        "I can help you format widgets. Use when formatting widgets.",
        "You can use this to format widgets. Use when formatting widgets.",
        "Lets you format widgets. Use when formatting widgets.",
    ],
)
def test_description_first_or_second_person_warns(tmp_path: Path, description: str):
    """Rule description-person: first/second-person voice warns."""
    _make_skill(tmp_path, description=description)
    result = _only_result(tmp_path)
    assert "description-person" in _rules(result.warnings), (
        f"description-person: '{description}' not flagged"
    )


def test_description_third_person_passes(tmp_path: Path):
    """Rule description-person: third person, including 'when you …', passes."""
    _make_skill(
        tmp_path,
        description="Formats widgets and handles I/O. Use when you need widgets.",
    )
    result = _only_result(tmp_path)
    assert "description-person" not in _rules(result.warnings), (
        f"description-person: third-person description flagged: {result.warnings}"
    )


def test_caps_emphasis_at_threshold_warns(tmp_path: Path):
    """Rule caps-emphasis: 5 all-caps emphasis words in one file warns."""
    body = "# T\n\nYou MUST do a. NEVER do b. ALWAYS c. IMPORTANT: d. CRITICAL: e.\n"
    _make_skill(tmp_path, body=body)
    result = _only_result(tmp_path)
    assert "caps-emphasis" in _rules(result.warnings), (
        f"caps-emphasis: expected a warning, got {_rules(result.warnings)}"
    )


def test_caps_emphasis_below_threshold_or_in_code_passes(tmp_path: Path):
    """Rule caps-emphasis: 4 in prose passes; words inside code do not count."""
    body = (
        "# T\n\nYou MUST do a. NEVER do b. ALWAYS c. IMPORTANT: d.\n\n"
        "```\nMUST MUST MUST NEVER\n```\n`ALWAYS`\n"
    )
    _make_skill(tmp_path, body=body)
    result = _only_result(tmp_path)
    assert "caps-emphasis" not in _rules(result.warnings), (
        f"caps-emphasis: should pass, got {result.warnings}"
    )


@pytest.mark.parametrize(
    "phrase",
    ["before August 2025", "until August 31, 2026", "as of 2024", "after mid-2025"],
)
def test_time_sensitive_phrase_warns(tmp_path: Path, phrase: str):
    """Rule time-sensitive: dated wording in normal prose warns."""
    _make_skill(tmp_path, body=f"# T\n\nUse the old API {phrase}.\n")
    result = _only_result(tmp_path)
    assert "time-sensitive" in _rules(result.warnings), (
        f"time-sensitive: '{phrase}' not flagged"
    )


def test_time_sensitive_phrase_in_old_patterns_passes(tmp_path: Path):
    """Rule time-sensitive: dated wording under 'Old patterns' is allowed."""
    body = (
        "# T\n\n## Current method\n\nUse v2.\n\n"
        "## Old patterns\n\n### v1\n\nBefore August 2025, v1 was used.\n\n"
        "## Next\n\nUse v2 everywhere.\n"
    )
    _make_skill(tmp_path, body=body)
    result = _only_result(tmp_path)
    assert "time-sensitive" not in _rules(result.warnings), (
        f"time-sensitive: 'Old patterns' section flagged: {result.warnings}"
    )


# ---------------------------------------------------------------------------
# CLI: severity, --strict, GitHub annotations, summary
# ---------------------------------------------------------------------------


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "awos_recruitment_mcp.validate",
            "--registry-path",
            str(tmp_path),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_warnings_pass_by_default_and_fail_with_strict(tmp_path: Path):
    """Warnings exit 0 by default and 1 under --strict; human output shows WARN."""
    _make_skill(tmp_path, description="Formats widgets.")

    default = _run_cli(tmp_path)
    assert default.returncode == 0, f"Warnings failed by default: {default.stdout}"
    assert "WARN" in default.stdout and "description-trigger" in default.stdout, (
        f"Expected a WARN line naming the rule, got: {default.stdout}"
    )

    strict = _run_cli(tmp_path, "--strict")
    assert strict.returncode == 1, f"--strict did not fail on warnings: {strict.stdout}"


def test_cli_json_carries_severity(tmp_path: Path):
    """JSON output lists warnings separately and every item carries severity."""
    _make_skill(tmp_path, description="Formats widgets.", body="line\n" * 501)

    result = _run_cli(tmp_path, "--format", "json")
    data = json.loads(result.stdout)
    assert result.returncode == 1, "skill-body-length error should fail the run"
    assert {e["severity"] for e in data["errors"]} == {"error"}, data["errors"]
    assert {w["severity"] for w in data["warnings"]} == {"warning"}, data["warnings"]
    assert "skill-body-length" in [e["rule"] for e in data["errors"]], data["errors"]
    assert data["summary"]["warnings"] == len(data["warnings"]), data["summary"]


def test_cli_github_annotations_and_summary(tmp_path: Path):
    """--format github prints workflow annotations; --summary writes markdown."""
    _make_skill(tmp_path, description="Formats widgets.")
    summary = tmp_path / "summary.md"

    result = _run_cli(tmp_path, "--format", "github", "--summary", str(summary))
    assert result.returncode == 0, result.stdout
    assert "::warning file=" in result.stdout, (
        f"Expected a ::warning annotation, got: {result.stdout}"
    )
    assert "title=description-trigger" in result.stdout, result.stdout
    text = summary.read_text()
    assert "| warning | `description-trigger` | 1 |" in text, text
    assert "| `skills/widget-skill` | 0 | 1 |" in text, text
