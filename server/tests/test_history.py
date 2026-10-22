"""Tests for the skill version history (git walk) and GET /history.json."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from awos_recruitment_mcp.history import build_history
from awos_recruitment_mcp.registry_index import hash_skill


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo: Path, message: str, date: str) -> None:
    _git(repo, "add", "-A")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", message],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "GIT_AUTHOR_DATE": f"{date}T12:00:00",
            "GIT_COMMITTER_DATE": f"{date}T12:00:00",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )


@pytest.fixture
def repo(tmp_path):
    """A repo where skill ``s`` goes through three versions and ``gone`` is removed."""
    _git(tmp_path, "init", "-q")
    skill = tmp_path / "registry" / "skills" / "s"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("v1\n")
    gone = tmp_path / "registry" / "skills" / "gone"
    gone.mkdir()
    (gone / "SKILL.md").write_text("g\n")
    _commit(tmp_path, "add s and gone", "2026-01-01")

    (skill / "references").mkdir()
    (skill / "references" / "a.md").write_text("a\n")
    _commit(tmp_path, "s: add reference", "2026-02-01")

    (skill / "evals").mkdir()
    (skill / "evals" / "case.md").write_text("not bundled\n")
    _commit(tmp_path, "s: add evals (no content change)", "2026-02-15")

    (gone / "SKILL.md").unlink()
    gone.rmdir()
    _commit(tmp_path, "remove gone", "2026-03-01")

    (skill / "SKILL.md").write_text("v3\n")
    _commit(tmp_path, "s: v3", "2026-04-01")
    return tmp_path


def test_build_history_lists_each_content_version_once(repo):
    history = build_history(repo)

    s = history["skills"]["s"]
    assert [v["from"] for v in s] == ["2026-01-01", "2026-02-01", "2026-04-01"]
    assert [v["to"] for v in s] == ["2026-02-01", "2026-04-01", None]
    assert len({v["hash"] for v in s}) == 3
    # The current checkout hashes to the latest version.
    assert s[-1]["hash"] == hash_skill(repo / "registry" / "skills" / "s")["hash"]


def test_build_history_closes_removed_skills(repo):
    history = build_history(repo)

    gone = history["skills"]["gone"]
    assert len(gone) == 1
    assert gone[0]["from"] == "2026-01-01"
    assert gone[0]["to"] == "2026-03-01"


def test_build_history_ignores_files_outside_the_bundle(repo):
    """The evals/ commit changed no bundled file, so it opened no version."""
    history = build_history(repo)
    assert all(v["from"] != "2026-02-15" for v in history["skills"]["s"])


async def test_history_route_serves_file_or_empty(tmp_path, client_factory):
    (tmp_path / "skills").mkdir()

    async with client_factory(tmp_path) as client:
        empty = await client.get("/history.json")
    assert empty.status_code == 200
    assert empty.json() == {"version": 1, "generated_at": None, "skills": {}}

    (tmp_path / "history.json").write_text(
        json.dumps({"version": 1, "generated_at": "x", "skills": {"s": []}})
    )
    async with client_factory(tmp_path) as client:
        served = await client.get("/history.json")
    assert served.json()["skills"] == {"s": []}
