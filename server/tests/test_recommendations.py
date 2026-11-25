"""Tests for recommendations: the matcher, the loader, validate and the MCP tools.

A recommendation is a capability that a stack probably needs but that is
not the knowledge of one of its technologies. The match is plain text on
whole words, so most tests pin what must and must not trigger an entry.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client

import awos_recruitment_mcp.recommendations as recommendations_module
import awos_recruitment_mcp.server as server_module
from awos_recruitment_mcp.models.capability import RegistryCapability
from awos_recruitment_mcp.models.recommendation import Recommendation
from awos_recruitment_mcp.recommendations import (
    RecommendationsFileError,
    has_phrase,
    load_recommendations,
    matched_term,
    recommend,
)
from awos_recruitment_mcp.validate import validate_recommendations, validate_registry

_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "registry"


def _rec(**overrides) -> Recommendation:
    data = {
        "id": "dr-for-cloud",
        "recommend": "disaster-recovery-plan",
        "type": "skill",
        "when_stack_has": ["aws", "google cloud"],
        "reason": "Plan for the loss of a region.",
        "examples": {"match": ["AWS"], "no_match": ["Java lambda"]},
    }
    data.update(overrides)
    return Recommendation.model_validate(data)


def _caps(*caps: tuple[str, str, bool | None]) -> dict:
    return {
        (t, n): RegistryCapability(
            name=n, description=f"{n} description", type=t, user_invoked=u
        )
        for t, n, u in caps
    }


_CAPS = _caps(
    ("skill", "disaster-recovery-plan", True),
    ("skill", "verify-ui", False),
    ("tool", "playwright", None),
    ("skill", "pr-review", False),
    ("skill", "other-skill", False),
)


def _text(result) -> str:
    return result.content[0].text if result.content else ""


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("term", "phrase", "expected"),
    [
        ("AWS", "aws", True),
        ("Terraform modules for AWS ECS", "aws", True),
        ("aws-sdk", "aws", True),
        ("Laws and regulations", "aws", False),
        ("Google  Cloud Run", "google cloud", True),
        ("Spring Cloud", "google cloud", False),
        ("Next.js 14", "next.js", True),
        ("nextjs", "next.js", False),
        ("Reactive streams", "react", False),
        ("React 18", "react", True),
    ],
)
def test_has_phrase_matches_whole_words_only(term, phrase, expected):
    assert has_phrase(term, phrase) is expected, (
        f"has_phrase({term!r}, {phrase!r}) must be {expected}: a phrase "
        "matches as whole words, case-insensitive, never inside a word"
    )


def test_unless_term_has_cancels_the_match_for_that_term_only():
    rec = _rec(when_stack_has=["react"], unless_term_has=["react native"])
    assert matched_term(rec, ["React Native"]) is None, (
        "A term with an unless phrase must not trigger the entry"
    )
    assert matched_term(rec, ["React Native", "React 18"]) == "React 18", (
        "Another term in the same stack can still trigger the entry"
    )


def test_unless_stack_has_cancels_the_match_for_the_whole_stack():
    rec = _rec(when_stack_has=["react", "tailwind"], unless_stack_has=["react native"])
    for stack in (
        ["React Native", "React Navigation"],
        ["React Native", "Tailwind CSS"],
        ["Tailwind CSS", "React Native"],
    ):
        assert matched_term(rec, stack) is None, (
            f"No term of {stack} may trigger the entry: the stack has React Native"
        )
    assert matched_term(rec, ["React 18", "React Navigation"]) == "React 18"


def test_unless_stack_has_drops_a_web_and_mobile_monorepo():
    """The chosen trade-off: a miss costs less than a false match."""
    rec = _rec(when_stack_has=["react"], unless_stack_has=["react native"])
    assert matched_term(rec, ["React 18 web app", "React Native app"]) is None


def test_matcher_reads_the_whole_term():
    rec = _rec(when_stack_has=["react"], unless_stack_has=["react native"])
    long_term = "x" * 95 + " React Native"
    assert matched_term(rec, [long_term, "React Navigation"]) is None, (
        "An exclusion phrase after the 100th character must still apply"
    )


# ---------------------------------------------------------------------------
# recommend()
# ---------------------------------------------------------------------------


def test_recommend_returns_the_item_shape():
    items = recommend([_rec()], _CAPS, ["Python", "AWS Lambda"])
    assert items == [
        {
            "id": "dr-for-cloud",
            "name": "disaster-recovery-plan",
            "type": "skill",
            "description": "disaster-recovery-plan description",
            "reason": "Plan for the loss of a region.",
            "matched_term": "AWS Lambda",
            "user_invoked": True,
        }
    ], f"Unexpected recommend() item shape: {items}"


def test_recommend_leaves_user_invoked_out_of_non_skill_items():
    rec = _rec(id="browser", recommend="playwright", type="tool")
    (item,) = recommend([rec], _CAPS, ["AWS"])
    assert "user_invoked" not in item, (
        f"user_invoked is a skill-only field, as in search; got {item}"
    )


def test_recommend_skips_excluded_names():
    items = recommend([_rec()], _CAPS, ["AWS"], exclude=["Disaster-Recovery-Plan"])
    assert items == [], "A target named in exclude must not be recommended"


def test_recommend_skips_declined_names():
    items = recommend([_rec()], _CAPS, ["AWS"], declined=["disaster-recovery-plan"])
    assert items == [], "A target named in declined must not be recommended"


def test_recommend_skips_an_entry_whose_requirement_was_declined():
    rec = _rec(id="ui", recommend="verify-ui", requires="playwright")
    assert recommend([rec], _CAPS, ["AWS"], declined=["Playwright"]) == [], (
        "verify-ui cannot run without playwright, so a declined playwright "
        "must drop it"
    )
    (item,) = recommend([rec], _CAPS, ["AWS"], exclude=["playwright"])
    assert item["name"] == "verify-ui", (
        "An installed playwright (in exclude, not declined) must keep verify-ui"
    )


def test_recommend_returns_a_target_once():
    second = _rec(id="dr-again", when_stack_has=["azure"])
    items = recommend([_rec(), second], _CAPS, ["AWS", "Azure"])
    assert [i["id"] for i in items] == ["dr-for-cloud"], (
        "Two entries with the same target must yield one item, the first in file order"
    )


def test_recommend_stops_at_the_limit():
    recs = [
        _rec(id=f"e{i}", recommend=name)
        for i, name in enumerate(
            ["disaster-recovery-plan", "verify-ui", "pr-review", "other-skill"]
        )
    ] + [_rec(id="e9", recommend="playwright", type="tool")]
    items = recommend(recs, _CAPS, ["AWS"])
    assert [i["id"] for i in items] == ["e0", "e1", "e2", "e3"], (
        f"recommend() must return at most 4 items in file order, got {items}"
    )


def test_recommend_skips_a_target_missing_from_the_registry():
    rec = _rec(recommend="no-such-skill")
    assert recommend([rec], _CAPS, ["AWS"]) == [], (
        "A target that is not in the registry must be left out, not returned"
    )


def test_recommend_needs_a_trigger():
    assert recommend([_rec()], _CAPS, ["Python", "Spring Cloud"]) == []


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def test_load_without_file_is_empty(tmp_path):
    assert load_recommendations(tmp_path) == []


def test_load_rejects_a_mapping(tmp_path):
    (tmp_path / "recommendations.yaml").write_text("dr: {}\n")
    with pytest.raises(RecommendationsFileError, match="list of entries"):
        load_recommendations(tmp_path)


def test_load_rejects_duplicate_ids(tmp_path):
    entry = (
        "- id: a\n  recommend: x\n  type: skill\n  when_stack_has: [aws]\n"
        "  reason: r\n  examples: {match: [AWS], no_match: [GCP]}\n"
    )
    (tmp_path / "recommendations.yaml").write_text(entry + entry)
    with pytest.raises(RecommendationsFileError, match="duplicate id 'a'"):
        load_recommendations(tmp_path)


def test_load_reports_a_non_utf8_file(tmp_path):
    (tmp_path / "recommendations.yaml").write_bytes(b"- id: \xff\xfe\n")
    with pytest.raises(RecommendationsFileError):
        load_recommendations(tmp_path)


def test_load_reports_an_unreadable_file(tmp_path, monkeypatch):
    (tmp_path / "recommendations.yaml").write_text("[]\n")

    def deny(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(recommendations_module, "open", deny, raising=False)
    with pytest.raises(RecommendationsFileError, match="denied"):
        load_recommendations(tmp_path)


def test_real_registry_file_loads():
    recs = load_recommendations(_REGISTRY_PATH)
    assert any(r.id == "dr-for-cloud" for r in recs), (
        "registry/recommendations.yaml must load and hold the dr-for-cloud entry"
    )


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def _write_registry(tmp_path: Path, recommendations: str) -> Path:
    skill = tmp_path / "skills" / "disaster-recovery-plan"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: disaster-recovery-plan\ndescription: DR plan\n"
        "disable-model-invocation: true\n---\nbody\n"
    )
    (tmp_path / "recommendations.yaml").write_text(recommendations)
    return tmp_path


def _messages(registry: Path) -> list[str]:
    (result,) = validate_recommendations(registry)
    return [e.message for e in result.errors]


def test_validate_real_registry_recommendations_are_valid():
    (result,) = validate_recommendations(_REGISTRY_PATH)
    assert result.valid, (
        "registry/recommendations.yaml must pass validate: "
        f"{[e.message for e in result.errors]}"
    )


def test_validate_registry_includes_recommendations():
    files = [r.file for r in validate_registry(_REGISTRY_PATH)]
    assert "recommendations.yaml" in files, (
        "validate_registry must check recommendations.yaml, so CI runs it"
    )


def test_validate_reports_a_missing_target(tmp_path):
    reg = _write_registry(
        tmp_path,
        "- id: a\n  recommend: playwright\n  type: tool\n  when_stack_has: [aws]\n"
        "  reason: r\n  examples: {match: [AWS], no_match: [GCP]}\n",
    )
    assert any("no tool named 'playwright'" in m for m in _messages(reg))


def test_validate_reports_examples_that_do_not_hold(tmp_path):
    reg = _write_registry(
        tmp_path,
        "- id: a\n  recommend: disaster-recovery-plan\n  type: skill\n"
        "  when_stack_has: [aws, lambda]\n  reason: r\n"
        "  examples: {match: [Azure], no_match: [Java lambda expressions]}\n",
    )
    messages = _messages(reg)
    assert any("'Azure' must trigger" in m for m in messages), messages
    assert any("'Java lambda expressions' must not trigger" in m for m in messages), (
        "A trigger word with a second meaning must fail through its no_match example"
    )


def test_validate_runs_a_stack_example(tmp_path):
    reg = _write_registry(
        tmp_path,
        "- id: a\n  recommend: disaster-recovery-plan\n  type: skill\n"
        "  when_stack_has: [aws]\n  unless_term_has: [azure devops]\n"
        "  reason: r\n"
        "  examples: {match: [AWS], no_match: [[Azure DevOps, AWS]]}\n",
    )
    messages = _messages(reg)
    assert any("'Azure DevOps, AWS' must not trigger" in m for m in messages), (
        f"A list example must run as one stack: {messages}"
    )


def test_validate_reports_an_unknown_requirement(tmp_path):
    reg = _write_registry(
        tmp_path,
        "- id: a\n  recommend: disaster-recovery-plan\n  type: skill\n"
        "  when_stack_has: [aws]\n  requires: playwright\n  reason: r\n"
        "  examples: {match: [AWS], no_match: [GCP]}\n",
    )
    assert any("no capability named 'playwright'" in m for m in _messages(reg))


def test_validate_reports_a_non_utf8_file(tmp_path):
    reg = _write_registry(tmp_path, "")
    (reg / "recommendations.yaml").write_bytes(b"- id: \xff\xfe\n")
    (result,) = validate_recommendations(reg)
    assert not result.valid
    assert any("UTF-8" in e.message for e in result.errors), result.errors


def test_validate_reports_uppercase_phrases_and_bad_shape(tmp_path):
    reg = _write_registry(
        tmp_path,
        "- id: a\n  recommend: disaster-recovery-plan\n  type: skill\n"
        "  when_stack_has: [AWS]\n  reason: r\n"
        "  examples: {match: [AWS], no_match: [GCP]}\n"
        "- id: b\n  recommend: disaster-recovery-plan\n  type: skill\n"
        "  reason: r\n  examples: {match: [AWS], no_match: [GCP]}\n",
    )
    messages = _messages(reg)
    assert any("'AWS' must be lowercase" in m for m in messages), messages
    assert any(m.startswith("b:") for m in messages), (
        f"An entry without when_stack_has must fail schema checks: {messages}"
    )


def test_validate_without_file_reports_nothing(tmp_path):
    assert validate_recommendations(tmp_path) == []


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


async def test_tools_are_listed(mcp_client):
    names = {t.name for t in await mcp_client.list_tools()}
    assert {"recommend_capabilities", "report_recommendation"} <= names, (
        f"Both recommendation tools must be registered, got: {sorted(names)}"
    )


@patch("awos_recruitment_mcp.tools.recommend.track_recommendations")
async def test_recommend_tool_for_a_cloud_stack(mock_track, mcp_client):
    result = await mcp_client.call_tool(
        "recommend_capabilities",
        {"stack": ["Python", "FastAPI", "AWS", "Terraform"]},
    )
    assert not result.is_error, _text(result)
    items = result.structured_content["result"]
    by_id = {i["id"]: i for i in items}
    assert "dr-for-cloud" in by_id, f"AWS must trigger dr-for-cloud, got {items}"
    assert by_id["dr-for-cloud"]["user_invoked"] is True
    assert by_id["dr-for-cloud"]["matched_term"] == "AWS"
    mock_track.assert_called_once()


async def test_recommend_tool_for_react_native_returns_no_web_ui_items(mcp_client):
    result = await mcp_client.call_tool(
        "recommend_capabilities", {"stack": ["React Native", "Kotlin"]}
    )
    items = result.structured_content["result"]
    assert not [i for i in items if i["name"] in {"verify-ui", "playwright"}], (
        f"React Native is not a web UI; got {items}"
    )


async def test_recommend_tool_for_a_mobile_stack_returns_no_web_items(mcp_client):
    result = await mcp_client.call_tool(
        "recommend_capabilities",
        {"stack": ["React Native", "React Navigation", "Tailwind CSS", "AWS"]},
    )
    names = [i["name"] for i in result.structured_content["result"]]
    assert not {"playwright", "verify-ui", "shadcn"} & set(names), (
        f"A React Native app is not a web frontend; got {names}"
    )
    assert "disaster-recovery-plan" in names, (
        f"The stack exclusion must not drop unrelated entries; got {names}"
    )


async def test_recommend_tool_for_azure_devops_alone_returns_no_dr(mcp_client):
    result = await mcp_client.call_tool(
        "recommend_capabilities", {"stack": ["Python", "Azure DevOps", "Azure AD"]}
    )
    names = [i["name"] for i in result.structured_content["result"]]
    assert "disaster-recovery-plan" not in names, (
        f"Azure DevOps and Azure AD do not mean the system runs in Azure; got {names}"
    )


async def test_recommend_tool_drops_verify_ui_when_playwright_was_declined(
    mcp_client,
):
    result = await mcp_client.call_tool(
        "recommend_capabilities", {"stack": ["React"], "declined": ["playwright"]}
    )
    names = [i["name"] for i in result.structured_content["result"]]
    assert not {"playwright", "verify-ui"} & set(names), (
        f"verify-ui needs playwright, which the user declined; got {names}"
    )


async def test_recommend_tool_leaves_review_skills_to_search(mcp_client):
    result = await mcp_client.call_tool(
        "recommend_capabilities", {"stack": ["GitHub", "GitHub Actions", "GitLab CI"]}
    )
    items = result.structured_content["result"]
    assert items == [], (
        "A search for GitHub or GitLab already returns the review skills near "
        f"the top, so no entry must trigger on them; got {items}"
    )


async def test_recommend_tool_honours_exclude(mcp_client):
    result = await mcp_client.call_tool(
        "recommend_capabilities",
        {
            "stack": ["React", "AWS"],
            "exclude": ["playwright", "disaster-recovery-plan"],
        },
    )
    names = [i["name"] for i in result.structured_content["result"]]
    assert not {"playwright", "disaster-recovery-plan"} & set(names), (
        f"Excluded names must be left out, got {names}"
    )
    assert "verify-ui" in names, (
        f"A name that is not excluded must stay in the result, got {names}"
    )


async def test_recommend_tool_rejects_an_empty_stack(mcp_client):
    result = await mcp_client.call_tool("recommend_capabilities", {"stack": [" "]})
    assert "Error: stack must be a non-empty list" in _text(result)


@patch("awos_recruitment_mcp.tools.recommend.track_recommendation_outcome")
async def test_report_recommendation_forwards_to_telemetry(mock_track, mcp_client):
    result = await mcp_client.call_tool(
        "report_recommendation", {"id": "dr-for-cloud", "outcome": "declined"}
    )
    assert "Outcome recorded for 'dr-for-cloud' (declined)" in _text(result)
    mock_track.assert_called_once_with(
        "dr-for-cloud", "disaster-recovery-plan", "skill", "declined"
    )


@patch("awos_recruitment_mcp.tools.recommend.track_recommendation_outcome")
async def test_report_recommendation_rejects_an_unknown_id(mock_track, mcp_client):
    result = await mcp_client.call_tool(
        "report_recommendation", {"id": "no-such-entry", "outcome": "installed"}
    )
    assert "unknown recommendation id" in _text(result)
    mock_track.assert_not_called()


async def test_malformed_file_disables_recommendations_not_search(
    tmp_path, monkeypatch
):
    """A broken recommendations.yaml must not take search down with it."""
    reg = _write_registry(tmp_path, "not: a list\n")
    monkeypatch.setattr(
        server_module,
        "config",
        dataclasses.replace(server_module.config, registry_path=str(reg)),
    )
    async with Client(server_module.mcp) as client:
        rec = await client.call_tool("recommend_capabilities", {"stack": ["AWS"]})
        assert rec.structured_content["result"] == []
        found = await client.call_tool(
            "search_capabilities", {"query": "disaster recovery plan"}
        )
        assert not found.is_error, "Search must keep working"
