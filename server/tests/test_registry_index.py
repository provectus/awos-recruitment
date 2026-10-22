"""Tests for the registry index (GET /index.json) and registry/removed.yaml."""

from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from awos_recruitment_mcp.registry_index import (
    RemovedFileError,
    build_registry_index,
    combined_hash,
    hash_skill,
    iter_skill_files,
    load_removed,
)

REGISTRY = Path(__file__).resolve().parents[2] / "registry"


def _write_skill(root: Path, name: str, extra: dict[str, str] | None = None) -> Path:
    skill = root / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: d\n---\nbody\n")
    for rel, content in (extra or {}).items():
        target = skill / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return skill


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def test_iter_skill_files_matches_bundle_rules(tmp_path):
    """SKILL.md, references/, assets/ and allowed scripts ship; evals/, dotfiles and other scripts do not."""
    skill = _write_skill(
        tmp_path,
        "s",
        {
            "references/a.md": "a",
            "assets/t.html": "<html>",
            "scripts/run.py": "print()",
            "scripts/notes.txt": "no",
            "scripts/.hidden.sh": "no",
            "evals/case.json": "{}",
            "README.md": "no",
        },
    )

    rel_paths = [rel for rel, _ in iter_skill_files(skill)]

    assert rel_paths == [
        "SKILL.md",
        "assets/t.html",
        "references/a.md",
        "scripts/run.py",
    ]


def test_hash_skill_uses_sha256_per_file_and_sorted_fold(tmp_path):
    skill = _write_skill(tmp_path, "s", {"references/a.md": "alpha"})

    result = hash_skill(skill)

    skill_md = hashlib.sha256((skill / "SKILL.md").read_bytes()).hexdigest()
    ref = hashlib.sha256(b"alpha").hexdigest()
    assert result["files"] == {"SKILL.md": skill_md, "references/a.md": ref}
    expected = hashlib.sha256(
        f"SKILL.md\0{skill_md}\nreferences/a.md\0{ref}\n".encode()
    ).hexdigest()
    assert result["hash"] == expected


def test_bundle_and_index_hash_the_same_files(tmp_path):
    """What the tar archive ships is exactly what the index hashes."""
    skill = _write_skill(
        tmp_path, "s", {"references/a.md": "a", "scripts/x.sh": "x", "evals/e.md": "e"}
    )
    index_paths = {rel for rel, _ in iter_skill_files(skill)}

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel, abs_path in iter_skill_files(skill):
            tar.add(str(abs_path), arcname=f"s/{rel}")
    buf.seek(0)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        tar_paths = {n.removeprefix("s/") for n in tar.getnames()}

    assert tar_paths == index_paths
    assert "evals/e.md" not in tar_paths


# ---------------------------------------------------------------------------
# removed.yaml
# ---------------------------------------------------------------------------


def test_load_removed_absent_file_gives_empty_types(tmp_path):
    assert load_removed(tmp_path) == {"skills": {}, "agents": {}, "hooks": {}, "mcp": {}}


def test_load_removed_parses_entries(tmp_path):
    (tmp_path / "removed.yaml").write_text(
        "skills:\n"
        "  old:\n"
        "    removed: 2026-09-01\n"
        "    reason: gone\n"
        "    replacement: new\n"
        "mcp:\n"
        "  x:\n"
        "    removed: 2026-01-02\n"
    )

    removed = load_removed(tmp_path)

    assert removed["skills"]["old"] == {
        "removed": "2026-09-01",
        "reason": "gone",
        "replacement": "new",
    }
    assert removed["mcp"]["x"] == {"removed": "2026-01-02", "reason": None, "replacement": None}
    assert removed["agents"] == {}


@pytest.mark.parametrize(
    "content, fragment",
    [
        ("tools:\n  x:\n    removed: 2026-01-01\n", "unknown capability type"),
        ("skills:\n  x:\n    removed: soon\n", "must be a date"),
    ],
)
def test_load_removed_rejects_malformed(tmp_path, content, fragment):
    (tmp_path / "removed.yaml").write_text(content)
    with pytest.raises(RemovedFileError, match=fragment):
        load_removed(tmp_path)


# ---------------------------------------------------------------------------
# Real registry
# ---------------------------------------------------------------------------


def test_real_registry_index_covers_every_skill():
    index = build_registry_index(REGISTRY)

    on_disk = sorted(p.name for p in (REGISTRY / "skills").iterdir() if (p / "SKILL.md").is_file())
    assert sorted(index["skills"]) == on_disk
    assert index["version"] == 1
    for entry in index["skills"].values():
        assert "SKILL.md" in entry["files"]
        assert len(entry["hash"]) == 64


def test_real_removed_entries_do_not_exist_in_registry():
    """A tombstone for a capability that still exists would mislead the CLI."""
    removed = load_removed(REGISTRY)
    assert any(removed.values()), "expected at least one tombstone in registry/removed.yaml"

    locations = {
        "skills": lambda n: (REGISTRY / "skills" / n).is_dir(),
        "agents": lambda n: (REGISTRY / "agents" / f"{n}.md").is_file(),
        "hooks": lambda n: (REGISTRY / "hooks" / n).is_dir(),
        "mcp": lambda n: (REGISTRY / "mcp" / f"{n}.yaml").is_file(),
    }
    for cap_type, entries in removed.items():
        for name, fields in entries.items():
            assert not locations[cap_type](name), f"{cap_type}/{name} is tombstoned but still exists"
            replacement = fields["replacement"]
            if replacement is not None:
                assert locations[cap_type](replacement), (
                    f"{cap_type}/{name}: replacement '{replacement}' does not exist"
                )


# ---------------------------------------------------------------------------
# HTTP route
# ---------------------------------------------------------------------------


async def test_index_route_serves_hashes_and_tombstones(tmp_path, client_factory):
    _write_skill(tmp_path, "s", {"references/a.md": "a"})
    (tmp_path / "removed.yaml").write_text("skills:\n  old:\n    removed: 2026-09-01\n")

    async with client_factory(tmp_path) as client:
        response = await client.get("/index.json")

    assert response.status_code == 200
    body = response.json()
    assert body["skills"]["s"] == hash_skill(tmp_path / "skills" / "s")
    assert body["removed"]["skills"]["old"]["removed"] == "2026-09-01"
    assert body["generated_at"]


async def test_index_route_reports_malformed_removed_file(tmp_path, client_factory):
    (tmp_path / "skills").mkdir()
    (tmp_path / "removed.yaml").write_text("- not a mapping\n")

    async with client_factory(tmp_path) as client:
        response = await client.get("/index.json")

    assert response.status_code == 500
    assert "removed.yaml" in response.json()["error"]


async def test_index_route_hash_matches_bundle_content(tmp_path, client_factory):
    """Hash the files a client extracts from /bundle/skills: it must equal the index hash."""
    _write_skill(tmp_path, "s", {"references/a.md": "a", "evals/e.md": "e"})

    async with client_factory(tmp_path) as client:
        index = (await client.get("/index.json")).json()
        bundle = await client.post("/bundle/skills", json={"names": ["s"]})

    files: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(bundle.content), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                data = tar.extractfile(member).read()
                files[member.name.removeprefix("s/")] = hashlib.sha256(data).hexdigest()

    assert files == index["skills"]["s"]["files"]
    assert combined_hash(files) == index["skills"]["s"]["hash"]


def test_index_carries_commit_and_date_of_the_current_version(tmp_path):
    """history.json names the commit of each version; the index copies it for the current one."""
    _write_skill(tmp_path, "s", {})
    current = hash_skill(tmp_path / "skills" / "s")["hash"]
    (tmp_path / "history.json").write_text(
        '{"version": 1, "skills": {"s": ['
        '{"hash": "' + "0" * 64 + '", "from": "2026-03-01", "to": "2026-09-24", "commit": "aaaaaaa"},'
        '{"hash": "' + current + '", "from": "2026-09-24", "to": null, "commit": "bbbbbbb"}]}}'
    )

    entry = build_registry_index(tmp_path)["skills"]["s"]

    assert entry["commit"] == "bbbbbbb"
    assert entry["released"] == "2026-09-24"


def test_index_omits_commit_when_history_does_not_know_the_current_version(tmp_path):
    _write_skill(tmp_path, "s", {})
    (tmp_path / "history.json").write_text('{"version": 1, "skills": {"s": [{"hash": "x", "from": "d", "commit": "c"}]}}')

    entry = build_registry_index(tmp_path)["skills"]["s"]

    assert "commit" not in entry
