"""Tests for the check_skill_updates MCP tool and the file-based check behind it."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastmcp import Client

import awos_recruitment_mcp.server as server_module
import awos_recruitment_mcp.tools.update_check as tool_module
from awos_recruitment_mcp.registry_index import combined_hash, hash_skill
from awos_recruitment_mcp.update_check import check_files, parse_shasum_output

PROJECT_ID = "b4252689-6fa4-4675-b630-ecb331160d84"


def sha(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def test_parse_shasum_output_groups_by_skill_and_ignores_noise():
    text = "\n".join(
        [
            f"{sha('a')}  /home/u/proj/.claude/skills/one/SKILL.md",
            f"{sha('b')}  .claude/skills/one/references/x.md",
            f"{sha('c')} *.claude\\skills\\two\\SKILL.md",
            f"{sha('d')}  /home/u/proj/README.md",
            "garbage line",
            "",
        ]
    )

    parsed = parse_shasum_output(text)

    assert parsed == {
        "one": {"SKILL.md": sha("a"), "references/x.md": sha("b")},
        "two": {"SKILL.md": sha("c")},
    }


def test_check_files_classifies_every_state():
    index = {
        "skills": {"fresh": {"hash": combined_hash({"SKILL.md": sha("v2")})}, "stale": {"hash": "zz"}},
        "removed": {"skills": {"old": {"removed": "2026-09-01", "replacement": "fresh"}}},
    }
    stale_v1 = combined_hash({"SKILL.md": sha("v1")})
    history = {"skills": {"stale": [{"hash": stale_v1, "from": "2026-03-11"}, {"hash": "zz", "from": "2026-10-01"}]}}
    skills = {
        "fresh": {"SKILL.md": sha("v2")},
        "stale": {"SKILL.md": sha("v1")},
        "edited": {"SKILL.md": sha("mine")},
        "old": {"SKILL.md": sha("x")},
        "mine": {"SKILL.md": sha("y")},
    }
    index["skills"]["edited"] = {"hash": "ee"}

    results = {r["name"]: r for r in check_files(skills, index, history)}

    assert results["fresh"]["state"] == "up-to-date"
    assert results["stale"]["state"] == "outdated"
    assert results["stale"]["detail"] == "version from 2026-03-11, 1 version behind"
    assert results["edited"]["state"] == "modified-or-unknown"
    assert results["old"]["state"] == "removed"
    assert results["old"]["replacement"] == "fresh"
    assert results["mine"]["state"] == "not-in-registry"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A registry with skill ``s`` at v2, a history that knows v1, pointed at by the tool."""
    skill = tmp_path / "skills" / "s"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("v2\n")
    v1_hash = combined_hash({"SKILL.md": sha("v1\n")})
    (tmp_path / "history.json").write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "x",
                "skills": {
                    "s": [
                        {"hash": v1_hash, "from": "2026-03-11", "to": "2026-10-01", "commit": "a"},
                        {"hash": hash_skill(skill)["hash"], "from": "2026-10-01", "to": None, "commit": "b"},
                    ]
                },
            }
        )
    )
    patched = dataclasses.replace(server_module.config, registry_path=str(tmp_path))
    monkeypatch.setattr(server_module, "config", patched)
    monkeypatch.setattr(tool_module, "config", patched)
    return tmp_path


@patch("awos_recruitment_mcp.update_check.track_client_event")
async def test_tool_recognizes_an_old_copy_without_a_lock_file(mock_track, registry):
    file_hashes = f"{sha('v1' + chr(10))}  /proj/.claude/skills/s/SKILL.md\n"

    async with Client(server_module.mcp) as client:
        assert "check_skill_updates" in {t.name for t in await client.list_tools()}
        result = await client.call_tool(
            "check_skill_updates", {"file_hashes": file_hashes, "project_id": PROJECT_ID}
        )

    data = result.data if getattr(result, "data", None) else json.loads(result.content[0].text)
    assert data["skills"][0]["state"] == "outdated"
    assert data["skills"][0]["detail"] == "version from 2026-03-11, 1 version behind"
    assert data["summary"].startswith("awos-recruitment: 1 skill outdated (s)")
    assert data["command"] == "npx @provectusinc/awos-recruitment skill update"
    assert mock_track.call_args_list[0].args[2]["source"] == "mcp"


async def test_tool_is_quiet_when_everything_is_current(registry):
    file_hashes = f"{sha('v2' + chr(10))}  .claude/skills/s/SKILL.md\n"

    async with Client(server_module.mcp) as client:
        result = await client.call_tool("check_skill_updates", {"file_hashes": file_hashes})

    data = result.data if getattr(result, "data", None) else json.loads(result.content[0].text)
    assert data["summary"] == ""
    assert data["skills"][0]["state"] == "up-to-date"


async def test_tool_explains_empty_input(registry):
    async with Client(server_module.mcp) as client:
        result = await client.call_tool("check_skill_updates", {"file_hashes": "nothing useful"})

    data = result.data if getattr(result, "data", None) else json.loads(result.content[0].text)
    assert data["skills"] == []
    assert "No `.claude/skills/" in data["note"]


@patch("awos_recruitment_mcp.update_check.track_client_event")
async def test_tool_stays_quiet_about_a_skipped_version(mock_track, registry):
    """The lock file says the user skipped the current registry version: no summary."""
    file_hashes = f"{sha('v1' + chr(10))}  .claude/skills/s/SKILL.md\n"
    current = hash_skill(registry / "skills" / "s")["hash"]
    lock = json.dumps(
        {
            "version": 1,
            "project_id": PROJECT_ID,
            "skills": {"s": {"hash": "1" * 64, "files": {}, "skip": {"hash": current, "at": "2026-10-20T00:00:00Z"}}},
        }
    )

    async with Client(server_module.mcp) as client:
        result = await client.call_tool("check_skill_updates", {"file_hashes": file_hashes, "lock": lock})

    data = result.data if getattr(result, "data", None) else json.loads(result.content[0].text)
    assert data["summary"] == ""
    assert data["skills"][0]["state"] == "skipped"
    # project_id is read from the lock text when not passed separately.
    assert mock_track.call_args_list[0].args[0] == PROJECT_ID


def test_skips_from_lock_ignores_garbage():
    from awos_recruitment_mcp.update_check import skips_from_lock

    assert skips_from_lock(None) == ({}, None)
    assert skips_from_lock("{not json") == ({}, None)
    assert skips_from_lock('{"skills": {"a": {"skip": "nope"}}}') == ({}, None)


@patch("awos_recruitment_mcp.update_check.track_client_event")
async def test_tool_is_quiet_about_a_merged_copy_with_edits(mock_track, registry):
    """Lock base = current registry version, files differ (the user's edits): no summary."""
    file_hashes = f"{sha('v2 plus my note' + chr(10))}  .claude/skills/s/SKILL.md\n"
    current = hash_skill(registry / "skills" / "s")["hash"]
    lock = json.dumps({"version": 1, "project_id": PROJECT_ID, "skills": {"s": {"hash": current, "files": {}}}})

    async with Client(server_module.mcp) as client:
        result = await client.call_tool("check_skill_updates", {"file_hashes": file_hashes, "lock": lock})

    data = result.data if getattr(result, "data", None) else json.loads(result.content[0].text)
    assert data["summary"] == ""
    assert data["skills"][0]["state"] == "current-with-edits"


async def test_tool_reports_edits_without_a_lock_as_modified(registry):
    file_hashes = f"{sha('v2 plus my note' + chr(10))}  .claude/skills/s/SKILL.md\n"

    async with Client(server_module.mcp) as client:
        result = await client.call_tool("check_skill_updates", {"file_hashes": file_hashes})

    data = result.data if getattr(result, "data", None) else json.loads(result.content[0].text)
    assert data["skills"][0]["state"] == "modified-or-unknown"


def test_parse_lock_reads_bases_and_skips():
    from awos_recruitment_mcp.update_check import parse_lock

    skips, bases, pid = parse_lock(
        json.dumps({"project_id": PROJECT_ID, "skills": {"a": {"hash": "h", "skip": {"hash": "k"}}, "b": "junk"}})
    )
    assert skips == {"a": "k"}
    assert bases == {"a": "h"}
    assert pid == PROJECT_ID
