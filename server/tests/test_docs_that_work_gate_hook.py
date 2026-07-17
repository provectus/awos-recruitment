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

HOOK_SCRIPT = (
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


def run_hook(cwd: Path, stdin_text: str = COMMIT_PAYLOAD) -> subprocess.CompletedProcess:
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


def test_hook_script_exists_and_is_executable():
    """The registry entrypoint must exist with the executable bit set."""
    assert HOOK_SCRIPT.is_file(), f"Missing hook entrypoint: {HOOK_SCRIPT}"
    assert HOOK_SCRIPT.stat().st_mode & 0o111, (
        f"Hook entrypoint is not executable: {HOOK_SCRIPT}"
    )


def test_blocks_when_owning_docs_not_updated(repo: Path):
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


def test_allows_when_owning_docs_also_updated(repo: Path):
    """Updating the owning CLAUDE.md alongside the code change passes."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    (repo / "server" / "CLAUDE.md").write_text("updated docs\n")

    result = run_hook(repo)

    assert result.returncode == 0, (
        f"Expected allow, got {result.returncode}; stderr: {result.stderr}"
    )


def test_doc_only_change_set_passes(repo: Path):
    """A change set consisting only of doc files is never gated."""
    (repo / "server" / "CLAUDE.md").write_text("only docs changed\n")
    (repo / "README.md").write_text("also docs\n")

    result = run_hook(repo)

    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_unchanged_retry_passes_then_gate_rearms(repo: Path):
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


def test_content_edit_after_block_invalidates_marker(repo: Path):
    """Editing file content between attempts re-blocks despite the marker."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    assert run_hook(repo).returncode == 2

    (repo / "server" / "src" / "app.py").write_text("changed again\n")

    result = run_hook(repo)
    assert result.returncode == 2, (
        f"Expected block after content edit, got {result.returncode}"
    )


def test_nested_file_does_not_trigger_root_docs(repo: Path):
    """Root README.md does not own nested files without their own docs."""
    (repo / "lib").mkdir()
    (repo / "lib" / "util.py").write_text("code\n")

    result = run_hook(repo)

    assert result.returncode == 0, (
        f"Expected allow (no docs ancestor below root), got {result.returncode}; "
        f"stderr: {result.stderr}"
    )


def test_root_level_file_triggers_root_docs(repo: Path):
    """A file changed at the repo root is owned by the root README.md."""
    (repo / "Makefile").write_text("all:\n")

    result = run_hook(repo)

    assert result.returncode == 2, f"Expected block, got {result.returncode}"
    assert "README.md" in result.stderr, (
        f"Expected root README.md named on stderr, got: {result.stderr!r}"
    )


def test_clean_tree_passes(repo: Path):
    """Nothing to commit — nothing to gate."""
    result = run_hook(repo)
    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_non_commit_command_passes(repo: Path):
    """Bash commands without git commit are not gated."""
    (repo / "server" / "src" / "app.py").write_text("changed\n")
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "ls -la server/"}}
    )

    result = run_hook(repo, payload)

    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_outside_git_repo_passes(tmp_path: Path):
    """Fail open when the working directory is not a git repository."""
    result = run_hook(tmp_path)
    assert result.returncode == 0, f"Expected allow, got {result.returncode}"


def test_garbage_stdin_passes(repo: Path):
    """Unreadable payloads fail open."""
    result = run_hook(repo, "not json at all")
    assert result.returncode == 0, f"Expected allow, got {result.returncode}"
