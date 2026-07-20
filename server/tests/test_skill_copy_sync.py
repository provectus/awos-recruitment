"""Byte-equality guard for the dogfooded docs-that-work skill copy.

`.claude/skills/docs-that-work/` exists so this repo's own Claude sessions
can invoke the skill; `registry/skills/docs-that-work/` is the shippable
source of truth. Edit the registry copy and re-sync (cp -R) — this test
keeps CI red on drift in either direction.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_SKILL = REPO_ROOT / "registry" / "skills" / "docs-that-work"
DOGFOOD_SKILL = REPO_ROOT / ".claude" / "skills" / "docs-that-work"


def _relative_files(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_dogfood_copy_matches_registry_source() -> None:
    assert REGISTRY_SKILL.is_dir() and DOGFOOD_SKILL.is_dir()

    registry_files = _relative_files(REGISTRY_SKILL)
    dogfood_files = _relative_files(DOGFOOD_SKILL)

    assert registry_files.keys() == dogfood_files.keys(), (
        "File sets differ between registry and .claude copies"
    )
    for name, content in registry_files.items():
        assert dogfood_files[name] == content, f"Drift in {name}"
