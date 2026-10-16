"""Compare installed skill hashes with the registry index.

Used by ``POST /check``, called by the ``skill-update-check`` hook with the
project's lock file.  Local edits cannot be seen from here: the CLI's
``skill status`` compares file by file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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


def check_skills(installed: dict[str, str], index: dict[str, Any]) -> CheckResult:
    """Compare ``{skill name: lock hash}`` with a registry index.

    Args:
        installed: Skill names and the capability hash from the lock file.
        index: The document ``build_registry_index`` returns.

    Returns:
        A :class:`CheckResult` with names sorted.
    """
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
        elif registry_skills[name]["hash"] != installed[name]:
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
