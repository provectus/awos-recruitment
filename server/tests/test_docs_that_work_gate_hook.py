"""Behavior tests for the docs-that-work-gate registry hook entrypoint.

These tests execute the actual registry script (pure POSIX sh + git, no
server code) with Bash tool-call JSON payloads on stdin inside scratch git
repositories, the same way Claude Code invokes it. Exit code 2 means
"block the commit", exit code 0 means "allow".
"""

import json
import subprocess
from pathlib import Path

import pytest

HOOK_SCRIPT: Path = (
    Path(__file__).resolve().parents[2]
    / "registry"
    / "hooks"
    / "docs-that-work-gate"
    / "docs-that-work-gate.sh"
)

COMMIT_PAYLOAD = json.dumps(
    {
        "tool_name": "Bash",
        "tool_input": {"command": 'git add -A && git commit -m "change"'},
    }
)


def run_hook(
    cwd: Path, stdin_text: str = COMMIT_PAYLOAD
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HOOK_SCRIPT)],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
    )


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, timeout=10
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A committed scratch repo: root README.md, server/CLAUDE.md, server/src/app.py."""
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@test")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("root docs\n")
    (tmp_path / "server" / "src").mkdir(parents=True)
    (tmp_path / "server" / "CLAUDE.md").write_text("server docs\n")
    (tmp_path / "server" / "src" / "app.py").write_text("code\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-m", "init")
    return tmp_path


def test_hook_script_exists_and_is_executable() -> None:
    """The registry entrypoint must exist with the executable bit set."""
    assert HOOK_SCRIPT.is_file(), f"Missing hook entrypoint: {HOOK_SCRIPT}"
    assert HOOK_SCRIPT.stat().st_mode & 0o111, (
        f"Hook entrypoint is not executable: {HOOK_SCRIPT}"
    )


def test_blocks_when_owning_docs_not_updated(repo: Path) -> None:
    """A code change under server/ with untouched server/CLAUDE.md blocks."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")

    result = run_hook(repo)

    assert result.returncode == 2, f"Expected block, got {result.returncode}"
    assert "server/CLAUDE.md" in result.stderr, (
        f"Expected stale doc named on stderr, got: {result.stderr!r}"
    )
    assert "docs-that-work" in result.stderr, (
        f"Expected the docs-that-work skill referenced, got: {result.stderr!r}"
    )


def test_block_message_instructs_install_when_skill_missing(repo: Path) -> None:
    """Without .claude/skills/docs-that-work, the message says to install it."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")

    result = run_hook(repo)

    assert result.returncode == 2, f"Expected block, got {result.returncode}"
    assert "npx @provectusinc/awos-recruitment skill docs-that-work" in result.stderr, (
        f"Expected install instruction on stderr, got: {result.stderr!r}"
    )


def test_block_message_demands_skill_invocation_when_installed(repo: Path) -> None:
    """With the skill installed, the message imperatively demands invoking it."""
    (repo / ".claude" / "skills" / "docs-that-work").mkdir(parents=True)
    (repo / "server" / "src" / "app.py").write_text("changed\n")

    result = run_hook(repo)

    assert result.returncode == 2, f"Expected block, got {result.returncode}"
    assert "MUST invoke the docs-that-work skill" in result.stderr, (
        f"Expected imperative skill instruction on stderr, got: {result.stderr!r}"
    )
    assert "npx @provectusinc/awos-recruitment" not in result.stderr, (
        f"Install instruction should be absent when skill exists, got: {result.stderr!r}"
    )


def test_allows_when_owning_docs_also_updated(repo: Path) -> None:
    """Updating the owning CLAUDE.md alongside the code change passes."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    (repo / "server" / "CLAUDE.md").write_text("updated docs\n")

    result = run_hook(repo)

    assert result.returncode == 0, (
        f"Expected allow, got {result.returncode}; stderr: {result.stderr}"
    )


def test_doc_only_change_set_passes(repo: Path) -> None:
    """A change set consisting only of doc files is never gated."""
    (repo / "server" / "CLAUDE.md").write_text("only docs changed\n")
    (repo / "README.md").write_text("also docs\n")

    result = run_hook(repo)

    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_unchanged_retry_passes_then_gate_rearms(repo: Path) -> None:
    """Block, identical retry passes via the marker, third attempt blocks again."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")

    first = run_hook(repo)
    assert first.returncode == 2, f"Expected initial block, got {first.returncode}"

    retry = run_hook(repo)
    assert retry.returncode == 0, (
        f"Expected unchanged retry to pass via marker, got {retry.returncode}"
    )

    third = run_hook(repo)
    assert third.returncode == 2, (
        f"Expected gate to re-arm after marker consumed, got {third.returncode}"
    )


def test_content_edit_after_block_invalidates_marker(repo: Path) -> None:
    """Editing file content between attempts re-blocks despite the marker."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    assert run_hook(repo).returncode == 2

    (repo / "server" / "src" / "app.py").write_text("changed again\n")

    result = run_hook(repo)
    assert result.returncode == 2, (
        f"Expected block after content edit, got {result.returncode}"
    )


def test_untracked_rewrite_after_block_invalidates_marker(repo: Path) -> None:
    """Rewriting an UNTRACKED file between attempts must re-block.

    Regression: `git diff HEAD` never sees untracked content and porcelain
    emits a content-independent `?? path`, so the checksum used to be
    byte-identical across a full rewrite of a new file.
    """
    (repo / "server" / "brand_new.py").write_text("brand new content v1\n")

    first = run_hook(repo)
    assert first.returncode == 2, "First attempt must block"

    (repo / "server" / "brand_new.py").write_text("totally different v2\n")

    second = run_hook(repo)
    assert second.returncode == 2, (
        "Rewritten untracked content must invalidate the acknowledgement"
    )


def test_unchanged_untracked_retry_still_passes(repo: Path) -> None:
    """Loop-breaker 2 must survive the fix: identical retry passes."""
    (repo / "server" / "brand_new.py").write_text("brand new content v1\n")

    first = run_hook(repo)
    assert first.returncode == 2

    second = run_hook(repo)
    assert second.returncode == 0, "Unchanged retry must still pass"


def test_nested_file_does_not_trigger_root_docs(repo: Path) -> None:
    """Root README.md does not own nested files without their own docs."""
    (repo / "lib").mkdir()
    (repo / "lib" / "util.py").write_text("code\n")

    result = run_hook(repo)

    assert result.returncode == 0, (
        f"Expected allow (no docs ancestor below root), got {result.returncode}; "
        f"stderr: {result.stderr}"
    )


def test_root_level_file_triggers_root_docs(repo: Path) -> None:
    """A file changed at the repo root is owned by the root README.md."""
    (repo / "Makefile").write_text("all:\n")

    result = run_hook(repo)

    assert result.returncode == 2, f"Expected block, got {result.returncode}"
    assert "README.md" in result.stderr, (
        f"Expected root README.md named on stderr, got: {result.stderr!r}"
    )


def test_clean_tree_passes(repo: Path) -> None:
    """Nothing to commit — nothing to gate."""
    result = run_hook(repo)
    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_non_commit_command_passes(repo: Path) -> None:
    """Bash commands without git commit are not gated."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "ls -la server/"}}
    )

    result = run_hook(repo, payload)

    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_outside_git_repo_passes(tmp_path: Path) -> None:
    """Fail open when the working directory is not a git repository."""
    result = run_hook(tmp_path)
    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_garbage_stdin_passes(repo: Path) -> None:
    """Unreadable payloads fail open."""
    result = run_hook(repo, "not json at all")
    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_description_mentioning_commit_does_not_trigger(repo: Path) -> None:
    """A non-commit command whose description mentions 'git commit' passes."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    payload = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": "ls -la",
                "description": "List files before I git commit them",
            },
        }
    )

    result = run_hook(repo, payload)

    assert result.returncode == 0, (
        f"Description text must not trigger the gate: {result.stderr}"
    )


def test_commit_command_with_description_still_gated(repo: Path) -> None:
    """A real commit command still blocks when a description is present."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    payload = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {
                "command": 'git add -A && git commit -m "x"',
                "description": "Commit the change",
            },
        }
    )

    result = run_hook(repo, payload)

    assert result.returncode == 2, "Real commit must still be gated"


def test_unborn_head_repo_blocks_and_marker_cycle_works(tmp_path: Path) -> None:
    """On an unborn HEAD (no commits yet) the checksum falls back to the
    staged diff (`git diff HEAD || git diff --cached`): block, then
    edit + re-stage re-blocks, then an identical retry passes.

    The SECOND run is the assertion that pins the `--cached` fallback:
    re-staging edited content leaves the porcelain status byte-identical
    (`A  server/app.py`) and adds no untracked files, so only the staged
    diff distinguishes the tree from the marker — without the fallback the
    checksum would match and the run would wrongly pass. The final run
    keeps marker-cycle coverage: the fresh marker written by the second
    block is consumed by an unchanged retry.

    Note: staging a doc alongside the code change would count it as "fresh"
    (any CLAUDE.md/README.md present in `git status` counts, regardless of
    commit history), so the code change's owning doc must be gitignored to
    stay out of the change set and trigger the block — see docs-that-work-gate.sh
    comment "Ownership rule" / loop-breaker 1.
    """
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@test")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "CLAUDE.md").write_text("docs\n")
    (tmp_path / ".gitignore").write_text("server/CLAUDE.md\n")
    (tmp_path / "server" / "app.py").write_text("code\n")
    git(tmp_path, "add", "-A")

    first = run_hook(tmp_path)
    assert first.returncode == 2, f"Expected block: {first.stderr}"

    (tmp_path / "server" / "app.py").write_text("edited\n")
    git(tmp_path, "add", "server/app.py")

    second = run_hook(tmp_path)
    assert second.returncode == 2, (
        "Edited staged content must re-block: porcelain is unchanged, so "
        "only the staged-diff fallback can detect the edit"
    )

    third = run_hook(tmp_path)
    assert third.returncode == 0, "Identical retry must pass via marker"


def test_payload_without_command_key_passes(repo: Path) -> None:
    """A payload with no tool_input.command fails open."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {}})

    result = run_hook(repo, payload)

    assert result.returncode == 0


def test_unwritable_git_dir_still_blocks_with_message(repo: Path) -> None:
    """A read-only .git must not turn the block into a silent exit 1.

    Exit 1 is non-blocking for Claude Code hooks; the gate must still exit 2
    and print the actionable message even when the marker cannot be written.
    """
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    git_dir = repo / ".git"
    git_dir.chmod(0o555)
    try:
        result = run_hook(repo)
    finally:
        git_dir.chmod(0o755)

    assert result.returncode == 2, (
        f"Expected block (2), got {result.returncode}: {result.stderr}"
    )
    assert "documentation may be stale" in result.stderr


def test_glob_metacharacter_filename_handled(repo: Path) -> None:
    """A changed path containing '*' must not be glob-expanded."""
    (repo / "server" / "src" / "weird*name.py").write_text("code\n")

    result = run_hook(repo)

    assert result.returncode == 2
    assert "server/CLAUDE.md" in result.stderr


def test_renamed_file_uses_new_path(repo: Path) -> None:
    """`git mv` porcelain (`R old -> new`) must resolve ownership by new path."""
    git(repo, "mv", "server/src/app.py", "server/src/renamed.py")

    result = run_hook(repo)

    assert result.returncode == 2
    assert "server/CLAUDE.md" in result.stderr


def test_deleted_owning_doc_climbs_to_ancestor(repo: Path) -> None:
    """Deleting server/CLAUDE.md while changing server code: the deleted doc
    cannot be 'fresh' (it no longer exists); ownership climbs to root README,
    which only owns root-level files — so nothing is stale and the change
    passes. Pins current behavior."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    git(repo, "rm", "-q", "server/CLAUDE.md")

    result = run_hook(repo)

    assert result.returncode == 0


def test_filename_with_space_still_blocks(repo: Path) -> None:
    """Porcelain C-quotes 'a b.py'; the gate must still block on presence."""
    (repo / "server" / "src" / "a b.py").write_text("code\n")

    result = run_hook(repo)

    assert result.returncode == 2
    assert "server/CLAUDE.md" in result.stderr
