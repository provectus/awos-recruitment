"""Skill version history from git — fingerprints for copies installed before the lock file.

``python -m awos_recruitment_mcp.history [repo_root]`` prints a JSON document:

.. code-block:: json

    {
      "version": 1,
      "generated_at": "2026-10-16T12:00:00+00:00",
      "skills": {
        "pytest-best-practices": [
          {"hash": "<capability hash>", "from": "2026-03-01", "to": "2026-05-07", "commit": "abc1234"},
          {"hash": "<capability hash>", "from": "2026-05-07", "to": null, "commit": "def5678"}
        ]
      }
    }

One entry per distinct content version of each skill, oldest first.  The
hash follows the same scheme as ``registry_index.hash_skill`` so a copy in
a user project can be matched to the exact version it came from.  The
deploy pipeline writes the output to ``registry/history.json`` before the
Docker build; the server serves it as ``GET /history.json``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from awos_recruitment_mcp.registry_index import combined_hash, is_bundled_skill_file

HISTORY_VERSION = 1
HISTORY_FILE = "history.json"

_SKILLS_PREFIX = "registry/skills/"


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _skill_commits(repo_root: Path) -> list[tuple[str, str, set[str]]]:
    """Return ``(commit, date, {skill names touched})`` oldest first."""
    out = _git(
        repo_root,
        "log",
        "--reverse",
        "--date=short",
        "--format=%x00%H %ad",
        "--name-only",
        "--",
        _SKILLS_PREFIX,
    )
    commits: list[tuple[str, str, set[str]]] = []
    for block in out.split("\x00"):
        block = block.strip()
        if not block:
            continue
        header, _, body = block.partition("\n")
        commit, _, date = header.partition(" ")
        touched: set[str] = set()
        for line in body.splitlines():
            if line.startswith(_SKILLS_PREFIX):
                rest = line[len(_SKILLS_PREFIX):]
                name = rest.split("/", 1)[0]
                if name:
                    touched.add(name)
        commits.append((commit, date, touched))
    return commits


def _skill_tree(repo_root: Path, commit: str, name: str) -> dict[str, str]:
    """``{relative path: blob id}`` for the bundled files of a skill at a commit."""
    try:
        out = _git(repo_root, "ls-tree", "-r", commit, "--", f"{_SKILLS_PREFIX}{name}/")
    except subprocess.CalledProcessError:
        return {}
    prefix = f"{_SKILLS_PREFIX}{name}/"
    tree: dict[str, str] = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != "blob":
            continue
        rel_path = path[len(prefix):]
        if is_bundled_skill_file(rel_path):
            tree[rel_path] = parts[2]
    return tree


class _BlobHasher:
    """sha256 of blob contents, one ``git cat-file`` call per distinct blob."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.cache: dict[str, str] = {}

    def __call__(self, blob: str) -> str:
        if blob not in self.cache:
            content = subprocess.run(
                ["git", "-C", str(self.repo_root), "cat-file", "blob", blob],
                check=True,
                capture_output=True,
            ).stdout
            self.cache[blob] = hashlib.sha256(content).hexdigest()
        return self.cache[blob]


def build_history(repo_root: str | Path) -> dict[str, Any]:
    """Walk the git history of ``registry/skills/`` and list every version of every skill.

    Args:
        repo_root: A checkout with full history (``fetch-depth: 0`` in CI).

    Returns:
        The document described in the module docstring.
    """
    root = Path(repo_root)
    hash_blob = _BlobHasher(root)

    versions: dict[str, list[dict[str, Any]]] = {}
    current: dict[str, str | None] = {}  # skill -> hash of its latest version

    for commit, date, touched in _skill_commits(root):
        for name in sorted(touched):
            tree = _skill_tree(root, commit, name)
            if "SKILL.md" not in tree:
                # Removed (or never had a SKILL.md): close the open version.
                if current.get(name) is not None:
                    versions[name][-1]["to"] = date
                    current[name] = None
                continue

            files = {rel: hash_blob(blob) for rel, blob in tree.items()}
            cap_hash = combined_hash(files)
            if current.get(name) == cap_hash:
                continue

            entries = versions.setdefault(name, [])
            if entries and entries[-1]["to"] is None:
                entries[-1]["to"] = date
            entries.append({"hash": cap_hash, "from": date, "to": None, "commit": commit[:7]})
            current[name] = cap_hash

    return {
        "version": HISTORY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skills": {name: versions[name] for name in sorted(versions)},
    }


def empty_history() -> dict[str, Any]:
    """What the server serves when no ``history.json`` was generated."""
    return {"version": HISTORY_VERSION, "generated_at": None, "skills": {}}


def main(argv: list[str]) -> int:
    repo_root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[3]
    json.dump(build_history(repo_root), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
