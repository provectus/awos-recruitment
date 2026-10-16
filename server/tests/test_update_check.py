"""Tests for the update check: check_skills, POST /check and the server instructions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastmcp import Client

import awos_recruitment_mcp.server as server_module
from awos_recruitment_mcp.registry_index import hash_skill
from awos_recruitment_mcp.update_check import check_skills

PROJECT_ID = "b4252689-6fa4-4675-b630-ecb331160d84"


def _write_skill(root: Path, name: str, body: str) -> dict:
    skill = root / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n---\n{body}\n")
    return hash_skill(skill)


@pytest.fixture
def registry(tmp_path):
    """Two skills (``fresh`` and ``stale``) and one tombstone (``old``)."""
    _write_skill(tmp_path, "fresh", "v1")
    _write_skill(tmp_path, "stale", "v2")
    (tmp_path / "removed.yaml").write_text(
        "skills:\n  old:\n    removed: 2026-09-01\n    replacement: fresh\n"
    )
    return tmp_path


def _lock(registry: Path) -> dict:
    fresh = hash_skill(registry / "skills" / "fresh")["hash"]
    return {
        "version": 1,
        "project_id": PROJECT_ID,
        "skills": {
            "fresh": {"server": "s", "installed_at": "t", "hash": fresh, "files": {}},
            "stale": {"server": "s", "installed_at": "t", "hash": "0" * 64, "files": {}},
            "old": {"server": "s", "installed_at": "t", "hash": "1" * 64, "files": {}},
            "mine": {"server": "s", "installed_at": "t", "hash": "2" * 64, "files": {}},
        },
    }


# ---------------------------------------------------------------------------
# check_skills
# ---------------------------------------------------------------------------


def test_check_skills_classifies_every_case():
    index = {
        "skills": {"fresh": {"hash": "a"}, "stale": {"hash": "b"}},
        "removed": {"skills": {"old": {"replacement": "fresh"}}},
    }

    result = check_skills({"fresh": "a", "stale": "x", "old": "y", "mine": "z"}, index)

    assert result.outdated == ["stale"]
    assert result.removed == [{"name": "old", "replacement": "fresh"}]
    assert result.unknown == ["mine"]
    assert result.up_to_date == 1
    assert result.summary == (
        "awos-recruitment: 1 skill outdated (stale); 1 removed from registry (old -> fresh). "
        "Run `npx @provectusinc/awos-recruitment skill update`."
    )


def test_summary_is_empty_when_everything_is_current():
    result = check_skills({"fresh": "a"}, {"skills": {"fresh": {"hash": "a"}}, "removed": {}})
    assert result.summary == ""
    assert result.up_to_date == 1


# ---------------------------------------------------------------------------
# POST /check
# ---------------------------------------------------------------------------


@patch("awos_recruitment_mcp.update_check.track_client_event")
async def test_check_route_returns_json(mock_track, registry, client_factory):
    async with client_factory(registry) as client:
        response = await client.post("/check", json=_lock(registry))

    assert response.status_code == 200
    body = response.json()
    assert body["outdated"] == ["stale"]
    assert body["removed"] == [{"name": "old", "replacement": "fresh"}]
    assert body["unknown"] == ["mine"]
    assert body["up_to_date"] == 1
    assert body["summary"].startswith("awos-recruitment: 1 skill outdated (stale)")
    events = [c.args[1] for c in mock_track.call_args_list]
    assert events == ["capability_update_checked", "capability_removed_in_use"]
    assert mock_track.call_args_list[0].args[0] == PROJECT_ID
    assert mock_track.call_args_list[0].args[2]["source"] == "hook"


async def test_check_route_text_plain_returns_summary_only(registry, client_factory):
    async with client_factory(registry) as client:
        response = await client.post(
            "/check", json=_lock(registry), headers={"Accept": "text/plain"}
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("awos-recruitment: 1 skill outdated (stale)")


async def test_check_route_text_plain_is_empty_when_current(registry, client_factory):
    lock = _lock(registry)
    lock["skills"] = {"fresh": lock["skills"]["fresh"]}

    async with client_factory(registry) as client:
        response = await client.post("/check", json=lock, headers={"Accept": "text/plain"})

    assert response.status_code == 200
    assert response.text == ""


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"skills": {"Bad Name": {"hash": "0" * 64}}},
        {"skills": {"ok": {"hash": "not-a-hash"}}},
        {"project_id": "org/repo", "skills": {}},
    ],
)
async def test_check_route_rejects_bad_bodies(registry, client_factory, body):
    async with client_factory(registry) as client:
        response = await client.post("/check", json=body)

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Server instructions nudge connected sessions to check for updates
# ---------------------------------------------------------------------------


async def test_server_instructions_offer_the_update_check():
    async with Client(server_module.mcp) as client:
        info = client.server_info if hasattr(client, "server_info") else None
        instructions = (
            info.instructions if info is not None and hasattr(info, "instructions")
            else server_module.mcp.instructions
        )

    assert "skill status" in instructions
    assert "once per session" in instructions
    assert "do not run it without asking" in instructions
