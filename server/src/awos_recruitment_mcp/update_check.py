"""Compare installed skill hashes with the registry index.

Used by ``POST /check`` (the ``skill-update-check`` hook sends the lock
file) and by the ``check_skill_updates`` MCP tool (the agent sends the
sha256 of every file under ``.claude/skills/``, so no lock file is needed).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from awos_recruitment_mcp.history import HISTORY_FILE
from awos_recruitment_mcp.registry_index import combined_hash
from awos_recruitment_mcp.telemetry import track_client_event

UPDATE_COMMAND = "npx @provectusinc/awos-recruitment skill update"


@dataclass
class CheckResult:
    """Outcome of one update check.

    Attributes:
        outdated: Installed skills whose registry hash differs.
        removed: ``{name, replacement}`` for skills with a tombstone.
        unknown: Installed skills the registry does not know.
        up_to_date: Count of skills whose hash matches.
    """

    outdated: list[str] = field(default_factory=list)
    removed: list[dict[str, str | None]] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    up_to_date: int = 0

    @property
    def summary(self) -> str:
        """One line for the user, empty when there is nothing to report."""
        parts: list[str] = []
        if self.outdated:
            parts.append(
                f"{len(self.outdated)} skill{'s' if len(self.outdated) != 1 else ''} outdated "
                f"({', '.join(self.outdated)})"
            )
        if self.removed:
            names = ", ".join(
                f"{r['name']} -> {r['replacement']}" if r["replacement"] else str(r["name"])
                for r in self.removed
            )
            parts.append(
                f"{len(self.removed)} removed from registry ({names})"
            )
        if not parts:
            return ""
        return f"awos-recruitment: {'; '.join(parts)}. Run `{UPDATE_COMMAND}`."

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "outdated": self.outdated,
            "removed": self.removed,
            "unknown": self.unknown,
            "up_to_date": self.up_to_date,
            "command": UPDATE_COMMAND,
        }


def check_skills(
    installed: dict[str, str],
    index: dict[str, Any],
    skips: dict[str, str] | None = None,
) -> CheckResult:
    """Compare ``{skill name: lock hash}`` with a registry index.

    Args:
        installed: Skill names and the capability hash from the lock file.
        index: The document ``build_registry_index`` returns.
        skips: ``{skill name: registry hash the user skipped}`` from the lock
            file. A skill whose current registry hash was skipped counts as
            up to date until the registry moves on.

    Returns:
        A :class:`CheckResult` with names sorted.
    """
    skips = skips or {}
    result = CheckResult()
    registry_skills = index.get("skills", {})
    removed_skills = index.get("removed", {}).get("skills", {})

    for name in sorted(installed):
        if name in removed_skills:
            result.removed.append(
                {"name": name, "replacement": removed_skills[name].get("replacement")}
            )
        elif name not in registry_skills:
            result.unknown.append(name)
        elif (
            registry_skills[name]["hash"] != installed[name]
            and skips.get(name) != registry_skills[name]["hash"]
        ):
            result.outdated.append(name)
        else:
            result.up_to_date += 1

    return result


def track_check(project_id: str, result: CheckResult, source: str) -> None:
    """Emit ``capability_update_checked`` and one ``capability_removed_in_use`` per removed skill."""
    track_client_event(
        project_id,
        "capability_update_checked",
        {
            "source": source,
            "total": len(result.outdated) + len(result.removed) + len(result.unknown) + result.up_to_date,
            "outdated": len(result.outdated),
            "removed": len(result.removed),
        },
    )
    for removed in result.removed:
        track_client_event(
            project_id,
            "capability_removed_in_use",
            {
                "capability_name": str(removed["name"]),
                "capability_type": "skill",
                "has_replacement": removed["replacement"] is not None,
                "source": source,
            },
        )


# ---------------------------------------------------------------------------
# File-based check (no lock file needed): the agent sends sha256 per file
# ---------------------------------------------------------------------------

_SHASUM_LINE = re.compile(r"^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")
_SKILLS_SEGMENT = ".claude/skills/"


def parse_shasum_output(text: str) -> dict[str, dict[str, str]]:
    """Parse ``shasum -a 256`` / ``sha256sum`` output into ``{skill: {rel path: sha256}}``.

    Lines look like ``<sha256>  <path>``.  Only paths that contain
    ``.claude/skills/<name>/`` count; everything else is ignored.  Windows
    separators are accepted.
    """
    skills: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        match = _SHASUM_LINE.match(line)
        if not match:
            continue
        digest, path = match.group(1).lower(), match.group(2).replace("\\", "/")
        idx = path.find(_SKILLS_SEGMENT)
        if idx < 0:
            continue
        rest = path[idx + len(_SKILLS_SEGMENT):]
        name, _, rel_path = rest.partition("/")
        if not name or not rel_path:
            continue
        skills.setdefault(name, {})[rel_path] = digest
    return skills


def load_history(registry_path: str | Path) -> dict[str, Any]:
    """Return ``history.json`` from the registry directory, or an empty history."""
    history_file = Path(registry_path) / HISTORY_FILE
    if not history_file.is_file():
        return {"skills": {}}
    try:
        with open(history_file, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"skills": {}}


def parse_lock(lock_text: str | None) -> tuple[dict[str, str], dict[str, str], str | None]:
    """Read skips, bases and ``project_id`` from lock file text.

    Returns ``(skips, bases, project_id)``: ``skips`` maps a skill to the
    registry hash the user skipped, ``bases`` maps a skill to the registry
    hash its lock entry records (the version installed or merged). Malformed
    or missing text yields nothing: the check then reports every outdated
    skill, which is the safe default.
    """
    if not lock_text:
        return {}, {}, None
    try:
        lock = json.loads(lock_text)
    except ValueError:
        return {}, {}, None
    if not isinstance(lock, dict):
        return {}, {}, None
    skips: dict[str, str] = {}
    bases: dict[str, str] = {}
    for name, entry in (lock.get("skills") or {}).items():
        if not isinstance(entry, dict):
            continue
        skip = entry.get("skip")
        if isinstance(skip, dict) and isinstance(skip.get("hash"), str):
            skips[str(name)] = skip["hash"]
        if isinstance(entry.get("hash"), str):
            bases[str(name)] = entry["hash"]
    project_id = lock.get("project_id")
    return skips, bases, project_id if isinstance(project_id, str) else None


def skips_from_lock(lock_text: str | None) -> tuple[dict[str, str], str | None]:
    """Read ``{skill: skipped registry hash}`` and ``project_id`` from lock file text."""
    skips, _bases, project_id = parse_lock(lock_text)
    return skips, project_id


def check_files(
    skills: dict[str, dict[str, str]],
    index: dict[str, Any],
    history: dict[str, Any],
    skips: dict[str, str] | None = None,
    bases: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Classify installed skills from their file hashes.

    Args:
        skills: ``{skill name: {relative path: sha256}}`` from the project.
        index: The document ``build_registry_index`` returns.
        history: The document ``build_history`` returns (may be empty).

    Returns:
        One dict per skill, sorted by name: ``name``, ``state`` (``up-to-date``,
        ``outdated``, ``removed``, ``modified-or-unknown``, ``not-in-registry``),
        ``detail``, ``replacement``.
    """
    registry_skills = index.get("skills", {})
    removed_skills = index.get("removed", {}).get("skills", {})
    history_skills = history.get("skills", {})

    results: list[dict[str, Any]] = []
    for name in sorted(skills):
        local_hash = combined_hash(skills[name])
        entry: dict[str, Any] = {"name": name, "state": "", "detail": "", "replacement": None}

        if name in removed_skills:
            replacement = removed_skills[name].get("replacement")
            entry["state"] = "removed"
            entry["replacement"] = replacement
            entry["detail"] = (
                f"removed {removed_skills[name].get('removed')}; "
                + (f"install '{replacement}' instead" if replacement else "no replacement")
            )
        elif name not in registry_skills:
            entry["state"] = "not-in-registry"
            entry["detail"] = "the registry has no skill with this name"
        elif registry_skills[name]["hash"] == local_hash:
            entry["state"] = "up-to-date"
        elif (skips or {}).get(name) == registry_skills[name]["hash"]:
            entry["state"] = "skipped"
            entry["detail"] = "the user skipped this registry version"
        elif (bases or {}).get(name) == registry_skills[name]["hash"]:
            # The lock file says this copy is the current registry version
            # plus the user's own edits (installed or merged): nothing to offer.
            entry["state"] = "current-with-edits"
            entry["detail"] = "current registry version plus the user's own edits"
        else:
            versions = history_skills.get(name, [])
            position = next((i for i, v in enumerate(versions) if v["hash"] == local_hash), -1)
            if position >= 0:
                behind = len(versions) - 1 - position
                entry["state"] = "outdated"
                entry["detail"] = (
                    f"version from {versions[position]['from']}, "
                    f"{behind} version{'' if behind == 1 else 's'} behind"
                )
            else:
                entry["state"] = "modified-or-unknown"
                entry["detail"] = (
                    "differs from every registry version: local edits, or a version "
                    "the history does not know"
                )
        results.append(entry)
    return results


def summarize_files(results: list[dict[str, Any]]) -> str:
    """One line for the user; empty when nothing needs attention."""
    outdated = [r["name"] for r in results if r["state"] == "outdated"]
    removed = [r for r in results if r["state"] == "removed"]
    modified = [r["name"] for r in results if r["state"] == "modified-or-unknown"]
    parts: list[str] = []
    if outdated:
        parts.append(f"{len(outdated)} skill{'s' if len(outdated) != 1 else ''} outdated ({', '.join(outdated)})")
    if removed:
        names = ", ".join(
            f"{r['name']} -> {r['replacement']}" if r["replacement"] else str(r["name"]) for r in removed
        )
        parts.append(f"{len(removed)} removed from registry ({names})")
    if modified:
        parts.append(f"{len(modified)} with local edits or unknown version ({', '.join(modified)})")
    if not parts:
        return ""
    return f"awos-recruitment: {'; '.join(parts)}. Run `{UPDATE_COMMAND}`."


def result_from_files(results: list[dict[str, Any]]) -> CheckResult:
    """Fold a file-based check into a :class:`CheckResult` for telemetry."""
    return CheckResult(
        outdated=[r["name"] for r in results if r["state"] == "outdated"],
        removed=[
            {"name": r["name"], "replacement": r["replacement"]}
            for r in results
            if r["state"] == "removed"
        ],
        unknown=[r["name"] for r in results if r["state"] in ("not-in-registry", "modified-or-unknown")],
        up_to_date=sum(1 for r in results if r["state"] == "up-to-date"),
    )
