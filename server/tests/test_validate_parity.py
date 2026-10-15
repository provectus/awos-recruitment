"""Tests for the repo-local vs registry skill parity check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from awos_recruitment_mcp.validate.parity import (
    SKILL_PAIRS,
    check_pairs,
    compare_pair,
    normalize_skill_md,
)

_REGISTRY_SKILL_MD = (
    "---\nname: registry-name\ndescription: Does a thing.\nversion: 0.1.0\n---\n\n"
    "# Title\n\nBody.\n"
)
_LOCAL_SKILL_MD = (
    "---\nname: Local Alias\ndescription: Does a thing.\nversion: 0.1.0\n---\n\n"
    "<!-- Generated from registry/skills/registry-name. Do not edit here:\n"
    "     change the registry skill and re-copy. -->\n\n"
    "# Title\n\nBody.\n"
)


def _pair(tmp_path: Path, local_md: str = _LOCAL_SKILL_MD) -> tuple[Path, Path]:
    local = tmp_path / ".claude" / "skills" / "alias"
    registry = tmp_path / "registry" / "skills" / "registry-name"
    for root, md in ((local, local_md), (registry, _REGISTRY_SKILL_MD)):
        (root / "references").mkdir(parents=True)
        (root / "SKILL.md").write_text(md, encoding="utf-8")
        (root / "references" / "a.md").write_text("# A\n", encoding="utf-8")
    return local, registry


# ---------------------------------------------------------------------------
# normalize_skill_md
# ---------------------------------------------------------------------------


def test_normalize_drops_name_line_and_body_comment():
    assert normalize_skill_md(_LOCAL_SKILL_MD) == normalize_skill_md(_REGISTRY_SKILL_MD)


def test_normalize_drops_comment_above_front_matter():
    above = "<!-- provenance -->\n" + _REGISTRY_SKILL_MD
    assert normalize_skill_md(above) == normalize_skill_md(_REGISTRY_SKILL_MD)


def test_normalize_keeps_other_front_matter_differences():
    changed = _REGISTRY_SKILL_MD.replace("version: 0.1.0", "version: 0.2.0")
    assert normalize_skill_md(changed) != normalize_skill_md(_REGISTRY_SKILL_MD)


def test_normalize_only_strips_one_leading_comment():
    body_comment_twice = _REGISTRY_SKILL_MD.replace(
        "# Title", "<!-- one -->\n\n<!-- two -->\n\n# Title"
    )
    assert normalize_skill_md(body_comment_twice) != normalize_skill_md(_REGISTRY_SKILL_MD)


# ---------------------------------------------------------------------------
# compare_pair
# ---------------------------------------------------------------------------


def test_in_sync_pair_has_no_problems(tmp_path: Path):
    local, registry = _pair(tmp_path)
    assert compare_pair(local, registry) == []


def test_readme_and_evals_are_ignored(tmp_path: Path):
    local, registry = _pair(tmp_path)
    (local / "README.md").write_text("# Local docs\n")
    (registry / "evals").mkdir()
    (registry / "evals" / "evals.json").write_text("{}\n")
    assert compare_pair(local, registry) == []


def test_body_drift_is_reported(tmp_path: Path):
    local, registry = _pair(tmp_path, _LOCAL_SKILL_MD.replace("Body.", "Different body."))
    problems = compare_pair(local, registry)
    assert problems and problems[0].startswith("SKILL.md differs"), problems


def test_reference_drift_is_reported(tmp_path: Path):
    local, registry = _pair(tmp_path)
    (local / "references" / "a.md").write_text("# A changed\n")
    problems = compare_pair(local, registry)
    assert any(p == "differs: references/a.md" for p in problems), problems


def test_missing_reference_is_reported(tmp_path: Path):
    local, registry = _pair(tmp_path)
    (registry / "references" / "b.md").write_text("# B\n")
    problems = compare_pair(local, registry)
    assert problems == ["only in registry: references/b.md"], problems


def test_missing_directory_is_reported(tmp_path: Path):
    local, registry = _pair(tmp_path)
    problems = compare_pair(local, tmp_path / "nowhere")
    assert problems == [f"registry copy '{tmp_path / 'nowhere'}' is not a directory"]


def test_check_pairs_labels_each_pair(tmp_path: Path):
    _pair(tmp_path)
    pairs = ((".claude/skills/alias", "registry/skills/registry-name"),)
    assert check_pairs(tmp_path, pairs) == {
        ".claude/skills/alias <-> registry/skills/registry-name": []
    }


def test_shipped_pairs_point_at_existing_registry_skills():
    """Every registry side of a shipped pair must exist; the local side is allowed to lag."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    for _local, registry in SKILL_PAIRS:
        assert (repo_root / registry / "SKILL.md").is_file(), registry


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "awos_recruitment_mcp.validate.parity", *args],
        capture_output=True,
        text=True,
    )


def test_cli_exit_code_follows_sync_state(tmp_path: Path, monkeypatch):
    # The CLI uses the shipped SKILL_PAIRS, so stage every pair under tmp_path.
    for local, registry in SKILL_PAIRS:
        for rel, md in ((local, _LOCAL_SKILL_MD), (registry, _REGISTRY_SKILL_MD)):
            (tmp_path / rel).mkdir(parents=True)
            (tmp_path / rel / "SKILL.md").write_text(md, encoding="utf-8")

    ok = _cli("--repo-root", str(tmp_path))
    assert ok.returncode == 0, ok.stdout
    assert f"All {len(SKILL_PAIRS)} skill pairs in sync." in ok.stdout

    first_local = tmp_path / SKILL_PAIRS[0][0] / "SKILL.md"
    first_local.write_text(_LOCAL_SKILL_MD.replace("Body.", "Drifted."), encoding="utf-8")
    failing = _cli("--repo-root", str(tmp_path))
    assert failing.returncode == 1, failing.stdout
    assert "FAIL  " + SKILL_PAIRS[0][0] in failing.stdout
    assert "out of sync" in failing.stdout
