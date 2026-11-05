"""Behavior tests for registry/hooks/format-on-edit/format-on-edit.sh.

Runs the real script via subprocess. Formatters are stub scripts that
record their arguments, so the tests need no Node, Python or Go tooling.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[2]
    / "registry"
    / "hooks"
    / "format-on-edit"
    / "format-on-edit.sh"
)


def _stub(path: Path, log: Path, exit_code: int = 0) -> None:
    """Write an executable that appends its name and args to *log*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'#!/bin/sh\necho "$(basename "$0") $*" >> "{log}"\nexit {exit_code}\n'
    )
    path.chmod(0o755)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    return root


@pytest.fixture
def log(tmp_path):
    return tmp_path / "calls.log"


def run_hook(project: Path, payload: str, path_dirs: list[Path] | None = None, **env_extra):
    path = os.pathsep.join([str(p) for p in path_dirs or []] + ["/usr/bin", "/bin"])
    env = {"PATH": path, "CLAUDE_PROJECT_DIR": str(project), **env_extra}
    return subprocess.run(
        [str(HOOK)], input=payload, capture_output=True, text=True, env=env, timeout=30
    )


def edit_payload(file_path: Path, tool: str = "Edit") -> str:
    return json.dumps(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": str(file_path), "old_string": "a", "new_string": "b"},
            "tool_response": {"filePath": str(file_path), "success": True},
        }
    )


def calls(log: Path) -> list[str]:
    return log.read_text().splitlines() if log.exists() else []


def test_formats_ts_file_with_local_prettier(project, log):
    _stub(project / "node_modules" / ".bin" / "prettier", log)
    target = project / "src" / "app.ts"
    target.write_text("const a=1\n")

    result = run_hook(project, edit_payload(target))

    assert result.returncode == 0
    assert result.stdout == ""
    assert calls(log) == [f"prettier --write --ignore-unknown {target}"]


def test_prefers_biome_when_the_project_configures_it(project, log):
    _stub(project / "node_modules" / ".bin" / "prettier", log)
    _stub(project / "node_modules" / ".bin" / "biome", log)
    (project / "biome.json").write_text("{}")
    target = project / "src" / "app.tsx"
    target.write_text("x")

    run_hook(project, edit_payload(target, tool="Write"))

    assert calls(log) == [f"biome format --write {target}"]


def test_python_uses_ruff_only_with_ruff_config(project, log):
    _stub(project / ".venv" / "bin" / "ruff", log)
    _stub(project / ".venv" / "bin" / "black", log)
    target = project / "src" / "main.py"
    target.write_text("x=1\n")

    run_hook(project, edit_payload(target))
    assert calls(log) == [f"black -q {target}"]

    log.unlink()
    (project / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
    run_hook(project, edit_payload(target))
    assert calls(log) == [f"ruff format {target}"]


def test_go_uses_gofmt_from_path(project, log, tmp_path):
    tools = tmp_path / "tools"
    _stub(tools / "gofmt", log)
    target = project / "main.go"
    target.write_text("package main\n")

    run_hook(project, edit_payload(target), path_dirs=[tools])

    assert calls(log) == [f"gofmt -w {target}"]


def test_terraform_falls_back_to_tofu(project, log, tmp_path):
    tools = tmp_path / "tools"
    _stub(tools / "tofu", log)
    target = project / "main.tf"
    target.write_text('resource "x" "y" {}\n')

    run_hook(project, edit_payload(target), path_dirs=[tools])

    assert calls(log) == [f"tofu fmt {target}"]


def test_no_formatter_installed_does_nothing(project, log):
    target = project / "src" / "app.ts"
    target.write_text("x")

    result = run_hook(project, edit_payload(target))

    assert result.returncode == 0
    assert calls(log) == []


def test_never_uses_a_global_prettier(project, log, tmp_path):
    tools = tmp_path / "tools"
    _stub(tools / "prettier", log)
    target = project / "src" / "app.ts"
    target.write_text("x")

    run_hook(project, edit_payload(target), path_dirs=[tools])

    assert calls(log) == []


def test_skips_files_outside_the_project(project, log, tmp_path):
    _stub(project / "node_modules" / ".bin" / "prettier", log)
    outside = tmp_path / "elsewhere.ts"
    outside.write_text("x")

    run_hook(project, edit_payload(outside))

    assert calls(log) == []


def test_skips_unknown_file_types(project, log):
    _stub(project / "node_modules" / ".bin" / "prettier", log)
    target = project / "src" / "script.rb"
    target.write_text("puts 1\n")

    run_hook(project, edit_payload(target))

    assert calls(log) == []


def test_failing_formatter_does_not_fail_the_hook(project, log):
    _stub(project / "node_modules" / ".bin" / "prettier", log, exit_code=2)
    target = project / "src" / "broken.ts"
    target.write_text("const = ;\n")

    result = run_hook(project, edit_payload(target))

    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert len(calls(log)) == 1


def test_quoted_file_path_inside_content_is_ignored(project, log):
    _stub(project / "node_modules" / ".bin" / "prettier", log)
    target = project / "src" / "real.ts"
    target.write_text("x")
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": '{"file_path": "/etc/passwd"}',
            },
        }
    )

    run_hook(project, payload)

    assert calls(log) == [f"prettier --write --ignore-unknown {target}"]


@pytest.mark.parametrize("payload", ["", "not json", '{"tool_input": {}}'])
def test_malformed_input_exits_zero(project, log, payload):
    _stub(project / "node_modules" / ".bin" / "prettier", log)

    result = run_hook(project, payload)

    assert result.returncode == 0
    assert calls(log) == []


def test_can_be_turned_off(project, log):
    _stub(project / "node_modules" / ".bin" / "prettier", log)
    target = project / "src" / "app.ts"
    target.write_text("x")

    run_hook(project, edit_payload(target), AWOS_FORMAT_ON_EDIT="0")

    assert calls(log) == []
