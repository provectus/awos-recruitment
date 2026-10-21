"""MCP tool: tell the agent which installed skills are outdated, no lock file needed."""

from __future__ import annotations

from awos_recruitment_mcp.registry_index import build_registry_index
from awos_recruitment_mcp.server import config, mcp
from awos_recruitment_mcp.update_check import (
    UPDATE_COMMAND,
    check_files,
    load_history,
    parse_shasum_output,
    parse_lock,
    result_from_files,
    summarize_files,
    track_check,
)


@mcp.tool
async def check_skill_updates(
    file_hashes: str,
    lock: str | None = None,
    project_id: str | None = None,
) -> dict:
    """Check whether the skills installed in this project are outdated or removed from the registry.

    Call this at most ONCE per session, and only when the user runs
    /awos:tech, /awos:hire or /awos:implement (before the command's own
    work) or asks about skills, versions or updates. Do not call it on other
    messages. First run this read-only command and pass its full output as
    `file_hashes`:

        shasum -a 256 .claude/skills/*/* .claude/skills/*/*/*

    Run it as its own command, not chained with other commands. `sha256sum`
    works too; "Is a directory" lines and a non-zero exit are expected. If the
    returned `summary` is not empty, run `npx @provectusinc/awos-recruitment
    skill diff <names>` and tell the user in one line what is outdated and,
    per skill, in two or three short points what the update would change
    (including their own edits that it would remove); then offer to update
    before you continue. Do not paste the diff. For a skill in state
    `modified-or-unknown`, also offer to merge (see the server instructions). If it is empty, say nothing about it. Do not
    update on your own: run `command` only after the user agrees. If the user
    declines, offer `skill skip <names>` so this version is not offered again,
    and run it if they agree. Pass the lock file text as `lock` when it exists.

    Args:
        file_hashes: Raw output of `shasum -a 256` / `sha256sum` over the files
            under `.claude/skills/`. One `<sha256>  <path>` per line.
        lock: Optional full text of `.claude/awos-recruitment.lock.json`, when the
            file exists. Skills whose current registry version the user
            skipped (`skill skip`) are then left out of the summary.
        project_id: Optional `project_id` from the lock file, for anonymous
            telemetry. Read from `lock` when not given.
    """
    skills = parse_shasum_output(file_hashes)
    if not skills:
        return {
            "summary": "",
            "skills": [],
            "command": UPDATE_COMMAND,
            "note": "No `.claude/skills/<name>/<file>` paths found in file_hashes.",
        }

    skips, bases, lock_project_id = parse_lock(lock)
    project_id = project_id or lock_project_id

    index = build_registry_index(config.registry_path)
    history = load_history(config.registry_path)
    results = check_files(skills, index, history, skips, bases)

    if project_id is not None:
        track_check(project_id, result_from_files(results), source="mcp")

    return {
        "summary": summarize_files(results),
        "skills": results,
        "command": UPDATE_COMMAND,
    }
