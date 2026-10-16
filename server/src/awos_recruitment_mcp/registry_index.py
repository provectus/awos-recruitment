"""Registry index — content hashes of every skill plus tombstones for removed capabilities.

The CLI records the hash of each installed file in the project's lock file.
``GET /index.json`` serves the same hashes computed from the registry on
disk, so a client can tell whether an installed copy is current, outdated,
modified locally, or removed from the registry.

The hashing scheme is shared with the CLI (``cli/src/lib/lock.ts``) and must
stay in lockstep:

* each file: hex sha256 of its bytes;
* a capability: hex sha256 over ``"<relative path>\\0<file sha256>\\n"`` for
  every file, sorted by relative path (POSIX separators).

Tombstones come from ``registry/removed.yaml``. When a capability is removed
or renamed, add an entry there so installed copies can learn about it.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from awos_recruitment_mcp.validate import _ALLOWED_SCRIPT_EXTENSIONS

INDEX_VERSION = 1

REMOVED_FILE = "removed.yaml"

CAPABILITY_TYPES: tuple[str, ...] = ("skills", "agents", "hooks", "mcp")

# Subdirectories of a skill that the bundle ships. ``evals/`` stays out: it
# holds the author's test cases, not anything the installed skill reads.
_SKILL_SUBDIRS: tuple[str, ...] = ("references", "scripts", "assets")


class RemovedFileError(ValueError):
    """``removed.yaml`` is present but malformed."""


def iter_skill_files(skill_dir: Path) -> list[tuple[str, Path]]:
    """Return ``(relative_path, absolute_path)`` for every file a skill bundle ships.

    The selection is the single source of truth for both the tar archive
    served by ``POST /bundle/skills`` and the hashes in ``GET /index.json``,
    so an installed copy hashes to the same value as the registry.

    Args:
        skill_dir: The ``registry/skills/<name>/`` directory.

    Returns:
        Pairs sorted by relative path. Relative paths use ``/`` separators.
    """
    files: list[tuple[str, Path]] = []

    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        files.append(("SKILL.md", skill_md))

    for subdir_name in _SKILL_SUBDIRS:
        subdir = skill_dir / subdir_name
        if not subdir.is_dir():
            continue
        for sub_file in sorted(subdir.iterdir()):
            if not sub_file.is_file() or sub_file.name.startswith("."):
                continue
            if (
                subdir_name == "scripts"
                and sub_file.suffix not in _ALLOWED_SCRIPT_EXTENSIONS
            ):
                continue
            files.append((f"{subdir_name}/{sub_file.name}", sub_file))

    files.sort(key=lambda pair: pair[0])
    return files


def hash_file(path: Path) -> str:
    """Return the hex sha256 of a file's bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def combined_hash(files: dict[str, str]) -> str:
    """Fold per-file hashes into one capability hash.

    Args:
        files: Mapping of relative path to hex sha256.

    Returns:
        Hex sha256 over ``"<path>\\0<hash>\\n"`` lines, sorted by path.
    """
    digest = hashlib.sha256()
    for rel_path in sorted(files):
        digest.update(f"{rel_path}\0{files[rel_path]}\n".encode("utf-8"))
    return digest.hexdigest()


def hash_skill(skill_dir: Path) -> dict[str, Any]:
    """Return ``{"hash": <combined>, "files": {<relative path>: <sha256>}}`` for a skill."""
    files = {rel_path: hash_file(abs_path) for rel_path, abs_path in iter_skill_files(skill_dir)}
    return {"hash": combined_hash(files), "files": files}


def _as_date_string(value: Any, context: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    raise RemovedFileError(f"{context}: 'removed' must be a date (YYYY-MM-DD)")


def load_removed(registry_path: str | Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Load tombstones from ``<registry>/removed.yaml``.

    The file maps a capability type (``skills``, ``agents``, ``hooks``,
    ``mcp``) to names, each with ``removed`` (date, required), ``reason``
    (string, optional) and ``replacement`` (name or null, optional).

    Args:
        registry_path: Root directory of the registry.

    Returns:
        ``{type: {name: {"removed": str, "reason": str | None, "replacement": str | None}}}``
        with every capability type present, empty when the file is absent.

    Raises:
        RemovedFileError: The file exists but does not match the shape above.
    """
    result: dict[str, dict[str, dict[str, Any]]] = {t: {} for t in CAPABILITY_TYPES}

    removed_file = Path(registry_path) / REMOVED_FILE
    if not removed_file.is_file():
        return result

    with open(removed_file, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise RemovedFileError(f"{REMOVED_FILE}: top level must be a mapping")

    for cap_type, entries in data.items():
        if cap_type not in CAPABILITY_TYPES:
            raise RemovedFileError(
                f"{REMOVED_FILE}: unknown capability type '{cap_type}' "
                f"(expected one of {', '.join(CAPABILITY_TYPES)})"
            )
        if entries is None:
            continue
        if not isinstance(entries, dict):
            raise RemovedFileError(f"{REMOVED_FILE}: '{cap_type}' must be a mapping of names")

        for name, fields in entries.items():
            context = f"{REMOVED_FILE}: {cap_type}/{name}"
            if not isinstance(fields, dict) or "removed" not in fields:
                raise RemovedFileError(f"{context}: needs a 'removed' date")
            unknown = set(fields) - {"removed", "reason", "replacement"}
            if unknown:
                raise RemovedFileError(
                    f"{context}: unknown field(s) {', '.join(sorted(unknown))}"
                )
            reason = fields.get("reason")
            replacement = fields.get("replacement")
            if reason is not None and not isinstance(reason, str):
                raise RemovedFileError(f"{context}: 'reason' must be a string")
            if replacement is not None and not isinstance(replacement, str):
                raise RemovedFileError(f"{context}: 'replacement' must be a name or null")

            result[cap_type][str(name)] = {
                "removed": _as_date_string(fields["removed"], context),
                "reason": reason,
                "replacement": replacement,
            }

    return result


def build_registry_index(registry_path: str | Path) -> dict[str, Any]:
    """Build the document served at ``GET /index.json``.

    Args:
        registry_path: Root directory of the registry.

    Returns:
        ``{"version", "generated_at", "skills": {name: {"hash", "files"}}, "removed": {...}}``.
        Only skills carry hashes for now; agents, hooks and MCP definitions
        appear in ``removed`` only.
    """
    root = Path(registry_path)
    skills_dir = root / "skills"

    skills: dict[str, Any] = {}
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
                continue
            skills[skill_dir.name] = hash_skill(skill_dir)

    return {
        "version": INDEX_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skills": skills,
        "removed": load_removed(root),
    }
